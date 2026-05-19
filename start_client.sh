#!/bin/bash
echo "==================================="
echo "  Mario AI Client - Let's-a Go!"
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
echo "Checking client dependencies..."
pip3 install -r "$SCRIPT_DIR/client/requirements.txt" --quiet 2>/dev/null

# Get server IP
SERVER_IP="${1:-localhost}"
if [ "$SERVER_IP" = "localhost" ] && [ -z "$1" ]; then
    read -p "Enter server IP address (or 'localhost' for testing): " SERVER_IP
fi

echo
echo "==================================="
echo "  Connecting to ws://${SERVER_IP}:8765/ws"
echo "  Press ESC or close window to quit"
echo "==================================="
echo
cd "$SCRIPT_DIR/client"
python3 main.py --server "ws://${SERVER_IP}:8765/ws"
