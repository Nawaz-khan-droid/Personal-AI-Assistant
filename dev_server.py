"""
JARVIS Dev Web Server
Serves the static UI and mints LiveKit tokens using the local dev credentials.
No cloud account required — LiveKit dev mode uses built-in devkey/secret.
"""
import os
from dotenv import load_dotenv
import uvicorn

load_dotenv()
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from fastapi.staticfiles import StaticFiles
from livekit import api

import random

# ── Credentials ────────────────────────────────────────────────────────────────
# livekit-server.exe --dev defaults to these built-in credentials.
# No cloud account, no paid plan — 100% local.
LIVEKIT_URL    = os.getenv("LIVEKIT_URL",        "ws://127.0.0.1:7880")
LIVEKIT_KEY    = os.getenv("LIVEKIT_API_KEY",    "devkey")
LIVEKIT_SECRET = os.getenv("LIVEKIT_API_SECRET", "secret")

app = FastAPI(title="JARVIS Dev Server")

# Allow browser to call /api/token from any origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static UI files
STATIC_DIR = os.path.join(os.path.dirname(__file__), "backend", "static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
def serve_index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))

class TokenRequest(BaseModel):
    password: str
    persona: str = "JARVIS"

@app.post("/api/token")
def get_token(req: TokenRequest):
    """
    Mint a LiveKit JWT for the frontend to join the room.
    Uses local devkey/secret — no cloud account required.
    """
    try:
        import os as _os
        expected_pwd = _os.getenv("JARVIS_UI_PASSWORD", "jarvis_secure_123")
        if req.password != expected_pwd:
            return JSONResponse({"error": "Unauthorized"}, status_code=401)
        
        uid = "user_" + _os.urandom(4).hex()
        # Generate a unique room name to prevent LiveKit Cloud dispatch zombie states
        # when a worker crashes or disconnects uncleanly.
        safe_persona = req.persona.lower().strip()
        room_name = f"{safe_persona}-room-{random.randint(1000, 9999)}"
        
        token = api.AccessToken(LIVEKIT_KEY, LIVEKIT_SECRET)
        token.with_identity(uid)
        token.with_name("Operator")
        token.with_grants(api.VideoGrants(
            room_join=True,
            room=room_name,
            can_publish=True,
            can_subscribe=True,
        ))
        jwt = token.to_jwt()
        print(f"[TOKEN] Minted JWT for {uid} | room={room_name}")
        return JSONResponse({"token": jwt, "url": LIVEKIT_URL, "room": room_name})
    except Exception as e:
        print(f"[TOKEN ERROR] {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/health")
def health():
    return {"status": "ok", "livekit_url": LIVEKIT_URL}

if __name__ == "__main__":
    print("=" * 55)
    print("  JARVIS Dev Server")
    print(f"  UI:     http://127.0.0.1:8000")
    print(f"  Token:  http://127.0.0.1:8000/api/token")
    print(f"  LiveKit:{LIVEKIT_URL}  (Key: {LIVEKIT_KEY})")
    print("  No cloud account required — using dev credentials.")
    print("=" * 55)
    port = int(os.getenv("PORT", "8000"))
    print("=" * 55)
    print("  JARVIS Dev Server")
    print(f"  UI:     http://127.0.0.1:{port}")
    print(f"  Token:  http://127.0.0.1:{port}/api/token")
    print(f"  LiveKit:{LIVEKIT_URL}  (Key: {LIVEKIT_KEY})")
    print("  No cloud account required — using dev credentials.")
    print("=" * 55)
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
