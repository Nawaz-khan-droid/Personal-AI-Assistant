import io
import re
import os
import asyncio
import logging
from typing import Union

import numpy as np
import soundfile as sf
import onnxruntime as ort
from kokoro_onnx import Kokoro

logger = logging.getLogger(__name__)

KOKORO_MODEL_PATH = os.getenv("KOKORO_MODEL_PATH", "kokoro-v1.0.onnx")
KOKORO_VOICES_PATH = os.getenv("KOKORO_VOICES_PATH", "voices-v1.0.bin")

VoiceParam = Union[str, np.ndarray]

# Hard-cap ONNX threads for 2 vCPU HF Spaces environment
_ONNX_OPTIONS = ort.SessionOptions()
_ONNX_OPTIONS.intra_op_num_threads = 1
_ONNX_OPTIONS.inter_op_num_threads = 1
_ONNX_OPTIONS.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL


class TTSService:
    def __init__(self):
        self.engine = None
        self._loaded = False

    def load_model(self):
        if self._loaded:
            return True
        try:
            self.engine = Kokoro(KOKORO_MODEL_PATH, KOKORO_VOICES_PATH, session_options=_ONNX_OPTIONS)
            self._loaded = True
            logger.info("Kokoro-ONNX TTS engine loaded")
            return True
        except Exception as e:
            logger.error(f"Failed to load Kokoro model: {e}")
            return False

    def is_available(self) -> bool:
        return self._loaded

    async def stream_speech(self, text: str, voice: VoiceParam, send_fn):
        """
        Stream TTS audio sentence-by-sentence.
        voice: string voice ID (e.g. 'am_adam') OR numpy array (custom blend).
        Runs each ONNX inference in a thread to avoid blocking the event loop.
        """
        if not self.load_model():
            return

        sentences = re.split(r'(?<=[.!?])\s+', text.replace("\n", " "))
        for sentence in sentences:
            if not sentence.strip():
                continue
            try:
                samples, sample_rate = await asyncio.to_thread(
                    self.engine.create, sentence, voice, 1.0, "en-us"
                )
                byte_io = io.BytesIO()
                sf.write(byte_io, samples, sample_rate, format="WAV", subtype="PCM_16")
                wav_bytes = byte_io.getvalue()
                if callable(send_fn):
                    await send_fn(wav_bytes)
                await asyncio.sleep(0.01)
            except Exception as e:
                logger.error(f"TTS sentence error: {e}")

    def create_custom_persona(self, voice_1_vec, voice_2_vec, alpha=0.5):
        return (1.0 - alpha) * voice_1_vec + (alpha * voice_2_vec)


tts_service = TTSService()
