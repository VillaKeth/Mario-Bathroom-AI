#!/bin/bash
echo "==================================="
echo "  Mario AI Server - Starting Up!"
echo "==================================="
echo

cd "$(dirname "$0")/server"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python3 not found! Install Python 3.10+"
    exit 1
fi

# Install deps
echo "Installing server dependencies..."
pip3 install -r requirements.txt --quiet

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
echo "==================================="
echo
python3 main.py
