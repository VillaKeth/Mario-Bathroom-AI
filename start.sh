#!/usr/bin/env bash
# One-click: start the AI server, wait for it, then open the character window.
cd "$(dirname "$0")"
if [ ! -d venv ]; then echo "[ERROR] Run ./setup.sh first."; exit 1; fi
source venv/bin/activate
echo "Starting the AI server..."
( cd server && python main.py ) &
echo "Waiting for the server to be ready..."
until curl -s -o /dev/null http://localhost:8765/health; do sleep 2; done
echo "Server ready. Opening the character window..."
python client/main.py
