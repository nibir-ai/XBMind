"""Tests for TTS providers."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from xbmind.config import ElevenLabsConfig, PiperConfig
from xbmind.tts.base import TTSProvider
from xbmind.tts.elevenlabs import ElevenLabsTTS
from xbmind.tts.piper import PiperTTS


class TestPiperTTS:
    """Tests for PiperTTS."""

    def test_init(self, piper_config: PiperConfig) -> None:
        """Test Piper provider initialisation."""
        tts = PiperTTS(piper_config)
        assert tts.name == "Piper TTS"
        assert tts.sample_rate == 22050

    @pytest.mark.asyncio
    async def test_synthesize_empty_text(self, piper_config: PiperConfig) -> None:
        """Test that empty text returns empty bytes."""
        tts = PiperTTS(piper_config)
        result = await tts.synthesize("")
        assert result == b""

    @pytest.mark.asyncio
    async def test_synthesize_whitespace_only(self, piper_config: PiperConfig) -> None:
        """Test that whitespace-only text returns empty bytes."""
        tts = PiperTTS(piper_config)
        result = await tts.synthesize("   ")
        assert result == b""

    def test_raw_to_wav(self, piper_config: PiperConfig) -> None:
        """Test raw PCM to WAV conversion."""
        tts = PiperTTS(piper_config)
        raw_pcm = b"\x00\x00" * 1000  # 1000 silent int16 samples
        wav_bytes = tts._raw_to_wav(raw_pcm)

        # WAV files start with "RIFF"
        assert wav_bytes[:4] == b"RIFF"
        assert len(wav_bytes) > len(raw_pcm)  # WAV has headers

    @pytest.mark.asyncio
    async def test_stop_without_process(self, piper_config: PiperConfig) -> None:
        """Test stopping when no process is running."""
        tts = PiperTTS(piper_config)
        await tts.stop()  # Should not raise


class TestElevenLabsTTS:
    """Tests for ElevenLabsTTS."""

    def test_init(self) -> None:
        """Test ElevenLabs provider initialisation."""
        config = ElevenLabsConfig()
        tts = ElevenLabsTTS(config)
        assert tts.name == "ElevenLabs"
        assert tts.sample_rate == 44100

    @pytest.mark.asyncio
    async def test_synthesize_without_start(self) -> None:
        """Test that synthesizing without starting raises RuntimeError."""
        config = ElevenLabsConfig()
        tts = ElevenLabsTTS(config)
        with pytest.raises(RuntimeError, match="not started"):
            await tts.synthesize("test")

    @pytest.mark.asyncio
    async def test_synthesize_empty_text(self) -> None:
        """Test that empty text returns empty bytes."""
        config = ElevenLabsConfig()
        tts = ElevenLabsTTS(config)
        tts._client = MagicMock()
        result = await tts.synthesize("")
        assert result == b""

    @pytest.mark.asyncio
    async def test_stop_clears_client(self) -> None:
        """Test that stopping closes the client."""
        config = ElevenLabsConfig()
        tts = ElevenLabsTTS(config)
        tts._client = AsyncMock()
        await tts.stop()
        assert tts._client is None
