"""Character Creator Wizard — standalone FastAPI server.

Serves a 6-step browser wizard for creating AI characters.
Run standalone: python -m character_creator.server
"""
import os
import sys
import logging
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

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8766)
