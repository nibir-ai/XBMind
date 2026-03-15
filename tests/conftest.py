"""Shared test fixtures for XBMind test suite."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from xbmind.config import (
    AudioConfig,
    BluetoothConfig,
    ElevenLabsConfig,
    FasterWhisperConfig,
    GoogleCloudSTTConfig,
    LLMConfig,
    MemoryConfig,
    OllamaConfig,
    PiperConfig,
    ShellToolConfig,
    STTConfig,
    TimerToolConfig,
    TTSConfig,
    VADConfig,
    WakeWordConfig,
    WeatherToolConfig,
    XBMindSettings,
)
from xbmind.utils.events import EventBus


@pytest.fixture
def event_bus() -> EventBus:
    """Create a test event bus."""
    return EventBus()


@pytest.fixture
def bluetooth_config() -> BluetoothConfig:
    """Create a test Bluetooth config."""
    return BluetoothConfig(
        device_name="TestSpeaker",
        auto_pair=False,
        reconnect_enabled=False,
    )


@pytest.fixture
def audio_config() -> AudioConfig:
    """Create a test audio config."""
    return AudioConfig(
        sample_rate=16000,
        channels=1,
        block_size=512,
    )


@pytest.fixture
def vad_config() -> VADConfig:
    """Create a test VAD config."""
    return VADConfig(
        threshold=0.5,
        pre_roll_duration=0.5,
        silence_duration=1.0,
        max_recording_duration=10.0,
    )


@pytest.fixture
def wake_word_config() -> WakeWordConfig:
    """Create a test wake word config."""
    return WakeWordConfig(
        model_name="hey_jarvis",
        threshold=0.5,
        play_chime=False,
    )


@pytest.fixture
def stt_config() -> FasterWhisperConfig:
    """Create a test STT config."""
    return FasterWhisperConfig(
        model_size="tiny",
        device="cpu",
        compute_type="int8",
    )


@pytest.fixture
def ollama_config() -> OllamaConfig:
    """Create a test Ollama config."""
    return OllamaConfig(
        base_url="http://localhost:11434",
        model="llama3.2",
        timeout=10.0,
    )


@pytest.fixture
def memory_config(tmp_path: object) -> MemoryConfig:
    """Create a test memory config with temp database."""
    return MemoryConfig(
        db_path=str(tmp_path) + "/test_conversations.db",  # type: ignore[operator]
        max_messages=10,
        keep_recent=3,
    )


@pytest.fixture
def piper_config() -> PiperConfig:
    """Create a test Piper config."""
    return PiperConfig(
        executable="piper",
        model_path="test_model.onnx",
        sample_rate=22050,
    )


@pytest.fixture
def weather_config() -> WeatherToolConfig:
    """Create a test weather tool config."""
    return WeatherToolConfig(timeout=5.0)


@pytest.fixture
def timer_config() -> TimerToolConfig:
    """Create a test timer tool config."""
    return TimerToolConfig(max_duration=60)


@pytest.fixture
def shell_config() -> ShellToolConfig:
    """Create a test shell tool config."""
    return ShellToolConfig(
        allowlist=["echo", "date", "uname -a"],
        timeout=5,
    )


@pytest.fixture
def sample_audio() -> np.ndarray:
    """Create a sample audio array (1 second of silence at 16kHz)."""
    return np.zeros(16000, dtype=np.float32)


@pytest.fixture
def sample_speech_audio() -> np.ndarray:
    """Create a sample audio array with a simulated tone."""
    t = np.linspace(0, 1.0, 16000, dtype=np.float32)
    return 0.5 * np.sin(2 * np.pi * 440 * t)


@pytest.fixture
def settings() -> XBMindSettings:
    """Create a full test settings object."""
    return XBMindSettings()
