#!/usr/bin/env bash
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# XBMind — Master Installer
# Supports: Ubuntu/Debian, Fedora/RHEL, Arch/Manjaro, openSUSE, Void
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_DIR="$PROJECT_DIR/.venv"
MODELS_DIR="$PROJECT_DIR/models"

# ── Colours ──────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# ── Helpers ──────────────────────────────────────────────────────────
info()  { echo -e "${CYAN}→${NC} $*"; }
ok()    { echo -e "  ${GREEN}✓${NC} $*"; }
warn()  { echo -e "  ${YELLOW}⚠${NC} $*"; }
fail()  { echo -e "  ${RED}✗${NC} $*"; }
header(){ echo -e "\n${BOLD}━━━ $* ━━━${NC}"; }

ask() {
    # Usage: ask "Question" default(y/n)
    local question="$1"
    local default="${2:-y}"
    local prompt

    if [ "$default" = "y" ]; then
        prompt="[Y/n]"
    else
        prompt="[y/N]"
    fi

    echo -en "${CYAN}?${NC} ${question} ${prompt} "
    read -r answer </dev/tty
    answer="${answer:-$default}"
    [[ "$answer" =~ ^[Yy] ]]
}

# ── Banner ───────────────────────────────────────────────────────────
clear 2>/dev/null || true
echo -e "${BOLD}"
echo "╔══════════════════════════════════════════════════╗"
echo "║                                                  ║"
echo "║       ██╗  ██╗██████╗ ███╗   ███╗██╗███╗   ██╗  ║"
echo "║       ╚██╗██╔╝██╔══██╗████╗ ████║██║████╗  ██║  ║"
echo "║        ╚███╔╝ ██████╔╝██╔████╔██║██║██╔██╗ ██║  ║"
echo "║        ██╔██╗ ██╔══██╗██║╚██╔╝██║██║██║╚██╗██║  ║"
echo "║       ██╔╝ ██╗██████╔╝██║ ╚═╝ ██║██║██║ ╚████║  ║"
echo "║       ╚═╝  ╚═╝╚═════╝ ╚═╝     ╚═╝╚═╝╚═╝  ╚═══╝  ║"
echo "║                                                  ║"
echo "║       AI Smart Speaker — Master Installer        ║"
echo "║                    v0.1.0                        ║"
echo "╚══════════════════════════════════════════════════╝"
echo -e "${NC}"

# ══════════════════════════════════════════════════════════════════════
# PHASE 1: Detect the system
# ══════════════════════════════════════════════════════════════════════
header "Phase 1 — System Detection"

# ── Detect distro ────────────────────────────────────────────────────
DISTRO="unknown"
PKG_MANAGER="unknown"

if [ -f /etc/os-release ]; then
    . /etc/os-release
    DISTRO_NAME="${NAME:-unknown}"
    DISTRO_ID="${ID:-unknown}"
else
    DISTRO_NAME="$(uname -s)"
    DISTRO_ID="$(uname -s | tr '[:upper:]' '[:lower:]')"
fi

if command -v pacman &> /dev/null; then
    PKG_MANAGER="pacman"
    DISTRO="arch"
elif command -v apt-get &> /dev/null; then
    PKG_MANAGER="apt"
    DISTRO="debian"
elif command -v dnf &> /dev/null; then
    PKG_MANAGER="dnf"
    DISTRO="fedora"
elif command -v zypper &> /dev/null; then
    PKG_MANAGER="zypper"
    DISTRO="suse"
elif command -v xbps-install &> /dev/null; then
    PKG_MANAGER="xbps"
    DISTRO="void"
elif command -v apk &> /dev/null; then
    PKG_MANAGER="apk"
    DISTRO="alpine"
fi

ok "Distribution: ${DISTRO_NAME} (${DISTRO_ID})"
ok "Package manager: ${PKG_MANAGER}"
ok "Architecture: $(uname -m)"
ok "Kernel: $(uname -r)"

# ── Detect Python ────────────────────────────────────────────────────
if ! command -v python3 &> /dev/null; then
    fail "Python 3 not found. Please install Python 3.11+"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PYTHON_MINOR=$(python3 -c 'import sys; print(sys.version_info.minor)')

if ! python3 -c 'import sys; assert sys.version_info >= (3, 11)' 2>/dev/null; then
    fail "Python 3.11+ required (found ${PYTHON_VERSION})"
    exit 1
fi
ok "Python: ${PYTHON_VERSION}"

# ── Detect GPU ───────────────────────────────────────────────────────
HAS_NVIDIA=false
if command -v nvidia-smi &> /dev/null; then
    HAS_NVIDIA=true
    GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1 || echo "unknown")
    ok "NVIDIA GPU: ${GPU_NAME}"
else
    ok "GPU: None detected (will use CPU)"
fi

echo ""
echo -e "${BOLD}XBMind will install the following:${NC}"
echo "  • System packages (bluez, pipewire, portaudio, ffmpeg)"
echo "  • Python virtual environment + dependencies"
echo "  • PyTorch (CPU-only, ~200 MB)"
echo "  • AI models (Piper TTS, openWakeWord, faster-whisper)"
echo "  • Ollama LLM runtime"
echo "  • Bluetooth auto-pair configuration"
echo "  • Systemd user service"
echo ""

if ! ask "Proceed with installation?" "y"; then
    echo "Aborted."
    exit 0
fi

# ══════════════════════════════════════════════════════════════════════
# PHASE 2: System Dependencies
# ══════════════════════════════════════════════════════════════════════
header "Phase 2 — System Dependencies"

install_system_deps() {
    case "$PKG_MANAGER" in
        pacman)
            info "Installing via pacman..."
            sudo pacman -S --needed --noconfirm \
                bluez bluez-utils \
                pipewire pipewire-pulse \
                portaudio \
                python-dbus \
                ffmpeg \
                wget curl
            ;;
        apt)
            info "Installing via apt..."
            sudo apt-get update -qq
            sudo apt-get install -y -qq \
                bluez \
                pulseaudio-utils \
                pipewire \
                libportaudio2 portaudio19-dev \
                python3-dev python3-venv python3-dbus \
                libdbus-1-dev libglib2.0-dev \
                ffmpeg \
                wget curl
            ;;
        dnf)
            info "Installing via dnf..."
            sudo dnf install -y \
                bluez \
                pulseaudio-utils \
                pipewire \
                portaudio-devel \
                python3-devel python3-dbus \
                dbus-devel glib2-devel \
                ffmpeg \
                wget curl
            ;;
        zypper)
            info "Installing via zypper..."
            sudo zypper install -y \
                bluez \
                pulseaudio-utils \
                pipewire \
                portaudio-devel \
                python3-devel python3-dbus \
                dbus-1-devel glib2-devel \
                ffmpeg \
                wget curl
            ;;
        xbps)
            info "Installing via xbps..."
            sudo xbps-install -Sy \
                bluez \
                pulseaudio-utils \
                pipewire \
                portaudio-devel \
                python3-devel python3-dbus \
                dbus-devel glib2-devel \
                ffmpeg \
                wget curl
            ;;
        apk)
            info "Installing via apk..."
            sudo apk add \
                bluez \
                pulseaudio-utils \
                pipewire \
                portaudio-dev \
                python3-dev py3-dbus \
                dbus-dev glib-dev \
                ffmpeg \
                wget curl
            ;;
        *)
            warn "Unsupported package manager: ${PKG_MANAGER}"
            warn "Please install manually: bluez, pipewire, portaudio, python3-dbus, ffmpeg, wget, curl"
            if ! ask "Continue anyway (assuming deps are installed)?" "n"; then
                exit 1
            fi
            ;;
    esac
}

if ask "Install system dependencies?" "y"; then
    install_system_deps
    ok "System dependencies installed"
else
    warn "Skipped system dependencies"
fi

# ══════════════════════════════════════════════════════════════════════
# PHASE 3: Python Virtual Environment + Dependencies
# ══════════════════════════════════════════════════════════════════════
header "Phase 3 — Python Environment"

# ── Create venv ──────────────────────────────────────────────────────
if [ -d "$VENV_DIR" ]; then
    if ask "Virtual environment already exists. Recreate it?" "n"; then
        info "Removing old virtual environment..."
        rm -rf "$VENV_DIR"
        python3 -m venv "$VENV_DIR" --system-site-packages
        ok "Created fresh virtual environment"
    else
        ok "Using existing virtual environment"
    fi
else
    info "Creating virtual environment..."
    python3 -m venv "$VENV_DIR" --system-site-packages
    ok "Created virtual environment at .venv/"
fi

# Activate — install.sh always runs under bash, so bash activate is fine here
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

# ── Upgrade pip ──────────────────────────────────────────────────────
info "Upgrading pip..."
pip install --upgrade pip setuptools wheel -q
ok "pip upgraded"

# ── Install PyTorch ──────────────────────────────────────────────────
info "Installing PyTorch..."

if [ "$HAS_NVIDIA" = true ]; then
    echo ""
    echo "  NVIDIA GPU detected. Choose PyTorch build:"
    echo "    1) CPU-only  (~200 MB, recommended for smart speaker)"
    echo "    2) CUDA 12.1 (~2 GB,  GPU-accelerated STT)"
    echo ""
    echo -en "${CYAN}?${NC} Choose [1/2]: "
    read -r torch_choice </dev/tty
    torch_choice="${torch_choice:-1}"

    if [ "$torch_choice" = "2" ]; then
        info "Installing PyTorch with CUDA 12.1..."
        pip install torch --index-url https://download.pytorch.org/whl/cu121 -q
        ok "PyTorch installed (CUDA 12.1)"
    else
        pip install torch --index-url https://download.pytorch.org/whl/cpu -q
        ok "PyTorch installed (CPU-only)"
    fi
else
    pip install torch --index-url https://download.pytorch.org/whl/cpu -q
    ok "PyTorch installed (CPU-only)"
fi

# ── Install requirements ─────────────────────────────────────────────
info "Installing Python dependencies (this may take a few minutes)..."
pip install -r "$PROJECT_DIR/requirements.txt" -q
ok "Core dependencies installed"

# ── Install openwakeword (special handling) ──────────────────────────
info "Installing openwakeword (ONNX-only)..."
# openwakeword requires tflite-runtime which has no Python 3.13+ wheels.
# We install with --no-deps and provide its real dependencies manually.
pip install openwakeword --no-deps -q
pip install scipy scikit-learn tqdm requests -q
ok "openwakeword installed (ONNX backend)"

# ── Editable install ─────────────────────────────────────────────────
info "Installing XBMind in development mode..."
pip install -e "$PROJECT_DIR" -q
ok "XBMind package installed"

# ── Create data directories ─────────────────────────────────────────
mkdir -p "$PROJECT_DIR/data"
mkdir -p "$MODELS_DIR/piper"
mkdir -p "$MODELS_DIR/whisper"
ok "Data directories created"

# ══════════════════════════════════════════════════════════════════════
# PHASE 4: AI Models
# ══════════════════════════════════════════════════════════════════════
header "Phase 4 — AI Models"

if ask "Download AI models? (Piper TTS, openWakeWord, faster-whisper — ~500 MB total)" "y"; then

    # ── Piper TTS voice ──────────────────────────────────────────────
    PIPER_DIR="$MODELS_DIR/piper"
    PIPER_MODEL="en_US-lessac-medium.onnx"
    PIPER_CONFIG="en_US-lessac-medium.onnx.json"
    PIPER_BASE_URL="https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium"

    if [ ! -f "$PIPER_DIR/$PIPER_MODEL" ]; then
        info "Downloading Piper TTS voice model (~100 MB)..."
        wget -q --show-progress -O "$PIPER_DIR/$PIPER_MODEL" \
            "$PIPER_BASE_URL/$PIPER_MODEL"
        ok "Downloaded ${PIPER_MODEL}"
    else
        ok "Piper model already exists"
    fi

    if [ ! -f "$PIPER_DIR/$PIPER_CONFIG" ]; then
        wget -q --show-progress -O "$PIPER_DIR/$PIPER_CONFIG" \
            "$PIPER_BASE_URL/$PIPER_CONFIG"
        ok "Downloaded Piper config"
    else
        ok "Piper config already exists"
    fi

    # ── Piper binary ─────────────────────────────────────────────────
    if ! command -v piper &> /dev/null && [ ! -f "$MODELS_DIR/piper/piper" ]; then
        info "Downloading Piper TTS binary..."
        PIPER_RELEASE="2023.11.14-2"
        ARCH=$(uname -m)

        case "$ARCH" in
            x86_64)  PIPER_ARCH="amd64" ;;
            aarch64) PIPER_ARCH="arm64" ;;
            armv7l)  PIPER_ARCH="armv7" ;;
            *)       PIPER_ARCH="" ;;
        esac

        if [ -n "$PIPER_ARCH" ]; then
            PIPER_URL="https://github.com/rhasspy/piper/releases/download/${PIPER_RELEASE}/piper_linux_${PIPER_ARCH}.tar.gz"
            wget -q --show-progress -O /tmp/piper.tar.gz "$PIPER_URL"
            tar -xzf /tmp/piper.tar.gz -C "$MODELS_DIR"
            rm -f /tmp/piper.tar.gz
            ok "Piper binary installed at ${MODELS_DIR}/piper/"
        else
            warn "Unsupported architecture (${ARCH}) — install Piper manually"
        fi
    else
        ok "Piper binary already installed"
    fi

    # ── openWakeWord models ──────────────────────────────────────────
    info "Downloading openWakeWord models..."
    "$VENV_DIR/bin/python" -c "
try:
    import openwakeword
    openwakeword.utils.download_models()
    print('  \033[0;32m✓\033[0m openWakeWord models downloaded')
except Exception as e:
    print(f'  \033[1;33m⚠\033[0m Could not download wake word models: {e}')
"

    # ── faster-whisper model ─────────────────────────────────────────
    info "Pre-caching faster-whisper model (~150 MB)..."

    echo ""
    echo "  Choose Whisper model size:"
    echo "    1) tiny   — Fastest,  lowest accuracy  (~75 MB)"
    echo "    2) base   — Good balance               (~150 MB)  [default]"
    echo "    3) small  — Better accuracy, slower     (~500 MB)"
    echo "    4) medium — High accuracy, slow         (~1.5 GB)"
    echo ""
    echo -en "${CYAN}?${NC} Choose [1-4]: "
    read -r whisper_choice </dev/tty
    whisper_choice="${whisper_choice:-2}"

    case "$whisper_choice" in
        1) WHISPER_MODEL="tiny"   ;;
        3) WHISPER_MODEL="small"  ;;
        4) WHISPER_MODEL="medium" ;;
        *) WHISPER_MODEL="base"   ;;
    esac

    "$VENV_DIR/bin/python" -c "
try:
    from faster_whisper import WhisperModel
    print(f'  Downloading \"${WHISPER_MODEL}\" model...')
    model = WhisperModel('${WHISPER_MODEL}', device='cpu', compute_type='int8')
    del model
    print('  \033[0;32m✓\033[0m faster-whisper ${WHISPER_MODEL} model cached')
except Exception as e:
    print(f'  \033[1;33m⚠\033[0m Could not download model: {e}')
"
    ok "AI model downloads complete"

else
    warn "Skipped AI model downloads"
    echo "  Run later: ./scripts/download_models.sh"
fi

# ══════════════════════════════════════════════════════════════════════
# PHASE 5: Ollama (LLM Runtime)
# ══════════════════════════════════════════════════════════════════════
header "Phase 5 — Ollama LLM Runtime"

if command -v ollama &> /dev/null; then
    ok "Ollama is already installed"
    OLLAMA_INSTALLED=true
else
    OLLAMA_INSTALLED=false
    echo ""
    echo "  Ollama is the local LLM runtime that powers XBMind's AI brain."
    echo "  It runs models like Llama 3.2 entirely on your machine."
    echo ""

    if ask "Install Ollama?" "y"; then
        info "Installing Ollama..."
        curl -fsSL https://ollama.ai/install.sh | sh
        OLLAMA_INSTALLED=true
        ok "Ollama installed"
    else
        warn "Skipped Ollama installation"
        echo "  Install later: curl -fsSL https://ollama.ai/install.sh | sh"
    fi
fi

if [ "$OLLAMA_INSTALLED" = true ]; then
    echo ""
    echo "  Choose a default LLM model:"
    echo "    1) llama3.2   — 3B params, fast, good for most tasks  [default]"
    echo "    2) llama3.1   — 8B params, smarter, needs more RAM"
    echo "    3) mistral    — 7B params, good performance"
    echo "    4) phi3       — 3.8B params, Microsoft, compact"
    echo "    5) Skip       — Don't pull any model now"
    echo ""
    echo -en "${CYAN}?${NC} Choose [1-5]: "
    read -r model_choice </dev/tty
    model_choice="${model_choice:-1}"

    case "$model_choice" in
        2) OLLAMA_MODEL="llama3.1"  ;;
        3) OLLAMA_MODEL="mistral"   ;;
        4) OLLAMA_MODEL="phi3"      ;;
        5) OLLAMA_MODEL=""          ;;
        *) OLLAMA_MODEL="llama3.2"  ;;
    esac

    if [ -n "$OLLAMA_MODEL" ]; then
        info "Pulling ${OLLAMA_MODEL} (this may take several minutes)..."
        if ollama pull "$OLLAMA_MODEL" 2>/dev/null; then
            ok "${OLLAMA_MODEL} model ready"
        else
            warn "Could not pull model. Make sure 'ollama serve' is running."
            echo "  Run later: ollama pull ${OLLAMA_MODEL}"
        fi
    fi
fi

# ══════════════════════════════════════════════════════════════════════
# PHASE 6: Bluetooth Setup
# ══════════════════════════════════════════════════════════════════════
header "Phase 6 — Bluetooth Configuration"

echo ""
echo "  This step configures Bluetooth for auto-pairing with your speaker."
echo "  It requires sudo to modify system Bluetooth settings."
echo ""

if ask "Configure Bluetooth for XBMind?" "y"; then

    # ── Start Bluetooth service ──────────────────────────────────────
    info "Enabling Bluetooth service..."
    sudo systemctl enable bluetooth 2>/dev/null || true
    sudo systemctl start bluetooth 2>/dev/null || true
    ok "Bluetooth service enabled"

    # ── Configure BlueZ ──────────────────────────────────────────────
    BLUEZ_CONF="/etc/bluetooth/main.conf"

    if [ -f "$BLUEZ_CONF" ]; then
        info "Configuring BlueZ for auto-connect..."

        # Enable auto power on
        if ! grep -q "^AutoEnable=true" "$BLUEZ_CONF" 2>/dev/null; then
            sudo sed -i 's/^#\?AutoEnable=.*/AutoEnable=true/' "$BLUEZ_CONF"
            if ! grep -q "^AutoEnable=true" "$BLUEZ_CONF" 2>/dev/null; then
                echo "AutoEnable=true" | sudo tee -a "$BLUEZ_CONF" > /dev/null
            fi
        fi

        # Set discoverable timeout
        if ! grep -q "^DiscoverableTimeout = 0" "$BLUEZ_CONF" 2>/dev/null; then
            sudo sed -i 's/^#\?DiscoverableTimeout = .*/DiscoverableTimeout = 0/' "$BLUEZ_CONF"
        fi

        ok "BlueZ configured (auto-enable, discoverable)"
    fi

    # ── Add user to bluetooth group ──────────────────────────────────
    CURRENT_USER="${SUDO_USER:-$USER}"
    info "Adding ${CURRENT_USER} to bluetooth group..."
    sudo usermod -aG bluetooth "$CURRENT_USER" 2>/dev/null || true
    ok "User added to bluetooth group"

    # ── Configure PipeWire Bluetooth ─────────────────────────────────
    if command -v pipewire &> /dev/null; then
        info "Configuring PipeWire Bluetooth module..."
        PIPEWIRE_BT_CONF="/etc/pipewire/media-session.d/bluez-monitor.conf"
        if [ ! -f "$PIPEWIRE_BT_CONF" ]; then
            sudo mkdir -p "$(dirname "$PIPEWIRE_BT_CONF")"
            sudo tee "$PIPEWIRE_BT_CONF" > /dev/null << 'PIPEWIRE_EOF'
# Bluetooth monitor configuration for XBMind
properties = {
    bluez5.enable-sbc-xq = true
    bluez5.enable-msbc = true
    bluez5.enable-hw-volume = true
}
rules = [
    {
        matches = [ { device.name = "~bluez_card.*" } ]
        actions = {
            update-props = {
                bluez5.auto-connect = [ hfp_hf hsp_hs a2dp_sink ]
            }
        }
    }
]
PIPEWIRE_EOF
            ok "PipeWire Bluetooth config created"
        else
            ok "PipeWire Bluetooth config already exists"
        fi
    fi

    # ── Restart Bluetooth ────────────────────────────────────────────
    info "Restarting Bluetooth service..."
    sudo systemctl restart bluetooth 2>/dev/null || true
    ok "Bluetooth configured — put your speaker in pairing mode when ready"

else
    warn "Skipped Bluetooth setup"
    echo "  Configure later by re-running this installer"
fi

# ══════════════════════════════════════════════════════════════════════
# PHASE 7: Systemd Service
# ══════════════════════════════════════════════════════════════════════
header "Phase 7 — Systemd Service"

if ask "Install systemd user service? (auto-start XBMind on login)" "y"; then
    info "Installing systemd user service..."
    mkdir -p "$HOME/.config/systemd/user"

    sed "s|/path/to/xbmind|$PROJECT_DIR|g; s|/path/to/venv|$VENV_DIR|g" \
        "$PROJECT_DIR/systemd/xbmind.service" > "$HOME/.config/systemd/user/xbmind.service"

    systemctl --user daemon-reload 2>/dev/null || true
    ok "Systemd service installed"
    echo "  Enable:  systemctl --user enable xbmind"
    echo "  Start:   systemctl --user start xbmind"
    echo "  Logs:    journalctl --user -u xbmind -f"
else
    warn "Skipped systemd service installation"
fi

# ══════════════════════════════════════════════════════════════════════
# PHASE 8: Configuration
# ══════════════════════════════════════════════════════════════════════
header "Phase 8 — Configuration"

if [ ! -f "$PROJECT_DIR/config/local.yaml" ]; then
    if ask "Create a local config file from the template?" "y"; then
        cp "$PROJECT_DIR/config/config.yaml" "$PROJECT_DIR/config/local.yaml"
        ok "Created config/local.yaml"
        echo "  Edit this file to customise XBMind for your hardware:"
        echo "    nano ${PROJECT_DIR}/config/local.yaml"
    fi
else
    ok "config/local.yaml already exists"
fi

# ── Ask about speaker name ───────────────────────────────────────────
echo ""
echo -en "${CYAN}?${NC} Enter your Bluetooth speaker name (or press Enter for 'SRS-XB100'): "
read -r speaker_name </dev/tty
speaker_name="${speaker_name:-SRS-XB100}"

if [ -f "$PROJECT_DIR/config/local.yaml" ]; then
    sed -i "s/device_name:.*/device_name: \"${speaker_name}\"/" "$PROJECT_DIR/config/local.yaml"
    ok "Configured speaker: ${speaker_name}"
fi

# ══════════════════════════════════════════════════════════════════════
# DONE
# ══════════════════════════════════════════════════════════════════════
echo ""
echo -e "${BOLD}"
echo "╔══════════════════════════════════════════════════╗"
echo "║                                                  ║"
echo "║         Installation Complete! 🎉                ║"
echo "║                                                  ║"
echo "╚══════════════════════════════════════════════════╝"
echo -e "${NC}"

# Detect user's shell for correct activation instructions
USER_SHELL="$(basename "${SHELL:-/bin/bash}")"
case "$USER_SHELL" in
    fish)
        ACTIVATE_CMD="source .venv/bin/activate.fish"
        ;;
    csh|tcsh)
        ACTIVATE_CMD="source .venv/bin/activate.csh"
        ;;
    *)
        ACTIVATE_CMD="source .venv/bin/activate"
        ;;
esac

echo -e "${BOLD}Quick Start:${NC}"
echo ""
echo "  1. Activate the environment:"
echo -e "     ${CYAN}${ACTIVATE_CMD}${NC}"
echo ""
echo "  2. Make sure Ollama is running (skip if already started):"
echo -e "     ${CYAN}ollama serve${NC}  (in another terminal)"
echo ""
echo "  3. Put your speaker in pairing mode, then:"
echo -e "     ${CYAN}python -m xbmind.main${NC}"
echo ""
echo -e "  ${YELLOW}TIP:${NC} You can also run directly without activating:"
echo -e "     ${CYAN}.venv/bin/python -m xbmind.main${NC}"
echo ""
echo -e "${BOLD}Useful commands:${NC}"
echo "  systemctl --user start xbmind    # Start as service"
echo "  journalctl --user -u xbmind -f   # View logs"
echo "  curl localhost:7070/health        # Health check"
echo ""
echo -e "  Docs: ${CYAN}${PROJECT_DIR}/docs/${NC}"
echo -e "  Config: ${CYAN}${PROJECT_DIR}/config/local.yaml${NC}"
echo ""
