# Recognition Inspector — Design

- **Date:** 2026-06-26
- **Branch:** master
- **Status:** Design approved; implementation plan pending
- **Scope:** server (endpoints + small event buffer) + one static page + tests

## Problem

There is no way to *prove* Mario's face/voice recognition works, or to see who he
already knows. The user wants to feed a face + a voice and watch recognition
happen, plus inspect the enrolled roster.

## Goal

A single admin page (`/recognition`) backed by a few small endpoints that lets you:

1. See the **roster** — enrolled faces + voices (names, sample/id).
2. **Enroll** a face (photo) and a voice (WAV) under a name.
3. **Test** recognition — feed a face/voice → match name + confidence, or "new".
4. Watch a **live feed** of real recognition events from the running webcam/mic.

The proof loop: enroll "Alice" from a photo + voice → feed her again → see
`Alice (0.83)`; and talk into the real mic → the live event lands on the page.

## Non-goals

- Not changing recognition algorithms/thresholds (separate concern).
- Not a guest-facing UI — this is an admin/diagnostic tool.
- No new persistence beyond what `face_memory`/`speaker_id` already store.
- **No in-page webcam/mic capture** (avoids the getUserMedia/HTTPS gotcha). The
  "feed" panel is file-upload only; the live panel surfaces the *existing*
  client's webcam/mic recognition.

## Existing building blocks (reuse — do not reinvent)

- `face_memory.get_all_faces()`, `find_match(encoding, tolerance=0.6)` →
  `{name, confidence, ...}`, `store_face(person_id, name, encoding)` (128-dim,
  euclidean @ 0.6).
- `speaker_id.list_speakers()` → `[{id, name}]`,
  `identify_speaker(wav_bytes, sample_rate)` → `{name, speaker_id, confidence, is_new}`,
  `register_speaker(name, wav_bytes)` → `id` (cosine @ 0.65).
- `face_recognition` (present in venv) to encode an uploaded photo
  (`load_image_file` + `face_encodings`).
- STT (`stt`) for a transcript on the voice test.
- Static-page pattern: `/friend`, `/control` open an HTML file from
  `server/static/` and return `HTMLResponse`.
- Live recognition already runs: the `person_detected` handler (face, via the
  `face_enrollment` module) and `handle_audio` → `identify_speaker` (voice).

## Architecture

Endpoints + one HTML page + a small in-memory ring buffer for live events. All
recognition reuses the functions above; the new code is thin glue + UI.

### 1. Recognition event buffer (`server/main.py`)

- `_recognition_events = collections.deque(maxlen=100)` and a helper
  `_push_recognition_event(kind, name, confidence, is_new, source)` that appends
  `{seq, ts, kind: "face"|"voice", name, confidence, is_new, source: "live"|"upload"}`
  (`seq` = monotonically increasing int so the page can poll "since last seq").
- Two hook calls into existing paths:
  - **Face (live):** in the `person_detected` handler (`main.py:6356`), after the
    `face_enrollment` match/enroll resolves, push an event with the matched name +
    confidence (or the enrolled name, `is_new=True`).
  - **Voice (live):** in `handle_audio` after `identify_speaker` returns (the
    existing `speaker_info` block, ~`main.py:5560`), push an event.

### 2. Endpoints (`server/main.py`)

- `GET /recognition` → serve `server/static/recognition.html`.
- `GET /admin/recognition/roster` →
  `{faces: face_memory.get_all_faces(), voices: speaker_id.list_speakers()}`.
- `POST /admin/recognition/face` (multipart: `image` file, optional `name`):
  - decode bytes → `face_recognition.face_encodings(load_image_file(bytes))`.
  - no face → `{detected: false, reason: "no_face"}`.
  - `name` given → resolve/create a person row for that name (via `memory`,
    same mechanism the live path uses) → `face_memory.store_face(pid, name, enc)`
    → push `upload` event → `{enrolled: true, name}`.
  - else → `face_memory.find_match(enc)` → push `upload` event →
    `{detected: true, name, confidence, is_new}`.
- `POST /admin/recognition/voice` (multipart: `wav` file, optional `name`):
  - `name` given → `speaker_id.register_speaker(name, wav_bytes)` → push event →
    `{enrolled: true, name}`.
  - else → `speaker_id.identify_speaker(wav_bytes)` (+ STT transcript) → push
    event → `{transcript, name, confidence, is_new}`.
- `GET /admin/recognition/events?since=<seq>` → events with `seq > since`.
- **Admin gate:** if `GAME_CONFIG["admin_api_key"]` is set, the four `/admin/...`
  endpoints require it (header/param), matching the other admin endpoints.

### 3. Page (`server/static/recognition.html`, new)

Vanilla HTML/CSS/JS in the `/friend`/`/control` style. Three panels:

1. **Who Mario knows** — table of faces + voices; polls `/roster` every ~3s.
2. **Feed a face / voice** — file input for an image + a name; file input for a
   WAV + a name; **Test** and **Enroll** buttons per type; shows the JSON result
   rendered as a friendly line (match name + confidence bar, or "new / no face").
3. **Live feed** — scrolling log; polls `/events?since=<lastSeq>` every ~1.5s and
   appends `👤 Alice (0.82)` / `🎤 Bob (0.71)` / `🆕 new face enrolled`.

### Data flow

- **Upload face** → `/face` → encode + (enroll | match) → inline result + event.
- **Upload/record voice** → `/voice` → (enroll | identify + STT) → inline + event.
- **Live** → real webcam (client) → `person_detected` → face match →
  `_push_recognition_event` → page `/events` poll shows it. Real mic →
  STT + `identify_speaker` → event → page shows it.

### Error handling

- No face detected → `{detected:false, reason:"no_face"}` (friendly UI line).
- `face_recognition` / `resemblyzer` missing → endpoint returns
  `{error:"recognition_unavailable"}`; page shows a banner.
- Short/silent audio → `identify_speaker` returns low-conf/`is_new`; surfaced as-is.
- Every recognition call wrapped in try/except → JSON error, never a 500 that
  breaks the page. Upload size cap (e.g. 8 MB image, 10 MB wav).

## Testing

Real face/voice encoding needs heavy deps (a real photo for `face_recognition`,
real speech for `resemblyzer`), so units use synthetic vectors + structure
checks, and the real encode/identify path is covered by live-verify.

- **Unit (`tests/test_recognition_inspector.py`):**
  - Event buffer: `_push_recognition_event` appends correctly and
    `/events?since=<seq>` filtering returns only newer events (pure logic — test
    the deque + filter helper directly, no server import).
  - `face_memory` round-trip with **synthetic** 128-dim encodings (like
    `/admin/lookup_face`'s `seed` path): `store_face` then `find_match` on the
    same vector returns the name at high confidence; a random vector returns no
    match / `is_new`. Tests the match/enroll logic without a photo.
  - `speaker_id.list_speakers()` shape.
  - AST-assert (per `tests/test_edge_cases.py:1347`, `server.main` isn't
    importable): `main.py` defines the 4 routes (`/recognition`,
    `/admin/recognition/roster|face|voice|events`), the `_recognition_events`
    buffer, `_push_recognition_event`, and that the `person_detected` handler +
    `handle_audio` call `_push_recognition_event`.
- **Live (per `.claude/rules/testing.md`, the real proof):** open `/recognition`,
  enroll "TestAlice" from a real photo + a real voice clip → re-feed → page shows
  `TestAlice` + confidence; speak into the real mic → a live event appears;
  confirm Mario's spoken replies still play (`_play_wav` playing→done),
  in-character.

## Files

- `server/main.py` — endpoints, event buffer, 2 hook calls.
- `server/static/recognition.html` — new page.
- `tests/test_recognition_inspector.py` — new (synthetic-vector + AST tests; no
  checked-in media fixtures — the real photo/voice are supplied at live-verify).

## Security

- `/admin/recognition/*` behind `admin_api_key` when configured. Uploaded media is
  only decoded (never executed) and size-capped. Reachable over the tunnel like
  `/friend` — same "exposes the local server" caveat; the page is for the operator.
