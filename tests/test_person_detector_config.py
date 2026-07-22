"""F6: face detector parameters must be configurable (default unchanged).

Lets the party box opt into the stronger 'cnn' detector / a tighter tolerance
without editing code. Defaults preserve current behavior (hog, 0.6).
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from client.person_detector import PersonDetector  # noqa: E402


def test_default_detector_model_is_hog():
    assert PersonDetector().face_detector_model == "hog"


def test_detector_model_is_configurable():
    assert PersonDetector(face_detector_model="cnn").face_detector_model == "cnn"


def test_match_tolerance_defaults_to_class_constant():
    assert PersonDetector().match_tolerance == PersonDetector.FACE_MATCH_TOLERANCE


def test_match_tolerance_is_configurable():
    assert PersonDetector(match_tolerance=0.5).match_tolerance == 0.5


def test_frame_skip_defaults_to_class_constant():
    assert PersonDetector().frame_skip == PersonDetector.YOLO_FRAME_SKIP


def test_frame_skip_is_configurable():
    assert PersonDetector(frame_skip=1).frame_skip == 1


def test_ultra_tier_selects_cnn():
    from client.person_detector import resolve_detector_model
    assert resolve_detector_model("ultra", None) == "cnn"


def test_high_tier_selects_cnn():
    from client.person_detector import resolve_detector_model
    assert resolve_detector_model("high", None) == "cnn"


def test_low_tier_selects_hog():
    from client.person_detector import resolve_detector_model
    assert resolve_detector_model("low", None) == "hog"


def test_medium_tier_selects_hog():
    from client.person_detector import resolve_detector_model
    assert resolve_detector_model("medium", None) == "hog"


def test_env_override_wins_over_tier():
    from client.person_detector import resolve_detector_model
    assert resolve_detector_model("ultra", "hog") == "hog"


def test_unknown_tier_falls_back_to_hog():
    from client.person_detector import resolve_detector_model
    assert resolve_detector_model("banana", None) == "hog"
