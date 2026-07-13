import json
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


class CommandLogger:
    """
    Logs unrecognized/failed commands for debugging and model improvement.

    Adapted from thevickypedia/Jarvis training data collection pattern.
    Uses JSON-lines format (one JSON object per line) for safe concurrent appends.
    """

    def __init__(self, log_file: str = "unrecognized_commands.jsonl"):
        self.log_file = log_file

    def log(
        self,
        transcript: str,
        reason: str = "empty_transcript",
        session_id: Optional[str] = None,
        audio_size: Optional[int] = None,
        confidence: Optional[float] = None,
        details: Optional[str] = None,
    ):
        """Log an unrecognized or failed command."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "transcript": transcript,
            "reason": reason,
            "session_id": session_id,
            "audio_size_bytes": audio_size,
            "confidence": confidence,
            "details": details,
        }
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, default=str) + "\n")
            logger.debug(f"Logged command: {reason} | transcript={transcript!r}")
        except Exception as e:
            logger.error(f"Failed to log command: {e}")


command_logger = CommandLogger()
