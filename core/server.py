import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import random
import logging
import json
import time
from pathlib import Path
from livekit import api
from core.config import settings

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

logger = logging.getLogger("jarvis-server")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)

app = FastAPI(title="Jarvis Token Server")

# Allow the frontend Vite server to access the token API locally
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def audit_and_timing_middleware(request, call_next):
    start_time = time.monotonic()
    response = await call_next(request)
    duration = time.monotonic() - start_time
    logger.info(f"Audit: {request.method} {request.url.path} - Status: {response.status_code} - Timing: {duration:.3f}s")
    return response

class TokenRequest(BaseModel):
    password: str
    persona: str = "jarvis"

class TokenResponse(BaseModel):
    token: str
    url: str

@app.post("/api/token", response_model=TokenResponse)
async def get_token(request: TokenRequest):
    """
    Generates a LiveKit Access Token dynamically for the frontend client.
    Requires a valid password matching JARVIS_UI_PASSWORD.
    """
    from fastapi import HTTPException
    
    expected_password = os.getenv("JARVIS_UI_PASSWORD")
    if not expected_password or request.password != expected_password:
        raise HTTPException(status_code=401, detail="Unauthorized: Invalid UI password")
    # Generating a random participant identity for testing flexibility
    participant_identity = f"user-{random.randint(1000, 9999)}"
    
    # Prefix the room with the requested persona for the backend worker to catch
    safe_persona = request.persona.lower().strip()
    if safe_persona not in ["jarvis", "veronica"]:
        safe_persona = "jarvis"
    dynamic_room_name = f"{safe_persona}-session-{random.randint(1000, 9999)}"
    token = api.AccessToken(
        api_key=settings.livekit_api_key,
        api_secret=settings.livekit_api_secret
    ) \
    .with_identity(participant_identity) \
    .with_name("Jarvis Administrator") \
    .with_grants(api.VideoGrants(
        room_join=True,
        room=dynamic_room_name,
        can_publish=True,
        can_subscribe=True,
    ))
    
    # Monkeypatch to fix 15-hour Windows clock skew issue
    import datetime
    token.ttl = datetime.timedelta(days=2)
    return TokenResponse(token=token.to_jwt(), url=settings.livekit_url)

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "livekit_url": settings.livekit_url}

# Mount the static frontend dist folder as the root UI safely (SPA Catch-all)
from fastapi import HTTPException
from fastapi.responses import FileResponse

@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    dist_dir = Path("frontend/dist").resolve()
    if not dist_dir.exists():
        logger.warning("frontend/dist directory not found. Starting API without static UI.")
        raise HTTPException(status_code=404, detail="UI not built")
    
    # Path traversal guard
    requested_path = (dist_dir / full_path).resolve()
    try:
        requested_path.relative_to(dist_dir)
    except ValueError:
        logger.error(f"Path traversal attempt blocked: {full_path}")
        raise HTTPException(status_code=403, detail="Forbidden")
        
    if requested_path.is_file():
        return FileResponse(requested_path)
    
    # Fallback for SPA client-side routing
    index_path = dist_dir / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    raise HTTPException(status_code=404, detail="Not Found")
