"""Async event bus for internal XBMind communication.

Provides a lightweight publish/subscribe system built on
:class:`asyncio.Queue`.  Components publish typed events; subscribers
receive them without direct coupling.
"""

from __future__ import annotations

import asyncio
import enum
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from xbmind.utils.logger import get_logger

log = get_logger(__name__)


class EventType(enum.Enum):
    """All internal event types in XBMind."""

    # Audio pipeline events
    AUDIO_CHUNK = "audio_chunk"
    VAD_SPEECH_START = "vad_speech_start"
    VAD_SPEECH_END = "vad_speech_end"

    # Wake word events
    WAKE_WORD_DETECTED = "wake_word_detected"

    # STT events
    STT_RESULT = "stt_result"
    STT_ERROR = "stt_error"

    # LLM events
    LLM_RESPONSE = "llm_response"
    LLM_TOOL_CALL = "llm_tool_call"
    LLM_ERROR = "llm_error"

    # TTS events
    TTS_START = "tts_start"
    TTS_DONE = "tts_done"
    TTS_ERROR = "tts_error"

    # Bluetooth events
    BT_CONNECTED = "bt_connected"
    BT_DISCONNECTED = "bt_disconnected"
    BT_RECONNECTING = "bt_reconnecting"

    # System events
    HEALTH_CHECK = "health_check"
    SHUTDOWN = "shutdown"
    TIMER_ALERT = "timer_alert"


@dataclass
class Event:
    """A typed event with optional payload.

    Attributes:
        type: The event type.
        data: Arbitrary payload data.
        source: Name of the component that emitted the event.
    """

    type: EventType
    data: Any = None
    source: str = ""


# Type alias for event handler coroutines
EventHandler = Callable[[Event], Coroutine[Any, Any, None]]


@dataclass
class _Subscription:
    """Internal subscription record."""

    event_type: EventType
    handler: EventHandler
    handler_name: str = ""


class EventBus:
    """Asynchronous publish/subscribe event bus.

    Example::

        bus = EventBus()
        bus.subscribe(EventType.WAKE_WORD_DETECTED, on_wake)
        await bus.start()
        await bus.publish(Event(EventType.WAKE_WORD_DETECTED))
    """

    def __init__(self, max_queue_size: int = 1000) -> None:
        """Initialise the event bus.

        Args:
            max_queue_size: Maximum number of queued events before back-pressure.
        """
        self._queue: asyncio.Queue[Event | None] = asyncio.Queue(maxsize=max_queue_size)
        self._subscriptions: list[_Subscription] = []
        self._running: bool = False
        self._task: asyncio.Task[None] | None = None

    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Register a handler for an event type.

        Args:
            event_type: The type of event to listen for.
            handler: An async callable that receives an :class:`Event`.
        """
        sub = _Subscription(
            event_type=event_type,
            handler=handler,
            handler_name=getattr(handler, "__qualname__", str(handler)),
        )
        self._subscriptions.append(sub)
        log.debug("event_bus.subscribed", event_type=event_type.value, handler=sub.handler_name)

    async def publish(self, event: Event) -> None:
        """Publish an event to all matching subscribers.

        Args:
            event: The event to publish.
        """
        await self._queue.put(event)

    def publish_nowait(self, event: Event) -> None:
        """Publish an event without waiting (drops if full).

        Args:
            event: The event to publish.
        """
        try:
            self._queue.put_nowait(event)
        except asyncio.QueueFull:
            log.warning("event_bus.queue_full", event_type=event.type.value)

    async def start(self) -> None:
        """Start the event dispatch loop."""
        self._running = True
        self._task = asyncio.create_task(self._dispatch_loop(), name="event_bus")
        log.info("event_bus.started")

    async def stop(self) -> None:
        """Stop the event dispatch loop gracefully."""
        self._running = False
        await self._queue.put(None)  # Sentinel to unblock
        if self._task:
            await self._task
            self._task = None
        log.info("event_bus.stopped")

    async def _dispatch_loop(self) -> None:
        """Main loop: dequeue events and dispatch to subscribers."""
        while self._running:
            event = await self._queue.get()
            if event is None:
                break

            handlers = [s for s in self._subscriptions if s.event_type == event.type]
            for sub in handlers:
                try:
                    await sub.handler(event)
                except Exception:
                    log.exception(
                        "event_bus.handler_error",
                        event_type=event.type.value,
                        handler=sub.handler_name,
                    )
            self._queue.task_done()

    @property
    def pending(self) -> int:
        """Number of events waiting in the queue."""
        return self._queue.qsize()
