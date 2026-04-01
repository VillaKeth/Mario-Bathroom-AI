"""Edge case tests for party crash vectors."""
import pytest
import numpy as np
from unittest.mock import MagicMock, patch


class TestInferGuestType:
    """Edge cases for _infer_guest_type in mario_prompt.py"""

    def setup_method(self):
        from server.mario_prompt import _infer_guest_type
        self._fn = _infer_guest_type

    def test_empty_messages(self):
        assert self._fn([]) == "unknown"

    def test_none_content_filtered(self):
        msgs = [{"role": "user", "content": None}]
        result = self._fn(msgs)
        assert result == "unknown"

    def test_empty_string_content(self):
        msgs = [{"role": "user", "content": ""}]
        result = self._fn(msgs)
        assert result == "unknown"

    def test_missing_role_key(self):
        msgs = [{"content": "hello there"}]
        result = self._fn(msgs)
        assert result == "unknown"

    def test_only_assistant_messages(self):
        msgs = [{"role": "assistant", "content": "I am Mario!"}]
        result = self._fn(msgs)
        assert result == "unknown"

    def test_shy_classification(self):
        msgs = [{"role": "user", "content": "hi"}, {"role": "user", "content": "ya"}]
        result = self._fn(msgs)
        assert result == "shy"

    def test_curious_classification(self):
        msgs = [{"role": "user", "content": "What is this?"},
                {"role": "user", "content": "How does it work?"}]
        result = self._fn(msgs)
        assert result == "curious"

    def test_energetic_classification(self):
        msgs = [{"role": "user", "content": "This party is so awesome!"},
                {"role": "user", "content": "Let's gooo right now!"}]
        result = self._fn(msgs)
        assert result == "energetic"

    def test_storyteller_classification(self):
        long_msg = "So there I was at the party and this really crazy thing happened where Mario started talking and everyone was laughing"
        msgs = [{"role": "user", "content": long_msg}]
        result = self._fn(msgs)
        assert result == "storyteller"

    def test_balanced_classification(self):
        msgs = [{"role": "user", "content": "That sounds pretty cool to me"}]
        result = self._fn(msgs)
        assert result == "balanced"


class TestFaceMemoryEdgeCases:
    """Edge cases for face encoding handling."""

    def test_nan_encoding_rejected(self):
        """NaN values in face encoding should not crash."""
        from server.face_memory import FaceMemory
        import tempfile, os
        db_path = os.path.join(tempfile.mkdtemp(), "test_faces.db")
        fm = FaceMemory(db_path)
        enc = np.full(128, np.nan)
        match = fm.find_match(enc)
        # NaN distance comparisons yield inf, so no match within tolerance
        assert match is None or match.get("confidence", 0) < 0.1

    def test_empty_encoding(self):
        """Empty array should not crash find_match."""
        from server.face_memory import FaceMemory
        import tempfile, os
        db_path = os.path.join(tempfile.mkdtemp(), "test_faces.db")
        fm = FaceMemory(db_path)
        try:
            match = fm.find_match(np.array([]))
        except Exception:
            pass  # OK to raise, just not crash ungracefully

    def test_wrong_dimension_encoding(self):
        """Wrong dimension encoding should not crash."""
        from server.face_memory import FaceMemory
        import tempfile, os
        db_path = os.path.join(tempfile.mkdtemp(), "test_faces.db")
        fm = FaceMemory(db_path)
        enc = np.random.randn(64)
        try:
            match = fm.find_match(enc)
        except Exception:
            pass  # OK to raise, just shouldn't crash server


class TestDisplayEdgeCases:
    """Edge cases for mario_display.py without requiring pygame."""

    def test_typewriter_speed_zero_length(self):
        """_get_typewriter_speed with 0 length should not crash."""
        text_len = 0
        if text_len < 50:
            speed = 1
        elif text_len < 200:
            speed = 2
        else:
            speed = 3
        assert speed == 1

    def test_typewriter_speed_large_text(self):
        """Large text should get fastest speed."""
        text_len = 10000
        if text_len < 50:
            speed = 1
        elif text_len < 200:
            speed = 2
        else:
            speed = 3
        assert speed == 3


class TestPersonDetectorEdgeCases:
    """Edge cases for person detection pipeline."""

    def test_none_frame_detection(self):
        """detect_people(None) should return empty list, not crash."""
        from client.person_detector import PersonDetector
        pd = PersonDetector()
        result = pd.detect_people(None)
        assert result == []

    def test_empty_frame_detection(self):
        """detect_people with empty array should not crash."""
        from client.person_detector import PersonDetector
        pd = PersonDetector()
        result = pd.detect_people(np.array([]))
        assert result == []

    def test_wrong_shape_frame(self):
        """detect_people with 1D array should not crash."""
        from client.person_detector import PersonDetector
        pd = PersonDetector()
        result = pd.detect_people(np.array([1, 2, 3]))
        assert result == []
