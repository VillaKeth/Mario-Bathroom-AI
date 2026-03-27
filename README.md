# 🍄 Mario AI — Party Bathroom Bot

**It's-a me, MARIO!** An AI-powered Mario that guards your bathroom at parties. He talks, jokes, plays games, remembers guests by voice, and never breaks character.

> **Battle-tested**: 8+ hours continuous operation, 850+ responses, 100% health checks passing.

---

## 🚀 QUICK START (The Drunk-Proof Version)

You need **TWO computers**: a beefy PC (the brain) and a laptop in the bathroom (the face).

### Step 1: Set Up the Brain (Server PC with NVIDIA GPU)

**One-time setup** — do this sober, before the party:

```
1. Install Python 3.10+          → https://python.org/downloads
2. Install Ollama                 → https://ollama.ai
3. Install CUDA (NVIDIA drivers)  → https://developer.nvidia.com/cuda-downloads
```

Then open a terminal and run:

```bash
ollama pull llama3
```

That downloads Mario's brain (~4.7 GB). Only need to do this once.

### Step 2: Start Mario (Party Time!)

**On the server PC**, double-click:

```
📁 start_server.bat        (Windows)
📁 start_server.sh          (Mac/Linux)
```

That's it. Mario's brain is running. You'll see:

```
✅ Mario AI Server running on 0.0.0.0:8765
```

### Step 3: Set Up the Bathroom (Client Laptop)

**On the bathroom laptop**, double-click:

```
📁 start_client.bat        (Windows)
📁 start_client.sh          (Mac/Linux)
```

It will ask for the server's IP address. Type the server PC's local IP (like `192.168.1.42`) and hit Enter.

> **💡 Don't know the IP?** On the server PC, run `ipconfig` (Windows) or `ifconfig` (Mac/Linux). Look for `192.168.x.x`.

### Step 3 (Alternative): Browser Mode — No Client Needed!

Skip the Pygame client entirely. On **any device** on the same WiFi, open a browser and go to:

```
http://SERVER_IP:8765/chat
```

This gives you a full chat interface with audio, games, and health monitoring. Works on phones too! 📱

---

## 🎮 What Mario Can Do

| Feature | Description |
|---------|-------------|
| 🎤 **Voice Chat** | Talk to Mario and he responds with his real voice |
| 🧠 **Memory** | Remembers guests by voice — "Hey Tony, welcome back!" |
| 🚪 **Presence Detection** | Webcam detects when someone enters/exits the bathroom |
| 🎲 **Party Games** | Rock Paper Scissors, 20 Questions, Riddles, Truth or Dare, Simon Says |
| 😊 **13 Emotions** | Happy, excited, mischievous, surprised, worried, sleepy, and more |
| 🏆 **Leaderboard** | Tracks visits, game scores, and fun titles for each guest |
| 💬 **Idle Behavior** | Mario mumbles, hums, and comments when alone |
| 🔊 **Mario's Voice** | Custom-trained GPT-SoVITS + RVC model (Charles Martinet's voice) |

---

## 📐 Architecture

```
🖥️ Bathroom Laptop (Client)          🖥️ Server PC (GPU)
┌─────────────────────┐              ┌──────────────────────────┐
│  Microphone          │              │  Speech-to-Text (Whisper) │
│  Speaker             │◄──WebSocket─►│  AI Brain (Ollama llama3) │
│  Webcam (presence)   │   port 8765  │  Mario Voice (GPT-SoVITS) │
│  Mario Display       │              │  Memory (SQLite)          │
│  (Pygame)            │              │  Games + Emotions         │
└─────────────────────┘              └──────────────────────────┘
```

Or skip the client entirely and use the **browser chat** at `http://SERVER_IP:8765/chat`.

---

## 🛠️ Detailed Setup (For Sober People)

### Prerequisites

| Requirement | Why | Install |
|-------------|-----|---------|
| **Python 3.10+** | Runs everything | [python.org/downloads](https://python.org/downloads) |
| **Ollama** | Mario's brain (LLM) | [ollama.ai](https://ollama.ai) |
| **NVIDIA GPU + CUDA** | Fast voice synthesis | [NVIDIA CUDA](https://developer.nvidia.com/cuda-downloads) |

> **No GPU?** Mario will still work but voice generation will be slower. He'll fall back to Edge TTS (Microsoft's voices) instead of the custom Mario voice.

### Server Dependencies

```bash
cd server
pip install -r requirements.txt
```

This installs: FastAPI, Whisper, Edge-TTS, resemblyzer (speaker ID), and more.

### Client Dependencies

```bash
cd client
pip install -r requirements.txt
```

This installs: Pygame, OpenCV, sounddevice, websocket-client.

### Voice Models (Already Included!)

All voice models are pre-trained and included in the repo:

```
mario_models_new/
├── GPT_SoVITS_Mario/           ← Custom Mario voice (GPT-SoVITS)
│   ├── Mario_e15_s255.pth      ← Vocoder (15 epochs)
│   ├── Mario-e20.ckpt          ← Text model (20 epochs)
│   └── mario_ref.wav           ← Reference audio
└── MarioSwitch/                ← RVC v2 voice conversion
    ├── SuperMario-NintendoSwitchEra.pth   ← 500-epoch TITAN model
    └── ...index                            ← Voice index
```

**No extra downloads needed** (except `ollama pull llama3`).

### GPT-SoVITS Setup (Advanced — Already Done If You Cloned This Repo)

The custom Mario voice runs in its own Python environment:

```
gpt_sovits_env/      ← Pre-built virtual environment with PyTorch + dependencies
gpt_sovits_repo/     ← GPT-SoVITS inference library
```

The server automatically starts the GPT-SoVITS subprocess. If it fails, Mario falls back to Edge TTS.

---

## ⚙️ Configuration

Everything is in **`config.json`** at the project root:

```jsonc
{
  "server": {
    "port": 8765,                    // WebSocket port
    "llm_model": "llama3",          // Ollama model name
    "tts_mode": "sovits",           // "sovits" (Mario voice) or "edge" (fallback)
    "stt_model_size": "base",       // Whisper: tiny/base/small/medium/large-v3
    "text_input_cooldown_seconds": 2 // Cooldown between messages
  },
  "client": {
    "server_url": "ws://localhost:8765/ws",
    "enable_camera": true,
    "enable_microphone": true
  }
}
```

### Useful Endpoints

| URL | What It Does |
|-----|-------------|
| `http://SERVER:8765/chat` | 💬 Browser chat interface |
| `http://SERVER:8765/health` | 🩺 Server health check (JSON) |
| `http://SERVER:8765/stats` | 📊 Party statistics |
| `http://SERVER:8765/leaderboard` | 🏆 Guest leaderboard |
| `http://SERVER:8765/leaderboard_page` | 🏆 Leaderboard (pretty HTML page) |
| `http://SERVER:8765/tts_test` | 🔊 Test Mario's voice |
| `http://SERVER:8765/tts_cache_preview` | 📦 Browse cached voice lines |

---

## 🧪 Stress Testing

The app includes battle-tested stress testing tools:

```bash
# Quick smoke test (29 tests, ~2 min)
python party_stress_test.py --quick

# Full suite (52 tests, ~5 min)
python party_stress_test.py

# Endurance test (simulates 6 hours of party traffic)
python party_endurance_test.py --hours 6

# Ralph loop (runs until 3 perfect cycles in a row)
python party_endurance_test.py --ralph --hours 8
```

### Test Results (Latest)

| Test | Result |
|------|--------|
| E2E Suite | **52/52 (100%)** |
| 6-Hour Endurance | **851 responses, 98.9% success** |
| Ralph Loop | **3 consecutive perfect cycles** ✅ |
| Health Checks | **967/967 (100%)** across all tests |

---

## 🔥 Troubleshooting

### Mario won't start

| Problem | Fix |
|---------|-----|
| `Ollama not found` | Install Ollama from [ollama.ai](https://ollama.ai), then run `ollama serve` |
| `llama3 not found` | Run `ollama pull llama3` |
| `Port 8765 in use` | Kill the old process: `netstat -ano \| findstr 8765` then `taskkill /PID <pid> /F` |
| `CUDA not available` | Install NVIDIA drivers + CUDA toolkit. Mario falls back to CPU (slower). |

### No sound / bad audio

| Problem | Fix |
|---------|-----|
| No microphone | Run with `--no-mic` or use browser chat at `/chat` |
| No speakers | Check audio output device in system settings |
| Voice sounds weird | GPT-SoVITS may have failed — check server logs for TTS errors |

### Can't connect

| Problem | Fix |
|---------|-----|
| Client can't reach server | Make sure both are on same WiFi. Check server IP with `ipconfig`/`ifconfig`. |
| Firewall blocking | Allow port `8765` through Windows Firewall / macOS firewall |
| WebSocket drops | Server handles 1 client at a time. Disconnect other clients first. |

### Performance

| Problem | Fix |
|---------|-----|
| Slow responses (>5s) | Normal for first response (model loading). Subsequent: 1.5-3s. |
| Very slow (>15s) | Check GPU usage. Ollama may be running on CPU. Run `ollama ps`. |
| Memory issues | llama3 needs ~4.7 GB VRAM. Close other GPU apps. |

---

## 📁 Project Structure

```
Mario_AI/
├── server/                  ← Server code (runs on GPU PC)
│   ├── main.py              ← FastAPI WebSocket server
│   ├── llm.py               ← Ollama integration
│   ├── tts.py               ← Text-to-speech (Edge + RVC)
│   ├── stt.py               ← Speech-to-text (Whisper)
│   ├── speaker_id.py        ← Voice identification
│   ├── memory.py            ← Guest memory (SQLite)
│   ├── emotions.py          ← 13-emotion system
│   ├── game_handlers.py     ← Party games logic
│   ├── idle_behavior.py     ← Idle mumbles & actions
│   ├── gpt_sovits_server.py ← Mario voice subprocess
│   └── requirements.txt
├── client/                  ← Client code (runs on bathroom laptop)
│   ├── main.py              ← Pygame display + audio
│   ├── mario_display.py     ← Mario sprite rendering
│   ├── audio_capture.py     ← Microphone input
│   ├── audio_playback.py    ← Speaker output
│   ├── presence.py          ← Webcam presence detection
│   └── requirements.txt
├── mario_chat.html          ← Browser chat interface
├── mario_models_new/        ← Pre-trained Mario voice models
├── gpt_sovits_env/          ← GPT-SoVITS Python environment
├── gpt_sovits_repo/         ← GPT-SoVITS library
├── config.json              ← All configuration
├── start_server.bat/.sh     ← One-click server start
├── start_client.bat/.sh     ← One-click client start
├── party_stress_test.py     ← 52-test E2E suite
├── party_endurance_test.py  ← 6-hour endurance test
└── party_live_test.py       ← 30-min quality monitor
```

---

## 🎉 Party Day Checklist

- [ ] Server PC plugged in and on WiFi
- [ ] Run `start_server.bat` — wait for "Server running on 0.0.0.0:8765"
- [ ] Test in browser: `http://localhost:8765/chat` — say hi to Mario
- [ ] Set up bathroom laptop with speaker + webcam
- [ ] Run `start_client.bat` — enter server IP
- [ ] Mario should greet you when you walk in front of the camera
- [ ] **Optional**: Open `http://SERVER_IP:8765/leaderboard_page` on a TV/tablet for live scores
- [ ] 🍻 Party time!

---

*Built with ❤️ and too many late nights. Mario has been stress-tested for 8+ hours straight and survived. Your party is in good hands. 🍄*
