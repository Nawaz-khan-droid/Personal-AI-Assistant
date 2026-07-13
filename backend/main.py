"""
JARVIS LiveKit Worker — v1.x API (livekit-agents >= 1.0)
Uses AgentSession + Agent pattern (NOT the deprecated VoicePipelineAgent)
"""
import os
os.environ["OMP_NUM_THREADS"] = "2"
os.environ["OPENBLAS_NUM_THREADS"] = "2"

import asyncio
import json
import logging

from livekit.agents import AutoSubscribe, JobContext, JobProcess, WorkerOptions, cli
from livekit.agents.voice import Agent, AgentSession
from livekit.plugins import openai as livekit_openai
from backend.services.ai.livekit_stt import MoonshineSTT, MoonshineOptions
from backend.services.ai.livekit_tts import KokoroTTS, KokoroOptions
from backend.utils.logger import setup_logging
from backend import config

setup_logging()
logger = logging.getLogger("jarvis.worker")

PERSONA_VOICES = {
    "JARVIS": "am_adam",
    "VERONICA": "af_bella",
}

PERSONA_INSTRUCTIONS = {
    "JARVIS": (
        "You are JARVIS, a highly sophisticated, tactical personal AI operating core. "
        "Speak with calm, deliberate, refined British clarity. Use dry, subtle wit when appropriate. "
        "Address the operator as 'Sir'. Keep responses crisp and under 3 sentences. "
        "Never output markdown, bullet points, or lists — speak naturally."
    ),
    "VERONICA": (
        "You are Veronica, a sharp, confident AI companion. "
        "Speak with warmth and precision. Be concise and helpful. "
        "Never output markdown, bullet points, or lists — speak naturally."
    ),
}


def prewarm(proc: JobProcess):
    """Prewarm: load heavy ONNX models once before accepting jobs."""
    logger.info("Prewarming STT and TTS models...")
    proc.userdata["stt"] = MoonshineSTT(MoonshineOptions(model_name="tiny"))
    proc.userdata["tts"] = KokoroTTS(KokoroOptions(
        model_path="backend/static/kokoro-v1.0.int8.onnx",
        voices_path="backend/static/voices-v1.0.bin",
        voice="am_adam",
        lang="en-us"
    ))
    logger.info("Models prewarmed successfully.")


async def _send_transcript(ctx: JobContext, role: str, text: str):
    """Send transcript to UI via LiveKit data channel."""
    try:
        msg = json.dumps({"type": "transcript", "role": role, "text": text})
        await ctx.room.local_participant.publish_data(
            msg.encode("utf-8"), reliable=True
        )
    except Exception as e:
        logger.error(f"Failed to send transcript: {e}")


async def entrypoint(ctx: JobContext):
    logger.info(f"Agent job started. Room: {ctx.room.name}")

    groq_key = config.GROQ_API_KEY or os.environ.get("GROQ_API_KEY")
    if not groq_key:
        logger.warning("GROQ_API_KEY not set — LLM will fail to respond.")

    llm_plugin = livekit_openai.LLM(
        model="llama-3.3-70b-versatile",
        api_key=groq_key,
        base_url="https://api.groq.com/openai/v1"
    )

    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)
    logger.info("Connected to LiveKit room.")

    tts = ctx.proc.userdata["tts"]

    session = AgentSession(
        stt=ctx.proc.userdata["stt"],
        llm=llm_plugin,
        tts=tts,
        vad=None,
    )

    current_persona = "JARVIS"
    agent = Agent(instructions=PERSONA_INSTRUCTIONS[current_persona])

    logger.info("Starting AgentSession...")
    session.start(agent, room=ctx.room)

    @ctx.room.on("data_received")
    def on_data_received(data_msg):
        try:
            payload = json.loads(data_msg.data.decode("utf-8"))
            msg_type = payload.get("type")

            if msg_type == "persona_change":
                persona = payload.get("persona", "JARVIS")
                if persona in PERSONA_VOICES:
                    current_persona = persona
                    tts.opts.voice = PERSONA_VOICES[persona]
                    preview = "At your service, Sir." if persona == "JARVIS" else "Hello, I'm Veronica."
                    asyncio.create_task(session.say(preview, allow_interruptions=True))
                    asyncio.create_task(_send_transcript(ctx, "agent", preview))
                    logger.info(f"Persona changed to {persona}, voice={tts.opts.voice}")

            elif msg_type == "chat":
                text = payload.get("text", "").strip()
                if text:
                    asyncio.create_task(_handle_chat(ctx, session, llm_plugin, text))

        except Exception as e:
            logger.error(f"Error handling data message: {e}")

    await session.say(
        "Online, Sir. Systems are nominal. Awaiting your command.",
        allow_interruptions=True
    )
    await _send_transcript(ctx, "agent", "Online, Sir. Systems are nominal. Awaiting your command.")
    logger.info("Greeting sent. Agent is now active.")


async def _handle_chat(ctx: JobContext, session, llm_plugin, text: str):
    """Handle text chat: feed to LLM, speak response, send transcript."""
    await _send_transcript(ctx, "user", text)
    try:
        import httpx
        groq_key = config.GROQ_API_KEY or os.environ.get("GROQ_API_KEY")
        if not groq_key:
            resp_text = "I don't have an API key configured, Sir."
        else:
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {groq_key}"},
                    json={
                        "model": "llama-3.3-70b-versatile",
                        "messages": [
                            {"role": "system", "content": "You are JARVIS. Keep responses under 3 sentences. Speak naturally, no markdown."},
                            {"role": "user", "content": text},
                        ],
                        "max_tokens": 200,
                    },
                )
                r.raise_for_status()
                resp_text = r.json()["choices"][0]["message"]["content"]
        await session.say(resp_text, allow_interruptions=True)
        await _send_transcript(ctx, "agent", resp_text)
    except Exception as e:
        logger.error(f"Chat LLM error: {e}")
        fallback = "I'm having trouble reaching my brain, Sir. Try again shortly."
        await session.say(fallback, allow_interruptions=True)
        await _send_transcript(ctx, "agent", fallback)


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm,
            ws_url=os.environ.get("LIVEKIT_URL", "ws://127.0.0.1:7880"),
            initialize_process_timeout=30.0,
        )
    )
