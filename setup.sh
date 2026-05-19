#!/bin/bash
set -e

echo ""
echo "========================================"
echo "  Mario AI Party Bot - Setup Wizard"
echo "========================================"
echo ""

# Step 1: Check Python 3.10+
if ! python3 -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" 2>/dev/null; then
    echo "[ERROR] Python 3.10+ required. Install from https://python.org"
    exit 1
fi
echo "[OK] Python 3.10+ found"

# Step 2: Check Ollama installed
if ! command -v ollama &>/dev/null; then
    echo "[ERROR] Ollama not found. Install from https://ollama.ai"
    exit 1
fi
echo "[OK] Ollama found"

# Step 3: Check Ollama service running
if ! ollama list &>/dev/null; then
    echo "[WARNING] Ollama service not running."
    echo "         Open another terminal and run: ollama serve"
    read -p "Press Enter when Ollama is running..."
fi
echo "[OK] Ollama service running"

# Step 4: Create Python venv
if [ ! -f "venv/bin/python" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv venv
fi
source venv/bin/activate
echo "[OK] Virtual environment active"

# Step 5: Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip --quiet 2>/dev/null

# Step 6: Install PyTorch with CUDA (or CPU fallback)
echo ""
echo "Detecting GPU for PyTorch installation..."
if command -v nvidia-smi &>/dev/null && nvidia-smi &>/dev/null; then
    echo "[OK] NVIDIA GPU detected - installing PyTorch with CUDA support"
    echo "    This downloads ~2.5 GB, please be patient..."
    pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121 --quiet 2>/dev/null || \
        pip install torch torchaudio --quiet 2>/dev/null || \
        echo "[WARNING] PyTorch CUDA install failed, will try CPU version"
else
    echo "[INFO] No NVIDIA GPU detected - installing CPU-only PyTorch"
    echo "       Mario will work but voice will be slower."
    pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu --quiet 2>/dev/null || \
        pip install torch torchaudio --quiet 2>/dev/null
fi
echo "[OK] PyTorch installed"

# Step 7: Install server dependencies
echo ""
echo "Installing server dependencies..."
pip install -r server/requirements.txt --quiet || pip install -r server/requirements.txt
echo "[OK] Server dependencies installed"

# Step 8: Install client dependencies
echo "Installing client dependencies..."
pip install -r client/requirements.txt --quiet 2>/dev/null || \
    echo "[WARNING] Some client dependencies failed. This is OK if you use browser chat."
echo "[OK] Client dependencies installed"

# Step 9: Detect hardware tier
echo ""
TIER=$(python3 -c "
import sys; sys.path.insert(0, '.')
from server.hardware import detect_hardware
hw = detect_hardware()
v, r, c = hw['gpu_vram_gb'], hw['ram_gb'], hw['cpu_cores']
if v >= 20 and r >= 128 and c >= 32: print('ultra')
elif v >= 10 and r >= 32 and c >= 8: print('high')
elif v >= 6 and r >= 16: print('medium')
else: print('low')
" 2>/dev/null || echo "low")
echo "[OK] Hardware tier: $TIER"

# Step 10: Download models
if [ ! -f "mario_models_new/GPT_SoVITS_Mario/Mario-e20.ckpt" ] && [ ! -f "server/data/rvc_model/SuperMario-TITAN_e500_s13000.pth" ]; then
    echo "Downloading voice models from GitHub Release (~930 MB)..."
    if curl -L -o models-v2.1.zip https://github.com/VillaKeth/Mario-Bathroom-AI/releases/download/v2.1/models-v2.1.zip; then
        echo "Extracting models..."
        if command -v unzip &>/dev/null; then
            unzip -o models-v2.1.zip
        else
            python3 -m zipfile -e models-v2.1.zip .
        fi
        rm models-v2.1.zip
        echo "[OK] Models extracted"
    else
        echo "[WARNING] Model download failed. Mario will use Edge TTS fallback voice."
    fi
else
    echo "[OK] Voice models already present"
fi

# Step 11: GPT-SoVITS setup
if [ ! -f "gpt_sovits_env/bin/python" ]; then
    echo ""
    echo "Setting up GPT-SoVITS voice cloning (this takes 5-15 minutes)..."
    if [ ! -d "gpt_sovits_repo" ]; then
        if ! git clone https://github.com/RVC-Boss/GPT-SoVITS.git gpt_sovits_repo; then
            echo "[WARNING] Failed to clone GPT-SoVITS. Mario will use Edge TTS fallback voice."
        fi
    fi
    if [ -d "gpt_sovits_repo" ]; then
        cd gpt_sovits_repo
        bash install.sh || echo "[WARNING] GPT-SoVITS install failed. Will use Edge TTS fallback."
        cd ..
    fi
    echo "[OK] GPT-SoVITS setup attempted"
else
    echo "[OK] GPT-SoVITS already set up"
fi

# Step 12: Pull Ollama models
echo ""
echo "Pulling Ollama models for $TIER tier..."
pull_model() {
    local search="$1" model="$2" desc="$3"
    if ! ollama list 2>/dev/null | grep -q "$search"; then
        echo "Pulling $model ($desc)..."
        ollama pull "$model"
    fi
}
pull_model "llama3" "llama3" "~4.7 GB"
echo "[OK] llama3 ready"

if [ "$TIER" = "ultra" ]; then
    pull_model "llama3.1:70b" "llama3.1:70b-q4_k_m" "~40 GB"
    echo "[OK] llama3.1:70b ready"
    pull_model "mixtral:8x7b" "mixtral:8x7b" "~26 GB"
    echo "[OK] mixtral:8x7b ready"
fi

# Step 13: Fish Speech (ULTRA only)
if [ "$TIER" = "ultra" ]; then
    echo "Installing Fish Speech TTS..."
    pip install "fish-speech>=2.2.0" --quiet 2>/dev/null || echo "[WARNING] Fish Speech install failed. Optional."
fi

# Step 14: Generate config.json
if [ ! -f "config.json" ]; then
    cp config.example.json config.json
    echo "[OK] config.json created"
    echo ""
    echo "  ** IMPORTANT: Edit config.json to customize: **"
    echo "     - birthday_person_name"
    echo "     - birthday_person_facts"
    echo ""
else
    echo "[OK] config.json already exists"
fi

# Step 15: Run verification
echo ""
echo "Running setup verification..."
echo ""
python3 scripts/verify_setup.py

echo ""
echo "========================================"
echo "  Setup Complete!"
echo ""
echo "  TO START MARIO:"
echo "    1. Run: ./start_server.sh"
echo "    2. Open: http://localhost:8765/chat"
echo ""
echo "  That's it! No other setup needed."
echo "========================================"