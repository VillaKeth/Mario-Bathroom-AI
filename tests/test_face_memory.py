import pytest
import numpy as np
import json
import sqlite3
import tempfile
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_face_memory_import():
    from server.face_memory import FaceMemory
    assert FaceMemory is not None

def test_store_and_match_face():
    """Store a face encoding, then match it."""
    from server.face_memory import FaceMemory
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        fm = FaceMemory(db_path)
        encoding = np.random.randn(128).astype(np.float64)
        fm.store_face(person_id=1, name="TestUser", encoding=encoding)
        match = fm.find_match(encoding)
        assert match is not None
        assert match["person_id"] == 1
        assert match["name"] == "TestUser"
        assert match["confidence"] > 0.99
        if hasattr(fm, '_qdrant_client'):
            fm._qdrant_client.close()

def test_no_match_for_unknown():
    """Unknown face should return None."""
    from server.face_memory import FaceMemory
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        fm = FaceMemory(db_path)
        known = np.ones(128, dtype=np.float64)
        fm.store_face(person_id=1, name="Known", encoding=known)
        unknown = -np.ones(128, dtype=np.float64)
        match = fm.find_match(unknown, tolerance=0.4)
        assert match is None
        if hasattr(fm, '_qdrant_client'):
            fm._qdrant_client.close()

def test_multiple_faces():
    """Should match correct person among multiple stored faces."""
    from server.face_memory import FaceMemory
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        fm = FaceMemory(db_path)
        enc_a = np.random.randn(128).astype(np.float64)
        enc_b = np.random.randn(128).astype(np.float64)
        fm.store_face(person_id=1, name="Alice", encoding=enc_a)
        fm.store_face(person_id=2, name="Bob", encoding=enc_b)
        # Small noise (0.02 * sqrt(128) ≈ 0.23 distance, well under 0.6 tolerance)
        noisy_a = enc_a + np.random.randn(128) * 0.02
        match = fm.find_match(noisy_a)
        assert match is not None
        assert match["name"] == "Alice"
        if hasattr(fm, '_qdrant_client'):
            fm._qdrant_client.close()

def test_get_all_faces():
    """Should return all stored face entries."""
    from server.face_memory import FaceMemory
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        fm = FaceMemory(db_path)
        fm.store_face(1, "A", np.zeros(128))
        fm.store_face(2, "B", np.ones(128))
        all_faces = fm.get_all_faces()
        assert len(all_faces) == 2
        if hasattr(fm, '_qdrant_client'):
            fm._qdrant_client.close()

def test_update_existing_face():
    """Storing same person_id again should update, not duplicate."""
    from server.face_memory import FaceMemory
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        fm = FaceMemory(db_path)
        enc1 = np.random.randn(128).astype(np.float64)
        enc2 = np.random.randn(128).astype(np.float64)
        fm.store_face(1, "User", enc1)
        fm.store_face(1, "User", enc2)
        all_faces = fm.get_all_faces()
        assert len(all_faces) == 1
        if hasattr(fm, '_qdrant_client'):
            fm._qdrant_client.close()


def test_find_match_is_euclidean_within_tolerance():
    """find_match (euclidean-authoritative) matches a query within 0.6 distance.

    A controlled offset of 0.04 per dim over 128 dims gives a euclidean distance
    of 0.04 * sqrt(128) ≈ 0.45 — comfortably inside the calibrated 0.6 tolerance.
    """
    from server.face_memory import FaceMemory
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        fm = FaceMemory(db_path)
        known = np.zeros(128, dtype=np.float64)
        fm.store_face(person_id=7, name="Within", encoding=known)

        near = known + 0.04  # distance ≈ 0.45 < 0.6
        assert float(np.linalg.norm(near - known)) < 0.6  # sanity: inside tolerance
        match = fm.find_match(near)
        assert match is not None
        assert match["name"] == "Within"
        assert match["person_id"] == 7
        if hasattr(fm, '_qdrant_client'):
            fm._qdrant_client.close()


def test_find_match_is_euclidean_beyond_tolerance():
    """find_match returns None for a query beyond the 0.6 euclidean threshold.

    An offset of 0.1 per dim over 128 dims gives 0.1 * sqrt(128) ≈ 1.13 — well
    outside the 0.6 tolerance, so the (single) stored face must NOT match.
    """
    from server.face_memory import FaceMemory
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        fm = FaceMemory(db_path)
        known = np.zeros(128, dtype=np.float64)
        fm.store_face(person_id=9, name="Beyond", encoding=known)

        far = known + 0.1  # distance ≈ 1.13 > 0.6
        assert float(np.linalg.norm(far - known)) > 0.6  # sanity: outside tolerance
        match = fm.find_match(far)
        assert match is None
        if hasattr(fm, '_qdrant_client'):
            fm._qdrant_client.close()
