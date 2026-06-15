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
