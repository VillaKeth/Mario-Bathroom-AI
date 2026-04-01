import pytest
import numpy as np
import sys
import os

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_person_detector_import():
    from client.person_detector import PersonDetector
    assert PersonDetector is not None

def test_detector_init():
    """PersonDetector initializes without crashing (pure frame processor, no camera)."""
    from client.person_detector import PersonDetector
    det = PersonDetector()
    assert det is not None

def test_face_encoding_shape():
    """Face encodings should be 128-dimensional vectors."""
    from client.person_detector import PersonDetector
    det = PersonDetector()
    fake_encoding = det._empty_encoding()
    assert len(fake_encoding) == 128

def test_face_match_identical():
    """Identical encodings should match with high confidence."""
    from client.person_detector import PersonDetector
    det = PersonDetector()
    enc = np.random.randn(128).astype(np.float64)
    match, confidence = det.compare_faces(enc, enc)
    assert match == True
    assert confidence > 0.99

def test_face_match_different():
    """Very different encodings should not match."""
    from client.person_detector import PersonDetector
    det = PersonDetector()
    enc1 = np.ones(128, dtype=np.float64)
    enc2 = -np.ones(128, dtype=np.float64)
    match, confidence = det.compare_faces(enc1, enc2)
    assert match == False

def test_detect_people_returns_list():
    """detect_people should return a list even on fake frame."""
    from client.person_detector import PersonDetector
    det = PersonDetector()
    frame = np.zeros((240, 320, 3), dtype=np.uint8)
    results = det.detect_people(frame)
    assert isinstance(results, list)
