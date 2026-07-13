import io
import re
import os
import math
import struct
import wave
import asyncio
import logging
import threading
from typing import Union

import numpy as np
import soundfile as sf
import onnxruntime as ort

from backend import config
from backend.utils.retry import retry

logger = logging.getLogger(__name__)

_HF_TOKEN = config.HF_TOKEN or os.environ.get("HF_TOKEN", "")

try:
    from kokoro_onnx import Kokoro
    _HAS_KOKORO = True
except ImportError:
    _HAS_KOKORO = False
    logger.warning("kokoro_onnx not installed, will use gTTS fallback")

try:
    from huggingface_hub import InferenceClient
    _HAS_HF_CLIENT = True
except ImportError:
    _HAS_HF_CLIENT = False

try:
    from gtts import gTTS as _gTTS
    _HAS_GTTS = True
except ImportError:
    _HAS_GTTS = False

KOKORO_MODEL_PATH = os.getenv("KOKORO_MODEL_PATH", "backend/static/kokoro-v1.0.onnx")
KOKORO_VOICES_PATH = os.getenv("KOKORO_VOICES_PATH", "backend/static/voices-v1.0.bin")

VoiceParam = Union[str, np.ndarray]

# Hard-cap ONNX threads for 2 vCPU HF Spaces environment
_ONNX_OPTIONS = ort.SessionOptions()
_ONNX_OPTIONS.intra_op_num_threads = 1
_ONNX_OPTIONS.inter_op_num_threads = 1
_ONNX_OPTIONS.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

# Audio feedback tones
_ACK_SAMPLE_RATE = 24000
_ACK_DURATION = 0.08


def _generate_beep(duration: float = _ACK_DURATION, frequency: float = 660.0) -> bytes:
    """Generate a short sine-wave beep as WAV bytes for audio feedback.

    Adapted from thevickypedia/Jarvis acknowledgment sound pattern.
    Used to indicate start/end of voice interaction.
    """
    num_samples = int(_ACK_SAMPLE_RATE * duration)
    samples = []
    for i in range(num_samples):
        sample = math.sin(2 * math.pi * frequency * i / _ACK_SAMPLE_RATE)
        sample = int(max(-32768, min(32767, sample * 0.25 * 32767)))
        samples.append(sample)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(_ACK_SAMPLE_RATE)
        wf.writeframes(struct.pack(f"<{num_samples}h", *samples))
    return buf.getvalue()


def generate_ack_beep() -> bytes:
    """Short 660Hz beep — played when speech processing starts."""
    return _generate_beep(0.08, 660.0)


def generate_done_beep() -> bytes:
    """Short 880Hz beep — played when speech processing completes."""
    return _generate_beep(0.08, 880.0)


def _mp3_to_wav(mp3_bytes: bytes) -> bytes:
    """Convert MP3 bytes to WAV bytes using ffmpeg subprocess.

    ffmpeg is installed in the Dockerfile (apt-get install ffmpeg).
    This avoids the pydub dependency and produces a proper WAV container
    that browsers can decode with Web Audio API decodeAudioData().
    Falls back to raw MP3 bytes if ffmpeg is unavailable.
    """
    import subprocess
    import tempfile

    try:
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_in:
            tmp_in.write(mp3_bytes)
            tmp_in_path = tmp_in.name

        tmp_out_path = tmp_in_path.replace(".mp3", ".wav")

        result = subprocess.run(
            ["ffmpeg", "-y", "-i", tmp_in_path, "-ar", "22050", "-ac", "1", "-f", "wav", tmp_out_path],
            capture_output=True,
            timeout=15,
        )

        if result.returncode == 0:
            with open(tmp_out_path, "rb") as f:
                wav_bytes = f.read()
            os.unlink(tmp_in_path)
            os.unlink(tmp_out_path)
            return wav_bytes
        else:
            logger.warning(f"ffmpeg MP3→WAV failed: {result.stderr.decode()[:200]}")

    except Exception as e:
        logger.warning(f"MP3→WAV conversion error: {e}")
    finally:
        for p in (tmp_in_path if "tmp_in_path" in dir() else None,
                  tmp_out_path if "tmp_out_path" in dir() else None):
            if p and os.path.exists(p):
                try:
                    os.unlink(p)
                except Exception:
                    pass

    # Fallback: return raw MP3 — browser may still decode it
    return mp3_bytes


def _kokoro_invoke_isolated(engine, sentence: str, voice, lang_code: str):
    """
    Run Kokoro in a true isolated thread that absorbs ALL exceptions
    including C-level StopIteration that bypasses Python try/except.

    This function is called by asyncio's run_in_executor. The inner
    threading.Thread acts as an impermeable exception barrier: any
    BaseException (including StopIteration from C extensions) raised
    inside the thread is swallowed, so the executor thread itself
    always returns normally — never poisoning the asyncio Future.
    """
    result_holder = [None]

    def _inner():
        try:
            r = engine.create(sentence, voice, 1.0, lang_code)
            # Handle both generator and direct-return Kokoro API variants
            if hasattr(r, '__iter__') and not isinstance(r, (tuple, np.ndarray)):
                for item in r:  # for-loop internally handles StopIteration
                    result_holder[0] = item
                    break
            else:
                result_holder[0] = r
        except BaseException:
            # Swallow everything — StopIteration, RuntimeError, anything.
            pass

    t = threading.Thread(target=_inner, daemon=True)
    t.start()
    t.join(timeout=12.0)  # 12s hard cap per sentence
    return result_holder[0]


class TTSService:
    def __init__(self):
        self.engine = None
        self._loaded = False
        self._hf_client = None

        if _HAS_HF_CLIENT and _HF_TOKEN:
            try:
                self._hf_client = InferenceClient(token=_HF_TOKEN)
                logger.info("HF Inference API TTS client ready")
            except Exception as e:
                logger.warning(f"HF Inference client init failed: {e}")

    @retry(attempts=2, interval=2.0, backoff=1.0)
    def _load_engine(self):
        """Load Kokoro engine with retry (model files may not be ready on first attempt)."""
        if not _HAS_KOKORO:
            raise RuntimeError("kokoro_onnx not installed")
        self.engine = Kokoro(KOKORO_MODEL_PATH, KOKORO_VOICES_PATH)
        self._loaded = True
        logger.info("Kokoro-ONNX TTS engine loaded")

    def load_model(self):
        if self._loaded:
            return True
        try:
            self._load_engine()
            return True
        except Exception as e:
            logger.warning(f"Kokoro TTS unavailable ({e}), trying HF API or gTTS")
            return False

    def is_available(self) -> bool:
        return self._loaded or self._hf_client is not None or _HAS_GTTS

    async def stream_speech(self, text: str, voice: VoiceParam, send_fn, lang: str = "eng"):
        """
        Stream TTS audio.
        Priority: local Kokoro → HF Inference API → gTTS (via ffmpeg WAV conversion)
        """
        if not text or not text.strip():
            return

        is_female = False
        if isinstance(voice, str) and ("f_" in voice.lower() or "veronica" in voice.lower()):
            is_female = True

        lang_config = {
            "eng": {"kokoro_lang": "en-us", "kokoro_voice": voice,                                 "gtts_lang": "en",    "mms_model": "facebook/mms-tts-eng"},
            "hin": {"kokoro_lang": "hi",    "kokoro_voice": "hf_alpha" if is_female else "hm_omega", "gtts_lang": "hi",    "mms_model": "facebook/mms-tts-hin"},
            "spa": {"kokoro_lang": "es",    "kokoro_voice": "ef_dora" if is_female else "em_santa",  "gtts_lang": "es",    "mms_model": "facebook/mms-tts-spa"},
            "z":   {"kokoro_lang": "zh",    "kokoro_voice": "zf_xiaobei" if is_female else "zm_yunjie","gtts_lang": "zh-tw", "mms_model": "facebook/mms-tts-cmn"},
        }
        cfg = lang_config.get(lang, lang_config["eng"])

        if self._loaded and self.engine:
            await self._stream_kokoro(text, cfg["kokoro_voice"], send_fn, cfg["kokoro_lang"], cfg["gtts_lang"])
        elif self._hf_client is not None:
            await self._stream_hf(text, cfg["mms_model"], send_fn, cfg["gtts_lang"])
        elif _HAS_GTTS:
            await self._stream_gtts(text, send_fn, cfg["gtts_lang"])
        else:
            logger.warning("No TTS engine available")

    async def _stream_kokoro(self, text: str, voice: VoiceParam, send_fn, lang_code: str = "en-us", gtts_lang: str = "en"):
        """
        Kokoro ONNX TTS with bulletproof StopIteration isolation.

        Uses _kokoro_invoke_isolated() which wraps Kokoro in a daemon Thread.
        This is the only reliable way to prevent StopIteration from Kokoro's
        internal C generator from poisoning the asyncio Future chain in
        Python 3.10 + uvloop. asyncio.to_thread alone is insufficient because
        uvloop's _chain_future._set_state rejects StopIteration at the C level
        before Python try/except can intercept it.
        """
        sentences = re.split(r'(?<=[.!?])\s+', text.replace("\n", " "))
        produced_audio = False

        loop = asyncio.get_event_loop()

        for sentence in sentences:
            if not sentence.strip():
                continue
            try:
                # Use run_in_executor with _kokoro_invoke_isolated.
                # That function internally uses threading.Thread so StopIteration
                # is absorbed at the thread boundary and never reaches asyncio.
                result = await asyncio.wait_for(
                    loop.run_in_executor(
                        None,
                        _kokoro_invoke_isolated,
                        self.engine, sentence, voice, lang_code
                    ),
                    timeout=15.0
                )

                if result is None:
                    continue

                samples, sample_rate = result
                byte_io = io.BytesIO()
                sf.write(byte_io, samples, sample_rate, format="WAV", subtype="PCM_16")
                wav_bytes = byte_io.getvalue()
                if callable(send_fn):
                    await send_fn(wav_bytes)
                produced_audio = True
                await asyncio.sleep(0.01)

            except asyncio.TimeoutError:
                logger.warning(f"Kokoro timed out on sentence: {sentence[:40]}")
            except Exception as e:
                logger.error(f"Kokoro sentence error: {e}")

        if not produced_audio:
            logger.warning("Kokoro produced no audio — falling back to gTTS")
            await self._stream_gtts(text, send_fn, gtts_lang)

    async def _stream_gtts(self, text: str, send_fn, lang_code: str = "en"):
        """gTTS fallback — MP3 converted to WAV via ffmpeg for browser compatibility."""
        try:
            tts = _gTTS(text=text, lang=lang_code)
            mp3_buf = io.BytesIO()
            await asyncio.to_thread(tts.write_to_fp, mp3_buf)
            mp3_buf.seek(0)
            mp3_bytes = mp3_buf.read()

            # Convert MP3 → WAV using ffmpeg so Web Audio API can decode it
            wav_bytes = await asyncio.to_thread(_mp3_to_wav, mp3_bytes)

            if callable(send_fn):
                await send_fn(wav_bytes)
        except Exception as e:
            logger.error(f"gTTS error: {e}")

    async def _stream_hf(self, text: str, mms_model: str, send_fn, gtts_lang_code: str = "en"):
        """HF Inference API TTS — returns a complete WAV blob per call."""
        audio_bytes = None
        try:
            audio_bytes = await asyncio.wait_for(
                asyncio.to_thread(
                    self._hf_client.text_to_speech,
                    text, model=mms_model,
                ),
                timeout=20.0
            )
        except Exception as e:
            logger.warning(f"HF TTS {mms_model} failed: {e}")

        if audio_bytes and callable(send_fn):
            await send_fn(audio_bytes)
            return

        if _HAS_GTTS:
            logger.info("HF TTS failed, falling back to gTTS")
            await self._stream_gtts(text, send_fn, gtts_lang_code)

    def create_custom_persona(self, voice_1_vec, voice_2_vec, alpha=0.5):
        return (1.0 - alpha) * voice_1_vec + (alpha * voice_2_vec)


tts_service = TTSService()
