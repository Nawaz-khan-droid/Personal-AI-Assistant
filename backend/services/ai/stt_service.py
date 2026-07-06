import asyncio
import logging

import numpy as np

logger = logging.getLogger(__name__)

try:
    import moonshine
    _HAS_MOONSHINE = True
except ImportError:
    logger.warning("moonshine not installed. STT will use fallback.")
    _HAS_MOONSHINE = False


class STTService:
    def __init__(self):
        self.model = None
        if _HAS_MOONSHINE:
            try:
                self.model = moonshine.load_model("moonshine/tiny")
                logger.info("Moonshine STT model loaded (tiny, ~26MB)")
            except Exception as e:
                logger.error(f"Failed to load Moonshine model: {e}")

    def is_available(self) -> bool:
        return self.model is not None

    async def transcribe(self, audio_bytes: bytes) -> str:
        """
        Transcribe raw PCM Int16 bytes to text.
        Runs the ONNX inference in a thread to avoid blocking the event loop.
        """
        if not self.model:
            logger.warning("STT called but model not loaded")
            return ""
        try:
            audio_np = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            result = await asyncio.to_thread(self.model.transcribe, audio_np)
            return result.strip() if result else ""
        except Exception as e:
            logger.error(f"STT error: {e}")
            return ""


stt_service = STTService()
