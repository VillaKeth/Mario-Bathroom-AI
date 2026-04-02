# tests/test_easter_egg.py
import time
import pytest

def test_easter_egg_schedule_generates_3_to_5_times():
    from server.idle_behavior import EasterEggScheduler
    scheduler = EasterEggScheduler(party_duration_hours=8)
    times = scheduler.firing_times
    assert 3 <= len(times) <= 5

def test_easter_egg_minimum_gap_30_min():
    from server.idle_behavior import EasterEggScheduler
    scheduler = EasterEggScheduler(party_duration_hours=8)
    times = sorted(scheduler.firing_times)
    for i in range(1, len(times)):
        gap = times[i] - times[i-1]
        assert gap >= 1800, f"Gap too small: {gap}s between fire {i-1} and {i}"

def test_easter_egg_should_fire_at_correct_time():
    from server.idle_behavior import EasterEggScheduler
    scheduler = EasterEggScheduler(party_duration_hours=8)
    # Force a known firing time
    scheduler.firing_times = [time.time() - 1]  # 1 second ago
    scheduler._fire_count = 0
    assert scheduler.should_fire() is True

def test_easter_egg_does_not_double_fire():
    from server.idle_behavior import EasterEggScheduler
    scheduler = EasterEggScheduler(party_duration_hours=8)
    scheduler.firing_times = [time.time() - 1]
    scheduler._fire_count = 0
    scheduler.should_fire()  # consume it
    scheduler.record_fired()
    assert scheduler.should_fire() is False

def test_easter_egg_text():
    from server.idle_behavior import EasterEggScheduler
    scheduler = EasterEggScheduler(party_duration_hours=8)
    text = scheduler.get_text()
    assert "Jacob Hoppenstedt" in text
    assert "shouldn't have" in text.lower() or "shouldn't have-a" in text.lower()
