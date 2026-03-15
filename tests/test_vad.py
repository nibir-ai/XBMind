"""Tests for Voice Activity Detection."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from xbmind.audio.vad import VoiceActivityDetector
from xbmind.config import AudioConfig, VADConfig
from xbmind.utils.events import Event, EventBus, EventType


class TestVoiceActivityDetector:
    """Tests for VoiceActivityDetector."""

    def test_init(
        self, vad_config: VADConfig, audio_config: AudioConfig, event_bus: EventBus
    ) -> None:
        """Test VAD initialisation."""
        vad = VoiceActivityDetector(vad_config, audio_config, event_bus)
        assert not vad._is_speaking
        assert len(vad._speech_chunks) == 0

    def test_pre_roll_buffer_size(
        self, vad_config: VADConfig, audio_config: AudioConfig, event_bus: EventBus
    ) -> None:
        """Test that pre-roll buffer is correctly sized."""
        vad = VoiceActivityDetector(vad_config, audio_config, event_bus)
        expected_size = int(audio_config.sample_rate * vad_config.pre_roll_duration)
        expected_blocks = max(1, expected_size // audio_config.block_size)
        assert vad._pre_roll.maxlen == expected_blocks

    @pytest.mark.asyncio
    async def test_stop_without_start(
        self, vad_config: VADConfig, audio_config: AudioConfig, event_bus: EventBus
    ) -> None:
        """Test stopping VAD without starting it first."""
        vad = VoiceActivityDetector(vad_config, audio_config, event_bus)
        await vad.stop()  # Should not raise

    @pytest.mark.asyncio
    async def test_on_audio_chunk_not_running(
        self, vad_config: VADConfig, audio_config: AudioConfig, event_bus: EventBus
    ) -> None:
        """Test that audio chunks are ignored when not running."""
        vad = VoiceActivityDetector(vad_config, audio_config, event_bus)
        chunk = np.zeros(512, dtype=np.float32)
        event = Event(EventType.AUDIO_CHUNK, data=chunk, source="test")
        await vad._on_audio_chunk(event)  # Should not raise

    @pytest.mark.asyncio
    async def test_speech_end_with_empty_chunks(
        self, vad_config: VADConfig, audio_config: AudioConfig, event_bus: EventBus
    ) -> None:
        """Test that ending speech with no chunks doesn't publish."""
        vad = VoiceActivityDetector(vad_config, audio_config, event_bus)
        vad._is_speaking = True
        vad._speech_chunks = []

        published_events: list[Event] = []
        event_bus.subscribe(
            EventType.VAD_SPEECH_END,
            AsyncMock(side_effect=lambda e: published_events.append(e)),
        )
        await event_bus.start()

        await vad._end_speech("test")
        assert not vad._is_speaking
        assert len(published_events) == 0

        await event_bus.stop()

    @pytest.mark.asyncio
    async def test_speech_too_short_discarded(
        self, vad_config: VADConfig, audio_config: AudioConfig, event_bus: EventBus
    ) -> None:
        """Test that speech shorter than min_speech_duration is discarded."""
        vad = VoiceActivityDetector(vad_config, audio_config, event_bus)
        vad._is_speaking = True
        vad._speech_duration = 0.1  # Less than min_speech_duration (0.3)
        short_chunk = np.zeros(100, dtype=np.float32)
        vad._speech_chunks = [short_chunk]

        await vad._end_speech("test")
        assert not vad._is_speaking
        assert len(vad._speech_chunks) == 0
