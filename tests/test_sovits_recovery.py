"""Regression tests for the GPT-SoVITS auto-recovery fix.

Bug (overnight party run): a single subprocess read-timeout set
``_sovits_available = False``; the synthesize() gate required that flag, so
sovits was skipped for the rest of the night and every call fell back to Edge.
There was no recovery path. These tests pin the new behavior:

1. synthesize() still ATTEMPTS sovits even when _sovits_available is False.
2. _sovits_synthesize() rate-limits restarts (no spin) within the cooldown.
3. _sovits_synthesize() retries again once the cooldown elapses (never latches).
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))
import tts  # noqa: E402


def test_synthesize_attempts_sovits_even_when_unavailable(monkeypatch):
    """The latch is gone: a prior crash (_sovits_available=False) must NOT stop
    synthesize() from routing to the sovits path (which self-heals)."""
    monkeypatch.setattr(tts, "TTS_MODE", "sovits")
    monkeypatch.setattr(tts, "_sovits_available", False)  # simulate post-crash latch
    monkeypatch.setattr(tts, "FAST_MODE", False)

    called = {"sovits": False}

    def fake_sovits(text, _is_user=False):
        called["sovits"] = True
        return b"RIFFsovits"

    monkeypatch.setattr(tts, "_sovits_synthesize", fake_sovits)
    monkeypatch.setattr(tts, "_normalize_audio", lambda b: b)
    monkeypatch.setattr(tts, "_save_to_disk_cache", lambda k, w: None)

    out = tts.synthesize("hello there friend", nocache=True)

    assert called["sovits"] is True, "sovits path must be attempted despite the flag"
    assert out == b"RIFFsovits"


def test_sovits_restart_is_rate_limited(monkeypatch):
    """Within the cooldown, a dead subprocess must NOT trigger a fresh restart
    on every call (which would mean a 5s kill + ~23s model load each time)."""
    monkeypatch.setattr(tts, "_sovits_available", False)
    monkeypatch.setattr(tts, "_sovits_process", None)
    monkeypatch.setattr(tts, "_sovits_last_restart_attempt", 0.0)
    monkeypatch.setattr(tts, "_SOVITS_RESTART_COOLDOWN", 10_000.0)

    attempts = {"n": 0}

    def fake_start():
        attempts["n"] += 1
        return False  # restart keeps failing

    monkeypatch.setattr(tts, "_start_sovits_subprocess", fake_start)

    with pytest.raises(RuntimeError):
        tts._sovits_synthesize("hi")
    assert attempts["n"] == 1  # first call tries once

    with pytest.raises(RuntimeError):
        tts._sovits_synthesize("hi again")
    assert attempts["n"] == 1  # still 1 — cooldown suppressed a second spin


def test_sovits_retries_after_cooldown(monkeypatch):
    """Once the cooldown elapses, sovits is retried — it can never permanently
    latch onto Edge the way the old code did."""
    monkeypatch.setattr(tts, "_sovits_available", False)
    monkeypatch.setattr(tts, "_sovits_process", None)
    monkeypatch.setattr(tts, "_sovits_last_restart_attempt", 0.0)
    monkeypatch.setattr(tts, "_SOVITS_RESTART_COOLDOWN", 0.0)  # no cooldown

    attempts = {"n": 0}

    def fake_start():
        attempts["n"] += 1
        return False

    monkeypatch.setattr(tts, "_start_sovits_subprocess", fake_start)

    for _ in range(3):
        with pytest.raises(RuntimeError):
            tts._sovits_synthesize("hi")
    assert attempts["n"] == 3  # retried every call when cooldown is clear
