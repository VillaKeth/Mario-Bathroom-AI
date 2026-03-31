"""Dashboard — FastAPI router for /dashboard, /api/health, /api/reload."""

import gc
import logging
import os
import time

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, FileResponse

logger = logging.getLogger("dashboard")

DEBUG_DASHBOARD = True

router = APIRouter()

# Will be set by main.py at startup
_health_fn = None
_server_start_time = None


def init_dashboard(health_fn, server_start_time: float):
    """Wire up health function and start time from main.py."""
    global _health_fn, _server_start_time
    _health_fn = health_fn
    _server_start_time = server_start_time
    if DEBUG_DASHBOARD:
        logger.debug("[DEBUG_DASHBOARD] init_dashboard: wired health_fn, start_time=%.0f", server_start_time)


@router.get("/dashboard")
async def dashboard_page():
    """Serve the phone-friendly dashboard HTML."""
    html_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web", "dashboard.html")
    if os.path.exists(html_path):
        return FileResponse(html_path, media_type="text/html")
    return HTMLResponse("<h1>dashboard.html not found</h1>", status_code=404)


@router.get("/api/health")
async def api_health():
    """Detailed health JSON for dashboard consumption."""
    if _health_fn is None:
        return {"status": "error", "message": "Dashboard not initialized"}
    try:
        data = await _health_fn()
        return data
    except Exception as e:
        logger.error("api/health failed: %s", e)
        return {"status": "error", "message": str(e)}


@router.post("/api/reload")
async def api_reload():
    """Hot reload stub — returns 200 to confirm server is responsive."""
    if DEBUG_DASHBOARD:
        logger.debug("[DEBUG_DASHBOARD] api_reload: called")
    return {"status": "ok", "message": "Reload acknowledged", "timestamp": time.time()}
