# Installation Guide

## Supported Distributions

| Distribution | Package Manager | Status |
|-------------|----------------|--------|
| **Arch Linux / Manjaro / EndeavourOS** | `pacman` | ✅ Fully supported |
| **Ubuntu / Debian / Pop!_OS / Mint** | `apt` | ✅ Fully supported |
| **Fedora / RHEL / CentOS Stream** | `dnf` | ✅ Fully supported |
| **openSUSE Tumbleweed / Leap** | `zypper` | ✅ Fully supported |
| **Void Linux** | `xbps` | ✅ Supported |
| **Alpine Linux** | `apk` | ⚠️ Experimental |

## Prerequisites

- **Linux** (any distro listed above)
- **Python 3.11+** (tested up to 3.14)
- **Bluetooth adapter** (built-in or USB dongle)
- **USB microphone** (or built-in laptop mic)
- **Bluetooth speaker** (any A2DP speaker; target: Sony XB100)

## One-Command Install

```bash
git clone https://github.com/nibir-ai/XBMind.git
cd XBMind
./scripts/install.sh
```

The installer is fully interactive and handles **everything**:

1. **Detects your distro** and installs system packages automatically
2. **Creates a Python venv** and installs all dependencies
3. **Installs PyTorch** (CPU-only by default; offers CUDA if GPU detected)
4. **Downloads AI models** (Piper TTS, openWakeWord, faster-whisper)
5. **Installs Ollama** and lets you choose an LLM model
6. **Configures Bluetooth** for auto-pairing
7. **Sets up systemd** user service for auto-start
8. **Creates your config** and asks for your speaker name

Every step is optional — press `n` to skip anything.

## What Gets Installed

### System Packages
| Package | Purpose |
|---------|---------|
| `bluez` | Bluetooth stack |
| `pipewire` / `pipewire-pulse` | Audio routing to BT speaker |
| `portaudio` | Microphone capture |
| `python3-dbus` | Bluetooth D-Bus interface |
| `ffmpeg` | Audio format conversion |

### Python Dependencies (~200 MB + models)
| Package | Purpose |
|---------|---------|
| `torch` (CPU) | Silero VAD inference |
| `faster-whisper` | Speech-to-text (offline) |
| `openwakeword` | Wake word detection (ONNX) |
| `piper-tts` | Text-to-speech (offline) |
| `ollama` | Local LLM client |
| `openai` / `anthropic` / `google-generativeai` | Cloud LLM providers (optional) |

### AI Models (~500 MB)
| Model | Size | Purpose |
|-------|------|---------|
| Piper `en_US-lessac-medium` | ~100 MB | TTS voice |
| openWakeWord `hey_jarvis` | ~5 MB | Wake word |
| faster-whisper `base` | ~150 MB | STT (selectable: tiny/base/small/medium) |
| Ollama `llama3.2` | ~2 GB | Local LLM (selectable) |

## Post-Install

```bash
# Activate the virtual environment (pick your shell):
source .venv/bin/activate        # bash / zsh
source .venv/bin/activate.fish   # fish
source .venv/bin/activate.csh    # csh / tcsh

# Or skip activation entirely — run via the venv python directly:
.venv/bin/python -m xbmind.main
```

## Running as a Service

```bash
systemctl --user enable xbmind   # Auto-start on login
systemctl --user start xbmind    # Start now
journalctl --user -u xbmind -f   # View logs
```

## Raspberry Pi Notes

- Use a **Pi 4 or 5** (Pi 3 is too slow for STT)
- Use the `tiny` Whisper model (select during install)
- The installer auto-detects ARM architecture  

## Reinstalling / Updating

```bash
cd xbmind
git pull
./scripts/install.sh   # Re-run — it skips existing components
```

## Troubleshooting Install

### Python 3.14+ tflite-runtime error
The installer handles this automatically by installing `openwakeword` with `--no-deps`.

### Bluetooth not found
Make sure your Bluetooth adapter is connected. Check with `bluetoothctl show`.

### Ollama pull fails
Start the Ollama server first: `ollama serve`, then pull: `ollama pull llama3.2`.
