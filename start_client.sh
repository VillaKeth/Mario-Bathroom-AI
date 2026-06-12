#!/usr/bin/env bash
# Start ONLY the on-screen character window (the "client").
# Use this if the server is already running. Most people use ./start.sh (both).
cd "$(dirname "$0")"
if [ ! -d venv ]; then echo "[ERROR] Run ./setup.sh first."; exit 1; fi
source venv/bin/activate
echo "Opening the character window..."
python client/main.py
