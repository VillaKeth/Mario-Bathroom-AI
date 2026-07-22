# Recognition Reliability Hardening — Design

**Date:** 2026-07-22
**Scope:** Face + voice guest recognition for an 8-hour party deployment.
**Status:** Approved, ready for implementation planning.
**Predecessor:** `AUDIT_VOICE_FACE_RECOGNITION.md` (2026-06-17). That audit's F1–F4,
F7, F8 are fixed; its "still open" list is partly stale (see §1.2).

---

## 1. Starting position

### 1.1 Measured baseline

From `tests/recognition_lab/` — real LibriSpeech voices, Olivetti faces, party noise
mixed at controlled SNR. Numbers in `tests/recognition_lab/results.json`.

| | clean | 10 dB | 5 dB | 0 dB |
|---|---|---|---|---|
| Voice, single-sample enroll | 100% | 78% | 56% | 28% |
| Voice, multi-sample enroll | 100% | 83% | 67% | 44% |
| Face (cross-angle) | 100% | — | — | — |
| Voice+Face fused @5 dB | — | — | 100% | — |

Imposters: face 0/2 false-accept, voice 0/1 (a stranger raw-matched at cosine 0.74;
the open-set gate rejected it).

A bathroom party is realistically 5–10 dB SNR, so **voice alone is 67–83% and face is
what carries identity**. The fused path is the product.

### 1.2 Already working — do not rebuild

- Face enrollment end-to-end (`server/face_enrollment.py`), both enroll routes live.
- Open-set gate: `_voice_commit_ok`, `server/main.py:6294`.
- SNR-aware fusion: `server/main.py:6302`, face wins, voice floor scales with noise.
- TTS bleed suppressed client-side: `client/main.py:378-381` — mic is not sent while
  playback is active, plus a 500 ms grace. The audit lists this as open (F5c); it is not.
- EMA refinement fires only on a committed match: `server/main.py:6435-6439`. No
  print-drift from rejected matches. Also listed as a risk in the audit; it is not.
- Ask-and-enroll loop exists: unknown face → stash encoding (`main.py:7239`) → greet
  "Who are you?" (`main.py:7272`) → parse reply (`main.py:252`) → `link_pending_face`
  (`main.py:7152`).
- `resemblyzer`, `face_recognition`, `ultralytics` all installed in `venv/`.

Both galleries are currently empty (`voices.db` 0 speakers, `memory.db.face_encodings`
0 rows). That is expected — no party has run since the last reset, and enrollment is live.

### 1.3 Design principles

1. **Face carries identity, voice confirms.** Do not invert this to prop up voice.
2. **Fail closed.** A missed enrollment costs one greeting. A wrong binding breaks
   recognition *and* misnames a guest for the rest of the night. Always prefer "unknown".
3. **Measured, not guessed.** Every workstream lands with a before/after lab number.
4. **CPU-first.** The party box runs `gemma3:27b` plus GPT-SoVITS on one RTX 3090 Ti.
   Recognition must not contend for GPU except where it is event-driven and bounded.

---

## 2. Workstreams

Ordered by impact. W1 is an active wrong-answer bug; the rest are reliability.

### W1 — Binding correctness (bug fix)

**Problem.** `server/face_enrollment.py:resolve_faces` mis-binds names to faces whenever
more than one unknown face shares a frame. Two distinct defects:

- **`:56-59`** — if any speaker is currently identified, the loop calls
  `learn_guest(speaker_name, enc)` for *every* unknown face in the batch. Jacob speaks
  while three people are in view → three `face_encodings` rows all named "Jacob", three
  different encodings. All three are greeted as Jacob from then on. A doorway camera that
  catches hallway traffic poisons the gallery quickly.
- **`:65`** — `pending_encoding = enc` overwrites each iteration, so only the *last*
  unknown face survives. Three strangers enter, `new_face_count=3`, Mario asks "who are
  you?", and the first person to answer has a different stranger's face bound to their name.

**Fix.** Enroll only when the batch contains exactly one unknown face.

- Count unknown faces first, then act.
- Exactly one unknown, speaker known → link that face to the speaker (current behavior,
  now safe).
- Exactly one unknown, no speaker → stash as `pending_encoding` (current behavior).
- Two or more unknown → enroll nothing, stash nothing. Return `ambiguous: True`.

`resolve_faces` returns `{"detected", "new_face_count", "pending_encoding", "ambiguous"}`.
`server/main.py` keeps its existing group greeting (`:7261-7276`) unchanged — Mario still
says "and who's your friends?" — but no enrollment occurs while `ambiguous` is set.

**Acceptance.** Unit tests: one unknown + speaker → one row; three unknown + speaker →
zero rows; three unknown, no speaker → `pending_encoding is None` and `ambiguous is True`;
one unknown, no speaker → encoding stashed. Existing `test_face_enrollment` stays green.

### W2 — Multi-encoding face gallery

**Problem.** `server/face_memory.py` stores one encoding per person — `face_encodings`
has `person_id` as PRIMARY KEY (`:37-45`) and `store_face` overwrites it on re-store
(`:61-66`). A returning guest at a new angle or under different lighting exceeds the 0.6
Euclidean tolerance and is missed. This is the dominant face failure mode.

**Schema.** New table, one row per encoding:

```sql
CREATE TABLE IF NOT EXISTS face_gallery (
    encoding_id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id   INTEGER NOT NULL,
    name        TEXT    NOT NULL,
    encoding    TEXT    NOT NULL,        -- JSON list, 128 float64
    quality     REAL    NOT NULL DEFAULT 0.0,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_face_gallery_person ON face_gallery(person_id);
```

`face_encodings` is retained as the identity table (`person_id`, `name`, `first_seen`,
`last_seen`, `visit_count`) and remains the allocator of `person_id`. Its `encoding`
column is **not dropped** — it stays as the migration source and as a rollback path, and
after migration no code reads it. Removing the column is explicitly out of scope for this
work. Both tables live in `server/data/memory.db` (`server/main.py:927`).

**Migration.** On `FaceMemory.__init__`, if `face_gallery` is empty and `face_encodings`
has rows, copy each row's encoding across with `quality=0.0`. Idempotent. Back up
`memory.db` before the first migrated run.

**Matching.** `find_match` computes, per person, the *minimum* distance across that
person's encodings; the best person wins if that distance is within tolerance. Confidence
stays `max(0.0, 1.0 - distance)` for API compatibility. Party scale is 20–50 guests × ≤5
encodings = ≤250 vectors; a linear scan stays well under a millisecond, so no index.

**Cap and eviction.** `GALLERY_MAX_PER_PERSON = 5`. On insert past the cap, drop the
encoding closest to that person's centroid — the most redundant view — rather than the
oldest. Keeps angle and lighting diversity, which is the entire point of the gallery.

**Acceptance.** A person enrolled from view A is matched from view B where a
single-encoding gallery misses. Cap is never exceeded. Eviction increases mean
pairwise distance within a person's set. Migration is idempotent across two runs.

### W3 — Enrollment quality gate

**Problem.** `client/person_detector.py:158` returns `encodings[0]` with no quality
check, so a blurry, tiny, or profile face can become a guest's canonical print. With W2
this matters less per-encoding but still pollutes the gallery.

**Gate.** Reject a candidate encoding before enrollment unless all hold:

- Face box ≥ `face_min_box_px` (default 80) on its shorter side.
- Laplacian variance of the grayscale face crop ≥ `face_min_sharpness` (default 40.0) —
  standard blur detector, one OpenCV call on a crop already in memory.
- Face box is not extreme-aspect (ratio within 0.6–1.7), a cheap near-profile proxy.

The gate applies to **enrollment only**. Matching must still accept lower-quality
encodings — recognizing a returning guest from a mediocre frame is desirable; *storing*
that frame as their reference is not. `client/person_detector.py:_encode_face` serves both
paths and cannot tell them apart, so the check is split:

- **Client computes, does not reject.** `_encode_face` measures box size, sharpness, and
  aspect on the crop it already holds, and attaches a `quality` float (0.0–1.0) to the
  face entry in the `person_detected` payload alongside `encoding`. Cost is one OpenCV
  Laplacian call per face, CPU-only. It still returns an encoding regardless of score.
- **Server gates at enrollment.** `resolve_faces` enrolls only when
  `quality >= face_min_quality` (default 0.5, derived from the three sub-thresholds
  above). Matching ignores `quality` entirely.

A missing `quality` key — an older client, or the mirror path — is treated as
`quality=1.0` so the change is backward-compatible and never silently stops enrollment.
The score is persisted to `face_gallery.quality` and used as an eviction tie-breaker
(evict redundant-and-low-quality first).

**Acceptance.** Synthetic blurred/small/profile crops are rejected; a clean frontal crop
passes. Match rate on low-quality probes does not regress.

### W4 — Margin checks, both modalities

**Problem.** Both matchers take best-under-threshold with no ambiguity check —
`face_memory.py:106` and `speaker_id.py:216`. With 30 enrolled guests, two people with
similar embeddings produce a confident wrong name.

**Fix.** Accept the best match only if the runner-up *belonging to a different person* is
worse by a margin. Two encodings of the same person are not competitors — this interacts
directly with W2, so margins are computed per-person after the min-distance reduction.

- Face: `second_best_distance - best_distance >= face_match_margin` (default 0.05).
- Voice: `best_similarity - second_best_similarity >= voice_match_margin` (default 0.06).
- Fewer than two distinct enrolled people → margin check is skipped (nothing to confuse).
- Ambiguous → return unknown. Fusion and the open-set gate then behave as they already do
  for an unknown.

Defaults above are starting points; W8 tunes them against measured lab curves.

**Acceptance.** Two near-duplicate enrolled prints plus a probe between them returns
unknown rather than a coin-flip name. A clearly-best match is unaffected. Single-person
gallery still matches.

### W5 — Detector quality, resource-aware

**Problem.** `client/person_detector.py:83` defaults to the HOG face detector, which is
weak on non-frontal, small, low-light, and motion-blurred faces — precisely a bathroom
doorway. `:67` runs YOLO every 3rd frame, limiting chances at a good capture.

**Fix.**

- Auto-select the detector by hardware tier via `server/hardware.py:get_tier()`, which
  returns one of `ultra` / `high` / `medium` / `low` (four tiers, lowercase — note that
  CLAUDE.md's five-tier `VERY_HIGH` list is inaccurate). Use `cnn` on `ultra` and `high`,
  `hog` on `medium` and `low`. The party box (24 GB VRAM / 256 GB RAM / 64 cores) resolves
  to `ultra`; the P1000 dev box (4 GB VRAM) resolves to `low` and correctly stays on HOG.
  The existing `FACE_DETECTOR_MODEL` env override wins over the auto-selection.
- Adaptive frame skip: 3 while no person has been detected recently, 1 while a person box
  is present, reverting after 2 s with no detection. More shots at a good frontal frame
  exactly when someone is at the door.

GPU cost stays bounded: face encoding only runs on frames where YOLO already found a
person, which is event-driven rather than continuous, and the party box has 24 GB with
gemma3:27b at ~16 GB.

**Acceptance.** Tier→model mapping unit-tested with a mocked tier. Env override still
wins. Frame-skip state machine unit-tested. Encode-rate ceiling holds under a synthetic
always-person stream.

### W6 — Voice consistency gate

**Problem.** A 3 s chunk containing two speakers, or speech over loud music, yields a
blended embedding that is meaningless. `server/speaker_id.py` has an RMS energy floor
(`_has_speech_energy`) but no check that the chunk contains *one consistent* voice.

**Fix — two stages, cheap first.** Both run inside `get_embedding`, before the full-chunk
embedding is returned.

- **Stage A (no embedding cost).** Split the chunk into 3 equal sub-windows. Compute RMS
  and spectral flatness per window. Reject if **fewer than 2 of the 3** windows clear the
  existing `MIN_SPEECH_RMS` floor, or if the mean spectral flatness across windows exceeds
  `voice_max_flatness` (default 0.45) — flatness near 1.0 is noise-like, speech is peaky.
  This throws out music and room noise for the cost of an FFT.
- **Stage B (2 extra embeddings).** Only if Stage A passes: embed the first and second
  **half** of the chunk and compare. If `cos(first_half, second_half) <
  voice_consistency_tau` (default 0.60), the chunk is unstable — two speakers, or a
  speaker plus heavy interference — so reject it.

  Halves, not the Stage A thirds: the live chunk is 3.0 s (`CHUNK_SIZE = 96000` bytes at
  16 kHz int16), so halves are 1.5 s each. resemblyzer's partial-utterance window is
  1.6 s, so thirds (1.0 s) would be zero-padded and yield noisier embeddings. Stage A
  needs no embedding and keeps its finer 3-window split.

Rejection returns `None`, which every caller already handles as "no usable voice".

**Cost.** Two extra `embed_utterance` calls per *accepted* chunk, on CPU
(`VoiceEncoder("cpu")`, `speaker_id.py:110`), on a 64-core box, entirely off the GPU.
Rejected-at-Stage-A chunks cost only an FFT and never reach Stage B, so the common
noise case is nearly free.

**Acceptance.** Single-speaker clean and noisy chunks still pass and still match.
Two-speaker mixes are rejected at ≥80% while single-speaker false-rejects stay ≤5%.
`τ` and `voice_max_flatness` are chosen from the measured curve in W8, not assumed.

### W7 — Threshold unification

Face tolerance 0.6 is hardcoded twice — `client/person_detector.py:66` and
`server/face_memory.py:24`. Voice threshold is already config-driven
(`server.speaker_similarity_threshold`). Closes audit OQ4.

Add to `config.json` under `server`, all with the code defaults named above so behavior
is unchanged until tuned:

`face_match_tolerance`, `face_match_margin`, `voice_match_margin`,
`face_min_box_px`, `face_min_sharpness`, `face_min_quality`,
`voice_consistency_tau`, `voice_max_flatness`, `gallery_max_per_person`.

Per project convention, `config.json` is gitignored — add these to
`config.example.json` as the tracked template. Code defaults must stand alone so a
missing config key never changes behavior.

**Acceptance.** Removing every new key from config reproduces the code defaults exactly.

### W8 — Lab extension and tuning

The lab is the acceptance instrument for W2, W3, W4, W6. Extend
`tests/recognition_lab/run_recognition_test.py`, reusing its existing helpers
(`mix_party`, `snr_to_noise`, `enroll_voices`, `face_encoding`, `load_people`):

- **Multi-speaker mixes** — overlap two LibriSpeech speakers at several ratios; used to
  pick `voice_consistency_tau` and `voice_max_flatness` from a real curve.
- **Group enrollment scenario** — batches of 1, 2, and 3 unknown faces, asserting W1's
  fail-closed behavior end-to-end rather than only at unit level.
- **Cross-angle / low-light face probes** — enroll from one view, probe from another,
  with and without the W2 gallery, to quantify the gallery's gain.
- **Margin sweep** — vary `face_match_margin` and `voice_match_margin`, record
  true-accept vs false-accept, choose the knee.

`results.json` gains a `baseline` and `after` block so the delta is recorded in-repo
rather than living in a chat log. Every workstream reports its own before/after row.

---

## 3. Data flow after the changes

Unchanged in shape — the additions are gates and a wider gallery, not new stages.

**Face.** Camera frame → YOLO person box (adaptive skip, W5) → face detect (tier-selected
model, W5) → encoding + **quality score (W3, client-side, never rejects)** → server
`resolve_faces` → `find_match` across the **multi-encoding gallery (W2)** with a
**margin check (W4)** → identity or unknown. On the enrollment branch only:
**unknown-count check (W1)** then **quality threshold (W3)**.

**Voice.** Mic (already gated during TTS playback) → 3 s chunk → RMS floor →
**Stage A flatness (W6)** → **Stage B sub-window consistency (W6)** → embedding →
cosine scan with **margin check (W4)** → `_voice_commit_ok` → `fuse_identity` → identity
or unknown.

Fusion (`server/recognition_fusion.py`) is untouched. It already implements the correct
policy and is measured at 100% fused @5 dB.

---

## 4. Testing

Unit tests per workstream as listed in each acceptance block, following the existing TDD
pattern (`tests/test_face_enrollment.py`, `test_recognition_fusion.py`,
`test_speaker_audio_gate.py`, `test_person_detector_config.py`).

Lab runs per W8 for the statistical claims — unit tests cannot show a match-rate delta.

Live verification per `.claude/rules/testing.md`: recognition changes affect greetings, so
confirm the greeting audio actually plays (`_play_wav: playing` **and** `_play_wav: done`
in the client log) and that spoken text matches the bubble. Restart **both** server and
client when switching characters for a live test.

---

## 5. Risks

| Risk | Mitigation |
|---|---|
| Schema migration corrupts `memory.db` | Back up before first migrated run; migration is additive and idempotent; `face_encodings` is retained, not dropped. |
| CNN detector contends with LLM/TTS for GPU | Event-driven only (runs on YOLO person hits), tier-gated so the dev box never enables it, env override available to force `hog`. |
| Margins too strict → returning guests missed | Defaults are conservative; W8 sweeps both and picks the knee from measured curves; all config-driven for party-night adjustment. |
| Stage B adds latency to the response path | Two CPU embeddings on a 64-core box, only on chunks that already passed Stage A. Measure in W8; if it lands in the response path measurably, move it off the critical path. |
| Fail-closed W1 reduces total enrollments | Accepted trade — a wrong binding is strictly worse. Mario still asks; guests alone at the door still enroll normally. |

---

## 6. Non-goals

- **pyannote diarization.** Heavy dependency, HF token, GPU contention. W6's cheap gate
  is the chosen alternative.
- **Unified person-ID space** (audit OQ1). Face gallery, `voices.db`, and `memory.db`
  people are linked only by name string, so a shared first name collides identities. Real
  problem, materially larger change, deserves its own spec.
- **Privacy retention policy** (audit OQ3). No bulk wipe between parties. Separate concern.
- Rewriting fusion, the open-set gate, or TTS-bleed suppression — all already correct.
