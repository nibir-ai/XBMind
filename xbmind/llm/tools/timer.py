"""Timer tool with async TTS alert.

Sets a countdown timer that triggers a spoken TTS alert when it expires.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from xbmind.llm.base import ToolDefinition
from xbmind.llm.tools.base_tool import BaseTool
from xbmind.utils.events import Event, EventBus, EventType
from xbmind.utils.logger import get_logger

if TYPE_CHECKING:
    from xbmind.config import TimerToolConfig

log = get_logger(__name__)


class TimerTool(BaseTool):
    """Sets a countdown timer with an async TTS alert.

    When the timer expires, it publishes a ``TIMER_ALERT`` event
    that the orchestrator handles by speaking the alert message.

    Example::

        tool = TimerTool(config, event_bus)
        result = await tool.execute(seconds=300, label="pasta")
    """

    def __init__(self, config: TimerToolConfig, event_bus: EventBus) -> None:
        """Initialise the timer tool.

        Args:
            config: Timer tool configuration.
            event_bus: Event bus for publishing timer alerts.
        """
        self._config = config
        self._event_bus = event_bus
        self._active_timers: dict[str, asyncio.Task[None]] = {}

    @property
    def definition(self) -> ToolDefinition:
        """Tool definition for the LLM."""
        return ToolDefinition(
            name="set_timer",
            description=(
                "Set a countdown timer. When it expires, the assistant will "
                "speak an alert. Useful for cooking, reminders, etc."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "seconds": {
                        "type": "integer",
                        "description": "Timer duration in seconds (1-3600)",
                    },
                    "label": {
                        "type": "string",
                        "description": "Optional label for the timer (e.g. 'pasta', 'tea')",
                    },
                },
                "required": ["seconds"],
            },
        )

    async def execute(self, **kwargs: Any) -> str:
        """Set a countdown timer.

        Args:
            **kwargs: Must include ``seconds`` (int), optionally ``label`` (str).

        Returns:
            Confirmation message.
        """
        seconds = int(kwargs.get("seconds", 0))
        label = kwargs.get("label", "timer")

        if seconds <= 0:
            return "Error: Timer duration must be a positive number of seconds."

        if seconds > self._config.max_duration:
            return f"Error: Timer duration cannot exceed {self._config.max_duration} seconds."

        # Create the timer task
        timer_id = f"{label}_{seconds}"
        task = asyncio.create_task(
            self._timer_coroutine(seconds, label, timer_id),
            name=f"timer_{timer_id}",
        )
        self._active_timers[timer_id] = task

        # Format duration for display
        if seconds >= 3600:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            duration_str = f"{hours} hour{'s' if hours != 1 else ''}"
            if minutes:
                duration_str += f" and {minutes} minute{'s' if minutes != 1 else ''}"
        elif seconds >= 60:
            minutes = seconds // 60
            remaining_secs = seconds % 60
            duration_str = f"{minutes} minute{'s' if minutes != 1 else ''}"
            if remaining_secs:
                duration_str += f" and {remaining_secs} second{'s' if remaining_secs != 1 else ''}"
        else:
            duration_str = f"{seconds} second{'s' if seconds != 1 else ''}"

        log.info("tool.timer.set", seconds=seconds, label=label)
        return f"Timer set for {duration_str} (label: {label}). I'll alert you when it's done."

    async def _timer_coroutine(self, seconds: int, label: str, timer_id: str) -> None:
        """Wait for the timer duration, then fire an alert.

        Args:
            seconds: Duration to wait.
            label: Timer label.
            timer_id: Unique timer identifier.
        """
        try:
            await asyncio.sleep(seconds)

            alert_message = f"{self._config.alert_message} Your {label} timer is done!"

            await self._event_bus.publish(
                Event(
                    EventType.TIMER_ALERT,
                    data={"label": label, "message": alert_message},
                    source="timer_tool",
                )
            )

            log.info("tool.timer.expired", label=label, seconds=seconds)
        except asyncio.CancelledError:
            log.info("tool.timer.cancelled", label=label)
        finally:
            self._active_timers.pop(timer_id, None)

    async def cancel_all(self) -> None:
        """Cancel all active timers."""
        for _timer_id, task in list(self._active_timers.items()):
            task.cancel()
        self._active_timers.clear()
