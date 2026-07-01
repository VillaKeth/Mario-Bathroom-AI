# Screen-Watching Game Coach — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** An opt-in standalone `screen_watcher.py` process (`start_watching.bat`) that screenshots the bot's machine, has `llava` describe the game, and POSTs the description to a new server endpoint that turns it into a spoken Rudi roast — with `llava` loaded ONLY while the watcher runs.

**Architecture:** Watcher = eyes (capture + llava + owns the model lifecycle); server = voice (description → Rudi roast via existing LLM/TTS/display, idle-safe gated). They talk over one admin HTTP endpoint. Vision model lives entirely in the watcher process.

**Tech Stack:** Python, `mss` (screen capture), `cv2`+`numpy` (resize/JPEG — already in venv), `httpx` (HTTP — already in venv), Ollama (`llava-llama3`), FastAPI (existing server).

## Global Constraints

- `server/main.py` / `mario_prompt.py` use the module `logger`; a standalone script may use `print()` or its own logger.
- Admin endpoints gate on `GAME_CONFIG.get("admin_api_key","")`: if set, reject when `request_body.get("api_key") != api_key`.
- WebSocket response type is `"mario_response"`; speak via `send_response` / the idle-safe path.
- `config.json` is gitignored (machine-local) — read tunables via `GAME_CONFIG.get(key, default)` with defaults IN CODE; document new keys in `config.example.json` (tracked). Never require committing `config.json`.
- `git add <specific files>` only (never `-A`); commit trailer `Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>`.
- Tests run with `venv\Scripts\python.exe -m pytest`.
- llava must NOT be loaded by the server process — only by the watcher.

---

## File Structure

- `server/screen_watcher.py` *(new, standalone)* — `_encode_jpeg`, `capture_frame`, `describe_frame`, `unload_llava`, `post_frame`, `run_watch_loop`, `main`. Owns llava.
- `start_watching.bat` *(new)* — venv-activate + run the watcher (mirrors `start_client.bat`).
- `server/main.py` *(modify)* — add `POST /admin/watch_frame` endpoint.
- `server/mario_prompt.py` *(modify)* — add `build_watch_context(description, guest)` helper.
- `server/requirements.txt` *(modify)* — add `mss`.
- `config.example.json` *(modify)* — document watch keys.
- Tests: `tests/test_screen_watcher.py`, `tests/test_watch_endpoint.py`.

---

### Task 1: Screen capture (mss + JPEG encode)

**Files:**
- Create: `server/screen_watcher.py`
- Modify: `server/requirements.txt` (add `mss`)
- Test: `tests/test_screen_watcher.py`

**Interfaces:**
- Produces: `_encode_jpeg(frame_bgr, width=1024, quality=70) -> bytes` (pure; takes a numpy BGR array, returns JPEG bytes downscaled to `width`). `capture_frame(width=1024) -> bytes` (grabs primary monitor via mss → `_encode_jpeg`).

- [ ] **Step 1: Add dependency**

Append to `server/requirements.txt`:
```
mss
```

- [ ] **Step 2: Write the failing test** (pure encoder — no display needed)

```python
# tests/test_screen_watcher.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))
import numpy as np
import screen_watcher

def test_encode_jpeg_returns_downscaled_jpeg():
    frame = np.zeros((1080, 1920, 3), dtype=np.uint8)  # fake BGR screen
    frame[:, :, 1] = 128  # some green so it's not degenerate
    out = screen_watcher._encode_jpeg(frame, width=1024, quality=70)
    assert isinstance(out, (bytes, bytearray))
    assert out[:2] == b"\xff\xd8"          # JPEG SOI magic
    assert len(out) > 100
    # decode back and check it was downscaled to width 1024
    import cv2
    dec = cv2.imdecode(np.frombuffer(out, np.uint8), cv2.IMREAD_COLOR)
    assert dec.shape[1] == 1024
```

- [ ] **Step 3: Run test to verify it fails**

Run: `venv\Scripts\python.exe -m pytest tests/test_screen_watcher.py -v`
Expected: FAIL (`ModuleNotFoundError: screen_watcher` or attribute error).

- [ ] **Step 4: Write minimal implementation**

```python
# server/screen_watcher.py
"""Standalone screen-watch process: capture the screen, have llava describe the
game, POST the description to the server so Rudi can roast it. Run via
start_watching.bat. llava is loaded ONLY while this process runs and is
unloaded on exit."""
import cv2
import numpy as np

def _encode_jpeg(frame_bgr, width: int = 1024, quality: int = 70) -> bytes:
    """Downscale a BGR frame to `width` (keeping aspect) and JPEG-encode it."""
    h, w = frame_bgr.shape[:2]
    if w > width:
        scale = width / float(w)
        frame_bgr = cv2.resize(frame_bgr, (width, int(h * scale)), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", frame_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not ok:
        raise RuntimeError("JPEG encode failed")
    return buf.tobytes()

def capture_frame(width: int = 1024) -> bytes:
    """Grab the primary monitor and return a downscaled JPEG."""
    import mss  # imported lazily so the encoder is testable without a display
    with mss.mss() as sct:
        shot = sct.grab(sct.monitors[1])  # monitors[1] = primary
    frame = np.array(shot)[:, :, :3]      # BGRA -> BGR
    return _encode_jpeg(frame, width=width)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `venv\Scripts\python.exe -m pytest tests/test_screen_watcher.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add server/screen_watcher.py tests/test_screen_watcher.py server/requirements.txt
git commit -m "feat(watch): screen capture + JPEG encode (mss)"
```

---

### Task 2: llava describe + unload

**Files:**
- Modify: `server/screen_watcher.py`
- Test: `tests/test_screen_watcher.py`

**Interfaces:**
- Consumes: `_encode_jpeg`/`capture_frame` (Task 1).
- Produces: `describe_frame(jpeg: bytes, ollama_url, model, keepalive="3m") -> str` (POST Ollama `/api/chat` with the image, return the description). `unload_llava(ollama_url, model)` (POST Ollama `/api/generate` with `keep_alive=0`).

- [ ] **Step 1: Write the failing test** (mock Ollama via monkeypatch on httpx)

```python
# tests/test_screen_watcher.py  (append)
import base64, json
import screen_watcher

def test_describe_frame_sends_image_and_keepalive(monkeypatch):
    captured = {}
    class FakeResp:
        status_code = 200
        def raise_for_status(self): pass
        def json(self): return {"message": {"content": "Fortnite, low HP, being chased."}}
    def fake_post(url, json=None, timeout=None):
        captured["url"] = url; captured["json"] = json
        return FakeResp()
    monkeypatch.setattr(screen_watcher.httpx, "post", fake_post)
    out = screen_watcher.describe_frame(b"\xff\xd8fakejpeg", "http://x:11434", "llava-llama3:latest")
    assert out == "Fortnite, low HP, being chased."
    msg = captured["json"]["messages"][0]
    assert captured["json"]["keep_alive"] == "3m"
    assert base64.b64decode(msg["images"][0]) == b"\xff\xd8fakejpeg"  # image base64'd

def test_unload_llava_sends_keepalive_zero(monkeypatch):
    captured = {}
    class FakeResp:
        status_code = 200
        def raise_for_status(self): pass
        def json(self): return {}
    monkeypatch.setattr(screen_watcher.httpx, "post",
                        lambda url, json=None, timeout=None: (captured.update(json=json) or FakeResp()))
    screen_watcher.unload_llava("http://x:11434", "llava-llama3:latest")
    assert captured["json"]["keep_alive"] == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv\Scripts\python.exe -m pytest tests/test_screen_watcher.py -k "describe or unload" -v`
Expected: FAIL (`module 'screen_watcher' has no attribute 'httpx'` / `describe_frame`).

- [ ] **Step 3: Write minimal implementation**

Add to `server/screen_watcher.py` (add `import base64` and `import httpx` at top):

```python
import base64
import httpx

_DESCRIBE_PROMPT = (
    "Describe this game screenshot in ONE short sentence: what game, what's "
    "happening, and how the player is doing (winning, losing, or in danger)."
)

def describe_frame(jpeg: bytes, ollama_url: str, model: str, keepalive: str = "3m") -> str:
    """Ask llava (via Ollama) to describe the frame. Returns a one-line description."""
    b64 = base64.b64encode(jpeg).decode("ascii")
    resp = httpx.post(
        f"{ollama_url}/api/chat",
        json={
            "model": model,
            "messages": [{"role": "user", "content": _DESCRIBE_PROMPT, "images": [b64]}],
            "stream": False,
            "keep_alive": keepalive,
        },
        timeout=120.0,
    )
    resp.raise_for_status()
    return (resp.json().get("message", {}).get("content", "") or "").strip()

def unload_llava(ollama_url: str, model: str) -> None:
    """Evict llava from Ollama immediately (keep_alive=0). Best-effort."""
    try:
        httpx.post(f"{ollama_url}/api/generate",
                   json={"model": model, "keep_alive": 0}, timeout=10.0)
    except Exception:
        pass
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv\Scripts\python.exe -m pytest tests/test_screen_watcher.py -k "describe or unload" -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add server/screen_watcher.py tests/test_screen_watcher.py
git commit -m "feat(watch): llava describe + explicit unload"
```

---

### Task 3: Server endpoint `/admin/watch_frame` + roast context

**Files:**
- Modify: `server/mario_prompt.py` (add `build_watch_context`)
- Modify: `server/main.py` (add endpoint, near other `/admin/*` routes ~line 2136)
- Modify: `config.example.json` (document keys)
- Test: `tests/test_watch_endpoint.py`

**Interfaces:**
- Consumes: `llm.generate_response`, `filter_response`, `analyze_text`, `tts.synthesize_user`, `_idle_send_if_safe`, `_active_ws`, `state_current`, `GAME_CONFIG` (all existing in main.py).
- Produces: `mario_prompt.build_watch_context(description: str, guest: str = None) -> list[dict]` (returns an LLM message list). Endpoint `POST /admin/watch_frame` body `{description, api_key?, guest?}` → returns `{"ok": bool, "spoke": bool}`.

- [ ] **Step 1: Write the failing test** (context builder — pure, no server)

```python
# tests/test_watch_endpoint.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))
import mario_prompt

def test_build_watch_context_includes_description():
    ctx = mario_prompt.build_watch_context("Fortnite, 12 HP, being chased", guest="Jacob")
    assert isinstance(ctx, list) and ctx
    joined = " ".join(m["content"] for m in ctx)
    assert "Fortnite, 12 HP, being chased" in joined
    assert "Jacob" in joined
    assert ctx[-1]["role"] == "user"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv\Scripts\python.exe -m pytest tests/test_watch_endpoint.py -v`
Expected: FAIL (`no attribute 'build_watch_context'`).

- [ ] **Step 3: Implement the context builder**

Add to `server/mario_prompt.py`:

```python
def build_watch_context(description: str, guest: str = None, system_prompt: str = None) -> list[dict]:
    """LLM context for a screen-watch heckle: optional persona system prompt +
    the on-screen scene. Roast-first, occasional real tip, in character, short.
    The caller (main.py endpoint) passes the character prompt as system_prompt."""
    who = guest or "them"
    ctx = []
    if system_prompt:
        ctx.append({"role": "system", "content": system_prompt})
    ctx.append({"role": "user", "content":
        f"You're watching {who} play a game right now. On their screen: {description}. "
        "Drop ONE short line, mostly roast/heckle, occasionally a genuine tip. "
        "In character, under 20 words, no asterisks."})
    return ctx
```

The persona lives in `main.py`'s `_get_idle_prompt()`; the builder stays decoupled
by taking it as a parameter. The test calls it without `system_prompt` (context =
just the user turn) — that's why the assertion only checks the description/guest and
`ctx[-1]["role"] == "user"`.

- [ ] **Step 4: Run context test to verify it passes**

Run: `venv\Scripts\python.exe -m pytest tests/test_watch_endpoint.py -v`
Expected: PASS.

- [ ] **Step 5: Add the endpoint** in `server/main.py` (near other `@app.post("/admin/...")` routes, ~line 2136)

```python
@app.post("/admin/watch_frame")
async def admin_watch_frame(request_body: dict = {}):
    """Screen-watch heckle: turn a scene description into a spoken Rudi roast.
    Called by screen_watcher.py. Idle-safe gated (won't talk over a real convo)."""
    api_key = GAME_CONFIG.get("admin_api_key", "")
    if api_key and request_body.get("api_key") != api_key:
        return {"ok": False, "spoke": False, "error": "unauthorized"}
    description = (request_body.get("description") or "").strip()
    if not description:
        return {"ok": True, "spoke": False}
    if _active_ws is None:
        return {"ok": True, "spoke": False}
    guest = state_current.get("speaker_name")
    try:
        ctx = mario_prompt.build_watch_context(description, guest=guest, system_prompt=_get_idle_prompt())
        llm_response = await asyncio.wait_for(
            llm.generate_response(ctx, model=llm_router.get_model(
                llm_router.classify("roast", response_type="casual"))),
            timeout=_LLM_IDLE_TIMEOUT)
        text = filter_response((llm_response.get("text") or "").strip())
        if not text or len(text) < 3:
            return {"ok": True, "spoke": False}
        analyzed = analyze_text(text)
        loop = asyncio.get_event_loop()
        audio = await loop.run_in_executor(
            _tts_executor, lambda: tts.synthesize_user(analyzed["tts_text"]))
        await _idle_send_if_safe(_active_ws, analyzed["display_text"], audio,
                                 emotion="mischievous", pose_hint=analyzed.get("pose_hint"))
        return {"ok": True, "spoke": True}
    except Exception as e:
        logger.warning(f"[WATCH] heckle failed: {e}")
        return {"ok": False, "spoke": False}
```

- [ ] **Step 6: Document config keys** in `config.example.json` (add to the `server` block):

```json
    "llava_model": "llava-llama3:latest",
    "watch_interval_seconds": 20,
    "watch_max_minutes": 30,
    "watch_keepalive": "3m",
    "watch_jpeg_width": 1024,
```

- [ ] **Step 7: Verify** — context test passes + main.py imports clean

Run: `venv\Scripts\python.exe -m pytest tests/test_watch_endpoint.py -v`
Run: `venv\Scripts\python.exe -c "import ast; ast.parse(open(r'server/main.py',encoding='utf-8').read())"`
Expected: PASS + no syntax error.

- [ ] **Step 8: Commit**

```bash
git add server/mario_prompt.py server/main.py config.example.json tests/test_watch_endpoint.py
git commit -m "feat(watch): /admin/watch_frame endpoint + roast context (idle-safe)"
```

---

### Task 4: Watch loop + start_watching.bat (wire it together)

**Files:**
- Modify: `server/screen_watcher.py` (add `post_frame`, `run_watch_loop`, `main`, config load)
- Create: `start_watching.bat`
- Test: `tests/test_screen_watcher.py`

**Interfaces:**
- Consumes: `capture_frame`, `describe_frame`, `unload_llava` (Tasks 1-2).
- Produces: `post_frame(server_url, description, api_key, guest=None) -> bool`; `run_watch_loop(cfg, max_ticks=None) -> None` (loop: capture→describe→post each `interval`, honor `watch_max_minutes`, continue on per-tick errors, `unload_llava` in `finally`). `main()` loads config + runs.

- [ ] **Step 1: Write the failing test** (loop runs N ticks, unloads on exit, survives a bad tick)

```python
# tests/test_screen_watcher.py  (append)
import screen_watcher

def test_run_watch_loop_ticks_and_unloads(monkeypatch):
    calls = {"cap": 0, "desc": 0, "post": 0, "unload": 0, "sleep": 0}
    monkeypatch.setattr(screen_watcher, "capture_frame", lambda width=1024: b"\xff\xd8x")
    def fake_desc(*a, **k):
        calls["desc"] += 1
        if calls["desc"] == 2:
            raise RuntimeError("bad frame")  # a bad tick must not kill the loop
        return "scene"
    monkeypatch.setattr(screen_watcher, "describe_frame", fake_desc)
    monkeypatch.setattr(screen_watcher, "post_frame", lambda *a, **k: calls.update(post=calls["post"]+1) or True)
    monkeypatch.setattr(screen_watcher, "unload_llava", lambda *a, **k: calls.update(unload=calls["unload"]+1))
    monkeypatch.setattr(screen_watcher.time, "sleep", lambda s: calls.update(sleep=calls["sleep"]+1))
    cfg = {"ollama_url": "http://x:11434", "llava_model": "m", "server_url": "http://y:8765",
           "api_key": "", "interval": 0, "width": 1024}
    screen_watcher.run_watch_loop(cfg, max_ticks=3)
    assert calls["desc"] == 3            # ran 3 ticks
    assert calls["post"] == 2            # tick 2 errored before post, others posted
    assert calls["unload"] == 1          # unloaded exactly once on exit
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv\Scripts\python.exe -m pytest tests/test_screen_watcher.py -k watch_loop -v`
Expected: FAIL (`no attribute 'run_watch_loop'`).

- [ ] **Step 3: Implement loop + post + main** in `server/screen_watcher.py` (add `import time`, `import os`, `import json` at top)

```python
import time

def post_frame(server_url: str, description: str, api_key: str, guest: str = None) -> bool:
    try:
        r = httpx.post(f"{server_url}/admin/watch_frame",
                       json={"description": description, "api_key": api_key, "guest": guest},
                       timeout=15.0)
        return r.status_code == 200
    except Exception as e:
        print(f"[watch] post failed: {e}")
        return False

def run_watch_loop(cfg: dict, max_ticks: int = None) -> None:
    """Capture -> describe -> post every cfg['interval'] s until killed or
    watch_max_minutes elapses. Unloads llava on exit. Per-tick errors are logged
    and skipped (one bad frame never kills the session)."""
    started = time.monotonic()
    max_secs = cfg.get("max_minutes", 30) * 60
    ticks = 0
    try:
        while True:
            if max_ticks is not None and ticks >= max_ticks:
                break
            if max_ticks is None and (time.monotonic() - started) >= max_secs:
                print("[watch] max session time reached, exiting")
                break
            ticks += 1
            try:
                jpeg = capture_frame(width=cfg["width"])
                desc = describe_frame(jpeg, cfg["ollama_url"], cfg["llava_model"])
                if desc:
                    post_frame(cfg["server_url"], desc, cfg["api_key"])
            except Exception as e:
                print(f"[watch] tick failed (continuing): {e}")
            time.sleep(cfg["interval"])
    finally:
        unload_llava(cfg["ollama_url"], cfg["llava_model"])
        print("[watch] llava unloaded, watcher stopped")

def _load_cfg() -> dict:
    import os, json
    root = os.path.dirname(os.path.dirname(__file__))
    try:
        with open(os.path.join(root, "config.json"), encoding="utf-8") as f:
            s = json.load(f).get("server", {})
    except Exception:
        s = {}
    return {
        "ollama_url": os.environ.get("OLLAMA_URL", s.get("ollama_url", "http://localhost:11434")),
        "server_url": os.environ.get("MARIO_SERVER_URL", "http://localhost:8765"),
        "llava_model": s.get("llava_model", "llava-llama3:latest"),
        "api_key": s.get("admin_api_key", ""),
        "interval": s.get("watch_interval_seconds", 20),
        "max_minutes": s.get("watch_max_minutes", 30),
        "width": s.get("watch_jpeg_width", 1024),
    }

def main():
    cfg = _load_cfg()
    print(f"[watch] starting — every {cfg['interval']}s, llava={cfg['llava_model']} "
          f"(loads now, unloads on exit). Ctrl+C to stop.")
    try:
        run_watch_loop(cfg)
    except KeyboardInterrupt:
        print("[watch] interrupted")

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv\Scripts\python.exe -m pytest tests/test_screen_watcher.py -v`
Expected: PASS (all screen_watcher tests).

- [ ] **Step 5: Create `start_watching.bat`** (mirror `start_client.bat`)

```bat
@echo off
REM ============================================================
REM  Start ONLY the screen-watching process (Rudi watches your game).
REM  Requires start_server.bat (and usually start_client.bat) already running.
REM  Closing this window stops watching AND unloads the llava vision model.
REM ============================================================
cd /d "%~dp0"

if not exist "%~dp0venv\Scripts\python.exe" (
    echo [ERROR] Setup has not been run yet. Run setup.bat first.
    pause
    exit /b 1
)

call "%~dp0venv\Scripts\activate.bat"
echo Starting screen watcher... (close this window to stop and free the vision model)
python "%~dp0server\screen_watcher.py"
pause
```

- [ ] **Step 6: Commit**

```bash
git add server/screen_watcher.py tests/test_screen_watcher.py start_watching.bat
git commit -m "feat(watch): periodic watch loop + start_watching.bat (unloads llava on exit)"
```

---

## Self-Review

**Spec coverage:**
- Standalone watcher process + `start_watching.bat` → Task 4. ✓
- Same-machine capture (mss, downscaled JPEG) → Task 1. ✓
- llava in the watcher, loaded on run, unloaded on exit + keep_alive fallback → Tasks 2 & 4 (`describe_frame` keepalive `3m`, `unload_llava` in `finally`). ✓
- Server `/admin/watch_frame` → llava-free roast via existing LLM/TTS/display, idle-safe gated → Task 3. ✓
- Roast-first context, ~20s cadence, 30-min safety exit, admin-key gate, privacy (frames stay local, only description POSTed) → Tasks 3 & 4. ✓
- Config via GAME_CONFIG defaults + config.example.json (config.json gitignored) → Task 3/4. ✓
- Client "👁 watching" indicator → intentionally deferred (spec marked it optional; not required for the feature to work). Noted, not built.

**Placeholder scan:** No TBD/TODO. One conditional in Task 3 (context builder's system-prompt accessor) — resolved with an explicit fallback: if no in-module getter, take a `system_prompt` param and have main.py pass `_get_idle_prompt()`. The implementer picks the matching accessor; both paths are spelled out.

**Type consistency:** `_encode_jpeg`/`capture_frame`→bytes; `describe_frame(jpeg,ollama_url,model,keepalive)`→str; `unload_llava(ollama_url,model)`; `post_frame(server_url,description,api_key,guest)`→bool; `run_watch_loop(cfg,max_ticks)`; `build_watch_context(description,guest)`→list[dict]. Consistent across tasks.
