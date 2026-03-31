"""Tests for birthday_vip, sound_events, and catchphrase_mirror modules."""

import os
import sys
import pytest

# Ensure server/ is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

from birthday_vip import BirthdayVIP
from sound_events import SoundEventManager
from catchphrase_mirror import CatchphraseMirror


# ── Birthday VIP Tests ──

class TestBirthdayVIP:
    def test_unconfigured_returns_false(self):
        vip = BirthdayVIP(name="")
        assert not vip.is_configured()
        assert not vip.is_birthday_person("Anyone")
        assert vip.get_vip_prompt_injection() == ""

    def test_exact_name_match(self):
        vip = BirthdayVIP(name="Mike")
        assert vip.is_birthday_person("Mike")
        assert vip.is_birthday_person("mike")
        assert not vip.is_birthday_person("Steve")

    def test_fuzzy_name_match(self):
        vip = BirthdayVIP(name="Michael")
        assert vip.is_birthday_person("michael")  # case insensitive
        # Partial substring match
        vip2 = BirthdayVIP(name="Mike")
        assert vip2.is_birthday_person("Mikey")  # "mike" in "mikey"

    def test_vip_prompt_injection_contains_name(self):
        vip = BirthdayVIP(name="Sarah", birthday_facts=["Loves cats"])
        prompt = vip.get_vip_prompt_injection()
        assert "SARAH" in prompt
        assert "BIRTHDAY" in prompt
        assert "Loves cats" in prompt

    def test_interaction_count_increments(self):
        vip = BirthdayVIP(name="Alex")
        assert vip.interaction_count == 0
        vip.get_vip_prompt_injection()
        assert vip.interaction_count == 1
        vip.get_vip_prompt_injection()
        assert vip.interaction_count == 2

    def test_special_greeting(self):
        vip = BirthdayVIP(name="Kai")
        greeting = vip.get_special_greeting("Kai")
        assert greeting is not None
        assert "Kai" in greeting
        assert vip.get_special_greeting("RandomPerson") is None


# ── Sound Events Tests ──

class TestSoundEventManager:
    def test_no_dir_graceful(self, tmp_path):
        mgr = SoundEventManager(sfx_dir=str(tmp_path / "nonexistent"))
        assert not mgr.is_available()
        # trigger should not raise
        mgr.trigger("greeting")

    def test_available_with_wav(self, tmp_path):
        # Create a fake WAV file
        sfx_dir = tmp_path / "sfx"
        sfx_dir.mkdir()
        (sfx_dir / "coin.wav").write_bytes(b"RIFF" + b"\x00" * 40)
        mgr = SoundEventManager(sfx_dir=str(sfx_dir))
        assert mgr.is_available()
        assert "greeting" in mgr.get_available_events()

    def test_trigger_unknown_event(self, tmp_path):
        mgr = SoundEventManager(sfx_dir=str(tmp_path))
        # Should not raise
        mgr.trigger("nonexistent_event")

    def test_websocket_message(self):
        mgr = SoundEventManager()
        msg = mgr.trigger_websocket("greeting")
        assert msg is not None
        assert msg["type"] == "sound_effect"
        assert msg["event"] == "greeting"
        assert mgr.trigger_websocket("fake_event") is None


# ── Catchphrase Mirror Tests ──

class TestCatchphraseMirror:
    def test_no_mirror_below_threshold(self):
        mirror = CatchphraseMirror(threshold=3)
        mirror.feed("Bob", "pizza is great")
        mirror.feed("Bob", "pizza rocks")
        assert mirror.get_mirror_phrase("Bob") is None

    def test_mirror_at_threshold(self):
        mirror = CatchphraseMirror(threshold=3)
        mirror.feed("Alice", "I love pizza so much")
        mirror.feed("Alice", "pizza pizza pizza")
        mirror.feed("Alice", "more pizza please")
        phrase = mirror.get_mirror_phrase("Alice")
        assert phrase is not None
        assert "pizza" in phrase.lower()

    def test_stop_words_excluded(self):
        mirror = CatchphraseMirror(threshold=3)
        # "the" is a stop word — should not be tracked
        mirror.feed("Carl", "the the the the the")
        assert mirror.get_mirror_phrase("Carl") is None

    def test_party_catchphrases(self):
        mirror = CatchphraseMirror(threshold=2)
        mirror.feed("dave", "awesome awesome awesome")
        mirror.feed("eve", "fantastic fantastic")
        report = mirror.get_party_catchphrases()
        assert "dave" in report
        assert any(word == "awesome" for word, _ in report["dave"])

    def test_no_double_mirror(self):
        """Once a phrase is mirrored, it shouldn't trigger again."""
        mirror = CatchphraseMirror(threshold=3)
        mirror.feed("Frank", "amazing amazing amazing amazing")
        first = mirror.get_mirror_phrase("Frank")
        assert first is not None
        # Same word shouldn't trigger again
        second = mirror.get_mirror_phrase("Frank")
        assert second is None

    def test_reset(self):
        mirror = CatchphraseMirror(threshold=3)
        mirror.feed("Grace", "wonderful wonderful wonderful")
        mirror.reset()
        assert mirror.get_mirror_phrase("Grace") is None
        assert mirror.get_party_catchphrases() == {}
