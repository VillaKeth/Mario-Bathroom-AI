# Admin Live-Control Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `/control` a phone-first admin remote where every party feature toggles live (no restart), backed by a generic `LiveConfig` bus.

**Architecture:** A single flag manifest (`server/live_flags.py`) drives one whitelisted `POST /admin/live_set` and one `POST /admin/state` snapshot. Feature flags read live via `live_config.get(...)`. The page (`control.html`) renders groups from the manifest + state, adapts phone(Live)/desktop(Setup), and syncs against `/admin/state`.

**Tech Stack:** FastAPI (`server/main.py`), stdlib `LiveConfig` (`server/hot_reload.py`), vanilla HTML/JS (`server/static/control.html`), pytest.

## Global Constraints

- `print()`-style logging via existing `logger`/`logging` in `main.py`; `print()` in `command_handlers.py` (no logger there).
- WebSocket message type for client responses is `"mario_response"`.
- No ellipsis in hardcoded TTS strings.
- `git add <specific files>` only — never `git add -A` (Qdrant `.lock`).
- Commit trailer: `Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>`.
- Admin key check pattern (copy from existing endpoints): `GAME_CONFIG.get("admin_api_key","")`; if set and `request_body.get("api_key") != key` → `{"status":"error","message":"Invalid API key"}`.
- `LiveConfig` instance is the module global `live_config` in `main.py` (created line ~144). It auto-reloads on file mtime change; `.get(key, default)` is live, `.set(key, value)` persists.

---

### Task 1: Flag manifest module

**Files:**
- Create: `server/live_flags.py`
- Test: `tests/test_admin_live_control.py`

**Interfaces:**
- Produces: `LIVE_FLAGS: list[dict]`, `FLAG_BY_KEY: dict[str,dict]`, `coerce_flag(key, value) -> Any` (raises `ValueError`), `flag_defaults() -> dict`.

- [ ] **Step 1: Write failing test**

```python
# tests/test_admin_live_control.py
import pytest
from server import live_flags as lf

def test_manifest_has_expected_flags():
    keys = {f["key"] for f in lf.LIVE_FLAGS}
    assert {"llm_idle_enabled","gossip_enabled","safety_enabled","games_enabled",
            "recognition_enabled","distress_enabled","catchphrase_mirror_enabled",
            "paused"} <= keys

def test_coerce_bool_and_reject_unknown():
    assert lf.coerce_flag("paused", "true") is True
    assert lf.coerce_flag("paused", 0) is False
    with pytest.raises(ValueError):
        lf.coerce_flag("not_a_flag", 1)

def test_coerce_number_range():
    assert lf.coerce_flag("llm_idle_chance", "0.25") == 0.25
    with pytest.raises(ValueError):
        lf.coerce_flag("llm_idle_chance", 5)  # out of 0..1
```

- [ ] **Step 2: Run — expect fail** `pytest tests/test_admin_live_control.py -q` → ModuleNotFound / attribute errors.

- [ ] **Step 3: Implement `server/live_flags.py`**

```python
"""Single source of truth for live-toggleable admin flags.

Drives BOTH server-side validation (/admin/live_set) and the control page's
rendering (/admin/state). Add a toggle = add one entry here."""

def _b(v):  # bool coercer accepting JSON bools, 0/1, "true"/"false"
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

# type: bool|number|enum ; group: vibe|features|games|look|setup
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
]

FLAG_BY_KEY = {f["key"]: f for f in LIVE_FLAGS}

def coerce_flag(key, value):
    f = FLAG_BY_KEY.get(key)
    if f is None:
        raise ValueError(f"unknown flag: {key}")
    return f["coerce"](value)

def flag_defaults():
    return {f["key"]: f["default"] for f in LIVE_FLAGS}

def public_manifest():
    """Manifest without the (non-serialisable) coerce fn — safe for JSON."""
    return [{k: v for k, v in f.items() if k != "coerce"} for f in LIVE_FLAGS]
```

- [ ] **Step 4: Run — expect pass** `pytest tests/test_admin_live_control.py -q`

- [ ] **Step 5: Commit** `git add server/live_flags.py tests/test_admin_live_control.py && git commit -m "feat(admin): live-flag manifest + coercion"`

---

### Task 2: `/admin/live_set` + `/admin/state` endpoints

**Files:**
- Modify: `server/main.py` (append endpoints near other `/admin/*`, e.g. after `set_config`)
- Test: `tests/test_admin_live_control.py`

**Interfaces:**
- Consumes: `live_flags.coerce_flag`, `live_flags.public_manifest`, `live_flags.flag_defaults`, module `live_config`.
- Produces: `POST /admin/live_set {api_key,key,value}` → `{status, key, value}`; `POST /admin/state {api_key}` → `{status, flags:{...}, manifest:[...], phase, volume, character, active_game, paused}`.

- [ ] **Step 1: Write failing test** (uses FastAPI TestClient; follow the pattern already in `tests/` — check an existing admin endpoint test for app import + api_key fixture).

```python
def test_live_set_rejects_unknown_key(client, admin_key):
    r = client.post("/admin/live_set", json={"api_key": admin_key, "key": "x", "value": 1})
    assert r.json()["status"] == "error"

def test_live_set_roundtrips(client, admin_key):
    r = client.post("/admin/live_set", json={"api_key": admin_key,
                    "key": "gossip_enabled", "value": False})
    assert r.json()["status"] == "ok"
    s = client.post("/admin/state", json={"api_key": admin_key}).json()
    assert s["flags"]["gossip_enabled"] is False
```

- [ ] **Step 2: Run — expect fail** (404 / missing endpoint).

- [ ] **Step 3: Implement** — append to `main.py` (mirror the `admin_set_config` key-check + body shape):

```python
@app.post("/admin/live_set")
async def admin_live_set(request_body: dict = {}):
    """Set one whitelisted live flag. Instant (LiveConfig auto-reload)."""
    api_key = GAME_CONFIG.get("admin_api_key", "")
    if api_key and request_body.get("api_key") != api_key:
        return {"status": "error", "message": "Invalid API key"}
    key = request_body.get("key")
    try:
        value = live_flags.coerce_flag(key, request_body.get("value"))
    except ValueError as e:
        return {"status": "error", "message": str(e)}
    live_config.set(key, value)
    logger.info(f"[ADMIN] live_set {key} = {value!r}")
    return {"status": "ok", "key": key, "value": value}

@app.post("/admin/state")
async def admin_state(request_body: dict = {}):
    """Snapshot of every live flag + live subsystem readouts for the control page."""
    api_key = GAME_CONFIG.get("admin_api_key", "")
    if api_key and request_body.get("api_key") != api_key:
        return {"status": "error", "message": "Invalid API key"}
    flags = {}
    for k, default in live_flags.flag_defaults().items():
        flags[k] = live_config.get(k, default)
    active = state_current.get("_active_game") or {}
    return {"status": "ok", "flags": flags, "manifest": live_flags.public_manifest(),
            "phase": _current_night_phase_name(), "volume": live_config.get("tts_gain", 1.0),
            "character": _CHARACTER_DISPLAY_NAME, "active_game": active.get("type"),
            "paused": bool(live_config.get("paused", False))}
```

(During execution: confirm real names for `_current_night_phase_name`, `_CHARACTER_DISPLAY_NAME`, `state_current`, and the volume key — grep first; adjust to actual.)

- [ ] **Step 4: Add `import live_flags`** near the other server imports in `main.py`.
- [ ] **Step 5: Run — expect pass.**
- [ ] **Step 6: Commit** `git add server/main.py tests/test_admin_live_control.py && git commit -m "feat(admin): /admin/live_set + /admin/state bus"`

---

### Task 3: Make idle flags read live

**Files:** Modify `server/main.py` (idle globals ~3571; idle decision ~4037). Test: same test file.

- [ ] **Step 1: Failing test** — set `llm_idle_enabled=False` via `live_config`, assert the idle-send guard returns False/skips. (Find the smallest idle-decision function; if inline in a loop, extract a helper `_idle_llm_allowed() -> bool` that reads `live_config.get("llm_idle_enabled", True)` and `live_config.get("llm_idle_chance", ...)`, and test that.)
- [ ] **Step 2: Run — fail.**
- [ ] **Step 3: Implement** — replace the module-global reads (`_LLM_IDLE_ENABLED`, `_LLM_IDLE_CHANCE`) at the decision site with `live_config.get("llm_idle_enabled", True)` and `live_config.get("llm_idle_chance", _LLM_IDLE_CHANCE_DEFAULT)`. Keep the startup values as defaults.
- [ ] **Step 4: Run — pass.**
- [ ] **Step 5: Commit** `git add server/main.py tests/test_admin_live_control.py && git commit -m "feat(admin): idle chatter reads flag live"`

---

### Task 4: `paused` kill switch

**Files:** Modify `server/main.py` (the main user-text → reply entrypoint, `_dispatch_user_text` / response generator). Test: same file.

- [ ] **Step 1: Failing test** — with `live_config.set("paused", True)`, dispatching user text yields no spoken reply (status like `{"status":"paused"}` or empty response + no TTS).
- [ ] **Step 2: Run — fail.**
- [ ] **Step 3: Implement** — at the top of the reply path, `if live_config.get("paused", False): return {"status": "paused"}` (before LLM/TTS). Idle loop also checks `paused`.
- [ ] **Step 4: Run — pass.**
- [ ] **Step 5: Commit** `git add server/main.py tests/test_admin_live_control.py && git commit -m "feat(admin): paused kill switch skips replies + TTS"`

---

### Task 5: Feature gates read live (safety, gossip, games, recognition, distress, catchphrase)

Do these one flag at a time — each is its own test + commit. Pattern per flag:

- [ ] **Grep** for where the feature is gated/invoked (e.g. `safety_filter`, gossip inject, game routing in `command_handlers.py`, recognition, `detect_distress`, catchphrase mirror).
- [ ] **Failing test:** set `<flag>=False` via `live_config`, assert the feature's decision function returns the disabled branch.
- [ ] **Implement:** at the decision point, gate on `live_config.get("<flag>", <default>)`. For server modules without `live_config`, pass a getter or read a shared accessor (add a tiny `def flag(key, default): return live_config.get(key, default)` in `main.py` and call the feature with the boolean already resolved, OR import the live_config accessor). Prefer resolving the boolean in `main.py` and passing it in, to avoid import cycles.
- [ ] **Run — pass. Commit** `git add <files> && git commit -m "feat(admin): <feature> reads flag live"`.

Flags: `safety_enabled`, `gossip_enabled`, `games_enabled`, `recognition_enabled`, `distress_enabled`, `catchphrase_mirror_enabled`.

---

### Task 6: `/admin/outfit` broadcast to client

**Files:** Modify `server/main.py` (new endpoint), reuse mirror broadcast. Test: same file.

**Interfaces:** Produces `POST /admin/outfit {api_key, outfit}` → `{status, outfit}`; sends a WS message the client's `on_outfit_switched` consumes.

- [ ] **Step 1: Grep** the client/server for the outfit-switch message shape the client expects (`on_outfit_switched` in `client/ws_client.py` / `client/main.py:630`). Match its `type` + payload key (`outfit`).
- [ ] **Step 2: Failing test** — posting to `/admin/outfit` calls the mirror/broadcast with `{"type": <outfit type>, "outfit": name}` (assert via a monkeypatched broadcast).
- [ ] **Step 3: Implement** endpoint: key-check, then `await mirror_relay.broadcast_*({"type": "...", "outfit": outfit})` (use the actual broadcast fn used by other client pushes).
- [ ] **Step 4: Run — pass. Commit** `git add server/main.py tests/test_admin_live_control.py && git commit -m "feat(admin): /admin/outfit pushes outfit swap to client"`

---

### Task 7: Rewrite `control.html` (adaptive live/setup, layout A, state sync)

**Files:** Modify `server/static/control.html` (full rewrite). No unit test (manual + smoke).

- [ ] **Step 1:** Rebuild the page:
  - Keep the admin-key card + `post(path, body)` helper + localStorage key store.
  - On connect: `POST /admin/state`; render groups from `manifest` (bucket by `group`) + current `flags`.
  - Header `Live | Setup` pill; default via `matchMedia("(max-width:700px)")`; persist override in localStorage; toggling re-renders which groups/controls show.
  - Live groups: vibe (phase segmented → `/admin/set_night_phase`; volume slider → `/admin/set_volume`; pause toggle → `/admin/live_set`), features (bool toggles → `/admin/live_set`), games (stop → `/admin/force_stop_game`; event picker → `/admin/trigger_event/{name}`; memorial → `/admin/trigger_memorial` w/ confirm), look (outfit → `/admin/outfit`; emotion → `/admin/set_emotion`; announce → `/admin/announce`).
  - Setup-only: character switch (existing calls), idle timing fields → `/admin/set_config`, restart (typed RESTART) → `/admin/restart`, health readout (`/api/health`).
  - Toggle UX: optimistic flip; on non-ok response revert + toast; re-`POST /admin/state` after each action and on a 5s interval.
- [ ] **Step 2: Smoke test** — start server, `curl /control` returns 200 and contains the group ids; drive `/admin/state` + a `/admin/live_set` round-trip via curl.
- [ ] **Step 3: Commit** `git add server/static/control.html && git commit -m "feat(admin): adaptive live/setup control page (layout A)"`

---

### Task 8: Integration + live verification

- [ ] Restart the running server (or rely on hot endpoints), open `/control` over localhost, connect with the admin key.
- [ ] Flip each feature toggle; confirm `/admin/state` reflects it and the behavior changes live (idle off → no idle line; paused → silent; safety on → filtered).
- [ ] Per `.claude/rules/testing.md`: drive announce + outfit + emotion; confirm client audio plays (`_play_wav: playing`→`done`) and the on-screen character reflects outfit/emotion. Confirm zero wrong-character leaks (Rudi, not Mario).
- [ ] Run full suite: `venv/Scripts/python.exe -m pytest tests/ -q`. All green.
- [ ] Final commit if any fixups; leave branch ready for review.

---

## Self-Review

- **Spec coverage:** manifest (T1) ✓, live_set/state bus (T2) ✓, idle live (T3) ✓, paused (T4) ✓, feature gates live (T5) ✓, outfit (T6) ✓, adaptive page + sync (T7) ✓, auth (key check every endpoint) ✓, testing incl. live verify (T8) ✓.
- **Placeholders:** the read-site tasks (T3/T5/T6) name the pattern and require a grep-confirm during execution because exact line numbers drift with the concurrent session — acceptable and called out, not a hidden TODO.
- **Type consistency:** flag keys identical across manifest, endpoints, tests, page. `live_config.get/set` used throughout.
