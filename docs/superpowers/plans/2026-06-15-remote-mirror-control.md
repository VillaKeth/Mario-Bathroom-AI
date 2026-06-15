# Remote Mirror + Control Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let remote friends open a public link to watch the *real* running pygame client and (in testing mode) drive it, without ever altering or risking the standalone pygame app.

**Architecture:** The **pygame client is the tee** — it already owns the rendered Surface and receives the exact audio bytes it plays, so the server's core conversation paths stay untouched. The client pushes tagged binary frames + audio to a new server `/mirror_ingest` WebSocket; the server is a dumb relay that fans those bytes out to browser viewers connected to `/mirror`. A `/friend` HTML page draws frames on a canvas, plays the audio, and (in `remote` control mode, behind token+PIN auth) posts text through the existing `simulate_text` pipeline. Capture is fully off and zero-cost when no viewer is connected. Reach is a Cloudflare Tunnel (public HTTPS link, no installs for guests).

**Tech Stack:** Python, FastAPI (server WS + HTTP), pygame (client render loop), `websocket-client` (client→server WS), Pillow (JPEG encode), vanilla JS + WebSocket + Canvas + WebAudio (browser), `cloudflared` (tunnel).

---

## Invariant (do not violate)

**Requirement #1 — pygame independence (non-negotiable):**
The mirror is additive and opt-in. The pygame client and server must run identically to today when the mirror is disabled, or enabled but with no viewer connected. Every mirror code path is wrapped so its exceptions are logged and swallowed — never propagated into the render loop or the conversation pipeline. When no viewer is connected, capture/encode does not run (one boolean check per frame max).

There is always exactly **one** real pygame client (`_active_ws`) and **one** controller; browser viewers are a separate role and never become `_active_ws`.

## Binary tag protocol (client → server → browser)

All mirror binary messages are `1 tag byte + payload`, set once by the client sender, relayed verbatim by the server, parsed by the browser:
- `0x01` + JPEG bytes  → a video frame
- `0x02` + WAV bytes   → an audio clip

## File Structure

- **Create** `server/mirror.py` — viewer registry, fan-out relay, control-mode state, auth/gate pure functions, config defaults.
- **Create** `server/static/friend.html` — the remote page (canvas + audio + text box + PIN gate).
- **Create** `client/mirror_sender.py` — threaded sender: JPEG encode, 1-slot frame queue, audio queue, tagged binary to `/mirror_ingest`, start/stop.
- **Create** `docs/REMOTE_MIRROR.md` — runbook (cloudflared, sharing link + PIN, modes).
- **Create** `start_tunnel.bat` — convenience launcher for the tunnel.
- **Create** `tests/test_mirror.py` — unit tests for `server/mirror.py` and `client/mirror_sender.py` pure logic + `ws_client` routing.
- **Modify** `config.json` — add a `mirror` section.
- **Modify** `server/main.py` — register `/mirror`, `/mirror_ingest`, `/friend`, `/friend/say`, `/admin/mirror_mode`; extract `_dispatch_user_text`; wire active-ws getter.
- **Modify** `client/ws_client.py` — route `mirror_request` → `on_mirror_request` callback.
- **Modify** `client/mario_display.py` — add `on_frame_ready` hook fired after `pygame.display.flip()`.
- **Modify** `client/main.py` — instantiate `MirrorSender`, wire `on_mirror_request`, tee audio, set `display.on_frame_ready`.

---

### Task 1: Config — add the `mirror` section

**Files:**
- Modify: `config.json`
- Create: `server/mirror.py`
- Test: `tests/test_mirror.py`

- [ ] **Step 1: Add the `mirror` block to `config.json`** (top level, sibling of `"client"`):

```json
  "mirror": {
    "enabled": true,
    "control_mode": "station",
    "token": "changeme-token",
    "pin": "1234",
    "fps": 10,
    "jpeg_quality": 55,
    "max_width": 640,
    "ingest_url": "ws://localhost:8765/mirror_ingest"
  },
```

(Insert it as a new top-level key. `control_mode` is `"station"` = remote view-only, or `"remote"` = browser may drive. Change `token`/`pin` before exposing publicly.)

- [ ] **Step 2: Write the failing test for config defaults**

```python
# tests/test_mirror.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))
import mirror

def test_get_mirror_config_fills_defaults():
    cfg = mirror.get_mirror_config({})
    assert cfg["enabled"] is False          # absent → safe default off
    assert cfg["control_mode"] == "station" # absent → safe default view-only
    assert cfg["fps"] == 10
    assert cfg["jpeg_quality"] == 55
    assert cfg["max_width"] == 640

def test_get_mirror_config_respects_values():
    cfg = mirror.get_mirror_config({"mirror": {"enabled": True, "control_mode": "remote", "fps": 5}})
    assert cfg["enabled"] is True
    assert cfg["control_mode"] == "remote"
    assert cfg["fps"] == 5
    assert cfg["jpeg_quality"] == 55  # unspecified → default
```

- [ ] **Step 3: Run it — expect failure (module missing)**

Run: `python -m pytest tests/test_mirror.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'mirror'`

- [ ] **Step 4: Create `server/mirror.py` with config defaults**

```python
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
```

- [ ] **Step 5: Run the test — expect pass**

Run: `python -m pytest tests/test_mirror.py -v`
Expected: PASS (2 passed)

- [ ] **Step 6: Commit**

```bash
git add config.json server/mirror.py tests/test_mirror.py
git commit -m "feat(mirror): config section + defaults loader"
```

---

### Task 2: Auth / control-mode gate (pure function)

**Files:**
- Modify: `server/mirror.py`
- Test: `tests/test_mirror.py`

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_mirror.py
def test_authorize_rejected_in_station_mode():
    mcfg = {"token": "t", "pin": "p"}
    ok, reason = mirror.authorize_friend_input("t", "p", mcfg, control_mode="station")
    assert ok is False
    assert reason == "view_only"

def test_authorize_requires_token_and_pin_in_remote_mode():
    mcfg = {"token": "t", "pin": "p"}
    assert mirror.authorize_friend_input("t", "p", mcfg, "remote") == (True, "ok")
    assert mirror.authorize_friend_input("wrong", "p", mcfg, "remote")[0] is False
    assert mirror.authorize_friend_input("t", "wrong", mcfg, "remote")[0] is False
    assert mirror.authorize_friend_input("", "", mcfg, "remote")[0] is False
```

- [ ] **Step 2: Run — expect failure**

Run: `python -m pytest tests/test_mirror.py::test_authorize_rejected_in_station_mode -v`
Expected: FAIL — `AttributeError: module 'mirror' has no attribute 'authorize_friend_input'`

- [ ] **Step 3: Implement in `server/mirror.py`**

```python
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
```

- [ ] **Step 4: Run — expect pass**

Run: `python -m pytest tests/test_mirror.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add server/mirror.py tests/test_mirror.py
git commit -m "feat(mirror): token+pin auth gate, station mode is view-only"
```

---

### Task 3: Viewer registry + fan-out relay

**Files:**
- Modify: `server/mirror.py`
- Test: `tests/test_mirror.py`

- [ ] **Step 1: Write the failing tests** (use a fake async websocket)

```python
# append to tests/test_mirror.py
import pytest

class FakeWS:
    def __init__(self, fail=False):
        self.sent_bytes = []
        self.sent_json = []
        self.fail = fail
    async def send_bytes(self, data):
        if self.fail:
            raise RuntimeError("dead socket")
        self.sent_bytes.append(data)
    async def send_json(self, obj):
        if self.fail:
            raise RuntimeError("dead socket")
        self.sent_json.append(obj)

@pytest.fixture(autouse=True)
def _reset_mirror_state():
    mirror.reset_state()
    yield
    mirror.reset_state()

@pytest.mark.asyncio
async def test_add_viewer_signals_capture_start_on_first_only():
    station = FakeWS()
    mirror.set_active_ws_getter(lambda: station)
    v1, v2 = FakeWS(), FakeWS()
    await mirror.add_viewer(v1)
    await mirror.add_viewer(v2)
    # Only the first viewer should trigger a capture-start signal to the station.
    starts = [m for m in station.sent_json if m.get("type") == "mirror_request" and m.get("active")]
    assert len(starts) == 1
    assert mirror.viewer_count() == 2

@pytest.mark.asyncio
async def test_remove_last_viewer_signals_capture_stop():
    station = FakeWS()
    mirror.set_active_ws_getter(lambda: station)
    v1 = FakeWS()
    await mirror.add_viewer(v1)
    await mirror.remove_viewer(v1)
    stops = [m for m in station.sent_json if m.get("type") == "mirror_request" and not m.get("active")]
    assert len(stops) == 1
    assert mirror.viewer_count() == 0

@pytest.mark.asyncio
async def test_broadcast_sends_to_all_and_drops_dead():
    mirror.set_active_ws_getter(lambda: None)
    good, dead = FakeWS(), FakeWS(fail=True)
    await mirror.add_viewer(good)
    await mirror.add_viewer(dead)
    await mirror.broadcast(b"\x01frame")
    assert good.sent_bytes == [b"\x01frame"]
    # Dead viewer is auto-removed on send failure.
    assert mirror.viewer_count() == 1
```

(Requires `pytest-asyncio`. If not configured, add `asyncio_mode = auto` to `pytest.ini`/`pyproject` or mark accordingly. Check `python -m pytest --co -q tests/test_mirror.py` collects them.)

- [ ] **Step 2: Run — expect failure**

Run: `python -m pytest tests/test_mirror.py -k viewer -v`
Expected: FAIL — missing `reset_state`/`set_active_ws_getter`/`add_viewer`.

- [ ] **Step 3: Implement registry + relay in `server/mirror.py`**

```python
_viewers = set()
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
```

- [ ] **Step 4: Run — expect pass**

Run: `python -m pytest tests/test_mirror.py -v`
Expected: PASS (7 passed)

- [ ] **Step 5: Commit**

```bash
git add server/mirror.py tests/test_mirror.py
git commit -m "feat(mirror): viewer registry, capture start/stop signal, fan-out relay"
```

---

### Task 4: Client frame encoder (pure function)

**Files:**
- Create: `client/mirror_sender.py`
- Test: `tests/test_mirror.py`

- [ ] **Step 1: Confirm Pillow is available in the client venv**

Run: `python -c "import PIL; print(PIL.__version__)"`
Expected: prints a version. If it errors, add to setup: `pip install Pillow` and note it in `requirements`/`setup.bat`.

- [ ] **Step 2: Write the failing test**

```python
# append to tests/test_mirror.py
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "client"))
import mirror_sender

def test_encode_frame_downscales_and_returns_jpeg():
    # 1000x500 solid-red raw RGB buffer
    w, h = 1000, 500
    rgb = bytes([255, 0, 0]) * (w * h)
    out = mirror_sender.encode_frame(rgb, (w, h), max_width=640, quality=55)
    assert isinstance(out, (bytes, bytearray))
    assert out[:2] == b"\xff\xd8"          # JPEG SOI marker
    # Decoding it back yields the downscaled width.
    from PIL import Image
    import io
    img = Image.open(io.BytesIO(out))
    assert img.width == 640
    assert img.height == 320               # aspect preserved (500 * 640/1000)

def test_encode_frame_no_upscale_when_small():
    w, h = 300, 200
    rgb = bytes([0, 128, 0]) * (w * h)
    out = mirror_sender.encode_frame(rgb, (w, h), max_width=640, quality=55)
    from PIL import Image
    import io
    img = Image.open(io.BytesIO(out))
    assert img.width == 300                # never upscales
```

- [ ] **Step 3: Run — expect failure**

Run: `python -m pytest tests/test_mirror.py -k encode_frame -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'mirror_sender'`

- [ ] **Step 4: Create `client/mirror_sender.py` with the encoder**

```python
"""Client-side mirror sender: push tagged JPEG frames + audio to the server.

Additive and opt-in. All network/encoding work is gated behind an 'active'
flag and wrapped so it can never break the pygame render loop.
"""
import io
import logging
import queue
import threading

from PIL import Image

logger = logging.getLogger(__name__)
DEBUG_MIRROR = True

TAG_VIDEO = b"\x01"
TAG_AUDIO = b"\x02"


def encode_frame(rgb_bytes: bytes, size, max_width: int = 640, quality: int = 55) -> bytes:
    """RGB pixel buffer -> downscaled JPEG bytes. Never upscales."""
    w, h = size
    img = Image.frombytes("RGB", (w, h), rgb_bytes)
    if w > max_width:
        new_h = max(1, int(h * max_width / w))
        img = img.resize((max_width, new_h), Image.BILINEAR)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()
```

- [ ] **Step 5: Run — expect pass**

Run: `python -m pytest tests/test_mirror.py -k encode_frame -v`
Expected: PASS (2 passed)

- [ ] **Step 6: Commit**

```bash
git add client/mirror_sender.py tests/test_mirror.py
git commit -m "feat(mirror): client frame encoder (downscale + jpeg)"
```

---

### Task 5: `MirrorSender` threaded class

**Files:**
- Modify: `client/mirror_sender.py`
- Test: `tests/test_mirror.py`

- [ ] **Step 1: Write the failing tests** (logic only — no real socket)

```python
# append to tests/test_mirror.py
def test_sender_inactive_drops_everything():
    s = mirror_sender.MirrorSender("ws://x/mirror_ingest")
    # Not started/active: submit must be a no-op and not raise.
    s.submit_rgb(b"\x00\x00\x00", (1, 1))
    s.send_audio(b"RIFFxxxx")
    assert s._latest is None
    assert s._audio_q.empty()

def test_sender_active_stores_latest_frame_and_queues_audio():
    s = mirror_sender.MirrorSender("ws://x/mirror_ingest")
    s._active = True  # simulate "viewer connected" without opening a socket
    s.submit_rgb(b"\x01\x02\x03", (1, 1))
    s.submit_rgb(b"\x04\x05\x06", (1, 1))   # newer replaces older (1-slot)
    assert s._latest == (b"\x04\x05\x06", (1, 1))
    s.send_audio(b"RIFFdata")
    assert s._audio_q.get_nowait() == b"RIFFdata"
```

- [ ] **Step 2: Run — expect failure**

Run: `python -m pytest tests/test_mirror.py -k sender -v`
Expected: FAIL — `AttributeError: module 'mirror_sender' has no attribute 'MirrorSender'`

- [ ] **Step 3: Implement `MirrorSender` in `client/mirror_sender.py`**

```python
class MirrorSender:
    """Owns a background thread that connects to /mirror_ingest and sends
    tagged frames (latest-only) + audio (queued). Activated by the server's
    mirror_request signal via start()/stop()."""

    def __init__(self, ingest_url: str, max_width: int = 640, quality: int = 55, fps: int = 10):
        self.ingest_url = ingest_url
        self.max_width = max_width
        self.quality = quality
        self.frame_interval = 1.0 / max(1, fps)
        self._active = False
        self._latest = None          # (rgb_bytes, (w, h)) — 1-slot, newest wins
        self._latest_lock = threading.Lock()
        self._audio_q = queue.Queue(maxsize=32)
        self._stop = threading.Event()
        self._thread = None
        self._ws = None

    # --- called from the pygame render thread (must be cheap + never raise) ---
    def submit_rgb(self, rgb_bytes, size):
        if not self._active:
            return
        try:
            with self._latest_lock:
                self._latest = (rgb_bytes, size)
        except Exception:
            pass

    def send_audio(self, wav_bytes):
        if not self._active or not wav_bytes:
            return
        try:
            self._audio_q.put_nowait(wav_bytes)
        except queue.Full:
            pass

    # --- lifecycle (called from client wiring on mirror_request) ---
    def start(self):
        if self._active:
            return
        self._stop.clear()
        self._active = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        if DEBUG_MIRROR:
            logger.info("[mirror] sender started")

    def stop(self):
        self._active = False
        self._stop.set()
        try:
            if self._ws:
                self._ws.close()
        except Exception:
            pass
        self._ws = None
        with self._latest_lock:
            self._latest = None
        if DEBUG_MIRROR:
            logger.info("[mirror] sender stopped")

    def _run(self):
        import time
        import websocket  # websocket-client, already a client dependency
        try:
            self._ws = websocket.create_connection(self.ingest_url, timeout=5)
        except Exception as e:
            logger.error(f"[mirror] ingest connect failed (mirror disabled): {e}")
            self._active = False
            return
        last_frame = 0.0
        while not self._stop.is_set():
            sent_anything = False
            # Drain audio first (don't drop speech).
            try:
                while True:
                    wav = self._audio_q.get_nowait()
                    self._ws.send_binary(TAG_AUDIO + wav)
                    sent_anything = True
            except queue.Empty:
                pass
            except Exception as e:
                logger.error(f"[mirror] audio send failed: {e}")
                break
            # Then at most one frame per interval.
            now = time.time()
            if now - last_frame >= self.frame_interval:
                with self._latest_lock:
                    item = self._latest
                    self._latest = None
                if item is not None:
                    try:
                        jpeg = encode_frame(item[0], item[1], self.max_width, self.quality)
                        self._ws.send_binary(TAG_VIDEO + jpeg)
                        last_frame = now
                        sent_anything = True
                    except Exception as e:
                        logger.error(f"[mirror] frame send failed: {e}")
                        break
            if not sent_anything:
                time.sleep(0.01)
        try:
            if self._ws:
                self._ws.close()
        except Exception:
            pass
        self._ws = None
```

- [ ] **Step 4: Run — expect pass**

Run: `python -m pytest tests/test_mirror.py -k sender -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add client/mirror_sender.py tests/test_mirror.py
git commit -m "feat(mirror): MirrorSender thread (latest-frame + audio queue, tagged binary)"
```

---

### Task 6: Route `mirror_request` in the WS client

**Files:**
- Modify: `client/ws_client.py`
- Test: `tests/test_mirror.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_mirror.py
import json as _json
from ws_client import MarioWSClient  # client dir already on sys.path

def test_ws_client_routes_mirror_request():
    c = MarioWSClient("ws://localhost:8765/ws")
    got = {}
    c.on_mirror_request = lambda active: got.update(active=active)
    c._on_message(None, _json.dumps({"type": "mirror_request", "active": True}))
    assert got == {"active": True}
    c._on_message(None, _json.dumps({"type": "mirror_request", "active": False}))
    assert got == {"active": False}
```

- [ ] **Step 2: Run — expect failure**

Run: `python -m pytest tests/test_mirror.py -k mirror_request -v`
Expected: FAIL — `AttributeError: 'MarioWSClient' object has no attribute 'on_mirror_request'`

- [ ] **Step 3: Add the callback default**

In `client/ws_client.py`, in `__init__` after `self.on_character_switched = None` (line ~33), add:

```python
        self.on_mirror_request = None   # Called with (active: bool) — start/stop mirror capture
```

- [ ] **Step 4: Add the message branch**

In `client/ws_client.py` `_on_message`, after the `character_switched` branch (line ~182), add:

```python
                elif msg_type == "mirror_request":
                    active = bool(data.get("active", False))
                    if DEBUG_WS:
                        logger.info(f"[DEBUG_WS] mirror_request active={active}")
                    if self.on_mirror_request:
                        self.on_mirror_request(active)
```

- [ ] **Step 5: Run — expect pass**

Run: `python -m pytest tests/test_mirror.py -k mirror_request -v`
Expected: PASS (1 passed)

- [ ] **Step 6: Commit**

```bash
git add client/ws_client.py tests/test_mirror.py
git commit -m "feat(mirror): ws client routes mirror_request -> on_mirror_request"
```

---

### Task 7: Add the `on_frame_ready` hook to the display

**Files:**
- Modify: `client/mario_display.py`

(No unit test — needs a live pygame surface; verified in the manual integration task. Keep the change tiny and guard-checked so idle cost is one attribute test.)

- [ ] **Step 1: Add the callback default in `MarioDisplay.__init__`**

In `client/mario_display.py`, inside `def __init__(self):` (line ~214), add near the other callback attributes:

```python
        self.on_frame_ready = None   # Optional: called with the rendered Surface after flip (mirror)
```

- [ ] **Step 2: Fire it after the flip**

In `client/mario_display.py`, the `update()` method ends with `pygame.display.flip()` at line ~2033. Immediately after it add:

```python
        pygame.display.flip()

        # Mirror hook — additive, never breaks the loop.
        if self.on_frame_ready is not None:
            try:
                self.on_frame_ready(self._screen)
            except Exception:
                pass
```

(Leave the existing `flip()` line; only add the guarded hook below it.)

- [ ] **Step 3: Sanity import check**

Run: `python -c "import ast; ast.parse(open('client/mario_display.py', encoding='utf-8').read()); print('ok')"`
Expected: prints `ok`

- [ ] **Step 4: Commit**

```bash
git add client/mario_display.py
git commit -m "feat(mirror): MarioDisplay.on_frame_ready hook fired after flip"
```

---

### Task 8: Extract a reusable text-dispatch helper in the server

**Files:**
- Modify: `server/main.py`

(Refactor only — `/admin/simulate_text` and the new `/friend/say` must share one code path. No behavior change to `simulate_text`.)

- [ ] **Step 1: Add the helper near `admin_simulate_text` (above it, ~line 1847)**

```python
async def _dispatch_user_text(text: str):
    """Run a text input through the exact same pipeline as a real typed message,
    sending the response to the active pygame client. Returns a status dict.

    Shared by /admin/simulate_text and /friend/say."""
    global _current_response_task
    if not text:
        return {"status": "error", "message": "Text required"}
    if not _active_ws:
        return {"status": "error", "message": "No active WebSocket connection"}
    if _current_response_task and not _current_response_task.done():
        logger.info(f"[INTERRUPT] Cancelling previous response for input: '{text[:50]}'")
        _current_response_task.cancel()
        try:
            await _active_ws.send_json({"type": "clear_audio"})
        except Exception:
            pass
    async with _state_lock:
        state_current["_last_text_input_time"] = 0.0
        state_current["_user_request_active"] = True
        state_current["_last_user_msg_time"] = time.time()
    _current_response_task = asyncio.create_task(_text_input_task(_active_ws, text))
    return {"status": "ok", "message": f"Dispatched: {text[:50]}"}
```

- [ ] **Step 2: Replace the body of `admin_simulate_text` to delegate**

Change the existing `admin_simulate_text` (lines ~1848-1871) body to:

```python
@app.post("/admin/simulate_text")
async def admin_simulate_text(request_body: dict = {}):
    """Admin: Simulate text input as if a user typed it (uses active WS connection)."""
    return await _dispatch_user_text(request_body.get("text", ""))
```

- [ ] **Step 3: Syntax check**

Run: `python -c "import ast; ast.parse(open('server/main.py', encoding='utf-8').read()); print('ok')"`
Expected: prints `ok`

- [ ] **Step 4: Commit**

```bash
git add server/main.py
git commit -m "refactor(server): extract _dispatch_user_text shared by simulate_text"
```

---

### Task 9: Register `/mirror` + `/mirror_ingest` WebSocket endpoints

**Files:**
- Modify: `server/main.py`

- [ ] **Step 1: Import mirror and wire the active-ws getter at startup**

Near the other server imports at the top of `server/main.py`, add:

```python
import mirror as mirror_relay
```

Then, right after the line `app = FastAPI(title="Mario AI Server", lifespan=lifespan)` (line ~1151), add:

```python
mirror_relay.set_active_ws_getter(lambda: _active_ws)
_MIRROR_CFG = mirror_relay.get_mirror_config(_full_config) if "_full_config" in dir() else mirror_relay.get_mirror_config({})
```

(If the loaded config object has a different name in `main.py`, use that name instead of `_full_config`. Find it by searching for where `config.json` is read — reuse that dict. The goal: `_MIRROR_CFG` holds the merged mirror config, and `mirror_relay._control_mode_default` is seeded below.)

- [ ] **Step 2: Seed the runtime control mode**

Add to `server/mirror.py` (module level + helpers):

```python
_control_mode = "station"

def set_control_mode(mode: str):
    global _control_mode
    _control_mode = "remote" if mode == "remote" else "station"

def get_control_mode() -> str:
    return _control_mode
```

And in `reset_state()` add `global _control_mode` and `_control_mode = "station"`.

Then in `main.py` after `_MIRROR_CFG = ...`:

```python
mirror_relay.set_control_mode(_MIRROR_CFG.get("control_mode", "station"))
```

- [ ] **Step 3: Add the two WebSocket endpoints** (place them near the existing `@app.websocket("/ws")`, ~line 2386)

```python
@app.websocket("/mirror_ingest")
async def mirror_ingest_endpoint(ws: WebSocket):
    """The pygame client pushes tagged binary (frames + audio) here; we relay verbatim."""
    await ws.accept()
    try:
        while True:
            msg = await ws.receive()
            data = msg.get("bytes")
            if data is None:
                # ignore text/keepalive frames
                if msg.get("type") == "websocket.disconnect":
                    break
                continue
            await mirror_relay.broadcast(data)
    except Exception as e:
        print(f"[mirror] ingest closed: {e}")


@app.websocket("/mirror")
async def mirror_viewer_endpoint(ws: WebSocket):
    """A browser viewer. Receives relayed frames + audio. Never drives the bot."""
    await ws.accept()
    await mirror_relay.add_viewer(ws)
    try:
        while True:
            # We don't expect inbound data from viewers; this keeps the socket open.
            await ws.receive_text()
    except Exception:
        pass
    finally:
        await mirror_relay.remove_viewer(ws)
```

- [ ] **Step 4: Syntax check**

Run: `python -c "import ast; ast.parse(open('server/main.py', encoding='utf-8').read()); print('ok')"`
Expected: prints `ok`

- [ ] **Step 5: Add a relay smoke test**

```python
# append to tests/test_mirror.py
@pytest.mark.asyncio
async def test_ingest_relay_is_verbatim():
    mirror.set_active_ws_getter(lambda: None)
    v = FakeWS()
    await mirror.add_viewer(v)
    await mirror.broadcast(b"\x02RIFFwav")   # audio tag relayed unchanged
    await mirror.broadcast(b"\x01\xff\xd8jpg")  # video tag relayed unchanged
    assert v.sent_bytes == [b"\x02RIFFwav", b"\x01\xff\xd8jpg"]
```

Run: `python -m pytest tests/test_mirror.py -v`
Expected: PASS (all)

- [ ] **Step 6: Commit**

```bash
git add server/main.py server/mirror.py tests/test_mirror.py
git commit -m "feat(mirror): /mirror viewer + /mirror_ingest relay endpoints, control mode state"
```

---

### Task 10: The `/friend` browser page

**Files:**
- Create: `server/static/friend.html`

- [ ] **Step 1: Create `server/static/friend.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
<title>Mario AI — Live</title>
<style>
  html,body{margin:0;background:#111;color:#eee;font-family:system-ui,Arial,sans-serif;height:100%}
  #wrap{display:flex;flex-direction:column;height:100%}
  #stage{flex:1;display:flex;align-items:center;justify-content:center;background:#000;min-height:0}
  canvas{max-width:100%;max-height:100%;image-rendering:auto}
  #bar{display:flex;gap:8px;padding:10px;background:#1b1b1b;align-items:center}
  #bar input{flex:1;padding:12px;font-size:16px;border-radius:8px;border:1px solid #444;background:#222;color:#fff}
  #bar button{padding:12px 16px;font-size:16px;border-radius:8px;border:0;background:#e23;color:#fff}
  #bar button:disabled{background:#555}
  #status{padding:6px 10px;font-size:12px;color:#999}
  #tapcover{position:fixed;inset:0;background:rgba(0,0,0,.85);display:flex;align-items:center;justify-content:center;font-size:22px;cursor:pointer}
  .hidden{display:none!important}
</style>
</head>
<body>
<div id="wrap">
  <div id="stage"><canvas id="screen" width="640" height="360"></canvas></div>
  <div id="status">connecting…</div>
  <div id="bar" class="hidden">
    <input id="pin" type="text" inputmode="numeric" placeholder="PIN" size="6" autocomplete="off">
    <input id="msg" type="text" placeholder="Say something…" autocomplete="off">
    <button id="send">Send</button>
  </div>
</div>
<div id="tapcover">Tap to start</div>
<script>
const qs = new URLSearchParams(location.search);
const TOKEN = qs.get("token") || "";
const CONTROL_MODE = "__CONTROL_MODE__";   // injected by the server
const canvas = document.getElementById("screen");
const ctx = canvas.getContext("2d");
const statusEl = document.getElementById("status");
const bar = document.getElementById("bar");
const tapcover = document.getElementById("tapcover");
let audioUnlocked = false;

// Audio playback queue (WAV blobs arriving over WS).
const audioEl = new Audio();
const audioQueue = [];
let playing = false;
function pumpAudio(){
  if (playing || audioQueue.length === 0) return;
  playing = true;
  const url = URL.createObjectURL(audioQueue.shift());
  audioEl.src = url;
  audioEl.play().catch(()=>{ playing = false; });
}
audioEl.onended = audioEl.onerror = () => { playing = false; pumpAudio(); };

tapcover.onclick = () => {
  audioUnlocked = true;
  audioEl.play().catch(()=>{});   // unlock autoplay with a user gesture
  tapcover.classList.add("hidden");
};

if (CONTROL_MODE === "remote") bar.classList.remove("hidden");

function connect(){
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(proto + "://" + location.host + "/mirror");
  ws.binaryType = "arraybuffer";
  ws.onopen = () => statusEl.textContent = "live";
  ws.onclose = () => { statusEl.textContent = "reconnecting…"; setTimeout(connect, 2000); };
  ws.onmessage = (ev) => {
    const buf = new Uint8Array(ev.data);
    const tag = buf[0];
    const payload = buf.subarray(1);
    if (tag === 0x01) {                       // video frame (JPEG)
      const blob = new Blob([payload], {type: "image/jpeg"});
      createImageBitmap(blob).then(bmp => {
        if (canvas.width !== bmp.width || canvas.height !== bmp.height){
          canvas.width = bmp.width; canvas.height = bmp.height;
        }
        ctx.drawImage(bmp, 0, 0);
        bmp.close && bmp.close();
      }).catch(()=>{});
    } else if (tag === 0x02) {                // audio (WAV)
      if (!audioUnlocked) return;             // wait for the tap gesture
      audioQueue.push(new Blob([payload], {type: "audio/wav"}));
      pumpAudio();
    }
  };
}
connect();

// Sending text (remote mode only).
const sendBtn = document.getElementById("send");
const msgEl = document.getElementById("msg");
const pinEl = document.getElementById("pin");
async function send(){
  const text = msgEl.value.trim();
  if (!text) return;
  sendBtn.disabled = true;
  try {
    const r = await fetch("/friend/say", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({text, token: TOKEN, pin: pinEl.value.trim()})
    });
    const j = await r.json();
    statusEl.textContent = (j.status === "ok") ? "live" : ("✋ " + (j.message || j.reason || "rejected"));
    if (j.status === "ok") msgEl.value = "";
  } catch(e) {
    statusEl.textContent = "send failed";
  } finally {
    sendBtn.disabled = false;
  }
}
sendBtn.onclick = send;
msgEl.addEventListener("keydown", e => { if (e.key === "Enter") send(); });
</script>
</body>
</html>
```

- [ ] **Step 2: Commit**

```bash
git add server/static/friend.html
git commit -m "feat(mirror): /friend browser page (canvas + audio + gated text box)"
```

---

### Task 11: Serve `/friend`, handle `/friend/say`, add mode toggle

**Files:**
- Modify: `server/main.py`

- [ ] **Step 1: Add the three routes** (place near `/admin/simulate_text`, ~line 1872)

```python
import os as _os

_FRIEND_HTML_PATH = _os.path.join(_os.path.dirname(__file__), "static", "friend.html")


@app.get("/friend")
async def friend_page():
    """Serve the remote mirror page with the current control mode injected."""
    try:
        with open(_FRIEND_HTML_PATH, encoding="utf-8") as f:
            html = f.read()
    except Exception:
        return HTMLResponse("<h1>mirror page missing</h1>", status_code=500)
    html = html.replace("__CONTROL_MODE__", mirror_relay.get_control_mode())
    return HTMLResponse(html)


@app.post("/friend/say")
async def friend_say(request_body: dict = {}):
    """Authenticated remote text input. Only drives the bot in 'remote' control mode."""
    text = (request_body.get("text") or "").strip()
    token = request_body.get("token") or ""
    pin = request_body.get("pin") or ""
    ok, reason = mirror_relay.authorize_friend_input(
        token, pin, _MIRROR_CFG, mirror_relay.get_control_mode()
    )
    if not ok:
        return {"status": "error", "reason": reason}
    if not text:
        return {"status": "error", "message": "Text required"}
    return await _dispatch_user_text(text)


@app.post("/admin/mirror_mode")
async def admin_mirror_mode(request_body: dict = {}):
    """Flip control mode at runtime: {'mode': 'station'|'remote'}."""
    mode = request_body.get("mode", "station")
    mirror_relay.set_control_mode(mode)
    return {"status": "ok", "control_mode": mirror_relay.get_control_mode()}
```

- [ ] **Step 2: Syntax check**

Run: `python -c "import ast; ast.parse(open('server/main.py', encoding='utf-8').read()); print('ok')"`
Expected: prints `ok`

- [ ] **Step 3: Commit**

```bash
git add server/main.py
git commit -m "feat(mirror): serve /friend, authed /friend/say, /admin/mirror_mode toggle"
```

---

### Task 12: Wire the mirror into the client

**Files:**
- Modify: `client/main.py`

- [ ] **Step 1: Import and construct `MirrorSender`**

Near the top imports of `client/main.py` (after `from ws_client import MarioWSClient`, line ~77) add:

```python
from mirror_sender import MirrorSender
```

In the client's `__init__`, after `self.ws = MarioWSClient(server_url)` (line ~91), add (reading mirror settings from `_full_config`):

```python
        _mcfg = (_full_config or {}).get("mirror", {})
        self.mirror = MirrorSender(
            ingest_url=_mcfg.get("ingest_url", server_url.replace("/ws", "/mirror_ingest")),
            max_width=_mcfg.get("max_width", 640),
            quality=_mcfg.get("jpeg_quality", 55),
            fps=_mcfg.get("fps", 10),
        )
        self._mirror_enabled = bool(_mcfg.get("enabled", False))
```

- [ ] **Step 2: Wire the `mirror_request` callback**

Where the other `self.ws.on_*` callbacks are set (line ~115-117), add:

```python
        self.ws.on_mirror_request = self._on_mirror_request
```

And add the handler method to the client class:

```python
    def _on_mirror_request(self, active: bool):
        """Server signals a viewer connected/left — start/stop capture."""
        if not self._mirror_enabled:
            return
        try:
            if active:
                self.mirror.start()
                self.display.on_frame_ready = self._capture_frame
            else:
                self.display.on_frame_ready = None
                self.mirror.stop()
        except Exception as e:
            if DEBUG_CLIENT:
                logger.error(f"[DEBUG_CLIENT] mirror_request handling failed: {e}")

    def _capture_frame(self, surface):
        """Called by the display after flip when the mirror is active. Cheap + safe."""
        try:
            import pygame
            try:
                rgb = pygame.image.tobytes(surface, "RGB")
            except AttributeError:
                rgb = pygame.image.tostring(surface, "RGB")  # older pygame
            self.mirror.submit_rgb(rgb, surface.get_size())
        except Exception:
            pass
```

- [ ] **Step 3: Tee audio to the mirror**

In `_on_mario_audio` (line ~349), right after `self.audio_playback.play(wav_bytes)`, add:

```python
        self.audio_playback.play(wav_bytes)
        self.mirror.send_audio(wav_bytes)   # tee to remote viewers (no-op if inactive)
```

In `_on_audio_chunk`, after the chunk is handed to playback (find the `self.audio_playback.play(...)`/queue call in that method), add the same line:

```python
        self.mirror.send_audio(wav_bytes)   # tee streaming chunk to remote viewers
```

- [ ] **Step 4: Stop the mirror cleanly on shutdown**

In the client shutdown path, near `self.audio_playback.stop()` (line ~214), add:

```python
        try:
            self.mirror.stop()
        except Exception:
            pass
```

- [ ] **Step 5: Syntax check**

Run: `python -c "import ast; ast.parse(open('client/main.py', encoding='utf-8').read()); print('ok')"`
Expected: prints `ok`

- [ ] **Step 6: Commit**

```bash
git add client/main.py
git commit -m "feat(mirror): wire MirrorSender into client (capture + audio tee + lifecycle)"
```

---

### Task 13: Runbook + tunnel launcher

**Files:**
- Create: `docs/REMOTE_MIRROR.md`
- Create: `start_tunnel.bat`

- [ ] **Step 1: Create `docs/REMOTE_MIRROR.md`**

```markdown
# Remote Mirror — Letting Friends Watch / Test Remotely

Friends open ONE public link in any phone browser. They see the **real** pygame
client live and (in testing mode) can type to drive it. No installs for them.

## One-time setup (your PC)
1. Install cloudflared: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/
2. In `config.json` set a real `mirror.token` and `mirror.pin` (the defaults are placeholders).

## Run a session
1. Start the server + pygame client as usual (`start_server.bat`, then the client).
2. Start the tunnel: `start_tunnel.bat` (or `cloudflared tunnel --url http://localhost:8765`).
3. cloudflared prints a public URL like `https://random-words.trycloudflare.com`.
4. Share this with friends: `https://random-words.trycloudflare.com/friend?token=YOUR_TOKEN`
   and tell them the PIN out-of-band.

## Modes
- **Party (default, `control_mode: "station"`):** friends are VIEW-ONLY. The text box is hidden.
- **Testing (`control_mode: "remote"`):** the friend page shows a text box; with the right
  token+PIN, whoever is on the page drives the bot. There is only ever ONE controller — the
  page funnels into the same single conversation. Multiple people should share one page/phone.

Flip mode at runtime without restart:
`curl -X POST http://localhost:8765/admin/mirror_mode -H "Content-Type: application/json" -d "{\"mode\":\"remote\"}"`

## Safety
- The link is public — anyone with it + the PIN can drive the bot in `remote` mode. Use a
  strong token/PIN, and switch back to `station` for the actual party.
- Capture only runs while at least one viewer is connected — zero cost otherwise.
- The pygame app runs normally even if the tunnel/mirror is down.
```

- [ ] **Step 2: Create `start_tunnel.bat`**

```bat
@echo off
echo Starting Cloudflare tunnel to http://localhost:8765 ...
echo Share the printed https URL as:  https://THAT-URL/friend?token=YOUR_TOKEN
cloudflared tunnel --url http://localhost:8765
```

- [ ] **Step 3: Commit**

```bash
git add docs/REMOTE_MIRROR.md start_tunnel.bat
git commit -m "docs(mirror): remote mirror runbook + tunnel launcher"
```

---

### Task 14: Manual integration verification (per `.claude/rules/testing.md`)

**Files:** none (verification only)

This feature's WS plumbing, HTML, and browser audio cannot be unit-tested — verify by hand, with **audio confirmation** as the testing rules require.

- [ ] **Step 1: Pygame independence (mirror OFF)**

Set `config.json` → `mirror.enabled: false`. Start server + client. Confirm the app behaves exactly as before (greeting, a text message, audio plays — check client log `[audio_playback] _play_wav: playing` AND `_play_wav: done`). No mirror log lines appear.

- [ ] **Step 2: Pygame independence (mirror ON, no viewer)**

Set `mirror.enabled: true`, restart. With NO browser connected, confirm: app still behaves identically, `[mirror] sender started` does NOT appear, no frame encoding happens. (`on_frame_ready` stays `None` until a viewer connects.)

- [ ] **Step 3: View-only mirror (station mode)**

Keep `control_mode: "station"`. Start `cloudflared` (or just open `http://localhost:8765/friend?token=YOUR_TOKEN` locally). Confirm:
- Client log shows `[DEBUG_WS] mirror_request active=True` and `[mirror] sender started`.
- The browser canvas shows the live pygame window updating (~10fps).
- Speak a line to the bot locally → the browser **plays the audio** after you tap "Tap to start".
- The text box is **hidden** (view-only).
- Close the browser tab → client log shows `mirror_request active=False` and `[mirror] sender stopped`.

- [ ] **Step 4: Remote control (remote mode)**

Flip to remote: `curl -X POST http://localhost:8765/admin/mirror_mode -d "{\"mode\":\"remote\"}" -H "Content-Type: application/json"`. Reload `/friend`. Confirm:
- Text box is visible. Enter the PIN, type a message, Send.
- **The real pygame window** renders the response (sprite + speech bubble) and plays TTS — verify client log `mario says:` matches the bubble, and `_play_wav: playing` → `_play_wav: done`.
- The browser mirror shows the same frames + plays the same audio.
- Wrong PIN or wrong token → `/friend/say` returns `{"status":"error","reason":"bad_credentials"}` and nothing happens.
- In `station` mode, `/friend/say` returns `reason: "view_only"` (no drive).

- [ ] **Step 5: Character-leak check (march7th is active)**

Per testing rules, since the active character is `march7th` (not Mario): in Step 4 send "Who are you?", "Do you know Mario?", "Tell me a fun fact!" and confirm ZERO Mario references in the spoken audio text and the bubble.

- [ ] **Step 6: Isolation check**

While a viewer is connected and audio is playing, kill the browser tab and the tunnel. Confirm the pygame client + server keep running normally and the local conversation/audio is unaffected.

- [ ] **Step 7: Full test suite still green**

Run: `python -m pytest tests/test_mirror.py tests/test_pygame_client_controls.py -v`
Expected: all pass. Then run the broader suite if time permits: `python -m pytest -q`.

---

## Self-Review (completed by plan author)

**Spec coverage:**
- Pygame independence (req #1) → Tasks 7, 12 guards + Task 14 Steps 1-2, 6. ✓
- Frame capture, gated, ~10fps, downscale → Tasks 4, 5, 7, 12. ✓
- Mirror hub + audio tee, viewers separate from `_active_ws` → Tasks 3, 9, 12 (client tees audio). ✓
- `/friend` page (canvas + audio + text) → Tasks 10, 11. ✓
- `control_mode` station/remote toggle + hot flip → Tasks 9, 11. ✓
- Auth (token + PIN), wraps simulate_text → Tasks 2, 8, 11. ✓
- Reach via Cloudflare Tunnel, HTTPS → Task 13. ✓
- "Always one real pygame client = `_active_ws`" → `_dispatch_user_text` requires `_active_ws` (Task 8). ✓
- Phase 2 (voice) → intentionally out of scope; not in this plan. ✓

**Placeholder scan:** `__CONTROL_MODE__` in the HTML is an intentional server-injected token (replaced in Task 11), not a plan placeholder. The `_full_config` name in Tasks 9/12 is flagged to verify against the real loaded-config variable name in each file. No TODO/TBD steps. ✓

**Type/name consistency:** `MirrorSender`, `submit_rgb`, `send_audio`, `start`/`stop`, `encode_frame`, `on_frame_ready`, `on_mirror_request`, `add_viewer`/`remove_viewer`/`broadcast`/`viewer_count`/`get_control_mode`/`set_control_mode`/`authorize_friend_input`/`get_mirror_config`, tags `0x01`/`0x02` — used consistently across server, client, tests, and HTML. ✓
