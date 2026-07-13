# ── RULE 1: C-level thread locks MUST be absolute first lines ──────────
import os
os.environ["OMP_NUM_THREADS"] = "2"
os.environ["OPENBLAS_NUM_THREADS"] = "2"
# ───────────────────────────────────────────────────────────────────────

import logging

from livekit.agents import JobContext, WorkerOptions, cli, llm, stt, tts
from livekit.agents.voice import Agent, AgentSession
from livekit.plugins import groq, deepgram, openai
from livekit.plugins import silero
from core.config import settings
from profiles.jarvis_personal import JarvisPersonalProfile
from services.fallback_stt import LocalMoonshineSTT
from services.fallback_tts import LocalKokoroTTS

logger = logging.getLogger("jarvis-worker")


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
    
    # 3. TOOLS: Extract profile-specific toolsets for the LLM
    agent_tools = profile.get_tools()

    # EAR: VAD Pipeline Core
    vad_plugin = silero.VAD.load(activation_threshold=0.6, min_speech_duration=0.3, min_silence_duration=0.8)

    # EAR: Deepgram Nova-2 STT (Primary) with robust local Moonshine fallback
    dg_stt = deepgram.STT(
        model="nova-2", 
        api_key=settings.deepgram_api_key,
        smart_format=True,
        keywords=[("Jarvis", 2.0), ("Veronica", 2.0), ("weather", 2.0)]
    )
    local_stt = LocalMoonshineSTT()
    stt_plugin = stt.FallbackAdapter([dg_stt, local_stt], vad=vad_plugin)

    # BRAIN: LLM Proxy Chain
    groq_llm = openai.LLM(
        base_url="https://api.groq.com/openai/v1",
        api_key=settings.groq_api_key,
        model="llama-3.3-70b-versatile"
    )
    gemini_llm = openai.LLM(
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        api_key=settings.gemini_api_key,
        model="gemini-2.0-flash"
    )
    llm_plugin = llm.FallbackAdapter([groq_llm, gemini_llm], attempt_timeout=5.0)

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
    
    await session.start(agent=jarvis_agent, room=ctx.room, record=False)
    await session.say(profile.greeting_message, allow_interruptions=True)


if __name__ == "__main__":
    cli.run_app(WorkerOptions(
        entrypoint_fnc=entrypoint,
        api_key=settings.livekit_api_key,
        api_secret=settings.livekit_api_secret,
        ws_url=settings.livekit_url
    ))
