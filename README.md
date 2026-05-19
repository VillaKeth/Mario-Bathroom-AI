# 🍄 Mario AI — Party Bathroom Bot

**It's-a me, MARIO!** An AI-powered Mario that guards your bathroom at parties. He talks, jokes, plays games, remembers guests by voice, and never breaks character.

> **Battle-tested**: 8+ hours continuous operation, 850+ responses, 100% health checks passing.

---

## 🚀 SETUP (Fresh Computer — Do This Before The Party)

### Prerequisites — Install These First

| # | What | Link | Notes |
|---|------|------|-------|
| 1 | **Python 3.10+** | [python.org/downloads](https://python.org/downloads) | ⚠️ Check **"Add Python to PATH"** during install! |
| 2 | **Ollama** | [ollama.ai](https://ollama.ai) | Just download and run the installer |
| 3 | **Git** | [git-scm.com](https://git-scm.com) | Default options are fine |

> **No npm, no Node.js, no Docker needed.** This is 100% Python.

### One-Command Install

```bash
git clone https://github.com/VillaKeth/Mario-Bathroom-AI.git
cd Mario-Bathroom-AI
```

**Windows:**
```
setup.bat
```

**Mac / Linux:**
```bash
chmod +x setup.sh && ./setup.sh
```

☕ This takes 10-20 minutes (downloads ~5 GB of AI models). Go make coffee.

The setup wizard automatically:
- ✅ Creates a Python virtual environment
- ✅ Installs PyTorch (with CUDA if you have an NVIDIA GPU)
- ✅ Installs all Python dependencies
- ✅ Downloads Mario voice models (~930 MB)
- ✅ Sets up GPT-SoVITS voice cloning
- ✅ Pulls Ollama LLM models (~4.7 GB)
- ✅ Creates config.json
- ✅ Runs verification checks

### Start Mario

**Windows:**
```
start_server.bat
```

**Mac / Linux:**
```bash
./start_server.sh
```

You'll see:
```
✅ Mario AI Server running on 0.0.0.0:8765
```

### Talk to Mario

Open a browser and go to:
```
http://localhost:8765/chat
```

**That's it. You're done. 🎉**

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

## 🖥️ Two-Computer Setup (Optional — For Parties)

You can run Mario on **two computers**: a beefy PC (the brain) and a laptop in the bathroom (the face).

### Server PC (the brain)
Run `start_server.bat` as described above.

### Bathroom Laptop (the face)

**Windows:**
```
start_client.bat
```

**Mac / Linux:**
```bash
./start_client.sh
```

It will ask for the server's IP address. On the server PC, run `ipconfig` (Windows) or `ifconfig` (Mac/Linux) and look for `192.168.x.x`.

### Or Skip the Client — Browser Mode!

On **any device** on the same WiFi, open:
```
http://SERVER_IP:8765/chat
```
Works on phones too! 📱

---

## ⚙️ Configuration

Edit **`config.json`** at the project root:

```jsonc
{
  "server": {
    "birthday_person_name": "YourFriendName",
    "birthday_person_facts": [
      "Add facts about the birthday person here",
      "Mario will use these to personalize interactions"
    ],
    "party_location": "the bathroom",
    "party_theme": "Birthday Party"
  }
}
```

Everything else defaults to `"auto"` — hardware detection handles it.

### Useful URLs

| URL | What It Does |
|-----|-------------|
| `http://SERVER:8765/chat` | 💬 Browser chat interface |
| `http://SERVER:8765/health` | 🩺 Server health check (JSON) |
| `http://SERVER:8765/stats` | 📊 Party statistics |
| `http://SERVER:8765/leaderboard_page` | 🏆 Guest leaderboard |
| `http://SERVER:8765/dashboard` | 📊 Live dashboard |
| `http://SERVER:8765/tts_test` | 🔊 Test Mario's voice |

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

## 🔥 Troubleshooting

### Setup fails

| Problem | Fix |
|---------|-----|
| `python not found` | Make sure you checked "Add Python to PATH" during Python install. Restart your terminal. |
| `pip` errors during install | Run `setup.bat` again — it picks up where it left off |
| `Ollama not found` | Install Ollama from [ollama.ai](https://ollama.ai), then restart your terminal |
| PyTorch install is slow | Normal — it's ~2.5 GB. Be patient. |

### Mario won't start

| Problem | Fix |
|---------|-----|
| `llama3 not found` | Run `ollama pull llama3` |
| `Port 8765 in use` | Kill the old process: `netstat -ano | findstr 8765` then `taskkill /PID <pid> /F` |
| `CUDA not available` | Mario falls back to CPU (slower but works). Install NVIDIA CUDA for speed. |
| `ModuleNotFoundError` | Run `setup.bat` again to reinstall dependencies |

### No sound / bad audio

| Problem | Fix |
|---------|-----|
| No microphone | Use browser chat at `/chat` — it supports text input |
| Voice sounds weird | GPT-SoVITS may have failed — check server logs. Mario falls back to Edge TTS. |

### Can't connect (two-computer setup)

| Problem | Fix |
|---------|-----|
| Client can't reach server | Same WiFi? Check server IP with `ipconfig`/`ifconfig`. |
| Firewall blocking | Allow port `8765` through your firewall |

---

## 🧪 Verify Setup

After setup, run anytime to check everything:
```
python scripts/verify_setup.py
```

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
│   └── requirements.txt
├── client/                  ← Client code (optional, for bathroom laptop)
│   ├── main.py              ← Pygame display + audio
│   └── requirements.txt
├── web/                     ← Browser chat interface files
├── config.json              ← All configuration
├── config.example.json      ← Template config
├── setup.bat / setup.sh     ← One-command setup
├── start_server.bat / .sh   ← Start the server
└── start_client.bat / .sh   ← Start the client (optional)
```

---

## 🎉 Party Day Checklist

- [ ] Server PC plugged in and on WiFi
- [ ] Run `start_server.bat` — wait for "Server running on 0.0.0.0:8765"
- [ ] Test in browser: `http://localhost:8765/chat` — say hi to Mario
- [ ] (Optional) Set up bathroom laptop with speaker + webcam
- [ ] (Optional) Run `start_client.bat` — enter server IP
- [ ] (Optional) Open `http://SERVER_IP:8765/leaderboard_page` on a TV for live scores
- [ ] 🍻 Party time!

---

<details>
<summary>📋 Manual Setup (if setup script fails)</summary>

1. **Create venv and install deps:**
   ```bash
   python -m venv venv
   
   # Windows:
   venv\Scripts\activate
   # Mac/Linux:
   source venv/bin/activate
   
   # Install PyTorch (pick one):
   pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121   # NVIDIA GPU
   pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu     # No GPU
   
   # Install everything else:
   pip install -r server/requirements.txt
   pip install -r client/requirements.txt
   ```

2. **Pull Ollama model:**
   ```bash
   ollama pull llama3
   ```

3. **Create config:**
   ```bash
   # Windows:
   copy config.example.json config.json
   # Mac/Linux:
   cp config.example.json config.json
   ```

4. **Start server:**
   ```bash
   # Windows:
   start_server.bat
   # Mac/Linux:
   ./start_server.sh
   ```

</details>

---

*Built with ❤️ and too many late nights. Mario has been stress-tested for 8+ hours straight and survived. Your party is in good hands. 🍄*
