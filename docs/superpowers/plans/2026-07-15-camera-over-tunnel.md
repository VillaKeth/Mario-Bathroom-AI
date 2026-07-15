# Camera Over Tunnel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a remote guest on the party tunnel opt in to their device camera so the character recognizes/remembers their face and comments on what he sees.

**Architecture:** All decision logic (rate-limit, frame cache, throttle, greet-pending, vision-intent, face-encode) lives in a new pure, importable module `server/camera_relay.py` (unit-tested like `server/mirror.py`). `server/main.py` gets a thin `POST /friend/see` endpoint and a `_camera_vision_comment()` helper that reuse the existing remote-guest auth (`mirror.authorize_friend_input`), the existing face stack (`_face_memory`, `recognition_events`), and the existing proactive-speak path from `/admin/watch_frame` (`generate_response` → `filter_response` → `analyze_text` → `tts.synthesize_user` → `_idle_send_if_safe`). Vision uses the multimodal model via Ollama `/api/chat` `images:[…]` — no change to `server/llm.py`, because it passes message dicts through verbatim. Frames arrive by HTTP POST ~2.5s; the character's spoken reply reaches the remote browser because the pygame client plays it and the mirror relays that audio automatically.

**Tech Stack:** FastAPI, httpx, Ollama (multimodal `/api/chat`), `face_recognition`/dlib (128-d encodings), pytest, vanilla JS (`getUserMedia` + canvas).

## Global Constraints

- New pure server modules follow `server/mirror.py` style: a module-level `DEBUG_*` flag + `print()` for logging (NOT `logger`). Code inside `server/main.py` uses its existing `logger`.
- WebSocket message type for spoken replies is `"mario_response"` (never `"response"`).
- No ellipsis (`...`/`…`) in any hardcoded string that can reach TTS — use commas/periods.
- Generic/shared content must stay character-agnostic. Vision commentary text is produced by the LLM through `generate_response`, which already injects the non-Mario isolation guard at its chokepoint; also pass output through `filter_response`. Any hardcoded nudge string must be character-agnostic.
- `config.json` is gitignored (holds a live `admin_api_key`) — NEVER `git add config.json`. New config goes in `config_live.json` (tracked) and is documented in `config.example.json`.
- Git: `git add <specific files>` only (never `-A` — Qdrant `.lock` files must not be committed). Commit trailer: `Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>`.
- Frames are RAM-only (short TTL), never written to disk; only 128-d face embeddings persist (existing privacy-first design).
- Tests: pure modules are imported via `sys.path.insert(0, .../server)` then `import camera_relay`. Endpoint tests import `server/main.py` (heavy but cached), monkeypatch its module-level globals, and `asyncio.run(...)` the async handler directly (pattern from `tests/test_admin_live_control.py`).

---

## File Structure

| File | Responsibility |
|---|---|
| `server/camera_relay.py` (new) | Pure decision logic: per-client frame rate-limit, RAM frame cache w/ TTL, greet-pending set, global vision throttle, consecutive-no-face counter, vision-intent matcher, `encode_face_from_b64`, `reset_state`. |
| `server/main.py` (modify) | `POST /friend/see` endpoint (thin wiring); `_camera_vision_comment()` helper; on-demand vision hook in `/friend/say` + `/friend/say_audio`; refactor `/admin/recognition/face` to use the shared encoder. |
| `server/static/friend.html` (modify) | Camera opt-in button, self-view, ~2.5s capture loop → `POST /friend/see`, consent line, visibility pause, `camera_off` on stop. |
| `server/live_flags.py` (modify) | Add `camera_enabled`, `camera_vision_enabled`, `camera_vision_min_gap` live flags. |
| `config_live.json` (modify) | Defaults for the new `camera_*` keys. |
| `config.example.json` (modify) | Document the new `camera_*` keys. |
| `server/requirements.txt` (modify) | Add `face_recognition`/dlib as a documented-optional block. |
| `tests/test_camera_relay.py` (new) | Unit tests for the pure module. |
| `tests/test_friend_camera.py` (new) | Endpoint/wiring tests (import-main + monkeypatch + asyncio). |

---

## Task 1: `camera_relay.py` pure decision module

**Files:**
- Create: `server/camera_relay.py`
- Test: `tests/test_camera_relay.py`

**Interfaces:**
- Consumes: nothing (leaf module; `numpy`/`face_recognition` imported lazily inside `encode_face_from_b64`, added in Task 2).
- Produces (public API later tasks rely on):
  - `allow_frame(client_id: str, now: float, min_interval: float) -> bool`
  - `cache_frame(client_id: str, jpeg: bytes, now: float) -> None`
  - `get_cached_frame(client_id: str, now: float, ttl: float) -> bytes | None`
  - `clear_client(client_id: str) -> None`
  - `request_greet(client_id: str) -> None`
  - `take_greet(client_id: str) -> bool`
  - `vision_allowed(now: float, min_gap: float) -> bool`
  - `mark_vision(now: float) -> None`
  - `note_face(client_id: str, seen: bool) -> int`
  - `is_vision_request(text: str) -> bool`
  - `reset_state() -> None`
  - (Task 2 adds) `encode_face_from_b64(image_b64: str) -> tuple[bool, "np.ndarray|None"]`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_camera_relay.py`:

```python
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

import camera_relay as cr


def setup_function(_):
    cr.reset_state()


def test_allow_frame_rate_limits_per_client():
    assert cr.allow_frame("a", now=100.0, min_interval=2.0) is True   # first ever → allowed
    assert cr.allow_frame("a", now=101.0, min_interval=2.0) is False  # 1s later → too soon
    assert cr.allow_frame("a", now=102.5, min_interval=2.0) is True   # 2.5s later → allowed
    assert cr.allow_frame("b", now=101.0, min_interval=2.0) is True   # different client independent


def test_frame_cache_roundtrip_and_ttl():
    cr.cache_frame("a", b"jpegbytes", now=100.0)
    assert cr.get_cached_frame("a", now=110.0, ttl=30.0) == b"jpegbytes"  # within TTL
    assert cr.get_cached_frame("a", now=140.0, ttl=30.0) is None          # expired
    assert cr.get_cached_frame("nobody", now=100.0, ttl=30.0) is None     # unknown client


def test_clear_client_drops_frame_and_greet_and_noface():
    cr.cache_frame("a", b"x", now=100.0)
    cr.request_greet("a")
    cr.note_face("a", False)
    cr.clear_client("a")
    assert cr.get_cached_frame("a", now=101.0, ttl=30.0) is None
    assert cr.take_greet("a") is False
    assert cr.note_face("a", False) == 1  # counter was reset → this is the first again


def test_greet_pending_is_one_shot():
    assert cr.take_greet("a") is False   # nothing requested
    cr.request_greet("a")
    assert cr.take_greet("a") is True     # consumed once
    assert cr.take_greet("a") is False    # not again


def test_vision_throttle_is_global_gap():
    assert cr.vision_allowed(now=100.0, min_gap=45.0) is True   # never spoken → allowed
    cr.mark_vision(now=100.0)
    assert cr.vision_allowed(now=120.0, min_gap=45.0) is False  # 20s later → too soon
    assert cr.vision_allowed(now=146.0, min_gap=45.0) is True   # 46s later → allowed


def test_note_face_counts_consecutive_misses():
    assert cr.note_face("a", False) == 1
    assert cr.note_face("a", False) == 2
    assert cr.note_face("a", True) == 0    # a face resets the streak
    assert cr.note_face("a", False) == 1


def test_is_vision_request_matches_look_intent():
    for t in ["what do you see", "How do I look?", "can you see me?",
              "do i look ok", "check out my outfit", "look at me"]:
        assert cr.is_vision_request(t) is True, t
    for t in ["tell me a joke", "what's up", "play a game", "sing a song", ""]:
        assert cr.is_vision_request(t) is False, t
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_camera_relay.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'camera_relay'`.

- [ ] **Step 3: Write the module**

Create `server/camera_relay.py`:

```python
"""Pure decision logic for the remote-camera feature (guest camera over the tunnel).

Importable + side-effect-free so it is unit-testable (server/main.py is not).
main.py holds only the thin FastAPI wiring; every gate/throttle/cache decision
lives here. State is module-level and cleared by reset_state() for tests.
"""
import re
import time

DEBUG_CAMERA = True

_last_frame_ts: dict = {}      # client_id -> ts of last ACCEPTED frame
_frames: dict = {}             # client_id -> (jpeg_bytes, ts)
_wants_greet: set = set()      # client_ids awaiting a first vision greeting
_noface: dict = {}             # client_id -> consecutive no-face count
_last_vision_ts: float = 0.0   # global: last spontaneous/greeting vision comment


def reset_state():
    """Test helper: clear all module state."""
    global _last_frame_ts, _frames, _wants_greet, _noface, _last_vision_ts
    _last_frame_ts = {}
    _frames = {}
    _wants_greet = set()
    _noface = {}
    _last_vision_ts = 0.0


def allow_frame(client_id: str, now: float, min_interval: float) -> bool:
    """True if this client is allowed to submit a frame now (>= min_interval since
    its last accepted frame). Records the timestamp on allow."""
    last = _last_frame_ts.get(client_id)
    if last is not None and (now - last) < min_interval:
        return False
    _last_frame_ts[client_id] = now
    return True


def cache_frame(client_id: str, jpeg: bytes, now: float) -> None:
    """Stash the latest raw JPEG for this client (RAM only) for on-demand vision."""
    _frames[client_id] = (jpeg, now)


def get_cached_frame(client_id: str, now: float, ttl: float):
    """Return the cached JPEG if present and younger than ttl, else None."""
    item = _frames.get(client_id)
    if not item:
        return None
    jpeg, ts = item
    if (now - ts) > ttl:
        return None
    return jpeg


def clear_client(client_id: str) -> None:
    """Camera-off / disconnect: forget everything transient about this client."""
    _frames.pop(client_id, None)
    _last_frame_ts.pop(client_id, None)
    _noface.pop(client_id, None)
    _wants_greet.discard(client_id)


def request_greet(client_id: str) -> None:
    """Mark that this client should get a one-time vision greeting on its next face."""
    _wants_greet.add(client_id)


def take_greet(client_id: str) -> bool:
    """Consume the pending greeting for this client (True once, then False)."""
    if client_id in _wants_greet:
        _wants_greet.discard(client_id)
        return True
    return False


def vision_allowed(now: float, min_gap: float) -> bool:
    """True if a spontaneous vision comment is allowed now (global throttle)."""
    return (now - _last_vision_ts) >= min_gap


def mark_vision(now: float) -> None:
    global _last_vision_ts
    _last_vision_ts = now


def note_face(client_id: str, seen: bool) -> int:
    """Track consecutive no-face frames. Returns the current miss streak
    (0 right after a face is seen)."""
    if seen:
        _noface[client_id] = 0
        return 0
    _noface[client_id] = _noface.get(client_id, 0) + 1
    return _noface[client_id]


_VISION_INTENT = re.compile(
    r"\b(what do you see|see me|look at me|looking at me|how do i look|"
    r"do i look|my outfit|my hat|check .*out|can you see)\b",
    re.IGNORECASE,
)


def is_vision_request(text: str) -> bool:
    """True if the guest is explicitly asking the character to look at them."""
    return bool(text and _VISION_INTENT.search(text))
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_camera_relay.py -v`
Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
git add server/camera_relay.py tests/test_camera_relay.py
git commit -m "feat(camera): pure decision module for remote camera (rate-limit, cache, throttle, intent)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 2: Shared face encoder + refactor the admin endpoint

**Files:**
- Modify: `server/camera_relay.py` (add `encode_face_from_b64`)
- Modify: `server/main.py:2814-2845` (`/admin/recognition/face` uses the shared encoder)
- Test: `tests/test_camera_relay.py` (add encoder tests)

**Interfaces:**
- Produces: `encode_face_from_b64(image_b64: str) -> tuple[bool, "np.ndarray|None"]`.
  `(False, None)` = encoder could not run (missing dep / bad image). `(True, None)` = ran, no face. `(True, <ndarray>)` = first face's 128-d float64 encoding.
- Consumed by: Task 3/4 (`/friend/see`) and the refactored `/admin/recognition/face`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_camera_relay.py`:

```python
import base64
import types


def _install_fake_face_recognition(monkeypatch, encs):
    """Inject a fake `face_recognition` module that returns `encs` from face_encodings."""
    fake = types.SimpleNamespace(
        load_image_file=lambda buf: "IMG",
        face_encodings=lambda img: encs,
    )
    monkeypatch.setitem(sys.modules, "face_recognition", fake)


def test_encode_returns_encoding_for_a_face(monkeypatch):
    import numpy as np
    _install_fake_face_recognition(monkeypatch, [np.zeros(128, dtype=float)])
    b64 = base64.b64encode(b"not-a-real-jpeg-but-decodes").decode()
    available, enc = cr.encode_face_from_b64(b64)
    assert available is True
    assert enc is not None and enc.shape == (128,)


def test_encode_true_but_none_when_no_face(monkeypatch):
    _install_fake_face_recognition(monkeypatch, [])
    b64 = base64.b64encode(b"whatever").decode()
    available, enc = cr.encode_face_from_b64(b64)
    assert available is True
    assert enc is None


def test_encode_unavailable_when_import_missing(monkeypatch):
    monkeypatch.setitem(sys.modules, "face_recognition", None)  # import -> ImportError
    available, enc = cr.encode_face_from_b64(base64.b64encode(b"x").decode())
    assert available is False
    assert enc is None


def test_encode_unavailable_on_bad_base64():
    available, enc = cr.encode_face_from_b64("!!!not base64!!!")
    assert available is False
    assert enc is None
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_camera_relay.py -k encode -v`
Expected: FAIL — `AttributeError: module 'camera_relay' has no attribute 'encode_face_from_b64'`.

- [ ] **Step 3: Add the encoder to `camera_relay.py`**

Append to `server/camera_relay.py`:

```python
def encode_face_from_b64(image_b64: str):
    """Decode a base64 image and return the FIRST face's 128-d encoding.

    Returns (available, encoding):
      (False, None) -> encoder could not run (missing face_recognition, bad image)
      (True, None)  -> ran fine, but no face was found
      (True, enc)   -> enc is a numpy float64 array, shape (128,)
    Never raises. CPU-heavy — callers should run this in an executor.
    """
    try:
        import base64
        import io
        import face_recognition
        import numpy as np
        raw = base64.b64decode(image_b64 or "", validate=True)
        if not raw:
            return (False, None)
        img = face_recognition.load_image_file(io.BytesIO(raw))
        encs = face_recognition.face_encodings(img)
    except Exception as e:
        if DEBUG_CAMERA:
            print(f"[camera] encode unavailable: {e}")
        return (False, None)
    if not encs:
        return (True, None)
    return (True, np.array(encs[0], dtype=np.float64))
```

- [ ] **Step 4: Run to verify they pass**

Run: `python -m pytest tests/test_camera_relay.py -k encode -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Refactor `/admin/recognition/face` to use the shared encoder**

In `server/main.py`, replace the decode/encode block in `recognition_face` (currently `main.py:2821-2833`). Find:

```python
    try:
        import base64, io
        import face_recognition
        import numpy as _np
        img_bytes = base64.b64decode(body.get("image_b64", ""))
        img = face_recognition.load_image_file(io.BytesIO(img_bytes))
        encs = face_recognition.face_encodings(img)
    except Exception as e:
        logger.warning(f"[RECOG] face decode/encode failed: {e}")
        return {"error": "recognition_unavailable", "detail": str(e)[:200]}
    if not encs:
        return {"detected": False, "reason": "no_face"}
    enc = _np.array(encs[0], dtype=_np.float64)
```

Replace with:

```python
    available, enc = camera_relay.encode_face_from_b64(body.get("image_b64", ""))
    if not available:
        return {"error": "recognition_unavailable"}
    if enc is None:
        return {"detected": False, "reason": "no_face"}
```

Then add the import next to main.py's existing `mirror`/`recognition_events` imports, matching their style (they are imported bare because `server/` is on `sys.path`):

```python
import camera_relay
```

- [ ] **Step 6: Run the full recognition + camera suites**

Run: `python -m pytest tests/test_camera_relay.py tests/test_recognition_inspector.py -v`
Expected: PASS (existing recognition-inspector tests still green; the refactor preserves the `recognition_unavailable` / `no_face` contract).

- [ ] **Step 7: Commit**

```bash
git add server/camera_relay.py server/main.py tests/test_camera_relay.py
git commit -m "refactor(camera): shared encode_face_from_b64, reuse in /admin/recognition/face

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 3: `POST /friend/see` — auth, guards, cache, camera_off (no recognition yet)

**Files:**
- Modify: `server/main.py` (new endpoint after `/friend/say_audio`, ~`main.py:2478`)
- Test: `tests/test_friend_camera.py` (new)

**Interfaces:**
- Consumes: `mirror_relay.authorize_friend_input`, `mirror_relay.get_control_mode`, module global `_MIRROR_CFG`, `live_config`, `camera_relay.{allow_frame,cache_frame,clear_client,encode_face_from_b64,note_face}`.
- Produces: endpoint `POST /friend/see` with body `{token,pin,name,id,image_b64,reason}` and JSON result `{"status":...}`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_friend_camera.py`:

```python
import asyncio
import base64
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

import pytest

import main  # heavy but cached
import camera_relay
import mirror as mirror_relay


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    camera_relay.reset_state()
    mirror_relay.reset_state()
    mirror_relay.set_control_mode("remote")
    monkeypatch.setattr(main, "_MIRROR_CFG", {"token": "T", "pin": "P"}, raising=False)
    yield
    camera_relay.reset_state()
    mirror_relay.reset_state()


def _good(**over):
    body = {"token": "T", "pin": "P", "name": "Jake", "id": "c1",
            "image_b64": base64.b64encode(b"frame").decode(), "reason": "tick"}
    body.update(over)
    return body


def test_see_rejects_bad_credentials():
    r = asyncio.run(main.friend_see(_good(pin="WRONG")))
    assert r["status"] == "error"
    assert r["reason"] == "bad_credentials"


def test_see_rejects_missing_client_id():
    r = asyncio.run(main.friend_see(_good(id="")))
    assert r["status"] == "error"
    assert r["reason"] == "no_client_id"


def test_see_rejects_oversized_image():
    r = asyncio.run(main.friend_see(_good(image_b64="A" * 8_000_001)))
    assert r["status"] == "error"
    assert r["reason"] == "too_large"


def test_see_rate_limits_second_fast_frame(monkeypatch):
    monkeypatch.setattr(camera_relay, "encode_face_from_b64", lambda b: (True, None))
    r1 = asyncio.run(main.friend_see(_good()))
    r2 = asyncio.run(main.friend_see(_good()))
    assert r1["status"] == "ok"
    assert r2.get("throttled") is True


def test_see_camera_off_clears_cache(monkeypatch):
    monkeypatch.setattr(camera_relay, "encode_face_from_b64", lambda b: (True, None))
    asyncio.run(main.friend_see(_good()))
    camera_relay.cache_frame("c1", b"x", now=1.0)
    r = asyncio.run(main.friend_see(_good(reason="camera_off")))
    assert r["status"] == "ok"
    assert camera_relay.get_cached_frame("c1", now=2.0, ttl=30.0) is None


def test_see_reports_recognition_unavailable(monkeypatch):
    monkeypatch.setattr(camera_relay, "encode_face_from_b64", lambda b: (False, None))
    r = asyncio.run(main.friend_see(_good()))
    assert r["status"] == "ok"
    assert r["recognition"] == "unavailable"


def test_see_no_face_returns_face_false(monkeypatch):
    monkeypatch.setattr(camera_relay, "encode_face_from_b64", lambda b: (True, None))
    r = asyncio.run(main.friend_see(_good()))
    assert r["status"] == "ok"
    assert r["face"] is False
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_friend_camera.py -v`
Expected: FAIL — `AttributeError: module 'main' has no attribute 'friend_see'`.

- [ ] **Step 3: Add the endpoint**

In `server/main.py`, immediately after the `friend_say_audio` function (ends ~`main.py:2477`), add:

```python
@app.post("/friend/see")
async def friend_see(request_body: dict = {}):
    """Remote guest CAMERA input (opt-in, FaceTime-style over the tunnel): a base64
    JPEG frame. Same friend auth as /friend/say. Server-side dlib encode feeds the
    SAME face gallery as the in-person camera; vision commentary (Task 5) is layered
    on top. Frames are RAM-only; only embeddings persist."""
    token = request_body.get("token") or ""
    pin = request_body.get("pin") or ""
    name = (request_body.get("name") or "").strip() or "Guest"
    client_id = (request_body.get("id") or "").strip()
    reason = (request_body.get("reason") or "tick").strip()
    ok, why = mirror_relay.authorize_friend_input(
        token, pin, _MIRROR_CFG, mirror_relay.get_control_mode())
    if not ok:
        return {"status": "error", "reason": why}
    if not client_id:
        return {"status": "error", "reason": "no_client_id"}
    if not live_config.get("camera_enabled", True):
        return {"status": "error", "reason": "camera_disabled"}
    now = time.time()
    if reason == "camera_off":
        camera_relay.clear_client(client_id)
        return {"status": "ok"}
    image_b64 = request_body.get("image_b64") or ""
    if len(image_b64) > 8_000_000:
        return {"status": "error", "reason": "too_large"}
    min_interval = float(live_config.get("camera_frame_min_interval", 2.0))
    if not camera_relay.allow_frame(client_id, now, min_interval):
        return {"status": "ok", "throttled": True}
    # dlib encode is CPU-heavy — keep it off the event loop (like STT).
    loop = asyncio.get_event_loop()
    available, enc = await loop.run_in_executor(
        None, camera_relay.encode_face_from_b64, image_b64)
    if not available:
        return {"status": "ok", "recognition": "unavailable"}
    try:
        camera_relay.cache_frame(client_id, base64.b64decode(image_b64), now)
    except Exception:
        pass
    if enc is None:
        camera_relay.note_face(client_id, False)
        return {"status": "ok", "face": False}
    camera_relay.note_face(client_id, True)
    if reason == "camera_on":
        camera_relay.request_greet(client_id)
    # Recognition + vision are wired in Tasks 4 and 5.
    return {"status": "ok", "face": True}
```

- [ ] **Step 4: Run to verify they pass**

Run: `python -m pytest tests/test_friend_camera.py -v`
Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
git add server/main.py tests/test_friend_camera.py
git commit -m "feat(camera): /friend/see endpoint (auth, rate-limit, size guard, frame cache, camera_off)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 4: Recognition wiring in `/friend/see`

**Files:**
- Modify: `server/main.py` (`friend_see`: add recognition between the `note_face(True)` line and the return)
- Test: `tests/test_friend_camera.py` (add recognition tests)

**Interfaces:**
- Consumes: module globals `_face_memory` (has `.find_match(enc) -> {"person_id","name","confidence","visit_count"}|None` and `.learn_guest(name, enc)`), `recognition_events.push(kind,name,conf,is_new,source)`.
- Produces: `/friend/see` result now includes `{"recognized": name|None, "is_new": bool}`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_friend_camera.py`:

```python
class _FakeFaceMem:
    def __init__(self, match=None):
        self._match = match
        self.learned = []
    def find_match(self, enc, tolerance=None):
        return self._match
    def learn_guest(self, name, enc):
        self.learned.append(name)


def test_see_enrolls_unknown_face_under_guest_name(monkeypatch):
    import numpy as np
    monkeypatch.setattr(camera_relay, "encode_face_from_b64",
                        lambda b: (True, np.zeros(128)))
    fm = _FakeFaceMem(match=None)
    monkeypatch.setattr(main, "_face_memory", fm, raising=False)
    pushed = []
    monkeypatch.setattr(main.recognition_events, "push",
                        lambda *a, **k: pushed.append(a))
    r = asyncio.run(main.friend_see(_good(name="Jake")))
    assert r["face"] is True
    assert r["recognized"] == "Jake"
    assert r["is_new"] is True
    assert fm.learned == ["Jake"]                 # enrolled under the known name
    assert pushed and pushed[0][0] == "face"      # kind == "face"
    assert pushed[0][4] == "remote_cam"           # source


def test_see_matches_known_face_without_reenroll(monkeypatch):
    import numpy as np
    monkeypatch.setattr(camera_relay, "encode_face_from_b64",
                        lambda b: (True, np.zeros(128)))
    fm = _FakeFaceMem(match={"person_id": 7, "name": "Rosa", "confidence": 0.82,
                             "visit_count": 3})
    monkeypatch.setattr(main, "_face_memory", fm, raising=False)
    monkeypatch.setattr(main.recognition_events, "push", lambda *a, **k: None)
    r = asyncio.run(main.friend_see(_good(name="Jake")))
    assert r["recognized"] == "Rosa"
    assert r["is_new"] is False
    assert fm.learned == []                        # NOT re-enrolled
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_friend_camera.py -k "enrolls or matches" -v`
Expected: FAIL — `KeyError: 'recognized'` (endpoint doesn't add it yet).

- [ ] **Step 3: Wire recognition into `friend_see`**

In `server/main.py`, in `friend_see`, replace the block from `camera_relay.note_face(client_id, True)` through the final `return {"status": "ok", "face": True}` with:

```python
    camera_relay.note_face(client_id, True)
    if reason == "camera_on":
        camera_relay.request_greet(client_id)
    recognized = None
    is_new = False
    if _face_memory is not None:
        try:
            m = _face_memory.find_match(enc)
            if m:
                recognized = m["name"]
                recognition_events.push("face", recognized,
                                        m.get("confidence", 0.0), False, "remote_cam")
            else:
                _face_memory.learn_guest(name, enc)   # remote guests always have a name
                recognized = name
                is_new = True
                recognition_events.push("face", name, 1.0, True, "remote_cam")
        except Exception as e:
            logger.warning(f"[CAMERA] recognition failed: {e}")
    # Vision commentary is wired in Task 5.
    return {"status": "ok", "face": True, "recognized": recognized, "is_new": is_new}
```

- [ ] **Step 4: Run to verify they pass**

Run: `python -m pytest tests/test_friend_camera.py -v`
Expected: PASS (all Task 3 + Task 4 tests).

- [ ] **Step 5: Commit**

```bash
git add server/main.py tests/test_friend_camera.py
git commit -m "feat(camera): unified face recognition/enroll in /friend/see (name always known)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 5: Vision commentary (`_camera_vision_comment` + camera_on/lull triggers)

**Files:**
- Modify: `server/main.py` (add `_camera_vision_comment`; call it from `friend_see`)
- Test: `tests/test_friend_camera.py` (add vision tests)

**Interfaces:**
- Consumes: `live_config`, `GAME_CONFIG`, `_active_ws`, `_get_idle_prompt`, `llm.generate_response(messages, model=...)`, `filter_response`, `analyze_text`, `_tts_executor`, `tts.synthesize_user`, `_idle_send_if_safe`, `_LLM_IDLE_TIMEOUT`, `camera_relay.{take_greet,vision_allowed,mark_vision,get_cached_frame}`.
- Produces: `async def _camera_vision_comment(frame_bytes: bytes, guest_name: str, reason: str) -> bool` (True iff a line was actually spoken). `/friend/see` result gains `"commented": bool`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_friend_camera.py`:

```python
def _stub_speak_chain(monkeypatch, captured):
    """Make the speak chain deterministic and capture the spoken text."""
    async def fake_gen(messages, model=None, **k):
        captured["messages"] = messages
        return {"text": "Nice party hat, Jake!", "emotion": "happy", "energy": 0.6}
    monkeypatch.setattr(main.llm, "generate_response", fake_gen)
    monkeypatch.setattr(main, "filter_response", lambda t: t)
    monkeypatch.setattr(main, "analyze_text",
                        lambda t: {"tts_text": t, "display_text": t, "pose_hint": None})
    monkeypatch.setattr(main.tts, "synthesize_user", lambda t: b"WAV")

    async def fake_idle_send(ws, text, audio, **k):
        captured["spoke"] = text
        return True
    monkeypatch.setattr(main, "_idle_send_if_safe", fake_idle_send)
    monkeypatch.setattr(main, "_active_ws", object(), raising=False)
    monkeypatch.setattr(main, "_get_idle_prompt", lambda: "You are the character.")


def test_vision_comment_speaks_and_sends_image(monkeypatch):
    cap = {}
    _stub_speak_chain(monkeypatch, cap)
    monkeypatch.setattr(main.live_config, "get",
                        lambda k, d=None: {"camera_vision_enabled": True,
                                           "camera_vision_model": "gemma3:27b"}.get(k, d))
    spoke = asyncio.run(main._camera_vision_comment(b"frame", "Jake", reason="camera_on"))
    assert spoke is True
    assert cap["spoke"] == "Nice party hat, Jake!"
    # the frame rode along as an Ollama image on the user message
    user_msgs = [m for m in cap["messages"] if m.get("role") == "user"]
    assert user_msgs and "images" in user_msgs[-1] and user_msgs[-1]["images"]


def test_vision_comment_skips_when_disabled(monkeypatch):
    cap = {}
    _stub_speak_chain(monkeypatch, cap)
    monkeypatch.setattr(main.live_config, "get",
                        lambda k, d=None: {"camera_vision_enabled": False}.get(k, d))
    spoke = asyncio.run(main._camera_vision_comment(b"frame", "Jake", reason="camera_on"))
    assert spoke is False
    assert "spoke" not in cap


def test_vision_comment_skips_when_no_model(monkeypatch):
    cap = {}
    _stub_speak_chain(monkeypatch, cap)
    monkeypatch.setattr(main.live_config, "get",
                        lambda k, d=None: {"camera_vision_enabled": True,
                                           "camera_vision_model": ""}.get(k, d))
    monkeypatch.setattr(main.GAME_CONFIG, "get", lambda k, d=None: "", raising=False)
    spoke = asyncio.run(main._camera_vision_comment(b"frame", "Jake", reason="camera_on"))
    assert spoke is False


def test_lull_comment_respects_global_throttle(monkeypatch):
    cap = {}
    _stub_speak_chain(monkeypatch, cap)
    monkeypatch.setattr(main.live_config, "get",
                        lambda k, d=None: {"camera_vision_enabled": True,
                                           "camera_vision_model": "gemma3:27b",
                                           "camera_vision_min_gap": 45}.get(k, d))
    first = asyncio.run(main._camera_vision_comment(b"f", "Jake", reason="lull"))
    second = asyncio.run(main._camera_vision_comment(b"f", "Jake", reason="lull"))
    assert first is True
    assert second is False    # throttled: two lull comments back-to-back
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_friend_camera.py -k vision -v`
Expected: FAIL — `AttributeError: module 'main' has no attribute '_camera_vision_comment'`.

- [ ] **Step 3: Add the helper and wire the triggers**

In `server/main.py`, add the helper near `friend_see` (module scope):

```python
async def _camera_vision_comment(frame_bytes: bytes, guest_name: str, reason: str) -> bool:
    """Turn the guest's camera frame into a short in-character spoken reaction, via the
    multimodal model. Reuses the /admin/watch_frame speak chain; the pygame client plays
    it and the mirror relays that audio to the remote browser. Returns True iff spoken.

    reason: 'camera_on' | 'on_demand' | 'lull'. camera_on / on_demand bypass the
    spontaneous-comment throttle (they are explicitly warranted)."""
    if not frame_bytes or _active_ws is None:
        return False
    if not live_config.get("camera_vision_enabled", True):
        return False
    model = live_config.get("camera_vision_model", "") or GAME_CONFIG.get("camera_vision_model", "")
    if not model:
        return False
    now = time.time()
    if reason == "lull" and not camera_relay.vision_allowed(
            now, float(live_config.get("camera_vision_min_gap", 45))):
        return False
    try:
        img_b64 = base64.b64encode(frame_bytes).decode("ascii")
        instr = (f"You can see {guest_name} on their camera right now. In one or two short, "
                 f"warm sentences, react to what you actually see, like their look, expression, "
                 f"or surroundings. Stay in character. Do not mention cameras or being an AI.")
        messages = [
            {"role": "system", "content": _get_idle_prompt()},
            {"role": "user", "content": instr, "images": [img_b64]},
        ]
        llm_response = await asyncio.wait_for(
            llm.generate_response(messages, model=model), timeout=_LLM_IDLE_TIMEOUT)
        text = filter_response((llm_response.get("text") or "").strip())
        if not text or len(text) < 3:
            return False
        analyzed = analyze_text(text)
        loop = asyncio.get_event_loop()
        audio = await loop.run_in_executor(
            _tts_executor, lambda: tts.synthesize_user(analyzed["tts_text"]))
        sent = await _idle_send_if_safe(
            _active_ws, analyzed["display_text"], audio,
            emotion=llm_response.get("emotion", "happy"),
            pose_hint=analyzed.get("pose_hint"))
        if sent:
            camera_relay.mark_vision(now)
        return bool(sent)
    except Exception as e:
        logger.warning(f"[CAMERA_VISION] failed: {e}")
        return False
```

Then wire it into `friend_see`: in `server/main.py`, replace the `friend_see` line
`    # Vision commentary is wired in Task 5.` and the following `return` with:

```python
    commented = False
    if _face_memory is not None and camera_relay.take_greet(client_id):
        commented = await _camera_vision_comment(frame_bytes_for(client_id, now), name, reason="camera_on")
    elif reason == "tick":
        frame = camera_relay.get_cached_frame(
            client_id, now, float(live_config.get("camera_frame_ttl", 30)))
        if frame is not None:
            commented = await _camera_vision_comment(frame, name, reason="lull")
    return {"status": "ok", "face": True, "recognized": recognized,
            "is_new": is_new, "commented": bool(commented)}
```

And add a tiny local accessor helper just above `friend_see` so the greeting uses the just-cached frame:

```python
def frame_bytes_for(client_id: str, now: float):
    """The frame we cached for this client this request (long TTL read; used for the
    camera_on greeting so we react to the frame that just arrived)."""
    return camera_relay.get_cached_frame(client_id, now, ttl=60.0)
```

> Note: `camera_on` sets a pending greet in Task 3/4; the greeting fires here on the first frame that actually contains a face (which may be a later `tick`), so `take_greet` is checked on every face frame, not only `camera_on`.

- [ ] **Step 4: Run to verify they pass**

Run: `python -m pytest tests/test_friend_camera.py -v`
Expected: PASS (all camera tests).

- [ ] **Step 5: Commit**

```bash
git add server/main.py tests/test_friend_camera.py
git commit -m "feat(camera): multimodal vision commentary on camera_on + throttled lulls

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 6: On-demand "what do you see?" in the friend text/voice paths

**Files:**
- Modify: `server/main.py` (`friend_say` ~`main.py:2398`; `friend_say_audio` ~`main.py:2431`)
- Test: `tests/test_friend_camera.py` (add on-demand tests)

**Interfaces:**
- Consumes: `camera_relay.is_vision_request`, `camera_relay.get_cached_frame`, `_camera_vision_comment`, `_log_guest_turn`, `_resolve_guest_name`.
- Produces: when a friend message is a vision request AND a fresh frame is cached, the character answers by *looking* (vision comment) and the normal text dispatch is skipped; result `{"status":"ok","commented":True}`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_friend_camera.py`:

```python
def test_say_routes_vision_request_to_camera_when_frame_cached(monkeypatch):
    mirror_relay.set_control_mode("remote")
    camera_relay.cache_frame("c1", b"frame", now=main.time.time())
    calls = {}
    async def fake_comment(frame, name, reason):
        calls["reason"] = reason
        calls["frame"] = frame
        return True
    monkeypatch.setattr(main, "_camera_vision_comment", fake_comment)
    async def fake_log(ws, who, text):
        return None
    monkeypatch.setattr(main, "_log_guest_turn", fake_log)
    monkeypatch.setattr(main, "_active_ws", object(), raising=False)
    dispatched = {"n": 0}
    async def fake_dispatch(*a, **k):
        dispatched["n"] += 1
        return {"status": "ok"}
    monkeypatch.setattr(main, "_dispatch_user_text", fake_dispatch)

    body = {"token": "T", "pin": "P", "name": "Jake", "id": "c1",
            "text": "how do I look?"}
    r = asyncio.run(main.friend_say(body))
    assert r.get("commented") is True
    assert calls["reason"] == "on_demand"
    assert dispatched["n"] == 0          # normal text reply was skipped


def test_say_normal_text_still_dispatches(monkeypatch):
    mirror_relay.set_control_mode("remote")
    monkeypatch.setattr(main, "_active_ws", object(), raising=False)
    dispatched = {"n": 0}
    async def fake_dispatch(text, guest_name=None, **k):
        dispatched["n"] += 1
        return {"status": "ok"}
    monkeypatch.setattr(main, "_dispatch_user_text", fake_dispatch)
    async def fake_bt(obj):
        return None
    monkeypatch.setattr(main.mirror_relay, "broadcast_text", fake_bt)

    body = {"token": "T", "pin": "P", "name": "Jake", "id": "c1", "text": "tell me a joke"}
    r = asyncio.run(main.friend_say(body))
    assert dispatched["n"] == 1          # ordinary path unaffected
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_friend_camera.py -k "vision_request or normal_text" -v`
Expected: FAIL — first test fails because `friend_say` still dispatches (no on-demand branch).

- [ ] **Step 3: Add the on-demand branch**

In `server/main.py` `friend_say`, after the turn is granted and the `broadcast_text({"type":"turn",...})` call, and BEFORE `return await _dispatch_user_text(text, guest_name=name)`, insert:

```python
    # On-demand "look at me": if this is a vision request and we have a fresh camera
    # frame for this guest, answer by LOOKING instead of the normal text reply.
    if camera_relay.is_vision_request(text):
        frame = camera_relay.get_cached_frame(
            client_id, time.time(), float(live_config.get("camera_frame_ttl", 30)))
        if frame is not None:
            await _log_guest_turn(_active_ws, _resolve_guest_name(name), text)
            spoke = await _camera_vision_comment(frame, name, reason="on_demand")
            return {"status": "ok", "commented": bool(spoke)}
```

Apply the identical block in `friend_say_audio`, after its turn grant / broadcast and before `result = await _dispatch_user_text(text, guest_name=name)` — using the STT-produced `text`. Return `{"status": "ok", "commented": bool(spoke), "transcript": text}` in that path so the browser still echoes what it heard.

- [ ] **Step 4: Run to verify they pass**

Run: `python -m pytest tests/test_friend_camera.py -v`
Expected: PASS (all camera tests, including on-demand).

- [ ] **Step 5: Commit**

```bash
git add server/main.py tests/test_friend_camera.py
git commit -m "feat(camera): on-demand 'what do you see' routes friend chat to a vision look

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 7: Client — camera opt-in + capture loop in `friend.html`

**Files:**
- Modify: `server/static/friend.html`
- Test: `tests/test_friend_camera.py` (served-page smoke test)

**Interfaces:**
- Consumes: `POST /friend/see` (Tasks 3-5).
- Produces: a `📷` toggle, self-view, ~2.5s capture loop, consent line, visibility pause. (No JS unit harness in this repo — behavior is verified live in Task 9; the pytest here only asserts the page ships the elements.)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_friend_camera.py`:

```python
def test_friend_html_ships_camera_ui():
    path = os.path.join(os.path.dirname(__file__), "..", "server", "static", "friend.html")
    with open(path, encoding="utf-8") as f:
        html = f.read()
    assert 'id="cam"' in html            # the camera toggle button
    assert "/friend/see" in html         # posts frames to the new endpoint
    assert "getUserMedia" in html        # opens the camera
    assert "camera_on" in html and "camera_off" in html
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_friend_camera.py -k ships_camera_ui -v`
Expected: FAIL — the string `id="cam"` is not in the page yet.

- [ ] **Step 3: Add the camera button to the bar**

In `server/static/friend.html`, in the `#bar` div (currently the mic + send buttons, ~line 63-67), add a camera button before `#mic`:

```html
    <button id="cam" title="Turn camera on/off">📷</button>
```

Add a self-view element after the `#stage` div (~line 55), and a small style. In the `<style>` block add:

```css
  #selfwrap{position:fixed;right:10px;bottom:70px;width:120px;z-index:15;display:none}
  #selfwrap.on{display:block}
  #selfview{width:120px;border-radius:10px;border:2px solid #e23;background:#000}
  #camdot{position:absolute;top:4px;left:4px;width:10px;height:10px;border-radius:50%;
          background:#e23;box-shadow:0 0 6px #e23}
  #camnote{font-size:12px;color:#fc8;padding:2px 4px;text-align:center}
  #cam.on{background:#e23;border-color:#f88}
```

After the `#stage` div, add:

```html
  <div id="selfwrap">
    <video id="selfview" autoplay muted playsinline></video>
    <span id="camdot"></span>
    <div id="camnote">Mario can see you</div>
  </div>
```

- [ ] **Step 4: Add the capture loop script**

At the end of the `<script>` block in `friend.html` (after the mic handlers, ~line 360), add:

```javascript
// --- opt-in camera: guest -> POST /friend/see (recognition + vision) -----------
const camBtn = document.getElementById("cam");
const selfWrap = document.getElementById("selfwrap");
const selfView = document.getElementById("selfview");
let camStream = null, camTimer = null, camOn = false, camConsented = false;
const CAM_CANVAS = document.createElement("canvas");

async function postSee(reason){
  try {
    let image_b64 = "";
    if (reason !== "camera_off" && camStream && selfView.videoWidth){
      const vw = selfView.videoWidth, vh = selfView.videoHeight;
      const scale = Math.min(1, 480 / Math.max(vw, vh));
      CAM_CANVAS.width = Math.round(vw * scale);
      CAM_CANVAS.height = Math.round(vh * scale);
      CAM_CANVAS.getContext("2d").drawImage(selfView, 0, 0, CAM_CANVAS.width, CAM_CANVAS.height);
      image_b64 = CAM_CANVAS.toDataURL("image/jpeg", 0.6).split(",")[1] || "";
    }
    await fetch("/friend/see", {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        token: TOKEN, pin: (localStorage.getItem("mirror_pin")||""),
        name: myName, id: clientId, image_b64, reason
      })
    });
  } catch(e){}
}
async function camStart(){
  if (camOn || !myName) return;
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia){
    statusEl.textContent = "📷 not supported here"; return;
  }
  if (!camConsented){
    camConsented = confirm("Mario can see you and may remember your face. Turn the camera off anytime. Turn it on now?");
    if (!camConsented) return;
  }
  try { camStream = await navigator.mediaDevices.getUserMedia({video: true, audio: false}); }
  catch(e){ statusEl.textContent = "📷 allow camera access"; return; }
  selfView.srcObject = camStream;
  camOn = true; camBtn.classList.add("on"); selfWrap.classList.add("on");
  postSee("camera_on");
  camTimer = setInterval(() => { if (!document.hidden) postSee("tick"); }, 2500);
}
function camStop(){
  if (!camOn) return;
  camOn = false; camBtn.classList.remove("on"); selfWrap.classList.remove("on");
  if (camTimer){ clearInterval(camTimer); camTimer = null; }
  try { camStream && camStream.getTracks().forEach(t => t.stop()); } catch(e){}
  camStream = null; selfView.srcObject = null;
  postSee("camera_off");
}
camBtn.addEventListener("click", () => { camOn ? camStop() : camStart(); });
window.addEventListener("beforeunload", () => { if (camOn) camStop(); });
```

- [ ] **Step 5: Run the served-page smoke test**

Run: `python -m pytest tests/test_friend_camera.py -k ships_camera_ui -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add server/static/friend.html tests/test_friend_camera.py
git commit -m "feat(camera): friend.html opt-in camera, self-view, 2.5s capture loop

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 8: Config keys, live flags, and optional dependency

**Files:**
- Modify: `server/live_flags.py`
- Modify: `config_live.json`
- Modify: `config.example.json`
- Modify: `server/requirements.txt`
- Test: `tests/test_camera_relay.py` (flag/config presence)

**Interfaces:**
- Consumes: nothing new.
- Produces: `camera_enabled`, `camera_vision_enabled`, `camera_vision_min_gap` live flags; documented `camera_frame_min_interval`, `camera_frame_ttl`, `camera_vision_model` config keys.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_camera_relay.py`:

```python
def test_live_flags_include_camera_toggles():
    import live_flags as lf
    keys = {f["key"] for f in lf.LIVE_FLAGS}
    assert {"camera_enabled", "camera_vision_enabled", "camera_vision_min_gap"} <= keys
    # defaults are sane
    d = lf.flag_defaults()
    assert d["camera_enabled"] is True
    assert d["camera_vision_enabled"] is True
    assert d["camera_vision_min_gap"] == 45


def test_config_example_documents_camera_keys():
    import json
    path = os.path.join(os.path.dirname(__file__), "..", "config.example.json")
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)   # must remain valid JSON
    blob = json.dumps(cfg)
    for k in ("camera_enabled", "camera_vision_enabled", "camera_vision_model",
              "camera_frame_min_interval", "camera_vision_min_gap", "camera_frame_ttl"):
        assert k in blob, k
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_camera_relay.py -k "camera_toggles or example_documents" -v`
Expected: FAIL — camera flags not in `live_flags.py`.

- [ ] **Step 3: Add the live flags**

In `server/live_flags.py`, add to the `LIVE_FLAGS` list (before the closing `]`):

```python
    {"key": "camera_enabled", "label": "Remote camera", "type": "bool",
     "default": True, "group": "features", "coerce": _b},
    {"key": "camera_vision_enabled", "label": "Camera vision comments", "type": "bool",
     "default": True, "group": "features", "coerce": _b},
    {"key": "camera_vision_min_gap", "label": "Camera comment gap (s)", "type": "number",
     "default": 45, "min": 5, "max": 600, "group": "setup", "coerce": _num(5, 600, int)},
```

- [ ] **Step 4: Add config defaults + documentation**

In `config_live.json`, add these keys (keep valid JSON — add commas as needed):

```json
  "camera_enabled": true,
  "camera_vision_enabled": true,
  "camera_vision_model": "gemma3:27b",
  "camera_frame_min_interval": 2.0,
  "camera_vision_min_gap": 45,
  "camera_frame_ttl": 30
```

In `config.example.json`, add the same keys with the same values so they are discoverable (this file is the tracked template; `config.json` is gitignored).

- [ ] **Step 5: Add the optional server dependency**

In `server/requirements.txt`, append:

```
# === Optional: server-side face recognition (remote camera over the tunnel) ===
# Needed by POST /friend/see and POST /admin/recognition/face to encode faces on
# the server. Requires cmake + dlib + (Windows) Visual C++ Build Tools. The feature
# degrades gracefully if absent (recognition returns "unavailable"; self-view still works).
#   pip install cmake && pip install dlib && pip install face_recognition
# face_recognition>=1.3.0
```

- [ ] **Step 6: Run to verify they pass**

Run: `python -m pytest tests/test_camera_relay.py -k "camera_toggles or example_documents" -v`
Expected: PASS.

- [ ] **Step 7: Run the whole camera + flags suite**

Run: `python -m pytest tests/test_camera_relay.py tests/test_friend_camera.py tests/test_admin_live_control.py -v`
Expected: PASS (new camera flags don't break the live-flags manifest tests).

- [ ] **Step 8: Commit**

```bash
git add server/live_flags.py config_live.json config.example.json server/requirements.txt tests/test_camera_relay.py
git commit -m "feat(camera): live flags + config keys + optional face_recognition dep

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 9: Live end-to-end verification (manual — MANDATORY audio check)

**Files:** none (verification only). Follows `.claude/rules/testing.md`.

**Pre-req verification (from the spec's build-time verifies):**

- [ ] **Step 1: Confirm the server env can encode faces**

On the deployment box, in the server venv:
Run: `python -c "import face_recognition; print('ok')"`
Expected: `ok`. If it fails, install per the `server/requirements.txt` note — otherwise recognition returns `"unavailable"` (camera still shows a self-view, but no memory).

- [ ] **Step 2: Confirm the multimodal model answers with an image**

Run:
```bash
python - <<'PY'
import base64, httpx
img = base64.b64encode(open("tests/fixtures/any_small.jpg","rb").read()).decode()
r = httpx.post("http://localhost:11434/api/chat", json={
  "model": "gemma3:27b", "stream": False,
  "messages": [{"role":"user","content":"In 5 words, what do you see?","images":[img]}]
}, timeout=60)
print(r.json().get("message",{}).get("content"))
PY
```
Expected: a short description of the image (proves `images:[…]` works on this box). If the model isn't multimodal, set `camera_vision_enabled: false` — recognition still works.

- [ ] **Step 3: Drive the live flow over the tunnel**

Start the server + pygame client (`start_server.bat`, then the client). Ensure mirror `control_mode` is `remote` with a token+pin. Open `/friend?token=…` on a phone, join with the PIN + a name, tap **📷**, accept the consent prompt.

Verify, per `.claude/rules/testing.md`:
- [ ] Self-view appears; the red dot shows.
- [ ] Server log shows `/friend/see` hits and a `recognition_events` face push (`source=remote_cam`).
- [ ] The character speaks a camera greeting. In the CLIENT log confirm: a `mario says:` line, `received audio: NNN bytes`, `[audio_playback] _play_wav: playing NNN bytes`, AND `[audio_playback] _play_wav: done`.
- [ ] The spoken text matches the speech bubble text.
- [ ] Say / type "how do I look?" → the character reacts to the actual frame (on-demand look).
- [ ] Disconnect + reconnect later with the same face → greeted by name (persistence).
- [ ] For a non-Mario character: the greeting + on-demand comment contain ZERO Mario references, in both bubble text and audio.

- [ ] **Step 4: Run the full test suite**

Run: `python -m pytest -q`
Expected: all green (existing 636+ tests plus the new camera tests).

- [ ] **Step 5: Finish the branch**

Use `superpowers:finishing-a-development-branch` to merge `feature/camera-over-tunnel` (see Execution Handoff).

---

## Self-Review

**Spec coverage** (each spec section → task):
- §1 recognize + comment → Tasks 4 (recognition) + 5 (vision). ✅
- §1 balanced glance (cheap recog per tick, vision only at key moments) → Task 3 rate-limit, Task 5 camera_on/lull throttle, Task 6 on-demand. ✅
- §1 remember across parties → Task 4 `learn_guest` into the persistent gallery. ✅
- §4 transport HTTP POST → Task 3 endpoint + Task 7 client loop. ✅
- §5.1 client (button, self-view, cadence, visibility, consent, camera_off) → Task 7. ✅
- §5.2 endpoint (auth, rate-limit, size guard, executor encode, RAM cache) → Task 3. ✅
- §5.3 reuse recognition (find_match / learn_guest / push; name always known) → Task 4. ✅
- §5.4 vision commentary (images on quality model, filter + isolation, ambient/no turn-gate, triggers) → Tasks 5, 6. ✅
- §5.5 degradation (no dlib → unavailable; non-multimodal → skip) → Task 2 (encoder contract), Task 5 (`camera_vision_enabled`/no-model skip). ✅
- §6 config keys → Task 8. ✅
- §7 no-face no-op / edge cases → Task 3 (`note_face`, `face:false`). ✅
- §8 privacy (RAM-only frames, embeddings only) → Tasks 1/3 (cache TTL + `clear_client`). ✅
- §9 optional dep → Task 8. ✅
- §10 tests → Tasks 1-8 unit + Task 9 live audio-verify. ✅

**Placeholder scan:** no TBD/TODO; every code + test step is complete. ✅

**Type consistency:** `encode_face_from_b64 -> (available: bool, enc)` used identically in Tasks 2/3. `_camera_vision_comment(frame_bytes, guest_name, reason) -> bool` defined in Task 5, called in Tasks 5/6. `find_match` returns `{"person_id","name","confidence"}` (Task 4 reads `["name"]`/`.get("confidence")`). `camera_relay` public names match between Task 1 definition and Tasks 3-6 use. ✅

**Note on the no-face nudge:** the spec (§7) allows one throttled "move into the light" nudge after `camera_on`. This plan tracks the miss streak (`note_face`) but does not speak the nudge, to avoid talking over a silent guest; the counter is in place so the nudge is a trivial follow-up if wanted. Flagged rather than silently dropped.
