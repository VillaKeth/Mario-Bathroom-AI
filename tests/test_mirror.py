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
