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
