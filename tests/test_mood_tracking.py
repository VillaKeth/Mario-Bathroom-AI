"""Tests for per-guest mood recording and trend calculation."""
import pytest
from datetime import datetime, timedelta
from server.guest_profiles import GuestProfile, MoodEntry, GuestProfileManager


class TestMoodRecording:
    def setup_method(self):
        self.mgr = GuestProfileManager()
        self.mgr.identify_by_voice("Jake", "v1")

    def test_record_single_mood(self):
        self.mgr.record_mood("Jake", "excited", 0.9)
        p = self.mgr._profiles["Jake"]
        assert len(p.mood_history) == 1
        assert p.current_mood == "excited"

    def test_record_multiple_moods(self):
        self.mgr.record_mood("Jake", "nervous", 0.3)
        self.mgr.record_mood("Jake", "happy", 0.7)
        self.mgr.record_mood("Jake", "excited", 0.9)
        p = self.mgr._profiles["Jake"]
        assert len(p.mood_history) == 3
        assert p.current_mood == "excited"

    def test_mood_trend_improving(self):
        self.mgr.record_mood("Jake", "sad", 0.2)
        self.mgr.record_mood("Jake", "neutral", 0.5)
        self.mgr.record_mood("Jake", "excited", 0.9)
        assert self.mgr._profiles["Jake"].mood_trend == "improving"

    def test_mood_trend_declining(self):
        self.mgr.record_mood("Jake", "excited", 0.9)
        self.mgr.record_mood("Jake", "neutral", 0.5)
        self.mgr.record_mood("Jake", "sad", 0.2)
        assert self.mgr._profiles["Jake"].mood_trend == "declining"

    def test_mood_trend_stable(self):
        self.mgr.record_mood("Jake", "happy", 0.6)
        self.mgr.record_mood("Jake", "happy", 0.65)
        self.mgr.record_mood("Jake", "happy", 0.7)
        assert self.mgr._profiles["Jake"].mood_trend == "stable"

    def test_mood_for_unknown_guest_no_crash(self):
        self.mgr.record_mood("Nobody", "happy", 0.8)
        # Should not crash, just silently ignore

    def test_context_includes_mood(self):
        self.mgr.record_mood("Jake", "excited", 0.9)
        ctx = self.mgr.get_guest_context("Jake")
        assert "excited" in ctx
        assert "0.9" in ctx

    def test_context_includes_trend(self):
        self.mgr.record_mood("Jake", "sad", 0.2)
        self.mgr.record_mood("Jake", "neutral", 0.5)
        self.mgr.record_mood("Jake", "excited", 0.9)
        ctx = self.mgr.get_guest_context("Jake")
        assert "improving" in ctx