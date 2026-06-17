"""Tests for server/face_enrollment.py — the testable face-resolution logic
extracted from main.py's person_detected handler.

Covers the bugs from AUDIT_VOICE_FACE_RECOGNITION.md:
- F1: unknown face + known speaker must ENROLL (learn_guest), not crash.
- F2: unknown face + no speaker must be STASHED, then linkable by name later.
- F4: a matched face must surface its person_id (not a missing "id" key).
"""
import sys
import os
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

import face_enrollment  # noqa: E402


class FakeFaceMemory:
    """Duck-typed stand-in for FaceMemory; records enroll calls."""
    def __init__(self, match_result=None):
        self._match_result = match_result
        self.learned = []          # list of (name, encoding)

    def find_match(self, encoding, tolerance=None):
        return self._match_result

    def learn_guest(self, name, encoding):
        self.learned.append((name, np.asarray(encoding)))


def _face(enc):
    return {"encoding": list(enc), "confidence": 0.9}


def test_known_face_returns_name_and_person_id():
    """F4: a matched face surfaces person_id (not an absent 'id')."""
    fm = FakeFaceMemory(match_result={"name": "Alice", "person_id": 7, "visit_count": 3})
    res = face_enrollment.resolve_faces([_face(np.ones(128))], fm, speaker_name=None)
    assert res["detected"] == [{"name": "Alice", "person_id": 7, "visit_count": 3}]
    assert res["new_face_count"] == 0
    assert res["pending_encoding"] is None
    assert fm.learned == []  # known face must not re-enroll


def test_unknown_face_with_known_speaker_enrolls():
    """F1: unknown face + known speaker → learn_guest(speaker, enc)."""
    fm = FakeFaceMemory(match_result=None)
    enc = np.arange(128, dtype=np.float64)
    res = face_enrollment.resolve_faces([_face(enc)], fm, speaker_name="Bob")
    assert len(fm.learned) == 1
    name, learned_enc = fm.learned[0]
    assert name == "Bob"
    assert np.allclose(learned_enc, enc)
    assert "Bob" in [d["name"] for d in res["detected"]]
    assert res["new_face_count"] == 0
    assert res["pending_encoding"] is None


def test_unknown_face_no_speaker_is_stashed():
    """F2: unknown face + no speaker → stash for later naming, do not enroll."""
    fm = FakeFaceMemory(match_result=None)
    enc = np.arange(128, dtype=np.float64)
    res = face_enrollment.resolve_faces([_face(enc)], fm, speaker_name=None)
    assert fm.learned == []
    assert res["new_face_count"] == 1
    assert res["pending_encoding"] is not None
    assert np.allclose(res["pending_encoding"], enc)


def test_invalid_encoding_is_skipped():
    """Wrong-length encodings are ignored, valid ones in the same batch still process."""
    fm = FakeFaceMemory(match_result=None)
    faces = [{"encoding": [0.1, 0.2, 0.3], "confidence": 0.9},  # too short
             _face(np.zeros(128))]                              # valid, unknown, no speaker
    res = face_enrollment.resolve_faces(faces, fm, speaker_name=None)
    assert res["new_face_count"] == 1  # only the valid one counted


def test_nan_encoding_is_skipped():
    fm = FakeFaceMemory(match_result=None)
    bad = np.zeros(128); bad[0] = np.nan
    res = face_enrollment.resolve_faces([_face(bad)], fm, speaker_name="Bob")
    assert fm.learned == []
    assert res["new_face_count"] == 0


def test_missing_encoding_key_is_skipped():
    fm = FakeFaceMemory(match_result=None)
    res = face_enrollment.resolve_faces([{"confidence": 0.5}], fm, speaker_name="Bob")
    assert fm.learned == []
    assert res["detected"] == []


def test_link_pending_face_enrolls_by_name():
    """F2: once the guest gives a name, the stashed face is enrolled to it."""
    fm = FakeFaceMemory()
    enc = np.arange(128, dtype=np.float64)
    linked = face_enrollment.link_pending_face(fm, "Ann", enc)
    assert linked is True
    assert len(fm.learned) == 1
    assert fm.learned[0][0] == "Ann"


def test_link_pending_face_noops_when_nothing_pending():
    fm = FakeFaceMemory()
    assert face_enrollment.link_pending_face(fm, "Ann", None) is False
    assert fm.learned == []


def test_link_pending_face_noops_without_name():
    fm = FakeFaceMemory()
    assert face_enrollment.link_pending_face(fm, "", np.zeros(128)) is False
    assert fm.learned == []
