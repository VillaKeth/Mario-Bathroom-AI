# Recognition Reliability Hardening — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make returning-guest recognition reliable across an 8-hour party by fixing a name/face mis-binding bug and hardening both modalities behind measured thresholds.

**Architecture:** Face carries identity, voice confirms — the existing fusion policy (`server/recognition_fusion.py`) is correct and untouched. Changes are gates and a wider face gallery bolted onto the existing pipeline stages, not new stages. Everything fails closed to "unknown".

**Tech Stack:** Python 3.11, SQLite, numpy, `face_recognition` (dlib, 128-dim Euclidean), `resemblyzer` (256-dim cosine), `ultralytics` YOLOv8n, OpenCV, pytest.

**Spec:** `docs/superpowers/specs/2026-07-22-recognition-reliability-design.md`
**Branch:** `feature/recognition-reliability` (already created, spec committed at `4f20200`)

## Global Constraints

- Run everything through the repo venv: `venv/Scripts/python.exe` on Windows. Tests: `venv/Scripts/python.exe -m pytest`.
- `print()` for logging in `command_handlers.py`; `logger` elsewhere (both `face_memory.py` and `speaker_id.py` already have module loggers).
- **`git add <specific files>` only** — never `git add -A`. Qdrant `.lock` files under `server/data/qdrant_memories/` must never be committed.
- Commit trailer on every commit: `Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>`
- `config.json` is gitignored (it holds a live `admin_api_key`). New keys go in `config.example.json`, which IS tracked.
- **Code defaults must stand alone.** A missing config key must reproduce current behavior exactly.
- No ellipsis (`...`) in any hardcoded string that reaches TTS.
- Hardware tiers are `ultra` / `high` / `medium` / `low` — four, lowercase, from `server/hardware.py:get_tier()`. CLAUDE.md's five-tier `VERY_HIGH` list is wrong; do not use it.
- Tests live in `tests/`, import server modules via `sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))` — follow `tests/test_face_enrollment.py`.
- Existing suite must stay green. Baseline before starting: some tests fail in a fresh worktree purely because `config.json` is absent — diff your failing set against a clean baseline before blaming a change.

---

### Task 0: Capture the pre-change baseline

Must run BEFORE Task 1 touches anything. Once the modules change, the old numbers are unrecoverable without a worktree, and every accuracy claim in Task 8 is measured against this file.

**Files:**
- Create: `tests/recognition_lab/results_baseline.json`

**Interfaces:**
- Consumes: nothing.
- Produces: `tests/recognition_lab/results_baseline.json` — the untouched-code reference Task 8 compares against.

- [ ] **Step 1: Confirm the working tree is clean and on the branch**

Run: `git status --porcelain && git branch --show-current`
Expected: no output from the first command, `feature/recognition-reliability` from the second.

- [ ] **Step 2: Run the lab against unmodified code**

Run: `venv/Scripts/python.exe tests/recognition_lab/run_recognition_test.py`
Expected: completes and writes `tests/recognition_lab/results.json`.

If it fails because the corpus is missing, build it first with `venv/Scripts/python.exe tests/recognition_lab/build_library.py` and note in the commit that the corpus was regenerated (encodings may differ slightly from the committed numbers).

- [ ] **Step 3: Preserve it as the baseline**

```bash
cp tests/recognition_lab/results.json tests/recognition_lab/results_baseline.json
```

- [ ] **Step 4: Commit**

```bash
git add tests/recognition_lab/results_baseline.json
git commit -m "test(recognition): capture pre-change lab baseline

Reference numbers measured against untouched code, so the hardening work can
report a real delta instead of comparing against the stale figures already in
results.json.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 1: Fail-closed face/name binding (W1)

Fixes an active bug: with two unknown faces in one frame, every unknown face is enrolled under the current speaker's name, and the single `pending_encoding` slot keeps only the last face.

**Files:**
- Modify: `server/face_enrollment.py:27-71`
- Modify: `server/main.py:7236-7239`
- Test: `tests/test_face_enrollment.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `resolve_faces(faces, face_memory, speaker_name) -> {"detected": list[dict], "new_face_count": int, "pending_encoding": np.ndarray | None, "ambiguous": bool}`. The `ambiguous` key is new. Task 5 extends this function again.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_face_enrollment.py`:

```python
def _enc(seed):
    """Deterministic distinct 128-dim encoding."""
    rng = np.random.default_rng(seed)
    return rng.random(128).tolist()


def test_single_unknown_face_with_speaker_enrolls_one():
    mem = FakeFaceMemory(match_result=None)
    out = face_enrollment.resolve_faces([{"encoding": _enc(1)}], mem, "Jacob")
    assert len(mem.learned) == 1
    assert mem.learned[0][0] == "Jacob"
    assert out["ambiguous"] is False


def test_multiple_unknown_faces_with_speaker_enroll_nothing():
    """Three strangers + a known speaker must NOT all become that speaker."""
    mem = FakeFaceMemory(match_result=None)
    faces = [{"encoding": _enc(1)}, {"encoding": _enc(2)}, {"encoding": _enc(3)}]
    out = face_enrollment.resolve_faces(faces, mem, "Jacob")
    assert mem.learned == []
    assert out["ambiguous"] is True
    assert out["new_face_count"] == 3


def test_multiple_unknown_faces_no_speaker_stash_nothing():
    mem = FakeFaceMemory(match_result=None)
    faces = [{"encoding": _enc(1)}, {"encoding": _enc(2)}]
    out = face_enrollment.resolve_faces(faces, mem, None)
    assert out["pending_encoding"] is None
    assert out["ambiguous"] is True


def test_single_unknown_face_no_speaker_stashes():
    mem = FakeFaceMemory(match_result=None)
    out = face_enrollment.resolve_faces([{"encoding": _enc(1)}], mem, None)
    assert out["pending_encoding"] is not None
    assert out["ambiguous"] is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `venv/Scripts/python.exe -m pytest tests/test_face_enrollment.py -v -k "unknown_face"`
Expected: FAIL — `KeyError: 'ambiguous'` and `assert [] == []` failing on the three-stranger case (it currently learns 3).

- [ ] **Step 3: Rewrite `resolve_faces`**

Replace `server/face_enrollment.py:27-71` entirely:

```python
def resolve_faces(faces: list, face_memory, speaker_name: Optional[str]) -> dict:
    """Match/enroll a batch of detected faces.

    Known faces are always reported. Enrollment is FAIL-CLOSED: it happens only when
    the batch contains exactly ONE unknown face. With two or more unknowns we cannot
    tell which face belongs to the name we are about to hear, and a wrong binding is
    permanent and silent — so we enroll nothing and report `ambiguous`.

    Returns: {"detected", "new_face_count", "pending_encoding", "ambiguous"}
    """
    detected = []
    unknown = []

    for face_data in faces or []:
        if not isinstance(face_data, dict):
            continue
        enc = _valid_encoding(face_data.get("encoding"))
        if enc is None:
            continue

        match = face_memory.find_match(enc) if face_memory is not None else None
        if match and match.get("name"):
            detected.append({
                "name": match["name"],
                "person_id": match.get("person_id"),
                "visit_count": match.get("visit_count"),
                "confidence": match.get("confidence"),
            })
        else:
            unknown.append(enc)

    new_face_count = len(unknown)
    ambiguous = new_face_count > 1
    pending_encoding = None

    if new_face_count == 1:
        enc = unknown[0]
        if speaker_name:
            # Exactly one unknown face and we know who is talking -> safe to bind.
            if face_memory is not None:
                face_memory.learn_guest(speaker_name, enc)
            detected.append({"name": speaker_name, "person_id": None,
                             "visit_count": None, "confidence": None})
        else:
            # Nobody identified yet -> remember it until a name arrives.
            pending_encoding = enc

    return {
        "detected": detected,
        "new_face_count": new_face_count,
        "pending_encoding": pending_encoding,
        "ambiguous": ambiguous,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `venv/Scripts/python.exe -m pytest tests/test_face_enrollment.py -v`
Expected: PASS, all tests including the pre-existing F1/F2/F4 ones.

- [ ] **Step 5: Guard the stash at the call site**

`server/main.py:7236-7239` currently stashes unconditionally. Replace:

```python
        new_face_count = face_result["new_face_count"]
        if face_result["pending_encoding"] is not None:
            # F2: stash the unknown face so it can be named when the guest speaks.
            # W1: resolve_faces only supplies this when exactly ONE unknown face was
            # present, so we can never bind a name to the wrong stranger.
            state_current["detected_guest"] = None
            state_current["_last_face_encoding"] = face_result["pending_encoding"]
        elif face_result.get("ambiguous"):
            # Two or more unknown faces — greet the group but enroll nobody.
            state_current["detected_guest"] = None
            state_current["_last_face_encoding"] = None
            logger.info(f"[FACE_ENROLL] {new_face_count} unknown faces in frame — "
                        f"enrollment deferred (fail-closed)")
```

- [ ] **Step 6: Run the broader recognition suite**

Run: `venv/Scripts/python.exe -m pytest tests/test_face_enrollment.py tests/test_recognition_fusion.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add server/face_enrollment.py server/main.py tests/test_face_enrollment.py
git commit -m "fix(recognition): fail closed when multiple unknown faces share a frame

resolve_faces enrolled EVERY unknown face under the current speaker's name and
kept only the last face in its single pending slot. A group at the door produced
several gallery rows under one guest's name, and the first person to answer
'who are you?' got a stranger's face bound to them.

Enroll only when exactly one unknown face is present; otherwise report ambiguous
and enroll nothing. A missed enrollment self-corrects on the next visit; a wrong
binding is silent and permanent.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 2: Recognition config module (W7)

Shared tunables for every later task. Built first so nothing hardcodes a threshold twice.

**Files:**
- Create: `server/recognition_config.py`
- Modify: `config.example.json`
- Test: `tests/test_recognition_config.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `recognition_config.get(name: str) -> float | int`, `recognition_config.reset_cache() -> None`, `recognition_config.DEFAULTS: dict`. Tasks 3–7 read thresholds only through `get()`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_recognition_config.py`:

```python
"""Tests for server/recognition_config.py — central recognition tunables."""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

import recognition_config  # noqa: E402


def test_defaults_available_without_config(tmp_path, monkeypatch):
    monkeypatch.setattr(recognition_config, "_CONFIG_PATH", str(tmp_path / "missing.json"))
    recognition_config.reset_cache()
    assert recognition_config.get("face_match_tolerance") == 0.6
    assert recognition_config.get("gallery_max_per_person") == 5


def test_config_overrides_default(tmp_path, monkeypatch):
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"server": {"face_match_margin": 0.11}}), encoding="utf-8")
    monkeypatch.setattr(recognition_config, "_CONFIG_PATH", str(cfg))
    recognition_config.reset_cache()
    assert recognition_config.get("face_match_margin") == 0.11
    # untouched keys still fall back to code defaults
    assert recognition_config.get("voice_match_margin") == 0.06


def test_unknown_key_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(recognition_config, "_CONFIG_PATH", str(tmp_path / "missing.json"))
    recognition_config.reset_cache()
    try:
        recognition_config.get("nope")
    except KeyError:
        return
    raise AssertionError("expected KeyError for unknown tunable")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/Scripts/python.exe -m pytest tests/test_recognition_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'recognition_config'`.

- [ ] **Step 3: Create the module**

Create `server/recognition_config.py`:

```python
"""Central tunables for face + voice recognition.

Every threshold used by face_memory, speaker_id, person_detector and
face_enrollment is read from here so the party box can be tuned without a code
change. Code defaults stand alone: a missing config.json, or a missing key inside
it, reproduces the shipped behavior exactly.

See docs/superpowers/specs/2026-07-22-recognition-reliability-design.md (W7).
"""
import json
import logging
import os

logger = logging.getLogger(__name__)

DEFAULTS = {
    "face_match_tolerance": 0.6,      # dlib euclidean, calibrated
    "face_match_margin": 0.05,        # best vs runner-up distance gap
    "voice_match_margin": 0.06,       # best vs runner-up cosine gap
    "face_min_box_px": 80,            # shorter side of the face box
    "face_min_sharpness": 40.0,       # laplacian variance floor
    "face_min_quality": 0.5,          # combined score required to ENROLL
    "voice_consistency_tau": 0.60,    # sub-window agreement floor
    "voice_max_flatness": 0.45,       # spectral flatness ceiling (noise reject)
    "gallery_max_per_person": 5,      # encodings retained per identity
}

_CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")
_cache = None


def _load() -> dict:
    global _cache
    if _cache is not None:
        return _cache
    values = dict(DEFAULTS)
    try:
        with open(_CONFIG_PATH, encoding="utf-8") as f:
            server_cfg = json.load(f).get("server", {})
        for key in DEFAULTS:
            if key in server_cfg:
                values[key] = server_cfg[key]
    except FileNotFoundError:
        pass
    except Exception as e:
        logger.warning(f"[recognition_config] config read failed, using defaults: {e}")
    _cache = values
    return _cache


def get(name: str):
    """Return a recognition tunable (config.json server.<name>, else code default).

    Raises KeyError for an unknown tunable — a typo should fail loudly, not
    silently return None and disable a gate.
    """
    values = _load()
    if name not in values:
        raise KeyError(f"unknown recognition tunable: {name}")
    return values[name]


def reset_cache():
    """Drop the cached values (tests, config hot-reload)."""
    global _cache
    _cache = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/Scripts/python.exe -m pytest tests/test_recognition_config.py -v`
Expected: PASS, 3 tests.

- [ ] **Step 5: Add the keys to the tracked config template**

In `config.example.json`, inside the existing `"server"` object, add (keep surrounding keys and trailing-comma validity intact):

```json
    "face_match_tolerance": 0.6,
    "face_match_margin": 0.05,
    "voice_match_margin": 0.06,
    "face_min_box_px": 80,
    "face_min_sharpness": 40.0,
    "face_min_quality": 0.5,
    "voice_consistency_tau": 0.60,
    "voice_max_flatness": 0.45,
    "gallery_max_per_person": 5,
```

Verify it is still valid JSON:

Run: `venv/Scripts/python.exe -c "import json;json.load(open('config.example.json',encoding='utf-8'));print('config.example.json OK')"`
Expected: `config.example.json OK`

- [ ] **Step 6: Commit**

```bash
git add server/recognition_config.py tests/test_recognition_config.py config.example.json
git commit -m "feat(recognition): central config module for recognition tunables

Face tolerance was hardcoded in two places and every new gate would have added
more. One source, code defaults that stand alone, unknown keys raise.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 3: Multi-encoding face gallery (W2)

The dominant face failure: one encoding per person, overwritten on re-store, so a returning guest at a new angle exceeds tolerance and is missed.

**Files:**
- Modify: `server/face_memory.py` (whole file — `_init_db`, `store_face`, `find_match`, `learn_guest`)
- Test: `tests/test_face_gallery.py`

**Interfaces:**
- Consumes: `recognition_config.get` (Task 2).
- Produces: `FaceMemory.learn_guest(name, encoding, quality=0.0) -> int` (now returns the person_id and reuses an existing person_id for a known name). `FaceMemory.find_match` return shape is unchanged: `{"person_id", "name", "confidence", "visit_count"}`. New: `FaceMemory.gallery_size(person_id) -> int`. Task 4 modifies `find_match`; Task 5 passes `quality` into `learn_guest`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_face_gallery.py`:

```python
"""Tests for the multi-encoding face gallery (spec W2)."""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

from face_memory import FaceMemory  # noqa: E402


@pytest.fixture
def mem(tmp_path):
    return FaceMemory(str(tmp_path / "faces.db"))


def _vec(seed, jitter=0.0):
    rng = np.random.default_rng(seed)
    base = rng.random(128)
    if jitter:
        base = base + np.random.default_rng(seed + 999).normal(0, jitter, 128)
    return base


def test_same_name_reuses_person_id(mem):
    pid1 = mem.learn_guest("Jacob", _vec(1))
    pid2 = mem.learn_guest("Jacob", _vec(2))
    assert pid1 == pid2
    assert mem.gallery_size(pid1) == 2


def test_second_view_matches_after_gallery_enroll(mem):
    """A view that misses against view A alone must match once A and B are both stored."""
    view_a, view_b = _vec(1), _vec(2)
    mem.learn_guest("Jacob", view_a)
    assert mem.find_match(view_b) is None          # too far from A alone
    mem.learn_guest("Jacob", view_b)
    match = mem.find_match(view_b)
    assert match is not None and match["name"] == "Jacob"


def test_gallery_cap_enforced(mem):
    pid = None
    for i in range(9):
        pid = mem.learn_guest("Jacob", _vec(i))
    assert mem.gallery_size(pid) <= 5


def test_migration_from_legacy_encodings(tmp_path):
    """Rows written by the pre-gallery schema must be pulled into the gallery."""
    db = str(tmp_path / "faces.db")
    mem_a = FaceMemory(db)
    pid = mem_a.learn_guest("Jacob", _vec(1))
    # simulate a legacy DB: gallery emptied, identity row retains its encoding
    import sqlite3
    with sqlite3.connect(db) as conn:
        conn.execute("DELETE FROM face_gallery")
        conn.commit()
    mem_b = FaceMemory(db)                          # re-init triggers migration
    assert mem_b.gallery_size(pid) == 1
    assert mem_b.find_match(_vec(1))["name"] == "Jacob"


def test_migration_is_idempotent(tmp_path):
    db = str(tmp_path / "faces.db")
    mem_a = FaceMemory(db)
    pid = mem_a.learn_guest("Jacob", _vec(1))
    size_before = FaceMemory(db).gallery_size(pid)
    size_after = FaceMemory(db).gallery_size(pid)
    assert size_before == size_after == 1


def test_unknown_face_still_returns_none(mem):
    mem.learn_guest("Jacob", _vec(1))
    assert mem.find_match(_vec(500)) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `venv/Scripts/python.exe -m pytest tests/test_face_gallery.py -v`
Expected: FAIL — `AttributeError: 'FaceMemory' object has no attribute 'gallery_size'`.

- [ ] **Step 3: Add the gallery schema and migration**

In `server/face_memory.py`, add the import and extend `__init__` / `_init_db`. Replace lines 24-48:

```python
    def __init__(self, db_path: str, match_tolerance: float = None,
                 collection_name: str = "mario_faces"):
        # `collection_name` is retained for back-compat with existing callers
        # (main.py, recognition lab); it is unused now that matching is SQLite-only.
        self._db_path = db_path
        if match_tolerance is None:
            match_tolerance = recognition_config.get("face_match_tolerance")
        self._tolerance = match_tolerance
        self._lock = threading.RLock()
        self._init_db()

    def _init_db(self):
        os.makedirs(os.path.dirname(self._db_path) or ".", exist_ok=True)
        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS face_encodings (
                    person_id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    encoding TEXT NOT NULL,
                    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    visit_count INTEGER DEFAULT 1
                )
            """)
            # W2: one row per encoding. face_encodings stays as the identity table
            # and person_id allocator; its `encoding` column is kept as the
            # migration source and rollback path but is no longer read for matching.
            conn.execute("""
                CREATE TABLE IF NOT EXISTS face_gallery (
                    encoding_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    person_id   INTEGER NOT NULL,
                    name        TEXT    NOT NULL,
                    encoding    TEXT    NOT NULL,
                    quality     REAL    NOT NULL DEFAULT 0.0,
                    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_face_gallery_person "
                         "ON face_gallery(person_id)")
            conn.commit()
        finally:
            conn.close()
        self._migrate_legacy_encodings()

    def _migrate_legacy_encodings(self):
        """Pull pre-gallery `face_encodings.encoding` rows into face_gallery. Idempotent."""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                if conn.execute("SELECT COUNT(*) FROM face_gallery").fetchone()[0]:
                    return
                rows = conn.execute(
                    "SELECT person_id, name, encoding FROM face_encodings").fetchall()
                for pid, name, enc_json in rows:
                    conn.execute(
                        "INSERT INTO face_gallery (person_id, name, encoding, quality) "
                        "VALUES (?, ?, ?, 0.0)", (pid, name, enc_json))
                if rows:
                    conn.commit()
                    logger.info(f"[face_memory] migrated {len(rows)} legacy encodings into gallery")
            finally:
                conn.close()
```

Add to the imports at the top of the file, after `import numpy as np`:

```python
import recognition_config
```

- [ ] **Step 4: Add gallery insert with cap and eviction**

Add these methods to `FaceMemory`:

```python
    def _add_encoding(self, conn, person_id: int, name: str,
                      encoding: np.ndarray, quality: float = 0.0):
        """Insert an encoding, then evict the most redundant if over cap.

        Evicts the encoding CLOSEST to the person's centroid — the most redundant
        view — rather than the oldest, because gallery value is view diversity.
        Ties break toward the lower quality score.
        """
        conn.execute(
            "INSERT INTO face_gallery (person_id, name, encoding, quality) VALUES (?, ?, ?, ?)",
            (person_id, name, json.dumps(np.asarray(encoding).tolist()), float(quality)))

        cap = int(recognition_config.get("gallery_max_per_person"))
        rows = conn.execute(
            "SELECT encoding_id, encoding, quality FROM face_gallery WHERE person_id = ?",
            (person_id,)).fetchall()
        if len(rows) <= cap:
            return

        vecs = [(rid, np.array(json.loads(enc), dtype=np.float64), q) for rid, enc, q in rows]
        centroid = np.mean([v for _, v, _ in vecs], axis=0)
        victim = min(vecs, key=lambda t: (float(np.linalg.norm(t[1] - centroid)), t[2]))
        conn.execute("DELETE FROM face_gallery WHERE encoding_id = ?", (victim[0],))

    def gallery_size(self, person_id: int) -> int:
        """Number of encodings currently stored for a person."""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                return conn.execute(
                    "SELECT COUNT(*) FROM face_gallery WHERE person_id = ?",
                    (person_id,)).fetchone()[0]
            finally:
                conn.close()
```

- [ ] **Step 5: Rewrite `learn_guest` to reuse person_id and append to the gallery**

Replace the existing `learn_guest` (`face_memory.py:123-136`):

```python
    def learn_guest(self, name: str, encoding: np.ndarray, quality: float = 0.0) -> int:
        """Enroll an encoding for `name`, returning that guest's person_id.

        A name already in the gallery ADDS a view rather than creating a second
        identity — this is what accumulates the multi-view gallery that lets a
        returning guest match from a new angle.
        """
        enc = np.asarray(encoding, dtype=np.float64)
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                row = conn.execute(
                    "SELECT person_id FROM face_encodings WHERE name = ?", (name,)).fetchone()
                if row:
                    person_id = row[0]
                    conn.execute(
                        "UPDATE face_encodings SET last_seen = CURRENT_TIMESTAMP, "
                        "visit_count = visit_count + 1 WHERE person_id = ?", (person_id,))
                else:
                    max_id = conn.execute(
                        "SELECT MAX(person_id) FROM face_encodings").fetchone()[0] or 0
                    person_id = max_id + 1
                    conn.execute(
                        "INSERT INTO face_encodings (person_id, name, encoding) VALUES (?, ?, ?)",
                        (person_id, name, json.dumps(enc.tolist())))
                self._add_encoding(conn, person_id, name, enc, quality)
                conn.commit()
            finally:
                conn.close()

        if DEBUG_FACE:
            logger.info(f"[face_memory] learned {name} (person_id={person_id})")
        return person_id
```

- [ ] **Step 6: Rewrite `find_match` to reduce per person**

Replace the body of `find_match` (`face_memory.py:78-121`):

```python
    def find_match(self, encoding: np.ndarray,
                   tolerance: Optional[float] = None) -> Optional[dict]:
        """Best gallery match via per-person minimum Euclidean distance.

        dlib's 128-dim encodings are Euclidean-native and calibrated at 0.6. Each
        person may hold several encodings (different angles/lighting); a person's
        score is their BEST encoding, so extra views can only help.
        Party scale: 20-50 guests x <=5 encodings = <=250 vectors, well under 1ms.
        """
        tol = tolerance if tolerance is not None else self._tolerance
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                rows = conn.execute("""
                    SELECT g.person_id, g.name, g.encoding, COALESCE(e.visit_count, 1)
                    FROM face_gallery g
                    LEFT JOIN face_encodings e ON e.person_id = g.person_id
                """).fetchall()
            finally:
                conn.close()

        if not rows:
            return None

        best_per_person = {}
        for pid, name, enc_json, visits in rows:
            stored = np.array(json.loads(enc_json), dtype=np.float64)
            distance = float(np.linalg.norm(encoding - stored))
            current = best_per_person.get(pid)
            if current is None or distance < current[0]:
                best_per_person[pid] = (distance, name, visits)

        ranked = sorted(best_per_person.items(), key=lambda kv: kv[1][0])
        person_id, (distance, name, visits) = ranked[0]
        if distance > tol:
            return None

        match = {
            "person_id": person_id,
            "name": name,
            "confidence": max(0.0, 1.0 - distance),
            "visit_count": visits,
        }
        if DEBUG_FACE:
            logger.info(f"[face_memory] match: {name} ({match['confidence']:.3f})")
        return match
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `venv/Scripts/python.exe -m pytest tests/test_face_gallery.py tests/test_face_enrollment.py -v`
Expected: PASS.

Note: `test_second_view_matches_after_gallery_enroll` relies on two random 128-dim vectors being farther apart than 0.6, which holds for `default_rng` vectors in `[0,1)^128` (typical distance ~4.6). If it does not fail-then-pass as expected, the test is wrong, not the implementation — do not loosen the tolerance to make it green.

- [ ] **Step 8: Commit**

```bash
git add server/face_memory.py tests/test_face_gallery.py
git commit -m "feat(recognition): multi-encoding face gallery with diversity eviction

One encoding per person, overwritten on re-store, meant a returning guest at a
new angle blew past the 0.6 tolerance and was missed. Store up to N encodings
per identity, score a person by their best one, and evict the encoding closest
to their centroid so the retained set stays view-diverse.

learn_guest now reuses an existing person_id for a known name instead of minting
a second identity, which is what lets the gallery accumulate at all.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 4: Ambiguity margin checks (W4)

Both matchers take best-under-threshold with no runner-up check, so two similar guests produce a confident wrong name.

**Files:**
- Modify: `server/face_memory.py` (`find_match`)
- Modify: `server/speaker_id.py:163-228` (`identify_speaker`)
- Test: `tests/test_recognition_margin.py`

**Interfaces:**
- Consumes: `recognition_config.get` (Task 2), `find_match`'s `ranked` list (Task 3).
- Produces: no signature changes. `find_match` and `identify_speaker` now return "unknown" (`None` / `is_new=True`) when the top two candidates are too close.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_recognition_margin.py`:

```python
"""Tests for ambiguity margin rejection on both modalities (spec W4)."""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

from face_memory import FaceMemory  # noqa: E402


@pytest.fixture
def mem(tmp_path):
    return FaceMemory(str(tmp_path / "faces.db"))


def test_ambiguous_face_returns_unknown(mem):
    """Two enrolled people almost equidistant from the probe -> refuse to guess."""
    base = np.zeros(128)
    a = base.copy(); a[0] = 0.0
    b = base.copy(); b[0] = 0.40          # probe sits nearly between a and b
    mem.learn_guest("Alice", a)
    mem.learn_guest("Bob", b)
    probe = base.copy(); probe[0] = 0.20   # 0.20 from each -> gap 0.0
    assert mem.find_match(probe) is None


def test_clear_winner_still_matches(mem):
    base = np.zeros(128)
    a = base.copy()
    b = base.copy(); b[0] = 3.0
    mem.learn_guest("Alice", a)
    mem.learn_guest("Bob", b)
    probe = base.copy(); probe[0] = 0.05   # 0.05 from Alice, 2.95 from Bob
    match = mem.find_match(probe)
    assert match is not None and match["name"] == "Alice"


def test_single_person_gallery_unaffected(mem):
    """With one enrolled identity there is no runner-up, so no margin to clear."""
    base = np.zeros(128)
    mem.learn_guest("Alice", base)
    probe = base.copy(); probe[0] = 0.05
    match = mem.find_match(probe)
    assert match is not None and match["name"] == "Alice"


def test_same_person_two_views_are_not_competitors(mem):
    """Two encodings of ONE person must not look like an ambiguous pair."""
    base = np.zeros(128)
    v1 = base.copy()
    v2 = base.copy(); v2[0] = 0.10
    mem.learn_guest("Alice", v1)
    mem.learn_guest("Alice", v2)          # same name -> same person_id
    probe = base.copy(); probe[0] = 0.05
    match = mem.find_match(probe)
    assert match is not None and match["name"] == "Alice"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `venv/Scripts/python.exe -m pytest tests/test_recognition_margin.py -v`
Expected: `test_ambiguous_face_returns_unknown` FAILS (returns Alice or Bob); the other three PASS already.

- [ ] **Step 3: Add the face margin check**

In `server/face_memory.py:find_match`, insert immediately after the `if distance > tol: return None` guard:

```python
        # W4: refuse an ambiguous call. Only DIFFERENT people compete — `ranked` is
        # already reduced to one entry per person, so two views of the same guest
        # can never look like a tie.
        if len(ranked) >= 2:
            runner_up_distance = ranked[1][1][0]
            margin = recognition_config.get("face_match_margin")
            if (runner_up_distance - distance) < margin:
                if DEBUG_FACE:
                    logger.info(f"[face_memory] ambiguous: {name} {distance:.3f} vs "
                                f"runner-up {runner_up_distance:.3f} (margin {margin}) — unknown")
                return None
```

- [ ] **Step 4: Add the voice margin check**

In `server/speaker_id.py`, replace the scan block at `:193-228` (from `best_match = None` through the final `return`):

```python
    best_match = None
    best_similarity = -1.0
    second_similarity = -1.0

    for row_id, name, emb_blob in rows:
        try:
            stored_embedding = np.frombuffer(emb_blob, dtype=np.float32)
            if stored_embedding.shape != embedding.shape:
                logger.warning(f"[DEBUG_SPEAKER] Shape mismatch for {name}: "
                               f"stored={stored_embedding.shape} vs current={embedding.shape}, skipping")
                continue
            norm_product = np.linalg.norm(embedding) * np.linalg.norm(stored_embedding)
            if norm_product == 0:
                continue
            similarity = np.dot(embedding, stored_embedding) / norm_product
        except Exception as e:
            logger.error(f"[DEBUG_SPEAKER] Error comparing embedding for {name}: {e}")
            continue
        if DEBUG_SPEAKER:
            logger.info(f"[DEBUG_SPEAKER] identify_speaker SQLite: {name} similarity={similarity:.3f}")

        if similarity > best_similarity:
            second_similarity = best_similarity
            best_similarity = similarity
            best_match = (row_id, name)
        elif similarity > second_similarity:
            second_similarity = similarity

    if best_match and best_similarity >= SIMILARITY_THRESHOLD:
        # W4: two enrolled voices too close together -> refuse rather than coin-flip.
        margin = recognition_config.get("voice_match_margin")
        if second_similarity >= 0.0 and (best_similarity - second_similarity) < margin:
            if DEBUG_SPEAKER:
                logger.info(f"[DEBUG_SPEAKER] ambiguous: {best_similarity:.3f} vs "
                            f"{second_similarity:.3f} (margin {margin}) — treating as new")
            return {"name": None, "speaker_id": None,
                    "confidence": float(best_similarity), "is_new": True}
        if DEBUG_SPEAKER:
            logger.info(f"[DEBUG_SPEAKER] matched {best_match[1]} ({best_similarity:.3f})")
        return {
            "name": best_match[1],
            "speaker_id": best_match[0],
            "confidence": float(best_similarity),
            "is_new": False,
        }

    if DEBUG_SPEAKER:
        logger.info(f"[DEBUG_SPEAKER] identify_speaker: no match (best={best_similarity:.3f})")
    return {"name": None, "speaker_id": None, "confidence": float(best_similarity), "is_new": True}
```

Add `import recognition_config` to the imports at the top of `server/speaker_id.py`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `venv/Scripts/python.exe -m pytest tests/test_recognition_margin.py tests/test_face_gallery.py tests/test_speaker_audio_gate.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add server/face_memory.py server/speaker_id.py tests/test_recognition_margin.py
git commit -m "feat(recognition): reject ambiguous matches on both modalities

Both matchers took best-under-threshold with no runner-up check, so two guests
with similar embeddings produced a confident wrong name. Require the best
candidate to beat the runner-up FROM A DIFFERENT PERSON by a margin, else return
unknown and let fusion handle it.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 5: Enrollment quality gate (W3)

Stops a blurry, tiny, or profile frame becoming a guest's stored reference. Scored on the client, enforced on the server, because `_encode_face` cannot tell matching from enrollment.

**Files:**
- Modify: `client/person_detector.py` (`DetectedPerson`, `_encode_face`, `detect_people`)
- Modify: `client/main.py:784-789`
- Modify: `server/face_enrollment.py` (`resolve_faces`)
- Test: `tests/test_face_quality.py`

**Interfaces:**
- Consumes: `resolve_faces` (Task 1), `learn_guest(name, encoding, quality)` (Task 3), `recognition_config.get` (Task 2).
- Produces: `person_detector.face_quality(rgb_crop, face_location, min_box_px, min_sharpness) -> float` in `[0.0, 1.0]`. `DetectedPerson.face_quality` attribute. `person_detected` face entries carry a `quality` key.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_face_quality.py`:

```python
"""Tests for the enrollment quality gate (spec W3)."""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "client"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

import face_enrollment  # noqa: E402

cv2 = pytest.importorskip("cv2")
from person_detector import face_quality  # noqa: E402


def _sharp_crop(size=200):
    """High-frequency checkerboard -> high laplacian variance."""
    img = np.zeros((size, size, 3), dtype=np.uint8)
    img[::2, ::2] = 255
    img[1::2, 1::2] = 255
    return img


def test_good_face_scores_high():
    crop = _sharp_crop(200)
    q = face_quality(crop, (10, 190, 190, 10), min_box_px=80, min_sharpness=40.0)
    assert q >= 0.5


def test_small_face_scores_low():
    crop = _sharp_crop(200)
    q = face_quality(crop, (10, 50, 50, 10), min_box_px=80, min_sharpness=40.0)
    assert q < 0.5


def test_blurry_face_scores_low():
    crop = np.full((200, 200, 3), 128, dtype=np.uint8)   # flat -> zero variance
    q = face_quality(crop, (10, 190, 190, 10), min_box_px=80, min_sharpness=40.0)
    assert q < 0.5


def test_extreme_aspect_scores_zero():
    crop = _sharp_crop(200)
    q = face_quality(crop, (10, 190, 40, 10), min_box_px=10, min_sharpness=1.0)
    assert q == 0.0


class _RecordingMemory:
    def __init__(self):
        self.learned = []

    def find_match(self, encoding, tolerance=None):
        return None

    def learn_guest(self, name, encoding, quality=0.0):
        self.learned.append((name, quality))
        return 1


def _enc(seed):
    return np.random.default_rng(seed).random(128).tolist()


def test_low_quality_face_is_not_enrolled():
    mem = _RecordingMemory()
    face_enrollment.resolve_faces([{"encoding": _enc(1), "quality": 0.1}], mem, "Jacob")
    assert mem.learned == []


def test_high_quality_face_is_enrolled():
    mem = _RecordingMemory()
    face_enrollment.resolve_faces([{"encoding": _enc(1), "quality": 0.9}], mem, "Jacob")
    assert len(mem.learned) == 1


def test_missing_quality_key_defaults_to_enrollable():
    """Older clients send no quality — must not silently stop enrolling."""
    mem = _RecordingMemory()
    face_enrollment.resolve_faces([{"encoding": _enc(1)}], mem, "Jacob")
    assert len(mem.learned) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `venv/Scripts/python.exe -m pytest tests/test_face_quality.py -v`
Expected: FAIL with `ImportError: cannot import name 'face_quality'`.

- [ ] **Step 3: Add `face_quality` to the detector**

In `client/person_detector.py`, add after the `DetectedPerson` class:

```python
def face_quality(rgb_crop: np.ndarray, face_location: tuple,
                 min_box_px: int = 80, min_sharpness: float = 40.0) -> float:
    """Score a detected face 0.0-1.0 for ENROLLMENT suitability.

    Combines three cheap checks and takes the worst: box size, blur (laplacian
    variance), and aspect ratio as a near-profile proxy. Matching ignores this
    score entirely — recognizing a guest from a mediocre frame is desirable,
    storing that frame as their reference is not.
    """
    try:
        top, right, bottom, left = face_location
        height, width = bottom - top, right - left
        if height <= 0 or width <= 0:
            return 0.0

        size_score = min(1.0, min(height, width) / float(min_box_px))

        ratio = width / float(height)
        aspect_score = 1.0 if 0.6 <= ratio <= 1.7 else 0.0

        face_img = rgb_crop[max(0, top):bottom, max(0, left):right]
        if face_img.size == 0:
            return 0.0
        gray = cv2.cvtColor(face_img, cv2.COLOR_RGB2GRAY)
        lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        sharp_score = min(1.0, lap_var / float(min_sharpness))

        return float(min(size_score, aspect_score, sharp_score))
    except Exception as e:
        logger.debug(f"[person_detector] quality scoring failed: {e}")
        return 0.0
```

- [ ] **Step 4: Carry the score through the detector**

In `client/person_detector.py`, add `"face_quality"` to `DetectedPerson.__slots__` and to `__init__`:

```python
class DetectedPerson:
    """A person detected in a frame."""
    __slots__ = ("bbox", "confidence", "face_encoding", "face_location", "face_quality")

    def __init__(self, bbox: tuple, confidence: float,
                 face_encoding: Optional[np.ndarray] = None,
                 face_location: Optional[tuple] = None,
                 face_quality: float = 0.0):
        self.bbox = bbox  # (x1, y1, x2, y2)
        self.confidence = confidence
        self.face_encoding = face_encoding  # 128-dim or None
        self.face_location = face_location
        self.face_quality = face_quality
```

Change `_encode_face` to return a `(encoding, quality)` pair — replace its `if encodings:` block:

```python
            encodings = face_rec.face_encodings(rgb_crop, face_locations)
            if encodings:
                quality = face_quality(
                    rgb_crop, face_locations[0],
                    min_box_px=self.min_box_px, min_sharpness=self.min_sharpness)
                return encodings[0], quality      # 128-dim numpy array, 0.0-1.0
            return None, 0.0
```

Change the two other `return None` statements inside `_encode_face` to `return None, 0.0`, and update its docstring/signature line to:

```python
    def _encode_face(self, frame: np.ndarray, bbox: tuple) -> tuple:
        """Extract (128-dim face encoding, quality score) from a person bounding box."""
```

In `detect_people`, update the call site:

```python
                    # Try face encoding
                    if _face_rec_available:
                        person.face_encoding, person.face_quality = self._encode_face(frame, person.bbox)
```

Add the two thresholds to `PersonDetector.__init__`, after `self.frame_skip` is set:

```python
        # W3: enrollment quality thresholds (env-overridable for field tuning)
        self.min_box_px = int(os.environ.get("FACE_MIN_BOX_PX", "80"))
        self.min_sharpness = float(os.environ.get("FACE_MIN_SHARPNESS", "40.0"))
```

- [ ] **Step 5: Send the score to the server**

In `client/main.py:784-789`, replace the face entry construction:

```python
            faces = []
            for person in people:
                face_entry = {"confidence": person.confidence}
                if person.face_encoding is not None:
                    face_entry["encoding"] = person.face_encoding.tolist()
                    face_entry["quality"] = float(getattr(person, "face_quality", 1.0))
                faces.append(face_entry)
```

- [ ] **Step 6: Enforce the gate server-side**

In `server/face_enrollment.py`, add `import recognition_config` at the top, then change the unknown-face collection in `resolve_faces` to carry quality. Replace the `else:` branch of the match check:

```python
        else:
            unknown.append((enc, float(face_data.get("quality", 1.0))))
```

and replace the single-unknown decision block. **Preserve the `new_face_count` semantics Task 1 delivered** — 0 when the face was enrolled (it is no longer "new"), 1 when it was stashed or rejected, `len(unknown)` when ambiguous. Those values feed the group greeting and the `recognition_events` stream in `main.py`, and a pre-existing test asserts the enrolled case is 0:

```python
    if len(unknown) == 1:
        enc, quality = unknown[0]
        min_quality = recognition_config.get("face_min_quality")
        if quality < min_quality:
            # Too blurry / small / off-angle to become someone's stored reference.
            # Still counted as new so the greeting logic is unaffected.
            new_face_count = 1
        elif speaker_name:
            # Exactly one unknown face and we know who is talking -> safe to bind.
            if face_memory is not None:
                face_memory.learn_guest(speaker_name, enc, quality)
            detected.append({"name": speaker_name, "person_id": None,
                             "visit_count": None, "confidence": None})
            # Face was enrolled, so it is not "new" anymore.
            new_face_count = 0
        else:
            # Nobody identified yet -> remember it until a name arrives.
            pending_encoding = enc
            new_face_count = 1
    else:
        # Multiple unknowns (or none): count them as new, unenrolled faces.
        new_face_count = len(unknown)
```

- [ ] **Step 7: Update the existing test double for the new signature**

`resolve_faces` now calls `learn_guest` with three arguments, but `FakeFaceMemory` in `tests/test_face_enrollment.py` accepts two and will raise `TypeError`. Update it to match the real `FaceMemory.learn_guest` from Task 3:

```python
    def learn_guest(self, name, encoding, quality=0.0):
        self.learned.append((name, np.asarray(encoding)))
        return 1
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `venv/Scripts/python.exe -m pytest tests/test_face_quality.py tests/test_face_enrollment.py tests/test_person_detector_config.py -v`
Expected: PASS. If `test_person_detector_config.py` fails on the `_encode_face` return shape, update that test to unpack the pair — the new signature is intended.

- [ ] **Step 9: Commit**

```bash
git add client/person_detector.py client/main.py server/face_enrollment.py tests/test_face_quality.py tests/test_face_enrollment.py
git commit -m "feat(recognition): quality-gate face enrollment

_encode_face serves both matching and enrollment and cannot tell them apart, so
the client now SCORES each face (box size, laplacian blur, aspect) without
rejecting, and the server enforces a floor on the enrollment branch only.
Matching still accepts mediocre frames; only stored references must be clean.

A missing quality key is treated as 1.0 so an older client never silently stops
enrolling.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 6: Tier-aware detector and adaptive frame skip (W5)

HOG is weak on the non-frontal, low-light, motion-blurred faces a doorway produces. The party box can afford CNN; the dev box cannot.

**Files:**
- Modify: `client/person_detector.py` (module helper, `__init__`, `detect_people`)
- Test: `tests/test_person_detector_config.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `person_detector.resolve_detector_model(tier: str, env_override: str | None) -> str`, and `PersonDetector(..., hardware_tier: str | None)`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_person_detector_config.py`:

```python
def test_ultra_tier_selects_cnn():
    from person_detector import resolve_detector_model
    assert resolve_detector_model("ultra", None) == "cnn"


def test_high_tier_selects_cnn():
    from person_detector import resolve_detector_model
    assert resolve_detector_model("high", None) == "cnn"


def test_low_tier_selects_hog():
    from person_detector import resolve_detector_model
    assert resolve_detector_model("low", None) == "hog"


def test_medium_tier_selects_hog():
    from person_detector import resolve_detector_model
    assert resolve_detector_model("medium", None) == "hog"


def test_env_override_wins_over_tier():
    from person_detector import resolve_detector_model
    assert resolve_detector_model("ultra", "hog") == "hog"


def test_unknown_tier_falls_back_to_hog():
    from person_detector import resolve_detector_model
    assert resolve_detector_model("banana", None) == "hog"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `venv/Scripts/python.exe -m pytest tests/test_person_detector_config.py -v -k tier`
Expected: FAIL with `ImportError: cannot import name 'resolve_detector_model'`.

- [ ] **Step 3: Add tier resolution**

In `client/person_detector.py`, add after the optional-import block:

```python
# Tiers that can afford the GPU-backed CNN face detector. `hardware.get_tier()`
# returns ultra/high/medium/low (four tiers, lowercase). The party box (24GB VRAM,
# 256GB RAM, 64 cores) resolves to "ultra"; the P1000 dev box resolves to "low".
_CNN_TIERS = ("ultra", "high")


def resolve_detector_model(tier: str, env_override: Optional[str] = None) -> str:
    """Pick the dlib face detector for a hardware tier. Env override always wins."""
    if env_override:
        return env_override
    return "cnn" if tier in _CNN_TIERS else "hog"


def _detect_tier() -> str:
    """Best-effort hardware tier. The client may not have server/ importable."""
    try:
        import sys as _sys
        _server_dir = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "server")
        if _server_dir not in _sys.path:
            _sys.path.insert(0, _server_dir)
        from hardware import get_tier
        return get_tier()
    except Exception:
        return "low"
```

- [ ] **Step 4: Use it in `__init__` and add adaptive skip state**

In `PersonDetector.__init__`, add `hardware_tier: str = None` to the signature and replace the `self.face_detector_model = ...` line:

```python
        self.hardware_tier = hardware_tier or _detect_tier()
        self.face_detector_model = face_detector_model or resolve_detector_model(
            self.hardware_tier, os.environ.get("FACE_DETECTOR_MODEL"))
```

Add adaptive-skip state alongside the other init fields:

```python
        # W5: run every frame while someone is at the door, back off when idle.
        self._last_person_ts = 0.0
        self.person_active_window = float(os.environ.get("PERSON_ACTIVE_WINDOW", "2.0"))
```

- [ ] **Step 5: Apply adaptive skip in `detect_people`**

Replace the frame-skip block at the top of `detect_people`:

```python
        # W5: while a person was seen recently, examine every frame — more chances
        # at a good frontal capture. Fall back to the idle cadence after the window.
        now = time.time()
        effective_skip = 1 if (now - self._last_person_ts) < self.person_active_window \
            else self.frame_skip
        self._frame_count += 1
        if effective_skip > 1 and self._frame_count % effective_skip != 0:
            return []
```

and record detections just before `return people`:

```python
            if people:
                self._last_person_ts = now
            return people
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `venv/Scripts/python.exe -m pytest tests/test_person_detector_config.py tests/test_face_quality.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add client/person_detector.py tests/test_person_detector_config.py
git commit -m "feat(recognition): tier-aware face detector and adaptive frame skip

HOG is weak on exactly the faces a doorway produces. Select CNN on ultra/high
tiers (the 3090 Ti party box) and keep HOG on medium/low (the P1000 dev box),
with the existing FACE_DETECTOR_MODEL env override still winning.

Frame skip drops to 1 while a person is present so there are more chances at a
good frontal frame, reverting to the idle cadence after 2s.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 7: Two-stage voice consistency gate (W6)

A chunk holding two speakers, or speech over loud music, yields a blended meaningless embedding that the open-set gate then has to clean up.

**Files:**
- Modify: `server/speaker_id.py` (`get_embedding`, new helpers)
- Test: `tests/test_voice_consistency.py`

**Interfaces:**
- Consumes: `recognition_config.get` (Task 2).
- Produces: `speaker_id.spectral_flatness(samples) -> float`, `speaker_id.stage_a_ok(samples_int16) -> bool`. `get_embedding` returns `None` for rejected chunks, which every existing caller already handles.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_voice_consistency.py`:

```python
"""Tests for the two-stage voice consistency gate (spec W6)."""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

import speaker_id  # noqa: E402

RATE = 16000


def _tone(freq, seconds=3.0, amp=8000):
    t = np.arange(int(RATE * seconds)) / RATE
    return (amp * np.sin(2 * np.pi * freq * t)).astype(np.int16)


def _white_noise(seconds=3.0, amp=8000):
    return (np.random.default_rng(7).normal(0, amp, int(RATE * seconds))).astype(np.int16)


def test_spectral_flatness_noise_is_high():
    assert speaker_id.spectral_flatness(_white_noise().astype(np.float64)) > 0.4


def test_spectral_flatness_tone_is_low():
    assert speaker_id.spectral_flatness(_tone(220).astype(np.float64)) < 0.1


def test_stage_a_rejects_white_noise():
    assert speaker_id.stage_a_ok(_white_noise()) is False


def test_stage_a_accepts_tonal_signal():
    assert speaker_id.stage_a_ok(_tone(220)) is True


def test_stage_a_rejects_mostly_silent_chunk():
    chunk = _tone(220)
    chunk[len(chunk) // 3:] = 0          # only the first third has energy
    assert speaker_id.stage_a_ok(chunk) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `venv/Scripts/python.exe -m pytest tests/test_voice_consistency.py -v`
Expected: FAIL with `AttributeError: module 'speaker_id' has no attribute 'spectral_flatness'`.

- [ ] **Step 3: Add the Stage A helpers**

In `server/speaker_id.py`, add after `_has_speech_energy`:

```python
def spectral_flatness(samples: np.ndarray) -> float:
    """Wiener entropy: geometric mean / arithmetic mean of the magnitude spectrum.

    Near 1.0 for noise-like signals (white noise, room hiss, dense music), low for
    the peaky harmonic structure of speech. Costs one FFT and no embedding.
    """
    if samples is None or samples.size == 0:
        return 1.0
    windowed = samples.astype(np.float64) * np.hanning(len(samples))
    spectrum = np.abs(np.fft.rfft(windowed))
    spectrum = spectrum[spectrum > 1e-10]
    if spectrum.size == 0:
        return 1.0
    geometric = np.exp(np.mean(np.log(spectrum)))
    arithmetic = np.mean(spectrum)
    return float(geometric / arithmetic) if arithmetic > 0 else 1.0


def stage_a_ok(samples_int16: np.ndarray, min_rms: float = None,
               max_flatness: float = None) -> bool:
    """Cheap pre-embedding gate: enough speech energy, not noise-like.

    Splits the chunk into 3 windows. Requires at least 2 of 3 above the speech
    energy floor (rejects mostly-silent chunks) and a mean spectral flatness under
    the ceiling (rejects music and room noise). No embedding cost.
    """
    if samples_int16 is None or len(samples_int16) < 3:
        return False
    if max_flatness is None:
        max_flatness = recognition_config.get("voice_max_flatness")
    floor = MIN_SPEECH_RMS if min_rms is None else min_rms

    third = len(samples_int16) // 3
    windows = [samples_int16[i * third:(i + 1) * third] for i in range(3)]

    loud = 0
    for window in windows:
        vals = window.astype(np.float64)
        if vals.size and float(np.sqrt(np.mean(vals * vals))) >= floor:
            loud += 1
    if loud < 2:
        return False

    mean_flatness = float(np.mean([spectral_flatness(w.astype(np.float64)) for w in windows]))
    return mean_flatness <= max_flatness
```

Add `import recognition_config` to the imports at the top of `server/speaker_id.py` if Task 4 has not already added it.

- [ ] **Step 4: Run Stage A tests to verify they pass**

Run: `venv/Scripts/python.exe -m pytest tests/test_voice_consistency.py -v`
Expected: PASS, 5 tests.

- [ ] **Step 5: Wire both stages into `get_embedding`**

In `server/speaker_id.py:get_embedding`, replace the body between the RMS gate and `embedding = _encoder.embed_utterance(processed)`:

```python
    audio_np = np.frombuffer(audio_data, dtype=np.int16)

    # Stage A (W6): no embedding cost — reject noise/music/mostly-silence outright.
    if not stage_a_ok(audio_np):
        if DEBUG_SPEAKER:
            logger.info("[DEBUG_SPEAKER] get_embedding: rejected by stage A (energy/flatness)")
        return None

    processed = preprocess_wav(audio_np.astype(np.float32) / 32768.0, source_sr=sample_rate)

    if len(processed) < sample_rate * 1.0:
        if DEBUG_SPEAKER:
            logger.info("[DEBUG_SPEAKER] get_embedding: audio too short for embedding")
        return None

    # Stage B (W6): two extra CPU embeddings. Halves, not thirds — resemblyzer's
    # partial-utterance window is 1.6s, so 1.0s thirds would be zero-padded and
    # noisy. Disagreement between halves means two speakers or heavy interference.
    half = len(processed) // 2
    first, second = processed[:half], processed[half:]
    if min(len(first), len(second)) >= sample_rate * 1.0:
        emb_a = _encoder.embed_utterance(first)
        emb_b = _encoder.embed_utterance(second)
        denominator = np.linalg.norm(emb_a) * np.linalg.norm(emb_b)
        if denominator > 0:
            agreement = float(np.dot(emb_a, emb_b) / denominator)
            tau = recognition_config.get("voice_consistency_tau")
            if agreement < tau:
                if DEBUG_SPEAKER:
                    logger.info(f"[DEBUG_SPEAKER] get_embedding: rejected by stage B "
                                f"(agreement {agreement:.3f} < {tau})")
                return None

    embedding = _encoder.embed_utterance(processed)
```

- [ ] **Step 6: Run the voice suite**

Run: `venv/Scripts/python.exe -m pytest tests/test_voice_consistency.py tests/test_speaker_audio_gate.py tests/test_speaker_enroll_multi.py tests/test_recognition_margin.py -v`
Expected: PASS. `get_embedding` returning `None` on a rejected chunk is already the contract every caller handles.

- [ ] **Step 7: Commit**

```bash
git add server/speaker_id.py tests/test_voice_consistency.py
git commit -m "feat(recognition): two-stage voice consistency gate

A chunk holding two speakers or speech over music blends into a meaningless
embedding that the open-set gate then has to reject downstream.

Stage A costs one FFT: require 2 of 3 sub-windows above the speech floor and a
mean spectral flatness under the noise ceiling. Stage B runs only if A passes and
spends two CPU embeddings comparing the chunk's halves — disagreement means more
than one voice. Both stay off the GPU.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 8: Lab extension and threshold tuning (W8)

Unit tests cannot show a match-rate delta. The lab is the acceptance instrument for Tasks 3, 4, 5 and 7, and the source of every threshold that currently ships as a guess.

**Files:**
- Modify: `tests/recognition_lab/run_recognition_test.py`
- Modify: `tests/recognition_lab/results.json` (regenerated output)
- Modify: `docs/superpowers/specs/2026-07-22-recognition-reliability-design.md` (record measured values)

**Interfaces:**
- Consumes: everything from Tasks 1–7.
- Produces: `results.json` gaining `baseline` and `after` blocks plus a `tuned_thresholds` object.

- [ ] **Step 1: Confirm the baseline exists**

Run: `venv/Scripts/python.exe -c "import json;d=json.load(open('tests/recognition_lab/results_baseline.json',encoding='utf-8'));print(sorted(d))"`
Expected: prints the baseline's top-level keys.

If the file is missing, Task 0 was skipped. Recover it by running the lab in a clean worktree of `master` (`git worktree add ../mario-baseline master`) rather than guessing, then continue.

- [ ] **Step 2: Add shared helpers and a multi-speaker mix generator**

The existing lab helpers return *file paths*, not signals: `voice_block(p, source)` returns `(enroll_files: list, probe_files: list)`, and `person["faces"]` is a list of dicts shaped `{"file", "role", "encodes"}`. Load audio with the existing `load_float(path)` and resolve paths with the existing `abspath(rel)`.

In `tests/recognition_lab/run_recognition_test.py`, add alongside the existing `mix_party` helper:

```python
def tmp_db(*parts):
    """Fresh scratch SQLite path under the lab dir (removed if it already exists)."""
    path = os.path.join(HERE, "_tmp", "_".join(str(p) for p in parts) + ".db")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path):
        os.remove(path)
    return path


def face_files(person, role=None):
    """Absolute paths of a person's encodable face images, optionally by role."""
    return [abspath(f["file"]) for f in person.get("faces", [])
            if f.get("encodes") and (role is None or f.get("role") == role)]


def probe_signal(person, source, index=0):
    """Load one probe utterance for a person as a float signal."""
    _enroll_files, probe_files = voice_block(person, source)
    return load_float(abspath(probe_files[index]))


def mix_two_speakers(sig_a, sig_b, ratio_db=0.0):
    """Overlap two speakers at a given level ratio — the chunk Stage B must reject."""
    n = min(len(sig_a), len(sig_b))
    a, b = sig_a[:n], sig_b[:n]
    gain = 10 ** (ratio_db / 20.0)
    mixed = a + gain * b * (rms(a) / max(rms(b), 1e-9))
    peak = np.max(np.abs(mixed))
    return mixed / peak * 0.95 if peak > 0 else mixed
```

- [ ] **Step 3a: Add a public config override for tuning**

The sweeps need to vary a tunable at runtime. Reaching into `recognition_config._cache` from the lab would couple it to a private attribute, so add a small public API to `server/recognition_config.py` instead:

```python
def override(name: str, value):
    """Force a tunable to `value` for the current process (tuning sweeps, tests).

    Raises KeyError for an unknown tunable, same as get().
    """
    values = _load()
    if name not in values:
        raise KeyError(f"unknown recognition tunable: {name}")
    values[name] = value


def clear_overrides():
    """Drop all overrides and re-read from config on next access."""
    reset_cache()
```

Add a test to `tests/test_recognition_config.py` covering both — an override changes what `get` returns, `clear_overrides` restores the default, and an unknown name raises `KeyError`.

- [ ] **Step 3b: Add the Stage A flatness sweep**

**This is the highest-priority measurement in the task.** Task 7 found that the shipped `voice_max_flatness` of 0.45 false-rejects roughly 28% of genuine solo speech: real speech measures 0.45–0.57, overlapping the ceiling. A reviewer confirmed the flatness formula itself is mathematically correct, so the default is simply mis-calibrated. Left unchanged, Stage A silently discards a quarter of real voice input and voice ID regresses badly.

Sweep it against real speech (must pass) and party noise (must reject):

```python
def stage_a_flatness_sweep(speaker_id, people, source, noise_bed):
    """Choose voice_max_flatness from measured curves.

    Reports, per candidate ceiling, the fraction of genuine solo-speech chunks kept
    and the fraction of pure-noise chunks correctly rejected. Stage A costs no
    embedding, so this sweep is cheap.
    """
    import recognition_config
    speech = [probe_signal(p, source) for p in people]
    noise = [noise_bed[:len(speech[0])] for _ in people]

    out = {}
    for ceiling in (0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.80):
        recognition_config.override("voice_max_flatness", ceiling)
        kept = sum(1 for s in speech if speaker_id.stage_a_ok(to_pcm16(s)))
        rejected = sum(1 for n in noise if not speaker_id.stage_a_ok(to_pcm16(n)))
        out[f"{ceiling:.2f}"] = {
            "speech_kept": kept / max(len(speech), 1),
            "noise_rejected": rejected / max(len(noise), 1),
        }
    recognition_config.clear_overrides()
    return out
```

- [ ] **Step 3c: Add the Stage B sweep**

Sweeps `voice_consistency_tau` against single-speaker (must pass) and two-speaker (must reject) chunks. Run this AFTER choosing the flatness ceiling, and set the chosen ceiling first — otherwise Stage A rejects a quarter of the singles before Stage B sees them and the tau curve is measured on a biased sample:

```python
def stage_b_sweep(speaker_id, people, source, chosen_flatness):
    """Pick tau from measured curves rather than assumption.

    Reports, per candidate tau, the fraction of genuine single-speaker chunks kept
    and the fraction of two-speaker chunks correctly rejected.
    """
    import recognition_config
    singles = [probe_signal(p, source) for p in people]
    doubles = [mix_two_speakers(probe_signal(people[i], source),
                                probe_signal(people[(i + 1) % len(people)], source))
               for i in range(len(people))]

    out = {}
    for tau in (0.50, 0.55, 0.60, 0.65, 0.70, 0.75):
        recognition_config.override("voice_max_flatness", chosen_flatness)
        recognition_config.override("voice_consistency_tau", tau)

        kept = sum(1 for s in singles
                   if speaker_id.get_embedding(to_pcm16(s).tobytes()) is not None)
        rejected = sum(1 for d in doubles
                       if speaker_id.get_embedding(to_pcm16(d).tobytes()) is None)
        out[f"{tau:.2f}"] = {
            "single_kept": kept / max(len(singles), 1),
            "double_rejected": rejected / max(len(doubles), 1),
        }
    recognition_config.clear_overrides()
    return out
```

- [ ] **Step 4: Add the face gallery and margin sweeps**

```python
def _person_views(person):
    """Encoded face views for a person, skipping images dlib cannot encode."""
    return [e for e in (face_encoding(p) for p in face_files(person)) if e is not None]


def gallery_gain(FaceMemory, people):
    """Cross-view match rate with a single encoding vs the multi-view gallery."""
    single_hits = 0
    gallery_hits = 0
    eligible = 0
    for person in people:
        views = _person_views(person)
        if len(views) < 2:
            continue
        eligible += 1

        mem_single = FaceMemory(tmp_db("single", person["slug"]))
        mem_single.learn_guest(person["name"], views[0])
        single_hits += 1 if mem_single.find_match(views[-1]) else 0

        mem_gallery = FaceMemory(tmp_db("gallery", person["slug"]))
        for view in views[:-1]:
            mem_gallery.learn_guest(person["name"], view)
        gallery_hits += 1 if mem_gallery.find_match(views[-1]) else 0

    return {"single_encoding": single_hits / max(eligible, 1),
            "multi_encoding": gallery_hits / max(eligible, 1),
            "eligible_people": eligible}


def margin_sweep(FaceMemory, people):
    """True-accept vs false-accept as face_match_margin varies. Pick the knee."""
    import recognition_config
    views_by_person = {p["slug"]: _person_views(p) for p in people}
    eligible = [p for p in people if len(views_by_person[p["slug"]]) >= 2]

    out = {}
    for margin in (0.00, 0.03, 0.05, 0.08, 0.12):
        recognition_config.override("face_match_margin", margin)

        mem = FaceMemory(tmp_db("margin", f"{margin:.2f}".replace(".", "")))
        for person in people:
            views = views_by_person[person["slug"]]
            if views:
                mem.learn_guest(person["name"], views[0])

        true_accept = 0
        false_accept = 0
        for person in eligible:
            probe = views_by_person[person["slug"]][-1]
            got = (mem.find_match(probe) or {}).get("name")
            if got == person["name"]:
                true_accept += 1
            elif got is not None:
                false_accept += 1

        denominator = max(len(eligible), 1)
        out[f"{margin:.2f}"] = {"true_accept": true_accept / denominator,
                                "false_accept": false_accept / denominator}
    recognition_config.clear_overrides()
    return out
```

- [ ] **Step 5: Add the group-enrollment scenario**

```python
def group_enrollment_check(face_enrollment, FaceMemory, people):
    """W1 end-to-end: 1 unknown face enrolls, 2+ enroll nobody."""
    encs = []
    for person in people:
        views = _person_views(person)
        if views:
            encs.append(views[0])
        if len(encs) == 3:
            break
    if len(encs) < 3:
        return {"skipped": "need 3 encodable people"}

    mem_one = FaceMemory(tmp_db("group", "one"))
    face_enrollment.resolve_faces([{"encoding": encs[0].tolist(), "quality": 1.0}],
                                  mem_one, "Jacob")

    mem_many = FaceMemory(tmp_db("group", "many"))
    face_enrollment.resolve_faces([{"encoding": e.tolist(), "quality": 1.0} for e in encs],
                                  mem_many, "Jacob")

    return {
        "single_unknown_enrolled": mem_one.find_match(encs[0]) is not None,
        "group_enrolled_nobody": all(mem_many.find_match(e) is None for e in encs),
    }
```

- [ ] **Step 6: Call the new blocks from `main()` and widen `results.json`**

In `main()`, after the existing voice/face/fusion measurements, add the new sections and write both blocks:

Import the two server modules the new blocks need at the top of `main()` (the lab already puts `server/` on `sys.path` for `speaker_id`):

```python
    from face_memory import FaceMemory
    import face_enrollment

    results["stage_a_flatness_sweep"] = stage_a_flatness_sweep(
        speaker_id, people, source, noise_bed)
    chosen_flatness = pick_flatness_ceiling(results["stage_a_flatness_sweep"])
    results["chosen_flatness"] = chosen_flatness
    results["stage_b_sweep"] = stage_b_sweep(speaker_id, people, source, chosen_flatness)
    results["gallery_gain"] = gallery_gain(FaceMemory, people)
    results["margin_sweep"] = margin_sweep(FaceMemory, people)
    results["group_enrollment"] = group_enrollment_check(face_enrollment, FaceMemory, people)
```

`noise_bed` is the party-noise signal the existing lab already loads for its SNR mixing — reuse it rather than loading a second copy. `pick_flatness_ceiling` selects the lowest ceiling that keeps at least 95% of real speech while still rejecting at least 80% of pure noise:

```python
def pick_flatness_ceiling(sweep, min_speech_kept=0.95, min_noise_rejected=0.80):
    """Lowest ceiling meeting both targets; None if no candidate does."""
    for ceiling in sorted(sweep, key=float):
        row = sweep[ceiling]
        if row["speech_kept"] >= min_speech_kept and row["noise_rejected"] >= min_noise_rejected:
            return float(ceiling)
    return None
```

- [ ] **Step 7: Run the lab and record the numbers**

Run: `venv/Scripts/python.exe tests/recognition_lab/run_recognition_test.py`
Expected: completes and rewrites `tests/recognition_lab/results.json` with the new sections.

Then verify against the spec's acceptance criteria:
- `group_enrollment.single_unknown_enrolled` is `true` and `group_enrollment.group_enrolled_nobody` is `true` (Task 1).
- `gallery_gain.multi_encoding` exceeds `gallery_gain.single_encoding` (Task 3).
- **`chosen_flatness` is not `None`** — some ceiling keeps ≥95% of real speech while rejecting ≥80% of pure noise (Task 7's 28%-false-reject finding).
- Some tau in `stage_b_sweep` reaches `double_rejected >= 0.80` while `single_kept >= 0.95` (Task 7 target: reject 80% of two-speaker chunks, false-reject at most 5% of genuine ones).
- `margin_sweep` shows a margin where `false_accept` drops without `true_accept` collapsing (Task 4).

If `chosen_flatness` comes back `None`, no ceiling separates speech from noise on this metric. Do NOT relax the targets to manufacture a pass. Report it, and set `voice_max_flatness` to a value that keeps ≥99% of speech (effectively disabling Stage A's flatness test while leaving its energy test intact) — Stage B is the load-bearing half of the gate and had zero false rejects in Task 7's probe.

- [ ] **Step 8: Set the tuned thresholds**

Update `DEFAULTS` in `server/recognition_config.py` to the values the sweeps chose, and add a `tuned_thresholds` block to `results.json` recording which measurement justified each. If a sweep shows the shipped default was already the knee, say so explicitly rather than silently leaving it.

If no tau satisfies both Stage B criteria, do NOT relax the criteria — report it, and disable Stage B by setting `voice_consistency_tau` to `0.0` (which accepts everything) pending a redesign. Stage A stands on its own.

- [ ] **Step 9: Record results in the spec**

Add a "Measured results" section to `docs/superpowers/specs/2026-07-22-recognition-reliability-design.md` with the before/after table, so the numbers live in the repo rather than a chat log.

- [ ] **Step 10: Commit**

```bash
git add tests/recognition_lab/run_recognition_test.py tests/recognition_lab/results.json tests/recognition_lab/results_baseline.json server/recognition_config.py docs/superpowers/specs/2026-07-22-recognition-reliability-design.md
git commit -m "test(recognition): extend lab and tune thresholds from measured curves

Adds multi-speaker mixes, a Stage B tau sweep, a gallery cross-view gain
measurement, a face margin sweep, and an end-to-end group-enrollment check.
Thresholds that shipped as guesses are replaced with the knee of a measured
curve, and the baseline is kept alongside so the delta stays checkable.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 9: Full-suite regression and live verification

**Files:**
- Test: entire `tests/` suite
- Manual: running server + client

**Interfaces:**
- Consumes: Tasks 1–8.
- Produces: nothing — this is the gate before merge.

- [ ] **Step 1: Run the full suite**

Run: `venv/Scripts/python.exe -m pytest tests/ -q`
Expected: no NEW failures versus a `master` baseline. A fresh worktree without `config.json` fails roughly 28 tests for that reason alone — compare failing sets, do not assume every red test is a regression.

- [ ] **Step 2: Back up the party database before any migrated run**

```bash
cp server/data/memory.db server/data/memory.db.pre-gallery-backup
```

- [ ] **Step 3: Start the server and client and confirm the migration ran clean**

Launch via the venv python directly rather than `start_server.bat` (more reliable for a scripted test), then check the log for the migration line and no schema errors.

- [ ] **Step 4: Live-verify a full enrollment and recognition cycle**

Per `.claude/rules/testing.md`, a test is not complete until audio is confirmed. Walk the loop:
1. Show an unknown face → Mario asks "Who are you?"
2. Answer with a name → confirm enrollment in `memory.db.face_gallery`
3. Leave and return → confirm the greeting names the guest

For each spoken response, confirm in `logs/<DATE>/client.log`:
- `mario says:` line matches the speech bubble
- `received audio: NNNNN bytes`
- `_play_wav: playing` AND `_play_wav: done`

- [ ] **Step 5: Confirm the fail-closed path in the real system**

With two people in frame at once, confirm the log shows `enrollment deferred (fail-closed)` and that `face_gallery` gained no rows.

- [ ] **Step 6: Commit any fixes, then finish the branch**

Use the `superpowers:finishing-a-development-branch` skill to decide merge vs PR.

---

## Notes for the implementer

- **Order matters.** Task 2 (config) precedes every task that reads a threshold. Task 3 (gallery) precedes Task 4 (face margin), which relies on `ranked` being one entry per person.
- **Two module copies.** `server/` modules load as both bare (`import speaker_id`) and packaged (`server.speaker_id`) depending on entry point; module-level mutations do not cross between them. Tests import bare. If a change appears not to take effect at runtime, this is the first thing to check.
- **Never loosen a test to make it green.** If `test_second_view_matches_after_gallery_enroll` or a lab criterion fails, the finding is real — report it rather than adjusting the threshold until it passes.
