# Camera Over Tunnel — Design Spec

**Date:** 2026-07-15
**Status:** Approved (brainstorm), pending implementation plan
**Feature:** Let a remote guest (connected over the ngrok tunnel via `friend.html`) opt in to their
device camera, FaceTime-style, so the character can *see* them: recognize/remember their face and
comment on what he sees.

---

## 1. Goal

A remote guest on the party link taps a camera button. Their browser camera turns on (opt-in, with a
self-view). From then on the character:

1. **Recognizes and remembers** their face — greets them by name, ties their chat to a face, and
   enrolls new faces into the **same persistent gallery** as in-person guests.
2. **Comments on what he sees** — reacts to appearance / expression / surroundings via a multimodal
   LLM ("Hey Jacob, love the party hat!").

This reuses the existing remote-guest plumbing (`friend.html` + `/friend/*` endpoints) and the
existing face-recognition stack (`server/face_memory.py`, `server/recognition_events.py`). It is
mostly *gluing proven parts together*, not new subsystems.

### Decisions locked during brainstorming

| Question | Answer |
|---|---|
| Depth of "seeing" | **Both** — face recognition/memory **and** live vision commentary. |
| Cadence / vibe | **Balanced glance** — cheap recognition every ~2.5s; vision commentary only at key moments. |
| Face retention | **Remember across parties** — remote faces join the same persistent gallery as in-person guests. |

### Two small forks defaulted (owner did not object)

- Frames travel by **HTTP POST @ ~2.5s** (not a WebSocket upstream / not WebRTC).
- Vision commentary runs on the **quality (multimodal) model only**.

---

## 2. Non-goals

- **Not** real-time streamed video to the server (no WebRTC, no per-frame vision). The server only
  needs periodic still frames.
- **Not** reciprocal video setup — the guest *already* sees the character: `/mirror` streams the
  display down as JPEG frames (binary tag `0x01`). This feature is one-directional (guest → server).
- **Not** a rework of the recognition ML (thresholds, multi-encoding gallery, detector swap). Those
  are tracked separately in `AUDIT_VOICE_FACE_RECOGNITION.md` (F5c, F6). We consume the stack as-is.
- **Not** on-screen "eye contact" / avatar head-turn on the local display. Out of scope.

---

## 3. Current-state grounding (what we build on)

### Remote guest client — `server/static/friend.html`
- Connects to `ws://…/mirror`; receives binary frames (`0x01` JPEG video) and audio (`0x02` WAV),
  plus JSON control events (`presence`, `turn`, `transcript`).
- Sends **text** via `POST /friend/say`, **voice** via `POST /friend/say_audio` (base64 blob from
  `MediaRecorder`).
- Already uses `getUserMedia({audio:true})` for hold-to-talk — proves secure-context capture works
  over the tunnel (HTTPS) and localhost.
- Identity: temporary `mirror_name` + stable `mirror_client_id` (localStorage); `mirror_pin`.
- `CONTROL_MODE` is injected by the server; chat UI only active in `"remote"` mode.

### Remote input endpoints — `server/main.py`
- `POST /friend/say` (`main.py:2398`) and `POST /friend/say_audio` (`main.py:2431`):
  - Auth via `mirror_relay.authorize_friend_input(token, pin, _MIRROR_CFG, control_mode)`.
  - One-talker turn gate via `mirror_relay.acquire_or_refresh_turn(client_id, name, now)`.
  - Heavy work (STT) offloaded with `loop.run_in_executor(None, …)` to keep the mirror smooth.
  - Drive path: `await _dispatch_user_text(text, guest_name=name)`.

### Server-side face encode already exists — `POST /admin/recognition/face` (`main.py:2814`)
```python
import face_recognition
img = face_recognition.load_image_file(io.BytesIO(img_bytes))
encs = face_recognition.face_encodings(img)
enc = np.array(encs[0], dtype=np.float64)
# enroll:
pid = recognition_events.person_id_for_name(name)
_face_memory.store_face(pid, name, enc)
recognition_events.push("face", name, 1.0, True, "upload")
# or recognize:
m = _face_memory.find_match(enc)   # -> {"person_id","name","confidence","visit_count"} or None
```
This is the exact server-side encode path we reuse — but it is **admin-gated**; the new endpoint
gets **friend auth** instead.

### Recognition stack signatures (from `AUDIT_VOICE_FACE_RECOGNITION.md` §9)
```python
# server/face_memory.py
store_face(person_id: int, name: str, encoding: np.ndarray)
find_match(encoding, tolerance=None) -> Optional[dict]   # {"person_id","name","confidence","visit_count"}
learn_guest(name: str, encoding: np.ndarray)             # name-keyed enroll (assigns next person_id, writes both stores)
get_all_faces() -> list
# server/recognition_events.py
person_id_for_name(name) -> int
push(kind, name, confidence, is_new, source)
recent(since) -> list
```

### LLM / Ollama call
- `server/llm_router.py` **only routes** (picks a model name); it does not call Ollama.
- The actual call is in `server/llm.py` (`llm.MODEL_NAME`, `llm.check_ollama()`); `server/main.py`
  hits `http://localhost:11434/api/chat` via `httpx` (`main.py:626`).
- Ollama `/api/chat` accepts a per-message `images: [<base64>]` field for multimodal models
  (gemma3). This is where vision commentary hooks in.

### Dependency reality
- `server/requirements.txt` has **no** `face_recognition` / `dlib` / `opencv`. The
  `/admin/recognition/face` endpoint imports `face_recognition` **lazily** inside a `try`, so it only
  works where the package happens to be installed.
- `client/requirements.txt` lists `face_recognition` **commented-out / optional** (needs cmake +
  dlib + VC++ Build Tools).
- ⇒ Server-side encoding for remote camera has a real dependency gap, especially on the **dev box**.
  Must be handled by graceful degradation + a documented-optional server requirement.

---

## 4. Architecture

Transport chosen: **A — HTTP snapshot POST** (see §1 forks). Alternatives B (WS upstream on
`/mirror`) and C (WebRTC) were rejected: B fights the broadcast-down + open-viewing design of
`/mirror` and needs bespoke auth; C is heavy infra for zero benefit at a 2.5s cadence.

```
┌─────────────────────────── friend.html (guest browser) ───────────────────────────┐
│  [📷 Camera] opt-in  →  getUserMedia({video:true})  →  <video> self-view + 🔴 dot   │
│                                                                                     │
│   every ~2.5s (tab visible):  canvas.drawImage → JPEG(≈480px,q0.6) → base64         │
│        └── POST /friend/see {token,pin,name,id, image_b64, reason}                   │
│   stop:  release tracks  →  POST /friend/see {reason:"camera_off"}                   │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                        │  HTTPS (tunnel)
                                        ▼
┌──────────────────────────────── server/main.py ────────────────────────────────────┐
│  POST /friend/see                                                                   │
│   1. authorize_friend_input(token,pin,…)         (same as /friend/say_audio)         │
│   2. per-client rate-limit + size guard                                             │
│   3. reason=="camera_off" → drop cached frame, return                               │
│   4. run_in_executor: face_recognition.face_encodings(jpeg)   (CPU, off-loop)        │
│   5. cache latest frame per client_id in RAM (short TTL)                             │
│   6. RECOGNITION (every tick, cheap):                                               │
│        m = _face_memory.find_match(enc)                                             │
│         ├─ match  → recognition_events.push("face", m.name, …); greet-by-name once   │
│         └─ none   → _face_memory.learn_guest(name, enc)  (name always known!)        │
│                     recognition_events.push("face", name, 1.0, True, "remote_cam")   │
│   7. VISION COMMENTARY (throttled, key moments only):                               │
│        if reason=="camera_on"  OR  on-demand intent  OR  lull-window-open:           │
│           comment = await _vision_comment(cached_frame, guest_name)                 │
│           → TTS → mirror_relay.broadcast (ambient; does NOT claim the turn gate)      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Component detail

### 5.1 Client — `server/static/friend.html`

New UI (remote mode only, alongside the mic button):
- A `📷` toggle button, default **off**. First enable shows a one-time consent line:
  *"Mario can see you and may remember your face. You can turn the camera off anytime."*
- On enable:
  - `navigator.mediaDevices.getUserMedia({video: true, audio: false})`.
  - Show a small self-view (`<video muted playsinline>`), plus a red "camera on" indicator.
  - Start a `setInterval` (~2.5s) capture loop. Each tick: draw the current video frame to an
    offscreen `<canvas>` downscaled to ~480px on the long edge, `canvas.toDataURL("image/jpeg", 0.6)`,
    strip the data-URL prefix, `POST /friend/see`.
  - First post after enable carries `reason:"camera_on"`; subsequent posts `reason:"tick"`.
  - Pause the loop when `document.hidden` (visibilitychange); resume on focus.
- On disable: `getTracks().forEach(t=>t.stop())`, hide self-view, `POST /friend/see {reason:"camera_off"}`.
- Failure handling mirrors the mic: `getUserMedia` reject → status "📷 allow camera access"; no
  `getUserMedia` / insecure context → "📷 not supported here".

Frames are **not** rendered anywhere but the guest's own self-view; they are never echoed to other
viewers.

### 5.2 Server — new `POST /friend/see` (`server/main.py`)

Body: `{ token, pin, name, id, image_b64, reason }` where `reason ∈ {"camera_on","tick","camera_off"}`.

1. **Auth:** `authorize_friend_input(token, pin, _MIRROR_CFG, mirror_relay.get_control_mode())` —
   identical to `/friend/say_audio`. Reject with `{"status":"error","reason":…}` on failure. Require
   non-empty `id` (`client_id`).
2. **Rate limit + size guard:** enforce a per-`client_id` minimum interval (default ~2.0s, so a
   2.5s client is safe but a hostile client can't flood) and a max base64 size (reuse the existing
   `8_000_000` guard from `/admin/recognition/face`).
3. **`camera_off`:** clear this client's cached frame + any per-client camera state, return
   `{"status":"ok"}`.
4. **Decode + encode off-loop:** `await loop.run_in_executor(None, _encode_face, image_b64)` where
   `_encode_face` does the `face_recognition.load_image_file` + `face_encodings` from
   `/admin/recognition/face`. If `face_recognition` import fails → return
   `{"status":"ok","recognition":"unavailable"}` (camera keeps working client-side, self-view only).
5. **Cache latest frame** for this `client_id` in an in-memory dict `{client_id: (jpeg_bytes, ts)}`
   with a short TTL (e.g. 30s). RAM only — never written to disk.
6. **Recognition (every tick):**
   - `enc = encs[0]` (largest/first face). No face → return `{"status":"ok","face":false}` (silent;
     see §7 for the throttled nudge).
   - `m = _face_memory.find_match(enc)`.
     - **Match:** `recognition_events.push("face", m["name"], m["confidence"], False, "remote_cam")`.
       If this is the first recognition this session for this client, fire a greet-by-name (once,
       via the normal response/broadcast path).
     - **No match:** the guest's `name` is always known (join form), so enroll immediately:
       `_face_memory.learn_guest(name, enc)` +
       `recognition_events.push("face", name, 1.0, True, "remote_cam")`. Optionally
       `guest_profiles.identify_by_face(name, str(person_id))`.
   - This deliberately reuses the same functions as the (fixed) local `person_detected` handler, so
     remote and in-person faces share one gallery and one event stream.
7. **Vision commentary (throttled):** call `_vision_comment` only when a trigger is open (§5.4).

Return shape (superset, all optional): `{"status":"ok","face":bool,"recognized":name|null,
"is_new":bool,"commented":bool}`.

### 5.3 Recognition wiring — reuse, do not duplicate

No new storage. All writes go through `face_memory` + `recognition_events`, exactly like the local
camera path. Consequence of the retention decision: remote faces persist across parties and
cross-match with in-person sightings.

**Key simplification vs. the audit:** the audit's two 🔴 critical bugs (F1 wrong `store_face` args,
F2 stash-then-name path missing) exist because the *local* camera sees a face **before** the guest
gives a name. The remote path never has that problem — a remote guest has already entered a `name`
before any frame is sent — so we always take the clean `learn_guest(name, enc)` branch. No pending
/ stash state needed.

### 5.4 Vision commentary — `_vision_comment(frame_jpeg, guest_name) -> str`

- Builds a character-styled prompt ("You are <character>. You can see the guest on camera. In one or
  two short sentences, react warmly to what you see. TTS rules apply.") + the frame as
  `images:[base64]` on a `/api/chat` call to the **quality model** (`llm.MODEL_NAME` / the router's
  quality choice). Runs through the existing Ollama httpx path.
- Output goes through `safety_filter` and the **character isolation** guard before TTS — non-Mario
  characters must never leak Mario references in the vision comment (see [[dual-module-instance-gotcha]]:
  set_character mutations don't cross the bare vs `server.*` module copies — the vision helper must
  read the same `_CHARACTER_NAME` the rest of the response path uses).
- Result is **TTS'd and broadcast as an ambient line** — it does **not** call
  `acquire_or_refresh_turn`, so it never steals the one-talker turn from a text/voice chatter.
- **Triggers (balanced glance):**
  1. `reason == "camera_on"` → one greeting comment.
  2. **On-demand:** the guest's normal text/voice turn matches a light "what do you see / how do I
     look / can you see me" intent **and** a fresh cached frame exists → comment instead of / in
     addition to the normal reply. (Intent check lives in the text path, reading the frame cache.)
  3. **Lull:** a spontaneous comment is allowed only if `now - last_vision_comment_ts >
     VISION_MIN_GAP` (config, default ~45s) **and** no active chat turn is in progress. At most one
     per gap window.
- **Throttle state** is per-client (or global-per-session, simplest): `last_vision_comment_ts`.

### 5.5 Multimodal availability + degradation

- If the active quality model is **not** multimodal (e.g. dev box `llama3:8b`) or
  `camera_vision_enabled` is false → **skip commentary, keep recognition**. Detected via a config
  flag rather than a runtime probe on every call.
- If `face_recognition` is unavailable on the server → recognition returns `"unavailable"`; the
  client still shows the self-view (camera is not "broken" from the guest's view).
- Vision call has a timeout (reuse existing LLM timeout budget); on timeout/failure → no comment,
  logged, recognition unaffected.

---

## 6. Config

Add to `config_live.json` defaults (hot-reloadable personality/tuning) and **document in
`config.example.json`** (never edit the gitignored `config.json` — see [[config-json-untracked-secret]]):

| Key | Default | Meaning |
|---|---|---|
| `camera_enabled` | `true` | Master switch for the remote camera feature (server advertises it to `friend.html`). |
| `camera_vision_enabled` | `true` | Whether vision commentary runs (set false on text-only-model boxes). |
| `camera_frame_min_interval` | `2.0` | Server-side per-client min seconds between accepted frames. |
| `camera_vision_min_gap` | `45` | Min seconds between spontaneous (lull) vision comments. |
| `camera_frame_ttl` | `30` | Seconds a cached frame stays usable for on-demand vision. |

Client capture cadence (~2.5s) is a `friend.html` constant, kept just above
`camera_frame_min_interval`.

---

## 7. Error handling & edge cases

- **No face in frame:** silent no-op on ticks. After a `camera_on` with N consecutive no-face ticks,
  one throttled nudge ("I can't quite see you — move into the light?"), then silence.
- **Multiple faces:** take the first/largest encoding; do not try to enroll bystanders under the
  guest's name beyond the primary face.
- **Multiple remote guests with cameras on:** each `client_id` is independent — its frames enroll/
  match under *its own* `name`, its own throttle state. Vision comments are ambient and rate-limited
  globally enough not to storm.
- **Rapid enable/disable:** `camera_off` clears cache; a late in-flight `tick` for a stopped camera
  is harmless (just another recognition, or a dropped cache write).
- **Hostile client:** rate-limit + size guard + friend auth (token+pin). No raw frame is persisted or
  re-broadcast, limiting abuse blast radius.
- **Tab backgrounded:** client pauses capture; server frame cache TTL-expires; on-demand vision finds
  no fresh frame → falls back to a normal (non-vision) reply.

---

## 8. Privacy / consent

- Explicit opt-in button, default off; one-time consent line on first enable.
- Self-view always visible while on, plus a red indicator; camera-off releases tracks immediately.
- **Frames are RAM-only** (short TTL), never written to disk or re-broadcast. Only 128-dim face
  **embeddings** persist — consistent with the app's existing privacy-first design (embeddings, never
  raw media).
- Retention matches the owner's decision (remember across parties). A future bulk face-wipe control
  is out of scope here but noted in Open Questions.

---

## 9. Dependencies

- Add `face_recognition` (+ its dlib requirement) to `server/requirements.txt` as a **documented-
  optional** block (mirroring the client's commented install notes), because server-side encoding now
  has a *live* (non-admin) consumer. Feature degrades gracefully if absent.
- Confirm the party box's server environment can `import face_recognition` and that
  gemma3:27b (or the configured quality model) is pulled with vision support and answers
  `/api/chat` with an `images:[…]` payload.

---

## 10. Testing

Unit / integration (pytest, following existing `tests/` patterns):
- `/friend/see` rejects bad token / bad pin / missing `client_id`.
- Rate-limit rejects a too-fast second frame; size guard rejects oversized base64.
- `camera_off` clears the cached frame.
- **Enroll path:** unknown encoding + known `name` → `learn_guest(name, enc)` called +
  `recognition_events.push(... "remote_cam")`.
- **Match path:** a previously enrolled encoding → `find_match` returns the name; no re-enroll;
  greet-by-name fires once per session.
- **No-face** frame → no enroll, no crash, throttled-nudge logic.
- **Degradation:** `face_recognition` import failure → `recognition:"unavailable"`, 200 OK;
  `camera_vision_enabled=false` → recognition runs, `_vision_comment` never called.
- **Character isolation:** vision comment for a non-Mario character contains zero Mario references
  (mock the multimodal call).
- Vision throttle: two ticks inside `camera_vision_min_gap` yield at most one spontaneous comment.

Live / manual (per `.claude/rules/testing.md` — **mandatory audio verification**):
- Open `friend.html` over the real tunnel (HTTPS), enable camera, confirm `getUserMedia` self-view.
- On `camera_on`, confirm a vision greeting: client log shows `mario says:` line, `received audio`,
  `_play_wav: playing` **and** `_play_wav: done`; spoken text matches the bubble.
- For a non-Mario character: confirm **zero** Mario references in both text and audio.
- Re-connect later → confirm greet-by-name (recognition persisted).

---

## 11. File-by-file change list

| File | Change |
|---|---|
| `server/static/friend.html` | Camera opt-in button, self-view, capture loop, `POST /friend/see`, consent line, visibility pause. |
| `server/main.py` | New `POST /friend/see` handler; `_encode_face` helper (extracted/shared with `/admin/recognition/face`); per-client frame cache + throttle state; `_vision_comment` (Ollama `/api/chat` `images:[…]`); on-demand vision intent hook in the text drive path. |
| `server/mirror_relay.py` (or wherever `authorize_friend_input` / broadcast live) | Reuse as-is; possibly a small helper to broadcast an ambient (non-turn) line if one doesn't already exist. |
| `server/requirements.txt` | Documented-optional `face_recognition` / dlib block. |
| `config.example.json` | New `camera_*` keys documented. |
| `config_live.json` | New `camera_*` defaults. |
| `tests/test_friend_camera.py` (new) | Unit/integration per §10. |

---

## 12. Open questions (non-blocking)

- **OQ1 — bulk face wipe.** Retention is "across parties"; there is still no bulk face-wipe control
  (audit OQ3). Not required for this feature, but worth a follow-up given camera-over-internet
  raises the stakes.
- **OQ2 — on-demand intent location.** The "what do you see?" intent check could live in
  `command_handlers.py` (keyword) or as a light check in the `/friend/say*` path. Prefer the latter
  so it only triggers when a fresh frame exists; finalize during planning.
- **OQ3 — quality-model vision tag.** Exact Ollama model tag with vision on the party box
  (`gemma3:27b` vs a `-vision` variant) to be confirmed at build time (§9).
