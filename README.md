# Mario AI — Bathroom Party Bot 🍄

An AI-powered Mario character that lives in your bathroom at a party. He listens, talks back, remembers who you are, and reacts when you enter or leave.

## Architecture

```
MacBook (Client)  ←──WebSocket──→  Friend's PC (Server + GPU)
  • Mic capture                      • Speech-to-text (Whisper)
  • Speaker output                   • Speaker ID (resemblyzer)
  • Webcam (presence)                • LLM brain (Ollama + llama3)
  • Mario sprite (Pygame)            • Text-to-speech (Piper)
                                     • Memory (SQLite)
```

## Quick Start

### Server Setup (Friend's PC with GPU)

1. **Install Ollama** (for the LLM):
   ```bash
   # Linux/Mac
   curl -fsSL https://ollama.ai/install.sh | sh
   
   # Windows: download from https://ollama.ai
   
   # Pull the model
   ollama pull llama3
   ```

2. **Install Piper TTS**:
   ```bash
   pip install piper-tts
   # Or download from https://github.com/rhasspy/piper/releases
   ```

3. **Install server dependencies**:
   ```bash
   cd server
   pip install -r requirements.txt
   ```

4. **Start the server**:
   ```bash
   cd server
   python main.py
   ```
   Server runs on `0.0.0.0:8765`

### Client Setup (MacBook at party)

1. **Install client dependencies**:
   ```bash
   cd client
   pip install -r requirements.txt
   ```

2. **Start the client** (replace IP with server's IP):
   ```bash
   cd client
   python main.py --server ws://YOUR_FRIENDS_IP:8765/ws
   ```

3. **Without webcam** (if no camera available):
   ```bash
   python main.py --server ws://YOUR_FRIENDS_IP:8765/ws --no-camera
   ```

## Features

- 🎤 **Voice conversations** — Talk to Mario and he responds in character
- 🧠 **Memory** — Remembers who you are by your voice
- 🚪 **Presence detection** — Knows when you enter/leave via webcam
- 🎮 **Animated Mario** — Pygame sprite with talking/idle animations
- 🌐 **Client-server** — Heavy AI on powerful PC, lightweight client at party

## Troubleshooting

- **"Ollama not found"**: Make sure Ollama is running (`ollama serve`)
- **No audio**: Check mic permissions and `python -c "import sounddevice; print(sounddevice.query_devices())"`
- **Laggy responses**: Use a smaller Whisper model (`tiny` instead of `base`)
- **Can't connect**: Check firewall allows port 8765, verify IP address
