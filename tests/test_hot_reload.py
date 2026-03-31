"""Tests for LiveConfig hot reload system."""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

from hot_reload import LiveConfig, LIVE_CONFIG_DEFAULTS


def test_creates_config_on_init():
    """LiveConfig creates the file with defaults if it doesn't exist."""
    path = os.path.join(os.path.dirname(__file__), "..", "_test_live_config.json")
    try:
        if os.path.exists(path):
            os.remove(path)
        lc = LiveConfig(path)
        assert os.path.exists(path)
        with open(path) as f:
            data = json.load(f)
        assert data["chaos_level"] == LIVE_CONFIG_DEFAULTS["chaos_level"]
        assert data["warmth"] == LIVE_CONFIG_DEFAULTS["warmth"]
    finally:
        if os.path.exists(path):
            os.remove(path)


def test_get_returns_value():
    """get() returns stored value, or default for missing keys."""
    path = os.path.join(os.path.dirname(__file__), "..", "_test_live_config2.json")
    try:
        if os.path.exists(path):
            os.remove(path)
        lc = LiveConfig(path)
        assert lc.get("chaos_level") == 5
        assert lc.get("nonexistent", 42) == 42
    finally:
        if os.path.exists(path):
            os.remove(path)


def test_set_persists():
    """set() updates value and persists to disk."""
    path = os.path.join(os.path.dirname(__file__), "..", "_test_live_config3.json")
    try:
        if os.path.exists(path):
            os.remove(path)
        lc = LiveConfig(path)
        lc.set("chaos_level", 9)
        assert lc.get("chaos_level") == 9
        # Verify persistence — reload from disk
        lc2 = LiveConfig(path)
        assert lc2.get("chaos_level") == 9
    finally:
        if os.path.exists(path):
            os.remove(path)
