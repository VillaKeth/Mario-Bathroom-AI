"""Remote mirror: relay the pygame client's frames + audio to browser viewers.

Additive and opt-in. Nothing here may raise into the core server pipeline.
"""
import asyncio

DEBUG_MIRROR = True

_DEFAULTS = {
    "enabled": False,
    "control_mode": "station",   # "station" = view-only remote; "remote" = browser may drive
    "token": "",
    "pin": "",
    "fps": 10,
    "jpeg_quality": 55,
    "max_width": 640,
    "ingest_url": "ws://localhost:8765/mirror_ingest",
}


def get_mirror_config(full_config: dict) -> dict:
    """Return the mirror config merged over safe defaults."""
    out = dict(_DEFAULTS)
    out.update((full_config or {}).get("mirror", {}) or {})
    return out


def authorize_friend_input(token: str, pin: str, mcfg: dict, control_mode: str):
    """Decide whether a /friend text submission may drive the bot.

    Returns (ok: bool, reason: str). Control is only ever granted in 'remote'
    mode with a matching token AND pin. 'station' mode is view-only.
    """
    if control_mode != "remote":
        return (False, "view_only")
    want_token = (mcfg or {}).get("token", "")
    want_pin = (mcfg or {}).get("pin", "")
    if not want_token or not want_pin:
        return (False, "not_configured")
    if token == want_token and pin == want_pin:
        return (True, "ok")
    return (False, "bad_credentials")


# ---------------------------------------------------------------------------
# Task 3: viewer registry, capture start/stop signal, fan-out relay
# ---------------------------------------------------------------------------

_viewers: set = set()
_active_ws_getter = None  # callable returning the pygame client's WebSocket or None


def reset_state():
    """Test helper: clear all module state."""
    global _viewers, _active_ws_getter
    _viewers = set()
    _active_ws_getter = None


def set_active_ws_getter(fn):
    global _active_ws_getter
    _active_ws_getter = fn


def viewer_count() -> int:
    return len(_viewers)


async def _signal_capture(active: bool):
    """Tell the pygame client to start/stop capturing. Never raises."""
    try:
        ws = _active_ws_getter() if _active_ws_getter else None
        if ws is not None:
            await ws.send_json({"type": "mirror_request", "active": bool(active)})
    except Exception as e:
        if DEBUG_MIRROR:
            print(f"[mirror] _signal_capture failed (ignored): {e}")


async def add_viewer(ws):
    first = len(_viewers) == 0
    _viewers.add(ws)
    if first:
        await _signal_capture(True)


async def remove_viewer(ws):
    _viewers.discard(ws)
    if len(_viewers) == 0:
        await _signal_capture(False)


async def broadcast(data: bytes):
    """Fan out one tagged binary message to all viewers; drop dead sockets."""
    dead = []
    for ws in list(_viewers):
        try:
            await ws.send_bytes(data)
        except Exception:
            dead.append(ws)
    for ws in dead:
        _viewers.discard(ws)
    if dead and len(_viewers) == 0:
        await _signal_capture(False)
