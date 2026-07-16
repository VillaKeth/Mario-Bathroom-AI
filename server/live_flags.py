"""Single source of truth for live-toggleable admin flags.

Drives BOTH server-side validation (POST /admin/live_set) and the control
page's rendering (POST /admin/state). Add a toggle = add one entry here; the
endpoints validate against it and the page renders it automatically.

Values live in LiveConfig (config_live.json), which auto-reloads, so a set()
here is picked up by the next live_config.get() with no restart.
"""


def _b(v):
    """Coerce to bool, accepting JSON bools, 0/1, and "true"/"false" strings."""
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(v)
    if isinstance(v, str):
        return v.strip().lower() in ("1", "true", "yes", "on")
    raise ValueError("not a boolean")


def _num(lo, hi, kind):
    def f(v):
        try:
            n = kind(v)
        except (TypeError, ValueError):
            raise ValueError("not a number")
        if n < lo or n > hi:
            raise ValueError(f"out of range {lo}..{hi}")
        return n
    return f


def _enum(options):
    def f(v):
        s = str(v)
        if s not in options:
            raise ValueError(f"must be one of {options}")
        return s
    return f


# type: bool | number | enum ; group: vibe | features | games | look | setup
LIVE_FLAGS = [
    {"key": "paused", "label": "Pause bot", "type": "bool", "default": False,
     "group": "vibe", "coerce": _b},
    {"key": "llm_idle_enabled", "label": "Idle chatter", "type": "bool",
     "default": True, "group": "features", "coerce": _b},
    {"key": "gossip_enabled", "label": "Gossip", "type": "bool", "default": True,
     "group": "features", "coerce": _b},
    {"key": "safety_enabled", "label": "Safety filter", "type": "bool",
     "default": False, "group": "features", "coerce": _b},
    {"key": "games_enabled", "label": "Games", "type": "bool", "default": True,
     "group": "features", "coerce": _b},
    {"key": "recognition_enabled", "label": "Face recognition", "type": "bool",
     "default": True, "group": "features", "coerce": _b},
    {"key": "distress_enabled", "label": "Distress detect", "type": "bool",
     "default": True, "group": "features", "coerce": _b},
    {"key": "catchphrase_mirror_enabled", "label": "Catchphrase mirror",
     "type": "bool", "default": True, "group": "features", "coerce": _b},
    {"key": "llm_idle_chance", "label": "Idle AI chance", "type": "number",
     "default": 0.25, "min": 0.0, "max": 1.0, "group": "setup",
     "coerce": _num(0.0, 1.0, float)},
    {"key": "camera_enabled", "label": "Remote camera", "type": "bool",
     "default": True, "group": "features", "coerce": _b},
    {"key": "camera_vision_enabled", "label": "Camera vision comments", "type": "bool",
     "default": True, "group": "features", "coerce": _b},
    {"key": "camera_vision_min_gap", "label": "Camera comment gap (s)", "type": "number",
     "default": 45, "min": 5, "max": 600, "group": "setup", "coerce": _num(5, 600, int)},
    {"key": "camera_vision_timeout", "label": "Camera vision timeout (s)", "type": "number",
     "default": 60, "min": 5, "max": 300, "group": "setup", "coerce": _num(5, 300, int)},
]

FLAG_BY_KEY = {f["key"]: f for f in LIVE_FLAGS}


def coerce_flag(key, value):
    """Validate+coerce a value for `key`. Raises ValueError on unknown key or bad value."""
    f = FLAG_BY_KEY.get(key)
    if f is None:
        raise ValueError(f"unknown flag: {key}")
    return f["coerce"](value)


def flag_defaults():
    """{key: default} for every flag."""
    return {f["key"]: f["default"] for f in LIVE_FLAGS}


def public_manifest():
    """Manifest without the (non-JSON-serialisable) coerce fn — safe to return over HTTP."""
    return [{k: v for k, v in f.items() if k != "coerce"} for f in LIVE_FLAGS]
