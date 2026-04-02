"""Tests for night progression party clock reset fix.

These tests verify that the party start time gets properly reset when
it's stale (>24h old), preventing stuck WIND_DOWN phase from test artifacts.
"""

import time
import pytest
from unittest.mock import patch


def test_fresh_start_resets_party_clock():
    """Party clock should reset to current time on fresh server start."""
    from server.night_progression import NightProgression
    before = time.time()
    np = NightProgression()
    after = time.time()
    assert before <= np._start_time <= after


def test_phase_at_zero_hours_is_warm_up():
    from server.night_progression import NightProgression
    np = NightProgression(start_time=time.time())
    phase = np.get_time_phase(0)
    assert phase.name == "WARM_UP"


def test_phase_at_three_hours_is_party_mode():
    from server.night_progression import NightProgression
    np = NightProgression(start_time=time.time() - 3 * 3600)
    hours = np.get_hours_elapsed()
    phase = np.get_time_phase(hours)
    assert phase.name == "PARTY_MODE"


def test_phase_at_six_hours_is_unhinged():
    from server.night_progression import NightProgression
    np = NightProgression(start_time=time.time() - 6 * 3600)
    hours = np.get_hours_elapsed()
    phase = np.get_time_phase(hours)
    assert phase.name == "UNHINGED"


def test_phase_at_eight_hours_is_wind_down():
    from server.night_progression import NightProgression
    np = NightProgression(start_time=time.time() - 8 * 3600)
    hours = np.get_hours_elapsed()
    phase = np.get_time_phase(hours)
    assert phase.name == "WIND_DOWN"


def test_stale_start_time_gets_clamped():
    """If persisted start_time is >24h old, reset to now."""
    from server.night_progression import NightProgression
    stale_time = time.time() - 100 * 3600  # 100 hours ago
    np = NightProgression(start_time=stale_time)
    hours = (time.time() - np._start_time) / 3600
    assert hours < 24, f"Start time should be clamped, got {hours}h ago"
