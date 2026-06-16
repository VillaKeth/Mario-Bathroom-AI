# Voice & Face Recognition — Code Audit + Fix Plan

**Audience:** a second AI / engineer who has NOT seen this codebase.
**Scope:** static code audit only (no runtime testing). Covers how well the system
recognizes *returning guests* by **voice** and by **face**.
**Verdict up front:** the underlying ML is standard and fine. The *integration* is
broken — face recognition enrolls nobody at a live party (recognizes zero returning
guests), and voice recognition works but is tuned dangerously loose and half its
storage layer is dead code.

---

## 1. System context (what this app is)

"Mario AI Party Bot." A laptop/Pi runs an AI character (Mario, or a swappable
character) in a house-party bathroom for 8+ hours. It greets guests, plays games,
and is supposed to **remember returning guests** — greeting them by name on re-entry.
Two independent recognition subsystems feed that memory:

- **Voice ID** — identify a returning guest from a microphone clip.
- **Face ID** — identify a returning guest from a webcam frame.

Both are *privacy-first*: only numerical embedding vectors are stored, never raw
audio or images.

Deployment target is hostile to recognition: loud music, multiple simultaneous
speakers, the bot's own TTS bleeding into the mic, a doorway camera catching faces
at bad angles / low light / motion blur.

---

## 2. Architecture & file map

### Voice
| File | Role |
|------|------|
| `server/speaker_id.py` | Voice embeddings (resemblyzer, 256-dim) + cosine match. SQLite (`server/data/voices.db`) + Qdrant (`server/data/qdrant_voices/`) dual-store. |
| `client/audio_capture.py` | Mic capture. 16kHz, mono, int16 PCM. |
| `server/main.py` | Live wiring: buffers audio, runs `identify_speaker` (`:4813`), handles `register_speaker` event (`:5519`), EMA refine (`:4927`). |
| `server/command_handlers.py` | Parses "my name is X" → `register_speaker` (`:596`). |

### Face
| File | Role |
|------|------|
| `client/person_detector.py` | YOLOv8n person detection → dlib `face_recognition` HOG face detect → 128-dim encoding. |
| `client/presence.py` | Owns the camera, feeds frames to `PersonDetector`, fires `on_person_detected`. |
| `client/main.py` | `_on_person_detected` (`:531`) → sends `person_detected` WS event with 128-dim encodings. |
| `server/face_memory.py` | `FaceMemory` class: 128-dim encoding store, Euclidean match. SQLite (`server/data/faces.db`-ish via `_face_db_path`) + Qdrant (`server/data/qdrant_faces/`). |
| `server/main.py` | Live wiring: `person_detected` handler (`:5583`), admin endpoints (`:2188`, `:2218`, `:2231`). |
| `server/guest_profiles.py` | In-memory guest profile registry keyed by name; `identify_by_face` / `identify_by_voice`. |

### Key dependency facts (verified from code)
- **resemblyzer** `VoiceEncoder` → **256-dim** d-vectors (GE2E-style), CPU. Optional import; if missing, voice ID silently disables (`speaker_id.py:20-30`).
- **dlib `face_recognition`** → **128-dim** encodings, calibrated for **Euclidean** distance at **0.6** threshold. Optional import (`person_detector.py:32-39`).
- **YOLOv8n** (`ultralytics`) person detection, COCO class 0, conf 0.5, runs every 3rd frame (`person_detector.py:63-66`).
- Client mic: **16kHz / mono / int16** (`audio_capture.py:12-15`) — matches `identify_speaker` default `sample_rate=16000`. ✅ No sample-rate mismatch.

---

## 3. How the pipelines are SUPPOSED to work

### Voice
1. Client streams 16kHz PCM. Server buffers to ~3s chunks (`main.py:3301`, `CHUNK_SIZE=96000` bytes = 3.0s).
2. `_process_audio` runs STT + `identify_speaker` in parallel on the same chunk (`main.py:4811-4813`).
3. `identify_speaker` (`speaker_id.py:264`): embed → look up Qdrant first → SQLite cosine fallback → return `{name, speaker_id, confidence, is_new}`.
4. Enrollment: guest says "my name is X" → `command_handlers.py:596` → `speaker_id.register_speaker(name, last_audio_chunk)`.
5. Refinement: on each subsequent match, `update_speaker` EMA-blends the new clip into the stored print (`main.py:4927`).

### Face
1. Camera frame → YOLO person box → crop → HOG face detect → 128-dim encoding (`person_detector.py:88-149`).
2. Client sends `person_detected` event with encodings (`client/main.py:531`).
3. Server handler (`main.py:5583`): for each face, `find_match`; if known → greet by name; if unknown **but a speaker is currently identified** → link this face to that speaker's name; else stash as a pending unknown face.
4. Enrollment is *implicit*: faces get names by being linked to a voice-identified guest, or via the `/admin/learn_face` endpoint.

---

## 4. Findings

Severity: 🔴 critical (feature non-functional) · 🟠 major (design broken / silent degradation) · 🟡 minor (correctness wart, low impact).

| # | Sev | Location | One-line |
|---|-----|----------|----------|
| F1 | 🔴 | `server/main.py:5616` | Live face-enroll calls `store_face()` with wrong arguments → `TypeError` every time → no face ever stored. |
| F2 | 🔴 | `server/main.py:5622` + `:424` | `_last_face_encoding` is written but **never read** → the "name a stashed face later" enroll path does not exist. |
| F3 | 🟠 | `server/speaker_id.py` (`register_speaker:346`, `learn_voice:251`) | Voice enrollment writes **SQLite only**; Qdrant voice store is never called → "Qdrant-first" lookup always misses → dead storage layer. |
| F4 | 🟡 | `server/main.py:5607` | `match.get("id", "")` — `find_match` returns `person_id`, not `id` → face profile linking key always `""`. |
| F5 | 🟠 | `server/speaker_id.py:47` | Cosine threshold `0.65` with ~0.10 margin over impostors + single-utterance enrollment → unreliable under party noise. |
| F6 | 🟠 | `client/person_detector.py:139` | HOG face detector + `YOLO_FRAME_SKIP=3` + single encoding per identity → poor capture/recognition at doorway angles/lighting. |
| F7 | 🟡 | `server/face_memory.py:222` | `lookup_face_qdrant` uses COSINE@0.4 on Euclidean-native dlib vectors (wrong metric). Bypassed by `find_match`, but left as a foot-gun. |
| F8 | 🟡 | `server/main.py:4927` (`update_speaker`) | EMA refinement updates SQLite only; never touches the store the design calls "primary." Harmless given F3, but confirms storage confusion. |

---

## 5. Detailed findings + fixes

### F1 🔴 — Live face enrollment crashes every call (wrong `store_face` signature)

**Location:** `server/main.py:5616`, inside the `person_detected` handler.

**Code today:**
```python
else:
    # Unknown face
    speaker = state_current.get("speaker_name")
    if speaker:
        _face_memory.store_face(speaker, enc_array)          # <-- BUG
        guest_profiles.identify_by_face(speaker, "auto_linked")
        detected_names.append(speaker)
```

**Root cause:** `FaceMemory.store_face` signature is
`store_face(self, person_id: int, name: str, encoding: np.ndarray)`
(`face_memory.py:90`). The call passes only two positional args, so:
- `person_id` = `speaker` (a **name string**),
- `name` = `enc_array` (a **numpy array**),
- `encoding` = **missing** → `TypeError: store_face() missing 1 required positional argument: 'encoding'`.

The exception is swallowed by the event dispatcher's `except Exception` at
`main.py:2600` (logged as `handle_event error: ...`), so it fails silently to the
user and aborts the rest of the `person_detected` handler (group-greeting logic
below never runs for that event).

**Impact:** this is the **primary** live face-enrollment path (link an unrecognized
face to the guest currently identified by voice). It fails 100% of the time.
Combined with F2, **no face is ever stored during normal party operation.** The face
gallery stays empty, every face matches "unknown," the bot never recognizes a
returning guest by face. The ONLY working write path is the `/admin/learn_face`
HTTP test endpoint (`main.py:2188`), which nothing in the live flow calls.

**Fix:** use `learn_guest`, which is the name-based enroll method (assigns the next
`person_id` and writes both stores):
```python
    speaker = state_current.get("speaker_name")
    if speaker:
        _face_memory.learn_guest(speaker, enc_array)   # name-keyed enroll
        guest_profiles.identify_by_face(speaker, "auto_linked")
        detected_names.append(speaker)
```
`learn_guest(name, encoding)` is defined at `face_memory.py:262` and is what the
admin endpoint already uses. Note: the face gallery keys identities by **name**, in
its **own `person_id` space**, independent of the voice `speaker_id` / `memory.db`
person id (see Open Question OQ1).

---

### F2 🔴 — `_last_face_encoding` is write-only (stash-then-name path missing)

**Location:** set at `server/main.py:5622`, declared at `:424`. Never read anywhere.

**Code today (the stash):**
```python
else:
    new_face_count += 1
    state_current["detected_guest"] = None
    state_current["_last_face_encoding"] = enc_array   # stored, never used
```

**Root cause:** the intended design (documented at `main.py:3437-3438`) is: when a
face is seen with no known speaker, stash the encoding; later when the guest says
"my name is X," attach the stashed encoding to that name. The "attach later" half is
not implemented. `command_handlers.py:594-606` (the name-registration block) and the
`register_speaker` event handler (`main.py:5519`) register the **voice** but never
read `_last_face_encoding`, so the stashed face is dropped.

**Impact:** the fallback enrollment route (most common at a party — a new guest walks
in, the camera sees them *before* they speak) never enrolls a face. Reinforces F1:
between the two, live face enrollment is fully dead.

**Fix:** when a name is registered, consume any stashed face encoding. Add to the
`register_speaker` handler in `main.py` (after `state_current["speaker_id"] = new_id`,
around `:5527`):
```python
    # Attach a face stashed before the guest spoke, if any.
    pending_face = state_current.get("_last_face_encoding")
    if pending_face is not None and _face_memory is not None:
        try:
            _face_memory.learn_guest(name, pending_face)
            guest_profiles.identify_by_face(name, "auto_linked")
        except Exception as e:
            logger.warning(f"[FACE_ENROLL] stashed-face link failed: {e}")
        state_current["_last_face_encoding"] = None
```
Mirror the same block in `command_handlers.py` after `:599` (it has no `_face_memory`
handle directly — either pass it in, or set a flag the server consumes; simplest is
to do the linking server-side where `_face_memory` is in scope). Decide one owner for
this logic to avoid double-enroll.

---

### F3 🟠 — Qdrant voice store is dead code; all real matching is the SQLite scan

**Locations:** `register_speaker` (`speaker_id.py:346`) writes SQLite only;
`learn_voice` (`:251`) / `store_voice_qdrant` (`:154`) are **never called** anywhere
in the live flow (verified: only defined, never invoked).

**Root cause:** `identify_speaker` (`:264`) tries Qdrant first (`:285`) then falls
back to a SQLite linear cosine scan (`:298-343`). But the only enrollment path used
at runtime, `register_speaker`, does `INSERT INTO speakers ...` and never touches
Qdrant. So for every real guest the Qdrant lookup returns nothing and the SQLite
fallback does all the work.

**Impact:** not a crash — the SQLite cosine path is correct and functions. But:
- The "Qdrant primary" design is a lie; it adds a misleading layer and an always-empty
  `qdrant_voices` collection.
- The EMA refinement (F8) and any future Qdrant-only feature silently no-op.
- Confusing for maintainers (and for the next AI reading this).

**Fix (pick one):**
- **(a) Make Qdrant real:** have `register_speaker` also call `learn_voice(name, embedding)`
  so both stores get the print. Then Qdrant-first actually hits.
- **(b) Delete the Qdrant voice path:** remove `store_voice_qdrant` / `lookup_voice_qdrant` /
  `learn_voice` and the Qdrant branch in `identify_speaker`; keep the SQLite scan as the
  single source of truth (fine at party scale: 20–50 speakers, linear scan <1ms).

Recommended: **(b)** unless you expect thousands of enrolled voices. Simpler = fewer
ways to drift out of sync.

---

### F4 🟡 — Face profile link uses non-existent `id` key

**Location:** `server/main.py:5607`.
```python
face_id = str(match.get("id", ""))   # find_match returns "person_id", not "id"
```
`find_match` returns `{"person_id", "name", "confidence", "visit_count"}`
(`face_memory.py:155-161`). `match.get("id")` is always `None` → `face_id` always
`""`. `guest_profiles.identify_by_face(name, "")` then keys every face profile under
the same empty string in `_face_map`.

**Impact:** low — `identify_by_face` also keys by name, so greeting still works once
F1/F2 are fixed; but the `face_map` becomes useless for face-id-based lookup and could
collide profiles. Fix:
```python
face_id = str(match.get("person_id", ""))
```

---

### F5 🟠 — Voice threshold too loose + single-utterance enrollment

**Location:** `server/speaker_id.py:47`, `SIMILARITY_THRESHOLD = 0.65`
(overridable via `config.json → server.speaker_similarity_threshold`).

**Root cause / context (from the in-code comment):** enrollment audio is the short
"my name is X" utterance (~1.5–2s), which yields same-speaker self-similarity only
~0.70–0.74. The old 0.75 default never matched returning guests, so it was dropped to
0.65. Observed different-speaker scores ~0.49–0.56.

**Impact:** the impostor margin is ~0.10. resemblyzer d-vectors degrade fast under the
deployment conditions (music, crosstalk, TTS bleed, single short enrollment clip). A
loose threshold over noisy prints → both **false accepts** (greet the wrong person)
and **false rejects** (treat a returning guest as new). No VAD/SNR gate, no
diarization → a chunk containing two voices yields a blended garbage embedding.

**Fixes (in priority order):**
1. **Multi-sample enrollment.** Collect 3–5 short clips (or one 5–8s clip), embed each,
   store the L2-normalized mean. Far more stable prints → you can raise the threshold
   safely. Change `register_speaker` to accept/accumulate multiple chunks.
2. **VAD-gate enrollment & ID.** Only embed frames with speech energy above an SNR
   floor; reject chunks that are mostly noise/music.
3. **Suppress self-bleed.** Don't run `identify_speaker` on chunks captured while the
   bot's own TTS is playing (the server knows when it's speaking — gate on that state).
4. **Re-tune threshold after (1).** With averaged prints, expect to push back toward
   0.72–0.78. Keep it config-driven.
5. **Optional: light diarization** — at minimum, reject multi-speaker chunks (e.g.
   embedding instability across sub-windows) instead of enrolling/matching on them.

---

### F6 🟠 — Face capture/recognition robustness (HOG + frame skip + single encoding)

**Locations:** `client/person_detector.py:139` (HOG detector), `:66` (`YOLO_FRAME_SKIP=3`),
`server/face_memory.py:101` (single encoding per identity, overwritten on re-store).

**Root cause:**
- **HOG** face detector is fast but weak on non-frontal, small, low-light, motion-blurred
  faces — exactly a bathroom doorway. When `face_locations` is empty, encoding is `None`
  and the face is silently dropped (`person_detector.py:140-141`).
- **`YOLO_FRAME_SKIP=3`** processes only every 3rd frame — fewer chances to catch a good
  frontal frame.
- **Single encoding per identity.** `store_face` overwrites the stored encoding on each
  re-store (`face_memory.py:101-106`), incrementing `visit_count`. No multi-view gallery,
  so a returning guest at a new angle/lighting often exceeds the 0.6 Euclidean tolerance
  → miss.

**Impact:** even after F1/F2 are fixed, recognition accuracy is modest. Expect missed
detections (no enroll) and missed matches (returning guest not recognized).

**Fixes:**
1. **Use the CNN detector** for detection quality: `face_recognition.face_locations(img,
   model="cnn")` (GPU-accelerated; the party box is an RTX 3090 Ti — plenty). Or run a
   dedicated face detector (e.g. RetinaFace/SCRFD — already vendored under
   `gpt_sovits_env/.../modelscope/.../face_detection/`).
2. **Multi-encoding gallery per identity.** Store up to N (e.g. 5) encodings per person;
   match against the min distance across the set. Requires a schema change
   (`face_encodings` → one-row-per-encoding, or a JSON list column).
3. **Lower `YOLO_FRAME_SKIP`** (e.g. 1–2) when a person is present, or trigger encoding
   on motion/new-bbox rather than a fixed cadence.
4. **Quality gate before enroll.** Require a minimum face-box size and sharpness so you
   don't enroll a blurry/profile encoding as someone's canonical print.

---

### F7 🟡 — `lookup_face_qdrant` wrong metric (foot-gun, currently bypassed)

**Location:** `server/face_memory.py:222-260`. Uses Qdrant COSINE with a 0.4 threshold
on dlib encodings that are **Euclidean-native at 0.6**. `find_match` (`:118`)
deliberately routes ALL matching through the SQLite Euclidean scan and documents this
(`:120-134`), so the wrong-metric path is not used today. But it's still public and
callable. Either delete it or convert the Qdrant face collection to Euclidean distance
(`Distance.EUCLID`) and re-tune so it can't be misused later.

---

### F8 🟡 — EMA refinement updates only SQLite

**Location:** `server/main.py:4927` → `speaker_id.update_speaker` (`speaker_id.py:374`).
Blends 80% old / 20% new into the SQLite `speakers` row. Never updates Qdrant. Given F3
(SQLite is the de-facto source of truth) this actually works, but it confirms the
storage layers are out of sync conceptually. Resolve together with F3: once there's a
single source of truth, point EMA at it.

---

## 6. Recommended fix order

1. **F1 + F2** (one PR) — unbreak live face enrollment. ~5 lines + one consume block.
   Without these, face recognition is non-functional. Highest impact, lowest effort.
2. **F4** — one-word fix, do it in the same PR.
3. **F3 + F8** — collapse the voice storage to a single source of truth (recommend
   SQLite-only; delete dead Qdrant voice code). Removes confusion before further tuning.
4. **F5** — multi-sample voice enrollment + VAD gate + TTS-bleed suppression, then
   re-tune threshold. This is the big reliability win for voice.
5. **F6** — CNN/RetinaFace detector + multi-encoding gallery. Big reliability win for
   face. Larger change (schema + GPU detector).
6. **F7** — delete or correct the unused Qdrant face path.

---

## 7. Verification plan (per fix)

- **F1/F2:** with a known speaker set, send a `person_detected` event for an unknown
  encoding while `speaker_name` is set → assert a row appears via `GET /admin/faces`
  and `find_match` on the same encoding returns that name. Then test the
  stash-then-name path: send `person_detected` with no speaker, then `register_speaker`,
  then re-send the face → expect a by-name match.
- **F3:** after enrolling a voice, confirm `identify_speaker` returns the name on a
  second clip; confirm which store answered (DEBUG_SPEAKER logs). Ensure no empty
  `qdrant_voices` collection is required.
- **F5:** measure same-speaker vs different-speaker cosine on averaged prints; pick a
  threshold with a ≥0.15 margin. Test under recorded party-noise audio.
- **F6:** count detection rate (faces encoded / people entering) before vs after the
  detector swap; measure returning-guest match rate with a multi-encoding gallery.

**Project rule reminder (from `.claude/rules/testing.md`):** live tests must verify
actual audio playback (`_play_wav: playing` AND `_play_wav: done` in client logs) and
that spoken text matches the bubble — recognition changes affect greetings, so confirm
the greeting audio actually fires, not just the log line.

---

## 8. Open questions for the next AI / owner

- **OQ1 — ID-space unification.** Face gallery keys by **name** in its own `person_id`
  space (`face_memory.py`), voice keys by `speaker_id` in `voices.db`, and `memory.db`
  has its own person ids via `memory.register_person`. These are linked only by the
  name string. Should they be unified under one canonical person id? Today a name typo
  or two guests sharing a first name collides identities.
- **OQ2 — enrollment trigger.** Should face enrollment require a confirmed voice name
  (current intent), or should the bot proactively ask "what's your name?" when it sees a
  new face, to drive enrollment? Affects F2 design.
- **OQ3 — privacy retention.** Vectors persist across parties (SQLite/Qdrant on disk).
  Is there a wipe policy between events? `delete_speaker` exists (`speaker_id.py:405`);
  no equivalent bulk face wipe beyond per-row.
- **OQ4 — threshold config.** `speaker_similarity_threshold` is config-driven; face
  tolerance (0.6) is hardcoded in two places (`person_detector.py:65`,
  `face_memory.py:33`). Unify and make config-driven.

---

## 9. Quick reference — exact signatures (so fixes compile)

```python
# server/face_memory.py
class FaceMemory:
    def store_face(self, person_id: int, name: str, encoding: np.ndarray): ...   # :90
    def find_match(self, encoding, tolerance=None) -> Optional[dict]: ...         # :118
        # returns {"person_id", "name", "confidence", "visit_count"}
    def learn_guest(self, name: str, encoding: np.ndarray): ...                   # :262
    def get_all_faces(self) -> list: ...                                          # :288

# server/speaker_id.py  (module-level functions, not a class)
def identify_speaker(audio_data: bytes, sample_rate: int = 16000) -> dict: ...    # :264
    # returns {"name", "speaker_id", "confidence", "is_new"}
def register_speaker(name, audio_data, sample_rate=16000) -> int: ...             # :346
def update_speaker(speaker_id_val: int, audio_data, sample_rate=16000): ...       # :374
def learn_voice(name: str, embedding: np.ndarray): ...        # DEAD — never called # :251
def delete_speaker(speaker_id_val: int): ...                                      # :405

# server/guest_profiles.py
def identify_by_face(self, name: str, face_id: str) -> GuestProfile: ...          # :150
def identify_by_voice(self, name: str, voice_id: str) -> GuestProfile: ...        # :114
```
