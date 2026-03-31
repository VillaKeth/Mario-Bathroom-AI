"""
Tests for vomit detection enhancements:
  - Volume spike detection
  - Temporal coherence (2+ frames in 5s window)
  - Confidence scoring range (0.0–1.0)
  - Reset after timeout
"""

import sys
import os
import time
import numpy as np
import pytest

# Ensure the server package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

from audio_distress import DistressTracker


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_audio_bytes(rms_level: float = 0.01, duration_s: float = 0.5,
                      sample_rate: int = 16000) -> bytes:
    """Generate synthetic PCM16 audio at a given RMS level."""
    n_samples = int(sample_rate * duration_s)
    # White noise scaled to desired RMS
    noise = np.random.randn(n_samples).astype(np.float32) * rms_level
    pcm16 = (noise * 32768.0).clip(-32768, 32767).astype(np.int16)
    return pcm16.tobytes()


def _make_loud_audio(rms_level: float = 0.3, **kwargs) -> bytes:
    return _make_audio_bytes(rms_level=rms_level, **kwargs)


def _make_quiet_audio(rms_level: float = 0.01, **kwargs) -> bytes:
    return _make_audio_bytes(rms_level=rms_level, **kwargs)


def _distress_frame(confidence: float = 0.5) -> dict:
    """Simulate a single-frame detection result flagged as distress."""
    return {
        "is_distress": True,
        "confidence": confidence,
        "top_classes": [],
        "details": "test distress frame",
    }


def _clean_frame() -> dict:
    """Simulate a single-frame detection result with no distress."""
    return {
        "is_distress": False,
        "confidence": 0.0,
        "top_classes": [],
        "details": "",
    }


def _music_frame() -> dict:
    """Frame dominated by music (should be suppressed as false trigger)."""
    return {
        "is_distress": True,
        "confidence": 0.4,
        "top_classes": [("Music", 0.8), ("Speech", 0.1)],
        "details": "Music",
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestVolumeSpikeDetection:
    """Volume spike: RMS >3× baseline flags the frame."""

    def test_volume_spike_detected(self):
        tracker = DistressTracker()

        # Prime baseline with quiet audio
        quiet = _make_quiet_audio(rms_level=0.01)
        for _ in range(5):
            tracker.update(_clean_frame(), quiet)

        # Feed a loud frame — should register a volume spike
        loud = _make_loud_audio(rms_level=0.3)
        result = tracker.update(_distress_frame(), loud)

        assert result["volume_spike"] is True, "Loud audio should trigger volume spike"

    def test_no_spike_on_similar_volume(self):
        tracker = DistressTracker()

        audio = _make_quiet_audio(rms_level=0.05)
        for _ in range(5):
            tracker.update(_clean_frame(), audio)

        # Same level — no spike
        result = tracker.update(_clean_frame(), audio)
        assert result["volume_spike"] is False


class TestTemporalCoherence:
    """Temporal coherence: 2+ distress frames within 5s to confirm."""

    def test_temporal_coherence_requires_multiple_frames(self):
        tracker = DistressTracker()
        audio = _make_quiet_audio()

        # First distress frame — should NOT confirm yet
        r1 = tracker.update(_distress_frame(), audio)
        assert r1["confirmed_distress"] is False, "Single frame must not confirm"

        # Second distress frame (within 5s) — should confirm
        r2 = tracker.update(_distress_frame(), audio)
        assert r2["confirmed_distress"] is True, "Two frames should confirm"

    def test_single_spike_not_enough(self):
        """A single volume spike alone must not trigger confirmed_distress."""
        tracker = DistressTracker()

        # Prime baseline
        quiet = _make_quiet_audio(rms_level=0.01)
        for _ in range(5):
            tracker.update(_clean_frame(), quiet)

        # One loud spike with distress — only 1 event in window
        loud = _make_loud_audio(rms_level=0.3)
        result = tracker.update(_distress_frame(), loud)

        assert result["volume_spike"] is True, "Spike should be detected"
        assert result["confirmed_distress"] is False, (
            "Single spike must NOT confirm — needs 2+ frames"
        )


class TestConfidenceScoring:
    """Combined confidence must stay in [0.0, 1.0]."""

    def test_confidence_scoring_range(self):
        tracker = DistressTracker()
        audio = _make_quiet_audio()

        # Feed several distress frames with max confidence
        for _ in range(10):
            result = tracker.update(_distress_frame(confidence=1.0), audio)
            assert 0.0 <= result["combined_confidence"] <= 1.0, (
                f"Confidence out of range: {result['combined_confidence']}"
            )

    def test_confidence_zero_on_clean(self):
        tracker = DistressTracker()
        audio = _make_quiet_audio()
        result = tracker.update(_clean_frame(), audio)
        assert result["combined_confidence"] == 0.0


class TestResetAfterTimeout:
    """Events older than the coherence window should be pruned."""

    def test_reset_after_timeout(self):
        tracker = DistressTracker()
        # Shrink window for fast test
        tracker.COHERENCE_WINDOW = 0.3
        audio = _make_quiet_audio()

        # Record two distress events — confirmed
        tracker.update(_distress_frame(), audio)
        tracker.update(_distress_frame(), audio)
        assert tracker.distress_frame_count == 2

        # Wait for window to expire
        time.sleep(0.5)

        # After timeout, events should be pruned
        assert tracker.distress_frame_count == 0, (
            "Events must be pruned after coherence window expires"
        )

    def test_manual_reset(self):
        tracker = DistressTracker()
        audio = _make_quiet_audio()

        tracker.update(_distress_frame(), audio)
        tracker.update(_distress_frame(), audio)
        assert tracker.distress_frame_count == 2

        tracker.reset()
        assert tracker.distress_frame_count == 0


class TestFalseTriggerSuppression:
    """Music / laughter / glass sounds should suppress distress."""

    def test_music_suppresses_distress(self):
        tracker = DistressTracker()
        audio = _make_quiet_audio()

        # Two music-dominated frames — should NOT confirm as distress
        tracker.update(_music_frame(), audio)
        result = tracker.update(_music_frame(), audio)

        assert result["confirmed_distress"] is False, (
            "Music-dominated frames should be suppressed"
        )
        assert result["suppressed_by"] is not None
