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
