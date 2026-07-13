"""
RCA Summary:
- CRASH: MoonshineSTT missing abstract method `_recognize_impl` (required in livekit-agents v1.6+)
- OLD API: `stream()` no longer uses a custom SpeechStream; use `StreamAdapter` + `_recognize_impl` pattern
- FIX: Implement `_recognize_impl` which takes a full AudioBuffer and returns a SpeechEvent.
       The AgentSession uses STT.stream() → StreamAdapter handles the chunking internally.
"""
import asyncio
import logging
from dataclasses import dataclass

import numpy as np

from livekit.agents import stt, utils
from livekit.agents.types import APIConnectOptions, NOT_GIVEN, NotGivenOr

try:
    from moonshine_onnx import MoonshineOnnxModel
    from moonshine_onnx.transcribe import load_tokenizer
    MOONSHINE_AVAILABLE = True
except ImportError:
    MOONSHINE_AVAILABLE = False

logger = logging.getLogger("livekit.stt.moonshine")


@dataclass
class MoonshineOptions:
    model_name: str = "tiny"


class MoonshineSTT(stt.STT):
    """
    Moonshine ONNX STT for LiveKit agents v1.6+
    Implements the required `_recognize_impl` abstract method.
    ONNX inference is offloaded to asyncio.to_thread() to avoid blocking WebRTC.
    """

    def __init__(self, opts: MoonshineOptions = MoonshineOptions()):
        super().__init__(
            capabilities=stt.STTCapabilities(
                streaming=False,   # We implement recognize (batch), not streaming
                interim_results=False,
            )
        )
        self.opts = opts

        if not MOONSHINE_AVAILABLE:
            raise ImportError(
                "moonshine_onnx not installed. Run: pip install moonshine-onnx"
            )

        logger.info(f"Loading Moonshine '{opts.model_name}' model...")
        self._model = MoonshineOnnxModel(model_name=opts.model_name)
        self._decode = load_tokenizer().decode_batch
        logger.info("Moonshine model loaded.")

    async def _recognize_impl(
        self,
        buffer: utils.AudioBuffer,
        *,
        language: NotGivenOr[str] = NOT_GIVEN,
        conn_options: APIConnectOptions,
    ) -> stt.SpeechEvent:
        """
        Required abstract method — called by the LiveKit framework with a full audio buffer.
        Offloads ONNX inference to a thread so the event loop stays unblocked.
        """
        # Convert AudioBuffer frames to a single numpy float32 array
        frames = [np.frombuffer(bytes(frame), dtype=np.int16) for frame in buffer]
        if not frames:
            return stt.SpeechEvent(
                type=stt.SpeechEventType.FINAL_TRANSCRIPT,
                alternatives=[stt.SpeechData(text="", language="en")],
            )

        audio_np = np.concatenate(frames).astype(np.float32) / 32768.0

        def _run():
            tokens = self._model.generate(audio_np[None, ...])
            return self._decode(tokens)[0]

        try:
            text = await asyncio.to_thread(_run)
            text = text.strip() if text else ""
            logger.debug(f"Moonshine transcribed: '{text}'")
        except Exception as e:
            logger.error(f"Moonshine inference error: {e}", exc_info=True)
            text = ""

        return stt.SpeechEvent(
            type=stt.SpeechEventType.FINAL_TRANSCRIPT,
            alternatives=[stt.SpeechData(text=text, language="en")],
        )
