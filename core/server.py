import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import random
import logging
from livekit import api
from core.config import settings

app = FastAPI(title="Jarvis Token Server")

# Allow the frontend Vite server to access the token API locally
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    ))
    
    # Monkeypatch to fix 15-hour Windows clock skew issue
    import datetime
    token.ttl = datetime.timedelta(days=2)
    return TokenResponse(token=token.to_jwt(), url=settings.livekit_url)

# Mount the static frontend dist folder as the root UI
# Note: This requires the frontend to be built (npm run build) and placed in frontend/dist
if os.path.exists("frontend/dist"):
    app.mount("/", StaticFiles(directory="frontend/dist", html=True), name="ui")
else:
    logger = logging.getLogger("jarvis-server")
    logger.warning("frontend/dist directory not found. Starting API without static UI.")
