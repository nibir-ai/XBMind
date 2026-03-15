"""Tests for Speech-to-Text providers."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from xbmind.config import FasterWhisperConfig, GoogleCloudSTTConfig
from xbmind.stt.base import STTProvider, TranscriptionResult
from xbmind.stt.faster_whisper import FasterWhisperSTT
from xbmind.stt.google_cloud import GoogleCloudSTT


class TestTranscriptionResult:
    """Tests for TranscriptionResult dataclass."""

    def test_creation(self) -> None:
        """Test creating a transcription result."""
        result = TranscriptionResult(
            text="hello world",
            confidence=0.95,
            language="en",
            duration=1.5,
        )
        assert result.text == "hello world"
        assert result.confidence == 0.95
        assert result.language == "en"
        assert result.duration == 1.5

    def test_frozen(self) -> None:
        """Test that TranscriptionResult is immutable."""
        result = TranscriptionResult(text="test", confidence=0.5)
        with pytest.raises(AttributeError):
            result.text = "changed"  # type: ignore[misc]


class TestFasterWhisperSTT:
    """Tests for FasterWhisperSTT."""

    def test_init(self, stt_config: FasterWhisperConfig) -> None:
        """Test provider initialisation."""
        stt = FasterWhisperSTT(stt_config)
        assert "faster-whisper" in stt.name
        assert stt._model is None

    @pytest.mark.asyncio
    async def test_transcribe_without_start(
        self, stt_config: FasterWhisperConfig, sample_audio: np.ndarray
    ) -> None:
        """Test that transcribing without loading raises RuntimeError."""
        stt = FasterWhisperSTT(stt_config)
        with pytest.raises(RuntimeError, match="not loaded"):
            await stt.transcribe(sample_audio)

    @pytest.mark.asyncio
    async def test_stop_clears_model(self, stt_config: FasterWhisperConfig) -> None:
        """Test that stopping clears the model reference."""
        stt = FasterWhisperSTT(stt_config)
        stt._model = MagicMock()
        await stt.stop()
        assert stt._model is None

    @pytest.mark.asyncio
    async def test_transcribe_with_mock_model(
        self, stt_config: FasterWhisperConfig, sample_audio: np.ndarray
    ) -> None:
        """Test transcription with a mocked Whisper model."""
        stt = FasterWhisperSTT(stt_config)

        mock_segment = MagicMock()
        mock_segment.text = " Hello world"
        mock_segment.avg_log_prob = -0.3

        mock_info = MagicMock()
        mock_info.language = "en"

        mock_model = MagicMock()
        mock_model.transcribe.return_value = ([mock_segment], mock_info)
        stt._model = mock_model

        result = await stt.transcribe(sample_audio)
        assert result.text == "Hello world"
        assert result.language == "en"
        assert 0.0 <= result.confidence <= 1.0


class TestGoogleCloudSTT:
    """Tests for GoogleCloudSTT."""

    def test_init(self) -> None:
        """Test provider initialisation."""
        config = GoogleCloudSTTConfig()
        stt = GoogleCloudSTT(config)
        assert stt.name == "Google Cloud STT"
        assert stt._client is None

    @pytest.mark.asyncio
    async def test_transcribe_without_start(self, sample_audio: np.ndarray) -> None:
        """Test that transcribing without starting raises RuntimeError."""
        config = GoogleCloudSTTConfig()
        stt = GoogleCloudSTT(config)
        with pytest.raises(RuntimeError, match="not initialised"):
            await stt.transcribe(sample_audio)

    @pytest.mark.asyncio
    async def test_stop_clears_client(self) -> None:
        """Test that stopping clears the client."""
        config = GoogleCloudSTTConfig()
        stt = GoogleCloudSTT(config)
        stt._client = MagicMock()
        await stt.stop()
        assert stt._client is None
