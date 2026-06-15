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
