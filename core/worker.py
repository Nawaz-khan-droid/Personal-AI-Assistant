# ── RULE 1: C-level thread locks MUST be absolute first lines ──────────
import os
os.environ["OMP_NUM_THREADS"] = "2"
os.environ["OPENBLAS_NUM_THREADS"] = "2"
# ───────────────────────────────────────────────────────────────────────

import logging
import json
import time
import asyncio
from contextlib import contextmanager

from livekit.agents import JobContext, WorkerOptions, cli, llm, stt, tts
from livekit.agents.voice import Agent, AgentSession
from livekit.plugins import groq, deepgram, openai
from livekit.plugins import silero
from core.config import settings
from profiles.jarvis_personal import JarvisPersonalProfile
from services.fallback_stt import LocalMoonshineSTT
from services.fallback_tts import LocalKokoroTTS

# Clean up noisy libraries
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("livekit").setLevel(logging.INFO)

# Structured JSON logging
class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_obj = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_obj["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(log_obj)

logger = logging.getLogger("jarvis-worker")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)

@contextmanager
def _timed(name):
    start = time.monotonic()
    yield
    duration = time.monotonic() - start
    logger.info(f"Pipeline Timing: {name} took {duration:.3f}s")

class TokenBucketRateLimiter:
    def __init__(self, rpm=25):
        self.interval = 60.0 / rpm
        self.last_call = 0.0
        self.lock = asyncio.Lock()
        
    async def acquire(self):
        async with self.lock:
            now = time.monotonic()
            elapsed = now - self.last_call
            if elapsed < self.interval:
                await asyncio.sleep(self.interval - elapsed)
            self.last_call = time.monotonic()

class RateLimitedGroqLLM(groq.LLM):
    def __init__(self, rpm=25, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._limiter = TokenBucketRateLimiter(rpm=rpm)
        
    def chat(self, *args, **kwargs):
        original_stream = super().chat(*args, **kwargs)
        
        class RateLimitedStream(type(original_stream)):
            def __init__(self, inner, limiter):
                self.__dict__ = inner.__dict__.copy()
                self._inner = inner
                self._limiter = limiter
                self._started = False
                
            def __aiter__(self):
                return self
                
            async def __anext__(self):
                if not getattr(self, '_started', False):
                    await self._limiter.acquire()
                    self._started = True
                return await self._inner.__anext__()
                
            async def aclose(self):
                if hasattr(self._inner, "aclose"):
                    await self._inner.aclose()
                    
        return RateLimitedStream(original_stream, self._limiter)


async def entrypoint(ctx: JobContext):
    """
    LiveKit Worker Entrypoint.
    Executes whenever a LiveKit Cloud room allocates a connection to this worker.
    """
    logger.info(f"Connecting communication lines to LiveKit Cloud (Room: {ctx.room.name})...")
    await ctx.connect()
    logger.info(f"Persistent stream established inside room: {ctx.room.name}")

    # 1. PROFILE FACTORY: Load concrete profile based on room name
    requested_persona = "jarvis"
    logger.info(f"Checking persona for room: '{ctx.room.name}' with metadata: '{ctx.room.metadata}'")
    if "veronica" in ctx.room.name.lower():
        requested_persona = "veronica"
    elif ctx.room.metadata and ctx.room.metadata.lower() in ["jarvis", "veronica"]:
        requested_persona = ctx.room.metadata.lower()
        
    logger.info(f"Selected persona: {requested_persona}")
    profile = JarvisPersonalProfile(persona=requested_persona, language_mode="english")
    
    # 2. CHAT CONTEXT: Build context and inject the persona safely
    initial_ctx = llm.ChatContext()
    initial_ctx.add_message(role="system", content=profile.system_prompt)
    
    # 2.5 LONG-TERM MEMORY: Inject retrieved persistent semantic memory safely
    try:
        import asyncio
        stored_memories = await asyncio.to_thread(profile.memory.get_all_memories)
        if stored_memories:
            facts_block = "### STORED LONG-TERM USER PREFERENCES:\n"
            for cat, fact in stored_memories.items():
                facts_block += f"- {cat}: {fact}\n"
            facts_block += "\nUse this memory context natively during conversations. Only invoke the 'upsert_user_fact' tool if the user provides completely new info or explicitly updates a preference."
            initial_ctx.add_message(role="system", content=facts_block)
    except Exception as e:
        logger.error(f"Failed to prime memory context: {e}")
    
    # 3. TOOLS: Extract profile-specific toolsets for the LLM
    agent_tools = profile.get_tools()

    # EAR: VAD Pipeline Core
    vad_plugin = silero.VAD.load(activation_threshold=0.6, min_speech_duration=0.3, min_silence_duration=0.8)

    # EAR: Deepgram STT (Primary) with robust local Moonshine fallback
    primary_stt = deepgram.STT(
        model="nova-2-conversationalai", 
        api_key=settings.deepgram_api_key,
        smart_format=True,
        punctuate=True,
        keywords=[("Jarvis", 2.0), ("Veronica", 2.0), ("weather", 2.0)]
    )
    local_stt = LocalMoonshineSTT()
    stt_plugin = stt.FallbackAdapter([primary_stt, local_stt], vad=vad_plugin)

    groq_llm = RateLimitedGroqLLM(
        rpm=25,
        model="llama-3.1-8b-instant",
        api_key=settings.groq_api_key
    )
    gemini_llm = openai.LLM(
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        api_key=settings.gemini_api_key,
        model="gemini-3.1-flash-lite"
    )
    openai_llm = openai.LLM(
        model="gpt-4o-mini",
        api_key=settings.openai_api_key
    )
    llm_plugin = llm.FallbackAdapter([gemini_llm, groq_llm, openai_llm], attempt_timeout=5.0)

    # VOICE: TTS Proxy Chain
    tts_model = "aura-2-neptune-en" if profile.persona == "jarvis" else "aura-2-aurora-en"
    deepgram_tts = deepgram.TTS(
        model=tts_model,
        sample_rate=24000,
        api_key=settings.deepgram_api_key
    )
    local_tts = LocalKokoroTTS()
    tts_plugin = tts.FallbackAdapter([deepgram_tts, local_tts])

    # ORCHESTRATION: LiveKit 1.6+ Modern Agent Session
    jarvis_agent = Agent(
        instructions=profile.system_prompt,
        chat_ctx=initial_ctx,
        tools=agent_tools,
    )

    session = AgentSession(
        stt=stt_plugin,
        llm=llm_plugin,
        tts=tts_plugin,
        vad=vad_plugin,
    )
    
    # Expose session to profile tools (for set_reminder etc.)
    profile._session = session
    
    await session.start(agent=jarvis_agent, room=ctx.room, record=False)
    try:
        await session.say(profile.greeting_message, allow_interruptions=True)
    except Exception as e:
        logger.error(f"Error speaking greeting: {e}")


if __name__ == "__main__":
    cli.run_app(WorkerOptions(
        entrypoint_fnc=entrypoint,
        api_key=settings.livekit_api_key,
        api_secret=settings.livekit_api_secret,
        ws_url=settings.livekit_url
    ))
