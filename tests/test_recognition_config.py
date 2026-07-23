"""Tests for server/recognition_config.py — central recognition tunables."""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

import recognition_config  # noqa: E402


def test_defaults_available_without_config(tmp_path, monkeypatch):
    monkeypatch.setattr(recognition_config, "_CONFIG_PATH", str(tmp_path / "missing.json"))
    recognition_config.reset_cache()
    assert recognition_config.get("face_match_tolerance") == 0.6
    assert recognition_config.get("gallery_max_per_person") == 5


def test_config_overrides_default(tmp_path, monkeypatch):
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"server": {"face_match_margin": 0.11}}), encoding="utf-8")
    monkeypatch.setattr(recognition_config, "_CONFIG_PATH", str(cfg))
    recognition_config.reset_cache()
    assert recognition_config.get("face_match_margin") == 0.11
    # untouched keys still fall back to code defaults
    assert recognition_config.get("voice_match_margin") == 0.06


def test_unknown_key_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(recognition_config, "_CONFIG_PATH", str(tmp_path / "missing.json"))
    recognition_config.reset_cache()
    try:
        recognition_config.get("nope")
    except KeyError:
        return
    raise AssertionError("expected KeyError for unknown tunable")


def test_override_changes_get(tmp_path, monkeypatch):
    """override() forces a tunable to a new value for the current process."""
    monkeypatch.setattr(recognition_config, "_CONFIG_PATH", str(tmp_path / "missing.json"))
    recognition_config.reset_cache()
    original_flatness = recognition_config.get("voice_max_flatness")
    original_tau = recognition_config.get("voice_consistency_tau")
    recognition_config.override("voice_max_flatness", original_flatness + 0.05)
    assert recognition_config.get("voice_max_flatness") == original_flatness + 0.05
    # a key nobody touched is unaffected by another key's override
    assert recognition_config.get("voice_consistency_tau") == original_tau
    recognition_config.clear_overrides()


def test_clear_overrides_restores_default(tmp_path, monkeypatch):
    """clear_overrides() drops every override and falls back to config/DEFAULTS."""
    monkeypatch.setattr(recognition_config, "_CONFIG_PATH", str(tmp_path / "missing.json"))
    recognition_config.reset_cache()
    original = recognition_config.get("voice_consistency_tau")
    recognition_config.override("voice_consistency_tau", 0.99)
    assert recognition_config.get("voice_consistency_tau") == 0.99
    recognition_config.clear_overrides()
    assert recognition_config.get("voice_consistency_tau") == original


def test_override_unknown_key_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(recognition_config, "_CONFIG_PATH", str(tmp_path / "missing.json"))
    recognition_config.reset_cache()
    try:
        recognition_config.override("nope", 1.0)
    except KeyError:
        return
    raise AssertionError("expected KeyError for unknown tunable")
