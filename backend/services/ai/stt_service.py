import os
import asyncio
import logging

import numpy as np

from backend import config
from backend.utils.retry import retry
from backend.utils.timeout import timeout, FunctionTimeoutError

logger = logging.getLogger(__name__)

_HF_TOKEN = config.HF_TOKEN or os.environ.get("HF_TOKEN", "")

try:
    from huggingface_hub import InferenceClient
    _HAS_HF_CLIENT = True
except ImportError:
    _HAS_HF_CLIENT = False

try:
    from moonshine_onnx import MoonshineOnnxModel
    from moonshine_onnx.transcribe import load_tokenizer as _load_tokenizer
    _HAS_MOONSHINE = True
except ImportError:
    _HAS_MOONSHINE = False


class STTService:
    def __init__(self):
        self.model = None
        self.decode = None
        self._hf_client = None

        if _HAS_HF_CLIENT and _HF_TOKEN:
            try:
                self._hf_client = InferenceClient(token=_HF_TOKEN)
                logger.info("HF Inference API STT client ready (whisper-tiny.en)")
            except Exception as e:
                logger.warning(f"HF Inference client init failed: {e}")

        if _HAS_MOONSHINE:
            try:
                self.model = MoonshineOnnxModel(model_name="tiny")
                self.decode = _load_tokenizer().decode_batch
                logger.info("Moonshine ONNX STT model loaded (tiny) — local fallback")
            except Exception as e:
                logger.error(f"Failed to load Moonshine model: {e}")

    def is_available(self) -> bool:
        return self._hf_client is not None or self.model is not None

    async def _transcribe_hf(self, audio_bytes: bytes) -> str:
        """Try HF Inference API whisper-tiny.en first."""
        if not self._hf_client:
            return ""
        try:
            result = await asyncio.to_thread(
                self._hf_client.automatic_speech_recognition,
                audio_bytes,
                model="openai/whisper-tiny.en",
            )
            text = getattr(result, "text", None) or (result if isinstance(result, str) else "")
            return text.strip()
        except Exception as e:
            logger.warning(f"HF STT failed: {e}")
            return ""

    async def _transcribe_local(self, audio_bytes: bytes) -> str:
        """Local Moonshine fallback."""
        if not self.model:
            return ""
        audio_np = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        try:
            tokens = await timeout(
                30, asyncio.to_thread, self.model.generate, audio_np[None, ...]
            )
            if self.decode:
                text = self.decode(tokens)[0]
            else:
                text = " ".join(str(t) for t in tokens[0])
            return text.strip() if text else ""
        except Exception as e:
            logger.error(f"Local STT failed: {e}")
            return ""

    async def transcribe(self, audio_bytes: bytes) -> str:
        text = await self._transcribe_hf(audio_bytes)
        if text:
            return text
        return await self._transcribe_local(audio_bytes)

    async def transcribe_with_confidence(self, audio_bytes: bytes) -> tuple:
        audio_np = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        energy = float(np.sqrt(np.mean(audio_np ** 2)))

        text = await self.transcribe(audio_bytes)
        if not text:
            return "", 0.0

        energy_conf = min(1.0, energy * 8)
        length_conf = min(1.0, len(text) / 25.0)
        diversity = len(set(text.lower())) / max(1, len(text))
        diversity_conf = min(1.0, diversity * 3.0)

        confidence = 0.25 * energy_conf + 0.40 * length_conf + 0.35 * diversity_conf
        return text, round(min(1.0, confidence), 3)


stt_service = STTService()
