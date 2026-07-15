import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

import camera_relay as cr


def setup_function(_):
    cr.reset_state()


def test_allow_frame_rate_limits_per_client():
    assert cr.allow_frame("a", now=100.0, min_interval=2.0) is True   # first ever → allowed
    assert cr.allow_frame("a", now=101.0, min_interval=2.0) is False  # 1s later → too soon
    assert cr.allow_frame("a", now=102.5, min_interval=2.0) is True   # 2.5s later → allowed
    assert cr.allow_frame("b", now=101.0, min_interval=2.0) is True   # different client independent


def test_frame_cache_roundtrip_and_ttl():
    cr.cache_frame("a", b"jpegbytes", now=100.0)
    assert cr.get_cached_frame("a", now=110.0, ttl=30.0) == b"jpegbytes"  # within TTL
    assert cr.get_cached_frame("a", now=140.0, ttl=30.0) is None          # expired
    assert cr.get_cached_frame("nobody", now=100.0, ttl=30.0) is None     # unknown client


def test_clear_client_drops_frame_and_greet_and_noface():
    cr.cache_frame("a", b"x", now=100.0)
    cr.request_greet("a")
    cr.note_face("a", False)
    cr.clear_client("a")
    assert cr.get_cached_frame("a", now=101.0, ttl=30.0) is None
    assert cr.take_greet("a") is False
    assert cr.note_face("a", False) == 1  # counter was reset → this is the first again


def test_greet_pending_is_one_shot():
    assert cr.take_greet("a") is False   # nothing requested
    cr.request_greet("a")
    assert cr.take_greet("a") is True     # consumed once
    assert cr.take_greet("a") is False    # not again


def test_vision_throttle_is_global_gap():
    assert cr.vision_allowed(now=100.0, min_gap=45.0) is True   # never spoken → allowed
    cr.mark_vision(now=100.0)
    assert cr.vision_allowed(now=120.0, min_gap=45.0) is False  # 20s later → too soon
    assert cr.vision_allowed(now=146.0, min_gap=45.0) is True   # 46s later → allowed


def test_note_face_counts_consecutive_misses():
    assert cr.note_face("a", False) == 1
    assert cr.note_face("a", False) == 2
    assert cr.note_face("a", True) == 0    # a face resets the streak
    assert cr.note_face("a", False) == 1


def test_is_vision_request_matches_look_intent():
    for t in ["what do you see", "How do I look?", "can you see me?",
              "do i look ok", "check out my outfit", "look at me"]:
        assert cr.is_vision_request(t) is True, t
    for t in ["tell me a joke", "what's up", "play a game", "sing a song", "",
              "check the score out", "check my messages and then head out",
              "do I look at the map first?", "check this trick out"]:
        assert cr.is_vision_request(t) is False, t


import base64
import types


def _install_fake_face_recognition(monkeypatch, encs):
    """Inject a fake `face_recognition` module that returns `encs` from face_encodings."""
    fake = types.SimpleNamespace(
        load_image_file=lambda buf: "IMG",
        face_encodings=lambda img: encs,
    )
    monkeypatch.setitem(sys.modules, "face_recognition", fake)


def test_encode_returns_encoding_for_a_face(monkeypatch):
    import numpy as np
    _install_fake_face_recognition(monkeypatch, [np.zeros(128, dtype=float)])
    b64 = base64.b64encode(b"not-a-real-jpeg-but-decodes").decode()
    available, enc = cr.encode_face_from_b64(b64)
    assert available is True
    assert enc is not None and enc.shape == (128,)


def test_encode_true_but_none_when_no_face(monkeypatch):
    _install_fake_face_recognition(monkeypatch, [])
    b64 = base64.b64encode(b"whatever").decode()
    available, enc = cr.encode_face_from_b64(b64)
    assert available is True
    assert enc is None


def test_encode_unavailable_when_import_missing(monkeypatch):
    monkeypatch.setitem(sys.modules, "face_recognition", None)  # import -> ImportError
    available, enc = cr.encode_face_from_b64(base64.b64encode(b"x").decode())
    assert available is False
    assert enc is None


def test_encode_unavailable_on_bad_base64():
    available, enc = cr.encode_face_from_b64("!!!not base64!!!")
    assert available is False
    assert enc is None


def test_encode_tolerates_whitespace_in_base64(monkeypatch):
    import numpy as np
    _install_fake_face_recognition(monkeypatch, [np.zeros(128, dtype=float)])
    b64 = base64.b64encode(b"payload").decode()
    wrapped = b64[:4] + "\n" + b64[4:] + "  "   # newlines/spaces like a wrapped encoder
    available, enc = cr.encode_face_from_b64(wrapped)
    assert available is True
    assert enc is not None


def test_encode_unavailable_on_empty_string(monkeypatch):
    _install_fake_face_recognition(monkeypatch, [])
    available, enc = cr.encode_face_from_b64("")
    assert available is False
    assert enc is None
