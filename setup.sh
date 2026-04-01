#!/bin/bash
set -e

echo ""
echo "========================================"
echo "  Mario AI Party Bot — Setup Wizard"
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

# Step 5: Install dependencies
echo "Installing server dependencies..."
pip install -r server/requirements.txt --quiet
echo "Installing client dependencies..."
pip install -r client/requirements.txt --quiet
echo "[OK] Dependencies installed"

# Step 6: Detect hardware tier
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

# Step 7: Download models
if [ ! -f "mario_models_new/GPT_SoVITS_Mario/Mario-e20.ckpt" ] && [ ! -f "server/data/rvc_model/SuperMario-TITAN_e500_s13000.pth" ]; then
    echo "Downloading voice models from GitHub Release (~930 MB)..."
    curl -L -o models-v2.1.zip https://github.com/VillaKeth/Mario-Bathroom-AI/releases/download/v2.1/models-v2.1.zip
    echo "Extracting models..."
    if command -v unzip &>/dev/null; then
        unzip -o models-v2.1.zip
    else
        python3 -m zipfile -e models-v2.1.zip .
    fi
    rm models-v2.1.zip
    echo "[OK] Models extracted"
else
    echo "[OK] Voice models already present"
fi

# Step 8: GPT-SoVITS setup
if [ ! -f "gpt_sovits_env/bin/python" ]; then
    echo "Setting up GPT-SoVITS voice cloning (this takes 5-15 minutes)..."
    if [ ! -d "gpt_sovits_repo" ]; then
        git clone https://github.com/RVC-Boss/GPT-SoVITS.git gpt_sovits_repo
    fi
    cd gpt_sovits_repo
    bash install.sh
    cd ..
    echo "[OK] GPT-SoVITS installed"
else
    echo "[OK] GPT-SoVITS already set up"
fi

# Step 9: Pull Ollama models
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

# Step 10: Fish Speech (ULTRA only)
if [ "$TIER" = "ultra" ]; then
    echo "Installing Fish Speech TTS..."
    pip install "fish-speech>=2.2.0" --quiet 2>/dev/null || echo "[WARNING] Fish Speech install failed. Optional."
fi

# Step 11: Generate config.json
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

# Step 12: Run verification
echo ""
echo "Running setup verification..."
echo ""
python3 scripts/verify_setup.py

echo ""
echo "========================================"
echo "  Setup Complete!"
echo "  Run: ./start_server.sh"
echo "  Then open: http://localhost:8765/chat"
echo "========================================"
