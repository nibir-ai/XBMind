"""Date/time tool.

Returns the current date and time for a given timezone.
"""

from __future__ import annotations

import datetime
import zoneinfo
from typing import Any

from xbmind.llm.base import ToolDefinition
from xbmind.llm.tools.base_tool import BaseTool
from xbmind.utils.logger import get_logger

log = get_logger(__name__)


class DateTimeTool(BaseTool):
    """Returns the current date and time.

    Example::

        tool = DateTimeTool()
        result = await tool.execute(timezone="America/New_York")
    """

    @property
    def definition(self) -> ToolDefinition:
        """Tool definition for the LLM."""
        return ToolDefinition(
            name="datetime",
            description=(
                "Get the current date and time. "
                "Optionally specify a timezone (e.g. 'America/New_York', 'Europe/London', 'Asia/Tokyo')."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "timezone": {
                        "type": "string",
                        "description": (
                            "IANA timezone name (e.g. 'UTC', 'America/New_York'). "
                            "Defaults to the system local timezone."
                        ),
                    },
                },
                "required": [],
            },
        )

    async def execute(self, **kwargs: Any) -> str:
        """Get the current date and time.

        Args:
            **kwargs: Optional ``timezone`` (str).

        Returns:
            Formatted date and time string.
        """
        tz_name = kwargs.get("timezone", "")

        try:
            if tz_name:
                tz = zoneinfo.ZoneInfo(tz_name)
            else:
                tz = datetime.datetime.now().astimezone().tzinfo  # type: ignore[assignment]
                tz_name = str(tz)
        except (KeyError, zoneinfo.ZoneInfoNotFoundError):
            return f"Error: Unknown timezone '{tz_name}'. Use IANA timezone names like 'America/New_York'."

        now = datetime.datetime.now(tz=tz)

        return (
            f"Current date and time ({tz_name}):\n"
            f"• Date: {now.strftime('%A, %B %d, %Y')}\n"
            f"• Time: {now.strftime('%I:%M:%S %p')}\n"
            f"• ISO: {now.isoformat()}\n"
            f"• Unix timestamp: {int(now.timestamp())}"
        )
