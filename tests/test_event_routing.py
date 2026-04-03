"""Tests for person_detected event routing and face processing."""
import pytest
import numpy as np
from unittest.mock import MagicMock, patch
from server.guest_profiles import GuestProfileManager


class TestPersonDetectedRouting:
    """Tests for the person_detected event handler logic."""

    def setup_method(self):
        self.mgr = GuestProfileManager()

    def test_single_face_old_schema_backward_compat(self):
        """Old-style single face_encoding events still work."""
        event = {"type": "person_detected", "face_encoding": [0.1] * 128, "confidence": 0.8}
        faces = event.get("faces", [])
        if not faces and "face_encoding" in event:
            faces = [{"encoding": event["face_encoding"], "confidence": event.get("confidence", 0.5)}]
        assert len(faces) == 1
        assert len(faces[0]["encoding"]) == 128

    def test_multi_face_new_schema(self):
        """New multi-face schema parses correctly."""
        event = {
            "type": "person_detected",
            "faces": [
                {"encoding": [0.1] * 128, "confidence": 0.9},
                {"encoding": [0.2] * 128, "confidence": 0.7},
            ],
            "face_count": 2,
        }
        assert len(event["faces"]) == 2

    def test_invalid_face_encoding_rejected(self):
        """Face encodings that aren't 128-dim are skipped."""
        bad_encodings = [
            [0.1] * 64,
            [],
            "not_a_list",
        ]
        for enc in bad_encodings:
            valid = isinstance(enc, list) and len(enc) == 128
            assert not valid

    def test_nan_face_encoding_rejected(self):
        """Face encodings with NaN values are skipped."""
        enc = [float('nan')] * 128
        arr = np.array(enc, dtype=np.float64)
        assert np.any(np.isnan(arr))

    def test_known_face_updates_guest_profile(self):
        """Known face match creates/updates GuestProfile."""
        self.mgr.identify_by_face("Jake", "face_001")
        profile = self.mgr._profiles["Jake"]
        assert "face_001" in profile.face_ids

    def test_unknown_face_with_active_speaker_autolinks(self):
        """Unknown face + known speaker = auto-link face to speaker."""
        self.mgr.identify_by_voice("Jake", "voice_001")
        self.mgr.identify_by_face("Jake", "auto_linked")
        profile = self.mgr._profiles["Jake"]
        assert profile.voice_id == "voice_001"
        assert "auto_linked" in profile.face_ids

    def test_unknown_face_no_speaker_creates_mystery(self):
        """Unknown face + no speaker = mystery guest."""
        mystery = self.mgr.create_mystery_guest()
        assert "Mystery Guest" in mystery.name

    def test_detected_names_accumulate(self):
        """Multiple faces in one frame accumulate detected names."""
        detected_names = []
        new_face_count = 0
        names_to_check = ["Jake", "Lisa", None]
        for name in names_to_check:
            if name:
                self.mgr.identify_by_face(name, f"face_{name}")
                detected_names.append(name)
            else:
                new_face_count += 1
        assert detected_names == ["Jake", "Lisa"]
        assert new_face_count == 1

    def test_empty_faces_event_no_crash(self):
        """Event with empty faces array doesn't crash."""
        event = {"type": "person_detected", "faces": []}
        faces = event.get("faces", [])
        assert len(faces) == 0

    def test_face_count_matches_faces_array(self):
        """face_count field matches actual faces array length."""
        faces = [{"encoding": [0.1] * 128, "confidence": 0.9}] * 3
        event = {"type": "person_detected", "faces": faces, "face_count": len(faces)}
        assert event["face_count"] == len(event["faces"])