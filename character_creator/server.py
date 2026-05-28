"""Character Creator Wizard — standalone FastAPI server.

Serves a 6-step browser wizard for creating AI characters.
Run standalone: python -m character_creator.server
"""
import os
import sys
import logging
import httpx
import edge_tts
import base64
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Add server directory to path to import hardware module
PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "server"))
import hardware

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

from character_creator import voice_finder
from character_creator.sprite_generator import get_all_poses

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
    output_dir = os.path.join(PROJECT_ROOT, "character_creator", "_drafts", char_name, "voice")
    os.makedirs(output_dir, exist_ok=True)
    path = voice_finder.download_clip(url, output_dir)
    return {"success": path is not None, "path": path}

@app.get("/api/sprites/poses")
async def sprite_poses():
    return get_all_poses()

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

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8766)
