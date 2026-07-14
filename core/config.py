"""
core/config.py
--------------
Boot-time environment variable validation for the JARVIS Voice Assistant.

Loads all required keys from .env and fails FAST with a clear, actionable
error message if any are missing — before LiveKit, Groq, or Deepgram are
ever initialised.

No keys are hardcoded here. All values are read exclusively from the
environment / .env file via python-dotenv.
"""

import os
import sys
from dataclasses import dataclass
from dotenv import load_dotenv

# Load .env from the project root (one level up from this file's directory)
load_dotenv()


# ---------------------------------------------------------------------------
# Required environment variable names
# ---------------------------------------------------------------------------
_REQUIRED: dict[str, str] = {
    "LIVEKIT_URL":       "LiveKit Cloud WebSocket endpoint (wss://...)",
    "LIVEKIT_API_KEY":   "LiveKit Cloud API key",
    "LIVEKIT_API_SECRET": "LiveKit Cloud API secret",
    "GROQ_API_KEY":      "Groq Cloud API key (primary STT + LLM)",
    "DEEPGRAM_API_KEY":  "Deepgram API key (primary TTS)",
}


@dataclass(frozen=True)
class Settings:
    """
    Immutable, type-safe container for all resolved environment variables.
    Instantiate once at startup via Settings.load() and pass around.
    """
    livekit_url: str
    livekit_api_key: str
    livekit_api_secret: str
    groq_api_key: str
    deepgram_api_key: str
    gemini_api_key: str
    openai_api_key: str

    @classmethod
    def load(cls) -> "Settings":
        """
        Read and validate all required environment variables.

        Exits immediately with a descriptive error if any variable is absent
        or empty, so the problem is caught at process start — not mid-session.
        """
        missing: list[str] = []

        for key, description in _REQUIRED.items():
            value = os.environ.get(key, "").strip()
            if not value:
                missing.append(f"  {key:<25} — {description}")

        if missing:
            error_msg = (
                "STARTUP ABORTED — missing required environment variables:\n"
                + "\n".join(missing)
                + "\n\nSet them in your .env file at the project root and restart."
            )
            raise ValueError(error_msg)

        return cls(
            livekit_url=os.environ["LIVEKIT_URL"].strip(),
            livekit_api_key=os.environ["LIVEKIT_API_KEY"].strip(),
            livekit_api_secret=os.environ["LIVEKIT_API_SECRET"].strip(),
            groq_api_key=os.environ["GROQ_API_KEY"].strip(),
            deepgram_api_key=os.environ["DEEPGRAM_API_KEY"].strip(),
            gemini_api_key=os.environ.get("GEMINI_API_KEY", "").strip(),
            openai_api_key=os.environ.get("OPENAI_API_KEY", "").strip(),
        )


# ---------------------------------------------------------------------------
# Module-level singleton — imported by worker.py and other modules
# ---------------------------------------------------------------------------
settings = Settings.load()


# ---------------------------------------------------------------------------
# Self-test: run this file directly to verify your .env is wired correctly
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("[JARVIS] OK — All required environment variables loaded successfully.")
    print(f"  LIVEKIT_URL       : {settings.livekit_url}")
    print(f"  LIVEKIT_API_KEY   : {settings.livekit_api_key[:8]}...")
    print(f"  GROQ_API_KEY      : {settings.groq_api_key[:8]}...")
    print(f"  DEEPGRAM_API_KEY  : {settings.deepgram_api_key[:8]}...")
    print(f"  GEMINI_API_KEY    : {settings.gemini_api_key[:8]}...")
