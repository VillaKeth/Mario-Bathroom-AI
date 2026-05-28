"""Character Creator Wizard — standalone FastAPI server.

Serves a 6-step browser wizard for creating AI characters.
Run standalone: python -m character_creator.server
"""
import os
import sys
import logging
import httpx
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

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8766)
