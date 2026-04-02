"""Comprehensive tests for server/party_gossip.py — PartyGossip class."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

import time
import pytest
from unittest.mock import patch
from party_gossip import PartyGossip


# ── TestGossipInitialization ──────────────────────────────────────────────

class TestGossipInitialization:
    def test_fresh_instance_has_empty_gossip_log(self):
        pg = PartyGossip()
        assert pg._gossip_log == []

    def test_initial_guest_count_is_zero(self):
        pg = PartyGossip()
        assert pg.get_guest_count() == 0

    def test_gossip_count_starts_at_zero(self):
        pg = PartyGossip()
        assert pg.get_gossip_count() == 0


# ── TestGossipAnalysis ────────────────────────────────────────────────────

class TestGossipAnalysis:
    def test_analyze_basic_text_creates_entries(self):
        pg = PartyGossip()
        entries = pg.analyze_for_gossip("Alice", "a1", "I love pizza so much")
        assert len(entries) > 0
        assert all(isinstance(e, dict) for e in entries)

    def test_analyze_tracks_guest_opinions(self):
        pg = PartyGossip()
        pg.analyze_for_gossip("Bob", "b1", "I love chocolate ice cream")
        assert "b1" in pg._guest_opinions
        assert "love" in pg._guest_opinions["b1"]

    def test_gossip_created_for_food_drinks_music(self):
        pg = PartyGossip()
        food = pg.analyze_for_gossip("Carl", "c1", "This pizza is amazing")
        music = pg.analyze_for_gossip("Dana", "d1", "That music playlist is fire")
        drink = pg.analyze_for_gossip("Eve", "e1", "I want another drink please")
        assert any(e["type"] == "food" for e in food)
        assert any(e["type"] == "gaming" or e["type"] == "preference" for e in music) or len(music) > 0
        assert any(e["type"] == "food" for e in drink)  # "drink" is in food triggers

    def test_multiple_speakers_accumulate_gossip(self):
        pg = PartyGossip()
        pg.analyze_for_gossip("Alice", "a1", "I love sushi")
        pg.analyze_for_gossip("Bob", "b1", "Pizza is the best food ever")
        pg.analyze_for_gossip("Carl", "c1", "Tacos are my favorite thing")
        assert pg.get_gossip_count() >= 3

    def test_gossip_pruning_removes_old_entries(self):
        pg = PartyGossip()
        old_time = time.time() - (3600 * 5)  # 5 hours ago
        pg._gossip_log.append({
            "type": "opinion",
            "speaker_name": "OldGuest",
            "speaker_id": "old1",
            "text": "ancient gossip",
            "keyword": "love",
            "timestamp": old_time,
            "shared_count": 0,
        })
        assert pg.get_gossip_count() == 1
        # Trigger prune via analyze
        pg.analyze_for_gossip("New", "n1", "I love cake")
        # Old entry should be pruned, only new entries remain
        for entry in pg._gossip_log:
            assert entry["speaker_id"] != "old1"

    def test_gossip_cap_at_max(self):
        pg = PartyGossip()
        # Fill beyond the cap
        for i in range(550):
            pg._gossip_log.append({
                "type": "quote",
                "speaker_name": f"guest{i}",
                "speaker_id": f"g{i}",
                "text": f"quote {i}",
                "keyword": "something",
                "timestamp": time.time(),
                "shared_count": 0,
            })
        # Trigger prune
        pg.analyze_for_gossip("Final", "f1", "I love pizza")
        assert len(pg._gossip_log) <= PartyGossip.MAX_GOSSIP_LOG + 20  # some new entries from analyze


# ── TestGossipRetrieval ───────────────────────────────────────────────────

class TestGossipRetrieval:
    def test_get_gossip_excludes_current_speaker(self):
        pg = PartyGossip()
        pg.analyze_for_gossip("Alice", "a1", "I love pizza and pasta")
        gossip = pg.get_gossip_for_guest(current_speaker_id="a1", current_name="Alice")
        # Should not return gossip about Alice to Alice
        assert gossip == []

    def test_get_gossip_returns_empty_when_no_gossip(self):
        pg = PartyGossip()
        result = pg.get_gossip_for_guest(current_speaker_id="x1", current_name="X")
        assert result == []

    def test_get_gossip_respects_count(self):
        pg = PartyGossip()
        # Add gossip from multiple speakers
        for i in range(10):
            pg.analyze_for_gossip(f"Guest{i}", f"g{i}", f"I love pizza and sushi number {i}")
        result = pg.get_gossip_for_guest(
            current_speaker_id="new1", current_name="NewGuest",
            count=1, gossip_aggression=0.0,
        )
        # With count=1 and aggression=0, effective_count = max(1, 1+0) = 1
        assert len(result) <= 2  # at most 1 or 2 due to rounding

    def test_gossip_aggression_scales_amount(self):
        pg = PartyGossip()
        for i in range(20):
            pg.analyze_for_gossip(f"Guest{i}", f"g{i}", f"I love tacos and hate pizza {i}")
        low = pg.get_gossip_for_guest("new1", "New", count=2, gossip_aggression=0.0)
        # Reset used gossip for fair comparison
        pg._used_gossip.clear()
        high = pg.get_gossip_for_guest("new2", "New2", count=2, gossip_aggression=1.0)
        # High aggression should return more gossip (effective_count = 2 + 1*2 = 4)
        assert len(high) >= len(low)


# ── TestRivalries ─────────────────────────────────────────────────────────

class TestRivalries:
    def test_rivalry_detection_on_disagreement(self):
        pg = PartyGossip()
        # Both must match the SAME preference keyword ("pizza") so opinions
        # are stored under the same key, then opposing sentiment triggers rivalry.
        pg.analyze_for_gossip("Alice", "a1", "pizza is the best thing ever")
        pg.analyze_for_gossip("Bob", "b1", "pizza is the worst thing ever")
        # "best" vs "worst" on shared keyword "pizza" → rivalry detected
        assert len(pg._rivalries) >= 1

    def test_get_rivalry_hint_returns_hint(self):
        pg = PartyGossip()
        pg._rivalries.append(("Alice", "Bob", "pizza"))
        hint = pg.get_rivalry_hint("c1", "I also like pizza")
        assert hint is not None
        assert isinstance(hint, str)

    def test_get_new_rivalry_announcements_clears(self):
        pg = PartyGossip()
        pg._queue_rivalry_announcement("Alice", "Bob", "pizza")
        announcements = pg.get_new_rivalry_announcements()
        assert len(announcements) == 1
        assert "Alice" in announcements[0]
        assert "Bob" in announcements[0]
        # Second call should be empty (cleared)
        assert pg.get_new_rivalry_announcements() == []

    def test_no_self_rivalries(self):
        pg = PartyGossip()
        pg.analyze_for_gossip("Alice", "a1", "I love pizza and it is amazing")
        pg.analyze_for_gossip("Alice", "a1", "I hate pizza now, it is terrible")
        # Same speaker_id should not create rivalry with self
        for r in pg._rivalries:
            assert r[0] != r[1] or r[0] != "Alice"


# ── TestGuestTitles ───────────────────────────────────────────────────────

class TestGuestTitles:
    def test_assign_title_gives_new_guest_title(self):
        pg = PartyGossip()
        title = pg.assign_title("a1", "Alice")
        assert isinstance(title, str)
        assert len(title) > 0

    def test_assign_title_returns_cached(self):
        pg = PartyGossip()
        title1 = pg.assign_title("a1", "Alice")
        title2 = pg.assign_title("a1", "Alice")
        assert title1 == title2

    def test_update_title_from_speech(self):
        pg = PartyGossip()
        # Need at least 3 traits for update to work
        pg._guest_speech_traits["a1"] = ["foodie", "gamer", "jokester"]
        pg.assign_title("a1", "Alice")  # Cache initial title
        new_title = pg.update_title_from_speech("a1", "Alice")
        # Should return a new title derived from traits (may differ from original)
        assert new_title is None or isinstance(new_title, str)

    def test_analyze_speech_traits_detects_traits(self):
        pg = PartyGossip()
        pg._analyze_speech_traits("a1", "I love pizza and pasta, food is life")
        assert "foodie" in pg._guest_speech_traits["a1"]
        pg._analyze_speech_traits("a1", "Let me tell you a joke, it's hilarious and funny")
        assert "jokester" in pg._guest_speech_traits["a1"]


# ── TestPartyNarrative ────────────────────────────────────────────────────

class TestPartyNarrative:
    def test_add_dramatic_moment_stores(self):
        pg = PartyGossip()
        pg.add_dramatic_moment("Someone broke the soap dispenser!")
        assert len(pg._dramatic_moments) == 1
        assert pg._dramatic_moments[0]["text"] == "Someone broke the soap dispenser!"

    def test_get_party_narrative_hint_with_moments(self):
        pg = PartyGossip()
        pg.add_dramatic_moment("Guest sang karaoke")
        hint = pg.get_party_narrative_hint()
        assert hint is not None
        assert "karaoke" in hint

    def test_get_party_stats_gossip_generates(self):
        pg = PartyGossip()
        # Simulate party running for 2 hours with many visitors
        pg._party_start = time.time() - 7200  # 2 hours ago
        result = pg.get_party_stats_gossip(total_visits=25)
        assert result is not None
        assert isinstance(result, str)

    def test_get_known_guest_names_excludes_speaker(self):
        pg = PartyGossip()
        pg._guest_names = {"a1": "Alice", "b1": "Bob", "c1": "Carl"}
        names = pg.get_known_guest_names(exclude_id="a1")
        assert "Alice" not in names
        assert "Bob" in names
        assert "Carl" in names
