import asyncio
import base64
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

import numpy as np
import pytest

import main  # heavy but cached
import camera_relay
import mirror as mirror_relay


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    camera_relay.reset_state()
    mirror_relay.reset_state()
    mirror_relay.set_control_mode("remote")
    monkeypatch.setattr(main, "_MIRROR_CFG", {"token": "T", "pin": "P"}, raising=False)
    # Default the vision layer OFF for every test; the vision tests opt in by
    # replacing live_config.get wholesale. This keeps recognition/endpoint tests
    # hermetic even after Task 8 populates camera_vision_* in config_live.json.
    _real_get = main.live_config.get
    monkeypatch.setattr(main.live_config, "get",
                        lambda k, d=None: False if k == "camera_vision_enabled" else _real_get(k, d))
    yield
    camera_relay.reset_state()
    mirror_relay.reset_state()


def _good(**over):
    body = {"token": "T", "pin": "P", "name": "Jake", "id": "c1",
            "image_b64": base64.b64encode(b"frame").decode(), "reason": "tick"}
    body.update(over)
    return body


def test_see_rejects_bad_credentials():
    r = asyncio.run(main.friend_see(_good(pin="WRONG")))
    assert r["status"] == "error"
    assert r["reason"] == "bad_credentials"


def test_see_rejects_missing_client_id():
    r = asyncio.run(main.friend_see(_good(id="")))
    assert r["status"] == "error"
    assert r["reason"] == "no_client_id"


def test_see_rejects_oversized_image():
    r = asyncio.run(main.friend_see(_good(image_b64="A" * 8_000_001)))
    assert r["status"] == "error"
    assert r["reason"] == "too_large"


def test_see_rate_limits_second_fast_frame(monkeypatch):
    monkeypatch.setattr(camera_relay, "encode_face_from_b64", lambda b: (True, None))
    r1 = asyncio.run(main.friend_see(_good()))
    r2 = asyncio.run(main.friend_see(_good()))
    assert r1["status"] == "ok"
    assert r2.get("throttled") is True


def test_see_camera_off_clears_cache(monkeypatch):
    monkeypatch.setattr(camera_relay, "encode_face_from_b64", lambda b: (True, None))
    asyncio.run(main.friend_see(_good()))
    camera_relay.cache_frame("c1", b"x", now=1.0)
    r = asyncio.run(main.friend_see(_good(reason="camera_off")))
    assert r["status"] == "ok"
    assert camera_relay.get_cached_frame("c1", now=2.0, ttl=30.0) is None


def test_see_reports_recognition_unavailable(monkeypatch):
    monkeypatch.setattr(camera_relay, "encode_face_from_b64", lambda b: (False, None))
    r = asyncio.run(main.friend_see(_good()))
    assert r["status"] == "ok"
    assert r["recognition"] == "unavailable"


def test_see_no_face_returns_face_false(monkeypatch):
    monkeypatch.setattr(camera_relay, "encode_face_from_b64", lambda b: (True, None))
    r = asyncio.run(main.friend_see(_good()))
    assert r["status"] == "ok"
    assert r["face"] is False


def test_see_face_true_and_requests_greet_on_camera_on(monkeypatch):
    monkeypatch.setattr(camera_relay, "encode_face_from_b64",
                        lambda b: (True, np.zeros(128)))
    greeted = {"n": 0}
    monkeypatch.setattr(camera_relay, "request_greet",
                        lambda cid: greeted.__setitem__("n", greeted["n"] + 1))
    # Recognition is exercised by dedicated tests below with a fake _face_memory;
    # keep this test focused on the face/greet path and off the real face DB.
    monkeypatch.setattr(main, "_face_memory", None, raising=False)
    r = asyncio.run(main.friend_see(_good(reason="camera_on")))
    assert r["face"] is True                 # success path returns face True
    assert greeted["n"] == 1                  # camera_on requested a pending greet


class _FakeFaceMem:
    def __init__(self, match=None):
        self._match = match
        self.learned = []
    def find_match(self, enc, tolerance=None):
        return self._match
    def learn_guest(self, name, enc):
        self.learned.append(name)


def test_see_enrolls_unknown_face_under_guest_name(monkeypatch):
    import numpy as np
    monkeypatch.setattr(camera_relay, "encode_face_from_b64",
                        lambda b: (True, np.zeros(128)))
    fm = _FakeFaceMem(match=None)
    monkeypatch.setattr(main, "_face_memory", fm, raising=False)
    pushed = []
    monkeypatch.setattr(main.recognition_events, "push",
                        lambda *a, **k: pushed.append(a))
    r = asyncio.run(main.friend_see(_good(name="Jake")))
    assert r["face"] is True
    assert r["recognized"] == "Jake"
    assert r["is_new"] is True
    assert fm.learned == ["Jake"]                 # enrolled under the known name
    assert pushed and pushed[0][0] == "face"      # kind == "face"
    assert pushed[0][4] == "remote_cam"           # source


def test_see_matches_known_face_without_reenroll(monkeypatch):
    import numpy as np
    monkeypatch.setattr(camera_relay, "encode_face_from_b64",
                        lambda b: (True, np.zeros(128)))
    fm = _FakeFaceMem(match={"person_id": 7, "name": "Rosa", "confidence": 0.82,
                             "visit_count": 3})
    monkeypatch.setattr(main, "_face_memory", fm, raising=False)
    monkeypatch.setattr(main.recognition_events, "push", lambda *a, **k: None)
    r = asyncio.run(main.friend_see(_good(name="Jake")))
    assert r["recognized"] == "Rosa"
    assert r["is_new"] is False
    assert fm.learned == []                        # NOT re-enrolled


def _stub_speak_chain(monkeypatch, captured):
    """Make the speak chain deterministic and capture the spoken text."""
    async def fake_gen(messages, model=None, **k):
        captured["messages"] = messages
        return {"text": "Nice party hat, Jake!", "emotion": "happy", "energy": 0.6}
    monkeypatch.setattr(main.llm, "generate_response", fake_gen)
    monkeypatch.setattr(main, "filter_response", lambda t: t)
    monkeypatch.setattr(main, "analyze_text",
                        lambda t: {"tts_text": t, "display_text": t, "pose_hint": None})
    monkeypatch.setattr(main.tts, "synthesize_user", lambda t: b"WAV")

    async def fake_idle_send(ws, text, audio, **k):
        captured["spoke"] = text
        return True
    monkeypatch.setattr(main, "_idle_send_if_safe", fake_idle_send)
    monkeypatch.setattr(main, "_active_ws", object(), raising=False)
    monkeypatch.setattr(main, "_get_idle_prompt", lambda: "You are the character.")


def test_vision_comment_speaks_and_sends_image(monkeypatch):
    cap = {}
    _stub_speak_chain(monkeypatch, cap)
    monkeypatch.setattr(main.live_config, "get",
                        lambda k, d=None: {"camera_vision_enabled": True,
                                           "camera_vision_model": "gemma3:27b"}.get(k, d))
    spoke = asyncio.run(main._camera_vision_comment(b"frame", "Jake", reason="camera_on"))
    assert spoke is True
    assert cap["spoke"] == "Nice party hat, Jake!"
    # the frame rode along as an Ollama image on the user message
    user_msgs = [m for m in cap["messages"] if m.get("role") == "user"]
    assert user_msgs and "images" in user_msgs[-1] and user_msgs[-1]["images"]


def test_vision_comment_skips_when_disabled(monkeypatch):
    cap = {}
    _stub_speak_chain(monkeypatch, cap)
    monkeypatch.setattr(main.live_config, "get",
                        lambda k, d=None: {"camera_vision_enabled": False}.get(k, d))
    spoke = asyncio.run(main._camera_vision_comment(b"frame", "Jake", reason="camera_on"))
    assert spoke is False
    assert "spoke" not in cap


def test_vision_comment_skips_when_no_model(monkeypatch):
    cap = {}
    _stub_speak_chain(monkeypatch, cap)
    monkeypatch.setattr(main.live_config, "get",
                        lambda k, d=None: {"camera_vision_enabled": True,
                                           "camera_vision_model": ""}.get(k, d))
    # GAME_CONFIG is a plain dict in this codebase (main.py: GAME_CONFIG = {...}),
    # so its "get" method can't be monkeypatched directly (attribute is read-only
    # on a built-in dict instance) — set the item instead for the same effect.
    monkeypatch.setitem(main.GAME_CONFIG, "camera_vision_model", "")
    spoke = asyncio.run(main._camera_vision_comment(b"frame", "Jake", reason="camera_on"))
    assert spoke is False


def test_lull_comment_respects_global_throttle(monkeypatch):
    cap = {}
    _stub_speak_chain(monkeypatch, cap)
    monkeypatch.setattr(main.live_config, "get",
                        lambda k, d=None: {"camera_vision_enabled": True,
                                           "camera_vision_model": "gemma3:27b",
                                           "camera_vision_min_gap": 45}.get(k, d))
    first = asyncio.run(main._camera_vision_comment(b"f", "Jake", reason="lull"))
    second = asyncio.run(main._camera_vision_comment(b"f", "Jake", reason="lull"))
    assert first is True
    assert second is False    # throttled: two lull comments back-to-back
