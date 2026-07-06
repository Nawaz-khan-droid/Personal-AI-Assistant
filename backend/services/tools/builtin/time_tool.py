import logging
from typing import Dict, Any
from datetime import datetime
from zoneinfo import ZoneInfo, available_timezones

from ..tool_registry import Tool, registry

logger = logging.getLogger(__name__)


class TimeTool(Tool):
    @property
    def name(self) -> str:
        return "get_current_time"

    @property
    def description(self) -> str:
        return "Get the current time in a specific timezone."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "timezone": {
                    "type": "string",
                    "description": "IANA timezone name, e.g. 'America/New_York', 'Europe/London', 'Asia/Tokyo'. Default UTC."
                }
            },
            "required": []
        }

    async def execute(self, timezone: str = "UTC") -> str:
        try:
            if timezone not in available_timezones():
                return f"Error: Unknown timezone '{timezone}'"
            tz = ZoneInfo(timezone)
            now = datetime.now(tz)
            return now.strftime("%Y-%m-%d %H:%M:%S %Z")
        except Exception as e:
            return f"Error getting time: {e}"


registry.register(TimeTool())
