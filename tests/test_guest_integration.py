"""Integration tests for the full guest intelligence pipeline."""
import pytest
import threading
from datetime import datetime
from server.guest_profiles import GuestProfile, MoodEntry, GuestProfileManager


class TestGuestIntelligenceIntegration:
    """End-to-end scenarios simulating real party flow."""

    def setup_method(self):
        self.mgr = GuestProfileManager()

    def test_full_guest_lifecycle(self):
        """Voice ID → face link → mood track → context → exit → return."""
        p = self.mgr.identify_by_voice("Jake", "v1")
        assert p.total_interactions == 1

        p2 = self.mgr.identify_by_face("Jake", "face_001")
        assert p is p2
        assert "face_001" in p.face_ids

        self.mgr.record_mood("Jake", "nervous", 0.3)
        self.mgr.record_mood("Jake", "happy", 0.7)
        self.mgr.record_mood("Jake", "excited", 0.9)
        assert p.mood_trend == "improving"

        self.mgr.record_topic("Jake", "Deltarune")
        self.mgr.record_topic("Jake", "birthday cake")

        ctx = self.mgr.get_guest_context("Jake")
        assert "Jake" in ctx
        assert "excited" in ctx
        assert "improving" in ctx

        self.mgr.guest_exited("Jake")
        assert "Jake" not in self.mgr.get_active_guests()
        self.mgr.guest_entered("Jake")
        assert p.visit_count == 2

    def test_multi_guest_party_scenario(self):
        """5 guests arrive, interact, some leave."""
        names = ["Jake", "Lisa", "Carl", "Stacy", "Dave"]
        for i, name in enumerate(names):
            self.mgr.identify_by_voice(name, f"v{i}")

        assert len(self.mgr.get_active_guests()) == 5

        self.mgr.record_mood("Jake", "excited", 0.9)
        self.mgr.record_mood("Lisa", "happy", 0.7)
        self.mgr.record_mood("Carl", "nervous", 0.3)

        ctx = self.mgr.get_guest_context("Jake")
        assert "Lisa" in ctx or "Carl" in ctx

        self.mgr.guest_exited("Carl")
        self.mgr.guest_exited("Dave")
        assert len(self.mgr.get_active_guests()) == 3

    def test_mystery_guest_renamed(self):
        """Unknown face → mystery guest → voice identifies → rename."""
        mystery = self.mgr.create_mystery_guest()
        assert "Mystery Guest" in mystery.name

        self.mgr.rename_guest(mystery.name, "Jake")
        self.mgr.identify_by_voice("Jake", "v1")

        profile = self.mgr._profiles["Jake"]
        assert profile.voice_id == "v1"
        assert "Mystery Guest" not in self.mgr._profiles

    def test_vip_preregistered_recognized_immediately(self):
        """Jacob is VIP — recognized on first interaction."""
        self.mgr.register_vip("Jacob", voice_id="vip_001")
        profile = self.mgr._profiles["Jacob"]

        p = self.mgr.identify_by_voice("Jacob", "vip_001")
        assert p is profile
        assert p.total_interactions == 1

    def test_concurrent_guest_interactions(self):
        """Thread-safe handling of multiple simultaneous interactions."""
        errors = []
        def interact(name, vid):
            try:
                for i in range(20):
                    self.mgr.identify_by_voice(name, vid)
                    self.mgr.record_mood(name, "happy", 0.7)
                    self.mgr.record_topic(name, f"topic_{i}")
                    _ = self.mgr.get_guest_context(name)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=interact, args=("Jake", "v1")),
            threading.Thread(target=interact, args=("Lisa", "v2")),
            threading.Thread(target=interact, args=("Carl", "v3")),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors
        assert len(self.mgr._profiles) == 3