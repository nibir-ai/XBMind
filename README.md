<![CDATA[<div align="center">

# 🔊 XBMind

**Turn any Bluetooth speaker into an offline-first AI smart speaker.**

[![CI](https://github.com/xbmind/xbmind/actions/workflows/ci.yml/badge.svg)](https://github.com/xbmind/xbmind/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

*Zero hardware engineering — pure software only.*

</div>

---

## ✨ Features

- **🔵 Bluetooth Auto-Pair** — Scans, pairs, and reconnects to your Bluetooth speaker with exponential backoff. A2DP profile handling via D-Bus.
- **🎙️ Always-On Microphone** — Low-latency `sounddevice` capture with automatic device selection and Silero VAD with 500ms pre-roll buffer.
- **👂 Wake Word Detection** — openWakeWord running in a dedicated OS thread. Default: *"Hey Jarvis"*. Chime on activation.
- **🗣️ Speech-to-Text** — Offline-first via faster-whisper (CTranslate2). Optional Google Cloud STT fallback.
- **🧠 LLM Reasoning** — Ollama (offline-first) with swappable providers: OpenAI, Claude, Gemini. SQLite conversation memory with auto-summarization.
- **🔧 Built-in Tools** — Weather, date/time, timers, Wikipedia, and a configurable shell command runner.
- **📢 Text-to-Speech** — Piper TTS (offline) via subprocess pipe. Optional ElevenLabs cloud fallback.
- **🏥 Health Monitoring** — HTTP health check on `localhost:7070/health`. Systemd integration.

## 🏗️ Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Bluetooth   │────▶│   Audio In   │────▶│  Wake Word   │
│  Manager     │     │  (capture)   │     │  (oww)       │
└──────────────┘     └──────────────┘     └──────┬───────┘
                                                 │ wake!
                                          ┌──────▼───────┐
                                          │     VAD      │
                                          │  (silero)    │
                                          └──────┬───────┘
                                                 │ speech
                                          ┌──────▼───────┐
                                          │     STT      │
                                          │  (whisper)   │
                                          └──────┬───────┘
                                                 │ text
                                          ┌──────▼───────┐
                  ┌───────────────────────▶│     LLM      │◀── Tools
                  │  conversation memory   │  (ollama)    │    (weather,
                  │  (SQLite)              └──────┬───────┘     timer, …)
                  │                               │ response
                  │                        ┌──────▼───────┐
                  │                        │     TTS      │
                  │                        │  (piper)     │
                  │                        └──────┬───────┘
                  │                               │ audio
                  │                        ┌──────▼───────┐
                  └────────────────────────│  Audio Out   │
                                           │  (BT sink)   │
                                           └──────────────┘
```

## 🚀 Quickstart

### Prerequisites

- **Linux** (Arch, Ubuntu, Debian, Fedora, openSUSE, Void, Alpine)
- **Python 3.11+** (tested up to 3.14)
- **Bluetooth adapter** (built-in or USB)
- **USB microphone** (or built-in)

### One-Command Install

```bash
git clone https://github.com/xbmind/xbmind.git
cd xbmind
./scripts/install.sh
```

The interactive installer handles **everything** — system packages, Python venv, AI models, Ollama, Bluetooth setup, and systemd service. It auto-detects your distro and package manager.

### Running

```bash
# Activate the virtual environment (pick your shell):
source .venv/bin/activate        # bash / zsh
source .venv/bin/activate.fish   # fish
source .venv/bin/activate.csh    # csh / tcsh

# Or skip activation — run directly:
.venv/bin/python -m xbmind.main

# As a systemd service (no activation needed):
systemctl --user start xbmind
```

## 📁 Project Structure

```
xbmind/
├── xbmind/
│   ├── main.py              # Orchestrator & entry point
│   ├── config.py             # Pydantic v2 config models
│   ├── bluetooth/            # D-Bus BT management
│   ├── audio/                # Capture, VAD, playback
│   ├── wake_word/            # openWakeWord detector
│   ├── stt/                  # Speech-to-text providers
│   ├── llm/                  # LLM providers & tools
│   ├── tts/                  # Text-to-speech providers
│   └── utils/                # Logging, events, health
├── config/                   # YAML config files
├── scripts/                  # Setup & install scripts
├── systemd/                  # Systemd service file
├── tests/                    # Pytest test suite
└── docs/                     # Documentation
```

## 📖 Documentation

- [Architecture](docs/architecture.md)
- [Installation Guide](docs/installation.md)
- [Configuration Reference](docs/configuration.md)
- [Custom Wake Word](docs/custom-wake-word.md)
- [Custom TTS Voice](docs/custom-tts-voice.md)
- [Adding Tools](docs/adding-tools.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Hardware Tested](docs/hardware-tested.md)

## 🤝 Contributing

Contributions are welcome! Please read our [Contributing Guide](CONTRIBUTING.md) and [Code of Conduct](CODE_OF_CONDUCT.md) before submitting.

## 📄 License

This project is licensed under the MIT License — see [LICENSE](LICENSE) for details.
]]>
