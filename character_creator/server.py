"""Character Creator Wizard — standalone FastAPI server.

Serves a 6-step browser wizard for creating AI characters.
Run standalone: python -m character_creator.server
"""
import os
import sys
import json
import logging
import httpx
import edge_tts
import base64
import shutil
import asyncio
import uuid
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Add server directory to path to import hardware module
PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "server"))
import hardware
from character_creator.known_characters import lookup as kc_lookup, list_all as kc_list

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

@app.get("/api/hardware")
async def get_hardware_info():
    hw = hardware.detect_hardware()
    tier = hardware.get_tier()
    return {**hw, "tier": tier}

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
    
    compatible = [m for m in models if m["compatibility"] == "compatible"]
    if compatible:
        best = max(compatible, key=lambda m: m["vram_gb"])
        best["recommended"] = True
    
    return {"models": models, "detected_vram": detected_vram, "installed_models": installed}

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

@app.post("/api/server/launch")
async def launch_game_server():
    """Launch the game server (start.bat) as a detached process."""
    import subprocess
    start_bat = os.path.join(PROJECT_ROOT, "start.bat")
    if not os.path.exists(start_bat):
        return {"success": False, "error": "start.bat not found"}
    try:
        subprocess.Popen(
            [start_bat],
            cwd=PROJECT_ROOT,
            creationflags=subprocess.CREATE_NEW_CONSOLE | subprocess.DETACHED_PROCESS,
            shell=True
        )
        return {"success": True, "message": "Game server launching in new window..."}
    except Exception as e:
        return {"success": False, "error": str(e)}

from character_creator.sprite_generator import get_all_poses
from character_creator.voice_trainer import detect_available_engines, prepare_voice_artifacts

@app.post("/api/voice/search")
async def voice_search(body: dict):
    """Search YouTube for character voice clips (default, no coding needed)."""
    from character_creator import voice_finder
    query = body.get("query", "").strip()
    if not query:
        return {"results": [], "available": voice_finder.is_available(),
                "reason": "Empty query"}
    if not voice_finder.is_available():
        return {"results": [], "available": False,
                "reason": "yt-dlp not installed. Run setup.bat, or upload a clip instead."}
    results = await asyncio.to_thread(voice_finder.search, query, body.get("max_results", 6))
    return {"results": results, "available": True}

@app.post("/api/voice/download")
async def voice_download(body: dict):
    """Download a chosen YouTube clip as the character's reference audio."""
    from character_creator import voice_finder
    url = body.get("url", "").strip()
    char_name = body.get("character_name", "").lower().replace(" ", "_")
    if not url or not char_name:
        return {"success": False, "error": "Missing url or character_name"}
    draft_voice = os.path.join(os.path.dirname(__file__), "_drafts", char_name, "voice")
    path = await asyncio.to_thread(voice_finder.download_clip, url, draft_voice,
                                   body.get("max_duration", 25))
    if not path:
        return {"success": False, "error": "Download failed (clip unavailable or yt-dlp error)"}
    return {"success": True, "path": path}

@app.get("/api/sprites/poses")
async def sprite_poses():
    return get_all_poses()

@app.get("/api/voice/engines")
async def voice_engines():
    return {"engines": detect_available_engines()}

@app.get("/api/voice/edge-voices")
async def edge_voices():
    try:
        voices = await edge_tts.list_voices()
        simplified = []
        for v in voices:
            simplified.append({
                "name": v["ShortName"],
                "display_name": v["FriendlyName"],
                "gender": v["Gender"],
                "locale": v["Locale"],
            })
        return {"voices": simplified}
    except Exception as e:
        logger.error(f"Failed to list Edge voices: {e}")
        return {"voices": [], "error": str(e)}

@app.post("/api/voice/preview")
async def voice_preview(body: dict):
    voice_name = body.get("voice", "en-US-GuyNeural")
    text = body.get("text", "Hello! I am your new AI character. Nice to meet you!")
    rate = body.get("rate", "+0%")
    pitch = body.get("pitch", "+0Hz")
    try:
        communicate = edge_tts.Communicate(text, voice_name, rate=rate, pitch=pitch)
        audio_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data += chunk["data"]
        audio_b64 = base64.b64encode(audio_data).decode("utf-8")
        return {"success": True, "audio_base64": audio_b64, "format": "mp3"}
    except Exception as e:
        logger.error(f"Voice preview failed: {e}")
        return {"success": False, "error": str(e)}

@app.post("/api/upload/audio")
async def upload_audio(file: UploadFile = File(...), character_name: str = Form(...)):
    draft_dir = os.path.join(os.path.dirname(__file__), "_drafts", character_name.lower().replace(" ", "_"), "voice")
    os.makedirs(draft_dir, exist_ok=True)
    file_path = os.path.join(draft_dir, "reference_audio.wav")
    with open(file_path, "wb") as f:
        content = await file.read()
        if len(content) > 50 * 1024 * 1024:  # 50MB limit
            return {"success": False, "error": "File too large (max 50MB)"}
        f.write(content)
    return {"success": True, "path": file_path}

@app.post("/api/upload/sprite")
async def upload_sprite(file: UploadFile = File(...), character_name: str = Form(...), 
                         category: str = Form(...), emotion: str = Form(...)):
    draft_dir = os.path.join(os.path.dirname(__file__), "_drafts", character_name.lower().replace(" ", "_"), "sprites", category)
    os.makedirs(draft_dir, exist_ok=True)
    ext = os.path.splitext(file.filename)[1] or ".png"
    file_path = os.path.join(draft_dir, f"{emotion}{ext}")
    with open(file_path, "wb") as f:
        content = await file.read()
        if len(content) > 10 * 1024 * 1024:  # 10MB limit
            return {"success": False, "error": "File too large (max 10MB)"}
        f.write(content)
    return {"success": True, "path": file_path}

@app.delete("/api/upload/draft/{name}")
async def delete_draft(name: str):
    draft_dir = os.path.join(os.path.dirname(__file__), "_drafts", name.lower().replace(" ", "_"))
    if os.path.isdir(draft_dir):
        shutil.rmtree(draft_dir)
        return {"success": True, "deleted": True}
    return {"success": True, "deleted": False}

@app.get("/api/upload/draft/{name}")
async def list_draft(name: str):
    draft_dir = os.path.join(os.path.dirname(__file__), "_drafts", name.lower().replace(" ", "_"))
    result = {"audio": [], "sprites": {}}
    if not os.path.isdir(draft_dir):
        return result
    voice_dir = os.path.join(draft_dir, "voice")
    if os.path.isdir(voice_dir):
        result["audio"] = os.listdir(voice_dir)
    sprites_dir = os.path.join(draft_dir, "sprites")
    if os.path.isdir(sprites_dir):
        for cat in os.listdir(sprites_dir):
            cat_path = os.path.join(sprites_dir, cat)
            if os.path.isdir(cat_path):
                result["sprites"][cat] = os.listdir(cat_path)
    return result

@app.post("/api/sprites/generate")
async def start_sprite_generation(body: dict):
    from character_creator.sprite_generator import generate_all_poses, expected_sprite_count
    task_id = str(uuid.uuid4())[:8]
    char_name = body.get("character_name", "unknown")
    visual_desc = body.get("visual_description", "")
    art_style = body.get("art_style", "3d_figurine")
    output_dir = os.path.join(os.path.dirname(__file__), "_drafts", char_name, "sprites")
    os.makedirs(output_dir, exist_ok=True)
    
    asyncio.create_task(generate_all_poses(task_id, char_name, visual_desc, art_style, output_dir))
    
    return {"task_id": task_id, "status": "started", "total_poses": expected_sprite_count()}

@app.get("/api/sprites/status/{task_id}")
async def sprite_generation_status(task_id: str):
    from character_creator.sprite_generator import get_task_status
    return get_task_status(task_id)

from character_creator.character_builder import build_character
from character_creator.content_generator import generate_all_content, get_llm_backend
from fastapi.responses import StreamingResponse

# ─── Content Generation (SSE) ─────────────────────────────────────────────────

@app.get("/api/content/backend")
async def content_backend_info():
    """Return which LLM backend will be used for content generation.

    Includes a reachability probe: an unreachable Ollama silently yields EMPTY
    content pools, so the wizard must warn the user up front.
    """
    backend = get_llm_backend()
    reachable = True
    if backend["type"] == "ollama":
        try:
            import httpx
            async with httpx.AsyncClient(timeout=3) as client:
                r = await client.get(f"{backend['url'].rstrip('/')}/api/tags")
                reachable = r.status_code == 200
        except Exception:
            reachable = False
    return {"type": backend["type"], "model": backend["model"], "reachable": reachable}


@app.post("/api/content/generate")
async def generate_content_sse(body: dict):
    """Generate content pools via SSE streaming.
    
    Body: {
        character_name: str,
        description: str, 
        personality: str,
        char_dir: str,       # Path to character directory (returned by create-character)
        categories: ["idle", "games", "extras"]  # Optional, defaults to all
    }
    """
    char_name = body.get("character_name", "")
    description = body.get("description", "")
    personality = body.get("personality", "")
    char_dir = body.get("char_dir", "")
    categories = body.get("categories", None)
    
    if not char_dir or not os.path.isdir(char_dir):
        return {"success": False, "error": "Invalid character directory"}
    
    async def event_stream():
        async for event in generate_all_content(
            name=char_name,
            description=description,
            personality=personality,
            char_dir=char_dir,
            categories=categories,
        ):
            yield f"data: {json.dumps(event)}\n\n"
    
    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/api/content/regenerate-pool")
async def regenerate_single_pool(body: dict):
    """Regenerate a single content pool."""
    from character_creator.content_generator import (
        generate_pool, IDLE_POOL_SPECS, GAME_POOL_SPECS, EXTRAS_POOL_SPECS
    )
    
    char_name = body.get("character_name", "")
    description = body.get("description", "")
    personality = body.get("personality", "")
    char_dir = body.get("char_dir", "")
    pool_name = body.get("pool_name", "")
    category = body.get("category", "")
    
    # Find the spec
    all_specs = {"idle": IDLE_POOL_SPECS, "games": GAME_POOL_SPECS, "extras": EXTRAS_POOL_SPECS}
    spec = all_specs.get(category, {}).get(pool_name)
    if not spec:
        return {"success": False, "error": f"Unknown pool: {category}/{pool_name}"}
    
    backend = get_llm_backend()
    data = await generate_pool(char_name, description, personality, pool_name, spec, backend)
    
    if data is None:
        return {"success": False, "error": "Generation failed after retries"}
    
    # Write the file
    if category == "idle":
        # Read existing messages.yaml, update this pool
        idle_path = os.path.join(char_dir, "idle", "messages.yaml")
        existing = {}
        if os.path.exists(idle_path):
            with open(idle_path, "r", encoding="utf-8") as f:
                existing = yaml.safe_load(f) or {}
        existing[pool_name] = data
        with open(idle_path, "w", encoding="utf-8") as f:
            yaml.dump(existing, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    elif category == "games":
        game_path = os.path.join(char_dir, "games", f"{pool_name}.yaml")
        os.makedirs(os.path.dirname(game_path), exist_ok=True)
        with open(game_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    elif category == "extras":
        extras_path = os.path.join(char_dir, "content", "extras.yaml")
        existing = {}
        if os.path.exists(extras_path):
            with open(extras_path, "r", encoding="utf-8") as f:
                existing = yaml.safe_load(f) or {}
        existing[pool_name] = data
        os.makedirs(os.path.dirname(extras_path), exist_ok=True)
        with open(extras_path, "w", encoding="utf-8") as f:
            yaml.dump(existing, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    
    count = len(data) if isinstance(data, list) else sum(len(v) for v in data.values() if isinstance(v, list))
    return {"success": True, "pool": pool_name, "count": count}


# ─── Character Creation ────────────────────────────────────────────────────────

@app.post("/api/create-character")
async def create_character(body: dict):
    characters_dir = os.path.join(PROJECT_ROOT, "characters")
    try:
        char_dir = build_character(body, characters_dir)
        
        # Move staged uploads from draft workspace
        char_name_key = body.get("name", "").lower().replace(" ", "_")
        draft_dir = os.path.join(os.path.dirname(__file__), "_drafts", char_name_key)
        if os.path.isdir(draft_dir):
            _move_staged_files(draft_dir, char_dir)
        
        # Prepare voice artifacts
        voice_result = prepare_voice_artifacts(body, char_dir)
        
        # Auto-start AI sprite generation in background if visual description exists
        sprite_task_id = None
        visual_desc = body.get("visual_description", "")
        if visual_desc:
            from character_creator.sprite_generator import generate_all_poses, _generation_tasks
            sprite_task_id = str(uuid.uuid4())[:8]
            art_style = body.get("art_style", "3d_figurine")
            sprite_output = os.path.join(char_dir, "sprites")
            asyncio.create_task(generate_all_poses(
                sprite_task_id, char_name_key, visual_desc, art_style, sprite_output
            ))
            logger.info(f"Auto-started AI sprite generation (task: {sprite_task_id})")
        
        return {
            "success": True, "path": char_dir,
            "voice": voice_result, "sprite_task_id": sprite_task_id
        }
    except Exception as e:
        logger.error(f"Character creation failed: {e}")
        return {"success": False, "error": str(e)}

def _move_staged_files(draft_dir: str, char_dir: str):
    import shutil

    def merge_path(src: str, dst: str):
        if os.path.isdir(src):
            os.makedirs(dst, exist_ok=True)
            for child in os.listdir(src):
                merge_path(os.path.join(src, child), os.path.join(dst, child))
            shutil.rmtree(src, ignore_errors=True)
            return

        os.makedirs(os.path.dirname(dst), exist_ok=True)
        os.replace(src, dst)

    for item in os.listdir(draft_dir):
        src = os.path.join(draft_dir, item)
        dst = os.path.join(char_dir, item)
        merge_path(src, dst)
    shutil.rmtree(draft_dir, ignore_errors=True)

@app.get("/api/known-character/{name}")
async def get_known_character(name: str):
    """Lookup a known character by name."""
    result = kc_lookup(name)
    if result:
        return {"found": True, "data": result}
    return {"found": False, "data": None}

@app.get("/api/known-characters")
async def get_known_characters():
    """Get list of all available known characters."""
    characters = kc_list()
    return {"characters": characters}


# ─── Sprite Manager ───────────────────────────────────────────────────────────

@app.get("/api/sprites/backends")
async def get_sprite_backends():
    """Detect and return available image generation backends."""
    from character_creator.sprite_generator import detect_backends
    return await detect_backends()


@app.get("/api/sprites/config")
async def get_sprite_config():
    from character_creator.sprite_generator import load_sprite_config
    cfg = load_sprite_config()
    # Mask token for security
    masked = {**cfg}
    if masked.get("hf_token"):
        masked["hf_token"] = masked["hf_token"][:8] + "..." + masked["hf_token"][-4:]
    masked["hf_token_set"] = bool(cfg.get("hf_token"))
    return masked


@app.post("/api/sprites/config")
async def save_sprite_config_endpoint(body: dict):
    from character_creator.sprite_generator import load_sprite_config, save_sprite_config
    cfg = load_sprite_config()
    # Only update allowed keys; never blank out an existing token unless explicitly set
    allowed = {"backend", "hf_token", "a1111_url", "comfyui_url"}
    for key in allowed:
        if key in body and body[key] is not None:
            if key == "hf_token" and body[key] == "":
                continue  # empty string = keep existing
            cfg[key] = body[key]
    save_sprite_config(cfg)
    return {"success": True, "config": {k: ("***" if k == "hf_token" and v else v) for k, v in cfg.items()}}


@app.get("/sprites")
async def sprites_page():
    return FileResponse(os.path.join(STATIC_DIR, "sprites.html"))


@app.get("/api/characters")
async def list_all_characters():
    """List every character in the characters/ directory with their sprite status."""
    import yaml
    from character_creator.sprite_generator import expected_sprite_count
    chars_dir = os.path.join(PROJECT_ROOT, "characters")
    result = []
    EXPECTED_SPRITES = expected_sprite_count()

    for name in sorted(os.listdir(chars_dir)):
        if name.startswith("_"):
            continue
        char_dir = os.path.join(chars_dir, name)
        yaml_path = os.path.join(char_dir, "character.yaml")
        if not os.path.isfile(yaml_path):
            continue

        try:
            with open(yaml_path, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except Exception:
            data = {}

        visuals = data.get("visuals", {}) or {}
        identity = data.get("identity", {}) or {}

        # Count valid vs broken sprites
        sprites_dir = os.path.join(char_dir, "sprites")
        valid, broken = 0, 0
        sprite_list = []
        if os.path.isdir(sprites_dir):
            for root, _, files in os.walk(sprites_dir):
                for fn in files:
                    if fn.lower().endswith((".png", ".jpg", ".jpeg")):
                        fpath = os.path.join(root, fn)
                        fsize = os.path.getsize(fpath)
                        rel = os.path.relpath(fpath, sprites_dir).replace("\\", "/")
                        sprite_key = rel.rsplit(".", 1)[0]
                        if fsize > 5000:
                            valid += 1
                            sprite_list.append({"key": sprite_key, "valid": True, "size": fsize})
                        else:
                            broken += 1
                            sprite_list.append({"key": sprite_key, "valid": False, "size": fsize})

        # Check if currently generating
        generating_task = None
        from character_creator.sprite_generator import _generation_tasks
        for tid, task in _generation_tasks.items():
            if task.get("char_name") == name and task.get("status") == "running":
                generating_task = {
                    "task_id": tid,
                    "completed": task.get("completed", 0),
                    "total": task.get("total", EXPECTED_SPRITES),
                    "current": task.get("current", ""),
                }
                break

        result.append({
            "id": name,
            "name": identity.get("name", name),
            "display_name": identity.get("display_name", name),
            "tagline": identity.get("tagline", ""),
            "visual_description": visuals.get("visual_description", ""),
            "art_style": visuals.get("art_style", "3d_figurine"),
            "sprite_count": valid,
            "broken_count": broken,
            "expected_sprites": EXPECTED_SPRITES,
            "sprites": sprite_list,
            "generating": generating_task,
        })

    return {"characters": result}


@app.post("/api/sprites/generate/{char_name}")
async def generate_sprites_for_character(char_name: str, body: dict = None):
    """Start AI sprite generation for an existing character."""
    import yaml
    from character_creator.sprite_generator import generate_all_poses, _generation_tasks, expected_sprite_count

    chars_dir = os.path.join(PROJECT_ROOT, "characters")
    char_dir = os.path.join(chars_dir, char_name)
    yaml_path = os.path.join(char_dir, "character.yaml")

    if not os.path.isfile(yaml_path):
        return {"success": False, "error": f"Character '{char_name}' not found"}

    with open(yaml_path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    visuals = data.get("visuals", {}) or {}
    identity = data.get("identity", {}) or {}

    # Allow override from request body
    if body:
        visual_desc = body.get("visual_description") or visuals.get("visual_description", "")
        art_style = body.get("art_style") or visuals.get("art_style", "3d_figurine")
    else:
        visual_desc = visuals.get("visual_description", "")
        art_style = visuals.get("art_style", "3d_figurine")

    if not visual_desc:
        # Fall back to identity description (good enough for prompt generation)
        identity_desc = (data.get("identity", {}) or {}).get("description", "")
        display = identity.get("display_name", identity.get("name", char_name))
        if identity_desc:
            visual_desc = f"{display}, {identity_desc[:200]}"
        else:
            visual_desc = f"{display}, full body, anime art style"

    # Check if already running
    for tid, task in _generation_tasks.items():
        if task.get("char_name") == char_name and task.get("status") == "running":
            return {"success": False, "error": "Already generating", "task_id": tid}

    task_id = str(uuid.uuid4())[:8]
    sprites_dir = os.path.join(char_dir, "sprites")
    os.makedirs(sprites_dir, exist_ok=True)

    # Store char_name in task for /api/characters lookup
    from character_creator.sprite_generator import _generation_tasks as tasks
    tasks[task_id] = {
        "status": "running", "total": expected_sprite_count(), "completed": 0,
        "current": "starting...", "results": [], "char_name": char_name,
    }

    asyncio.create_task(generate_all_poses(task_id, char_name, visual_desc, art_style, sprites_dir))
    logger.info(f"Started sprite generation for '{char_name}' (task: {task_id})")

    return {"success": True, "task_id": task_id, "char_name": char_name}


@app.get("/api/sprites/preview/{char_name}/{pose:path}")
async def serve_sprite_preview(char_name: str, pose: str):
    """Serve a character sprite image for preview in the UI."""
    from fastapi.responses import Response
    chars_dir = os.path.join(PROJECT_ROOT, "characters")
    sprites_dir = os.path.join(chars_dir, char_name, "sprites")

    for ext in (".png", ".jpg", ".jpeg"):
        fpath = os.path.join(sprites_dir, pose.replace("/", os.sep) + ext)
        if os.path.isfile(fpath) and os.path.getsize(fpath) > 5000:
            with open(fpath, "rb") as f:
                data = f.read()
            mime = "image/jpeg" if ext in (".jpg", ".jpeg") else "image/png"
            return Response(content=data, media_type=mime)

    return Response(status_code=404)


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8766)
