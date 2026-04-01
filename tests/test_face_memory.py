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
        noisy_a = enc_a + np.random.randn(128) * 0.05
        match = fm.find_match(noisy_a)
        assert match is not None
        assert match["name"] == "Alice"

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
