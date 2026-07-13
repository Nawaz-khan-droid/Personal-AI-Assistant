"""
Logging utility with structured JSON logging.

Why: Structured logs are essential for production debugging and monitoring.
They're easily searchable and can be ingested by log aggregation tools.

Best Practice: Use JSON format for machine-readable logs in production.
"""

import logging
import json
import sys
from datetime import datetime, timezone
from typing import Any, Dict
from pathlib import Path


class JSONFormatter(logging.Formatter):
    """
    Format logs as JSON for easy parsing and analysis.
    
    Example output:
    {
        "timestamp": "2026-02-14T19:21:00Z",
        "level": "INFO",
        "message": "User query processed",
        "session_id": "sess_123",
        "execution_time_ms": 245
    }
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Include extra fields passed via logging.info(..., extra={...})
        for key in ["session_id", "user_id", "ip_address", "tool_name",
                    "execution_time_ms", "status"]:
            if hasattr(record, key):
                log_data[key] = getattr(record, key)
        
        # Include exception if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_data)


def setup_logging(log_level: str = "INFO", log_file: str = None):
    """
    Configure application-wide logging.
    
    Args:
        log_level: Minimum level to log (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional file path for log output
    
    Best Practice: Log to both console (for dev) and file (for prod).
    """
    # Create formatter
    json_formatter = JSONFormatter()
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(json_formatter)
    
    # Setup root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    root_logger.addHandler(console_handler)
    
    # File handler (if specified)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(json_formatter)
        root_logger.addHandler(file_handler)
    
    # Suppress noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    
    return root_logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger for a specific module.
    
    Usage:
        logger = get_logger(__name__)
        logger.info("Processing request", extra={"session_id": session_id})
    """
    return logging.getLogger(name)
