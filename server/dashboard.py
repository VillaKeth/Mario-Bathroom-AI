"""Dashboard — FastAPI router for /dashboard, /api/health, /api/reload, /api/canary, /api/report."""

import asyncio
import gc
import logging
import os
import time

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, FileResponse

logger = logging.getLogger("dashboard")

DEBUG_DASHBOARD = True

router = APIRouter()

# Will be set by main.py at startup
_health_fn = None
_server_start_time = None
_live_config = None  # Set by main.py for hot reload
_report_deps = None  # Dict of module refs for party report


def init_dashboard(health_fn, server_start_time: float, live_config=None, report_deps: dict = None):
    """Wire up health function, start time, live config, and report deps from main.py."""
    global _health_fn, _server_start_time, _live_config, _report_deps
    _health_fn = health_fn
    _server_start_time = server_start_time
    if live_config is not None:
        _live_config = live_config
    if report_deps is not None:
        _report_deps = report_deps
    if DEBUG_DASHBOARD:
        logger.debug("[DEBUG_DASHBOARD] init_dashboard: wired health_fn, start_time=%.0f, live_config=%s, report_deps=%s",
                     server_start_time, "yes" if _live_config else "no", "yes" if _report_deps else "no")


@router.get("/dashboard")
async def dashboard_page():
    """Serve the phone-friendly dashboard HTML."""
    html_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web", "dashboard.html")
    if os.path.exists(html_path):
        return FileResponse(html_path, media_type="text/html")
    return HTMLResponse("<h1>dashboard.html not found</h1>", status_code=404)


@router.get("/party-host")
async def party_host_page():
    """Serve the mobile party host quick-actions page."""
    html_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web", "party_host.html")
    if os.path.exists(html_path):
        return FileResponse(html_path, media_type="text/html")
    return HTMLResponse("<h1>party_host.html not found</h1>", status_code=404)


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
async def api_reload(request: Request):
    """Hot reload — update live config values."""
    if DEBUG_DASHBOARD:
        logger.debug("[DEBUG_DASHBOARD] api_reload: called")
    if _live_config is None:
        return {"status": "ok", "message": "Reload acknowledged (no live config)", "timestamp": time.time()}
    try:
        body = await request.json()
        if body:
            _live_config.update(body)
            if DEBUG_DASHBOARD:
                logger.debug("[DEBUG_DASHBOARD] api_reload: updated keys=%s", list(body.keys()))
        else:
            _live_config.reload()
        return {
            "status": "ok",
            "message": "Live config updated",
            "timestamp": time.time(),
            "config": _live_config.to_dict(),
        }
    except Exception as e:
        # Fallback: just reload from disk
        _live_config.reload()
        return {"status": "ok", "message": "Reloaded from disk", "timestamp": time.time()}


@router.get("/api/live-config")
async def api_live_config():
    """Return current live config values for dashboard sliders."""
    if _live_config is None:
        return {"status": "error", "message": "Live config not initialized"}
    return {"status": "ok", "config": _live_config.to_dict()}


@router.get("/api/canary")
async def api_canary():
    """Run canary self-tests and return results."""
    if DEBUG_DASHBOARD:
        logger.debug("[DEBUG_DASHBOARD] api_canary: running tests")
    try:
        from canary import Canary
        canary = Canary(server_url="http://localhost:8765")
        data = await canary.run_all()
        return {"status": "ok", **data}
    except Exception as e:
        logger.error("Canary tests failed: %s", e)
        return {"status": "error", "message": str(e)}


@router.get("/report")
async def report_page():
    """Serve the party report HTML page."""
    html_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web", "report.html")
    if os.path.exists(html_path):
        return FileResponse(html_path, media_type="text/html")
    return HTMLResponse("<h1>report.html not found</h1>", status_code=404)


@router.get("/api/report")
async def api_report():
    """Generate and return party report JSON."""
    if DEBUG_DASHBOARD:
        logger.debug("[DEBUG_DASHBOARD] api_report: generating report")
    try:
        from party_report import PartyReport

        deps = _report_deps or {}
        report = PartyReport(
            server_start_time=_server_start_time or time.time(),
            party_gossip=deps.get("party_gossip"),
            catchphrase_mirror=deps.get("catchphrase_mirror"),
            birthday_vip=deps.get("birthday_vip"),
            tts_router=deps.get("tts_router"),
            night_progression=deps.get("night_progression"),
            llm_router=deps.get("llm_router"),
            party_stats=deps.get("party_stats"),
            state_current=deps.get("state_current"),
            error_count=deps.get("error_count", 0),
        )
        data = report.generate()
        return {"status": "ok", "report": data}
    except Exception as e:
        logger.error("Report generation failed: %s", e)
        return {"status": "error", "message": str(e)}
