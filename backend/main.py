"""
JARVIS AI Voice Assistant - Main FastAPI Application

Pipeline: Browser Mic -> WebSocket -> Moonshine STT -> Groq LLM / Gemini Fallback
          -> Tool Registry -> Kokoro TTS -> WebSocket -> Browser Speakers
"""

import json
import os
import time
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import (
    FastAPI, WebSocket, WebSocketDisconnect,
    HTTPException, Request
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from backend import config
from backend.websocket_manager import manager as ws_manager
from backend.utils.logger import setup_logging, get_logger
from backend.utils.exceptions import JarvisBaseException, RateLimitError


class WSRateLimiter:
    """Per-IP rate limiter for WebSocket connections (separate from slowapi REST limiter)."""
    def __init__(self, max_turns: int = 30, window_seconds: int = 60):
        self.max_turns = max_turns
        self.window = window_seconds
        self._buckets: dict = {}

    def check(self, ip: str):
        now = time.time()
        bucket = self._buckets.get(ip)
        if bucket:
            ts, count = bucket
            if now - ts < self.window:
                if count >= self.max_turns:
                    retry_after = int(self.window - (now - ts))
                    raise RateLimitError(retry_after)
                self._buckets[ip] = (ts, count + 1)
            else:
                self._buckets[ip] = (now, 1)
        else:
            self._buckets[ip] = (now, 1)
from backend.services.ai.llm_service import llm_service
from backend.services.ai.stt_service import stt_service
from backend.services.ai.tts_service import tts_service
from backend.services.ai.voice_service import voice_service

setup_logging(log_level=config.LOG_LEVEL, log_file=config.LOG_FILE)
logger = get_logger(__name__)

limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("JARVIS backend starting up...")
    app.state.ws_rate_limiter = WSRateLimiter()
    os.makedirs("backend/static", exist_ok=True)
    try:
        app.state.model_health_snapshot = await llm_service.probe_gemini_models()
    except Exception as e:
        logger.warning(f"LLM startup probe failed: {e}")
        app.state.model_health_snapshot = {"status": "Not Found", "error": str(e)}
    yield
    logger.info("JARVIS backend shutting down...")


app = FastAPI(
    title="JARVIS AI Voice Assistant",
    description="Voice assistant with Moonshine STT, Groq/Gemini LLM, Kokoro TTS",
    version="2.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files (Kokoro model weights, legacy audio)
os.makedirs("backend/static", exist_ok=True)
app.mount("/static", StaticFiles(directory="backend/static"), name="static")

# Serve Next.js static build (frontend) if it exists
next_out = os.path.join(os.path.dirname(os.path.dirname(__file__)), "client", "out") if "__file__" in dir() else "client/out"
if os.path.isdir(next_out):
    app.mount("/", StaticFiles(directory=next_out, html=True), name="frontend")


# ============================================================================
# HEALTH & ROOT
# ============================================================================

@app.get("/health")
async def health_check():
    model_health = llm_service.get_model_health_snapshot() or getattr(app.state, "model_health_snapshot", {})
    return {
        "status": "healthy",
        "version": "2.0.0",
        "active_connections": ws_manager.get_active_count(),
        "llm": {
            "provider": "groq+gemini",
            "status": model_health.get("status", "unknown"),
        },
        "stt": "moonshine" if stt_service.is_available() else "unavailable",
        "tts": "kokoro" if tts_service.is_available() else "unavailable",
    }


@app.get("/")
async def root():
    return {
        "name": "JARVIS AI Voice Assistant",
        "version": "2.0.0",
        "endpoints": {
            "websocket": "/ws",
            "health": "/health",
            "rest_chat": "/api/chat",
        },
    }


# ============================================================================
# WEBSOCKET - Full Voice Pipeline: Mic -> STT -> LLM -> TTS -> Speaker
# ============================================================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    session_id = None

    try:
        session_id = await ws_manager.connect(websocket)
    except Exception as e:
        logger.error(f"Failed to accept WS connection: {e}")
        return

    logger.info(f"WebSocket connected: {session_id}")

    # Per-IP rate limit check (protects API key quotas from bot abuse)
    client_ip = websocket.client.host if websocket.client else "unknown"
    if hasattr(app.state, 'ws_rate_limiter'):
        app.state.ws_rate_limiter.check(client_ip)

    # Session state
    MAX_AUDIO_BUFFER = 320000  # ~10s at 16kHz 16-bit mono
    MAX_HISTORY_TURNS = 20     # prevents unbounded memory + token growth
    audio_buffer = bytearray()
    session_history = []
    min_audio_bytes = 2048

    # Voice state is managed centrally by voice_service
    voice_service.select_preset("am_adam")

    SYSTEM_PROMPT = (
        "You are JARVIS, a voice-first AI assistant. "
        "Respond concisely in 1-3 sentences (output is read aloud via TTS). "
        "You have 4 tools available. Use them rather than guessing:\n"
        "  - get_current_time(timezone): IANA timezone like 'America/New_York'. Default UTC.\n"
        "  - get_weather(location): City name like 'London'. Returns conditions, temp, humidity, wind.\n"
        "  - calculate(expression): Math expression like '(15 + 3) * 2'. Safe evaluator.\n"
        "  - web_search(query): DuckDuckGo search for recent/unknown info.\n"
        "Rules: Always call the tool when the question matches its domain. "
        "After receiving the tool result, present it conversationally. "
        "Never fabricate weather, time, calculations, or search results."
    )

    try:
        while True:
            message = await websocket.receive()

            # --- JSON CONTROL MESSAGES ---
            if "text" in message:
                try:
                    data = json.loads(message["text"])
                    msg_type = data.get("type", "")

                    if msg_type == "set_voice":
                        voice_service.select_preset(data.get("voice_id", "am_adam"))

                    elif msg_type == "set_voice_profile":
                        mode = data.get("mode", "preset")
                        if mode == "preset":
                            voice_service.select_preset(data.get("voice_id", "am_adam"))
                        elif mode == "mix":
                            voice_service.blend(
                                data.get("base_voice", "am_adam"),
                                data.get("mod_voice", "am_michael"),
                                float(data.get("alpha", 0.5)),
                            )

                    elif msg_type == "save_custom_mix":
                        path = voice_service.save_custom(
                            data.get("name", "custom_voice"),
                            data.get("base_voice", "am_adam"),
                            data.get("mod_voice", "am_michael"),
                            float(data.get("alpha", 0.5)),
                        )
                        await ws_manager.send_message(session_id, {
                            "type": "custom_voice_saved",
                            "name": data.get("name", "custom_voice"),
                            "path": path,
                        })

                    elif msg_type == "trigger_preview":
                        preview_text = data.get("text", "System tuning complete. Matrix online.")
                        async def _send_preview(data: bytes):
                            await ws_manager.send_bytes(session_id, data)
                        await tts_service.stream_speech(
                            preview_text, voice_service.get_active_voice(), _send_preview
                        )

                    elif msg_type == "update_voice_blend":
                        logger.info(f"Voice blend: {data.get('alpha')}")

                    elif msg_type == "speech_ended":
                        audio_buffer.clear()

                    elif msg_type == "clear_history":
                        session_history.clear()
                        await ws_manager.send_message(session_id, {
                            "type": "history_cleared"
                        })

                    elif msg_type == "text_message":
                        user_text = data.get("content", "")
                        await ws_manager.send_message(session_id, {
                            "type": "thinking", "status": "Processing..."
                        })
                        reply = await llm_service.chat_complete(
                            session_history + [{"role": "user", "content": user_text}],
                            system_prompt=SYSTEM_PROMPT,
                            tools=llm_service.tools_schema,
                        )
                        session_history.append({"role": "user", "content": user_text})
                        session_history.append({"role": "assistant", "content": reply})
                        if len(session_history) > MAX_HISTORY_TURNS * 2:
                            session_history = session_history[-(MAX_HISTORY_TURNS * 2):]
                        await ws_manager.send_message(session_id, {
                            "type": "bot_response_text", "text": reply
                        })
                        async def _send_audio(data: bytes):
                            await ws_manager.send_bytes(session_id, data)
                        await tts_service.stream_speech(
                            reply, voice_service.get_active_voice(), _send_audio
                        )

                    elif msg_type == "ping":
                        await ws_manager.send_message(session_id, {
                            "type": "pong",
                            "timestamp": data.get("timestamp"),
                        })

                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON from {session_id}")

            # --- BINARY AUDIO CHUNKS (raw PCM Int16 from browser mic) ---
            elif "bytes" in message:
                audio_buffer.extend(message["bytes"])
                if len(audio_buffer) > MAX_AUDIO_BUFFER:
                    audio_buffer = audio_buffer[-32000:]  # drop oldest ~1s
                raw = bytes(audio_buffer)

                if len(raw) < min_audio_bytes:
                    continue

                transcript = await stt_service.transcribe(raw)
                if not transcript:
                    continue

                logger.info(f"STT: {transcript}")

                await ws_manager.send_message(session_id, {
                    "type": "stt_text", "text": transcript
                })

                reply = await llm_service.chat_complete(
                    session_history + [{"role": "user", "content": transcript}],
                    system_prompt=SYSTEM_PROMPT,
                    tools=llm_service.tools_schema,
                )

                session_history.append({"role": "user", "content": transcript})
                session_history.append({"role": "assistant", "content": reply})
                if len(session_history) > MAX_HISTORY_TURNS * 2:
                    session_history = session_history[-(MAX_HISTORY_TURNS * 2):]

                await ws_manager.send_message(session_id, {
                    "type": "bot_response_text", "text": reply
                })

                async def _send_audio_chunk(data: bytes):
                    await ws_manager.send_bytes(session_id, data)
                await tts_service.stream_speech(
                    reply, voice_service.get_active_voice(), _send_audio_chunk
                )

                audio_buffer.clear()

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {session_id}")
    except Exception as e:
        logger.exception(f"WS error [{session_id}]: {e}")
        try:
            await ws_manager.send_message(session_id, {
                "type": "error", "message": "Internal server error"
            })
        except Exception:
            pass
    finally:
        if session_id:
            await ws_manager.disconnect(session_id)


# ============================================================================
# REST ENDPOINTS (legacy compatibility)
# ============================================================================

@app.post("/api/chat")
@limiter.limit("10/minute")
async def chat_endpoint(request: Request, user_input: str):
    try:
        reply = await llm_service.chat_complete(
            [{"role": "user", "content": user_input}],
            tools=llm_service.tools_schema,
        )
        return {"response": {"display_response": reply, "spoken_response": reply}}
    except Exception as e:
        logger.exception(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ============================================================================
# EXCEPTION HANDLERS
# ============================================================================

@app.exception_handler(JarvisBaseException)
async def jarvis_exception_handler(request: Request, exc: JarvisBaseException):
    status = 429 if isinstance(exc, RateLimitError) else 400
    return JSONResponse(status_code=status, content={"error": exc.message, "code": exc.code})


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled: {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": "An unexpected system error occurred.", "code": "internal_error"},
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=config.HOST,
        port=config.PORT,
        reload=config.ENVIRONMENT != "production",
        log_level="info",
    )
