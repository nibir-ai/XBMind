"""Pydantic v2 configuration models for XBMind.

Loads settings from YAML config files and environment variables.
Environment variables use the prefix ``XBMIND_`` with double-underscore
nesting (e.g. ``XBMIND_LLM__MODEL``).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# ── Sub-models ────────────────────────────────────────────────────────────────


class BluetoothConfig(BaseModel):
    """Bluetooth connection settings."""

    device_name: str = Field(default="SRS-XB100", description="Target BT device name (substring)")
    device_mac: str = Field(default="", description="MAC address, empty for auto-discovery")
    auto_pair: bool = Field(default=True, description="Auto-pair discovered devices")
    reconnect_enabled: bool = Field(default=True, description="Enable auto-reconnect")
    reconnect_base_delay: float = Field(default=1.0, ge=0.1, description="Base delay in seconds")
    reconnect_max_delay: float = Field(default=60.0, ge=1.0, description="Max backoff delay")
    reconnect_max_attempts: int = Field(default=0, ge=0, description="0 = infinite retries")
    profile: str = Field(default="a2dp_sink", description="Preferred BT profile")


class AudioConfig(BaseModel):
    """Audio capture settings."""

    input_device: int | None = Field(default=None, description="Device index, None=auto")
    sample_rate: int = Field(default=16000, ge=8000, le=48000)
    channels: int = Field(default=1, ge=1, le=2)
    block_size: int = Field(default=512, ge=64)
    dtype: str = Field(default="float32")


class VADConfig(BaseModel):
    """Voice Activity Detection settings."""

    threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    min_speech_duration: float = Field(default=0.3, ge=0.05)
    silence_duration: float = Field(default=1.5, ge=0.1)
    pre_roll_duration: float = Field(default=0.5, ge=0.0)
    max_recording_duration: float = Field(default=30.0, ge=1.0)


class WakeWordConfig(BaseModel):
    """Wake word detection settings."""

    model_name: str = Field(default="hey_jarvis", description="openWakeWord model name")
    threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    inference_framework: str = Field(default="onnx", pattern=r"^(onnx|tflite)$")
    play_chime: bool = Field(default=True)
    chime_path: str | None = Field(default=None, description="Custom chime WAV path")


class FasterWhisperConfig(BaseModel):
    """faster-whisper STT engine settings."""

    model_size: str = Field(default="base")
    device: str = Field(default="auto")
    compute_type: str = Field(default="int8")
    language: str | None = Field(default=None)
    beam_size: int = Field(default=5, ge=1)


class GoogleCloudSTTConfig(BaseModel):
    """Google Cloud Speech-to-Text settings."""

    language_code: str = Field(default="en-US")
    model: str = Field(default="latest_long")


class STTConfig(BaseModel):
    """Speech-to-Text settings."""

    provider: str = Field(default="faster_whisper", pattern=r"^(faster_whisper|google_cloud)$")
    faster_whisper: FasterWhisperConfig = Field(default_factory=FasterWhisperConfig)
    google_cloud: GoogleCloudSTTConfig = Field(default_factory=GoogleCloudSTTConfig)


class OllamaConfig(BaseModel):
    """Ollama LLM settings."""

    base_url: str = Field(default="http://localhost:11434")
    model: str = Field(default="llama3.2")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=500, ge=1)
    timeout: float = Field(default=30.0, ge=1.0)


class OpenAIConfig(BaseModel):
    """OpenAI API settings."""

    model: str = Field(default="gpt-4o-mini")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=500, ge=1)


class ClaudeConfig(BaseModel):
    """Anthropic Claude API settings."""

    model: str = Field(default="claude-3-haiku-20240307")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=500, ge=1)


class GeminiConfig(BaseModel):
    """Google Gemini API settings."""

    model: str = Field(default="gemini-1.5-flash")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=500, ge=1)


class MemoryConfig(BaseModel):
    """Conversation memory settings."""

    db_path: str = Field(default="data/conversations.db")
    max_messages: int = Field(default=50, ge=0)
    keep_recent: int = Field(default=10, ge=1)


class LLMConfig(BaseModel):
    """LLM provider settings."""

    provider: str = Field(
        default="ollama", pattern=r"^(ollama|openai|claude|gemini)$"
    )
    system_prompt: str = Field(
        default=(
            "You are XBMind, a helpful AI voice assistant running on a local machine. "
            "You are connected to a Bluetooth speaker. Be concise and conversational."
        )
    )
    ollama: OllamaConfig = Field(default_factory=OllamaConfig)
    openai: OpenAIConfig = Field(default_factory=OpenAIConfig)
    claude: ClaudeConfig = Field(default_factory=ClaudeConfig)
    gemini: GeminiConfig = Field(default_factory=GeminiConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)


class WeatherToolConfig(BaseModel):
    """Weather tool settings."""

    base_url: str = Field(default="https://wttr.in")
    default_location: str = Field(default="")
    timeout: float = Field(default=10.0, ge=1.0)


class TimerToolConfig(BaseModel):
    """Timer tool settings."""

    max_duration: int = Field(default=3600, ge=1)
    alert_message: str = Field(default="Your timer has finished!")


class ShellToolConfig(BaseModel):
    """Shell tool settings."""

    allowlist: list[str] = Field(
        default_factory=lambda: ["date", "uptime", "df -h", "free -h", "uname -a", "hostname"]
    )
    timeout: int = Field(default=10, ge=1)
    max_output_length: int = Field(default=1000, ge=100)


class ToolsEnabledConfig(BaseModel):
    """Toggle individual tools on/off."""

    weather: bool = True
    datetime: bool = True
    timer: bool = True
    wikipedia: bool = True
    shell: bool = False


class ToolsConfig(BaseModel):
    """Tools settings."""

    enabled: ToolsEnabledConfig = Field(default_factory=ToolsEnabledConfig)
    weather: WeatherToolConfig = Field(default_factory=WeatherToolConfig)
    timer: TimerToolConfig = Field(default_factory=TimerToolConfig)
    shell: ShellToolConfig = Field(default_factory=ShellToolConfig)


class PiperConfig(BaseModel):
    """Piper TTS settings."""

    executable: str = Field(default="piper")
    model_path: str = Field(default="models/piper/en_US-lessac-medium.onnx")
    sample_rate: int = Field(default=22050, ge=8000)
    length_scale: float = Field(default=1.0, ge=0.1, le=5.0)
    sentence_silence: float = Field(default=0.2, ge=0.0)


class ElevenLabsConfig(BaseModel):
    """ElevenLabs TTS settings."""

    voice_id: str = Field(default="21m00Tcm4TlvDq8ikWAM")
    model_id: str = Field(default="eleven_monolingual_v1")
    stability: float = Field(default=0.5, ge=0.0, le=1.0)
    similarity_boost: float = Field(default=0.75, ge=0.0, le=1.0)


class TTSConfig(BaseModel):
    """Text-to-Speech settings."""

    provider: str = Field(default="piper", pattern=r"^(piper|elevenlabs)$")
    piper: PiperConfig = Field(default_factory=PiperConfig)
    elevenlabs: ElevenLabsConfig = Field(default_factory=ElevenLabsConfig)


class HealthConfig(BaseModel):
    """Health check server settings."""

    enabled: bool = True
    host: str = Field(default="127.0.0.1")
    port: int = Field(default=7070, ge=1024, le=65535)


class LoggingConfig(BaseModel):
    """Logging settings."""

    level: str = Field(default="info", pattern=r"^(debug|info|warning|error)$")
    format: str = Field(default="console", pattern=r"^(console|json)$")
    file: str | None = Field(default=None)


# ── Root Settings ─────────────────────────────────────────────────────────────


class XBMindSettings(BaseSettings):
    """Root configuration for XBMind.

    Settings are loaded in this priority order (highest wins):
    1. Environment variables (``XBMIND_`` prefix)
    2. YAML config file
    3. Default values
    """

    model_config = SettingsConfigDict(
        env_prefix="XBMIND_",
        env_nested_delimiter="__",
        case_sensitive=False,
    )

    bluetooth: BluetoothConfig = Field(default_factory=BluetoothConfig)
    audio: AudioConfig = Field(default_factory=AudioConfig)
    vad: VADConfig = Field(default_factory=VADConfig)
    wake_word: WakeWordConfig = Field(default_factory=WakeWordConfig)
    stt: STTConfig = Field(default_factory=STTConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    tts: TTSConfig = Field(default_factory=TTSConfig)
    health: HealthConfig = Field(default_factory=HealthConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge *override* into *base*, returning a new dict."""
    merged = base.copy()
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_settings(config_path: str | Path | None = None) -> XBMindSettings:
    """Load settings from YAML file and environment variables.

    Args:
        config_path: Path to a YAML config file. If ``None``, tries
            ``config/local.yaml`` then ``config/config.yaml``.

    Returns:
        Fully validated ``XBMindSettings`` instance.
    """
    yaml_data: dict[str, Any] = {}

    if config_path is None:
        candidates = [
            Path("config/local.yaml"),
            Path("config/config.yaml"),
        ]
        for candidate in candidates:
            if candidate.is_file():
                config_path = candidate
                break

    if config_path is not None:
        path = Path(config_path)
        if path.is_file():
            with open(path, encoding="utf-8") as fh:
                loaded = yaml.safe_load(fh)
                if isinstance(loaded, dict):
                    yaml_data = loaded

    # Allow env-var override of config path
    env_config = os.environ.get("XBMIND_CONFIG")
    if env_config:
        env_path = Path(env_config)
        if env_path.is_file():
            with open(env_path, encoding="utf-8") as fh:
                loaded = yaml.safe_load(fh)
                if isinstance(loaded, dict):
                    yaml_data = _deep_merge(yaml_data, loaded)

    return XBMindSettings(**yaml_data)
