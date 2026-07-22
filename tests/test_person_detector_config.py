"""F6: face detector parameters must be configurable (default unchanged).

Lets the party box opt into the stronger 'cnn' detector / a tighter tolerance
without editing code. Defaults preserve current behavior (hog, 0.6).
"""
import sys
import os

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from client.person_detector import PersonDetector  # noqa: E402


def test_default_detector_model_is_hog(monkeypatch):
    # MINOR 8: pass an explicit tier so this is portable. With no tier, PersonDetector
    # auto-detects, so it passed on the 'low' dev box but would FAIL on the 'ultra'
    # party box (which, with CUDA dlib, selects 'cnn').
    monkeypatch.delenv("FACE_DETECTOR_MODEL", raising=False)
    assert PersonDetector(hardware_tier="low").face_detector_model == "hog"


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


def test_ultra_tier_selects_cnn(monkeypatch):
    # IMPORTANT 6: 'cnn' auto-selection is gated on dlib CUDA. Force it available.
    monkeypatch.setattr("client.person_detector._dlib_has_cuda", lambda: True)
    from client.person_detector import resolve_detector_model
    assert resolve_detector_model("ultra", None) == "cnn"


def test_high_tier_selects_cnn(monkeypatch):
    monkeypatch.setattr("client.person_detector._dlib_has_cuda", lambda: True)
    from client.person_detector import resolve_detector_model
    assert resolve_detector_model("high", None) == "cnn"


def test_cnn_tier_without_cuda_falls_back_to_hog(monkeypatch):
    """IMPORTANT 6: a CNN-capable tier on a CPU-only dlib build must stay on HOG —
    MMOD CNN on CPU is ~1-2 s/frame and starves the presence thread."""
    monkeypatch.setattr("client.person_detector._dlib_has_cuda", lambda: False)
    from client.person_detector import resolve_detector_model
    assert resolve_detector_model("ultra", None) == "hog"
    assert resolve_detector_model("high", None) == "hog"


def test_low_tier_selects_hog():
    from client.person_detector import resolve_detector_model
    assert resolve_detector_model("low", None) == "hog"


def test_medium_tier_selects_hog():
    from client.person_detector import resolve_detector_model
    assert resolve_detector_model("medium", None) == "hog"


def test_env_override_wins_over_tier():
    from client.person_detector import resolve_detector_model
    assert resolve_detector_model("ultra", "hog") == "hog"


def test_env_override_cnn_wins_even_without_cuda(monkeypatch):
    """The human override must beat everything, including the CUDA gate — a human can
    force cnn on a box where auto-selection would have refused it."""
    monkeypatch.setattr("client.person_detector._dlib_has_cuda", lambda: False)
    from client.person_detector import resolve_detector_model
    assert resolve_detector_model("low", "cnn") == "cnn"


def test_unknown_tier_falls_back_to_hog():
    from client.person_detector import resolve_detector_model
    assert resolve_detector_model("banana", None) == "hog"


# ---------------------------------------------------------------------------
# W5: adaptive frame skip + hardware_tier wiring + _detect_tier() safety net.
#
# These pin genuinely new, stateful, time-dependent behavior added alongside
# resolve_detector_model(). Time is controlled explicitly throughout (a fake
# clock swapped into the module under test, or absolute _last_person_ts
# values computed from it) -- nothing here sleeps or depends on how fast the
# test itself runs. YOLO is stubbed so no weights/camera/GPU are required.
# ---------------------------------------------------------------------------


class _FixedClock:
    """Stand-in for the `time` module exposing only the `.time()` call that
    detect_people() makes. Swapped into client.person_detector's own module
    namespace (via monkeypatch) so only that module's view of `time` is
    affected -- the real global time module is untouched."""

    def __init__(self, value):
        self._value = value

    def time(self):
        return self._value


class _FakeTensor:
    """Stand-in for a torch tensor slice: mimics box.xyxy[0].cpu().numpy()."""

    def __init__(self, values):
        self._arr = np.array(values, dtype=float)

    def cpu(self):
        return self

    def numpy(self):
        return self._arr


class _FakeBox:
    """Stand-in for one ultralytics result box (the bits detect_people() reads)."""

    def __init__(self, xyxy, conf):
        self.xyxy = [_FakeTensor(xyxy)]
        self.conf = [conf]


class _FakeResult:
    """Stand-in for one ultralytics Results entry (`r` in `for r in results`)."""

    def __init__(self, boxes):
        self.boxes = boxes


class _FakeYOLO:
    """Stub YOLO: records every predict() call, always reports one detection."""

    def __init__(self):
        self.call_count = 0

    def predict(self, frame, conf=None, classes=None, verbose=False):
        self.call_count += 1
        return [_FakeResult([_FakeBox((10, 10, 50, 50), 0.9)])]


class _FakeYOLOEmpty:
    """Stub YOLO: records every predict() call, always reports nobody home."""

    def __init__(self):
        self.call_count = 0

    def predict(self, frame, conf=None, classes=None, verbose=False):
        self.call_count += 1
        return [_FakeResult([])]


def _blank_frame():
    return np.zeros((240, 320, 3), dtype=np.uint8)


def test_adaptive_skip_processes_every_frame_while_person_present(monkeypatch):
    """While someone was seen within person_active_window, every frame should
    reach YOLO -- not just every Nth one (frame_skip=3 would otherwise let
    only 2 of the 6 calls below through)."""
    det = PersonDetector(frame_skip=3)
    det.is_available = True
    monkeypatch.setattr("client.person_detector._face_rec_available", False)
    fake_yolo = _FakeYOLO()
    det._yolo = fake_yolo

    fixed_now = 1_000_000.0
    monkeypatch.setattr("client.person_detector.time", _FixedClock(fixed_now))
    det._last_person_ts = fixed_now  # detected "just now"

    frame = _blank_frame()
    for _ in range(6):
        det.detect_people(frame)

    assert fake_yolo.call_count == 6


def test_adaptive_skip_reverts_once_active_window_expires(monkeypatch):
    """Once person_active_window has elapsed since the last detection, the
    configured frame_skip cadence takes back over: frame_skip=3 over 6 calls
    should let exactly 2 (the 3rd and 6th) reach YOLO."""
    det = PersonDetector(frame_skip=3)
    det.is_available = True
    monkeypatch.setattr("client.person_detector._face_rec_available", False)
    fake_yolo = _FakeYOLOEmpty()  # never finds anyone -> _last_person_ts frozen
    det._yolo = fake_yolo

    fixed_now = 1_000_000.0
    monkeypatch.setattr("client.person_detector.time", _FixedClock(fixed_now))
    det._last_person_ts = fixed_now - det.person_active_window - 1.0  # expired

    frame = _blank_frame()
    for _ in range(6):
        det.detect_people(frame)

    assert fake_yolo.call_count == 2


def test_last_person_ts_refreshes_when_people_detected(monkeypatch):
    """A successful detection stamps _last_person_ts with the current time so
    presence keeps the fast cadence alive for the next call. frame_skip=1
    isolates this from the skip-cadence math covered by the two tests above."""
    det = PersonDetector(frame_skip=1)
    det.is_available = True
    monkeypatch.setattr("client.person_detector._face_rec_available", False)
    det._yolo = _FakeYOLO()

    det._last_person_ts = 0.0  # sentinel: nobody seen yet
    fixed_now = 2_000_000.0
    monkeypatch.setattr("client.person_detector.time", _FixedClock(fixed_now))

    det.detect_people(_blank_frame())

    assert det._last_person_ts == fixed_now


def test_hardware_tier_ultra_selects_cnn_detector(monkeypatch):
    monkeypatch.delenv("FACE_DETECTOR_MODEL", raising=False)
    monkeypatch.setattr("client.person_detector._dlib_has_cuda", lambda: True)
    det = PersonDetector(hardware_tier="ultra")
    assert det.hardware_tier == "ultra"
    assert det.face_detector_model == "cnn"


def test_hardware_tier_ultra_without_cuda_selects_hog(monkeypatch):
    """IMPORTANT 6 at the constructor level: the party box wiring must also fall back
    to HOG when dlib has no CUDA, not just resolve_detector_model in isolation."""
    monkeypatch.delenv("FACE_DETECTOR_MODEL", raising=False)
    monkeypatch.setattr("client.person_detector._dlib_has_cuda", lambda: False)
    det = PersonDetector(hardware_tier="ultra")
    assert det.face_detector_model == "hog"


def test_hardware_tier_low_selects_hog_detector(monkeypatch):
    monkeypatch.delenv("FACE_DETECTOR_MODEL", raising=False)
    det = PersonDetector(hardware_tier="low")
    assert det.hardware_tier == "low"
    assert det.face_detector_model == "hog"


def test_detect_tier_returns_low_on_import_failure(monkeypatch):
    """hardware.py may not be importable from the client side (or may fail for
    any other reason) -- _detect_tier() must swallow it and fall back to the
    safe default rather than let an exception escape."""
    from client.person_detector import _detect_tier

    # sys.modules[name] = None is the standard way to force `import name` to
    # raise ImportError without touching the filesystem or sys.path.
    monkeypatch.setitem(sys.modules, "hardware", None)
    assert _detect_tier() == "low"
