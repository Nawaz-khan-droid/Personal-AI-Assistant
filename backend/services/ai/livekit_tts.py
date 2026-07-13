"""
Kokoro ONNX TTS for LiveKit agents v1.6+
Uses quantized int8 model for fast startup (<3s).
"""
import asyncio
import logging
import re
from dataclasses import dataclass

import numpy as np

from livekit import rtc
from livekit.agents import tts
from livekit.agents.tts import AudioEmitter
from livekit.agents.types import APIConnectOptions, DEFAULT_API_CONNECT_OPTIONS

try:
    from kokoro_onnx import Kokoro
    KOKORO_AVAILABLE = True
except ImportError:
    KOKORO_AVAILABLE = False

logger = logging.getLogger("livekit.tts.kokoro")

SAMPLE_RATE = 24000


@dataclass
class KokoroOptions:
    model_path:  str = "backend/static/kokoro-v1.0.int8.onnx"
    voices_path: str = "backend/static/voices-v1.0.bin"
    voice:       str = "am_adam"
    lang:        str = "en-us"
    speed:       float = 1.0


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r'(?<=[.!?])\s+', text.strip())
    return [p.strip() for p in parts if p.strip()]


class KokoroStream(tts.ChunkedStream):

    def __init__(self, *, tts_instance: "KokoroTTS", input_text: str,
                 conn_options: APIConnectOptions):
        super().__init__(tts=tts_instance, input_text=input_text, conn_options=conn_options)
        self._kokoro = tts_instance

    async def _run(self, output_emitter: AudioEmitter) -> None:
        sentences = _split_sentences(self._input_text)
        if not sentences:
            return

        for sentence in sentences:
            try:
                samples, sr = await asyncio.to_thread(
                    self._kokoro._synthesize_sentence, sentence
                )
            except asyncio.CancelledError:
                logger.debug("TTS cancelled mid-sentence (barge-in)")
                raise
            except Exception as e:
                logger.error(f"Kokoro synthesis error: {e}", exc_info=True)
                continue

            if sr != SAMPLE_RATE:
                ratio = SAMPLE_RATE / sr
                new_len = int(len(samples) * ratio)
                samples = np.interp(
                    np.linspace(0, len(samples) - 1, new_len),
                    np.arange(len(samples)),
                    samples
                ).astype(np.float32)

            audio_int16 = (np.clip(samples, -1.0, 1.0) * 32767).astype(np.int16)

            frame = rtc.AudioFrame(
                data=audio_int16.tobytes(),
                sample_rate=SAMPLE_RATE,
                num_channels=1,
                samples_per_channel=len(audio_int16),
            )
            output_emitter.push(frame)

        output_emitter.end_input()


class KokoroTTS(tts.TTS):
    def __init__(self, opts: KokoroOptions = KokoroOptions()):
        super().__init__(
            capabilities=tts.TTSCapabilities(streaming=False),
            sample_rate=SAMPLE_RATE,
            num_channels=1,
        )
        self.opts = opts

        if not KOKORO_AVAILABLE:
            raise ImportError("kokoro_onnx not installed. Run: pip install kokoro-onnx")

        logger.info(f"Loading Kokoro model: {opts.model_path}")
        self._model = Kokoro(opts.model_path, opts.voices_path)
        logger.info("Kokoro TTS model loaded.")

    def _synthesize_sentence(self, text: str):
        samples, sr = self._model.create(
            text,
            voice=self.opts.voice,
            speed=self.opts.speed,
            lang=self.opts.lang,
        )
        return samples, sr

    def synthesize(
        self,
        text: str,
        *,
        conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS,
    ) -> KokoroStream:
        return KokoroStream(
            tts_instance=self,
            input_text=text,
            conn_options=conn_options,
        )
