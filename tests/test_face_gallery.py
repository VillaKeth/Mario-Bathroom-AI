"""Tests for the multi-encoding face gallery (spec W2)."""
import json
import os
import sqlite3
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

import recognition_config  # noqa: E402
from face_memory import FaceMemory  # noqa: E402


@pytest.fixture(autouse=True)
def _fresh_recognition_config():
    """recognition_config caches tunables process-wide; an override left behind by
    another test file could otherwise change the margin outcomes asserted here."""
    recognition_config.reset_cache()
    yield
    recognition_config.reset_cache()


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


# ---------------------------------------------------------------------------
# Final-review IMPORTANT 4 — legacy data has MANY person_ids per name.
#
# Master's learn_guest allocated `max_id + 1` on EVERY call, so a real
# post-party memory.db holds several face_encodings rows for one guest, each
# with its own person_id. The migration copies them 1:1. If find_match reduces
# per person_id, one human's duplicate rows become COMPETING identities and the
# W4 margin rejects him against himself -> returning guests become permanently
# unrecognizable. speaker_id.identify_speaker already reduces per NAME for
# exactly this reason (server/speaker_id.py:281-303); find_match must match it.
# ---------------------------------------------------------------------------


def _write_legacy_rows(db_path, rows):
    """Insert pre-gallery `face_encodings` rows, one per (person_id, name, encoding)."""
    with sqlite3.connect(db_path) as conn:
        conn.execute("DELETE FROM face_gallery")
        conn.execute("DELETE FROM face_encodings")
        for pid, name, vec in rows:
            conn.execute(
                "INSERT INTO face_encodings (person_id, name, encoding) VALUES (?, ?, ?)",
                (pid, name, json.dumps(np.asarray(vec).tolist())))
        conn.commit()


def test_legacy_duplicate_person_ids_for_one_name_still_match(tmp_path):
    """Two legacy rows for ONE guest, and a new view roughly equidistant from both.

    Per-person_id reduction makes Jacob's two old rows each other's runner-up, the
    margin fires, and Jacob is unrecognizable forever. Per-NAME reduction collapses
    them into one identity, so there is no runner-up and he matches.
    """
    db = str(tmp_path / "faces.db")
    FaceMemory(db)                                   # create the schema
    view_a = np.zeros(128)
    view_b = np.zeros(128); view_b[0] = 0.40
    _write_legacy_rows(db, [(1, "Jacob", view_a), (2, "Jacob", view_b)])

    mem = FaceMemory(db)                             # re-init triggers the 1:1 migration
    probe = np.zeros(128); probe[0] = 0.20           # 0.20 from each of his own views
    match = mem.find_match(probe)

    assert match is not None, "guest rejected as ambiguous against his own duplicate rows"
    assert match["name"] == "Jacob"


def test_legacy_duplicates_do_not_mask_a_genuinely_different_person(tmp_path):
    """Collapsing per name must not swallow real ambiguity between two people."""
    db = str(tmp_path / "faces.db")
    FaceMemory(db)
    jacob_a = np.zeros(128)
    jacob_b = np.zeros(128); jacob_b[0] = 0.02
    rival = np.zeros(128); rival[0] = 0.40
    _write_legacy_rows(db, [(1, "Jacob", jacob_a), (2, "Jacob", jacob_b), (3, "Rival", rival)])

    mem = FaceMemory(db)
    probe = np.zeros(128); probe[0] = 0.21           # ~0.21 from Jacob, ~0.19 from Rival
    assert mem.find_match(probe) is None
