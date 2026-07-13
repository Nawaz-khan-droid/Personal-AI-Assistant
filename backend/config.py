"""
Application configuration with Pydantic BaseSettings for type-safe env var validation.

Why: Pydantic's BaseSettings automatically reads from environment variables,
provides type coercion, range validation, and `.env` file support.
Backward-compatible module-level constants are provided for existing imports.

Adapted from thevickypedia/Jarvis pydantic-based config pattern.
"""

import os
from dotenv import load_dotenv

load_dotenv()

try:
    from pydantic_settings import BaseSettings
    from pydantic import Field
    _HAS_PYDANTIC_SETTINGS = True
except ImportError:
    _HAS_PYDANTIC_SETTINGS = False


if _HAS_PYDANTIC_SETTINGS:

    class Settings(BaseSettings):
        """Type-safe validated configuration via environment variables."""

        # API Keys
        groq_api_key: str = Field(default="", alias="GROQ_API_KEY")
        gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
        hf_token: str = Field(default="", alias="HF_TOKEN")
        elevenlabs_api_key: str = Field(default="", alias="ELEVENLABS_API_KEY")
        openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
        google_factcheck_api_key: str = Field(default="", alias="GOOGLE_FACTCHECK_API_KEY")
        newsdata_api_key: str = Field(default="", alias="NEWSDATA_API_KEY")

        # LiveKit (Fix #5a: required for worker auth)
        livekit_url: str = Field(default="ws://localhost:7880", alias="LIVEKIT_URL")
        livekit_api_key: str = Field(default="devkey", alias="LIVEKIT_API_KEY")
        livekit_api_secret: str = Field(default="secret", alias="LIVEKIT_API_SECRET")

        # Model settings
        groq_model: str = Field(default="llama-3.3-70b-versatile", alias="GROQ_MODEL")
        gemini_model: str = Field(default="gemini-2.0-flash", alias="GEMINI_MODEL")
        openai_model: str = Field(default="gpt-4o", alias="OPENAI_MODEL")
        llm_provider: str = Field(default="gemini", alias="LLM_PROVIDER")

        # ElevenLabs
        elevenlabs_voice_id: str = Field(default="AolUMF9fjkrPfGw4trAx", alias="ELEVENLABS_VOICE_ID")
        elevenlabs_agent_id: str = Field(default="", alias="ELEVENLABS_AGENT_ID")
        elevenlabs_enable_agent: bool = Field(default=False, alias="ELEVENLABS_ENABLE_AGENT")

        # Server
        host: str = Field(default="127.0.0.1", alias="HOST")
        port: int = Field(default=8000, ge=1, le=65535, alias="PORT")

        # Rate limiting
        rate_limit: str = Field(default="10/minute", alias="RATE_LIMIT")
        llm_rate_limit: str = Field(default="15/minute", alias="LLM_RATE_LIMIT")

        # Upload
        max_upload_mb: int = Field(default=10, ge=1, le=100, alias="MAX_UPLOAD_MB")

        # CORS
        cors_origins: str = Field(
            default="http://127.0.0.1:3000,http://localhost:3000",
            alias="CORS_ORIGINS",
        )

        # Audio
        tts_ttl_seconds: int = Field(default=600, alias="TTS_TTL_SECONDS")

        # Environment
        environment: str = Field(default="development", alias="ENVIRONMENT")
        log_level: str = Field(default="INFO", alias="LOG_LEVEL")
        log_file: str = Field(default="assistant.log", alias="LOG_FILE")
        default_language: str = Field(default="en", alias="DEFAULT_LANGUAGE")

        model_config = {"extra": "allow"}

    settings = Settings()

else:
    # Fallback if pydantic-settings not installed
    class _Settings:  # type: ignore
        pass

    settings = _Settings()
    settings.groq_api_key = os.getenv("GROQ_API_KEY", "")
    settings.gemini_api_key = os.getenv("GEMINI_API_KEY", "")
    settings.groq_model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    settings.gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    settings.host = os.getenv("HOST", "127.0.0.1")
    settings.port = int(os.getenv("PORT", "8000"))
    settings.environment = os.getenv("ENVIRONMENT", "development")
    settings.log_level = os.getenv("LOG_LEVEL", "INFO")
    settings.log_file = os.getenv("LOG_FILE", "assistant.log")
    settings.rate_limit = os.getenv("RATE_LIMIT", "10/minute")
    settings.llm_rate_limit = os.getenv("LLM_RATE_LIMIT", "15/minute")
    settings.max_upload_mb = int(os.getenv("MAX_UPLOAD_MB", "10"))
    settings.cors_origins = os.getenv("CORS_ORIGINS", "http://127.0.0.1:3000,http://localhost:3000")
    settings.tts_ttl_seconds = int(os.getenv("TTS_TTL_SECONDS", "600"))
    settings.default_language = os.getenv("DEFAULT_LANGUAGE", "en")
    settings.llm_provider = os.getenv("LLM_PROVIDER", "gemini")
    settings.elevenlabs_voice_id = os.getenv("ELEVENLABS_VOICE_ID", "AolUMF9fjkrPfGw4trAx")
    settings.elevenlabs_agent_id = os.getenv("ELEVENLABS_AGENT_ID", "")
    settings.elevenlabs_enable_agent = os.getenv("ELEVENLABS_ENABLE_AGENT", "false").lower() in ("1", "true", "yes")
    settings.livekit_url = os.getenv("LIVEKIT_URL", "ws://localhost:7880")
    settings.livekit_api_key = os.getenv("LIVEKIT_API_KEY", "devkey")
    settings.livekit_api_secret = os.getenv("LIVEKIT_API_SECRET", "secret")


# Backward-compatible module-level constants
HF_TOKEN = getattr(settings, 'hf_token', os.getenv("HF_TOKEN", ""))
GROQ_API_KEY = settings.groq_api_key
GROQ_MODEL = settings.groq_model
GEMINI_API_KEY = settings.gemini_api_key
GEMINI_MODEL = settings.gemini_model
LLM_PROVIDER = settings.llm_provider
ELEVENLABS_API_KEY = getattr(settings, 'elevenlabs_api_key', os.getenv("ELEVENLABS_API_KEY"))
ELEVENLABS_VOICE_ID = settings.elevenlabs_voice_id
ELEVENLABS_AGENT_ID = settings.elevenlabs_agent_id
ELEVENLABS_ENABLE_AGENT = settings.elevenlabs_enable_agent
HOST = settings.host
PORT = settings.port
RATE_LIMIT = settings.rate_limit
LLM_RATE_LIMIT = settings.llm_rate_limit
MAX_UPLOAD_MB = settings.max_upload_mb
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024
TTS_TTL_SECONDS = settings.tts_ttl_seconds
DEFAULT_LANGUAGE = settings.default_language
ENVIRONMENT = settings.environment
LOG_LEVEL = settings.log_level
LOG_FILE = settings.log_file
OPENAI_API_KEY = getattr(settings, 'openai_api_key', os.getenv("OPENAI_API_KEY"))
OPENAI_MODEL = settings.openai_model
GOOGLE_FACTCHECK_API_KEY = getattr(settings, 'google_factcheck_api_key', os.getenv("GOOGLE_FACTCHECK_API_KEY"))
NEWSDATA_API_KEY = getattr(settings, 'newsdata_api_key', os.getenv("NEWSDATA_API_KEY"))
LIVEKIT_URL = getattr(settings, 'livekit_url', os.getenv("LIVEKIT_URL", "ws://localhost:7880"))
LIVEKIT_API_KEY = getattr(settings, 'livekit_api_key', os.getenv("LIVEKIT_API_KEY", "devkey"))
LIVEKIT_API_SECRET = getattr(settings, 'livekit_api_secret', os.getenv("LIVEKIT_API_SECRET", "secret"))

# CORS origins as list
CORS_ORIGINS = [
    o.strip()
    for o in settings.cors_origins.split(",")
    if o.strip()
]
