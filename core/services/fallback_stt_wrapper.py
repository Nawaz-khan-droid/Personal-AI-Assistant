import logging
from livekit.agents import stt
import traceback

logger = logging.getLogger("jarvis-fallback-stt")

class ResilientSTT(stt.STT):
    """
    A custom wrapper to handle STT fallbacks from cloud to local ONNX models.
    This uses Session-Level Fallback logic to prevent mid-stream chunk desyncs.
    """
    def __init__(self, primary: stt.STT, fallback: stt.STT):
        super().__init__(capabilities=stt.STTCapabilities(streaming=True, interim_results=True))
        self.primary = primary
        self.fallback = fallback
        self._primary_failed = False

    def stream(self, **kwargs) -> stt.SpeechStream:
        # If the primary failed in a previous session, permanently use fallback
        if self._primary_failed:
            return self.fallback.stream(**kwargs)
            
        return ResilientSpeechStream(self, self.primary, self.fallback, **kwargs)
        
    async def _recognize_impl(self, *args, **kwargs):
        return await self.primary.recognize(*args, **kwargs)


class ResilientSpeechStream(stt.SpeechStream):
    def __init__(self, parent: 'ResilientSTT', primary: stt.STT, fallback: stt.STT, **kwargs):
        super().__init__(stt=parent, conn_options=kwargs.get("conn_options"))
        self.parent = parent
        self.primary = primary
        self.fallback = fallback
        self._kwargs = kwargs
        
        self._primary_stream = self.primary.stream(**kwargs)
        self._fallback_stream = None
        self._using_fallback = False

    async def _run(self):
        pass

    def _switch_to_fallback(self):
        """Internal helper to safely trip the breaker and spin up the fallback."""
        self.parent._primary_failed = True
        self._using_fallback = True
        if self._fallback_stream is None:
            self._fallback_stream = self.fallback.stream(**self._kwargs)

    async def push_frame(self, frame):
        if self._using_fallback:
            if self._fallback_stream:
                await self._fallback_stream.push_frame(frame)
            return

        try:
            await self._primary_stream.push_frame(frame)
        except Exception as e:
            logger.warning(f"Primary STT failed on push_frame: {e}. Switching to Session-Level Fallback.")
            self._switch_to_fallback()
            # Push the current frame to the newly spun-up fallback stream
            await self._fallback_stream.push_frame(frame)
            
            # Attempt to safely close the broken primary stream in the background
            try:
                await self._primary_stream.aclose()
            except Exception:
                pass

    async def flush(self):
        if self._using_fallback:
            if self._fallback_stream:
                await self._fallback_stream.flush()
            return

        try:
            await self._primary_stream.flush()
        except Exception as e:
            logger.warning(f"Primary STT failed on flush: {e}. Switching to Session-Level Fallback.")
            self._switch_to_fallback()
            await self._fallback_stream.flush()
            try:
                await self._primary_stream.aclose()
            except Exception:
                pass

    async def aclose(self):
        try:
            await self._primary_stream.aclose()
        except Exception:
            pass
            
        if self._fallback_stream:
            try:
                await self._fallback_stream.aclose()
            except Exception:
                pass

    async def __anext__(self):
        if self._using_fallback:
            if self._fallback_stream:
                return await self._fallback_stream.__anext__()
            else:
                raise StopAsyncIteration
                
        try:
            return await self._primary_stream.__anext__()
        except StopAsyncIteration:
            raise StopAsyncIteration
        except Exception as e:
            logger.error(f"Primary STT __anext__ exception: {e}")
            logger.debug(traceback.format_exc())
            logger.warning("Primary STT disconnected during read. Enacting Session-Level Fallback.")
            self._switch_to_fallback()
            
            # Safely close the primary stream
            try:
                await self._primary_stream.aclose()
            except Exception:
                pass
                
            # Re-raise the original exception so the session gracefully drops this utterance
            raise e
