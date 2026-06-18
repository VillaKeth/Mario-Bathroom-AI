# Mario Debug MCP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give Claude Code an MCP server that can see the pygame screen, verify played audio, tail server+client logs, read on-screen state, and inject input (a guest speaking / appearing) into the running Mario AI app.

**Architecture:** A standalone FastMCP server (`mcp_mario_debug/`) bridges over `127.0.0.1` to the existing FastAPI server (`:8765`, extended with a log ring + STT-inject endpoint) and a new flag-gated debug HTTP server inside the pygame client (`:8770`), with an OS-screenshot fallback. The debug surface is off unless `MARIO_DEBUG=1` and binds localhost only.

**Tech Stack:** Python, FastMCP (`mcp` SDK), `httpx`, `mss`, `pillow`, stdlib `http.server`, pygame, numpy, FastAPI.

**Branch:** `feat/debug-mcp`. **Spec:** `docs/superpowers/specs/2026-06-18-mario-debug-mcp-design.md`.

---

## File Structure

| File | Responsibility | New/Modify |
|------|----------------|-----------|
| `mcp_mario_debug/__init__.py` | package marker | New |
| `mcp_mario_debug/bridge.py` | pure HTTP/logic layer: calls `:8765`/`:8770`, OS-grab fallback, returns dicts/png bytes | New |
| `mcp_mario_debug/server.py` | thin FastMCP tool defs delegating to `bridge` | New |
| `mcp_mario_debug/requirements.txt` | `mcp`, `httpx`, `mss`, `pillow` | New |
| `mcp_mario_debug/README.md` | setup + tool list | New |
| `server/debug_ring.py` | pure `LogRing` (deque + logging.Handler + filtered snapshot) | New |
| `server/main.py` | install LogRing; `GET /debug/log`; `POST /admin/inject_audio`; gate `/debug/*` | Modify |
| `client/audio_playback.py` | `analyze_wav()` helper + clip ring + `audio_log_snapshot()`; thread `text` through `play()` | Modify |
| `client/debug_server.py` | stdlib http.server, pure `route()` dispatcher, localhost+flag gate | New |
| `client/mario_display.py` | `debug_state()` + frame publish (`latest_frame_png()`) | Modify |
| `client/presence.py` | `inject_frame()` — run detector on an image, fire real callbacks | Modify |
| `client/main.py` | start `debug_server` under `MARIO_DEBUG`, pass `self` | Modify |
| `.mcp.json` | register `mario-debug` stdio server | Modify |
| `tests/test_debug_ring.py` | LogRing unit tests | New |
| `tests/test_audio_analyze.py` | analyze_wav + ring unit tests | New |
| `tests/test_debug_server_routing.py` | client `route()` unit tests (fake provider) | New |
| `tests/test_mcp_bridge.py` | bridge unit tests (httpx MockTransport) | New |

**Decomposition note:** wav analysis, log ring, and the client request router are extracted as **pure functions/classes** so they unit-test without booting `server/main.py` (heavy) or opening sockets/pygame.

---

## Task 1: Server log ring (pure, testable)

**Files:**
- Create: `server/debug_ring.py`
- Test: `tests/test_debug_ring.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_debug_ring.py
import logging
from server.debug_ring import LogRing


def test_ring_caps_and_snapshots_newest_last():
    ring = LogRing(maxlen=3)
    for i in range(5):
        ring.append(f"line{i}", level="INFO")
    snap = ring.snapshot()
    assert [l["msg"] for l in snap] == ["line2", "line3", "line4"]


def test_grep_filter_is_case_insensitive():
    ring = LogRing(maxlen=10)
    ring.append("Sovits started", level="INFO")
    ring.append("edge fallback", level="WARNING")
    assert [l["msg"] for l in ring.snapshot(grep="SOVITS")] == ["Sovits started"]


def test_level_filter_minimum_severity():
    ring = LogRing(maxlen=10)
    ring.append("debugging", level="DEBUG")
    ring.append("a warning", level="WARNING")
    out = ring.snapshot(level="WARNING")
    assert [l["msg"] for l in out] == ["a warning"]


def test_handler_feeds_ring():
    ring = LogRing(maxlen=10)
    logger = logging.getLogger("test_feed")
    logger.setLevel(logging.INFO)
    logger.addHandler(ring.handler())
    logger.info("hello from logger")
    assert any("hello from logger" in l["msg"] for l in ring.snapshot())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv\Scripts\python.exe -m pytest tests/test_debug_ring.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'server.debug_ring'`

- [ ] **Step 3: Write minimal implementation**

```python
# server/debug_ring.py
"""In-memory log ring for the debug MCP. Pure + thread-safe; no FastAPI import."""
import logging
import threading
from collections import deque

_LEVELS = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40, "CRITICAL": 50}


class LogRing:
    def __init__(self, maxlen: int = 2000):
        self._dq = deque(maxlen=maxlen)
        self._lock = threading.Lock()

    def append(self, msg: str, level: str = "INFO", name: str = ""):
        with self._lock:
            self._dq.append({"msg": msg, "level": level.upper(), "name": name})

    def snapshot(self, n: int = 200, grep: str = "", level: str = "DEBUG"):
        floor = _LEVELS.get(level.upper(), 0)
        with self._lock:
            items = list(self._dq)
        if grep:
            g = grep.lower()
            items = [l for l in items if g in l["msg"].lower()]
        items = [l for l in items if _LEVELS.get(l["level"], 0) >= floor]
        return items[-n:]

    def handler(self) -> logging.Handler:
        ring = self

        class _RingHandler(logging.Handler):
            def emit(self, record):
                try:
                    ring.append(record.getMessage(), record.levelname, record.name)
                except Exception:
                    pass

        h = _RingHandler()
        h.setLevel(logging.DEBUG)
        return h
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv\Scripts\python.exe -m pytest tests/test_debug_ring.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add server/debug_ring.py tests/test_debug_ring.py
git commit -m "feat(debug-mcp): pure LogRing for server log tailing

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 2: Server endpoints — `/debug/log` + `/admin/inject_audio` + gating

**Files:**
- Modify: `server/main.py` (logging setup near line 85; add endpoints near the other `/admin/*` routes, e.g. after `/admin/simulate_text` at line 1970)

- [ ] **Step 1: Install the ring at import time**

After `logging.basicConfig(...)` (line 85) add:

```python
import debug_ring as _debug_ring_mod
DEBUG_ENABLED = os.environ.get("MARIO_DEBUG", "") == "1"
_LOG_RING = _debug_ring_mod.LogRing(maxlen=3000)
logging.getLogger().addHandler(_LOG_RING.handler())  # root: captures all module logs
```

- [ ] **Step 2: Add the endpoints**

Insert after `admin_simulate_text` (line 1970):

```python
def _require_debug():
    """Debug routes are localhost-only AND off unless MARIO_DEBUG=1."""
    return DEBUG_ENABLED


@app.get("/debug/log")
async def debug_log(n: int = 200, grep: str = "", level: str = "DEBUG"):
    if not _require_debug():
        return {"status": "error", "message": "debug disabled (set MARIO_DEBUG=1)"}
    return {"status": "ok", "lines": _LOG_RING.snapshot(n=n, grep=grep, level=level)}


@app.post("/admin/inject_audio")
async def admin_inject_audio(request_body: dict = {}):
    """Simulate a guest SPEAKING: a base64 WAV -> STT -> normal reply pipeline."""
    api_key = GAME_CONFIG.get("admin_api_key", "")
    if api_key and request_body.get("api_key") != api_key:
        return {"status": "error", "message": "Invalid API key"}
    b64 = request_body.get("wav_b64") or ""
    try:
        wav_bytes = base64.b64decode(b64)
    except Exception as e:
        return {"status": "error", "message": f"bad base64: {e}"}
    try:
        with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
            sr = wf.getframerate()
            pcm = wf.readframes(wf.getnframes())
    except Exception as e:
        return {"status": "error", "message": f"bad wav: {e}"}
    text = stt.transcribe(pcm, sr)
    if not text:
        return {"status": "ok", "transcript": "", "note": "STT returned empty"}
    await _dispatch_user_text(text)
    return {"status": "ok", "transcript": text}
```

Add `import io` and `import wave` at the top of `server/main.py` if not present (check the import block lines 15-47).

- [ ] **Step 3: Write the endpoint test (TestClient, stt mocked)**

```python
# tests/test_inject_audio_endpoint.py
import base64, io, wave, os
import pytest


def _synth_wav(sr=16000, secs=0.2):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sr)
        wf.writeframes(b"\x00\x01" * int(sr * secs))
    return buf.getvalue()


@pytest.mark.skipif(os.environ.get("MARIO_SKIP_HEAVY") == "1", reason="boots main.py")
def test_inject_audio_runs_stt_and_dispatches(monkeypatch):
    os.environ["MARIO_DEBUG"] = "1"
    import server.main as m
    from fastapi.testclient import TestClient
    monkeypatch.setattr(m, "stt", type("S", (), {"transcribe": staticmethod(lambda pcm, sr: "hello mario")}))
    dispatched = {}
    async def fake_dispatch(text):
        dispatched["text"] = text
        return {"status": "ok"}
    monkeypatch.setattr(m, "_dispatch_user_text", fake_dispatch)
    m.GAME_CONFIG["admin_api_key"] = ""  # no key for test
    client = TestClient(m.app)
    r = client.post("/admin/inject_audio", json={"wav_b64": base64.b64encode(_synth_wav()).decode()})
    assert r.json()["transcript"] == "hello mario"
    assert dispatched["text"] == "hello mario"
```

- [ ] **Step 4: Run tests**

Run: `venv\Scripts\python.exe -m pytest tests/test_inject_audio_endpoint.py -v`
Expected: PASS (or SKIP if `MARIO_SKIP_HEAVY=1`). If import of `server.main` is too heavy/slow in CI, keep the skip guard; the bridge test (Task 8) covers the call path with a mock server.

- [ ] **Step 5: Commit**

```bash
git add server/main.py tests/test_inject_audio_endpoint.py
git commit -m "feat(debug-mcp): /debug/log + /admin/inject_audio (gated by MARIO_DEBUG)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 3: Client audio analysis helper + clip ring

**Files:**
- Modify: `client/audio_playback.py`
- Test: `tests/test_audio_analyze.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_audio_analyze.py
import io, wave, numpy as np
from client.audio_playback import analyze_wav, AudioPlayback


def _wav(sr=32000, secs=0.5, amp=0.5):
    n = int(sr * secs)
    samples = (np.ones(n) * amp * 32767).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sr)
        wf.writeframes(samples.tobytes())
    return buf.getvalue()


def test_analyze_reports_sr_duration_peak_rms():
    a = analyze_wav(_wav(sr=32000, secs=0.5, amp=0.5))
    assert a["sample_rate"] == 32000
    assert abs(a["duration_s"] - 0.5) < 0.02
    assert 0.45 < a["peak"] <= 0.51
    assert a["engine_guess"] == "sovits"   # 32000 Hz


def test_analyze_engine_guess_edge_at_24k():
    assert analyze_wav(_wav(sr=24000))["engine_guess"] == "edge"


def test_ring_records_clips_newest_last():
    ap = AudioPlayback()
    ap._record_clip(_wav(), text="first")
    ap._record_clip(_wav(), text="second")
    snap = ap.audio_log_snapshot(n=5)
    assert [c["text"] for c in snap] == ["first", "second"]
    assert snap[-1]["played_ok"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv\Scripts\python.exe -m pytest tests/test_audio_analyze.py -v`
Expected: FAIL — `ImportError: cannot import name 'analyze_wav'`

- [ ] **Step 3: Implement**

Add near the top of `client/audio_playback.py` (after imports):

```python
from collections import deque

def analyze_wav(wav_bytes: bytes) -> dict:
    """Pure: extract sample_rate, duration, peak, rms, engine_guess from WAV bytes."""
    import io as _io, wave as _wave
    with _wave.open(_io.BytesIO(wav_bytes), "rb") as wf:
        sr = wf.getframerate(); n = wf.getnframes(); sw = wf.getsampwidth()
        ch = wf.getnchannels(); frames = wf.readframes(n)
    dtype = np.int16 if sw == 2 else np.int32
    norm = 32767.0 if sw == 2 else 2147483647.0
    audio = np.frombuffer(frames, dtype=dtype).astype(np.float32) / norm
    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    rms = float(np.sqrt(np.mean(audio ** 2))) if audio.size else 0.0
    dur = (n / float(sr)) if sr else 0.0
    engine = "sovits" if sr == 32000 else ("edge" if sr in (22050, 24000) else f"other({sr})")
    return {"sample_rate": sr, "channels": ch, "duration_s": round(dur, 3),
            "peak": round(peak, 4), "rms": round(rms, 4), "engine_guess": engine}
```

In `AudioPlayback.__init__` add:

```python
        self._clip_ring = deque(maxlen=50)
        self._ring_lock = threading.Lock()
```

Add methods to `AudioPlayback`:

```python
    def _record_clip(self, wav_bytes: bytes, text: str = "", played_ok: bool = True):
        try:
            info = analyze_wav(wav_bytes)
        except Exception as e:
            info = {"error": str(e)}
        info.update({"text": text or "", "played_ok": played_ok, "bytes": len(wav_bytes or b"")})
        with self._ring_lock:
            self._clip_ring.append(info)

    def audio_log_snapshot(self, n: int = 10):
        with self._ring_lock:
            return list(self._clip_ring)[-n:]
```

Thread `text` through playback. Change `play` signature (line 56) to `def play(self, wav_bytes, on_start=None, text=None):` and queue `self._play_queue.put((wav_bytes, on_start, text))`. In `_worker` (line 146) unpack 3-tuple tolerantly:

```python
            if isinstance(item, tuple):
                wav_bytes = item[0]
                on_start = item[1] if len(item) > 1 else None
                text = item[2] if len(item) > 2 else None
            else:
                wav_bytes, on_start, text = item, None, None
```

and call `self._play_wav(wav_bytes, text=text)`. Change `_play_wav` (line 160) to `def _play_wav(self, wav_bytes, text=None):` and at the end of its `try` (after the `_play_wav: done` log, line 200) add:

```python
            self._record_clip(wav_bytes, text=text, played_ok=True)
```

and in the `except` add `self._record_clip(wav_bytes, text=text, played_ok=False)`.

- [ ] **Step 4: Run tests**

Run: `venv\Scripts\python.exe -m pytest tests/test_audio_analyze.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add client/audio_playback.py tests/test_audio_analyze.py
git commit -m "feat(debug-mcp): wav analysis + played-clip ring in audio_playback

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 4: Display debug state + frame publish

**Files:**
- Modify: `client/mario_display.py`

- [ ] **Step 1: Add state fields in `__init__`** (near line 298 where `self._speaking` is set)

```python
        self._frame_lock = threading.Lock()
        self._latest_frame_png = None
```

Confirm `import threading` is present at the top of `mario_display.py`; add it if missing.

- [ ] **Step 2: Add `debug_state()` + frame publish methods**

Add as methods on the display class:

```python
    def debug_state(self) -> dict:
        return {
            "state": getattr(self, "state", None),
            "emotion": getattr(self, "_emotion", None),
            "speaking": bool(getattr(self, "_speaking", False)),
            "pose_hint": getattr(self, "_pose_hint", None),
            "text_full": getattr(self, "_typewriter_text", ""),
            "text_shown": getattr(self, "current_text", ""),
        }

    def _publish_frame(self):
        """Main-thread only: downscale current screen, PNG-encode, store under lock."""
        try:
            import io as _io
            surf = self._screen
            w, h = surf.get_size()
            if w > 960:
                scale = 960.0 / w
                surf = pygame.transform.smoothscale(surf, (960, int(h * scale)))
            buf = _io.BytesIO()
            pygame.image.save(surf, buf, "frame.png")
            with self._frame_lock:
                self._latest_frame_png = buf.getvalue()
        except Exception as e:
            logger.debug(f"[debug] _publish_frame failed: {e}")

    def latest_frame_png(self):
        with self._frame_lock:
            return self._latest_frame_png
```

- [ ] **Step 3: Call `_publish_frame` from the draw loop**

At the end of `_draw` after `pygame.display.flip()` (line 2083) add:

```python
        if self._frame % 6 == 0:
            self._publish_frame()
```

- [ ] **Step 4: Smoke-check it imports**

Run: `venv\Scripts\python.exe -c "import ast; ast.parse(open('client/mario_display.py',encoding='utf-8').read()); print('OK')"`
Expected: `OK`. (Pixel content is verified live in Task 9; no unit test for image bytes.)

- [ ] **Step 5: Commit**

```bash
git add client/mario_display.py
git commit -m "feat(debug-mcp): display debug_state() + downscaled frame publish

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 5: Presence frame injection

**Files:**
- Modify: `client/presence.py`

- [ ] **Step 1: Inspect** `client/presence.py` for the `PersonDetector` it holds and its `on_enter`/`on_person_detected` callbacks (wired in `client/main.py:142-148`).

- [ ] **Step 2: Add `inject_frame()`** to `PresenceDetector`:

```python
    def inject_frame(self, frame) -> dict:
        """Simulate the webcam seeing `frame` (a numpy BGR image): run detection,
        fire the same callbacks the live loop fires. Returns a detection summary."""
        result = {"people": 0, "faces": 0, "encoding_dim": 0}
        try:
            if getattr(self, "_detector", None) is not None:
                people = self._detector.detect_people(frame)
                result["people"] = len(people)
                if people and self.on_person_detected:
                    self.on_person_detected(people)
            if result["people"] and self.on_enter:
                self.on_enter()
        except Exception as e:
            result["error"] = str(e)
        return result
```

Adjust attribute names (`self._detector`) to match what `enable_person_detection` actually stores — read that method first and use its real field.

- [ ] **Step 3: Syntax check**

Run: `venv\Scripts\python.exe -c "import ast; ast.parse(open('client/presence.py',encoding='utf-8').read()); print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add client/presence.py
git commit -m "feat(debug-mcp): PresenceDetector.inject_frame for simulated guests

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 6: Client debug HTTP server (pure router + socket wrapper)

**Files:**
- Create: `client/debug_server.py`
- Test: `tests/test_debug_server_routing.py`

- [ ] **Step 1: Write the failing test (routing is pure, no sockets)**

```python
# tests/test_debug_server_routing.py
import json
from client.debug_server import route


class FakeProvider:
    def __init__(self):
        self.injected = None
    def debug_state(self): return {"state": "TALKING", "emotion": "happy"}
    def audio_log_snapshot(self, n=10): return [{"text": "hi", "played_ok": True}]
    def log_snapshot(self, n=200, grep="", level="DEBUG"): return [{"msg": "x", "level": "INFO"}]
    def latest_frame_png(self): return b"\x89PNG\r\n\x1a\n_fake_"
    def inject_frame_b64(self, b64): self.injected = b64; return {"people": 1, "faces": 1}


def test_state_route_returns_json():
    status, ctype, body = route("GET", "/state", {}, b"", FakeProvider())
    assert status == 200 and ctype == "application/json"
    assert json.loads(body)["emotion"] == "happy"


def test_frame_route_returns_png_bytes():
    status, ctype, body = route("GET", "/frame.png", {}, b"", FakeProvider())
    assert status == 200 and ctype == "image/png" and body.startswith(b"\x89PNG")


def test_frame_route_404_when_no_frame():
    class P(FakeProvider):
        def latest_frame_png(self): return None
    status, _, _ = route("GET", "/frame.png", {}, b"", P())
    assert status == 503


def test_inject_frame_passes_b64():
    p = FakeProvider()
    body = json.dumps({"image_b64": "QUJD"}).encode()
    status, _, resp = route("POST", "/inject_frame", {}, body, p)
    assert status == 200 and p.injected == "QUJD"


def test_unknown_route_404():
    status, _, _ = route("GET", "/nope", {}, b"", FakeProvider())
    assert status == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv\Scripts\python.exe -m pytest tests/test_debug_server_routing.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'client.debug_server'`

- [ ] **Step 3: Implement**

```python
# client/debug_server.py
"""Flag-gated localhost debug HTTP surface for the pygame client.

Enabled only when MARIO_DEBUG=1. Binds 127.0.0.1 so it is never reachable off
the box (and never via the Cloudflare tunnel). The MCP (mcp_mario_debug) calls it.
"""
import json
import logging
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger(__name__)
DEBUG_PORT = 8770


def route(method: str, path: str, query: dict, body: bytes, provider):
    """Pure dispatcher → (status:int, content_type:str, body:bytes). No sockets."""
    def js(obj, status=200):
        return status, "application/json", json.dumps(obj).encode()
    if method == "GET" and path == "/state":
        return js(provider.debug_state())
    if method == "GET" and path == "/audio":
        n = int((query.get("n") or ["10"])[0])
        return js({"clips": provider.audio_log_snapshot(n=n)})
    if method == "GET" and path == "/log":
        n = int((query.get("n") or ["200"])[0])
        grep = (query.get("grep") or [""])[0]
        level = (query.get("level") or ["DEBUG"])[0]
        return js({"lines": provider.log_snapshot(n=n, grep=grep, level=level)})
    if method == "GET" and path == "/frame.png":
        png = provider.latest_frame_png()
        if not png:
            return 503, "application/json", json.dumps({"error": "no frame yet"}).encode()
        return 200, "image/png", png
    if method == "POST" and path == "/inject_frame":
        try:
            data = json.loads(body or b"{}")
        except Exception as e:
            return js({"error": f"bad json: {e}"}, status=400)
        return js(provider.inject_frame_b64(data.get("image_b64", "")))
    return 404, "application/json", json.dumps({"error": "not found"}).encode()


def _make_handler(provider):
    class _H(BaseHTTPRequestHandler):
        def _handle(self, method):
            u = urlparse(self.path)
            length = int(self.headers.get("Content-Length", 0) or 0)
            body = self.rfile.read(length) if length else b""
            try:
                status, ctype, payload = route(method, u.path, parse_qs(u.query), body, provider)
            except Exception as e:
                status, ctype, payload = 500, "application/json", json.dumps({"error": str(e)}).encode()
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        def do_GET(self): self._handle("GET")
        def do_POST(self): self._handle("POST")
        def log_message(self, *a): pass  # silence access logs
    return _H


def start_debug_server(provider, port: int = DEBUG_PORT):
    """Start the debug server on 127.0.0.1 if MARIO_DEBUG=1. Returns the server or None."""
    if os.environ.get("MARIO_DEBUG", "") != "1":
        return None
    srv = ThreadingHTTPServer(("127.0.0.1", port), _make_handler(provider))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    logger.info(f"[debug] client debug server on http://127.0.0.1:{port} (MARIO_DEBUG=1)")
    return srv
```

- [ ] **Step 4: Run tests**

Run: `venv\Scripts\python.exe -m pytest tests/test_debug_server_routing.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add client/debug_server.py tests/test_debug_server_routing.py
git commit -m "feat(debug-mcp): client debug HTTP server (pure router + localhost gate)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 7: Wire debug server into the client (the `provider`)

**Files:**
- Modify: `client/main.py`

- [ ] **Step 1: Build a provider adapter + client log ring in `MarioClient`**

In `client/main.py`, add a module-level client log ring near the top (after logging is configured):

```python
from collections import deque as _deque
_CLIENT_LOG_RING = _deque(maxlen=3000)

class _ClientRingHandler(logging.Handler):
    def emit(self, record):
        try:
            _CLIENT_LOG_RING.append({"msg": record.getMessage(), "level": record.levelname, "name": record.name})
        except Exception:
            pass

logging.getLogger().addHandler(_ClientRingHandler())
```

Add a provider class (adapts MarioClient to what `route()` expects):

```python
import base64 as _b64
import numpy as _np

class _DebugProvider:
    def __init__(self, client):
        self._c = client
    def debug_state(self):
        return self._c.display.debug_state()
    def audio_log_snapshot(self, n=10):
        return self._c.audio_playback.audio_log_snapshot(n=n)
    def log_snapshot(self, n=200, grep="", level="DEBUG"):
        items = list(_CLIENT_LOG_RING)
        if grep:
            g = grep.lower(); items = [l for l in items if g in l["msg"].lower()]
        return items[-n:]
    def latest_frame_png(self):
        return self._c.display.latest_frame_png()
    def inject_frame_b64(self, b64):
        try:
            import cv2
            raw = _np.frombuffer(_b64.b64decode(b64), _np.uint8)
            frame = cv2.imdecode(raw, cv2.IMREAD_COLOR)
        except Exception as e:
            return {"error": f"decode failed: {e}"}
        return self._c.presence.inject_frame(frame)
```

- [ ] **Step 2: Start the server in `start()`**

In `MarioClient.start()` after `self.audio_playback.start()` (line 176) add:

```python
        try:
            from debug_server import start_debug_server
            self._debug_srv = start_debug_server(_DebugProvider(self))
        except Exception as _e:
            logger.debug(f"[debug] debug server not started: {_e}")
```

- [ ] **Step 3: Thread spoken text into playback** so `mario_audio_out` shows what was said. Find where `_on_mario_text`/`_on_mario_audio` call `self.audio_playback.play(wav_bytes)` (e.g. line 445) and pass the current text: `self.audio_playback.play(wav_bytes, text=self.display._typewriter_text)`.

- [ ] **Step 4: Syntax check**

Run: `venv\Scripts\python.exe -c "import ast; ast.parse(open('client/main.py',encoding='utf-8').read()); print('OK')"`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add client/main.py
git commit -m "feat(debug-mcp): wire client debug server + log ring + spoken-text tagging

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 8: MCP bridge (pure logic, httpx)

**Files:**
- Create: `mcp_mario_debug/__init__.py`, `mcp_mario_debug/bridge.py`, `mcp_mario_debug/requirements.txt`
- Test: `tests/test_mcp_bridge.py`

- [ ] **Step 1: Write the failing test (httpx MockTransport)**

```python
# tests/test_mcp_bridge.py
import httpx
from mcp_mario_debug import bridge


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_health_passthrough():
    def h(req): return httpx.Response(200, json={"ws_connected": True, "tts": "ok"})
    b = bridge.Bridge(server="http://s", client="http://c", admin_key="", http=_client(h))
    assert b.health()["ws_connected"] is True


def test_send_text_posts_admin_key():
    seen = {}
    def h(req):
        seen["body"] = req.read().decode()
        return httpx.Response(200, json={"status": "ok"})
    b = bridge.Bridge(server="http://s", client="http://c", admin_key="K", http=_client(h))
    b.send_text("hi")
    assert '"api_key": "K"' in seen["body"] and '"text": "hi"' in seen["body"]


def test_audio_out_reads_client():
    def h(req):
        assert req.url.path == "/audio"
        return httpx.Response(200, json={"clips": [{"text": "hi", "engine_guess": "sovits"}]})
    b = bridge.Bridge(server="http://s", client="http://c", admin_key="", http=_client(h))
    assert b.audio_out(3)[0]["engine_guess"] == "sovits"


def test_logs_merge_both_sources():
    def h(req):
        src = "server" if req.url.host == "s" else "client"
        return httpx.Response(200, json={"lines": [{"msg": f"from {src}", "level": "INFO"}]})
    b = bridge.Bridge(server="http://s", client="http://c", admin_key="", http=_client(h))
    msgs = [l["msg"] for l in b.logs(source="both")]
    assert "from server" in msgs and "from client" in msgs


def test_client_down_returns_error_not_raise():
    def h(req): raise httpx.ConnectError("refused")
    b = bridge.Bridge(server="http://s", client="http://c", admin_key="", http=_client(h))
    assert "error" in b.state()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv\Scripts\python.exe -m pytest tests/test_mcp_bridge.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'mcp_mario_debug'`

- [ ] **Step 3: Implement**

```python
# mcp_mario_debug/__init__.py
"""Mario debug MCP — eyes/ears/hands on the running app."""
```

```python
# mcp_mario_debug/bridge.py
"""Pure bridge logic to the server (:8765) and client (:8770) debug surfaces.
No FastMCP import here, so it unit-tests with httpx.MockTransport. mss/pillow are
imported lazily inside screenshot() so this module imports without them."""
import base64
import httpx

DEFAULT_SERVER = "http://127.0.0.1:8765"
DEFAULT_CLIENT = "http://127.0.0.1:8770"


class Bridge:
    def __init__(self, server=DEFAULT_SERVER, client=DEFAULT_CLIENT, admin_key="", http=None):
        self.server = server.rstrip("/")
        self.client = client.rstrip("/")
        self.admin_key = admin_key
        self.http = http or httpx.Client(timeout=20.0)

    # ---- low level ----
    def _get(self, base, path, **params):
        try:
            r = self.http.get(base + path, params=params)
            return r.json()
        except Exception as e:
            return {"error": f"{type(e).__name__}: {e}"}

    def _post(self, base, path, payload):
        try:
            r = self.http.post(base + path, json=payload)
            return r.json()
        except Exception as e:
            return {"error": f"{type(e).__name__}: {e}"}

    def _keyed(self, payload):
        d = dict(payload)
        if self.admin_key:
            d["api_key"] = self.admin_key
        return d

    # ---- monitor ----
    def health(self):
        return self._get(self.server, "/api/health")

    def state(self):
        return self._get(self.client, "/state")

    def audio_out(self, n=10):
        r = self._get(self.client, "/audio", n=n)
        return r.get("clips", r)

    def logs(self, source="both", n=200, grep="", level="DEBUG"):
        out = []
        if source in ("server", "both"):
            r = self._get(self.server, "/debug/log", n=n, grep=grep, level=level)
            out += [{**l, "src": "server"} for l in r.get("lines", [])]
        if source in ("client", "both"):
            r = self._get(self.client, "/log", n=n, grep=grep, level=level)
            out += [{**l, "src": "client"} for l in r.get("lines", [])]
        return out

    def screenshot_png(self):
        """Return PNG bytes: client frame first, else OS window grab (mss)."""
        try:
            r = self.http.get(self.client + "/frame.png")
            if r.status_code == 200 and r.content[:4] == b"\x89PNG":
                return r.content
        except Exception:
            pass
        try:
            import mss, mss.tools
            with mss.mss() as sct:
                shot = sct.grab(sct.monitors[1])
                return mss.tools.to_png(shot.rgb, shot.size)
        except Exception as e:
            return None

    # ---- control ----
    def send_text(self, text):
        return self._post(self.server, "/admin/simulate_text", self._keyed({"text": text}))

    def inject_audio(self, wav_bytes):
        b64 = base64.b64encode(wav_bytes).decode()
        return self._post(self.server, "/admin/inject_audio", self._keyed({"wav_b64": b64}))

    def inject_frame(self, image_bytes):
        b64 = base64.b64encode(image_bytes).decode()
        return self._post(self.client, "/inject_frame", {"image_b64": b64})

    def set_emotion(self, emotion):
        return self._post(self.server, "/admin/set_emotion", self._keyed({"emotion": emotion}))

    def trigger_event(self, name):
        return self._post(self.server, f"/admin/trigger_event/{name}", self._keyed({}))

    def set_night_phase(self, phase):
        return self._post(self.server, "/admin/set_night_phase", self._keyed({"phase": phase}))
```

```
# mcp_mario_debug/requirements.txt
mcp>=1.2.0
httpx>=0.27.0
mss>=9.0.0
pillow>=10.0.0
```

- [ ] **Step 4: Run tests**

Run: `venv\Scripts\python.exe -m pytest tests/test_mcp_bridge.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add mcp_mario_debug/__init__.py mcp_mario_debug/bridge.py mcp_mario_debug/requirements.txt tests/test_mcp_bridge.py
git commit -m "feat(debug-mcp): pure bridge to server+client debug surfaces

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 9: FastMCP server + registration

**Files:**
- Create: `mcp_mario_debug/server.py`, `mcp_mario_debug/README.md`
- Modify: `.mcp.json`

- [ ] **Step 1: Implement `server.py`** (thin; reads admin key from `config.json` in-process, never logs it)

```python
# mcp_mario_debug/server.py
"""FastMCP server exposing the Mario AI app as debug tools."""
import base64
import json
import os
from mcp.server.fastmcp import FastMCP, Image

from mcp_mario_debug.bridge import Bridge

mcp = FastMCP("mario-debug")


def _admin_key():
    try:
        repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(repo, "config.json"), encoding="utf-8") as f:
            cfg = json.load(f)
        return (cfg.get("server", cfg) or {}).get("admin_api_key", "") or cfg.get("admin_api_key", "")
    except Exception:
        return ""


_bridge = Bridge(admin_key=_admin_key())


@mcp.tool()
def mario_health() -> dict:
    """Server health: ws_connected, tts, emotion, uptime, cache stats."""
    return _bridge.health()


@mcp.tool()
def mario_state() -> dict:
    """What's on the pygame screen now: state, emotion, speaking, pose, full+shown text."""
    return _bridge.state()


@mcp.tool()
def mario_audio_out(n: int = 10) -> dict:
    """Last N played audio clips: text, duration, peak, rms, sample-rate, engine_guess, played_ok."""
    return {"clips": _bridge.audio_out(n)}


@mcp.tool()
def mario_logs(source: str = "both", grep: str = "", level: str = "DEBUG", n: int = 150) -> dict:
    """Tail server and/or client logs. source = server|client|both."""
    return {"lines": _bridge.logs(source=source, n=n, grep=grep, level=level)}


@mcp.tool()
def mario_screenshot() -> Image:
    """Screenshot of the pygame client (client frame, else OS window grab). Returns a PNG."""
    png = _bridge.screenshot_png()
    if not png:
        return Image(data=b"", format="png")
    return Image(data=png, format="png")


@mcp.tool()
def mario_send_text(text: str) -> dict:
    """Inject a typed user message into the live session (as if a guest typed it)."""
    return _bridge.send_text(text)


@mcp.tool()
def mario_inject_audio(wav_path: str) -> dict:
    """Simulate a guest SPEAKING: read a WAV file from disk, run it through STT -> reply."""
    try:
        with open(wav_path, "rb") as f:
            wav = f.read()
    except Exception as e:
        return {"error": f"read failed: {e}"}
    return _bridge.inject_audio(wav)


@mcp.tool()
def mario_inject_frame(image_path: str) -> dict:
    """Simulate a guest APPEARING: read an image, run it through person/face detection."""
    try:
        with open(image_path, "rb") as f:
            img = f.read()
    except Exception as e:
        return {"error": f"read failed: {e}"}
    return _bridge.inject_frame(img)


@mcp.tool()
def mario_set_emotion(emotion: str) -> dict:
    """Force the current emotion (e.g. happy, sad, excited, sleepy)."""
    return _bridge.set_emotion(emotion)


@mcp.tool()
def mario_trigger_event(name: str) -> dict:
    """Trigger a shot/ceremony event by name (e.g. deltarune, birthday_boy)."""
    return _bridge.trigger_event(name)


@mcp.tool()
def mario_set_night_phase(phase: str) -> dict:
    """Override night phase: WARM_UP | PARTY_MODE | UNHINGED | WIND_DOWN | AUTO."""
    return _bridge.set_night_phase(phase)


def main():
    mcp.run()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Register in `.mcp.json`** — add inside `mcpServers`:

```json
    "mario-debug": {
      "type": "stdio",
      "command": "mcp_mario_debug/venv/Scripts/python.exe",
      "args": ["-m", "mcp_mario_debug.server"]
    }
```

- [ ] **Step 3: Create the venv + install**

```bash
python -m venv mcp_mario_debug/venv
mcp_mario_debug/venv/Scripts/python.exe -m pip install -r mcp_mario_debug/requirements.txt
```

- [ ] **Step 4: Verify the server starts (imports + lists tools)**

Run: `mcp_mario_debug/venv/Scripts/python.exe -c "import mcp_mario_debug.server as s; print(sorted(t.name for t in __import__('asyncio').run(s.mcp.list_tools())))"`
Expected: prints the 11 tool names without error.

- [ ] **Step 5: Write `README.md`** (setup, MARIO_DEBUG note, tool table) and **commit**

```bash
git add mcp_mario_debug/server.py mcp_mario_debug/README.md .mcp.json
git commit -m "feat(debug-mcp): FastMCP server + .mcp.json registration

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 10: Live end-to-end verification

**Files:** none (manual/live; documented in README).

- [ ] **Step 1:** Relaunch server with `MARIO_DEBUG=1` (set in environment before `start_server.bat`) and the client with `MARIO_DEBUG=1`. Confirm log lines: server `MARIO_DEBUG` active and client `[debug] client debug server on http://127.0.0.1:8770`.
- [ ] **Step 2:** In Claude Code, reload MCP servers; call `mario_health` → expect `ws_connected: true`.
- [ ] **Step 3:** `mario_screenshot` → confirm a viewable pygame frame.
- [ ] **Step 4:** `mario_send_text("who are you?")`, wait, `mario_audio_out` → confirm a clip with matching text, `engine_guess: sovits`, `played_ok: true`; `mario_state` → `speaking`/text reflect the reply.
- [ ] **Step 5:** `mario_logs(grep="sovits")` → confirm synth lines. `mario_inject_audio` with a test WAV → confirm transcript+reply. `mario_inject_frame` with a face image → confirm `people>=1`. **Commit** any README/cache updates.

---

## Self-Review Notes

- **Spec coverage:** screenshot (T4,T8,T9), state (T4,T9), audio_out (T3,T9), logs server+client (T1,T2,T7,T9), health (T9), send_text (T9), inject_audio (T2,T9), inject_frame (T5,T7,T9), set_emotion/trigger_event/set_night_phase (T8,T9), gating MARIO_DEBUG+localhost (T2,T6), `.mcp.json` (T9). All spec items mapped.
- **Type consistency:** `analyze_wav`→keys reused by ring + tests; `route()` signature identical in impl + tests; `Bridge` method names match `server.py` calls and bridge tests.
- **Assumptions to verify during impl (not placeholders — concrete fallbacks given):** `PresenceDetector` internal detector field name (Task 5 Step 1 says read it first); exact `play()` call site line for text-tagging (Task 7 Step 3 says find it); `/admin/set_emotion`/`set_night_phase` already exist (confirmed this session) — if a signature differs, adjust the one `_post` payload.
