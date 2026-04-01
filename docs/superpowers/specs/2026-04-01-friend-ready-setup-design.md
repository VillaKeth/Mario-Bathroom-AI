# Friend-Ready Setup System — Design Spec

**Date:** 2026-04-01
**Goal:** Enable a new user (specifically the Threadripper Pro friend) to clone the repo and get the Mario AI Party Bot fully running with one command, taking advantage of all available hardware.

---

## Problem Statement

The Mario AI Party Bot has many gitignored dependencies that a fresh clone won't include:
- `gpt_sovits_env/` — Python venv for GPT-SoVITS TTS
- `gpt_sovits_repo/` — The GPT-SoVITS library source
- `mario_models_new/GPT_SoVITS_Mario/` — Voice model checkpoints (~500MB)
- `server/data/rvc_model/` — RVC v2 voice conversion model
- `mario_ref_audio/` — Mario voice reference sentences
- `config.json` — Main configuration (gitignored, contains party-specific settings)
- Ollama models — llama3 (4.7GB), optionally llama3.1:70b-q4_k_m (40GB), mixtral:8x7b (26GB)
- Fish Speech library — Needed for ULTRA tier voice cloning

A new user currently has to reverse-engineer what's needed from code comments and error messages. This spec creates a turnkey setup experience.

---

## Target User

**Primary:** Friend with Threadripper Pro workstation
- GPU: ≥20GB VRAM (likely RTX 3090/4090 or A6000)
- RAM: ≥128GB
- CPU: ≥32 cores (Threadripper Pro)
- Hardware tier: **ULTRA**
- Should get ALL features: Fish Speech, dual-model LLM (70B + Mixtral), 8 TTS workers, 8192 context window

**Secondary:** Any developer cloning the repo
- Script auto-detects tier and adjusts accordingly
- Lower tiers skip Fish Speech, use single llama3 model, fewer workers

---

## Deliverables

### 1. `setup.bat` — One-Click Windows Installer

**Location:** Project root

**Flow:**
```
1. Print banner: "🍄 Mario AI Party Bot — Setup Wizard"
2. Check Python 3.10+ → error if missing with install link
3. Check/prompt for Ollama → error if missing with install link
4. Detect hardware (GPU VRAM, RAM, CPU cores) → print tier
5. Create Python venv `venv/` → install server + client deps
6. Download models-v2.0.zip from GitHub Release → extract
   - mario_models_new/GPT_SoVITS_Mario/ (checkpoints)
   - server/data/rvc_model/ (RVC v2 model)  
   - mario_ref_audio/ (reference audio)
7. Clone GPT-SoVITS repo → create gpt_sovits_env → install deps
8. Pull Ollama models (tier-aware):
   - ALL tiers: ollama pull llama3
   - ULTRA: + ollama pull llama3.1:70b-instruct-q4_K_M
   - ULTRA: + ollama pull mixtral:8x7b
9. ULTRA only: pip install fish-speech in main venv
10. Generate config.json from config.example.json if not exists
11. Run scripts/verify_setup.py → report pass/fail for each component
12. Print: "✅ Setup complete! Run start_server.bat to launch."
```

**Error handling:**
- Each step has clear error message with fix instructions
- Non-fatal failures (e.g., Fish Speech install fails) print warning but continue
- Final summary shows what passed and what needs manual attention

**Idempotent:** Running setup.bat again skips already-completed steps (checks for existing venv, models, etc.)

### 2. `setup.sh` — Linux/Mac equivalent

Same logic as setup.bat but for bash. Uses `python3`/`pip3`, different venv activation syntax.

### 3. `config.example.json` — Template Configuration

**Location:** Project root (checked into git)

Identical to config.json but with:
- All `"auto"` values for hardware-detected settings
- `birthday_person_name: "YourFriendName"` placeholder
- `birthday_person_facts: []` empty array with comment
- `admin_api_key: ""` empty
- `alert_webhook_url: ""` empty
- All debug flags set to `true` (helpful for new setup)

### 4. `scripts/verify_setup.py` — Post-Setup Health Check

**Location:** `scripts/verify_setup.py`

Checks each component and prints pass/fail:
```
🔍 Mario AI Setup Verification
================================
[✅] Python 3.10+ .............. 3.11.9
[✅] Ollama reachable .......... http://localhost:11434
[✅] llama3 model .............. 4.7GB
[✅] llama3.1:70b-q4_k_m ...... 40GB (ULTRA)
[✅] mixtral:8x7b .............. 26GB (ULTRA)
[✅] GPT-SoVITS venv ........... gpt_sovits_env/Scripts/python.exe
[✅] GPT-SoVITS models ......... Mario-e20.ckpt, Mario_e15_s255.pth
[✅] RVC model ................. server/data/rvc_model/
[✅] Mario ref audio ........... mario_ref_audio/
[✅] Fish Speech ............... v2.2.0 (ULTRA only)
[✅] config.json ............... Valid, 69 settings
[✅] Qdrant client ............. qdrant-client 1.9.0
[✅] VIP profiles .............. 1 profile (Jacob Hoppenstedt)
[✅] SFX WAV files ............. 6 files in assets/sfx/
[✅] Server imports ............ All modules load
[✅] Quick TTS test ............ Edge TTS synthesized OK (1.2s)
================================
16/16 checks passed — Ready to party! 🎉

Hardware: ULTRA tier (24GB VRAM, 128GB RAM, 64 cores)
Run: start_server.bat
```

**Exit codes:** 0 = all pass, 1 = critical failures, 2 = warnings only

### 5. GitHub Release Asset: `models-v2.0.zip`

**Contents:**
```
models-v2.0.zip
├── mario_models_new/
│   └── GPT_SoVITS_Mario/
│       ├── Mario-e20.ckpt          (~200MB GPT checkpoint)
│       ├── Mario_e15_s255.pth      (~200MB SoVITS checkpoint)
│       ├── mario_ref.wav           (reference audio)
│       └── tts_infer.yaml          (inference config)
├── server/
│   └── data/
│       └── rvc_model/
│           └── Mario_RVC_v2.pth    (~100MB RVC model)
└── mario_ref_audio/
    └── mario_reference_sentences.wav
```

**Upload to:** GitHub Release tagged `v2.0` (or `v2.1` if v2.0 exists)
**Download URL pattern:** `https://github.com/VillaKeth/Mario-Bathroom-AI/releases/download/v2.1/models-v2.0.zip`

### 6. Updated README.md

Add/update sections:
- **Quick Start (5 minutes):** Clone → setup.bat → start_server.bat → open browser
- **Hardware Tiers:** Table showing what each tier gets
- **Manual Setup:** Step-by-step for each component (fallback if script fails)
- **ULTRA Tier Features:** Fish Speech, 70B model, Mixtral, full TTS chain
- **Customization:** How to change birthday person, add VIP profiles, adjust personality

---

## Architecture Decisions

### Why setup.bat and not a Python installer?
- Zero dependencies — runs before Python venv is created
- Batch/bash are universally available
- Can check system prerequisites (Python, Ollama) before any pip installs

### Why GitHub Releases for models?
- No auth needed (public repo)
- `curl` available everywhere
- Setup script can auto-download
- Versioned alongside code releases

### Why config.example.json instead of auto-generating?
- User can see all available options
- Copy + customize is familiar workflow
- Setup script copies it if config.json doesn't exist
- Comments explain what each setting does

### Why a separate verify script?
- Can be run anytime, not just after setup
- Useful for debugging "it doesn't work" issues
- Provides clear pass/fail for each component
- Exit code enables CI/CD integration

---

## Out of Scope

- Docker/container setup (could be added later)
- Automated GPU driver installation
- Ollama auto-installation (user must install manually, script checks)
- Training new voice models (uses pre-trained Mario voice)
- Cloud deployment (this is for local/LAN use)

---

## Success Criteria

1. Friend clones repo, runs `setup.bat`, everything installs without errors
2. `verify_setup.py` reports 16/16 checks passed
3. Server starts and responds to browser chat at localhost:8765/chat
4. Hardware auto-detected as ULTRA tier with all features enabled
5. VIP knowledge works (ask "What university did Jacob go to?" → "University of Florida")
6. GPT-SoVITS produces Mario-voice audio
7. Fish Speech available as TTS fallback (ULTRA tier)
8. Dual-model routing active (70B for quality, Mixtral for fast)
