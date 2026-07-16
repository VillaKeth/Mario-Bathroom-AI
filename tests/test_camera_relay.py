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


def test_live_flags_include_camera_toggles():
    import live_flags as lf
    keys = {f["key"] for f in lf.LIVE_FLAGS}
    assert {"camera_enabled", "camera_vision_enabled", "camera_vision_min_gap"} <= keys
    # defaults are sane
    d = lf.flag_defaults()
    assert d["camera_enabled"] is True
    assert d["camera_vision_enabled"] is True
    assert d["camera_vision_min_gap"] == 45


def test_config_example_documents_camera_keys():
    import json
    path = os.path.join(os.path.dirname(__file__), "..", "config.example.json")
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)   # must remain valid JSON
    blob = json.dumps(cfg)
    for k in ("camera_enabled", "camera_vision_enabled", "camera_vision_model",
              "camera_frame_min_interval", "camera_vision_min_gap", "camera_frame_ttl"):
        assert k in blob, k


def test_sweep_evicts_expired_frames():
    cr.cache_frame("a", b"x", now=100.0)
    cr.allow_frame("a", now=100.0, min_interval=2.0)
    cr.sweep(now=200.0, frame_ttl=30.0)          # 100s later, past the 30s frame TTL
    assert cr.get_cached_frame("a", now=200.0, ttl=30.0) is None
    assert "a" not in cr._frames


def test_sweep_keeps_fresh_frames():
    cr.cache_frame("a", b"x", now=100.0)
    cr.sweep(now=110.0, frame_ttl=30.0)          # within TTL
    assert cr.get_cached_frame("a", now=110.0, ttl=30.0) == b"x"


def test_sweep_caps_total_clients():
    for i in range(cr._MAX_CLIENTS + 25):
        cr.allow_frame(f"c{i}", now=float(i), min_interval=0.0)
    cr.sweep(now=1_000_000.0, frame_ttl=30.0)
    assert len(cr._last_frame_ts) <= cr._MAX_CLIENTS


# --- meta-preamble stripping (LLM output hygiene for spoken vision lines) ---

def test_strip_meta_preamble_bare_preamble_becomes_empty():
    # llava-llama3 flake seen live 2026-07-16: whole response was this string
    assert cr.strip_meta_preamble("Here's my response:") == ""


def test_strip_meta_preamble_removes_lead_keeps_content():
    assert cr.strip_meta_preamble("Here's my response: Wahoo! Nice hat!") == "Wahoo! Nice hat!"
    assert cr.strip_meta_preamble("Here is the description: You look sharp.") == "You look sharp."
    assert cr.strip_meta_preamble("Sure, here's my reply: Looking good!") == "Looking good!"
    assert cr.strip_meta_preamble("Response: You look great!") == "You look great!"
    assert cr.strip_meta_preamble("Here's what I see: A star is born!") == "A star is born!"


def test_strip_meta_preamble_leaves_real_speech_alone():
    assert cr.strip_meta_preamble("Wahoo! Nice hat!") == "Wahoo! Nice hat!"
    assert cr.strip_meta_preamble("Here's the deal, we party!") == "Here's the deal, we party!"
    assert cr.strip_meta_preamble("") == ""
    assert cr.strip_meta_preamble(None) == ""


def test_strip_meta_preamble_only_strips_once_at_start():
    # a mid-text "response:" is content, not preamble
    t = "You look great! My response: always party."
    assert cr.strip_meta_preamble(t) == t
