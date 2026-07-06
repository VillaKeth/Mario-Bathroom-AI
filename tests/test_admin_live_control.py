"""Tests for the admin live-toggle bus: live_flags manifest, /admin/live_set,
/admin/state, and the read-site refactors that make feature flags apply live."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

import pytest

import live_flags as lf


# --- Task 1: manifest + coercion -------------------------------------------

def test_manifest_has_expected_flags():
    keys = {f["key"] for f in lf.LIVE_FLAGS}
    assert {
        "llm_idle_enabled", "gossip_enabled", "safety_enabled", "games_enabled",
        "recognition_enabled", "distress_enabled", "catchphrase_mirror_enabled",
        "paused",
    } <= keys


def test_coerce_bool_and_reject_unknown():
    assert lf.coerce_flag("paused", "true") is True
    assert lf.coerce_flag("paused", 0) is False
    assert lf.coerce_flag("paused", "off") is False
    with pytest.raises(ValueError):
        lf.coerce_flag("not_a_flag", 1)


def test_coerce_number_range():
    assert lf.coerce_flag("llm_idle_chance", "0.25") == 0.25
    with pytest.raises(ValueError):
        lf.coerce_flag("llm_idle_chance", 5)  # out of 0..1


def test_public_manifest_is_json_safe():
    import json
    # coerce fns are callables — must be stripped from the public manifest
    json.dumps(lf.public_manifest())
    assert all("coerce" not in entry for entry in lf.public_manifest())


def test_flag_defaults_covers_all_flags():
    assert set(lf.flag_defaults()) == {f["key"] for f in lf.LIVE_FLAGS}


# --- Task 2: /admin/live_set + /admin/state --------------------------------
# These import server/main.py (heavy but cached) and monkeypatch its module-level
# `live_config` to a temp file so the tests never touch the RUNNING server's
# config_live.json.

import asyncio

from hot_reload import LiveConfig


@pytest.fixture
def srv_tmp(tmp_path, monkeypatch):
    import main as srv
    lc = LiveConfig(str(tmp_path / "live.json"))
    monkeypatch.setattr(srv, "live_config", lc)
    return srv


def _key(srv):
    return srv.GAME_CONFIG.get("admin_api_key", "")


def test_live_set_rejects_unknown_key(srv_tmp):
    r = asyncio.run(srv_tmp.admin_live_set(
        {"api_key": _key(srv_tmp), "key": "definitely_not_a_flag", "value": 1}))
    assert r["status"] == "error"


def test_live_set_bad_value_rejected(srv_tmp):
    r = asyncio.run(srv_tmp.admin_live_set(
        {"api_key": _key(srv_tmp), "key": "llm_idle_chance", "value": 9}))
    assert r["status"] == "error"


def test_live_set_and_state_roundtrip(srv_tmp):
    r = asyncio.run(srv_tmp.admin_live_set(
        {"api_key": _key(srv_tmp), "key": "gossip_enabled", "value": False}))
    assert r["status"] == "ok" and r["value"] is False
    s = asyncio.run(srv_tmp.admin_state({"api_key": _key(srv_tmp)}))
    assert s["status"] == "ok"
    assert s["flags"]["gossip_enabled"] is False
    assert any(f["key"] == "gossip_enabled" for f in s["manifest"])
    assert "coerce" not in s["manifest"][0]  # JSON-safe
