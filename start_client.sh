#!/bin/bash
echo "==================================="
echo "  Mario AI Client - Let's-a Go!"
echo "==================================="
echo

cd "$(dirname "$0")/client"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python3 not found! Install Python 3.10+"
    exit 1
fi

# Install deps
echo "Installing client dependencies..."
pip3 install -r requirements.txt --quiet

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
python3 main.py --server "ws://${SERVER_IP}:8765/ws"
