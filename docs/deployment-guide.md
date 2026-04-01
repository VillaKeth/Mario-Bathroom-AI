# 🎉 Mario AI v2.0 — Party Deployment Guide

> Everything you need to deploy the ULTRA-upgraded Mario for an 8-hour party.

---

## Hardware Requirements

### Server (The Brain)
| Component | Minimum | Recommended (ULTRA) |
|-----------|---------|---------------------|
| CPU | 8-core | Threadripper Pro 3995wx |
| RAM | 32 GB | 256 GB |
| GPU | RTX 3060 12GB | RTX 3090 Ti 24GB |
| Storage | 50 GB free | 100 GB free |
| OS | Windows 10/11 or Linux | Windows 11 |

### Client (The Bathroom)
- Any laptop with mic, speakers, and webcam
- Python 3.10+
- Network connection to server

### VRAM Budget (24GB GPU)
| Component | VRAM |
|-----------|------|
| Llama 3.1 70B (Q4_K_M) | ~18 GB |
| Fish Speech TTS | ~1-2 GB |
| RVC v2 | ~1-2 GB |
| Buffers | ~2 GB |
| **Total** | **~22-24 GB** |

> Whisper STT runs on CPU (int8) to save VRAM.

---

## Pre-Party Setup (Do This Sober, Day Before)

### 1. Install Dependencies

**Server machine:**
```bash
# Install Python 3.10+
# Install CUDA drivers (https://developer.nvidia.com/cuda-downloads)
# Install Ollama (https://ollama.ai)

cd server
pip install -r requirements.txt
```

**Client machine:**
```bash
cd client
pip install -r requirements.txt
```

### 2. Pull LLM Models

```bash
# Quality model (70B) — ~40GB download, takes a while
ollama pull llama3.1:70b-instruct-q4_K_M

# Fast model (8x7B) — ~26GB download
ollama pull mixtral:8x7b
```

Verify they're loaded:
```bash
ollama list
```

### 3. Install Fish Speech TTS

```bash
pip install fish-speech
# Or follow: https://github.com/fishaudio/fish-speech
```

Place Mario voice reference audio in `mario_ref_audio/`.

### 4. Configure `config.json`

Key settings to update:
```json
{
  "server": {
    "llm_quality_model": "llama3.1:70b-instruct-q4_K_M",
    "llm_fast_model": "mixtral:8x7b",
    "stt_device": "cpu",
    "birthday_person_name": "BIRTHDAY_PERSON_NAME_HERE",
    "party_start_time": null,
    "tts_mode": "fish_speech"
  },
  "alert_webhook_url": "YOUR_DISCORD_OR_SLACK_WEBHOOK"
}
```

> `party_start_time` is set automatically when the server starts. Set it manually (epoch timestamp) to resume after a restart.

### 5. Tailscale Setup (Remote Monitoring)

Both machines need Tailscale for secure remote access:

```bash
# Install: https://tailscale.com/download
tailscale up
tailscale ip  # Note the 100.x.x.x IP
```

Access the dashboard from your phone:
```
http://100.x.x.x:8765/dashboard
```

---

## Party Day Checklist

### T-60 Minutes: Start Services

```bash
# 1. Start Ollama (if not auto-started)
ollama serve

# 2. Start the server
start_server.bat        # Windows
./start_server.sh       # Linux/Mac

# 3. Wait for "✅ Mario AI Server running on 0.0.0.0:8765"
```

### T-45 Minutes: Run Pre-Flight Checks

```bash
# Run canary self-test (10 smoke tests)
python scripts/deploy_check.py

# Or via API:
curl http://localhost:8765/api/canary
```

All checks should be ✅ GREEN.

### T-30 Minutes: Start Client

On the bathroom laptop:
```bash
start_client.bat        # Windows
./start_client.sh       # Linux/Mac
# Enter server IP when prompted (use Tailscale IP for remote)
```

### T-15 Minutes: Verify Everything

- [ ] Mario appears fullscreen on bathroom monitor (F11)
- [ ] Mic picks up speech (check server logs for STT output)
- [ ] Mario responds with voice (speakers working)
- [ ] Webcam feed shows in pygame window
- [ ] Dashboard accessible on phone via Tailscale
- [ ] Birthday person name set in config

### T-0: Party Time! 🎉

Mario handles everything automatically:
- **Phase 1 (0-2h):** WARM_UP — Friendly, ice-breaker energy
- **Phase 2 (2-5h):** PARTY_MODE — Full energy, games, roasts
- **Phase 3 (5-7h):** UNHINGED — Maximum chaos, conspiracy theories
- **Phase 4 (7-8h):** WIND_DOWN — Sentimental, heartfelt goodbyes

---

## During the Party

### Monitor via Dashboard
```
http://SERVER_IP:8765/dashboard
```
Shows: health status, guest count, current phase, TTS stats, GPU usage.

### Emergency Controls

| Key | Action |
|-----|--------|
| **F11** | Toggle fullscreen |
| **F12** | PANIC MODE — Mutes Mario, shows "Technical Difficulties" |
| **ESC** | Quit client |

### Hot Reload (No Restart Needed)
Edit `config_live.json` to adjust on-the-fly:
- `tts_rate`, `tts_pitch` — Voice tuning
- `idle_interval_min/max` — How often Mario talks unprompted
- `llm_timeout_seconds` — Response timeout

```bash
curl -X POST http://localhost:8765/api/reload
```

### If Something Goes Wrong

1. **Mario stops responding:** Check dashboard health. Watchdog auto-restarts after 3 failures.
2. **GPU out of memory:** Lower `llm_quality_model` to a smaller model in config, hot-reload.
3. **Client disconnects:** It auto-reconnects. Shows "bathroom break" overlay meanwhile.
4. **F12 panic mode:** Mutes everything. Press F12 again to resume.

---

## Post-Party

### Generate Party Report
```bash
curl http://localhost:8765/api/report
```
Or visit `http://SERVER_IP:8765/report` for the HTML version.

Shows: total guests, interactions, popular games, funniest moments, phase timeline.

### Logs
- Server logs: `logs/` directory
- Debug log: `server_debug.log`

---

## Architecture Overview

```
┌─────────────────────────────────────────────────┐
│                 SERVER (Brain PC)                 │
│                                                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐   │
│  │ Whisper   │  │ Ollama   │  │ Fish Speech  │   │
│  │ STT (CPU) │  │ LLM(GPU) │  │ TTS (GPU)    │   │
│  └────┬─────┘  └────┬─────┘  └──────┬───────┘   │
│       │              │               │            │
│  ┌────┴──────────────┴───────────────┴────────┐  │
│  │              main.py (FastAPI)              │  │
│  │  WebSocket :8765  │  Dashboard :8765        │  │
│  └────────────────────┬───────────────────────┘  │
│                       │                           │
│  ┌────────────────────┼───────────────────────┐  │
│  │  watchdog  │ night_progression │ gossip    │  │
│  │  canary    │ birthday_vip      │ games     │  │
│  │  hot_reload│ catchphrase_mirror│ memory    │  │
│  └────────────────────────────────────────────┘  │
└──────────────────────┬────────────────────────────┘
                       │ WebSocket (ws://:8765/ws)
┌──────────────────────┴────────────────────────────┐
│              CLIENT (Bathroom Laptop)              │
│                                                    │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐    │
│  │ Pygame   │  │ Mic      │  │ Speakers     │    │
│  │ Display  │  │ Capture  │  │ Playback     │    │
│  └──────────┘  └──────────┘  └──────────────┘    │
└────────────────────────────────────────────────────┘
```

---

## v2.0 New Features

| Feature | Description |
|---------|-------------|
| **Dual LLM Router** | Mixtral (fast) + 70B (quality) with smart routing |
| **Fish Speech TTS** | High-quality Mario voice with 5-level fallback |
| **Night Progression** | 4 phases with escalating energy over 8 hours |
| **Reliability Layer** | Watchdog, auto-restart, health dashboard |
| **Pygame Hardening** | Fullscreen, panic mode, crash recovery |
| **Vomit Detection** | Volume spike + temporal coherence analysis |
| **Pre-Party Canary** | 10 automated smoke tests before guests arrive |
| **Hot Reload** | Change settings without restarting |
| **Birthday VIP** | Special treatment for the birthday person |
| **Sound Effects** | Nintendo SFX triggers on keywords |
| **Catchphrase Mirror** | Learns and echoes guest phrases |
| **Party Report** | End-of-party stats and highlight reel |
