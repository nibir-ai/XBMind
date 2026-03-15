"""Tests for the Orchestrator."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from xbmind.config import XBMindSettings
from xbmind.main import Orchestrator
from xbmind.utils.events import EventBus, EventType


class TestOrchestrator:
    """Tests for the main Orchestrator."""

    def test_init(self, settings: XBMindSettings) -> None:
        """Test orchestrator initialisation."""
        orch = Orchestrator(settings)
        assert not orch._running
        assert orch._session_id
        assert orch._tools == {}

    def test_create_stt_provider_default(self, settings: XBMindSettings) -> None:
        """Test STT provider factory returns faster-whisper by default."""
        orch = Orchestrator(settings)
        provider = orch._create_stt_provider()
        assert "faster-whisper" in provider.name

    def test_create_llm_provider_default(self, settings: XBMindSettings) -> None:
        """Test LLM provider factory returns Ollama by default."""
        orch = Orchestrator(settings)
        provider = orch._create_llm_provider()
        assert "Ollama" in provider.name

    def test_create_tts_provider_default(self, settings: XBMindSettings) -> None:
        """Test TTS provider factory returns Piper by default."""
        orch = Orchestrator(settings)
        provider = orch._create_tts_provider()
        assert "Piper" in provider.name

    def test_register_tools(self, settings: XBMindSettings) -> None:
        """Test that tools are registered based on config."""
        orch = Orchestrator(settings)
        orch._register_tools()
        # Default config enables weather, datetime, timer, wikipedia
        assert "weather" in orch._tools
        assert "datetime" in orch._tools
        assert "set_timer" in orch._tools
        assert "wikipedia" in orch._tools
        # Shell is disabled by default
        assert "shell" not in orch._tools

    def test_set_health(self, settings: XBMindSettings) -> None:
        """Test health status updates."""
        orch = Orchestrator(settings)
        # Without health server, should not raise
        orch._set_health("test", True)

    def test_resume_wake_word_no_detector(self, settings: XBMindSettings) -> None:
        """Test resuming wake word when detector is None."""
        orch = Orchestrator(settings)
        orch._resume_wake_word()  # Should not raise


class TestEventBus:
    """Tests for the EventBus."""

    @pytest.mark.asyncio
    async def test_publish_subscribe(self) -> None:
        """Test basic pub/sub functionality."""
        bus = EventBus()
        received: list[str] = []

        async def handler(event: MagicMock) -> None:
            received.append(event.data)

        bus.subscribe(EventType.WAKE_WORD_DETECTED, handler)
        await bus.start()

        from xbmind.utils.events import Event

        await bus.publish(Event(EventType.WAKE_WORD_DETECTED, data="test"))

        # Give the dispatch loop time to process
        import asyncio

        await asyncio.sleep(0.1)

        assert "test" in received
        await bus.stop()

    @pytest.mark.asyncio
    async def test_no_subscribers(self) -> None:
        """Test publishing with no subscribers doesn't raise."""
        bus = EventBus()
        await bus.start()

        from xbmind.utils.events import Event

        await bus.publish(Event(EventType.SHUTDOWN))

        import asyncio

        await asyncio.sleep(0.1)
        await bus.stop()

    def test_pending_property(self) -> None:
        """Test pending event count."""
        bus = EventBus()
        assert bus.pending == 0
