"""Remote mirror: relay the pygame client's frames + audio to browser viewers.

Additive and opt-in. Nothing here may raise into the core server pipeline.
"""
import asyncio
import json
import time
from collections import deque

DEBUG_MIRROR = True

# Binary message tags (must match client/mirror_sender.py).
TAG_VIDEO = b"\x01"
TAG_AUDIO = b"\x02"

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
_capture_active = False        # last capture state we signaled to the pygame client
_SEND_TIMEOUT = 8.0            # per-viewer send timeout (seconds); generous so a big
                              # audio chunk to a phone over the tunnel isn't false-dropped.
                              # module-level so tests can override.
_control_mode = "station"

# --- relay queue: decouple the ingest socket from slow viewers ----------------
# The pygame client pushes frames+audio at /mirror_ingest. We must drain that
# socket continuously, or the OS send buffer fills and the client's send_binary
# times out (then its sender thread dies and the viewer page freezes until a
# refresh). So ingest only ever calls enqueue() — a non-blocking hand-off — and
# a single background worker fans out to viewers via broadcast(). A slow viewer
# (e.g. a phone over the Cloudflare tunnel) can no longer stall the ingest read.
_pending = deque()        # bytes messages awaiting fan-out
_PENDING_MAX = 64         # cap; video collapses to latest, audio is preserved
_relay_event = None       # asyncio.Event, created lazily inside the loop
_relay_task = None        # the single drain worker task
_lag_task = None          # diagnostic event-loop-lag monitor task

# --- single-talker turn-lock + live transcript (remote mode UX) ---------------
# One person "holds the turn" while chatting; each accepted message refreshes the
# idle timer. After _TURN_IDLE_SECONDS of silence the turn auto-frees so someone
# else can talk. This is best-effort UX (identity is name + a random browser id),
# NOT a security boundary.
_TURN_IDLE_SECONDS = 30.0
_turn = {"owner": None, "name": None, "expires": 0.0}
_transcript = deque(maxlen=6)   # items: {"who": str, "text": str}
_presence_task = None           # watcher loop: frees idle turns + tells viewers


def set_control_mode(mode: str):
    global _control_mode
    _control_mode = "remote" if mode == "remote" else "station"


def get_control_mode() -> str:
    return _control_mode


def reset_state():
    """Test helper: clear all module state."""
    global _viewers, _active_ws_getter, _capture_active, _control_mode
    global _pending, _relay_event, _relay_task, _turn, _transcript, _presence_task
    _viewers = set()
    _active_ws_getter = None
    _capture_active = False
    _control_mode = "station"
    if _relay_task is not None:
        _relay_task.cancel()
    _relay_task = None
    _relay_event = None
    _pending = deque()
    if _presence_task is not None:
        _presence_task.cancel()
    _presence_task = None
    _turn = {"owner": None, "name": None, "expires": 0.0}
    _transcript = deque(maxlen=6)


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


async def _sync_capture_state():
    """Signal the pygame client only when the desired capture state changes.
    desired = (there is at least one viewer). Idempotent: no change -> no signal."""
    global _capture_active
    desired = len(_viewers) > 0
    if desired != _capture_active:
        _capture_active = desired
        await _signal_capture(desired)


async def add_viewer(ws):
    _viewers.add(ws)
    await _sync_capture_state()


async def remove_viewer(ws):
    existed = ws in _viewers
    _viewers.discard(ws)
    if existed:
        await _sync_capture_state()


async def _close_quietly(ws):
    try:
        await ws.close()
    except Exception:
        pass


async def _drop_dead(dead):
    """Remove dead viewers AND close their sockets, so the browser's onclose
    fires and the page reconnects (instead of freezing forever with no frames)."""
    if not dead:
        return
    for ws in dead:
        _viewers.discard(ws)
        await _close_quietly(ws)
    await _sync_capture_state()


async def broadcast(data: bytes):
    """Fan out one tagged binary message to all viewers concurrently.
    Drop (and close) sockets that error or exceed _SEND_TIMEOUT; never let one
    slow viewer block the others."""
    if not _viewers:
        return

    async def _safe_send(ws):
        try:
            await asyncio.wait_for(ws.send_bytes(data), timeout=_SEND_TIMEOUT)
            return None
        except Exception:
            return ws

    results = await asyncio.gather(*[_safe_send(ws) for ws in list(_viewers)])
    await _drop_dead([ws for ws in results if ws is not None])


# ---------------------------------------------------------------------------
# Relay queue: non-blocking ingest hand-off + single fan-out worker
# ---------------------------------------------------------------------------

def enqueue(data: bytes):
    """Non-blocking hand-off from the ingest socket to the fan-out worker.

    Video frames collapse to the latest un-sent one (frames are disposable);
    audio is preserved in order (never drop speech). Never awaits, so draining
    the ingest socket is fully decoupled from slow viewers / the tunnel."""
    if not data:
        return
    tag = data[:1]
    if tag == TAG_VIDEO and _pending and _pending[-1][:1] == TAG_VIDEO:
        _pending[-1] = data  # newest frame replaces the un-sent older one
    else:
        _pending.append(data)
        if len(_pending) > _PENDING_MAX:
            # Over budget: drop the oldest VIDEO frame first (audio is precious);
            # only if there is no video to shed do we drop the oldest item.
            for i, item in enumerate(_pending):
                if item[:1] == TAG_VIDEO:
                    del _pending[i]
                    break
            else:
                _pending.popleft()
    if _relay_event is not None:
        _relay_event.set()


async def _relay_worker():
    """Drain _pending and fan out to viewers. Runs for the life of the server."""
    global _relay_event
    if _relay_event is None:
        _relay_event = asyncio.Event()
    ev = _relay_event
    while True:
        await ev.wait()
        ev.clear()
        while _pending:
            data = _pending.popleft()
            t0 = time.monotonic()
            await broadcast(data)
            dt = time.monotonic() - t0
            if dt > 1.0:
                print(f"[mirror] SLOW broadcast {dt:.1f}s tag={data[:1]!r} {len(data)}B "
                      f"viewers={len(_viewers)} pending={len(_pending)}")


async def _loop_lag_monitor():
    """Diagnostic: detect when the asyncio event loop is blocked (synchronous
    work starving coroutines). A 1s sleep that returns much later == a block."""
    while True:
        t0 = time.monotonic()
        await asyncio.sleep(1.0)
        lag = time.monotonic() - t0 - 1.0
        if lag > 1.5:
            print(f"[mirror] EVENT LOOP BLOCKED ~{lag:.1f}s (coroutines starved)")


def ensure_relay_worker():
    """Start the single drain worker if not already running. Idempotent.
    Must be called from within the server event loop (e.g. the ingest endpoint)."""
    global _relay_task, _relay_event, _lag_task
    if _relay_event is None:
        _relay_event = asyncio.Event()
    if _relay_task is None or _relay_task.done():
        _relay_task = asyncio.ensure_future(_relay_worker())
    if _lag_task is None or _lag_task.done():
        _lag_task = asyncio.ensure_future(_loop_lag_monitor())
    return _relay_task


# ---------------------------------------------------------------------------
# Single-talker turn-lock
# ---------------------------------------------------------------------------

def acquire_or_refresh_turn(client_id: str, name: str, now: float):
    """Try to take (or keep) the talking turn.

    Granted if the turn is free, already owned by this client, or the current
    holder has gone idle past _TURN_IDLE_SECONDS. On grant, (re)sets the owner
    and pushes the idle deadline out. Returns (granted, holder_name) — on denial
    holder_name is the CURRENT holder so the caller can say who's talking."""
    held = _turn["owner"] is not None and now < _turn["expires"]
    if held and _turn["owner"] != client_id:
        return (False, _turn["name"])
    _turn["owner"] = client_id
    _turn["name"] = name
    _turn["expires"] = now + _TURN_IDLE_SECONDS
    return (True, name)


def release_turn(client_id: str):
    """Free the turn, but only if this client actually holds it."""
    if _turn["owner"] == client_id:
        _turn["owner"] = None
        _turn["name"] = None
        _turn["expires"] = 0.0


def expire_turn_if_idle(now: float) -> bool:
    """If a turn is held but has gone idle, free it. Returns True iff this call
    changed the state (so a watcher knows when to broadcast 'turn free')."""
    if _turn["owner"] is not None and now >= _turn["expires"]:
        _turn["owner"] = None
        _turn["name"] = None
        _turn["expires"] = 0.0
        return True
    return False


def turn_state(now: float) -> dict:
    """Snapshot of the turn for pushing to viewers."""
    if _turn["owner"] is not None and now < _turn["expires"]:
        return {
            "busy": True,
            "name": _turn["name"],
            "seconds_left": max(0, int(_turn["expires"] - now)),
        }
    return {"busy": False, "name": None, "seconds_left": 0}


# ---------------------------------------------------------------------------
# Live transcript
# ---------------------------------------------------------------------------

def add_transcript(who: str, text: str):
    """Append one line to the rolling transcript (capped at 6)."""
    who = (who or "").strip() or "?"
    text = (text or "").strip()
    if text:
        _transcript.append({"who": who, "text": text})


def transcript_snapshot() -> list:
    """Current transcript lines, oldest first."""
    return list(_transcript)


# ---------------------------------------------------------------------------
# JSON control fan-out (presence / turn / transcript)
# ---------------------------------------------------------------------------

async def broadcast_text(obj: dict):
    """Fan out one JSON control message to all viewers concurrently. Same
    drop-dead + timeout policy as broadcast(); never blocks on a slow viewer."""
    if not _viewers:
        return
    payload = json.dumps(obj)

    async def _safe_send(ws):
        try:
            await asyncio.wait_for(ws.send_text(payload), timeout=_SEND_TIMEOUT)
            return None
        except Exception:
            return ws

    results = await asyncio.gather(*[_safe_send(ws) for ws in list(_viewers)])
    await _drop_dead([ws for ws in results if ws is not None])


# ---------------------------------------------------------------------------
# Presence / turn-expiry watcher
# ---------------------------------------------------------------------------

async def _presence_loop():
    """Background watcher: frees an idle turn and tells viewers when it happens,
    so a disabled composer re-enables even if nobody is actively sending."""
    while True:
        await asyncio.sleep(2.0)
        try:
            if expire_turn_if_idle(time.time()):
                await broadcast_text({"type": "turn", "busy": False, "name": None, "seconds_left": 0})
        except Exception:
            pass


def ensure_presence_loop():
    """Start the single turn-expiry watcher if not already running. Idempotent.
    Must be called from within the server event loop (e.g. a viewer connect)."""
    global _presence_task
    if _presence_task is None or _presence_task.done():
        _presence_task = asyncio.ensure_future(_presence_loop())
    return _presence_task
