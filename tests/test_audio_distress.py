"""Tests for DistressTracker — volume-spike + distress-class gating.

These exercise the tighter `frame_is_distress` rule introduced to kill party
false-positives: a bare RMS volume spike (shout, door slam) must NOT confirm
distress on its own — it must co-occur with at least one actually-detected
distress class. The PANNs path (is_distress=True) and false-trigger suppression
must keep working.

No real PANNs model is needed: we construct DistressTracker() directly and feed
synthetic frame_result dicts plus small fake int16 PCM audio_bytes.
"""

import sys
import os

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

from audio_distress import DistressTracker  # noqa: E402


# ---------------------------------------------------------------------------
# Audio helpers — RMS is computed from int16 PCM (value / 32768).
#   quiet baseline frame (value=100)  -> RMS ~= 0.00305  (> 0.001, usable baseline)
#   loud spike frame    (value=15000) -> RMS ~= 0.4578   (> baseline * 3)
#   normal frame        (value=300)   -> RMS ~= 0.00916  (no spike vs itself)
# ---------------------------------------------------------------------------
_FRAME_SAMPLES = 1600  # 0.1s at 16kHz


def _quiet_bytes() -> bytes:
    return np.full(_FRAME_SAMPLES, 100, dtype=np.int16).tobytes()


def _loud_bytes() -> bytes:
    return np.full(_FRAME_SAMPLES, 15000, dtype=np.int16).tobytes()


def _normal_bytes() -> bytes:
    return np.full(_FRAME_SAMPLES, 300, dtype=np.int16).tobytes()


# ---------------------------------------------------------------------------
# 1. Bare volume spike, NO distress classes -> must NOT confirm.
# ---------------------------------------------------------------------------
def test_bare_volume_spike_without_distress_class_does_not_confirm():
    tracker = DistressTracker()

    # Prime baseline with a quiet frame so a subsequent loud frame trips a spike.
    tracker.update({"is_distress": False, "distress_classes": []}, _quiet_bytes())

    r1 = tracker.update({"is_distress": False, "distress_classes": []}, _loud_bytes())
    r2 = tracker.update({"is_distress": False, "distress_classes": []}, _loud_bytes())

    # Sanity: the engineered audio really does trip the volume spike detector.
    assert r1["volume_spike"] is True
    assert r2["volume_spike"] is True

    # But with no distress class, a bare spike must not count toward a trigger.
    assert r2["distress_frame_count"] == 0
    assert r2["confirmed_distress"] is False


# ---------------------------------------------------------------------------
# 2. Volume spike WITH a distress class -> two frames confirm.
# ---------------------------------------------------------------------------
def test_volume_spike_with_distress_class_confirms():
    tracker = DistressTracker()

    # Prime baseline quiet so the loud frames register as spikes.
    tracker.update({"is_distress": False, "distress_classes": []}, _quiet_bytes())

    frame = {"is_distress": False, "distress_classes": [("Gargling", 0.2)]}
    r1 = tracker.update(frame, _loud_bytes())
    r2 = tracker.update(frame, _loud_bytes())

    # Confirm the spike actually fired (otherwise the test would be vacuous).
    assert r1["volume_spike"] is True
    assert r2["volume_spike"] is True

    assert r2["distress_frame_count"] == 2
    assert r2["confirmed_distress"] is True


# ---------------------------------------------------------------------------
# 3. PANNs path: is_distress=True, normal audio (no spike needed).
# ---------------------------------------------------------------------------
def test_panns_is_distress_confirms_without_spike():
    tracker = DistressTracker()

    frame = {"is_distress": True, "distress_classes": [("Cough", 0.3)]}
    r1 = tracker.update(frame, _normal_bytes())
    r2 = tracker.update(frame, _normal_bytes())

    # No engineered spike here — confirmation comes purely from the PANNs flag.
    assert r1["volume_spike"] is False
    assert r2["volume_spike"] is False

    assert r2["distress_frame_count"] == 2
    assert r2["confirmed_distress"] is True


# ---------------------------------------------------------------------------
# 4. False-trigger suppression still works (Laughter dominates).
# ---------------------------------------------------------------------------
def test_false_trigger_laughter_is_suppressed():
    tracker = DistressTracker()

    frame = {
        "is_distress": True,
        "distress_classes": [("Cough", 0.3)],
        "top_classes": [("Laughter", 0.9)],
    }
    r = tracker.update(frame, _normal_bytes())

    # Laughter above threshold suppresses the frame entirely — it must not count.
    assert r["suppressed_by"] == "Laughter"
    assert r["distress_frame_count"] == 0
    assert r["confirmed_distress"] is False


# ---------------------------------------------------------------------------
# Bonus: a single distress frame (PANNs) is not enough — needs MIN_FRAMES.
# ---------------------------------------------------------------------------
def test_single_distress_frame_does_not_confirm():
    tracker = DistressTracker()

    frame = {"is_distress": True, "distress_classes": [("Cough", 0.3)]}
    r = tracker.update(frame, _normal_bytes())

    assert r["distress_frame_count"] == 1
    assert r["confirmed_distress"] is False
