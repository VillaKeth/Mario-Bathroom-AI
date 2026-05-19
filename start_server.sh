#!/bin/bash
echo "==================================="
echo "  Mario AI Server - Starting Up!"
echo "==================================="
echo

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Activate virtual environment (created by setup.sh)
if [ -f "$SCRIPT_DIR/venv/bin/activate" ]; then
    source "$SCRIPT_DIR/venv/bin/activate"
    echo "[OK] Virtual environment activated"
elif [ -f "$SCRIPT_DIR/.venv/bin/activate" ]; then
    source "$SCRIPT_DIR/.venv/bin/activate"
    echo "[OK] Virtual environment activated"
else
    echo "[WARNING] No virtual environment found."
    echo "         Run setup.sh first for best results."
    echo "         Falling back to system Python..."
    echo
fi

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python3 not found! Install Python 3.10+"
    exit 1
fi

# Install/update deps
echo "Checking server dependencies..."
pip3 install -r "$SCRIPT_DIR/server/requirements.txt" --quiet 2>/dev/null

# Check Ollama
if command -v ollama &> /dev/null; then
    if ! ollama list 2>/dev/null | grep -q "llama3"; then
        echo "Pulling llama3 model..."
        ollama pull llama3
    fi
else
    echo "WARNING: Ollama not found! Install from https://ollama.ai"
fi

echo
echo "==================================="
echo "  Starting Mario AI Server"
echo "  Listening on 0.0.0.0:8765"
echo "  Browser chat: http://localhost:8765/chat"
echo "==================================="
echo
cd "$SCRIPT_DIR/server"
python3 main.py
