# Recognition Inspector Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A `/recognition` admin page that proves Mario's face + voice recognition works — see who he knows, enroll/test a face photo + voice clip, and watch live recognition events.

**Architecture:** A small importable `recognition_events` module (event ring-buffer + a name→id helper, unit-testable), thin FastAPI endpoints in `server/main.py` that reuse the existing `face_memory` / `speaker_id` / `stt` functions, one static HTML page, and two one-line hooks into the live face/voice paths.

**Tech Stack:** Python 3.12, FastAPI/Starlette, `face_recognition` (dlib, in venv), `resemblyzer`, `faster-whisper`, vanilla HTML/JS, pytest, `ast` for structural tests.

## Global Constraints

- `server/main.py` logs via `logger` (NOT `print`).
- Uploads are **base64-in-JSON** (`{"image_b64": ...}` / `{"wav_b64": ...}`), matching the existing `register_speaker` base64 pattern — do NOT add FastAPI `UploadFile`/multipart.
- Do NOT change recognition thresholds (face euclidean 0.6, voice cosine 0.65).
- `/admin/recognition/*` endpoints honor `GAME_CONFIG["admin_api_key"]` when set (reject mismatched `api_key`), like other `/admin` endpoints.
- `server.main` is NOT importable in the unit env (`tests/test_edge_cases.py:1347`) — verify its internals by parsing `server/main.py` AST.
- Run tests with `venv/Scripts/python.exe -m pytest ...`.
- Wrap every recognition call in try/except — a failure returns JSON `{"error": ...}`, never a 500.
- Git: stage specific files only (never `git add -A`; Qdrant `.lock` files must not be committed). Commit trailer: `Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>`.

## Existing functions (reuse — exact signatures)

- `face_memory` instance is the module global `_face_memory` in `main.py`.
  - `_face_memory.get_all_faces() -> [{"person_id","name","visit_count","first_seen","last_seen"}]`
  - `_face_memory.find_match(encoding: np.ndarray, tolerance=None) -> {"person_id","name","confidence","visit_count"} | None`
  - `_face_memory.store_face(person_id: int, name: str, encoding: np.ndarray)` (UPSERT by person_id)
- `speaker_id.list_speakers() -> [{"id","name"}]`
- `speaker_id.identify_speaker(audio_pcm: bytes, sample_rate=16000) -> {"name","speaker_id","confidence","is_new"}`
- `speaker_id.register_speaker(name: str, audio_pcm: bytes, sample_rate=16000) -> int`
- `stt.transcribe(audio_pcm: bytes, sample_rate=16000) -> str`
- Live face path: `face_enrollment.resolve_faces(...)` at `main.py:6369`, returns `{"detected":[{"name","person_id"|None,"confidence"?}], "new_face_count", "pending_encoding"}`.
- Live voice path: `speaker_id.identify_speaker(...)` in `handle_audio` (the `speaker_info` block, ~`main.py:5560`).
- Static page pattern: open an HTML file under `server/static/`, return `HTMLResponse` (see `friend_page` / `control_page`).

**Note on audio format:** `identify_speaker`/`register_speaker` expect raw int16 PCM bytes; an uploaded `.wav` has a 44-byte header. Decode it with the stdlib `wave` module (Task 3).

---

### Task 1: `recognition_events` module (event buffer + name→id helper)

**Files:**
- Create: `server/recognition_events.py`
- Test: `tests/test_recognition_inspector.py`

**Interfaces:**
- Produces:
  - `push(kind: str, name: str|None, confidence: float, is_new: bool, source: str) -> dict`
  - `recent(since: int = 0) -> list[dict]` (events with `seq > since`, oldest→newest)
  - `person_id_for_name(name: str) -> int` (deterministic, stable per name)

- [ ] **Step 1: Write the failing test**

Create `tests/test_recognition_inspector.py`:

```python
"""Tests for the Recognition Inspector (server/recognition_events.py + main.py routes)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

import recognition_events as re_mod


def setup_function(_):
    re_mod._events.clear()
    re_mod._seq = 0


def test_push_appends_and_assigns_increasing_seq():
    a = re_mod.push("face", "Alice", 0.82, False, "live")
    b = re_mod.push("voice", "Bob", 0.71, False, "upload")
    assert a["seq"] == 1 and b["seq"] == 2
    assert a["kind"] == "face" and a["name"] == "Alice" and a["source"] == "live"
    assert "ts" in a


def test_recent_filters_by_since():
    re_mod.push("face", "A", 1.0, True, "live")
    re_mod.push("face", "B", 1.0, True, "live")
    assert [e["name"] for e in re_mod.recent(since=0)] == ["A", "B"]
    assert [e["name"] for e in re_mod.recent(since=1)] == ["B"]
    assert re_mod.recent(since=2) == []


def test_person_id_for_name_is_stable_and_distinct():
    assert re_mod.person_id_for_name("Alice") == re_mod.person_id_for_name("alice")
    assert re_mod.person_id_for_name("Alice") != re_mod.person_id_for_name("Bob")
    assert isinstance(re_mod.person_id_for_name("Alice"), int)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/Scripts/python.exe -m pytest tests/test_recognition_inspector.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'recognition_events'`.

- [ ] **Step 3: Write minimal implementation**

Create `server/recognition_events.py`:

```python
"""In-memory recognition-event feed for the Recognition Inspector page, plus a
deterministic name->person_id helper for ad-hoc enrollment. Importable + pure so
it is unit-testable (server/main.py is not)."""
import hashlib
import time
from collections import deque

_events: deque = deque(maxlen=100)
_seq: int = 0


def push(kind: str, name, confidence: float, is_new: bool, source: str) -> dict:
    """Record one recognition event. kind: 'face'|'voice'. source: 'live'|'upload'."""
    global _seq
    _seq += 1
    evt = {
        "seq": _seq,
        "ts": time.time(),
        "kind": kind,
        "name": name,
        "confidence": round(float(confidence or 0.0), 3),
        "is_new": bool(is_new),
        "source": source,
    }
    _events.append(evt)
    return evt


def recent(since: int = 0) -> list:
    """Events with seq > since, oldest first."""
    return [e for e in _events if e["seq"] > since]


def person_id_for_name(name: str) -> int:
    """Stable positive person_id derived from the (case-insensitive) name, so
    re-enrolling the same name UPSERTs the same face_encodings row."""
    digest = hashlib.md5(name.strip().lower().encode("utf-8")).hexdigest()
    return int(digest[:8], 16)  # 0 .. ~4.29e9, positive
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/Scripts/python.exe -m pytest tests/test_recognition_inspector.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add server/recognition_events.py tests/test_recognition_inspector.py
git commit -m "feat(recognition): event ring-buffer + name->id helper module" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 2: Roster, events, and page-serve endpoints

**Files:**
- Modify: `server/main.py` (add `import recognition_events` near the other server imports; add 3 routes — place them next to the other `/admin` routes, e.g. after `admin_lookup_face`)
- Create: `server/static/recognition.html` (minimal stub — full UI in Task 4)
- Test: `tests/test_recognition_inspector.py` (add AST tests)

**Interfaces:**
- Consumes: `recognition_events.recent` (Task 1), `_face_memory.get_all_faces`, `speaker_id.list_speakers`.
- Produces routes: `GET /recognition`, `GET /admin/recognition/roster`, `GET /admin/recognition/events`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_recognition_inspector.py`:

```python
import ast

_MAIN = os.path.join(os.path.dirname(__file__), "..", "server", "main.py")


def _main_src():
    with open(_MAIN, encoding="utf-8") as f:
        return f.read()


def test_main_imports_recognition_events():
    assert "import recognition_events" in _main_src()


def test_roster_and_events_routes_declared():
    src = _main_src()
    assert '"/recognition"' in src or "'/recognition'" in src
    assert "/admin/recognition/roster" in src
    assert "/admin/recognition/events" in src


def test_recognition_html_stub_exists():
    p = os.path.join(os.path.dirname(__file__), "..", "server", "static", "recognition.html")
    assert os.path.exists(p), "server/static/recognition.html must exist"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `venv/Scripts/python.exe -m pytest tests/test_recognition_inspector.py -q`
Expected: the 3 new tests FAIL (import + routes + html absent).

- [ ] **Step 3a: Add the import**

In `server/main.py`, with the other server-module imports (near `import command_handlers`), add:

```python
import recognition_events
```

- [ ] **Step 3b: Create the page stub**

Create `server/static/recognition.html`:

```html
<!doctype html><html><head><meta charset="utf-8"><title>Recognition Inspector</title></head>
<body><h1>Recognition Inspector</h1><p>Loading…</p></body></html>
```

- [ ] **Step 3c: Add the routes**

In `server/main.py`, after the `admin_lookup_face` endpoint, add:

```python
_RECOGNITION_HTML_PATH = os.path.join(os.path.dirname(__file__), "static", "recognition.html")


def _recognition_admin_ok(body_or_params: dict) -> bool:
    key = GAME_CONFIG.get("admin_api_key", "")
    return (not key) or body_or_params.get("api_key") == key


@app.get("/recognition")
async def recognition_page():
    """Serve the Recognition Inspector page."""
    try:
        with open(_RECOGNITION_HTML_PATH, encoding="utf-8") as f:
            return HTMLResponse(f.read())
    except Exception:
        return HTMLResponse("<h1>recognition page missing</h1>", status_code=500)


@app.get("/admin/recognition/roster")
async def recognition_roster():
    """Who Mario knows: enrolled faces + voices."""
    try:
        faces = _face_memory.get_all_faces() if _face_memory else []
    except Exception as e:
        faces = []
        logger.warning(f"[RECOG] roster faces failed: {e}")
    try:
        voices = speaker_id.list_speakers()
    except Exception as e:
        voices = []
        logger.warning(f"[RECOG] roster voices failed: {e}")
    return {"faces": faces, "voices": voices}


@app.get("/admin/recognition/events")
async def recognition_events_feed(since: int = 0):
    """Recent recognition events newer than `since` (seq)."""
    return {"events": recognition_events.recent(since)}
```

- [ ] **Step 4: Run tests + compile**

Run: `venv/Scripts/python.exe -m pytest tests/test_recognition_inspector.py -q` → PASS.
Run: `venv/Scripts/python.exe -m py_compile server/main.py` → success.

- [ ] **Step 5: Commit**

```bash
git add server/main.py server/static/recognition.html tests/test_recognition_inspector.py
git commit -m "feat(recognition): roster + events + page-serve endpoints" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 3: Face + voice test/enroll endpoints

**Files:**
- Modify: `server/main.py` (add 2 POST routes after the events route)
- Test: `tests/test_recognition_inspector.py` (synthetic face round-trip + AST)

**Interfaces:**
- Consumes: `recognition_events.push`/`person_id_for_name`, `_face_memory.store_face`/`find_match`, `speaker_id.identify_speaker`/`register_speaker`, `stt.transcribe`.
- Produces routes: `POST /admin/recognition/face`, `POST /admin/recognition/voice`.

- [ ] **Step 1: Write the failing test (synthetic face round-trip + AST)**

Append to `tests/test_recognition_inspector.py`:

```python
import numpy as np
import recognition_events as _re2


def test_face_store_then_find_roundtrip(tmp_path):
    # Reuse the real face_memory module against a temp DB; synthetic 128-dim vector.
    import face_memory
    fm = face_memory.FaceMemory(str(tmp_path / "faces.db"))
    enc = np.zeros(128, dtype=np.float64); enc[0] = 1.0
    pid = _re2.person_id_for_name("TestAlice")
    fm.store_face(pid, "TestAlice", enc)
    m = fm.find_match(enc)
    assert m is not None and m["name"] == "TestAlice" and m["confidence"] > 0.95
    far = np.zeros(128, dtype=np.float64); far[1] = 5.0
    assert fm.find_match(far) is None  # beyond 0.6 tolerance


def test_face_voice_routes_declared():
    src = _main_src()
    assert "/admin/recognition/face" in src
    assert "/admin/recognition/voice" in src
```

(If `FaceMemory`'s constructor name/signature differs, adjust to the real one in `server/face_memory.py` — it is `FaceMemory(db_path, match_tolerance=0.6, collection_name="mario_faces")`.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `venv/Scripts/python.exe -m pytest tests/test_recognition_inspector.py -q`
Expected: `test_face_voice_routes_declared` FAILS (routes absent). `test_face_store_then_find_roundtrip` should PASS already (it tests existing `face_memory`) — that is fine, it guards the behavior the endpoint relies on.

- [ ] **Step 3: Add the endpoints**

In `server/main.py`, after `recognition_events_feed`, add:

```python
@app.post("/admin/recognition/face")
async def recognition_face(body: dict):
    """Enroll (if `name` given) or test-recognize a face from a base64 image."""
    if not _recognition_admin_ok(body):
        return {"error": "unauthorized"}
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
    name = (body.get("name") or "").strip()
    if name:
        pid = recognition_events.person_id_for_name(name)
        _face_memory.store_face(pid, name, enc)
        recognition_events.push("face", name, 1.0, True, "upload")
        return {"enrolled": True, "name": name}
    m = _face_memory.find_match(enc)
    if m:
        recognition_events.push("face", m["name"], m["confidence"], False, "upload")
        return {"detected": True, "name": m["name"], "confidence": m["confidence"], "is_new": False}
    recognition_events.push("face", None, 0.0, True, "upload")
    return {"detected": True, "name": None, "is_new": True}


def _wav_to_pcm(wav_bytes: bytes):
    """Decode an uploaded WAV (base64-decoded bytes) to (int16 PCM bytes, rate)."""
    import io, wave
    with wave.open(io.BytesIO(wav_bytes), "rb") as w:
        rate = w.getframerate()
        frames = w.readframes(w.getnframes())
    return frames, rate


@app.post("/admin/recognition/voice")
async def recognition_voice(body: dict):
    """Enroll (if `name` given) or test-recognize a speaker from a base64 WAV."""
    if not _recognition_admin_ok(body):
        return {"error": "unauthorized"}
    try:
        import base64
        wav_bytes = base64.b64decode(body.get("wav_b64", ""))
        pcm, rate = _wav_to_pcm(wav_bytes)
    except Exception as e:
        logger.warning(f"[RECOG] voice decode failed: {e}")
        return {"error": "bad_audio", "detail": str(e)[:200]}
    name = (body.get("name") or "").strip()
    try:
        if name:
            sid = speaker_id.register_speaker(name, pcm, rate)
            recognition_events.push("voice", name, 1.0, True, "upload")
            return {"enrolled": True, "name": name, "speaker_id": sid}
        info = speaker_id.identify_speaker(pcm, rate)
        try:
            transcript = stt.transcribe(pcm, rate)
        except Exception:
            transcript = ""
        recognition_events.push("voice", info.get("name"), info.get("confidence", 0.0),
                                info.get("is_new", True), "upload")
        return {"transcript": transcript, "name": info.get("name"),
                "confidence": info.get("confidence", 0.0), "is_new": info.get("is_new", True)}
    except Exception as e:
        logger.warning(f"[RECOG] voice identify/enroll failed: {e}")
        return {"error": "recognition_unavailable", "detail": str(e)[:200]}
```

- [ ] **Step 4: Run tests + compile**

Run: `venv/Scripts/python.exe -m pytest tests/test_recognition_inspector.py -q` → PASS.
Run: `venv/Scripts/python.exe -m py_compile server/main.py` → success.

- [ ] **Step 5: Commit**

```bash
git add server/main.py tests/test_recognition_inspector.py
git commit -m "feat(recognition): face + voice enroll/test endpoints" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 4: The Recognition Inspector page (full UI)

**Files:**
- Modify: `server/static/recognition.html` (replace the stub)
- Test: `tests/test_recognition_inspector.py` (structure assertions)

**Interfaces:**
- Consumes: `GET /admin/recognition/roster`, `POST /admin/recognition/face`, `POST /admin/recognition/voice`, `GET /admin/recognition/events`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_recognition_inspector.py`:

```python
def test_recognition_html_has_three_panels_and_calls():
    p = os.path.join(os.path.dirname(__file__), "..", "server", "static", "recognition.html")
    html = open(p, encoding="utf-8").read()
    for needle in ("/admin/recognition/roster", "/admin/recognition/face",
                   "/admin/recognition/voice", "/admin/recognition/events",
                   "image_b64", "wav_b64"):
        assert needle in html, f"recognition.html must reference {needle}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/Scripts/python.exe -m pytest tests/test_recognition_inspector.py::test_recognition_html_has_three_panels_and_calls -q`
Expected: FAIL (stub lacks the calls).

- [ ] **Step 3: Write the page**

Replace `server/static/recognition.html` with:

```html
<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Mario — Recognition Inspector</title>
<style>
 body{font-family:system-ui,sans-serif;margin:0;background:#10131a;color:#e8eaed}
 h1{background:#e52521;margin:0;padding:12px 16px;font-size:18px}
 .wrap{display:grid;grid-template-columns:1fr 1fr;gap:14px;padding:14px}
 .card{background:#1b2130;border-radius:10px;padding:14px}
 .card h2{margin:0 0 10px;font-size:15px;color:#ffd54a}
 table{width:100%;border-collapse:collapse;font-size:13px}
 td,th{padding:4px 6px;border-bottom:1px solid #2a3142;text-align:left}
 input,button{font-size:13px;padding:6px;border-radius:6px;border:1px solid #2a3142;background:#0d1017;color:#e8eaed}
 button{background:#2d6cdf;cursor:pointer;border:none}
 .row{display:flex;gap:6px;align-items:center;margin:6px 0;flex-wrap:wrap}
 #feed{font-family:monospace;font-size:13px;max-height:260px;overflow:auto}
 .res{margin-top:6px;font-size:13px;color:#9ad}
 .bar{height:8px;background:#2a3142;border-radius:4px;overflow:hidden;width:120px;display:inline-block;vertical-align:middle}
 .bar>i{display:block;height:100%;background:#3ad07a}
</style></head>
<body>
<h1>🍄 Recognition Inspector</h1>
<div class="wrap">
 <div class="card"><h2>Who Mario knows</h2>
   <b>Faces</b><table id="faces"></table>
   <b>Voices</b><table id="voices"></table></div>
 <div class="card"><h2>Live recognition feed</h2><div id="feed"></div></div>
 <div class="card"><h2>Feed a FACE</h2>
   <div class="row"><input type="file" id="fimg" accept="image/*">
     <input type="text" id="fname" placeholder="name (blank = test)"></div>
   <div class="row"><button onclick="sendFace(false)">Test recognize</button>
     <button onclick="sendFace(true)">Enroll as name</button></div>
   <div class="res" id="fres"></div></div>
 <div class="card"><h2>Feed a VOICE (.wav)</h2>
   <div class="row"><input type="file" id="vwav" accept="audio/wav,.wav">
     <input type="text" id="vname" placeholder="name (blank = test)"></div>
   <div class="row"><button onclick="sendVoice(false)">Test recognize</button>
     <button onclick="sendVoice(true)">Enroll as name</button></div>
   <div class="res" id="vres"></div></div>
</div>
<script>
const J=(u,o)=>fetch(u,o).then(r=>r.json());
function bar(c){return `<span class="bar"><i style="width:${Math.round((c||0)*100)}%"></i></span> ${(c||0).toFixed(2)}`;}
async function roster(){const d=await J('/admin/recognition/roster');
 document.getElementById('faces').innerHTML='<tr><th>name</th><th>visits</th></tr>'+
   (d.faces||[]).map(f=>`<tr><td>${f.name}</td><td>${f.visit_count}</td></tr>`).join('')||'<tr><td>none</td></tr>';
 document.getElementById('voices').innerHTML='<tr><th>name</th><th>id</th></tr>'+
   (d.voices||[]).map(v=>`<tr><td>${v.name}</td><td>${v.id}</td></tr>`).join('')||'<tr><td>none</td></tr>';}
function b64(file){return new Promise(res=>{const r=new FileReader();r.onload=()=>res(r.result.split(',')[1]);r.readAsDataURL(file);});}
async function sendFace(enroll){const f=document.getElementById('fimg').files[0];if(!f)return;
 const name=enroll?document.getElementById('fname').value:'';
 const d=await J('/admin/recognition/face',{method:'POST',headers:{'Content-Type':'application/json'},
   body:JSON.stringify({image_b64:await b64(f),name})});
 document.getElementById('fres').innerHTML=d.enrolled?`✅ enrolled ${d.name}`:
   d.detected===false?'🚫 no face found':d.name?`👤 ${d.name} ${bar(d.confidence)}`:'🆕 new / unknown face';roster();}
async function sendVoice(enroll){const f=document.getElementById('vwav').files[0];if(!f)return;
 const name=enroll?document.getElementById('vname').value:'';
 const d=await J('/admin/recognition/voice',{method:'POST',headers:{'Content-Type':'application/json'},
   body:JSON.stringify({wav_b64:await b64(f),name})});
 document.getElementById('vres').innerHTML=d.enrolled?`✅ enrolled ${d.name}`:
   d.error?('⚠️ '+d.error):`${d.name?('🎤 '+d.name+' '+bar(d.confidence)):'🆕 new speaker'} <i>“${d.transcript||''}”</i>`;roster();}
let lastSeq=0;
async function feed(){const d=await J('/admin/recognition/events?since='+lastSeq);
 const el=document.getElementById('feed');
 (d.events||[]).forEach(e=>{lastSeq=e.seq;const ic=e.kind==='face'?'👤':'🎤';
   el.innerHTML=`<div>${ic} ${e.name||'unknown'} ${e.is_new?'🆕':''} ${bar(e.confidence)} <small>(${e.source})</small></div>`+el.innerHTML;});}
roster();setInterval(roster,3000);setInterval(feed,1500);
</script></body></html>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/Scripts/python.exe -m pytest tests/test_recognition_inspector.py -q` → PASS.

- [ ] **Step 5: Commit**

```bash
git add server/static/recognition.html tests/test_recognition_inspector.py
git commit -m "feat(recognition): inspector page UI (roster, feed, live)" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 5: Live recognition hooks

**Files:**
- Modify: `server/main.py` — `person_detected` handler (~`:6371`, after `face_enrollment.resolve_faces`) and `handle_audio` (the `speaker_info` block, ~`:5560`)
- Test: `tests/test_recognition_inspector.py` (AST)

**Interfaces:**
- Consumes: `recognition_events.push`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_recognition_inspector.py`:

```python
def test_live_paths_push_recognition_events():
    src = _main_src()
    tree = ast.parse(src)
    def fn(name):
        for n in ast.walk(tree):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name:
                return n
    def calls_push(node):
        for c in ast.walk(node):
            if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute) \
               and c.func.attr == "push" and isinstance(c.func.value, ast.Name) \
               and c.func.value.id == "recognition_events":
                return True
        return False
    assert calls_push(fn("handle_event")), "person_detected handler must push a face event"
    # voice path lives in the audio handler function:
    audio_fn = fn("_process_audio") or fn("handle_audio")
    assert audio_fn and calls_push(audio_fn), "audio path must push a voice event"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/Scripts/python.exe -m pytest tests/test_recognition_inspector.py::test_live_paths_push_recognition_events -q`
Expected: FAIL (no `recognition_events.push` in those functions yet).

- [ ] **Step 3a: Hook the face path**

In `server/main.py`, in the `person_detected` handler immediately AFTER the
`face_result = face_enrollment.resolve_faces(...)` call (~`:6371`), add:

```python
        try:
            for _d in face_result["detected"]:
                recognition_events.push("face", _d["name"], _d.get("confidence") or 0.0,
                                        _d.get("person_id") is None, "live")
            for _ in range(face_result.get("new_face_count", 0)):
                recognition_events.push("face", None, 0.0, True, "live")
        except Exception:
            pass
```

- [ ] **Step 3b: Hook the voice path**

In `server/main.py`, in the audio handler (`_process_audio`), right after the
`speaker_info = ...`/`identify_speaker(...)` result is available and before the
`_generate_and_send_response(..., source="audio")` call, add:

```python
        try:
            if speaker_info:
                recognition_events.push("voice", speaker_info.get("name"),
                                        speaker_info.get("confidence", 0.0),
                                        speaker_info.get("is_new", True), "live")
        except Exception:
            pass
```

(If the local variable is named differently than `speaker_info`, use the dict
returned by `identify_speaker` in that scope.)

- [ ] **Step 4: Run test + compile + full file**

Run: `venv/Scripts/python.exe -m pytest tests/test_recognition_inspector.py -q` → PASS (all).
Run: `venv/Scripts/python.exe -m py_compile server/main.py` → success.
Run: `venv/Scripts/python.exe -m pytest tests/ -q -p no:cacheprovider --ignore=tests/convert_and_test.py --ignore=tests/test_mcp_chatgpt_browser.py` → no NEW failures vs the known baseline (pre-existing: `test_pygame_client_controls` IndexErrors; e2e/latency need a running server; qdrant flaky).

- [ ] **Step 5: Commit**

```bash
git add server/main.py tests/test_recognition_inspector.py
git commit -m "feat(recognition): push live face/voice events to the inspector feed" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 6: Live verification (MANDATORY — the real proof)

**Files:** none (manual, per `.claude/rules/testing.md`).

- [ ] **Step 1:** Ensure server (`start_server.bat`) + client are running; open `http://localhost:8765/recognition`.
- [ ] **Step 2 (face):** Upload a clear face photo with name "TestAlice" → **Enroll**. Roster shows TestAlice. Upload the same photo → **Test** → result shows `👤 TestAlice` with a high confidence bar.
- [ ] **Step 3 (voice):** Upload a WAV of someone saying a sentence with name "TestBob" → **Enroll**. Roster shows TestBob. Upload another clip of the same voice → **Test** → shows `🎤 TestBob` + the transcript.
- [ ] **Step 4 (live):** Stand in front of the real webcam / speak into the mic. Within a couple seconds the **Live feed** panel shows `👤 …` / `🎤 …` events. Confirm Mario's spoken replies still play to completion (client log `_play_wav: playing` → `done`) and stay in-character.
- [ ] **Step 5:** Negative check — upload a photo of a *different* person under no name → **Test** → returns `🆕 new / unknown` (not a false match).

---

## Self-Review

- **Spec coverage:** roster (Task 2), enroll+test face/voice (Task 3), page 3 panels (Task 4), live event feed + hooks (Tasks 1/5), event buffer (Task 1), admin gate (Task 2/3 `_recognition_admin_ok`), error handling (try/except in every endpoint), testing (synthetic + AST units + Task 6 live). All spec sections mapped. ✓
- **Placeholder scan:** every code step has full code; commands have expected output. The two live-hook insertions name the anchor (`face_enrollment.resolve_faces` / `identify_speaker`) and give exact code. ✓
- **Type consistency:** `recognition_events.push(kind,name,confidence,is_new,source)` / `recent(since)` / `person_id_for_name(name)` used identically across Tasks 1–5; endpoint shapes (`{detected,name,confidence,is_new}` / `{enrolled,name}` / `{events:[...]}`) match what `recognition.html` reads in Task 4. ✓
