<div align="center">

<img src="https://img.shields.io/badge/XBMind-v0.1.0-blueviolet?style=for-the-badge" alt="version" />

# XBMind

**Turn any Bluetooth speaker into an offline AI smart speaker.**

[![CI](https://github.com/nibir-ai/XBMind/actions/workflows/ci.yml/badge.svg)](https://github.com/nibir-ai/XBMind/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-69%20passed-brightgreen.svg)](#)
[![Lint](https://img.shields.io/badge/ruff-clean-green.svg)](#)

Zero hardware engineering — pure software only.  
Primary target: **Sony SRS-XB100** · Works with any A2DP Bluetooth speaker.

[Installation](#-quickstart) · [Documentation](#-documentation) · [Contributing](CONTRIBUTING.md) · [Roadmap](ROADMAP.md)

</div>

---

## What is XBMind?

XBMind turns a Linux machine + Bluetooth speaker + USB microphone into a fully functional **offline AI smart speaker** — like Alexa or Google Home, but running entirely on your hardware with no cloud dependency.

Say *"Hey Jarvis"*, ask a question, and hear the answer through your Bluetooth speaker. That's it.

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🔵 **Bluetooth Auto-Pair** | Discovers, pairs, and auto-reconnects with exponential backoff via D-Bus |
| 🎙️ **Always-On Mic** | Low-latency capture via `sounddevice` with USB mic auto-detection |
| 👂 **Wake Word** | openWakeWord (ONNX) in a dedicated OS thread — default: *"Hey Jarvis"* |
| 🗣️ **Speech-to-Text** | Offline via faster-whisper (CTranslate2) with optional Google Cloud fallback |
| 🧠 **LLM Brain** | Ollama (offline) with swappable providers: OpenAI, Claude, Gemini |
| 🔧 **Built-in Tools** | Weather, date/time, timers, Wikipedia, shell commands |
| 📢 **Text-to-Speech** | Piper TTS (offline) via subprocess pipe, optional ElevenLabs fallback |
| 💾 **Memory** | SQLite conversation history with auto-summarization |
| 🏥 **Health Check** | HTTP endpoint at `localhost:7070/health` with JSON component status |
| ⚙️ **Systemd Ready** | User service with auto-start, journald logging |

---

## 🏗️ How It Works

```
   Mic → Wake Word → VAD → STT → LLM → TTS → Bluetooth Speaker
              │                    │
         openWakeWord         Ollama (local)
         "Hey Jarvis"         + tool calling
```

<details>
<summary>Detailed pipeline diagram</summary>

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Bluetooth   │────▶│   Audio In   │────▶│  Wake Word   │
│  Manager     │     │  (sounddev)  │     │  (oww/onnx)  │
└──────────────┘     └──────────────┘     └──────┬───────┘
                                                 │ wake!
                                          ┌──────▼───────┐
                                          │     VAD      │
                                          │ (silero+buf) │
                                          └──────┬───────┘
                                                 │ speech
                                          ┌──────▼───────┐
                                          │     STT      │
                                          │  (whisper)   │
                                          └──────┬───────┘
                                                 │ text
                                          ┌──────▼───────┐
                  ┌──────────────────────▶│     LLM      │◀── Tools
                  │  conversation memory  │  (ollama)    │    (weather,
                  │  (SQLite)             └──────┬───────┘     timer, …)
                  │                              │ response
                  │                       ┌──────▼───────┐
                  │                       │     TTS      │
                  │                       │   (piper)    │
                  │                       └──────┬───────┘
                  │                              │ audio
                  │                       ┌──────▼───────┐
                  └───────────────────────│  Audio Out   │
                                          │  (BT sink)   │
                                          └──────────────┘
```

</details>

---

## 🚀 Quickstart

### Prerequisites

- **Linux** — Arch, Ubuntu, Debian, Fedora, openSUSE, Void, or Alpine
- **Python 3.11+** — tested up to 3.14
- **Bluetooth adapter** — built-in or USB dongle
- **USB microphone** — or built-in laptop mic

### Install

```bash
git clone https://github.com/nibir-ai/XBMind.git
cd XBMind
./scripts/install.sh
```

The interactive installer handles everything:

| Phase | What it does |
|-------|-------------|
| 1 | Detects your distro and package manager |
| 2 | Installs system dependencies (bluez, pipewire, portaudio) |
| 3 | Creates Python venv and installs all packages |
| 4 | Downloads AI models (Piper, Whisper, openWakeWord) |
| 5 | Installs and configures Ollama + pulls an LLM model |
| 6 | Configures Bluetooth auto-pairing |
| 7 | Sets up systemd user service |
| 8 | Creates local config with your speaker name |

Every step is optional — press `n` to skip.

### Run

```bash
# Activate venv (pick your shell):
source .venv/bin/activate        # bash / zsh
source .venv/bin/activate.fish   # fish

# Launch:
python -m xbmind.main

# Or run directly without activating:
.venv/bin/python -m xbmind.main

# Or as a systemd service:
systemctl --user enable --now xbmind
```

---

## 📁 Project Structure

```
XBMind/
├── xbmind/                  # Core Python package
│   ├── main.py              #   Orchestrator & entry point
│   ├── config.py            #   Pydantic v2 settings
│   ├── bluetooth/           #   D-Bus BT management + audio sink
│   ├── audio/               #   Mic capture, Silero VAD, playback
│   ├── wake_word/           #   openWakeWord detector
│   ├── stt/                 #   Speech-to-text (Whisper, Google)
│   ├── llm/                 #   LLM providers + tool system + memory
│   ├── tts/                 #   Text-to-speech (Piper, ElevenLabs)
│   └── utils/               #   Event bus, health server, logging
├── config/                  # YAML configuration files
├── scripts/                 # Interactive master installer
├── systemd/                 # Systemd user service
├── tests/                   # 69 pytest tests (all mocked, no hardware)
├── docs/                    # Full documentation
└── .github/                 # CI/CD workflows, issue templates
```

---

## 🐧 Supported Distros

| Distribution | Package Manager | Status |
|-------------|----------------|--------|
| Arch / Manjaro / EndeavourOS | `pacman` | ✅ Tested |
| Ubuntu / Debian / Pop!_OS | `apt` | ✅ Supported |
| Fedora / RHEL | `dnf` | ✅ Supported |
| openSUSE | `zypper` | ✅ Supported |
| Void Linux | `xbps` | ✅ Supported |
| Alpine Linux | `apk` | ⚠️ Experimental |

---

## 📖 Documentation

| Guide | Description |
|-------|-------------|
| [Architecture](docs/architecture.md) | System design, async model, event bus, thread model |
| [Installation](docs/installation.md) | Step-by-step setup for all distros |
| [Configuration](docs/configuration.md) | Every `config.yaml` key documented |
| [Custom Wake Word](docs/custom-wake-word.md) | Train your own openWakeWord model |
| [Custom TTS Voice](docs/custom-tts-voice.md) | Use any Piper ONNX voice |
| [Adding Tools](docs/adding-tools.md) | Write and register new LLM tools |
| [Troubleshooting](docs/troubleshooting.md) | 20+ real issues with fixes |
| [Hardware Tested](docs/hardware-tested.md) | Community-verified hardware list |

---

## 🤝 Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) for community standards.

## 📄 License

MIT — see [LICENSE](LICENSE).
