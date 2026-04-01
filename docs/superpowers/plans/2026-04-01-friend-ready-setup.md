# Friend-Ready Setup System — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable a new user to clone the repo and run one command (`setup.bat`) to get the Mario AI Party Bot fully operational, with automatic hardware detection and tier-appropriate feature setup.

**Architecture:** A batch/shell setup script orchestrates: Python venv creation, model downloads from GitHub Releases, GPT-SoVITS installation via its own install script, tier-aware Ollama model pulling, and config generation. A separate verify script validates every component post-setup.

**Tech Stack:** Windows Batch + Bash, Python 3.10+, curl, Ollama CLI, GPT-SoVITS install.ps1, pip

**Spec:** `docs/superpowers/specs/2026-04-01-friend-ready-setup-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `config.example.json` | CREATE | Template config with all fields, `"auto"` for hardware-detected values, placeholder birthday facts |
| `scripts/verify_setup.py` | CREATE | Post-setup health check — validates every component, prints pass/fail table |
| `scripts/package_models.py` | CREATE | Helper to create `models-v2.1.zip` from local model dirs for GitHub Release upload |
| `setup.bat` | CREATE | One-click Windows setup: venv, models, GPT-SoVITS, Ollama, Fish Speech, config |
| `setup.sh` | CREATE | Linux/Mac equivalent of setup.bat |
| `README.md` | MODIFY | Add "First Time Setup" section, hardware tier table, manual setup fallback |
| `start_server.bat` | MODIFY | Add check for config.json existence, point to setup.bat if missing |

---

### Task 1: Create `config.example.json`

**Files:**
- Create: `config.example.json`

This is the template that `setup.bat` copies to `config.json`. All hardware-detected values use `"auto"`. Birthday person uses placeholder values.

- [ ] **Step 1: Create config.example.json**

```json
{
  "server": {
    "host": "0.0.0.0",
    "port": 8765,
    "stt_model_size": "auto",
    "stt_device": "cpu",
    "llm_model": "llama3",
    "tts_voice": "en-US-GuyNeural",
    "tts_rate": "+20%",
    "tts_pitch": "+0Hz",
    "tts_fast_mode": true,
    "tts_mode": "sovits",
    "tts_streaming": true,
    "speaker_similarity_threshold": 0.75,
    "debug_server": true,
    "debug_tts": true,
    "debug_idle": true,
    "debug_pose": true,
    "game_max_rounds_simon": 5,
    "game_max_rounds_truth_dare": 5,
    "game_max_questions_20q": 10,
    "game_max_attempts_riddle": 5,
    "game_max_rounds_word_chain": 10,
    "game_max_rounds_rapid_fire": 15,
    "conversation_history_limit": "auto",
    "command_cooldown_seconds": 1.0,
    "text_input_cooldown_seconds": 2.0,
    "llm_timeout_seconds": 30,
    "idle_interval_min_seconds": 15,
    "idle_interval_max_seconds": 90,
    "admin_api_key": "",
    "tts_workers": "auto",
    "tts_concurrency": "auto",
    "gpu_idle_threshold": "auto",
    "precache_pause_seconds": "auto",
    "max_background_tasks": "auto",
    "max_cache_memory": "auto",
    "llm_num_predict": "auto",
    "llm_num_ctx": "auto",
    "llm_quality_model": "auto",
    "llm_fast_model": "auto",
    "party_start_time": null,
    "birthday_person_name": "YourFriendName",
    "birthday_person_facts": [
      "REPLACE: Add facts about the birthday person here",
      "REPLACE: Each fact is a string in this array",
      "REPLACE: Mario will use these to personalize interactions"
    ]
  },
  "client": {
    "server_url": "ws://localhost:8765/ws",
    "enable_camera": true,
    "enable_microphone": true,
    "window_width": 800,
    "window_height": 600,
    "audio_send_interval": 0.25,
    "audio_gain": 1.0
  },
  "elevenlabs_api_key": "",
  "alert_webhook_url": ""
}
```

- [ ] **Step 2: Verify config.example.json is valid JSON**

Run: `python -c "import json; json.load(open('config.example.json'))" && echo OK`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add config.example.json
git commit -m "feat: add config.example.json template for new user setup"
```

---

### Task 2: Create `scripts/verify_setup.py`

**Files:**
- Create: `scripts/verify_setup.py`

Standalone script that checks every component. No server imports — uses subprocess calls, file checks, and pip queries. Prints color-coded pass/fail table. Exits 0 on all-pass, 1 on critical failure, 2 on warnings-only.

- [ ] **Step 1: Create verify_setup.py**

The script must check these components in order:
1. Python version ≥ 3.10
2. CUDA / GPU drivers (nvidia-smi or torch.cuda)
3. Hardware tier detection (import server.hardware)
4. Ollama installed (`ollama --version`)
5. Ollama service running (`ollama list`)
6. llama3 model present (parse `ollama list` output)
7. ULTRA-only: `llama3.1:70b-q4_k_m` present (NOTE: this is the exact name from `hardware.py` — no "instruct" suffix)
8. ULTRA-only: mixtral:8x7b present
9. GPT-SoVITS venv exists (`gpt_sovits_env/Scripts/python.exe`)
10. GPT-SoVITS Mario models exist (`mario_models_new/GPT_SoVITS_Mario/Mario-e20.ckpt`, `Mario_e15_s255.pth`)
11. GPT-SoVITS pretrained models exist (`gpt_sovits_repo/GPT_SoVITS/pretrained_models/chinese-roberta-wwm-ext-large/`, `chinese-hubert-base/`)
12. RVC models exist — check BOTH `mario_models_new/MarioSwitch/SuperMario-NintendoSwitchEra.pth` AND `server/data/rvc_model/SuperMario-TITAN_e500_s13000.pth` (TITAN is actively used by server)
13. Mario reference audio exists (`server/data/mario_reference_sentences_30s.wav` or fallback `mario_reference_sentences.wav`)
14. ULTRA-only: Fish Speech installed (use `pip show fish-speech` — actual import name may differ)
15. config.json exists and is valid JSON
16. qdrant-client installed (`python -c "from qdrant_client import QdrantClient"`)
17. VIP profile exists (`server/data/vip_profiles/jacob_hoppenstedt.json`)
18. SFX WAV files exist (6 files in `assets/sfx/`)
19. Server core imports work (`python -c "from server import main"`)
20. Edge TTS quick test (synthesize one sentence, measure time)

Each check prints: `[✅]`, `[❌]`, `[⚠️]`, or `[  ]` (skipped) with details.

Implementation approach:
```python
#!/usr/bin/env python3
"""Post-setup health check for Mario AI Party Bot."""
import sys, os, json, subprocess, shutil, importlib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
# ... check functions ...

class Check:
    def __init__(self, name, description):
        self.name = name
        self.description = description
        self.status = None  # pass/fail/warn/skip
        self.detail = ""

def check_python_version(): ...
def check_cuda_drivers(): ...
def check_hardware_tier(): ...
def check_ollama_installed(): ...
def check_ollama_running(): ...
def check_ollama_model(model_name): ...
def check_file_exists(path, desc): ...
def check_python_import(module, desc): ...
def check_edge_tts(): ...  # synthesize one sentence

def main():
    checks = []
    # Run all checks, collect results
    # Print formatted table
    # Exit with appropriate code
```

- [ ] **Step 2: Test verify_setup.py on current machine**

Run: `python scripts/verify_setup.py`
Expected: Most checks pass (this machine has everything installed). Note any failures.

- [ ] **Step 3: Test with `--full-tts` flag**

Run: `python scripts/verify_setup.py --full-tts`
Expected: Additional GPT-SoVITS subprocess test (takes 10-15s).

- [ ] **Step 4: Commit**

```bash
git add scripts/verify_setup.py
git commit -m "feat: add post-setup verification script (20 component checks)"
```

---

### Task 3: Create `scripts/package_models.py`

**Files:**
- Create: `scripts/package_models.py`

Helper script that creates `models-v2.1.zip` from the local model directories. Run this on the dev machine to prepare the GitHub Release asset.

- [ ] **Step 1: Create package_models.py**

The script must zip these directories/files:
```
mario_models_new/GPT_SoVITS_Mario/
    Mario-e20.ckpt
    Mario_e15_s255.pth
    mario_ref.wav
    tts_infer.yaml
mario_models_new/MarioSwitch/
    SuperMario-NintendoSwitchEra.pth
    added_IVF423_Flat_nprobe_1_SuperMario-NintendoSwitchEra_v2.index
mario_models_new/SuperMario_TITAN/
    (all files)
server/data/rvc_model/
    SuperMario-TITAN_e500_s13000.pth
    added_IVF445_Flat_nprobe_1_SuperMario-TITAN_v2.index
server/data/mario_reference_sentences_30s.wav
server/data/mario_reference_sentences.wav (if exists)
```

Script should:
1. Verify all source files exist
2. Create zip with preserved directory structure
3. Print total size and file count
4. Save to `models-v2.1.zip` in project root

```python
#!/usr/bin/env python3
"""Package model files into a zip for GitHub Release upload."""
import zipfile, os, sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

INCLUDE_PATHS = [
    "mario_models_new/GPT_SoVITS_Mario",
    "mario_models_new/MarioSwitch",
    "mario_models_new/SuperMario_TITAN",
    "server/data/rvc_model",
    "server/data/mario_reference_sentences_30s.wav",
]

def main():
    output = PROJECT_ROOT / "models-v2.1.zip"
    # ... zip creation logic with progress ...
    print(f"Created {output} ({output.stat().st_size / 1024 / 1024:.1f} MB)")
```

- [ ] **Step 2: Run package_models.py to create the zip**

Run: `python scripts/package_models.py`
Expected: Creates `models-v2.1.zip` with all model files. Prints size.

- [ ] **Step 3: Verify zip contents**

Run: `python -c "import zipfile; z=zipfile.ZipFile('models-v2.1.zip'); [print(f) for f in z.namelist()[:20]]; print(f'Total: {len(z.namelist())} files')"` 
Expected: Lists model files with correct directory structure.

- [ ] **Step 4: Commit script (NOT the zip)**

```bash
git add scripts/package_models.py
git commit -m "feat: add model packaging script for GitHub Release"
```

---

### Task 4: Create `setup.bat`

**Files:**
- Create: `setup.bat`

One-click Windows installer. Must be idempotent (skip already-completed steps).

- [ ] **Step 1: Create setup.bat**

Key implementation details:
- Use `curl.exe` (built into Windows 10+) to download from GitHub Releases
- Use `powershell -Command "Expand-Archive ..."` for zip extraction
- Hardware detection via Python one-liner: `python -c "from server.hardware import detect_hardware, _tier; hw=detect_hardware(); print(_tier(hw))"`
  - NOTE: This requires server deps installed first, so detection happens after venv creation
- GPT-SoVITS setup calls `install.ps1` from the cloned repo
- Ollama model pulling uses `ollama pull` (blocks until complete, shows progress)
- Fish Speech: `pip install fish-speech>=2.2.0` (only for ULTRA tier)
- Config: `copy config.example.json config.json` if config.json doesn't exist

Flow:
```batch
@echo off
setlocal enabledelayedexpansion
echo.
echo  ========================================
echo   Mario AI Party Bot - Setup Wizard
echo  ========================================

REM Step 1: Check Python 3.10+
python -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" 2>nul
if errorlevel 1 (
    echo ERROR: Python 3.10+ required. Install from https://python.org
    pause & exit /b 1
)

REM Step 2: Check Ollama installed
ollama --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Ollama not found. Install from https://ollama.ai
    pause & exit /b 1
)

REM Step 3: Check Ollama service running
ollama list >nul 2>&1
if errorlevel 1 (
    echo WARNING: Ollama service not running. Start it with: ollama serve
    echo (Open another terminal and run: ollama serve)
    pause
)

REM Step 4: Create Python venv (if not exists)
if not exist "venv\Scripts\python.exe" (
    echo Creating Python virtual environment...
    python -m venv venv
)
call venv\Scripts\activate.bat

REM Step 5: Install dependencies
echo Installing server dependencies...
pip install -r server\requirements.txt --quiet
echo Installing client dependencies...
pip install -r client\requirements.txt --quiet

REM Step 6: Detect hardware tier (uses nvidia-smi fallback if torch not ready)
for /f %%i in ('python -c "import sys; sys.path.insert(0,'.'); from server.hardware import detect_hardware; hw=detect_hardware(); v,r,c=hw['gpu_vram_gb'],hw['ram_gb'],hw['cpu_cores']; print('ultra' if v>=20 and r>=128 and c>=32 else 'high' if v>=10 and r>=32 and c>=8 else 'medium' if v>=6 and r>=16 else 'low')"') do set TIER=%%i
if "%TIER%"=="" set TIER=low
echo.
echo Detected hardware tier: %TIER%

REM Step 7: Download models (if not exists)
REM Check for multiple critical model files to catch partial extractions
if not exist "mario_models_new\GPT_SoVITS_Mario\Mario-e20.ckpt" if not exist "server\data\rvc_model\SuperMario-TITAN_e500_s13000.pth" (
    echo Downloading voice models from GitHub Release...
    curl -L -o models-v2.1.zip https://github.com/VillaKeth/Mario-Bathroom-AI/releases/download/v2.1/models-v2.1.zip
    echo Extracting models...
    powershell -Command "Expand-Archive -Force 'models-v2.1.zip' '.'"
    del models-v2.1.zip
) else (
    echo Voice models already present, skipping download.
)

REM Step 8: GPT-SoVITS setup (if venv not exists)
if not exist "gpt_sovits_env\Scripts\python.exe" (
    echo Setting up GPT-SoVITS (this takes a while)...
    if not exist "gpt_sovits_repo" (
        git clone https://github.com/RVC-Boss/GPT-SoVITS.git gpt_sovits_repo
    )
    cd gpt_sovits_repo
    REM install.ps1 requires mandatory params: -Device (CU126|CU128|CPU) -Source (HF|HF-Mirror|ModelScope)
    REM Detect CUDA version to choose CU126 vs CU128; default to CU128 for modern GPUs
    powershell -ExecutionPolicy Bypass -File install.ps1 -Device CU128 -Source HF
    cd ..
) else (
    echo GPT-SoVITS already set up, skipping.
)

REM Step 9: Pull Ollama models
echo Pulling Ollama models for %TIER% tier...
ollama list 2>nul | findstr "llama3 " >nul
if errorlevel 1 (
    echo Pulling llama3 (~4.7 GB)...
    ollama pull llama3
)

if "%TIER%"=="ultra" (
    ollama list 2>nul | findstr "llama3.1:70b" >nul
    if errorlevel 1 (
        echo Pulling llama3.1:70b-q4_k_m (~40 GB, this will take a while)...
        ollama pull llama3.1:70b-q4_k_m
    )
    ollama list 2>nul | findstr "mixtral:8x7b" >nul
    if errorlevel 1 (
        echo Pulling mixtral:8x7b (~26 GB)...
        ollama pull mixtral:8x7b
    )
)

REM Step 10: Fish Speech (ULTRA only)
if "%TIER%"=="ultra" (
    echo Installing Fish Speech TTS...
    pip install fish-speech>=2.2.0 --quiet 2>nul
    if errorlevel 1 (
        echo WARNING: Fish Speech install failed. This is optional - GPT-SoVITS will be used.
    )
)

REM Step 11: Generate config.json
if not exist "config.json" (
    echo Creating config.json from template...
    copy config.example.json config.json
    echo NOTE: Edit config.json to set birthday_person_name and birthday_person_facts
)

REM Step 12: Run verification
echo.
echo Running setup verification...
python scripts\verify_setup.py

echo.
echo ========================================
echo   Setup Complete!
echo   Run: start_server.bat
echo   Then open: http://localhost:8765/chat
echo ========================================
pause
```

NOTE: The above is pseudocode — the actual implementation must handle Windows batch edge cases (errorlevel behavior, variable expansion, path quoting). The subagent should test each section. Key fixes from review: Python version uses one-liner (not findstr regex), install.ps1 gets mandatory -Device/-Source params, model check uses multiple files, Ollama model names match hardware.py exactly (`llama3.1:70b-q4_k_m` not `instruct`), and tier detection has `low` fallback.

- [ ] **Step 2: Test setup.bat on current machine (dry run)**

Since this machine already has everything installed, most steps should be skipped. Verify:
- Python check passes
- Ollama check passes
- venv creation skipped (or creates fresh)
- Model download skipped (files already exist)
- GPT-SoVITS skipped (venv exists)
- Ollama models skipped (already pulled)
- config.json skipped (already exists)
- Verification runs successfully

- [ ] **Step 3: Commit**

```bash
git add setup.bat
git commit -m "feat: add one-click Windows setup script with hardware tier detection"
```

---

### Task 5: Create `setup.sh`

**Files:**
- Create: `setup.sh`

Linux/Mac equivalent. Same logic as setup.bat but in bash.

- [ ] **Step 1: Create setup.sh**

Key differences from setup.bat:
- Uses `python3` and `pip3`
- venv activation: `source venv/bin/activate`
- GPT-SoVITS: `bash install.sh` instead of `powershell install.ps1`
- GPT-SoVITS venv path: `gpt_sovits_env/bin/python` (not Scripts)
- Uses `unzip` or `python -m zipfile` for extraction
- Check for `nvidia-smi` instead of assuming CUDA

```bash
#!/bin/bash
set -e
echo ""
echo "========================================"
echo "  Mario AI Party Bot — Setup Wizard"
echo "========================================"
# ... same flow as setup.bat but bash syntax ...
```

- [ ] **Step 2: Make executable**

Run: `chmod +x setup.sh` (or note in README for Linux/Mac users)

- [ ] **Step 3: Commit**

```bash
git add setup.sh
git commit -m "feat: add Linux/Mac setup script"
```

---

### Task 6: Update `README.md`

**Files:**
- Modify: `README.md`

Add a prominent "First Time Setup" section near the top, after the existing Quick Start. Add hardware tier table. Keep existing content intact.

- [ ] **Step 1: Add "First Time Setup" section after Quick Start**

Insert after the existing Quick Start section (after "Browser Mode"):

```markdown
## 🔧 First Time Setup (New Machine)

If this is your first time running Mario AI, use the setup wizard:

### Windows
```
git clone https://github.com/VillaKeth/Mario-Bathroom-AI.git
cd Mario-Bathroom-AI
setup.bat
```

### Linux / Mac
```
git clone https://github.com/VillaKeth/Mario-Bathroom-AI.git
cd Mario-Bathroom-AI
chmod +x setup.sh && ./setup.sh
```

The setup wizard will:
1. ✅ Create a Python virtual environment
2. ✅ Download voice models (~500 MB)
3. ✅ Install GPT-SoVITS (Mario voice cloning)
4. ✅ Pull Ollama LLM models (tier-appropriate)
5. ✅ Install Fish Speech (ULTRA tier only)
6. ✅ Generate config.json
7. ✅ Run verification checks

### Hardware Tiers

Mario auto-detects your hardware and adjusts features:

| Tier | GPU VRAM | RAM | CPU Cores | LLM Models | TTS Workers | Features |
|------|----------|-----|-----------|------------|-------------|----------|
| **ULTRA** | ≥20 GB | ≥128 GB | ≥32 | 70B + Mixtral | 8 | All features + Fish Speech |
| **HIGH** | ≥10 GB | ≥32 GB | ≥8 | llama3 | 4 | Full features |
| **MEDIUM** | ≥6 GB | ≥16 GB | — | llama3 | 2 | Standard |
| **LOW** | <6 GB | <16 GB | — | llama3 | 1 | Basic |

### Prerequisites

Before running setup, install:
- **Python 3.10+** → https://python.org
- **Ollama** → https://ollama.ai
- **Git** → https://git-scm.com
- **NVIDIA GPU drivers** (for CUDA) → https://nvidia.com/drivers

### Verify Setup

After setup, run anytime to check everything:
```
python scripts/verify_setup.py
```
```

- [ ] **Step 2: Add "Manual Setup" section**

Insert after the First Time Setup section. This is a step-by-step fallback for when the script doesn't work:

```markdown
### Manual Setup (if setup script fails)

<details>
<summary>Click to expand manual setup steps</summary>

1. **Create venv and install deps:**
   ```
   python -m venv venv
   venv\Scripts\activate  (Windows) or source venv/bin/activate (Linux/Mac)
   pip install -r server/requirements.txt
   pip install -r client/requirements.txt
   ```

2. **Download voice models:**
   Download `models-v2.1.zip` from [Releases](https://github.com/VillaKeth/Mario-Bathroom-AI/releases) and extract to project root.

3. **Install GPT-SoVITS:**
   ```
   git clone https://github.com/RVC-Boss/GPT-SoVITS.git gpt_sovits_repo
   cd gpt_sovits_repo
   powershell -ExecutionPolicy Bypass -File install.ps1  (Windows)
   # or: bash install.sh  (Linux/Mac)
   cd ..
   ```

4. **Pull Ollama models:**
   ```
   ollama pull llama3
   # ULTRA tier also needs:
   ollama pull llama3.1:70b-q4_k_m
   ollama pull mixtral:8x7b
   ```

5. **Create config.json:**
   ```
   copy config.example.json config.json  (Windows)
   # or: cp config.example.json config.json  (Linux/Mac)
   ```
   Edit `config.json` to set `birthday_person_name` and `birthday_person_facts`.

6. **Run verification:**
   ```
   python scripts/verify_setup.py
   ```

</details>
```

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: add first-time setup guide, hardware tiers, manual fallback"
```

---

### Task 7: Update `start_server.bat` with config check

**Files:**
- Modify: `start_server.bat`

Add a check at the top: if config.json doesn't exist, tell the user to run setup.bat first.

- [ ] **Step 1: Add config.json check to start_server.bat**

Insert after the Python check, before the dependency install:

```batch
REM Check config.json exists
if not exist "%~dp0config.json" (
    echo ERROR: config.json not found!
    echo Run setup.bat first, or copy config.example.json to config.json
    pause
    exit /b 1
)
```

- [ ] **Step 2: Test start_server.bat still works**

Run: `start_server.bat` (or dry-run the check)
Expected: Passes config check (config.json exists), continues normally.

- [ ] **Step 3: Commit**

```bash
git add start_server.bat
git commit -m "fix: add config.json existence check to start_server.bat"
```

---

### Task 8: Create GitHub Release + Upload Models

**Files:**
- No code files — this is a git/GitHub task

This task requires the `gh` CLI or manual GitHub web UI. The subagent should attempt `gh` first, fall back to instructions.

- [ ] **Step 1: Create models zip**

Run: `python scripts/package_models.py`
Expected: Creates `models-v2.1.zip` with all model files.

- [ ] **Step 2: Create GitHub Release v2.1**

Option A (if `gh` CLI available):
```bash
gh release create v2.1 --title "v2.1 — Friend-Ready Setup" --notes "Added one-click setup script, config template, verification script. Download models-v2.1.zip for voice models."
gh release upload v2.1 models-v2.1.zip
```

Option B (manual):
- Go to https://github.com/VillaKeth/Mario-Bathroom-AI/releases/new
- Tag: v2.1
- Title: "v2.1 — Friend-Ready Setup"
- Attach: models-v2.1.zip
- Publish

- [ ] **Step 3: Verify download URL works**

Run: `curl -sI https://github.com/VillaKeth/Mario-Bathroom-AI/releases/download/v2.1/models-v2.1.zip | findstr "HTTP"`
Expected: `HTTP/2 302` or `HTTP/1.1 302` (redirect to download)

- [ ] **Step 4: Clean up local zip**

Run: `del models-v2.1.zip` (don't commit the zip)

- [ ] **Step 5: Push all commits**

```bash
git push origin master
```

---

### Task 9: Full End-to-End Verification

**Depends on:** Tasks 1-8

This task validates the entire setup experience by simulating a fresh clone. Since we can't truly wipe the machine, we verify each component individually.

- [ ] **Step 1: Verify config.example.json is in git**

Run: `git ls-files config.example.json`
Expected: `config.example.json`

- [ ] **Step 2: Verify config.json is NOT in git**

Run: `git ls-files config.json`
Expected: (empty — gitignored)

- [ ] **Step 3: Run verify_setup.py**

Run: `python scripts/verify_setup.py`
Expected: All applicable checks pass.

- [ ] **Step 4: Run full test suite**

Run: `python -m pytest tests/test_memory_semantic.py tests/test_vip_knowledge.py tests/test_e2e_comprehensive.py tests/test_llm_router.py -v --tb=short`
Expected: 124+ tests pass, 0 failures.

- [ ] **Step 5: Verify README has setup section**

Run: `findstr "First Time Setup" README.md`
Expected: Match found.

- [ ] **Step 6: Verify setup.bat references correct GitHub Release URL**

Run: `findstr "models-v2.1.zip" setup.bat`
Expected: Download URL for v2.1 release.

- [ ] **Step 7: Update TODO.md**

Add completed items for this sprint.

- [ ] **Step 8: Final commit and push**

```bash
git add -A
git commit -m "chore: final verification pass for friend-ready setup"
git push
```
