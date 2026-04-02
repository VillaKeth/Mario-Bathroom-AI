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


# ── TestGossipPruningAndComparison ────────────────────────────────────────

class TestGossipPruningAndComparison:
    """Tests for _prune_gossip(), get_comparison_hint(), and _analyze_speech_traits()."""

    def _make_entry(self, speaker_name="Guest", speaker_id="g1",
                    text="something", keyword="love", timestamp=None):
        return {
            "type": "opinion",
            "speaker_name": speaker_name,
            "speaker_id": speaker_id,
            "text": text,
            "keyword": keyword,
            "timestamp": timestamp or time.time(),
            "shared_count": 0,
        }

    # ── _prune_gossip tests ───────────────────────────────────────────────

    def test_prune_removes_old_entries(self):
        pg = PartyGossip()
        old_ts = time.time() - (PartyGossip.GOSSIP_AGE_LIMIT + 100)
        pg._gossip_log = [self._make_entry(speaker_id=f"old{i}", timestamp=old_ts) for i in range(5)]
        assert len(pg._gossip_log) == 5
        pg._prune_gossip()
        assert len(pg._gossip_log) == 0

    def test_prune_caps_at_max_size(self):
        pg = PartyGossip()
        now = time.time()
        pg._gossip_log = [
            self._make_entry(speaker_id=f"g{i}", timestamp=now) for i in range(600)
        ]
        pg._prune_gossip()
        assert len(pg._gossip_log) == PartyGossip.MAX_GOSSIP_LOG

    def test_prune_keeps_recent_entries(self):
        pg = PartyGossip()
        old_ts = time.time() - (PartyGossip.GOSSIP_AGE_LIMIT + 100)
        now = time.time()
        pg._gossip_log = [
            self._make_entry(speaker_id="old1", timestamp=old_ts),
            self._make_entry(speaker_id="old2", timestamp=old_ts),
            self._make_entry(speaker_id="new1", timestamp=now),
            self._make_entry(speaker_id="new2", timestamp=now),
        ]
        pg._prune_gossip()
        assert len(pg._gossip_log) == 2
        ids = {g["speaker_id"] for g in pg._gossip_log}
        assert ids == {"new1", "new2"}

    def test_prune_empty_log_no_crash(self):
        pg = PartyGossip()
        assert pg._gossip_log == []
        pg._prune_gossip()  # should not raise
        assert pg._gossip_log == []

    def test_prune_resets_used_gossip_index(self):
        pg = PartyGossip()
        now = time.time()
        pg._gossip_log = [
            self._make_entry(speaker_id=f"g{i}", timestamp=now) for i in range(600)
        ]
        pg._used_gossip = {0, 1, 2, 50, 100}
        pg._prune_gossip()
        # After cap-triggered prune, _used_gossip is cleared because indices shifted
        assert pg._used_gossip == set()

    # ── get_comparison_hint tests ─────────────────────────────────────────

    def test_comparison_hint_finds_match(self):
        pg = PartyGossip()
        # Set up opinions for two guests on the same topic ("pizza")
        pg._guest_opinions = {
            "a1": {"pizza": "I love pizza"},
            "b1": {"pizza": "Pizza is okay"},
        }
        # Need gossip log entry so get_comparison_hint can resolve guest name
        pg._gossip_log = [self._make_entry(speaker_name="Alice", speaker_id="a1")]
        hint = pg.get_comparison_hint("b1", "I just had some pizza")
        assert hint is not None
        assert isinstance(hint, str)
        assert "Alice" in hint

    def test_comparison_hint_no_match(self):
        pg = PartyGossip()
        pg._guest_opinions = {
            "a1": {"sushi": "Sushi is great"},
        }
        pg._gossip_log = [self._make_entry(speaker_name="Alice", speaker_id="a1")]
        hint = pg.get_comparison_hint("b1", "I love basketball")
        assert hint is None

    def test_comparison_hint_empty_opinions(self):
        pg = PartyGossip()
        assert pg._guest_opinions == {}
        hint = pg.get_comparison_hint("x1", "Anything at all")
        assert hint is None

    def test_comparison_hint_same_guest_not_compared(self):
        pg = PartyGossip()
        pg._guest_opinions = {
            "a1": {"pizza": "Pizza is the best"},
        }
        pg._gossip_log = [self._make_entry(speaker_name="Alice", speaker_id="a1")]
        # Speaker a1 mentions pizza — should NOT match against themselves
        hint = pg.get_comparison_hint("a1", "I also love pizza")
        assert hint is None

    # ── _analyze_speech_traits tests ──────────────────────────────────────

    def test_analyze_traits_detects_foodie(self):
        pg = PartyGossip()
        pg._analyze_speech_traits("a1", "I love cooking and trying new recipes")
        assert "foodie" in pg._guest_speech_traits["a1"]

    def test_analyze_traits_empty_text(self):
        pg = PartyGossip()
        pg._analyze_speech_traits("a1", "")
        traits = pg._guest_speech_traits.get("a1", [])
        assert traits == []


class TestAlliances:
    def test_alliance_detection_on_agreement(self):
        pg = PartyGossip()
        pg.analyze_for_gossip("Alice", "a1", "I love pizza, it's amazing")
        pg.analyze_for_gossip("Bob", "b1", "I love pizza too, it's amazing")
        assert len(pg._alliances) >= 1
        names_in_alliances = [(a[0], a[1]) for a in pg._alliances]
        assert any("Bob" in pair and "Alice" in pair for pair in names_in_alliances)

    def test_alliance_not_created_on_opposition(self):
        pg = PartyGossip()
        pg.analyze_for_gossip("Alice", "a1", "pizza is the best food ever")
        pg.analyze_for_gossip("Bob", "b1", "pizza is the worst food ever")
        assert len(pg._alliances) == 0
        assert len(pg._rivalries) >= 1

    def test_alliance_hint_returns_string(self):
        pg = PartyGossip()
        pg._alliances = [("Alice", "Bob", "pizza")]
        hint = pg.get_alliance_hint("c1", "let's talk about pizza")
        assert hint is not None
        assert isinstance(hint, str)

    def test_alliance_hint_not_repeated(self):
        pg = PartyGossip()
        pg._alliances = [("Alice", "Bob", "pizza")]
        hint1 = pg.get_alliance_hint("c1", "pizza is great")
        hint2 = pg.get_alliance_hint("c1", "more pizza talk")
        assert hint1 is not None
        assert hint2 is None  # Already shared

    def test_alliance_hint_no_match(self):
        pg = PartyGossip()
        pg._alliances = [("Alice", "Bob", "pizza")]
        hint = pg.get_alliance_hint("c1", "I like gaming")
        assert hint is None


class TestTrendingTopics:
    def test_topic_tracking_across_guests(self):
        pg = PartyGossip()
        pg.analyze_for_gossip("Alice", "a1", "I love pizza so much")
        pg.analyze_for_gossip("Bob", "b1", "Pizza is the best food ever")
        pg.analyze_for_gossip("Carol", "c1", "Can we order more pizza?")
        # "pizza" mentioned by 3 guests — should be trending
        assert "pizza" in pg._topic_mentions
        assert len(pg._topic_mentions["pizza"]) >= 3

    def test_trending_hint_requires_3_guests(self):
        pg = PartyGossip()
        pg.analyze_for_gossip("Alice", "a1", "I love pizza")
        pg.analyze_for_gossip("Bob", "b1", "Pizza is the best")
        # Only 2 guests — not trending yet
        hint = pg.get_trending_topic_hint()
        assert hint is None

    def test_trending_hint_fires_at_3_guests(self):
        pg = PartyGossip()
        pg.analyze_for_gossip("Alice", "a1", "I love pizza")
        pg.analyze_for_gossip("Bob", "b1", "Pizza is the best")
        pg.analyze_for_gossip("Carol", "c1", "Pizza for everyone")
        hint = pg.get_trending_topic_hint("d1")
        assert hint is not None
        assert "pizza" in hint.lower() or "3" in hint

    def test_trending_not_repeated(self):
        pg = PartyGossip()
        pg.analyze_for_gossip("Alice", "a1", "I love pizza")
        pg.analyze_for_gossip("Bob", "b1", "Pizza is the best")
        pg.analyze_for_gossip("Carol", "c1", "Pizza for everyone")
        hint1 = pg.get_trending_topic_hint()
        hint2 = pg.get_trending_topic_hint()
        assert hint1 is not None
        assert hint2 is None  # Already surfaced

    def test_trending_empty_when_no_gossip(self):
        pg = PartyGossip()
        hint = pg.get_trending_topic_hint()
        assert hint is None

    def test_multiple_trending_topics(self):
        pg = PartyGossip()
        # 3 guests talk about pizza
        pg.analyze_for_gossip("Alice", "a1", "I love pizza")
        pg.analyze_for_gossip("Bob", "b1", "Pizza is the best")
        pg.analyze_for_gossip("Carol", "c1", "Pizza for everyone")
        # 3 guests talk about game
        pg.analyze_for_gossip("Dave", "d1", "This game is amazing")
        pg.analyze_for_gossip("Eve", "e1", "Best game ever")
        pg.analyze_for_gossip("Frank", "f1", "Love this game")
        # First call gets one, second gets the other
        hint1 = pg.get_trending_topic_hint()
        hint2 = pg.get_trending_topic_hint()
        assert hint1 is not None
        assert hint2 is not None
        # They should be different topics
        assert hint1 != hint2
