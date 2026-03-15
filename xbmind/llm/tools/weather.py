"""Weather tool using wttr.in.

Fetches current weather information via the free wttr.in API.
No API key required.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import httpx

from xbmind.llm.base import ToolDefinition
from xbmind.llm.tools.base_tool import BaseTool
from xbmind.utils.logger import get_logger

if TYPE_CHECKING:
    from xbmind.config import WeatherToolConfig

log = get_logger(__name__)


class WeatherTool(BaseTool):
    """Fetches weather information from wttr.in.

    Example::

        tool = WeatherTool(config)
        result = await tool.execute(location="London")
    """

    def __init__(self, config: WeatherToolConfig) -> None:
        """Initialise the weather tool.

        Args:
            config: Weather tool configuration.
        """
        self._config = config

    @property
    def definition(self) -> ToolDefinition:
        """Tool definition for the LLM."""
        return ToolDefinition(
            name="weather",
            description=(
                "Get the current weather for a given location. "
                "Returns temperature, conditions, humidity, and wind."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "City name or location (e.g. 'London', 'New York', 'Tokyo')",
                    },
                },
                "required": ["location"],
            },
        )

    async def execute(self, **kwargs: Any) -> str:
        """Fetch weather data for the given location.

        Args:
            **kwargs: Must include ``location`` (str).

        Returns:
            Formatted weather information string.
        """
        location = kwargs.get("location", self._config.default_location or "")
        if not location:
            return "Error: No location provided and no default configured."

        try:
            async with httpx.AsyncClient(timeout=self._config.timeout) as client:
                response = await client.get(
                    f"{self._config.base_url}/{location}",
                    params={"format": "j1"},
                    headers={"User-Agent": "XBMind/0.1"},
                )
                response.raise_for_status()
                data = response.json()

            current = data.get("current_condition", [{}])[0]
            area = data.get("nearest_area", [{}])[0]

            area_name = area.get("areaName", [{}])[0].get("value", location)
            country = area.get("country", [{}])[0].get("value", "")
            temp_c = current.get("temp_C", "?")
            temp_f = current.get("temp_F", "?")
            desc = current.get("weatherDesc", [{}])[0].get("value", "Unknown")
            humidity = current.get("humidity", "?")
            wind_kmph = current.get("windspeedKmph", "?")
            wind_dir = current.get("winddir16Point", "?")
            feels_like_c = current.get("FeelsLikeC", "?")

            return (
                f"Weather in {area_name}, {country}:\n"
                f"• Condition: {desc}\n"
                f"• Temperature: {temp_c}°C ({temp_f}°F)\n"
                f"• Feels like: {feels_like_c}°C\n"
                f"• Humidity: {humidity}%\n"
                f"• Wind: {wind_kmph} km/h {wind_dir}"
            )

        except httpx.HTTPStatusError as exc:
            log.exception("tool.weather.http_error", location=location)
            return f"Error fetching weather: HTTP {exc.response.status_code}"
        except httpx.TimeoutException:
            log.error("tool.weather.timeout", location=location)
            return "Error: Weather service timed out."
        except (KeyError, IndexError, ValueError):
            log.exception("tool.weather.parse_error", location=location)
            return "Error: Could not parse weather data."
