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
