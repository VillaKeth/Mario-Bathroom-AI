"""Tests for ambiguity margin rejection on both modalities (spec W4)."""
import os
import sqlite3
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

from face_memory import FaceMemory  # noqa: E402
import recognition_config  # noqa: E402
import speaker_id  # noqa: E402


@pytest.fixture(autouse=True)
def _fresh_recognition_config():
    """recognition_config caches tunables process-wide (module-global `_cache`), so a
    monkeypatched override left behind by another test file (e.g. test_recognition_config.py)
    could otherwise leak into these margin-dependent outcomes. Force a clean read of the
    real config.json (which sets none of these tunables) before and after every test here.
    """
    recognition_config.reset_cache()
    yield
    recognition_config.reset_cache()


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


# ---------------------------------------------------------------------------
# Voice side: speaker_id.identify_speaker.
#
# The plan's own Step 4 snippet tracked second-best similarity across raw
# `speakers` ROWS. That is wrong: register_speaker / register_speaker_multi
# each INSERT a new row, so a guest who enrolls twice has TWO rows under one
# name. Raw-row ranking would make that guest's own second print look like a
# competing runner-up and wrongly reject her own match as ambiguous. The fix
# mirrors face_memory's per-person reduction: collapse to the best similarity
# per distinct NAME before ranking and applying the margin.
#
# identify_speaker is exercised end-to-end with no real resemblyzer model:
# `_encoder` is monkeypatched to a sentinel object (bypasses the "not
# initialized" guard) and `get_embedding` is monkeypatched to return a fixed
# 2D unit PROBE vector. `_vec_at_similarity` builds a unit vector whose cosine
# similarity to PROBE=(1, 0) is EXACTLY the requested value, so the target
# similarity in each test is exact rather than approximate.
# ---------------------------------------------------------------------------

PROBE = np.array([1.0, 0.0])


def _vec_at_similarity(similarity):
    """Unit 2D vector whose cosine similarity to PROBE=(1, 0) is exactly `similarity`."""
    similarity = float(similarity)
    return np.array([similarity, (1.0 - similarity ** 2) ** 0.5])


def _init_speakers_table(db_path):
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS speakers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                embedding BLOB NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()


def _enroll(db_path, name, similarity):
    """Insert one `speakers` row whose embedding has the given cosine similarity to PROBE."""
    emb = _vec_at_similarity(similarity).astype(np.float32)
    with sqlite3.connect(db_path) as conn:
        conn.execute("INSERT INTO speakers (name, embedding) VALUES (?, ?)",
                     (name, emb.tobytes()))
        conn.commit()


@pytest.fixture
def voices_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "voices.db")
    _init_speakers_table(db_path)
    monkeypatch.setattr(speaker_id, "DB_PATH", db_path)
    monkeypatch.setattr(speaker_id, "_encoder", object())  # bypass the "not initialized" guard
    monkeypatch.setattr(speaker_id, "get_embedding", lambda data, sr=16000: PROBE.astype(np.float64))
    return db_path


def test_ambiguous_voice_returns_unknown(voices_db):
    """Two different enrolled voices close together above threshold -> refuse to guess.

    Mirrors the measured lab case from the design doc: probe "Fay" raw-matched voice
    "Ava" at cosine 0.68 (above the 0.65 threshold), with Fay's own print at 0.70 --
    a 0.02 gap, well under the 0.06 voice_match_margin.
    """
    _enroll(voices_db, "Ava", 0.68)
    _enroll(voices_db, "Fay", 0.70)
    result = speaker_id.identify_speaker(b"\x00\x00" * 8000)
    assert result["is_new"] is True
    assert result["name"] is None
    assert result["speaker_id"] is None


def test_clear_voice_winner_still_matches(voices_db):
    _enroll(voices_db, "Alice", 0.90)
    _enroll(voices_db, "Bob", 0.30)
    result = speaker_id.identify_speaker(b"\x00\x00" * 8000)
    assert result["is_new"] is False
    assert result["name"] == "Alice"


def test_single_enrolled_voice_unaffected(voices_db):
    """With one enrolled voice there is no runner-up, so no margin to clear."""
    _enroll(voices_db, "Alice", 0.90)
    result = speaker_id.identify_speaker(b"\x00\x00" * 8000)
    assert result["is_new"] is False
    assert result["name"] == "Alice"


def test_same_name_enrolled_twice_still_matches(voices_db):
    """THE regression the plan's raw-row snippet would have introduced: a returning
    guest who enrolled twice (register_speaker/_multi both INSERT, never UPDATE) has
    two rows under one name. Her own second print must not be treated as her runner-up.
    """
    _enroll(voices_db, "Alice", 0.90)   # first enrollment
    _enroll(voices_db, "Alice", 0.87)   # re-enrolled later -- a second, slightly different print
    result = speaker_id.identify_speaker(b"\x00\x00" * 8000)
    assert result["is_new"] is False
    assert result["name"] == "Alice"


def test_voice_below_threshold_is_new(voices_db):
    """Existing below-threshold behavior must survive the rewrite unchanged."""
    _enroll(voices_db, "Alice", 0.30)
    result = speaker_id.identify_speaker(b"\x00\x00" * 8000)
    assert result["is_new"] is True
    assert result["name"] is None
    assert result["speaker_id"] is None
    assert result["confidence"] == pytest.approx(0.30)


def test_duplicate_enrollment_does_not_mask_real_ambiguity(voices_db):
    """A repeat-enrolled name must not accidentally swallow genuine ambiguity from a
    truly different person."""
    _enroll(voices_db, "Alice", 0.90)
    _enroll(voices_db, "Alice", 0.89)    # Alice's own second view -- not a competitor
    _enroll(voices_db, "Bob", 0.87)      # a DIFFERENT person, genuinely close -> ambiguous
    result = speaker_id.identify_speaker(b"\x00\x00" * 8000)
    assert result["is_new"] is True
    assert result["name"] is None
