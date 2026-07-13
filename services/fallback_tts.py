import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import numpy as np
from livekit import rtc
from livekit.agents import tts
from kokoro_onnx import Kokoro


class KokoroChunkedStream(tts.ChunkedStream):
    """
    Asynchronous WebRTC streaming adapter. Offloads Kokoro inference to a thread pool,
    then slices the result into WebRTC-compliant 20ms rtc.AudioFrames.
    """
    def __init__(self, *args, kokoro_engine: Kokoro, executor: ThreadPoolExecutor, voice_target: str, **kwargs):
        super().__init__(*args, **kwargs)
        self._kokoro = kokoro_engine
        self._executor = executor
        self._voice_target = voice_target
        self._sample_rate = 24000
        self._num_channels = 1

    async def _run(self):
        """Executed automatically in the background by LiveKit's stream manager."""
        loop = asyncio.get_running_loop()
        
        # Offload the heavy ONNX math
        pcm_bytes = await loop.run_in_executor(
            self._executor,
            self._synthesize_sync,
            self._input_text
        )

        # Slice the monolithic byte array into WebRTC standard 20ms chunks
        # 24,000 Hz * 0.02 seconds = 480 samples. 480 samples * 2 bytes (16-bit) = 960 bytes per chunk.
        bytes_per_chunk = 960 
        
        for i in range(0, len(pcm_bytes), bytes_per_chunk):
            chunk = pcm_bytes[i : i + bytes_per_chunk]
            samples_in_chunk = len(chunk) // 2

            # Pack exactly to LiveKit media constraints (Rule 4 Media Packing)
            audio_frame = rtc.AudioFrame(
                data=chunk,
                sample_rate=self._sample_rate,
                num_channels=self._num_channels,
                samples_per_channel=samples_in_chunk
            )
            
            is_final = (i + bytes_per_chunk) >= len(pcm_bytes)
            
            self._event_ch.send_nowait(
                tts.SynthesizedAudio(
                    request_id=self._request_id,
                    frame=audio_frame,
                    is_final=is_final
                )
            )

    def _synthesize_sync(self, text: str) -> bytes:
        if not text.strip():
            return b""
            
        samples, _ = self._kokoro.create(text, voice=self._voice_target, speed=1.0, lang="en-us")
        samples = samples.flatten()
        pcm_audio = np.clip(samples * 32767.0, -32768.0, 32767.0).astype(np.int16)
        return pcm_audio.tobytes()


class LocalKokoroTTS(tts.TTS):
    """
    Native LiveKit TTS Plugin mapping Kokoro ONNX offline generation 
    directly into WebRTC compliant audio frame streaming.
    """
    def __init__(self, persona: str = "jarvis"):
        super().__init__(
            capabilities=tts.TTSCapabilities(streaming=False),
            sample_rate=24000,
            num_channels=1
        )
        
        self._persona = persona.lower()
        self._voice_target = "am_adam" if self._persona == "jarvis" else "af_sarah"
        
        project_root = Path(__file__).parent.parent
        model_path = project_root / "backend" / "static" / "kokoro-v1.0.int8.onnx"
        voices_path = project_root / "backend" / "static" / "voices-v1.0.bin"

        self._kokoro = Kokoro(str(model_path), str(voices_path))
        self._executor = ThreadPoolExecutor(max_workers=1)

    def synthesize(self, text: str, **kwargs) -> tts.ChunkedStream:
        """
        Required LiveKit override. 
        Returns immediately, handing off generation to the background ChunkedStream loop.
        """
        return KokoroChunkedStream(
            tts=self,
            input_text=text,
            conn_options=self._opts,
            kokoro_engine=self._kokoro,
            executor=self._executor,
            voice_target=self._voice_target
        )
