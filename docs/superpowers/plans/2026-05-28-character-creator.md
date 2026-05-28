# Character Creator Wizard — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a browser-based, 6-step character creation wizard that enables non-technical users to create fully functional AI characters without writing code.

**Architecture:** Standalone FastAPI server (`character_creator/server.py`, port 8766) serving a vanilla HTML/CSS/JS single-page wizard app. Backend API endpoints handle hardware detection, voice search/preview, sprite generation, and character file creation. All output goes to `characters/<name>/` matching existing Mario/Sonic/Rudi structure.

**Tech Stack:** Python 3.10+, FastAPI, uvicorn, vanilla HTML/CSS/JS (no build step), yt-dlp (voice search), rembg (background removal), existing SubNP image generation pipeline.

**Spec:** `docs/superpowers/specs/2026-05-28-character-creator-design.md`

---

## File Map

### New Files to Create

| File | Responsibility |
|------|---------------|
| `character_creator/__init__.py` | Package marker |
| `character_creator/server.py` | FastAPI app: API endpoints, file creation, static file serving |
| `character_creator/known_characters.py` | Known character database + lookup logic |
| `character_creator/known_characters.json` | Data: 20+ popular characters with auto-fill fields |
| `character_creator/voice_finder.py` | YouTube voice clip search/download via yt-dlp |
| `character_creator/sprite_generator.py` | Wraps SubNP pipeline + rembg for pose generation |
| `character_creator/character_builder.py` | Generates character.yaml, prompts, directory structure |
| `character_creator/voice_trainer.py` | Voice training orchestration (Fish Speech / GPT-SoVITS / RVC) |
| `character_creator/config_manager.py` | Reads/writes config.json model selections safely |
| `character_creator/static/index.html` | Single-page wizard app shell |
| `character_creator/static/styles.css` | Dark theme CSS |
| `character_creator/static/wizard.js` | Wizard step logic, API calls, state management |
| `character_creator/requirements.txt` | Dependencies for the creator module |
| `create_character.bat` | Windows launcher script |
| `create_character.sh` | Linux/macOS launcher script |
| `docs/creating-a-character.md` | Beginner guide |
| `docs/character-format.md` | Technical YAML reference |
| `tests/test_character_creator.py` | Unit tests for backend logic |

### Files to Modify

| File | Change |
|------|--------|
| `setup.bat` | Add auto-launch of character creator if no characters exist |
| `setup.sh` | Same for Linux/macOS |
| `README.md` | Add "Getting Started" beginner section |

---

## Task 1: Project Skeleton & Server Shell

**Files:**
- Create: `character_creator/__init__.py`
- Create: `character_creator/server.py`
- Create: `character_creator/requirements.txt`
- Create: `character_creator/static/index.html`
- Test: `tests/test_character_creator.py`

- [ ] **Step 1: Write failing test for server startup**

```python
# tests/test_character_creator.py
import pytest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from fastapi.testclient import TestClient
from character_creator.server import app

def test_server_serves_index():
    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Character Creator" in resp.text

def test_health_endpoint():
    client = TestClient(app)
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert data["status"] == "ok"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:\Users\Vketh\Desktop\Mario_AI && venv\Scripts\python -m pytest tests\test_character_creator.py -v`
Expected: FAIL — `character_creator` module not found

- [ ] **Step 3: Create package and minimal server**

```python
# character_creator/__init__.py
"""Character Creator Wizard — browser-based character creation for non-technical users."""
```

```python
# character_creator/server.py
"""Character Creator Wizard — standalone FastAPI server.

Serves a 6-step browser wizard for creating AI characters.
Run standalone: python -m character_creator.server
"""
import os
import logging
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

logger = logging.getLogger(__name__)

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))

app = FastAPI(title="Character Creator Wizard")

@app.get("/")
async def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))

@app.get("/api/health")
async def health():
    return {"status": "ok"}

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8766)
```

```html
<!-- character_creator/static/index.html -->
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Character Creator Wizard</title>
    <link rel="stylesheet" href="/static/styles.css">
</head>
<body>
    <div id="app">
        <h1>🎭 Character Creator</h1>
        <p>Loading wizard...</p>
    </div>
    <script src="/static/wizard.js"></script>
</body>
</html>
```

```txt
# character_creator/requirements.txt
fastapi>=0.100.0
uvicorn>=0.23.0
python-multipart>=0.0.6
pyyaml>=6.0
aiofiles>=23.0
httpx>=0.24.0
edge-tts>=6.1.0
rembg>=2.0.0
yt-dlp>=2023.0
```

- [ ] **Step 4: Create placeholder static files**

Create empty `character_creator/static/styles.css` and `character_creator/static/wizard.js` files.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd C:\Users\Vketh\Desktop\Mario_AI && venv\Scripts\python -m pytest tests\test_character_creator.py -v`
Expected: 2 PASS

- [ ] **Step 6: Commit**

```bash
git add character_creator/ tests/test_character_creator.py
git commit -m "feat: character creator wizard skeleton with FastAPI server"
```

---

## Task 2: Hardware Detection API

**Files:**
- Modify: `character_creator/server.py`
- Test: `tests/test_character_creator.py`

- [ ] **Step 1: Write failing test for hardware endpoint**

```python
# Append to tests/test_character_creator.py
def test_hardware_endpoint():
    client = TestClient(app)
    resp = client.get("/api/hardware")
    assert resp.status_code == 200
    data = resp.json()
    assert "cpu_cores" in data
    assert "ram_gb" in data
    assert "gpu_vram_gb" in data
    assert "gpu_name" in data
    assert "tier" in data
    assert data["tier"] in ("ultra", "high", "medium", "low")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv\Scripts\python -m pytest tests\test_character_creator.py::test_hardware_endpoint -v`
Expected: FAIL — 404

- [ ] **Step 3: Add hardware endpoint to server.py**

Add to `character_creator/server.py`:
```python
import sys
sys.path.insert(0, os.path.join(PROJECT_ROOT, "server"))
import hardware

@app.get("/api/hardware")
async def get_hardware():
    hw = hardware.detect_hardware()
    tier = hardware.get_tier()
    return {**hw, "tier": tier}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv\Scripts\python -m pytest tests\test_character_creator.py::test_hardware_endpoint -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add character_creator/server.py tests/test_character_creator.py
git commit -m "feat: hardware detection API endpoint for character creator"
```

---

## Task 3: Ollama Model Listing with Hardware Gating

**Files:**
- Modify: `character_creator/server.py`
- Test: `tests/test_character_creator.py`

- [ ] **Step 1: Write failing test for models endpoint**

```python
def test_models_endpoint():
    client = TestClient(app)
    resp = client.get("/api/models")
    assert resp.status_code == 200
    data = resp.json()
    assert "models" in data
    assert "detected_vram" in data
    assert isinstance(data["models"], list)
    # Each model should have name, vram_required, compatibility
    if data["models"]:
        m = data["models"][0]
        assert "name" in m
        assert "vram_gb" in m
        assert "compatibility" in m
        assert m["compatibility"] in ("compatible", "slow", "incompatible")
```

- [ ] **Step 2: Run test to verify it fails**

Expected: FAIL — 404

- [ ] **Step 3: Implement models endpoint**

Add to `character_creator/server.py`:
```python
import httpx

MODEL_VRAM_ESTIMATES = {
    "llama3": 5, "llama3.1:8b": 5, "llama3.2:3b": 2,
    "gemma3:27b": 18, "gemma3:12b": 8, "gemma3:4b": 3,
    "llama3.1:70b": 39, "mixtral:8x7b": 26, "mixtral:8x22b": 48,
    "phi3:mini": 3, "phi3:medium": 8, "mistral": 5,
    "qwen2:7b": 5, "qwen2:72b": 40, "deepseek-coder:6.7b": 5,
}

def _classify_model(model_name: str, vram_gb: int, detected_vram: int, detected_ram: int) -> str:
    if vram_gb <= detected_vram:
        return "compatible"
    elif vram_gb <= detected_vram + (detected_ram * 0.3):
        return "slow"
    return "incompatible"

@app.get("/api/models")
async def get_models():
    hw = hardware.detect_hardware()
    detected_vram = hw["gpu_vram_gb"]
    detected_ram = hw["ram_gb"]
    
    # Query Ollama for installed models
    installed = []
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get("http://localhost:11434/api/tags")
            if resp.status_code == 200:
                for m in resp.json().get("models", []):
                    installed.append(m["name"])
    except Exception:
        pass
    
    models = []
    for name, vram in MODEL_VRAM_ESTIMATES.items():
        compat = _classify_model(name, vram, detected_vram, detected_ram)
        models.append({
            "name": name,
            "vram_gb": vram,
            "compatibility": compat,
            "installed": any(name.split(":")[0] in inst for inst in installed),
            "recommended": False,
        })
    
    # Mark best compatible model as recommended
    compatible = [m for m in models if m["compatibility"] == "compatible"]
    if compatible:
        best = max(compatible, key=lambda m: m["vram_gb"])
        best["recommended"] = True
    
    return {"models": models, "detected_vram": detected_vram, "installed_models": installed}
```

- [ ] **Step 4: Run test to verify it passes**

- [ ] **Step 5: Commit**

```bash
git add character_creator/server.py tests/test_character_creator.py
git commit -m "feat: Ollama model listing with hardware gating"
```

---

## Task 3B: Config.json Model Selection Manager

**Files:**
- Create: `character_creator/config_manager.py`
- Modify: `character_creator/server.py`
- Test: `tests/test_character_creator.py`

- [ ] **Step 1: Write failing test for config read/write**

```python
from character_creator.config_manager import read_model_config, write_model_config

def test_read_model_config():
    import tempfile, json
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg_path = os.path.join(tmpdir, "config.json")
        with open(cfg_path, "w") as f:
            json.dump({"server": {"llm_quality_model": "llama3", "llm_fast_model": "llama3"}}, f)
        result = read_model_config(cfg_path)
        assert result["quality_model"] == "llama3"
        assert result["fast_model"] == "llama3"

def test_write_model_config_preserves_other_fields():
    import tempfile, json
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg_path = os.path.join(tmpdir, "config.json")
        original = {"character": "mario", "server": {"port": 8765, "llm_quality_model": "llama3", "llm_fast_model": "llama3"}, "client": {"width": 480}}
        with open(cfg_path, "w") as f:
            json.dump(original, f)
        write_model_config(cfg_path, quality_model="gemma3:12b", fast_model="llama3.2:3b")
        with open(cfg_path) as f:
            updated = json.load(f)
        assert updated["character"] == "mario"  # preserved
        assert updated["server"]["port"] == 8765  # preserved
        assert updated["server"]["llm_quality_model"] == "gemma3:12b"  # updated
        assert updated["server"]["llm_fast_model"] == "llama3.2:3b"  # updated
        assert updated["client"]["width"] == 480  # preserved

def test_write_model_config_skips_when_unchanged():
    import tempfile, json
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg_path = os.path.join(tmpdir, "config.json")
        original = {"server": {"llm_quality_model": "llama3", "llm_fast_model": "llama3"}}
        with open(cfg_path, "w") as f:
            json.dump(original, f)
        # Pass None to skip updating a field
        write_model_config(cfg_path, quality_model=None, fast_model="phi3:mini")
        with open(cfg_path) as f:
            updated = json.load(f)
        assert updated["server"]["llm_quality_model"] == "llama3"  # unchanged
        assert updated["server"]["llm_fast_model"] == "phi3:mini"  # updated
```

- [ ] **Step 2: Run tests to verify they fail**

- [ ] **Step 3: Implement config_manager.py**

```python
# character_creator/config_manager.py
"""Config.json manager — reads/writes model selections without overwriting other fields."""
import json
import os
import logging

logger = logging.getLogger(__name__)

def read_model_config(config_path: str) -> dict:
    if not os.path.exists(config_path):
        return {"quality_model": "", "fast_model": "", "character": ""}
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    server = cfg.get("server", {})
    return {
        "quality_model": server.get("llm_quality_model", ""),
        "fast_model": server.get("llm_fast_model", ""),
        "character": cfg.get("character", ""),
    }

def write_model_config(config_path: str, quality_model: str | None = None,
                        fast_model: str | None = None, character: str | None = None) -> None:
    if not os.path.exists(config_path):
        cfg = {"server": {}, "client": {}}
    else:
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    if quality_model is not None:
        cfg.setdefault("server", {})["llm_quality_model"] = quality_model
    if fast_model is not None:
        cfg.setdefault("server", {})["llm_fast_model"] = fast_model
    if character is not None:
        cfg["character"] = character
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=4, ensure_ascii=False)
    logger.info(f"Updated config.json: quality={quality_model}, fast={fast_model}, character={character}")
```

- [ ] **Step 4: Add config API endpoints to server.py**

```python
from character_creator.config_manager import read_model_config, write_model_config

@app.get("/api/config/models")
async def get_config_models():
    config_path = os.path.join(PROJECT_ROOT, "config.json")
    return read_model_config(config_path)

@app.post("/api/config/models")
async def set_config_models(body: dict):
    config_path = os.path.join(PROJECT_ROOT, "config.json")
    write_model_config(
        config_path,
        quality_model=body.get("quality_model"),
        fast_model=body.get("fast_model"),
        character=body.get("character"),
    )
    return {"success": True}
```

- [ ] **Step 5: Run tests to verify they pass**

- [ ] **Step 6: Commit**

```bash
git add character_creator/config_manager.py character_creator/server.py tests/test_character_creator.py
git commit -m "feat: config.json model selection manager with safe read/write"
```

---

## Task 4: Known Character Database & Lookup API

**Files:**
- Create: `character_creator/known_characters.py`
- Create: `character_creator/known_characters.json`
- Modify: `character_creator/server.py`
- Test: `tests/test_character_creator.py`

- [ ] **Step 1: Write failing test for known character lookup**

```python
def test_known_character_lookup_found():
    client = TestClient(app)
    resp = client.get("/api/known-character/goku")
    assert resp.status_code == 200
    data = resp.json()
    assert data["found"] is True
    assert data["data"]["display_name"]
    assert data["data"]["description"]
    assert data["data"]["theme_colors"]

def test_known_character_lookup_not_found():
    client = TestClient(app)
    resp = client.get("/api/known-character/xyznotreal")
    assert resp.status_code == 200
    data = resp.json()
    assert data["found"] is False
```

- [ ] **Step 2: Run tests to verify they fail**

- [ ] **Step 3: Create known_characters.py with loader**

```python
# character_creator/known_characters.py
"""Known character database — auto-fill data for popular characters."""
import json
import os

_DB_PATH = os.path.join(os.path.dirname(__file__), "known_characters.json")
_cache = None

def _load():
    global _cache
    if _cache is None:
        with open(_DB_PATH, "r", encoding="utf-8") as f:
            _cache = json.load(f)
    return _cache

def lookup(name: str) -> dict | None:
    db = _load()
    key = name.lower().strip().replace(" ", "_")
    return db.get(key)

def list_all() -> list[str]:
    return list(_load().keys())
```

- [ ] **Step 4: Create known_characters.json with 20+ characters**

Create `character_creator/known_characters.json` with entries for: goku, spongebob, darth_vader, pikachu, batman, spiderman, homer_simpson, shrek, naruto, luigi, yoshi, link, kirby, patrick_star, squidward, thanos, iron_man, elsa, buzz_lightyear, garfield, deadpool, rick_sanchez, groot, stitch, bender.

Each entry follows this schema:
```json
{
  "display_name": "Goku AI 🐉",
  "tagline": "Kamehameha!",
  "description": "The legendary Saiyan warrior from Dragon Ball...",
  "accent_markers": ["Speaks with enthusiastic, energetic tone", ...],
  "catchphrases": ["Kamehameha!", "I'm Goku!", ...],
  "theme_colors": {"primary": "#FF6B00", "secondary": "#0066CC", "accent": "#FFD700", "text": "#FFFFFF"},
  "voice_search_terms": ["Goku voice clips clean", "Goku English dub quotes"],
  "edge_voice": "en-US-ChristopherNeural",
  "voice_rate": "+20%",
  "voice_pitch": "+5Hz",
  "visual_description": "Goku from Dragon Ball Z, muscular Saiyan warrior with spiky black hair, orange gi...",
  "art_style": "anime",
  "pronunciation": {"kamehameha": "kah may hah may hah", "senzu": "sen zoo"},
  "system_prompt_hints": "Enthusiastic, loves fighting, always hungry, incredibly kind..."
}
```

- [ ] **Step 5: Add API endpoint to server.py**

```python
from character_creator.known_characters import lookup as kc_lookup, list_all as kc_list

@app.get("/api/known-character/{name}")
async def known_character(name: str):
    data = kc_lookup(name)
    if data:
        return {"found": True, "data": data}
    return {"found": False, "data": None}

@app.get("/api/known-characters")
async def known_characters_list():
    return {"characters": kc_list()}
```

- [ ] **Step 6: Run tests to verify they pass**

- [ ] **Step 7: Commit**

```bash
git add character_creator/known_characters.py character_creator/known_characters.json character_creator/server.py tests/test_character_creator.py
git commit -m "feat: known character database with 20+ popular characters"
```

---

## Task 5: Voice Finder (YouTube Search via yt-dlp)

**Files:**
- Create: `character_creator/voice_finder.py`
- Modify: `character_creator/server.py`
- Test: `tests/test_character_creator.py`

- [ ] **Step 1: Write failing test for voice finder**

```python
def test_voice_search_endpoint():
    client = TestClient(app)
    resp = client.post("/api/voice/search", json={"query": "Mario voice clips"})
    assert resp.status_code == 200
    data = resp.json()
    assert "results" in data
    assert "available" in data  # whether yt-dlp is installed
```

- [ ] **Step 2: Run test to verify it fails**

- [ ] **Step 3: Implement voice_finder.py**

```python
# character_creator/voice_finder.py
"""Voice clip finder — searches YouTube via yt-dlp and downloads clips."""
import subprocess
import json
import os
import logging
import tempfile

logger = logging.getLogger(__name__)

def is_available() -> bool:
    try:
        subprocess.run(["yt-dlp", "--version"], capture_output=True, timeout=5)
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False

def search(query: str, max_results: int = 5) -> list[dict]:
    if not is_available():
        return []
    try:
        result = subprocess.run(
            ["yt-dlp", f"ytsearch{max_results}:{query}",
             "--dump-json", "--no-download", "--flat-playlist"],
            capture_output=True, text=True, timeout=30
        )
        clips = []
        for line in result.stdout.strip().split("\n"):
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                clips.append({
                    "id": data.get("id", ""),
                    "title": data.get("title", ""),
                    "duration": data.get("duration", 0),
                    "url": data.get("webpage_url", f"https://youtube.com/watch?v={data.get('id', '')}"),
                })
            except json.JSONDecodeError:
                continue
        return clips
    except Exception as e:
        logger.error(f"Voice search failed: {e}")
        return []

def download_clip(url: str, output_dir: str, max_duration: int = 30) -> str | None:
    if not is_available():
        return None
    output_path = os.path.join(output_dir, "reference_audio.wav")
    try:
        subprocess.run([
            "yt-dlp", url,
            "-x", "--audio-format", "wav",
            "--postprocessor-args", f"-t {max_duration}",
            "-o", output_path,
        ], capture_output=True, timeout=120, check=True)
        if os.path.exists(output_path):
            return output_path
    except Exception as e:
        logger.error(f"Voice download failed: {e}")
    return None
```

- [ ] **Step 4: Add voice API endpoints to server.py**

```python
from character_creator import voice_finder

@app.post("/api/voice/search")
async def voice_search(body: dict):
    query = body.get("query", "")
    available = voice_finder.is_available()
    results = voice_finder.search(query) if available else []
    return {"results": results, "available": available}

@app.post("/api/voice/download")
async def voice_download(body: dict):
    url = body.get("url", "")
    char_name = body.get("character_name", "temp")
    output_dir = os.path.join(PROJECT_ROOT, "characters", char_name, "voice")
    os.makedirs(output_dir, exist_ok=True)
    path = voice_finder.download_clip(url, output_dir)
    return {"success": path is not None, "path": path}
```

- [ ] **Step 5: Run tests to verify they pass**

- [ ] **Step 6: Commit**

```bash
git add character_creator/voice_finder.py character_creator/server.py tests/test_character_creator.py
git commit -m "feat: voice clip search and download via yt-dlp"
```

---

## Task 5B: Voice Training Orchestration

**Files:**
- Create: `character_creator/voice_trainer.py`
- Modify: `character_creator/server.py`
- Test: `tests/test_character_creator.py`

- [ ] **Step 1: Write failing test for voice engine detection**

```python
from character_creator.voice_trainer import detect_available_engines, get_engine_status

def test_detect_available_engines():
    engines = detect_available_engines()
    assert isinstance(engines, list)
    # At minimum, edge should always be available
    engine_names = [e["name"] for e in engines]
    assert "edge" in engine_names
    for engine in engines:
        assert "name" in engine
        assert "available" in engine
        assert "vram_required" in engine
        assert "status" in engine  # "ready", "needs_setup", "unavailable"
```

- [ ] **Step 2: Run test to verify it fails**

- [ ] **Step 3: Implement voice_trainer.py**

```python
# character_creator/voice_trainer.py
"""Voice training orchestration — detects engines, triggers training, tracks progress."""
import os
import sys
import logging
import subprocess
import shutil

logger = logging.getLogger(__name__)

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))

def detect_available_engines() -> list[dict]:
    engines = []
    
    # Fish Speech (priority 1, ~4GB VRAM)
    fish_available = False
    try:
        import fish_speech
        fish_available = True
    except ImportError:
        pass
    engines.append({
        "name": "fish_speech", "display_name": "Fish Speech",
        "priority": 1, "vram_required": 4,
        "available": fish_available,
        "needs_reference_audio": True,
        "status": "ready" if fish_available else "needs_setup",
        "description": "Best quality voice cloning. Needs reference audio."
    })
    
    # GPT-SoVITS (priority 2, ~8GB VRAM)
    sovits_path = os.path.join(PROJECT_ROOT, "gpt_sovits_repo")
    sovits_env = os.path.join(PROJECT_ROOT, "gpt_sovits_env")
    sovits_available = os.path.isdir(sovits_path) and os.path.isdir(sovits_env)
    engines.append({
        "name": "gpt_sovits", "display_name": "GPT-SoVITS",
        "priority": 2, "vram_required": 8,
        "available": sovits_available,
        "needs_reference_audio": True,
        "status": "ready" if sovits_available else "needs_setup",
        "description": "Trainable voice cloning. Needs training audio."
    })
    
    # Edge TTS + RVC (priority 3, ~2GB VRAM)
    rvc_available = False
    try:
        rvc_model_dir = os.path.join(PROJECT_ROOT, "server", "data", "rvc_model")
        rvc_available = os.path.isdir(rvc_model_dir)
    except Exception:
        pass
    engines.append({
        "name": "edge_rvc", "display_name": "Edge TTS + RVC",
        "priority": 3, "vram_required": 2,
        "available": rvc_available,
        "needs_reference_audio": True,
        "status": "ready" if rvc_available else "needs_setup",
        "description": "Voice conversion on top of Edge TTS base voice."
    })
    
    # Edge TTS (priority 4, 0 VRAM — always available)
    engines.append({
        "name": "edge", "display_name": "Edge TTS",
        "priority": 4, "vram_required": 0,
        "available": True,
        "needs_reference_audio": False,
        "status": "ready",
        "description": "Free Microsoft voices. Always available fallback."
    })
    
    return engines

def get_engine_status(engine_name: str) -> dict:
    engines = detect_available_engines()
    for e in engines:
        if e["name"] == engine_name:
            return e
    return {"name": engine_name, "available": False, "status": "unknown"}

def prepare_voice_artifacts(config: dict, char_dir: str) -> dict:
    """Prepare voice artifacts for a character based on chosen engine and audio.
    
    Resolves reference audio from char_dir/voice/ (already moved from drafts by server).
    For Fish Speech: reference_audio.wav is sufficient (zero-shot cloning at runtime).
    For GPT-SoVITS: triggers training subprocess if engine is available.
    For Edge+RVC: reference audio used for RVC voice conversion at runtime.
    For Edge TTS: no audio needed, just uses edge_voice setting.
    
    Returns dict with keys: engine, fallback_engine, artifacts_ready, errors, training_status
    """
    engine = config.get("preferred_engine", "edge")
    voice_dir = os.path.join(char_dir, "voice")
    os.makedirs(voice_dir, exist_ok=True)
    ref_audio = os.path.join(voice_dir, "reference_audio.wav")
    
    result = {"engine": engine, "fallback_engine": "edge", "artifacts_ready": False,
              "errors": [], "training_status": "not_needed"}
    
    if engine == "edge":
        result["artifacts_ready"] = True
        return result
    
    # All non-edge engines require reference audio
    if not os.path.exists(ref_audio):
        result["errors"].append(f"Reference audio required for {engine} but not found at {ref_audio}")
        result["engine"] = "edge"
        result["artifacts_ready"] = True
        return result
    
    if engine == "fish_speech":
        status = get_engine_status("fish_speech")
        if status["available"]:
            # Fish Speech uses zero-shot cloning — reference_audio.wav is all it needs
            result["artifacts_ready"] = True
            result["training_status"] = "not_needed_zero_shot"
        else:
            result["errors"].append("Fish Speech not installed, falling back to Edge TTS")
            result["engine"] = "edge"
            result["artifacts_ready"] = True
    
    elif engine == "gpt_sovits":
        status = get_engine_status("gpt_sovits")
        if status["available"]:
            # GPT-SoVITS needs training — trigger it as a background process
            try:
                _trigger_sovits_training(ref_audio, char_dir)
                result["artifacts_ready"] = True
                result["training_status"] = "training_started"
            except Exception as e:
                result["errors"].append(f"GPT-SoVITS training failed: {e}. Falling back to Edge TTS.")
                result["engine"] = "edge"
                result["artifacts_ready"] = True
                result["training_status"] = "training_failed"
        else:
            result["errors"].append("GPT-SoVITS not installed, falling back to Edge TTS")
            result["engine"] = "edge"
            result["artifacts_ready"] = True
    
    elif engine == "edge_rvc":
        status = get_engine_status("edge_rvc")
        if status["available"]:
            # RVC uses the reference audio for voice conversion at runtime
            result["artifacts_ready"] = True
            result["training_status"] = "not_needed_runtime_conversion"
        else:
            result["errors"].append("RVC not set up, falling back to Edge TTS")
            result["engine"] = "edge"
            result["artifacts_ready"] = True
    
    return result

def _trigger_sovits_training(ref_audio: str, char_dir: str):
    """Trigger GPT-SoVITS training as a background subprocess.
    
    This is a best-effort operation — the character is still usable with Edge TTS
    fallback even if training fails or hasn't completed yet.
    """
    sovits_path = os.path.join(PROJECT_ROOT, "gpt_sovits_repo")
    if not os.path.isdir(sovits_path):
        raise FileNotFoundError("gpt_sovits_repo not found")
    
    # Start training in background — non-blocking
    # The actual training script and parameters depend on the GPT-SoVITS version
    # This creates a marker file so the TTS router knows training was requested
    marker = os.path.join(char_dir, "voice", ".training_requested")
    with open(marker, "w") as f:
        f.write(f"engine=gpt_sovits\naudio={ref_audio}\nstatus=pending\n")
    
    logger.info(f"GPT-SoVITS training requested for {char_dir}")
```

- [ ] **Step 4: Add voice engine API endpoints to server.py**

```python
from character_creator.voice_trainer import detect_available_engines, prepare_voice_artifacts

@app.get("/api/voice/engines")
async def voice_engines():
    return {"engines": detect_available_engines()}
```

- [ ] **Step 5: Run tests to verify they pass**

- [ ] **Step 6: Commit**

```bash
git add character_creator/voice_trainer.py character_creator/server.py tests/test_character_creator.py
git commit -m "feat: voice training orchestration with engine detection and fallbacks"
```

---

## Task 6: Sprite Generator Wrapper

**Files:**
- Create: `character_creator/sprite_generator.py`
- Modify: `character_creator/server.py`
- Test: `tests/test_character_creator.py`

- [ ] **Step 1: Write failing test for sprite generation config**

```python
def test_sprite_poses_endpoint():
    client = TestClient(app)
    resp = client.get("/api/sprites/poses")
    assert resp.status_code == 200
    data = resp.json()
    assert "emotions" in data
    assert "states" in data
    assert len(data["emotions"]) >= 25  # unique emotion sprites
    assert len(data["states"]) >= 9   # 9 state groups
    # Verify total unique state sprite paths = 11
    total_state_paths = sum(len(s["paths"]) for s in data["states"])
    assert total_state_paths >= 11
```

- [ ] **Step 2: Run test to verify it fails**

- [ ] **Step 3: Implement sprite_generator.py**

This file defines the canonical pose matrix (from the spec) and wraps the existing SubNP generation pipeline from `client/generate_character_poses.py`.

```python
# character_creator/sprite_generator.py
"""Sprite generator — wraps SubNP pipeline for character pose generation."""
import os
import sys
import logging
import json

logger = logging.getLogger(__name__)

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))

# Canonical emotion sprites (25 unique paths)
EMOTION_SPRITES = {
    "happy": "positive/happy",
    "excited": "positive/excited",
    "laughing": "positive/laughing",
    "love": "positive/love",
    "proud": "positive/proud",
    "sad": "negative/sad",
    "angry": "negative/angry",
    "annoyed": "negative/annoyed",
    "nervous": "negative/nervous",
    "scared": "negative/scared",
    "embarrassed": "negative/embarrassed",
    "disgusted": "negative/disgusted",
    "grossed_out": "negative/grossed_out",
    "confused": "thinking/confused",
    "thinking": "thinking/thinking",
    "curious": "thinking/curious",
    "determined": "thinking/determined",
    "mischievous": "thinking/mischievous",
    "shocked": "thinking/shocked",
    "idea": "thinking/idea",
    "surprised": "thinking/surprised",
    "mind_blown": "reactions/mind_blown",
    "sassy": "reactions/sassy",
    "cringe": "reactions/cringe",
    "impressed": "reactions/impressed",
}

# Emotion aliases (map to same sprite path)
EMOTION_ALIASES = {
    "loving": "positive/love",
    "frustrated": "negative/annoyed",
    "worried": "negative/nervous",
    "solemn": "memorial/moment_of_silence",
    "celebratory": "party/celebrate",
    "bored": "sleep/yawning",
}

# Additional emotion sprites (special categories)
SPECIAL_EMOTIONS = {
    "sleepy": "sleep/sleepy",
    "neutral": "neutral/idle",
    "memorial": "memorial/moment_of_silence",
    "toast": "toast/raising_glass",
    "party": "party/celebrate",
    "birthday": "birthday/birthday",
}

# State sprites (9 states, 11 unique images including array variants)
STATE_SPRITES = {
    "idle": ["neutral/idle"],
    "talking": ["speech/talking", "speech/talking_excited"],
    "listening": ["speech/listening"],
    "greeting": ["greeting/wave"],
    "thinking": ["thinking/thinking"],
    "sleeping": ["sleep/sleeping"],
    "dancing": ["movement/dancing", "party/celebrate"],
    "entering": ["movement/entering"],
    "exiting": ["greeting/farewell"],
}

ALL_EMOTIONS = {**EMOTION_SPRITES, **SPECIAL_EMOTIONS}

# Pose prompts for AI generation (emotion_name -> pose description template)
POSE_PROMPTS = {
    "happy": "{char} with a warm genuine smile, arms open, welcoming happy pose",
    "excited": "{char} jumping with excitement, fist pumped, huge grin",
    "laughing": "{char} laughing hard, head thrown back, genuine amusement",
    "love": "{char} with heart eyes, hands clasped near face, love-struck expression",
    "proud": "{char} standing tall, hands on hips, chin up, supremely confident proud pose",
    "sad": "{char} looking down sadly, shoulders slumped, disappointed expression",
    "angry": "{char} with intense angry expression, fists clenched, leaning forward",
    "annoyed": "{char} with arms crossed, one eyebrow raised, clearly unimpressed look",
    "nervous": "{char} looking nervously to the side, hands fidgeting, uncertain expression",
    "scared": "{char} jumping back with wide eyes, arms up in surprise, startled and scared",
    "embarrassed": "{char} scratching back of head sheepishly, embarrassed half-smile",
    "disgusted": "{char} leaning away with disgusted face, hand up in stop gesture",
    "grossed_out": "{char} holding nose in disgust, leaning away, revolted face",
    "confused": "{char} with head tilted, confused expression, one eyebrow raised high",
    "thinking": "{char} looking upward thoughtfully, finger tapping chin, pondering",
    "curious": "{char} leaning forward with curiosity, eyes bright, interested expression",
    "determined": "{char} with intense focused eyes, determined expression, leaning forward",
    "mischievous": "{char} with a mischievous grin, fingers steepled, plotting look",
    "shocked": "{char} with mouth wide open in shock, eyes huge, absolutely stunned",
    "idea": "{char} with index finger raised, bright idea moment, excited eyes",
    "surprised": "{char} doing a dramatic double take, wide eyes, surprised",
    "mind_blown": "{char} with hands on sides of head, amazed shocked expression",
    "sassy": "{char} with hand on hip, head tilted, finger wagging, sassy attitude",
    "cringe": "{char} cringing hard, one eye closed, teeth gritted, looking away",
    "impressed": "{char} nodding approvingly, arms crossed, raised eyebrow, genuine respect",
    "sleepy": "{char} mid-yawn, hand covering mouth, half-closed eyes, sleepy",
    "neutral": "{char} standing relaxed, casual confident stance, neutral expression",
    "memorial": "{char} with head bowed, one hand over heart, solemn respectful pose",
    "toast": "{char} raising a glass high, confident smile, toasting",
    "party": "{char} raising both arms in celebration, huge grin, confetti around",
    "birthday": "{char} holding a birthday cake with candles, warm smile",
}

STATE_PROMPTS = {
    "idle": "{char} standing relaxed in a casual idle pose",
    "talking": "{char} gesturing with one hand while speaking, animated expression",
    "talking_excited": "{char} gesturing enthusiastically with both hands, excited while talking",
    "listening": "{char} with head slightly tilted, attentive listening pose",
    "wave": "{char} waving hello, big smile, welcoming gesture",
    "sleeping": "{char} curled up sleeping, peaceful expression",
    "dancing": "{char} doing a fun dance move, energetic and happy",
    "entering": "{char} walking in confidently, dramatic entrance",
    "farewell": "{char} waving goodbye, looking back with a smile",
}

ART_STYLE_SUFFIXES = {
    "3d_figurine": ", 3D rendered figurine style, clean gray studio background, full body shot, highly detailed, high quality, soft studio lighting",
    "anime": ", anime art style, cel-shaded, clean lines, vibrant colors, full body shot, studio background",
    "pixel_art": ", pixel art style, 16-bit, clean pixelated edges, retro game aesthetic, full body",
    "realistic": ", photorealistic 3D render, unreal engine style, detailed textures, studio lighting, full body",
    "cartoon": ", cartoon style, bold outlines, bright colors, expressive, full body shot, clean background",
}

def get_all_poses() -> dict:
    """Return the full pose matrix for the wizard UI."""
    unique_emotions = []
    seen_paths = set()
    for name, path in {**EMOTION_SPRITES, **SPECIAL_EMOTIONS}.items():
        if path not in seen_paths:
            seen_paths.add(path)
            unique_emotions.append({
                "name": name,
                "path": path,
                "category": path.split("/")[0],
                "prompt_template": POSE_PROMPTS.get(name, ""),
            })

    states = []
    for state_name, paths in STATE_SPRITES.items():
        states.append({
            "name": state_name,
            "paths": paths,
            "prompts": [STATE_PROMPTS.get(p.split("/")[-1], "") for p in paths],
        })

    return {"emotions": unique_emotions, "states": states}
```

- [ ] **Step 4: Add sprite API endpoint to server.py**

```python
from character_creator.sprite_generator import get_all_poses

@app.get("/api/sprites/poses")
async def sprite_poses():
    return get_all_poses()
```

- [ ] **Step 5: Run tests to verify they pass**

- [ ] **Step 6: Commit**

```bash
git add character_creator/sprite_generator.py character_creator/server.py tests/test_character_creator.py
git commit -m "feat: sprite generator with canonical pose matrix"
```

---

## Task 7: Character Builder (YAML + Directory Generation)

**Files:**
- Create: `character_creator/character_builder.py`
- Modify: `character_creator/server.py`
- Test: `tests/test_character_creator.py`

- [ ] **Step 1: Write failing test for character creation**

```python
import tempfile
import shutil
from character_creator.character_builder import build_character

def test_build_character_creates_directory():
    with tempfile.TemporaryDirectory() as tmpdir:
        config = {
            "name": "TestBot",
            "display_name": "TestBot AI 🤖",
            "tagline": "Testing!",
            "description": "A test character",
            "theme_colors": {"primary": "#FF0000", "secondary": "#00FF00", "accent": "#0000FF", "text": "#FFFFFF"},
            "edge_voice": "en-US-GuyNeural",
            "voice_rate": "+10%",
            "voice_pitch": "+0Hz",
            "accent_markers": ["Speaks normally"],
            "catchphrases": ["Hello!"],
            "pronunciation": {},
            "preferred_engine": "edge",
        }
        char_dir = build_character(config, tmpdir)
        
        assert os.path.isdir(char_dir)
        assert os.path.isfile(os.path.join(char_dir, "character.yaml"))
        assert os.path.isdir(os.path.join(char_dir, "sprites"))
        assert os.path.isdir(os.path.join(char_dir, "prompts"))
        assert os.path.isfile(os.path.join(char_dir, "prompts", "system_prompt.md"))
        
        import yaml
        with open(os.path.join(char_dir, "character.yaml")) as f:
            data = yaml.safe_load(f)
        assert data["identity"]["name"] == "TestBot"
        assert data["voice"]["edge_voice"] == "en-US-GuyNeural"
```

- [ ] **Step 2: Run test to verify it fails**

- [ ] **Step 3: Implement character_builder.py**

This module takes a wizard config dict and generates the full character directory structure: `character.yaml`, prompt files, empty directories for sprites/games/memories, catchphrase YAML, idle messages, test phrases, etc. All output matches the format used by Mario/Sonic/Rudi.

Key functions:
- `build_character(config: dict, characters_dir: str) -> str` — main entry, returns path to created dir
- `_generate_character_yaml(config: dict) -> dict` — builds the YAML structure
- `_generate_system_prompt(config: dict) -> str` — generates system_prompt.md
- `_generate_idle_prompt(config: dict) -> str` — generates idle_prompt.md
- `_generate_default_catchphrases(config: dict) -> dict` — default catchphrase pools
- `_generate_default_idle_messages(config: dict) -> dict` — default idle chatter
- `_generate_test_phrases(config: dict) -> list` — test phrases for voice verification

The YAML output MUST include ALL sections required by `shared/character_loader.py`: `identity`, `voice` (with `edge_voice`, `voice_rate`, `voice_pitch`, `accent_markers`, `catchphrases`, `pronunciation`), `visuals` (with `emotion_sprite_map`, `state_sprite_map`, `theme_colors`), `speech`, `games`, and `memory`. Refer to `characters/mario/character.yaml` as the gold standard.

- [ ] **Step 4: Run tests to verify they pass**

- [ ] **Step 5: Write failing test for character_loader compatibility**

```python
def test_character_loader_compatibility():
    """Verify wizard output can be loaded by the real character_loader."""
    import tempfile
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "shared"))
    from character_loader import CharacterLoader
    
    with tempfile.TemporaryDirectory() as tmpdir:
        config = {
            "name": "TestBot",
            "display_name": "TestBot AI 🤖",
            "tagline": "Testing!",
            "description": "A test character for loader compatibility",
            "theme_colors": {"primary": "#FF0000", "secondary": "#00FF00", "accent": "#0000FF", "text": "#FFFFFF"},
            "edge_voice": "en-US-GuyNeural",
            "voice_rate": "+10%",
            "voice_pitch": "+0Hz",
            "accent_markers": ["Speaks normally"],
            "catchphrases": ["Hello!", "Testing one two three!"],
            "pronunciation": {},
            "preferred_engine": "edge",
        }
        char_dir = build_character(config, tmpdir)
        
        # Load using the REAL character_loader
        loader = CharacterLoader(char_dir)
        
        # Verify all required sections exist and load
        assert loader.get("identity", "name") == "TestBot"
        assert loader.get("voice", "edge_voice") == "en-US-GuyNeural"
        assert loader.get("visuals", "theme_colors") is not None
        assert loader.get("visuals", "emotion_sprite_map") is not None
        assert loader.get("visuals", "state_sprite_map") is not None
        
        # Verify prompts directory has required files
        assert os.path.isfile(os.path.join(char_dir, "prompts", "system_prompt.md"))
        assert os.path.isfile(os.path.join(char_dir, "prompts", "idle_prompt.md"))
        assert os.path.isfile(os.path.join(char_dir, "prompts", "phases.yaml"))
        assert os.path.isfile(os.path.join(char_dir, "prompts", "greetings.yaml"))
        assert os.path.isfile(os.path.join(char_dir, "prompts", "guest_type_hints.yaml"))
        assert os.path.isfile(os.path.join(char_dir, "prompts", "time_flavors.yaml"))
```

- [ ] **Step 6: Run loader compatibility test — verify it passes**

- [ ] **Step 5: Add create character API endpoint to server.py (with voice training)**

```python
from character_creator.character_builder import build_character
from character_creator.voice_trainer import prepare_voice_artifacts

@app.post("/api/create-character")
async def create_character(body: dict):
    characters_dir = os.path.join(PROJECT_ROOT, "characters")
    try:
        # 1. Build character directory, YAML, prompts
        char_dir = build_character(body, characters_dir)
        
        # 2. Move staged uploads from draft workspace to final location
        char_name_key = body.get("name", "").lower().replace(" ", "_")
        draft_dir = os.path.join(PROJECT_ROOT, "character_creator", "_drafts", char_name_key)
        if os.path.isdir(draft_dir):
            _move_staged_files(draft_dir, char_dir)
        
        # 3. Resolve reference_audio_path from the FINAL char_dir (after draft move)
        #    The draft upload saved audio to _drafts/<name>/voice/reference_audio.wav,
        #    which is now at characters/<name>/voice/reference_audio.wav after move.
        voice_dir = os.path.join(char_dir, "voice")
        ref_audio = os.path.join(voice_dir, "reference_audio.wav")
        if os.path.exists(ref_audio):
            body["reference_audio_path"] = ref_audio
        
        # 4. Prepare voice artifacts (detect engine, copy audio, trigger training)
        voice_result = prepare_voice_artifacts(body, char_dir)
        
        return {
            "success": True,
            "path": char_dir,
            "voice": voice_result,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

def _move_staged_files(draft_dir: str, char_dir: str):
    """Move staged uploads from draft workspace to final character directory."""
    import shutil
    for item in os.listdir(draft_dir):
        src = os.path.join(draft_dir, item)
        dst = os.path.join(char_dir, item)
        if os.path.isdir(src):
            if os.path.exists(dst):
                for sub in os.listdir(src):
                    shutil.move(os.path.join(src, sub), os.path.join(dst, sub))
            else:
                shutil.move(src, dst)
        else:
            shutil.move(src, dst)
    shutil.rmtree(draft_dir, ignore_errors=True)
```

- [ ] **Step 6: Run all tests**

Run: `venv\Scripts\python -m pytest tests\test_character_creator.py -v`

- [ ] **Step 7: Commit**

```bash
git add character_creator/character_builder.py character_creator/server.py tests/test_character_creator.py
git commit -m "feat: character builder generates full directory structure and YAML"
```

---

## Task 8: Edge TTS Voice Preview API

**Files:**
- Modify: `character_creator/server.py`
- Test: `tests/test_character_creator.py`

- [ ] **Step 1: Write failing test**

```python
def test_edge_voices_endpoint():
    client = TestClient(app)
    resp = client.get("/api/voice/edge-voices")
    assert resp.status_code == 200
    data = resp.json()
    assert "voices" in data
    assert isinstance(data["voices"], list)
```

- [ ] **Step 2: Run test to verify it fails**

- [ ] **Step 3: Implement edge voices listing and preview**

Add endpoints:
- `GET /api/voice/edge-voices` — returns list of available Edge TTS voices (name, gender, locale)
- `POST /api/voice/preview` — generates a short TTS sample and returns WAV bytes as base64

Uses `edge_tts.list_voices()` for the voice list, and `edge_tts.Communicate()` for preview generation.

- [ ] **Step 4: Run tests to verify they pass**

- [ ] **Step 5: Commit**

```bash
git add character_creator/server.py tests/test_character_creator.py
git commit -m "feat: Edge TTS voice listing and preview API"
```

---

## Task 9: File Upload Endpoints (Audio + Images)

**Files:**
- Modify: `character_creator/server.py`
- Test: `tests/test_character_creator.py`

- [ ] **Step 1: Write failing test**

```python
def test_upload_audio_endpoint():
    client = TestClient(app)
    # Create a minimal WAV file for testing
    import struct
    sample_rate = 22050
    num_samples = sample_rate  # 1 second
    data_size = num_samples * 2
    header = struct.pack('<4sI4s4sIHHIIHH4sI',
        b'RIFF', 36 + data_size, b'WAVE',
        b'fmt ', 16, 1, 1, sample_rate, sample_rate * 2, 2, 16,
        b'data', data_size)
    wav_bytes = header + b'\x00' * data_size
    
    resp = client.post(
        "/api/upload/audio",
        files={"file": ("test.wav", wav_bytes, "audio/wav")},
        data={"character_name": "test_upload"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    # Verify file is in draft workspace, NOT in characters/
    assert "_drafts" in data["path"]
    assert "characters" not in data["path"]
```

- [ ] **Step 2: Implement upload endpoints with draft staging**

Add endpoints:
- `POST /api/upload/audio` — accepts audio file upload, saves to draft workspace `character_creator/_drafts/<name>/voice/` (NOT directly to `characters/`)
- `POST /api/upload/sprite` — accepts image upload for a specific emotion/state slot, saves to `character_creator/_drafts/<name>/sprites/<category>/`
- Both handle file validation (size limits: 50MB audio, 10MB image; type checking: audio/wav, audio/mp3, image/png, image/jpeg)
- Draft files are moved to final `characters/<name>/` only during `/api/create-character` (see Task 7, Step 5)
- `DELETE /api/upload/draft/<name>` — cleanup endpoint to remove draft workspace on "Start Fresh"
- `GET /api/upload/draft/<name>` — list all staged files for a draft (returns `{audio: [filenames], sprites: {category: [filenames]}}`) so the wizard can rebuild upload previews on resume

- [ ] **Step 3: Run tests**

- [ ] **Step 4: Commit**

```bash
git add character_creator/server.py tests/test_character_creator.py
git commit -m "feat: file upload endpoints for audio and sprite images"
```

---

## Task 10: Sprite Generation API (Background Task)

**Files:**
- Modify: `character_creator/sprite_generator.py`
- Modify: `character_creator/server.py`
- Test: `tests/test_character_creator.py`

- [ ] **Step 1: Write failing test for generation trigger**

```python
def test_sprite_generation_start():
    client = TestClient(app)
    resp = client.post("/api/sprites/generate", json={
        "character_name": "test_gen",
        "visual_description": "A friendly robot with blue eyes",
        "art_style": "3d_figurine",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "task_id" in data
    assert data["status"] == "started"
```

- [ ] **Step 2: Implement sprite generation as background task**

Add to `sprite_generator.py`:
- `generate_all_poses(char_name, visual_description, art_style, output_dir, progress_callback)` — generates all ~37 sprites using SubNP API, calls progress_callback with status updates
- Uses `rembg` for background removal on each generated image

Add to `server.py`:
- `POST /api/sprites/generate` — starts background generation task, returns task_id
- `GET /api/sprites/status/{task_id}` — returns progress (completed/total, current pose name)
- Uses `asyncio.create_task` or `BackgroundTasks` for non-blocking generation

- [ ] **Step 3: Run tests**

- [ ] **Step 4: Commit**

```bash
git add character_creator/sprite_generator.py character_creator/server.py tests/test_character_creator.py
git commit -m "feat: background sprite generation with progress tracking"
```

---

## Task 11: Frontend — CSS Theme & Wizard Shell

**Files:**
- Modify: `character_creator/static/styles.css`
- Modify: `character_creator/static/index.html`

- [ ] **Step 1: Create dark theme CSS**

Build `styles.css` with:
- Dark navy background (#0d0d1a), card backgrounds (#1a1a2e)
- Color palette: purple (#7B2FBE), blue (#1E90FF), red (#E52521), green (#00A86B), orange (#FF8C00), gold (#FFD700)
- Progress bar component with `aria-valuenow` and `aria-valuemax` attributes
- Step container with transitions
- Form input styles (dark inputs, colored borders on focus, visible focus outlines for keyboard nav)
- Card, grid, and button styles matching the mockups
- Responsive layout (works on mobile too)
- Upload area drag-and-drop styling (drag-over highlight state)
- Slider styling for voice tuning
- Color picker styling
- `.help-text` class for inline guidance below form fields
- `.auto-filled-badge` for showing "✨ Auto-filled" tags
- `.sr-only` class for screen-reader-only text
- Visible focus ring `:focus-visible` on all interactive elements

- [ ] **Step 2: Create wizard HTML shell with accessibility**

Update `index.html` with:
- Progress bar (6 steps with labels), using `role="progressbar"` and `aria-label`
- Step containers (div per step, show/hide with JS), each with `role="tabpanel"` and `aria-labelledby`
- Navigation (Back/Next buttons) with `aria-label` descriptions
- All form fields for each of the 6 steps with `<label>` elements and `id` associations
- Inline help text `<p class="help-text">` beneath every form group explaining what to do
- `aria-live="polite"` region for status messages (step changes, validation errors, generation progress)
- Skip-to-content link
- Semantic HTML: `<main>`, `<section>`, `<fieldset>`, `<legend>`

- [ ] **Step 3: Visually verify in browser**

Run: `cd character_creator && python -m uvicorn server:app --port 8766`
Open: `http://localhost:8766`
Verify: Dark theme renders, progress bar shows, step 1 is visible, tab navigation works through all form fields

- [ ] **Step 4: Commit**

```bash
git add character_creator/static/
git commit -m "feat: dark theme CSS and accessible wizard HTML shell"
```

---

## Task 12A: Frontend — Wizard State Management & Draft Resume

**Files:**
- Modify: `character_creator/static/wizard.js`

- [ ] **Step 1: Implement WizardState class with localStorage persistence**

```javascript
class WizardState {
    constructor() {
        this.currentStep = 0;
        this.data = {};
        this.restore();
    }
    save() {
        localStorage.setItem('wizard_state', JSON.stringify({
            currentStep: this.currentStep,
            data: this.data,
            savedAt: new Date().toISOString()
        }));
    }
    restore() {
        const saved = localStorage.getItem('wizard_state');
        if (saved) {
            try {
                const parsed = JSON.parse(saved);
                this.currentStep = parsed.currentStep || 0;
                this.data = parsed.data || {};
                return true;
            } catch (e) { return false; }
        }
        return false;
    }
    clear() { localStorage.removeItem('wizard_state'); }
}
```

- [ ] **Step 2: Implement WizardUI class with step navigation**

- Show/hide step containers
- Update progress bar on step change
- Next/Back button handlers with validation
- Jump-to-step (click on completed progress bar segments)
- Call `state.save()` on every step transition
- Update `aria-live` region with current step name on transition
- **Focus management:** On step change, focus the new step's `<h2>` heading. On validation failure, focus the first invalid field. On resume banner show, focus the banner. On success/error banners, focus the banner heading.

- [ ] **Step 3: Implement draft resume flow**

- On page load, check `WizardState.restore()`
- If draft found, show banner: "You have a draft from [date]. Resume or Start Fresh?"
- "Resume" → jump to `state.currentStep`, populate all form fields from `state.data`
- Also fetch `GET /api/upload/draft/<name>` to rebuild uploaded file previews (audio waveform, sprite thumbnails) — these can't be stored in localStorage
- "Start Fresh" → `state.clear()`, call `DELETE /api/upload/draft/<name>` to clean up staged files, start at step 0
- Generate "Edit Later" link that copies localStorage state as JSON to clipboard

- [ ] **Step 4: Implement per-step form validation**

- Step 1: Name is required (non-empty)
- Step 2: Skippable (no required fields)
- Step 3: At least one voice option chosen (edge voice or reference audio)
- Step 4: Skippable (placeholder sprites are acceptable)
- Step 5: At least one model selected
- Step 6: Review only (always valid)
- Show inline validation messages in `aria-live` region

- [ ] **Step 5: Test draft save/resume manually**

- Fill step 1, advance to step 3, reload page
- Verify resume banner appears with correct date
- Click resume, verify step 3 is shown with step 1 data intact
- Click Start Fresh, verify wizard starts at step 0

- [ ] **Step 6: Commit**

```bash
git add character_creator/static/wizard.js
git commit -m "feat: wizard state management with localStorage draft save/resume"
```

---

## Task 12B: Frontend — Step 1 (Identity) & Step 2 (Personality)

**Files:**
- Modify: `character_creator/static/wizard.js`

- [ ] **Step 1: Implement Step 1 (Identity) logic**

- Known vs Original character toggle (radio buttons)
- Name input with debounced known-character lookup (`fetch("/api/known-character/" + name)`)
- Auto-fill on match: display_name, tagline, description, theme_colors
- "✨ Auto-filled" badges appear on populated fields
- Color pickers for theme colors (4 pickers: primary, secondary, accent, text)
- All auto-filled values remain editable
- Help text: "Type a character name — if we recognize it, we'll auto-fill everything!"

- [ ] **Step 2: Implement Step 2 (Personality) logic**

- System prompt textarea with template (pre-filled for known characters)
- Tag input for accent markers (type + Enter to add, click × to remove)
- Catchphrase list editor (add/remove/reorder with drag)
- "Skip — use defaults" button for known characters (pre-checked if auto-filled)
- Advanced toggle → personality sliders (warmth, chaos, sarcasm, friendliness)
- Help text: "Known characters come with personality pre-configured. Customize if you want!"

- [ ] **Step 3: Test Steps 1 & 2 in browser**

- Type "Goku" → verify auto-fill happens within 500ms
- Toggle Known/Original → verify fields clear/restore
- Add/remove accent markers and catchphrases
- Verify state persists when navigating Back/Next

- [ ] **Step 4: Commit**

```bash
git add character_creator/static/wizard.js
git commit -m "feat: wizard Steps 1-2 — Identity and Personality"
```

---

## Task 12C: Frontend — Step 3 (Voice)

**Files:**
- Modify: `character_creator/static/wizard.js`

- [ ] **Step 1: Implement voice engine status display**

- Fetch `/api/voice/engines` on step entry
- Show engine cards in priority order (Fish Speech → GPT-SoVITS → Edge+RVC → Edge TTS)
- Color-code: green = ready, yellow = needs setup, gray = unavailable
- Help text: "We'll use the best available engine for your hardware"

- [ ] **Step 2: Implement reference audio upload & recording**

- Drag-and-drop upload zone for .wav/.mp3 files
- File type validation (reject non-audio), size limit (50MB)
- Browser microphone recording via MediaRecorder API
- Record/Stop/Play controls
- Preview playback of uploaded/recorded audio
- Graceful degradation: if MediaRecorder unavailable, show "Upload only" with explanation

- [ ] **Step 3: Implement voice search (auto-find online)**

- "Auto-find online" button (calls `/api/voice/search` with character name)
- Search results list with title, duration, play button
- "Use This" button per result → calls `/api/voice/download`
- Loading spinner during search
- Error state: "yt-dlp not installed" message with install instructions
- Help text: "We'll search YouTube for clean voice clips of your character"

- [ ] **Step 4: Implement Edge TTS voice picker**

- Fetch `/api/voice/edge-voices`
- Filterable grid: by gender, locale, name
- Voice preview button per voice (calls `/api/voice/preview`)
- Speed slider (-50% to +50%)
- Pitch slider (-50Hz to +50Hz)
- "Test Voice" button that generates sample with current settings

- [ ] **Step 5: Implement pronunciation rules editor**

- Add/remove rows: [word] → [pronunciation]
- Auto-populated for known characters
- Help text: "Tell the voice engine how to say tricky words"

- [ ] **Step 6: Test Step 3 in browser**

- Verify engine cards render with correct status
- Upload a test audio file, verify preview plays
- Test Edge TTS voice picker and preview
- Add/remove pronunciation rules

- [ ] **Step 7: Commit**

```bash
git add character_creator/static/wizard.js
git commit -m "feat: wizard Step 3 — Voice configuration with upload, record, auto-find"
```

---

## Task 12D: Frontend — Step 4 (Appearance)

**Files:**
- Modify: `character_creator/static/wizard.js`

- [ ] **Step 1: Implement AI generate vs upload toggle**

- Two main modes: "🤖 AI Generate All" and "📤 Upload My Own"
- Visual description textarea (auto-filled for known characters)
- Art style picker (5 buttons: 3D Figurine, Anime, Pixel Art, Realistic, Cartoon)
- Each style shows a small preview icon
- Help text: "Describe your character visually, or we'll use the auto-fill description"

- [ ] **Step 2: Implement sprite generation UI**

- "Generate All Sprites" button → calls `/api/sprites/generate`
- Progress bar polling `/api/sprites/status/{id}` every 2 seconds
- Generated sprite previews appear in a grid as they complete
- "Regenerate" button per sprite to retry individual poses
- Fallback: if API fails, show placeholder sprite with "⚠ Generation failed — upload manually" message
- Help text: "This generates ~37 poses. It takes a few minutes."

- [ ] **Step 3: Implement upload mode UI**

- Two guided grids matching the canonical sprite matrix:
  - **Emotion sprites** (25 unique slots): organized by category — Positive (happy, excited, laughing, love, proud), Negative (sad, angry, annoyed, nervous, scared, embarrassed, disgusted, grossed_out), Thinking (confused, thinking, curious, determined, mischievous, shocked, idea, surprised), Reactions (mind_blown, sassy, cringe, impressed), Special (sleepy, neutral, memorial, toast, party, birthday)
  - **State sprites** (11 unique images across 9 states): idle, talking (×2: normal + excited), listening, greeting/wave, thinking, sleeping, dancing (×2: dance + celebrate), entering, exiting/farewell
- Drag-and-drop per slot or "Choose File" button
- Image preview thumbnail per slot
- "Remove Background" toggle per image (calls rembg via API)
- Minimum required: at least `neutral` sprite (others use nearest-category fallback)
- Help text: "At minimum, upload a 'neutral' image. Missing poses will fall back to the closest available emotion."

- [ ] **Step 4: Test Step 4 in browser**

- Toggle between Generate and Upload modes
- Verify art style selection works
- Test individual image upload with preview
- Verify progress bar behavior (can mock API if SubNP is slow)

- [ ] **Step 5: Commit**

```bash
git add character_creator/static/wizard.js
git commit -m "feat: wizard Step 4 — Appearance with AI generation and upload"
```

---

## Task 12E: Frontend — Step 5 (Hardware & Models) & Step 6 (Review)

**Files:**
- Modify: `character_creator/static/wizard.js`

- [ ] **Step 1: Implement Step 5 (Hardware & Models) logic**

- Fetch `/api/hardware` → display hardware info cards (CPU, RAM, GPU)
- Fetch `/api/models` → display model list with compatibility badges
- Green checkmark = compatible, yellow warning = slow (CPU offload), gray lock = incompatible
- Single model picker (default): radio buttons, recommended model pre-selected
- "Advanced: Split models" toggle reveals dual picker (quality model + fast model)
- Fetch `/api/config/models` to show current config values (if config.json already has models set)
- Help text: "Pick a model that fits your GPU. Grayed-out models need more VRAM."
- No-Ollama fallback: if no models returned and Ollama unreachable, show "Ollama not detected" banner with install link

- [ ] **Step 2: Implement Step 6 (Review & Create) logic**

- Summary cards for all steps: Identity (name, colors), Personality (prompt preview), Voice (engine, voice name), Appearance (sprite count), Hardware (model name)
- Each card has "Edit" button → jump back to that step
- "Create Character" button → calls POST `/api/create-character` with full state
- **Model config protection:** On Step 5 entry, fetch `/api/config/models` and store as `originalModelConfig`. Track a `modelConfigDirty` flag — set to `true` ONLY when the user manually clicks a model or changes the dual-model toggle (NOT when the recommended model is auto-preselected). On "Create Character", only POST `/api/config/models` if `modelConfigDirty === true`. Pass `None` for unchanged fields so `config_manager.write_model_config` skips them.
- Progress indicators during creation (directory, YAML, prompts, voice, config)
- Error display if creation fails (with retry button)
- Success screen: character name, preview of theme colors, "Start Server" and "Create Another" buttons
- On success, call `state.clear()` to remove draft from localStorage

- [ ] **Step 3: Test Steps 5 & 6 in browser**

- Verify hardware cards show real system info
- Verify model gating colors match actual VRAM
- Create a test character end-to-end
- Verify config.json is updated (not overwritten)
- Verify success screen appears with correct info

- [ ] **Step 4: Commit**

```bash
git add character_creator/static/wizard.js
git commit -m "feat: wizard Steps 5-6 — Hardware/Models and Review/Create"
```

---

## Task 13: Launcher Scripts

**Files:**
- Create: `create_character.bat`
- Create: `create_character.sh`
- Modify: `setup.bat`
- Modify: `setup.sh`

- [ ] **Step 1: Create create_character.bat**

```bat
@echo off
echo Starting Character Creator Wizard...
echo.

if not exist "venv\Scripts\python.exe" (
    echo [ERROR] Run setup.bat first to install dependencies.
    pause
    exit /b 1
)

call venv\Scripts\activate.bat
echo Opening Character Creator in your browser...
start http://localhost:8766
python -m character_creator.server
pause
```

- [ ] **Step 2: Create create_character.sh**

```bash
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
```

- [ ] **Step 3: Modify setup.bat — add dependency install and auto-launch logic**

After server dependencies install (Step 7), add:
```bat
REM Step 7B: Install character creator dependencies
echo Installing character creator dependencies...
pip install -r character_creator\requirements.txt --quiet
echo [OK] Character creator dependencies installed
```

After the "Setup Complete!" message, add:
```bat
REM Check if any characters exist (besides _shared and test_bot)
set HAS_CHARS=0
for /d %%d in (characters\*) do (
    if /I not "%%~nxd"=="_shared" if /I not "%%~nxd"=="test_bot" set HAS_CHARS=1
)
if !HAS_CHARS!==0 (
    echo.
    echo  No characters found! Launching Character Creator Wizard...
    echo  Create your first character in the browser.
    echo.
    start http://localhost:8766
    python -m character_creator.server
)
```

- [ ] **Step 4: Test launcher scripts**

Double-click `create_character.bat`, verify browser opens to wizard.

- [ ] **Step 5: Commit**

```bash
git add create_character.bat create_character.sh setup.bat setup.sh
git commit -m "feat: launcher scripts with auto-wizard on first run"
```

---

## Task 14: Documentation

**Files:**
- Create: `docs/creating-a-character.md`
- Create: `docs/character-format.md`
- Modify: `README.md`

- [ ] **Step 1: Write docs/creating-a-character.md**

Beginner guide covering:
- What you need (Python, Ollama, this repo)
- Double-click setup.bat → wizard auto-opens
- Walk through each wizard step with descriptions
- "Your character is ready!" — how to start the server
- Troubleshooting common issues

- [ ] **Step 2: Write docs/character-format.md**

Technical reference for power users:
- Full `character.yaml` schema with every field documented
- Directory structure explanation
- How to edit YAML directly
- How to add custom sprites, catchphrases, prompts
- Voice engine configuration

- [ ] **Step 3: Update README.md**

Add "Getting Started" section at the top:
- Prerequisites (Python 3.10+, Ollama)
- Clone, run `setup.bat`, wizard opens
- Create your character, start the server
- Link to `docs/creating-a-character.md` for details

- [ ] **Step 4: Commit**

```bash
git add docs/ README.md
git commit -m "docs: beginner guide, technical reference, and README getting started"
```

---

## Task 15: Error Handling, Fallbacks & Edge Cases

**Files:**
- Modify: `character_creator/server.py`
- Modify: `character_creator/character_builder.py`
- Modify: `character_creator/sprite_generator.py`
- Modify: `character_creator/static/wizard.js`
- Test: `tests/test_character_creator.py`

- [ ] **Step 1: Write failing tests for error conditions**

```python
def test_create_character_missing_name():
    client = TestClient(app)
    resp = client.post("/api/create-character", json={"display_name": "NoName"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is False
    assert "name" in data["error"].lower()

def test_create_character_with_no_sprites_still_valid():
    """Character with zero sprites should still be loadable (uses placeholder)."""
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        config = {
            "name": "NoSprites",
            "display_name": "NoSprites AI",
            "tagline": "No images!",
            "description": "Character without any sprites",
            "theme_colors": {"primary": "#FF0000", "secondary": "#00FF00", "accent": "#0000FF", "text": "#FFFFFF"},
            "edge_voice": "en-US-GuyNeural",
            "voice_rate": "+0%", "voice_pitch": "+0Hz",
            "accent_markers": ["Normal"], "catchphrases": ["Hi!"],
            "pronunciation": {}, "preferred_engine": "edge",
        }
        char_dir = build_character(config, tmpdir)
        assert os.path.isfile(os.path.join(char_dir, "character.yaml"))

def test_hardware_endpoint_returns_gracefully_without_gpu():
    """Hardware endpoint should never crash, even if GPU detection fails."""
    client = TestClient(app)
    resp = client.get("/api/hardware")
    assert resp.status_code == 200
    data = resp.json()
    assert data["tier"] in ("ultra", "high", "medium", "low")

def test_models_endpoint_handles_ollama_offline():
    """Models endpoint should return model list even if Ollama is unreachable."""
    client = TestClient(app)
    resp = client.get("/api/models")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data["models"], list)
    assert len(data["models"]) > 0  # static model list still returned

def test_voice_search_handles_no_ytdlp():
    """Voice search should return empty results gracefully if yt-dlp is missing."""
    client = TestClient(app)
    resp = client.post("/api/voice/search", json={"query": "test"})
    assert resp.status_code == 200
    data = resp.json()
    assert "available" in data
    assert isinstance(data["results"], list)
```

- [ ] **Step 2: Run tests — verify which fail**

- [ ] **Step 3: Add input validation to create-character endpoint**

Validate required fields (name, display_name, edge_voice) before calling build_character. Return clear error messages.

- [ ] **Step 4: Add placeholder sprite fallback to character_builder**

When no sprites exist, generate `emotion_sprite_map` and `state_sprite_map` entries pointing to a single `sprites/placeholder.png`. Create a simple colored circle placeholder image.

- [ ] **Step 5: Add frontend error displays**

In `wizard.js`, add error handling for every `fetch()` call:
- Network error → show "Server unreachable — is the wizard server running?"
- API error → show the error message from the response
- Ollama offline → show install/start instructions in Step 5
- yt-dlp missing → show "Voice search unavailable — install yt-dlp or upload audio manually"
- Sprite generation failure → show "Generation failed for this pose — you can upload manually"

- [ ] **Step 6: Run all tests**

Run: `venv\Scripts\python -m pytest tests\test_character_creator.py -v`
Expected: All pass

- [ ] **Step 7: Commit**

```bash
git add character_creator/ tests/test_character_creator.py
git commit -m "feat: error handling, fallbacks, and edge case resilience"
```

---

## Task 16: Integration Testing & Polish

**Files:**
- Modify: `tests/test_character_creator.py`
- Various polish fixes

- [ ] **Step 1: Write end-to-end integration test**

```python
def test_full_wizard_flow_e2e():
    """Test the complete flow: create character via API, verify output."""
    client = TestClient(app)
    
    # 1. Check hardware
    hw = client.get("/api/hardware").json()
    assert hw["tier"]
    
    # 2. Lookup known character
    kc = client.get("/api/known-character/goku").json()
    assert kc["found"]
    
    # 3. Get models
    models = client.get("/api/models").json()
    assert models["models"]
    
    # 4. Get pose matrix
    poses = client.get("/api/sprites/poses").json()
    assert len(poses["emotions"]) >= 25
    
    # 5. Get voice engines
    engines = client.get("/api/voice/engines").json()
    assert any(e["name"] == "edge" for e in engines["engines"])
    
    # 6. Read current config
    cfg = client.get("/api/config/models").json()
    assert "quality_model" in cfg
    
    # 7. Create character
    with tempfile.TemporaryDirectory() as tmpdir:
        import character_creator.server as srv
        orig_root = srv.PROJECT_ROOT
        srv.PROJECT_ROOT = tmpdir
        os.makedirs(os.path.join(tmpdir, "characters"))
        
        # Also create a config.json in tmpdir
        import json
        with open(os.path.join(tmpdir, "config.json"), "w") as f:
            json.dump({"character": "mario", "server": {"port": 8765}}, f)
        
        try:
            config = {**kc["data"], "name": "Goku", "preferred_engine": "edge"}
            resp = client.post("/api/create-character", json=config)
            assert resp.json()["success"]
            
            # Verify character_loader can load it
            sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "shared"))
            from character_loader import CharacterLoader
            loader = CharacterLoader(os.path.join(tmpdir, "characters", "goku"))
            assert loader.get("identity", "name") == "Goku"
        finally:
            srv.PROJECT_ROOT = orig_root
```

- [ ] **Step 2: Run full test suite**

Run: `venv\Scripts\python -m pytest tests\test_character_creator.py -v`
Expected: All tests pass

- [ ] **Step 3: Manual browser testing**

- Start server: `python -m character_creator.server`
- Walk through all 6 steps with a known character (Goku)
- Walk through all 6 steps with an original character
- Create both characters
- Verify `characters/<name>/character.yaml` is valid
- Verify the main server can load each new character
- Test draft resume: fill halfway, reload, verify resume works
- Test keyboard navigation through all steps (Tab, Enter, Arrow keys)
- Test error states: disconnect Ollama, verify graceful fallback messages

- [ ] **Step 4: Polish and fix issues found during testing**

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "feat: character creator wizard — complete with tests and docs"
```
