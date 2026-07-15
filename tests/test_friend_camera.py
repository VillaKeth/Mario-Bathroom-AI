import asyncio
import base64
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

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
