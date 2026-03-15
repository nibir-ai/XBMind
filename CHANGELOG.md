# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Initial project scaffolding and full architecture
- Bluetooth auto-pair and reconnect via D-Bus with exponential backoff
- Audio capture with `sounddevice` and automatic device selection
- Silero VAD with 500ms pre-roll circular buffer
- openWakeWord detection in dedicated OS thread ("Hey Jarvis" default)
- Speech-to-text via faster-whisper (offline) with Google Cloud STT fallback
- LLM integration: Ollama (primary), OpenAI, Claude, Gemini providers
- SQLite conversation memory with auto-summarization
- Built-in tools: weather, datetime, timer, wikipedia, shell
- Piper TTS (offline) with ElevenLabs optional fallback
- Asyncio orchestrator with event bus architecture
- HTTP health check server on `localhost:7070/health`
- Systemd user service configuration
- Comprehensive documentation and setup scripts
