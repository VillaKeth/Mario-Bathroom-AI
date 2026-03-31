"""Tests for the watchdog reliability layer."""

import sys
import os

# Ensure server/ is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

import pytest
from server.watchdog import Watchdog, DegradationTier


class TestWatchdog:
    """Watchdog unit tests — degradation tiers and failure tracking."""

    def test_initial_tier_is_full(self):
        wd = Watchdog("http://localhost:8765")
        assert wd.current_tier == DegradationTier.FULL
        assert wd.consecutive_failures == 0

    def test_health_check_success_stays_full(self):
        wd = Watchdog("http://localhost:8765")
        health = {
            "status": "ok",
            "llm": "ok",
            "tts": "ok",
            "stt": "ok",
        }
        wd._process_health(health)
        assert wd.current_tier == DegradationTier.FULL
        assert wd.consecutive_failures == 0

    def test_llm_slow_triggers_degraded(self):
        wd = Watchdog("http://localhost:8765")
        health = {
            "status": "ok",
            "llm": "slow",
            "tts": "ok",
            "stt": "ok",
        }
        wd._process_health(health)
        assert wd.current_tier == DegradationTier.DEGRADED

    def test_tts_failed_triggers_minimal(self):
        wd = Watchdog("http://localhost:8765")
        health = {
            "status": "ok",
            "llm": "ok",
            "tts": "failed",
            "stt": "ok",
        }
        wd._process_health(health)
        assert wd.current_tier == DegradationTier.MINIMAL

    def test_consecutive_failures_trigger_restart(self):
        wd = Watchdog("http://localhost:8765", max_failures=3)
        assert not wd.should_restart()
        wd._record_failure()
        wd._record_failure()
        assert not wd.should_restart()
        wd._record_failure()
        assert wd.should_restart()
        assert wd.current_tier == DegradationTier.EMERGENCY

    def test_success_resets_failures(self):
        wd = Watchdog("http://localhost:8765", max_failures=3)
        wd._record_failure()
        wd._record_failure()
        assert wd.consecutive_failures == 2
        wd._record_success()
        assert wd.consecutive_failures == 0
        assert not wd.should_restart()
