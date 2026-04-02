# 🍄 Mario AI Party Bot — Quick Start Guide

> Get Mario running on a Threadripper setup in 10 minutes.

---

## What You Need

The server auto-detects your hardware via `server/hardware.py` and picks optimal settings:

| Tier | GPU VRAM | RAM | CPU Cores | LLM Model |
|------|----------|-----|-----------|-----------|
| **Ultra** (Threadripper) | ≥20 GB | ≥128 GB | ≥32 | 70B Q4 + Mixtral 8x7B |
| High | ≥10 GB | ≥32 GB | ≥8 | llama3 (single) |
| Medium | ≥6 GB | ≥16 GB | any | llama3 (single) |
| Low | <6 GB | <16 GB | any | llama3 (single) |

Your Threadripper Pro (256GB RAM, 64+ cores) will auto-select **Ultra** tier.

---

## Step 1: Clone & Install (Server Machine)

```bash
git clone https://github.com/VillaKeth/Mario-Bathroom-AI.git
cd Mario-Bathroom-AI

# Install Python dependencies
pip install -r server/requirements.txt

# Install Ollama (https://ollama.ai)
# Then pull the models:
ollama pull llama3.1:70b-instruct-q4_K_M    # Quality model (~40GB download)
ollama pull mixtral:8x7b                      # Fast model (~26GB download)
```

## Step 2: Configure

Edit `config.json`:
```json
{
  "server": {
    "birthday_person_name": "Jacob",
    "party_location": "Main Bathroom",
    "party_theme": "Jacob's Birthday Celebration",
    "expected_guest_count": 15
  }
}
```

Everything else is `"auto"` — hardware.py handles it.

## Step 3: Start the Server

```bash
# Windows
start_server.bat

# Linux/Mac
./start_server.sh
```

You'll see:
```
[HARDWARE] Detected: 64 cores, 256GB RAM, 24GB VRAM (NVIDIA RTX ...) → tier=ultra
✅ Mario AI Server running on 0.0.0.0:8765
```

## Step 4: Start the Client (Bathroom Laptop)

```bash
# Windows
start_client.bat

# Linux/Mac
./start_client.sh
```

Press **F11** for fullscreen. Mario is live! 🎉

---

## Key Controls

| Key | Action |
|-----|--------|
| **F11** | Toggle fullscreen |
| **F12** | PANIC MODE (mute everything) |
| **F3** | Chat history sidebar |
| **ESC** | Quit |

## Dashboard (Monitor from Phone)

```
http://SERVER_IP:8765/dashboard
```

Shows health status, guest count, current party phase, GPU stats.

## Hot Reload (No Restart)

Edit `config_live.json` to adjust voice speed, idle timing, etc:
```bash
curl -X POST http://localhost:8765/api/reload
```

---

## What's Built In

- **624 automated tests** — everything is verified
- **Dual LLM** — 70B for quality + Mixtral for speed (auto-routed)
- **4-phase night progression** — energy builds over 8 hours
- **10 party games** — trivia, karaoke, RPS, truth/dare, riddles, etc.
- **VIP birthday system** — Jacob gets special treatment + knowledge
- **Lisa Webb memorial** — triggers at 45 min (moment of silence + toast)
- **Gossip system** — tracks rivalries, alliances, trending topics across guests
- **Memory** — SQLite + Qdrant vector DB, remembers every guest
- **TTS fallback chain** — GPT-SoVITS → Fish Speech → Edge TTS → silence
- **16 Nintendo SFX** — coin, powerup, victory, etc.
- **Auto-recovery** — watchdog, circuit breakers, reconnection

## Pre-Party Checklist

```bash
# Run smoke test
python server/canary.py

# Or via API
curl http://localhost:8765/api/canary
```

All green = ready to party! 🎂
