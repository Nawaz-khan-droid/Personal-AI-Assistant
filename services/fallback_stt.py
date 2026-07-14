import asyncio
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from livekit import rtc
from livekit.agents import stt
from livekit.agents.utils import AudioBuffer, merge_frames
import moonshine_onnx
from livekit.plugins.silero import VAD


class LocalMoonshineSTT(stt.STT):
    """
    Native LiveKit STT Plugin bridging Moonshine Tiny ONNX logic.
    Inherits from livekit.agents.stt.STT to satisfy AgentSession polymorphic signatures.
    """

    def __init__(self):
        super().__init__(capabilities=stt.STTCapabilities(streaming=False, interim_results=False))
        self._model = None
        self._executor = ThreadPoolExecutor(max_workers=1)

    def _get_model(self):
        if self._model is None:
            self._model = moonshine_onnx.MoonshineOnnxModel(model_name="moonshine/tiny")
        return self._model

    async def _recognize_impl(self, buffer: AudioBuffer, **kwargs) -> stt.SpeechEvent:
        """
        Required LiveKit override. Accepts an AudioBuffer (a list of AudioFrames or single AudioFrame),
        converts it, and runs the ONNX transcription inside a ThreadPoolExecutor.
        """
        loop = asyncio.get_running_loop()
        
        # Offload the heavy synchronous conversion and transcription to a background thread
        decoded_text = await loop.run_in_executor(
            self._executor,
            self._transcribe_sync,
            buffer
        )

        return stt.SpeechEvent(
            type=stt.SpeechEventType.FINAL_TRANSCRIPT,
            alternatives=[stt.SpeechData(language="en", text=decoded_text)]
        )

    def stream(
        self,
        *,
        language: str | None = None,
        **kwargs,
    ) -> stt.RecognizeStream:
        """
        LiveKit requires STT plugins to expose a stream() method. Since Moonshine is
        an offline batch transcriber, we use LiveKit's built-in StreamAdapter to 
        automatically buffer incoming VAD chunks and pass them to recognize().
        """
        # The VAD will automatically collect spoken phrases and hand them to our recognize() method
        return stt.StreamAdapter(stt=self, **kwargs)

    def _transcribe_sync(self, buffer: AudioBuffer) -> str:
        """
        Synchronous worker function executing the matrix math cleanly.
        """
        frame = merge_frames(buffer)
        pcm_bytes = frame.data.tobytes()

        if not pcm_bytes:
            return ""

        # Convert raw PCM (16kHz, mono, 16-bit) to float32 normalized for Moonshine
        audio_int16 = np.frombuffer(pcm_bytes, dtype=np.int16)
        audio_float32 = audio_int16.astype(np.float32) / 32768.0

        model = self._get_model()
        results = moonshine_onnx.transcribe(audio_float32, model=model)
        
        if results and len(results) > 0:
            return results[0]
        return ""
