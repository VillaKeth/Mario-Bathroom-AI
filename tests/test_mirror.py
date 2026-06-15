import asyncio
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))
import mirror

def test_get_mirror_config_fills_defaults():
    cfg = mirror.get_mirror_config({})
    assert cfg["enabled"] is False          # absent → safe default off
    assert cfg["control_mode"] == "station" # absent → safe default view-only
    assert cfg["fps"] == 10
    assert cfg["jpeg_quality"] == 55
    assert cfg["max_width"] == 640

def test_get_mirror_config_respects_values():
    cfg = mirror.get_mirror_config({"mirror": {"enabled": True, "control_mode": "remote", "fps": 5}})
    assert cfg["enabled"] is True
    assert cfg["control_mode"] == "remote"
    assert cfg["fps"] == 5
    assert cfg["jpeg_quality"] == 55  # unspecified → default

def test_authorize_rejected_in_station_mode():
    mcfg = {"token": "t", "pin": "p"}
    ok, reason = mirror.authorize_friend_input("t", "p", mcfg, control_mode="station")
    assert ok is False
    assert reason == "view_only"

def test_authorize_requires_token_and_pin_in_remote_mode():
    mcfg = {"token": "t", "pin": "p"}
    assert mirror.authorize_friend_input("t", "p", mcfg, "remote") == (True, "ok")
    assert mirror.authorize_friend_input("wrong", "p", mcfg, "remote")[0] is False
    assert mirror.authorize_friend_input("t", "wrong", mcfg, "remote")[0] is False
    assert mirror.authorize_friend_input("", "", mcfg, "remote")[0] is False

# ---------------------------------------------------------------------------
# Task 3: viewer registry, capture signal, fan-out relay
# ---------------------------------------------------------------------------

import pytest


class FakeWS:
    def __init__(self, fail=False):
        self.sent_bytes = []
        self.sent_json = []
        self.fail = fail

    async def send_bytes(self, data):
        if self.fail:
            raise RuntimeError("dead socket")
        self.sent_bytes.append(data)

    async def send_json(self, obj):
        if self.fail:
            raise RuntimeError("dead socket")
        self.sent_json.append(obj)


@pytest.fixture(autouse=True)
def _reset_mirror_state():
    mirror.reset_state()
    yield
    mirror.reset_state()


@pytest.mark.asyncio
async def test_add_viewer_signals_capture_start_on_first_only():
    station = FakeWS()
    mirror.set_active_ws_getter(lambda: station)
    v1, v2 = FakeWS(), FakeWS()
    await mirror.add_viewer(v1)
    await mirror.add_viewer(v2)
    starts = [m for m in station.sent_json if m.get("type") == "mirror_request" and m.get("active")]
    assert len(starts) == 1
    assert mirror.viewer_count() == 2


@pytest.mark.asyncio
async def test_remove_last_viewer_signals_capture_stop():
    station = FakeWS()
    mirror.set_active_ws_getter(lambda: station)
    v1 = FakeWS()
    await mirror.add_viewer(v1)
    await mirror.remove_viewer(v1)
    stops = [m for m in station.sent_json if m.get("type") == "mirror_request" and not m.get("active")]
    assert len(stops) == 1
    assert mirror.viewer_count() == 0


@pytest.mark.asyncio
async def test_broadcast_sends_to_all_and_drops_dead():
    mirror.set_active_ws_getter(lambda: None)
    good, dead = FakeWS(), FakeWS(fail=True)
    await mirror.add_viewer(good)
    await mirror.add_viewer(dead)
    await mirror.broadcast(b"\x01frame")
    assert good.sent_bytes == [b"\x01frame"]
    assert mirror.viewer_count() == 1


@pytest.mark.asyncio
async def test_no_duplicate_or_spurious_capture_signals():
    station = FakeWS()
    mirror.set_active_ws_getter(lambda: station)
    v1, v2 = FakeWS(), FakeWS()
    await mirror.add_viewer(v1)      # start (1)
    await mirror.add_viewer(v2)      # no signal (already active)
    await mirror.remove_viewer(v2)   # still 1 viewer -> no stop
    await mirror.remove_viewer(v2)   # phantom (already gone) -> no signal
    await mirror.remove_viewer(v1)   # last out -> stop (1)
    starts = [m for m in station.sent_json if m.get("type") == "mirror_request" and m.get("active")]
    stops = [m for m in station.sent_json if m.get("type") == "mirror_request" and not m.get("active")]
    assert len(starts) == 1
    assert len(stops) == 1


@pytest.mark.asyncio
async def test_broadcast_drops_hanging_viewer_without_blocking_others(monkeypatch):
    monkeypatch.setattr(mirror, "_SEND_TIMEOUT", 0.05)
    mirror.set_active_ws_getter(lambda: None)

    class HangingWS(FakeWS):
        async def send_bytes(self, data):
            await asyncio.sleep(5)   # never completes within the timeout

    good = FakeWS()
    slow = HangingWS()
    await mirror.add_viewer(good)
    await mirror.add_viewer(slow)
    await mirror.broadcast(b"\x01frame")
    assert good.sent_bytes == [b"\x01frame"]   # good viewer got it despite slow one
    assert mirror.viewer_count() == 1           # hanging viewer was dropped


# ---------------------------------------------------------------------------
# Task 4: client frame encoder (downscale + jpeg)
# ---------------------------------------------------------------------------

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "client"))
import mirror_sender


def test_encode_frame_downscales_and_returns_jpeg():
    w, h = 1000, 500
    rgb = bytes([255, 0, 0]) * (w * h)
    out = mirror_sender.encode_frame(rgb, (w, h), max_width=640, quality=55)
    assert isinstance(out, (bytes, bytearray))
    assert out[:2] == b"\xff\xd8"          # JPEG SOI marker
    from PIL import Image
    import io
    img = Image.open(io.BytesIO(out))
    assert img.width == 640
    assert img.height == 320               # aspect preserved (500 * 640/1000)


def test_encode_frame_no_upscale_when_small():
    w, h = 300, 200
    rgb = bytes([0, 128, 0]) * (w * h)
    out = mirror_sender.encode_frame(rgb, (w, h), max_width=640, quality=55)
    from PIL import Image
    import io
    img = Image.open(io.BytesIO(out))
    assert img.width == 300                # never upscales


# ---------------------------------------------------------------------------
# Task 5: MirrorSender class (inactive drops, active stores + queues)
# ---------------------------------------------------------------------------

def test_sender_inactive_drops_everything():
    s = mirror_sender.MirrorSender("ws://x/mirror_ingest")
    s.submit_rgb(b"\x00\x00\x00", (1, 1))
    s.send_audio(b"RIFFxxxx")
    assert s._latest is None
    assert s._audio_q.empty()

def test_sender_active_stores_latest_frame_and_queues_audio():
    s = mirror_sender.MirrorSender("ws://x/mirror_ingest")
    s._active = True  # simulate "viewer connected" without opening a socket
    s.submit_rgb(b"\x01\x02\x03", (1, 1))
    s.submit_rgb(b"\x04\x05\x06", (1, 1))   # newer replaces older (1-slot)
    assert s._latest == (b"\x04\x05\x06", (1, 1))
    s.send_audio(b"RIFFdata")
    assert s._audio_q.get_nowait() == b"RIFFdata"


# ---------------------------------------------------------------------------
# Task 6: ws_client routes mirror_request -> on_mirror_request
# ---------------------------------------------------------------------------

import json as _json
from ws_client import MarioWSClient  # client dir already on sys.path

def test_ws_client_routes_mirror_request():
    c = MarioWSClient("ws://localhost:8765/ws")
    got = {}
    c.on_mirror_request = lambda active: got.update(active=active)
    c._on_message(None, _json.dumps({"type": "mirror_request", "active": True}))
    assert got == {"active": True}
    c._on_message(None, _json.dumps({"type": "mirror_request", "active": False}))
    assert got == {"active": False}


@pytest.mark.asyncio
async def test_ingest_relay_is_verbatim():
    mirror.set_active_ws_getter(lambda: None)
    v = FakeWS()
    await mirror.add_viewer(v)
    await mirror.broadcast(b"\x02RIFFwav")
    await mirror.broadcast(b"\x01\xff\xd8jpg")
    assert v.sent_bytes == [b"\x02RIFFwav", b"\x01\xff\xd8jpg"]
