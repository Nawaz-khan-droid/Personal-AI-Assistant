import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
ELEVENLABS_STT_MODEL = os.getenv("ELEVENLABS_STT_MODEL", "scribe_v2")
GOOGLE_FACTCHECK_API_KEY = os.getenv("GOOGLE_FACTCHECK_API_KEY")
NEWSDATA_API_KEY = os.getenv("NEWSDATA_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-exp")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini")

# ElevenLabs settings
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "AolUMF9fjkrPfGw4trAx")
ELEVENLABS_AGENT_ID = os.getenv("ELEVENLABS_AGENT_ID", "")
ELEVENLABS_ENABLE_AGENT = os.getenv("ELEVENLABS_ENABLE_AGENT", "false").lower() in ("1", "true", "yes")

# FastAPI settings
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", 8000))

# Rate limiting
RATE_LIMIT = os.getenv("RATE_LIMIT", "10/minute")
LLM_RATE_LIMIT = os.getenv("LLM_RATE_LIMIT", "15/minute")

# Upload limits (bytes)
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "10"))
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024

# CORS
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://127.0.0.1:3000,http://localhost:3000,http://127.0.0.1:5500,http://localhost:5500").split(",") if o.strip()]

# Audio cleanup
TTS_TTL_SECONDS = int(os.getenv("TTS_TTL_SECONDS", "600"))

# Other defaults
DEFAULT_LANGUAGE = "en"

# Environment
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = os.getenv("LOG_FILE", "assistant.log")
