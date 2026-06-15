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
