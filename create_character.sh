#!/bin/bash
echo "Starting Character Creator Wizard..."
if [ ! -f "venv/bin/python" ]; then
    echo "[ERROR] Run setup.sh first to install dependencies."
    exit 1
fi
source venv/bin/activate
echo "Opening Character Creator in your browser..."
python -c "import webbrowser; webbrowser.open('http://localhost:8766')" &
python -m character_creator.server
