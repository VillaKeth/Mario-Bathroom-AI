"""Tests for GuestProfile system — unified guest identity management."""
import pytest
import time
import threading
from datetime import datetime, timedelta

from server.guest_profiles import GuestProfile, MoodEntry, GuestProfileManager


class TestGuestProfile:
    """Tests for GuestProfile dataclass."""

    def test_create_profile_defaults(self):
        p = GuestProfile(name="Jake")
        assert p.name == "Jake"
        assert p.guest_id  # UUID generated
        assert p.voice_id is None
        assert p.face_ids == []
        assert p.visit_count == 1
        assert p.total_interactions == 0
        assert p.mood_history == []
        assert p.topics_discussed == []

    def test_current_mood_empty(self):
        p = GuestProfile(name="Jake")
        assert p.current_mood == "neutral"
        assert p.current_energy == 0.5

    def test_current_mood_with_entries(self):
        p = GuestProfile(name="Jake")
        p.mood_history.append(MoodEntry(timestamp=datetime.now(), emotion="excited", energy=0.9))
        assert p.current_mood == "excited"
        assert p.current_energy == 0.9

    def test_mood_trend_stable(self):
        p = GuestProfile(name="Jake")
        assert p.mood_trend == "stable"  # no history

    def test_mood_trend_improving(self):
        p = GuestProfile(name="Jake")
        now = datetime.now()
        p.mood_history = [
            MoodEntry(timestamp=now - timedelta(minutes=10), emotion="sad", energy=0.2),
            MoodEntry(timestamp=now - timedelta(minutes=5), emotion="neutral", energy=0.5),
            MoodEntry(timestamp=now, emotion="excited", energy=0.9),
        ]
        assert p.mood_trend == "improving"

    def test_mood_trend_declining(self):
        p = GuestProfile(name="Jake")
        now = datetime.now()
        p.mood_history = [
            MoodEntry(timestamp=now - timedelta(minutes=10), emotion="excited", energy=0.9),
            MoodEntry(timestamp=now - timedelta(minutes=5), emotion="neutral", energy=0.5),
            MoodEntry(timestamp=now, emotion="sad", energy=0.2),
        ]
        assert p.mood_trend == "declining"


class TestGuestProfileManager:
    """Tests for GuestProfileManager — identity management."""

    def setup_method(self):
        self.mgr = GuestProfileManager()

    def test_identify_by_voice_new_guest(self):
        profile = self.mgr.identify_by_voice("Jake", "voice_001")
        assert profile.name == "Jake"
        assert profile.voice_id == "voice_001"
        assert "Jake" in self.mgr.get_active_guests()

    def test_identify_by_voice_returning_guest(self):
        p1 = self.mgr.identify_by_voice("Jake", "voice_001")
        p2 = self.mgr.identify_by_voice("Jake", "voice_001")
        assert p1 is p2  # Same object
        assert p2.total_interactions == 2  # Incremented

    def test_identify_by_face_new_guest(self):
        profile = self.mgr.identify_by_face("Lisa", "face_abc")
        assert profile.name == "Lisa"
        assert "face_abc" in profile.face_ids

    def test_merge_voice_and_face_same_name(self):
        """Voice identifies Jake, then face identifies Jake — same profile."""
        p_voice = self.mgr.identify_by_voice("Jake", "voice_001")
        p_face = self.mgr.identify_by_face("Jake", "face_abc")
        assert p_voice is p_face
        assert p_face.voice_id == "voice_001"
        assert "face_abc" in p_face.face_ids

    def test_create_mystery_guest(self):
        m1 = self.mgr.create_mystery_guest()
        m2 = self.mgr.create_mystery_guest()
        assert m1.name == "Mystery Guest #1"
        assert m2.name == "Mystery Guest #2"

    def test_rename_guest(self):
        mystery = self.mgr.create_mystery_guest()
        assert mystery.name == "Mystery Guest #1"
        renamed = self.mgr.rename_guest("Mystery Guest #1", "Jake")
        assert renamed.name == "Jake"
        assert "Jake" in self.mgr._profiles
        assert "Mystery Guest #1" not in self.mgr._profiles

    def test_rename_updates_voice_map(self):
        self.mgr.identify_by_voice("Mystery Guest #1", "voice_001")
        self.mgr.rename_guest("Mystery Guest #1", "Jake")
        assert self.mgr._voice_map["voice_001"] == "Jake"

    def test_record_mood(self):
        self.mgr.identify_by_voice("Jake", "voice_001")
        self.mgr.record_mood("Jake", "excited", 0.9)
        profile = self.mgr._profiles["Jake"]
        assert len(profile.mood_history) == 1
        assert profile.mood_history[0].emotion == "excited"

    def test_record_topic(self):
        self.mgr.identify_by_voice("Jake", "voice_001")
        self.mgr.record_topic("Jake", "Deltarune")
        self.mgr.record_topic("Jake", "Lisa Webb toast")
        profile = self.mgr._profiles["Jake"]
        assert "Deltarune" in profile.topics_discussed
        assert len(profile.topics_discussed) == 2

    def test_topic_dedup(self):
        self.mgr.identify_by_voice("Jake", "voice_001")
        self.mgr.record_topic("Jake", "Deltarune")
        self.mgr.record_topic("Jake", "Deltarune")
        assert len(self.mgr._profiles["Jake"].topics_discussed) == 1

    def test_guest_enter_exit(self):
        self.mgr.identify_by_voice("Jake", "voice_001")
        assert "Jake" in self.mgr.get_active_guests()
        self.mgr.guest_exited("Jake")
        assert "Jake" not in self.mgr.get_active_guests()
        self.mgr.guest_entered("Jake")
        assert "Jake" in self.mgr.get_active_guests()
        assert self.mgr._profiles["Jake"].visit_count == 2

    def test_get_guest_context_basic(self):
        self.mgr.identify_by_voice("Jake", "voice_001")
        ctx = self.mgr.get_guest_context("Jake")
        assert "Jake" in ctx
        assert "voice-confirmed" in ctx

    def test_get_guest_context_with_mood(self):
        self.mgr.identify_by_voice("Jake", "voice_001")
        self.mgr.record_mood("Jake", "excited", 0.9)
        ctx = self.mgr.get_guest_context("Jake")
        assert "excited" in ctx
        assert "0.9" in ctx

    def test_get_guest_context_with_others(self):
        self.mgr.identify_by_voice("Jake", "voice_001")
        self.mgr.identify_by_voice("Lisa", "voice_002")
        ctx = self.mgr.get_guest_context("Jake")
        assert "Lisa" in ctx

    def test_register_vip(self):
        self.mgr.register_vip("Jacob", voice_id="vip_voice_001")
        assert "Jacob" in self.mgr._profiles
        profile = self.mgr._profiles["Jacob"]
        assert profile.voice_id == "vip_voice_001"

    def test_thread_safety_concurrent_identify(self):
        """Concurrent voice identifications don't corrupt state."""
        errors = []
        def identify_guest(name, vid):
            try:
                for _ in range(50):
                    self.mgr.identify_by_voice(name, vid)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=identify_guest, args=("Jake", "v1")),
            threading.Thread(target=identify_guest, args=("Lisa", "v2")),
            threading.Thread(target=identify_guest, args=("Carl", "v3")),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors
        assert len(self.mgr._profiles) == 3

    def test_get_unknown_guest_context(self):
        ctx = self.mgr.get_guest_context("Nobody")
        assert "Unknown" in ctx

    def test_greeting_debounce(self):
        self.mgr.identify_by_voice("Jake", "v1")
        assert self.mgr.should_greet("Jake") is True
        assert self.mgr.should_greet("Jake") is False  # Too soon

    def test_greeting_debounce_different_guests(self):
        self.mgr.identify_by_voice("Jake", "v1")
        self.mgr.identify_by_voice("Lisa", "v2")
        assert self.mgr.should_greet("Jake") is True
        assert self.mgr.should_greet("Lisa") is True  # Different guest, OK