import asyncio
import logging
from typing import Dict, Any

import requests

from ..tool_registry import Tool, registry

logger = logging.getLogger(__name__)

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"

WMO_CODES = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Foggy", 48: "Depositing rime fog",
    51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
    61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
    71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow",
    80: "Slight rain showers", 81: "Moderate rain showers", 82: "Violent rain showers",
    95: "Thunderstorm", 96: "Thunderstorm with slight hail", 99: "Thunderstorm with heavy hail",
}


class WeatherTool(Tool):
    @property
    def name(self) -> str:
        return "get_weather"

    @property
    def description(self) -> str:
        return "Get the current weather for any location (free, no API key)."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "City name, e.g. 'London' or 'Mumbai, India'."
                }
            },
            "required": ["location"]
        }

    def _geocode(self, location: str) -> tuple:
        resp = requests.get(GEOCODING_URL, params={"name": location, "count": 1}, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("results"):
            r = data["results"][0]
            return r["latitude"], r["longitude"], r.get("name", location)
        return None, None, location

    async def execute(self, location: str) -> str:
        try:
            lat, lon, name = await asyncio.to_thread(self._geocode, location)
            if lat is None:
                return f"Could not find coordinates for '{location}'."

            params = {
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m",
                "timezone": "auto",
            }
            resp = await asyncio.to_thread(
                lambda: requests.get(WEATHER_URL, params=params, timeout=10)
            )
            resp.raise_for_status()
            data = resp.json()
            current = data.get("current", {})

            temp = current.get("temperature_2m", "?")
            feels_like = current.get("apparent_temperature", "?")
            humidity = current.get("relative_humidity_2m", "?")
            wind = current.get("wind_speed_10m", "?")
            code = current.get("weather_code", 0)
            description = WMO_CODES.get(code, f"Code {code}")

            return (
                f"Weather in {name}: {description}, "
                f"Temperature {temp}°C (feels like {feels_like}°C), "
                f"Humidity {humidity}%, Wind {wind} km/h"
            )
        except Exception as e:
            logger.error(f"Weather tool error: {e}")
            return f"Error fetching weather for '{location}': {e}"


registry.register(WeatherTool())
