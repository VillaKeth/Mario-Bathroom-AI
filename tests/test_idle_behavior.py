"""Comprehensive tests for server/idle_behavior.py — IdleBehavior class."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

import pytest
import time
import random
from unittest.mock import patch, MagicMock
from idle_behavior import (
    IdleBehavior,
    IDLE_MUMBLES,
    MARIO_JOKES,
    MARIO_TRIVIA,
    MARIO_SONGS,
    NOISE_REACTIONS,
    MARIO_CHALLENGES,
    MARIO_COMPLIMENTS,
    HAND_WASH_REMINDERS,
    PLUMBING_FACTS,
    LONELY_MILD,
    LONELY_MEDIUM,
    LONELY_DEEP,
)


# ── Helpers ──────────────────────────────────────────────────────────────

def _make_history(messages: list[str], role: str = "user") -> list[dict]:
    """Build a minimal conversation_history list."""
    return [{"role": role, "content": m} for m in messages]


# ── TestIdleInitialization ───────────────────────────────────────────────

class TestIdleInitialization:
    """Verify fresh instance state."""

    def test_action_count_starts_at_zero(self):
        ib = IdleBehavior()
        assert ib._action_count == 0

    def test_memorial_not_yet_delivered(self):
        ib = IdleBehavior()
        assert ib._memorial_delivered is False
        assert ib._memorial_shot_delivered is False

    def test_party_start_time_is_set(self):
        before = time.time()
        ib = IdleBehavior()
        after = time.time()
        assert before <= ib._party_start_time <= after


# ── TestIdleActions ──────────────────────────────────────────────────────

class TestIdleActions:
    """get_idle_action timing, phases, counts, intervals."""

    def test_returns_none_if_called_too_quickly(self):
        ib = IdleBehavior()
        # First call should return None because _last_idle_action was just set
        result = ib.get_idle_action()
        assert result is None

    @patch("idle_behavior.time")
    def test_returns_string_after_interval(self, mock_time):
        mock_time.time.return_value = 1000.0
        mock_time.localtime.return_value = time.localtime(1000.0)
        ib = IdleBehavior()

        # Advance past the 15-second default interval
        mock_time.time.return_value = 1020.0
        result = ib.get_idle_action()
        assert isinstance(result, str)
        assert len(result) > 0

    @patch("idle_behavior.time")
    def test_respects_phase_parameter(self, mock_time):
        mock_time.time.return_value = 1000.0
        mock_time.localtime.return_value = time.localtime(1000.0)
        ib = IdleBehavior()

        # Test each phase value produces a string
        for phase in (1, 2, 3, 4):
            mock_time.time.return_value += 100
            result = ib.get_idle_action(phase=phase)
            assert isinstance(result, str), f"phase={phase} should return a string"

    @patch("idle_behavior.time")
    def test_action_count_increments(self, mock_time):
        mock_time.time.return_value = 1000.0
        mock_time.localtime.return_value = time.localtime(1000.0)
        ib = IdleBehavior()

        for i in range(1, 4):
            mock_time.time.return_value += 200
            ib.get_idle_action()
            assert ib._action_count == i

    @patch("idle_behavior.time")
    def test_idle_interval_grows(self, mock_time):
        mock_time.time.return_value = 1000.0
        mock_time.localtime.return_value = time.localtime(1000.0)
        ib = IdleBehavior()

        intervals = []
        for _ in range(5):
            mock_time.time.return_value += 200
            ib.get_idle_action()
            intervals.append(ib._idle_interval)

        # Each interval should be >= previous (formula: min(90, 15 + count*5))
        for a, b in zip(intervals, intervals[1:]):
            assert b >= a

    def test_reset_timer_resets_count_and_interval(self):
        ib = IdleBehavior()
        ib._action_count = 10
        ib._idle_interval = 65
        ib.reset_timer()
        assert ib._action_count == 0
        assert ib._idle_interval == 15


# ── TestContentPools ─────────────────────────────────────────────────────

class TestContentPools:
    """Each content getter should return a non-empty string."""

    def test_get_joke_returns_string(self):
        ib = IdleBehavior()
        joke = ib.get_joke()
        assert isinstance(joke, str) and len(joke) > 0
        assert joke in MARIO_JOKES

    def test_get_trivia_returns_string(self):
        ib = IdleBehavior()
        trivia = ib.get_trivia()
        assert isinstance(trivia, str) and len(trivia) > 0
        assert trivia in (MARIO_TRIVIA + PLUMBING_FACTS)

    def test_get_song_returns_string(self):
        ib = IdleBehavior()
        song = ib.get_song()
        assert isinstance(song, str) and len(song) > 0
        assert song in MARIO_SONGS

    def test_get_noise_reaction_returns_string(self):
        ib = IdleBehavior()
        reaction = ib.get_noise_reaction()
        assert isinstance(reaction, str) and len(reaction) > 0
        assert reaction in NOISE_REACTIONS

    def test_get_challenge_returns_string(self):
        ib = IdleBehavior()
        challenge = ib.get_challenge()
        assert isinstance(challenge, str) and len(challenge) > 0
        assert challenge in MARIO_CHALLENGES

    def test_get_compliment_returns_string(self):
        ib = IdleBehavior()
        compliment = ib.get_compliment()
        assert isinstance(compliment, str) and len(compliment) > 0
        assert compliment in MARIO_COMPLIMENTS

    def test_get_hand_wash_reminder_returns_string(self):
        ib = IdleBehavior()
        reminder = ib.get_hand_wash_reminder()
        assert isinstance(reminder, str) and len(reminder) > 0
        assert reminder in HAND_WASH_REMINDERS


# ── TestUniqueSelection ──────────────────────────────────────────────────

class TestUniqueSelection:
    """_pick_unique deduplication logic."""

    def test_never_same_item_twice_in_row(self):
        ib = IdleBehavior()
        # Pool must be larger than the global_recent window (15) to guarantee
        # the dedup logic always has fresh items available.
        pool = [f"item_{i}" for i in range(20)]
        prev = None
        for _ in range(15):
            pick = ib._pick_unique(pool, "test_pool")
            if prev is not None:
                assert pick != prev, "Should not return same item consecutively"
            prev = pick

    def test_works_with_single_item_pool(self):
        ib = IdleBehavior()
        result = ib._pick_unique(["only_one"], "single")
        assert result == "only_one"

    def test_cycles_through_all_items(self):
        ib = IdleBehavior()
        pool = ["a", "b", "c", "d"]
        seen = set()
        # Enough calls to cycle through all items
        for _ in range(40):
            seen.add(ib._pick_unique(pool, "cycle_test"))
        assert seen == set(pool)

    def test_handles_empty_pool(self):
        ib = IdleBehavior()
        result = ib._pick_unique([], "empty")
        assert result == "..."


# ── TestMemorialEvent ────────────────────────────────────────────────────

class TestMemorialEvent:
    """check_memorial_event timing and one-shot behaviour."""

    @patch("idle_behavior.time")
    def test_returns_none_before_45_minutes(self, mock_time):
        mock_time.time.return_value = 1000.0
        ib = IdleBehavior()
        # 30 minutes later
        mock_time.time.return_value = 1000.0 + 30 * 60
        assert ib.check_memorial_event() is None

    @patch("idle_behavior.time")
    def test_returns_message_at_45_minutes(self, mock_time):
        mock_time.time.return_value = 1000.0
        ib = IdleBehavior()
        # 46 minutes later
        mock_time.time.return_value = 1000.0 + 46 * 60
        result = ib.check_memorial_event()
        assert result is not None
        assert isinstance(result, str)

    @patch("idle_behavior.time")
    def test_fires_only_once_then_shot_then_none(self, mock_time):
        mock_time.time.return_value = 1000.0
        ib = IdleBehavior()
        mock_time.time.return_value = 1000.0 + 50 * 60

        first = ib.check_memorial_event()   # moment of silence
        assert first is not None
        second = ib.check_memorial_event()   # shot dedication
        assert second is not None
        third = ib.check_memorial_event()    # nothing left
        assert third is None

    @patch("idle_behavior.time")
    def test_memorial_mentions_lisa_webb(self, mock_time):
        mock_time.time.return_value = 1000.0
        ib = IdleBehavior()
        mock_time.time.return_value = 1000.0 + 50 * 60
        msg = ib.check_memorial_event()
        assert "Lisa Webb" in msg or "Lisa" in msg


# ── TestContextualBehavior ───────────────────────────────────────────────

class TestContextualBehavior:
    """get_long_stay_comment, get_contextual_idle, get_time_comment."""

    def test_long_stay_none_for_short_stay(self):
        ib = IdleBehavior()
        assert ib.get_long_stay_comment(1.5) is None

    def test_long_stay_returns_string_for_long_stay(self):
        ib = IdleBehavior()
        result = ib.get_long_stay_comment(7)
        assert isinstance(result, str) and len(result) > 0

    def test_contextual_idle_none_with_empty_history(self):
        ib = IdleBehavior()
        assert ib.get_contextual_idle([]) is None

    def test_contextual_idle_none_with_short_history(self):
        ib = IdleBehavior()
        assert ib.get_contextual_idle([{"role": "user", "content": "hi"}]) is None

    @patch("idle_behavior.random.random", return_value=0.1)
    @patch("idle_behavior.random.choice", side_effect=lambda x: x[0])
    def test_contextual_idle_returns_string_with_keyword(self, _choice, _rand):
        ib = IdleBehavior()
        history = _make_history(["hello there", "I love pizza and pasta so much"])
        result = ib.get_contextual_idle(history)
        assert isinstance(result, str) and len(result) > 0

    @patch("idle_behavior.time")
    def test_get_time_comment_returns_string(self, mock_time):
        mock_time.time.return_value = 1000.0
        ib = IdleBehavior()
        # Force cooldown to be satisfied
        ib._last_time_comment_at = 0
        result = ib.get_time_comment()
        assert result is None or isinstance(result, str)

    @patch("idle_behavior.time")
    def test_get_time_comment_respects_cooldown(self, mock_time):
        mock_time.time.return_value = 5000.0
        ib = IdleBehavior()
        ib._last_time_comment_at = 5000.0
        # Within 90-second cooldown
        mock_time.time.return_value = 5050.0
        result = ib.get_time_comment()
        assert result is None


# ── TestReengagementAndGames ─────────────────────────────────────────────

class TestReengagementAndGames:
    """get_reengagement_question and get_game_suggestion."""

    def test_reengagement_none_for_low_exchange(self):
        ib = IdleBehavior()
        assert ib.get_reengagement_question(exchange_count=1, seconds_quiet=30) is None

    @patch("idle_behavior.random.random", return_value=0.1)
    def test_reengagement_returns_string_for_high_exchange(self, _rand):
        ib = IdleBehavior()
        result = ib.get_reengagement_question(exchange_count=10, seconds_quiet=20)
        assert isinstance(result, str) and len(result) > 0

    def test_reengagement_none_for_short_silence(self):
        ib = IdleBehavior()
        assert ib.get_reengagement_question(exchange_count=10, seconds_quiet=5) is None

    def test_game_suggestion_none_for_low_exchange(self):
        ib = IdleBehavior()
        assert ib.get_game_suggestion(exchange_count=1) is None

    @patch("idle_behavior.random.random", return_value=0.1)
    def test_game_suggestion_returns_string_when_conditions_met(self, _rand):
        ib = IdleBehavior()
        result = ib.get_game_suggestion(exchange_count=10, detected_mood="energetic")
        assert isinstance(result, str) and len(result) > 0

    @patch("idle_behavior.random.random", return_value=0.1)
    def test_game_suggestion_mood_based(self, _rand):
        ib = IdleBehavior()
        for mood in ("drunk", "sad", "energetic"):
            ib._last_game_suggest = -100  # reset cooldown
            result = ib.get_game_suggestion(exchange_count=10, detected_mood=mood)
            assert isinstance(result, str), f"mood={mood} should return a string"

    @patch("idle_behavior.random.random", return_value=0.1)
    def test_game_suggestion_guest_type(self, _rand):
        ib = IdleBehavior()
        for gtype in ("shy", "curious", "storyteller"):
            ib._last_game_suggest = -100
            result = ib.get_game_suggestion(exchange_count=10, guest_type=gtype)
            assert isinstance(result, str), f"guest_type={gtype} should return a string"


# ── TestEdgeCases ────────────────────────────────────────────────────────

class TestEdgeCases:
    """Additional edge-case coverage."""

    def test_get_joke_cycles_deterministically(self):
        ib = IdleBehavior()
        ib._joke_index = 0
        first = ib.get_joke()
        second = ib.get_joke()
        assert first == MARIO_JOKES[0]
        assert second == MARIO_JOKES[1]

    def test_get_song_cycles_deterministically(self):
        ib = IdleBehavior()
        ib._song_index = 0
        assert ib.get_song() == MARIO_SONGS[0]
        assert ib.get_song() == MARIO_SONGS[1]

    def test_long_stay_boundary_at_3_minutes(self):
        ib = IdleBehavior()
        assert ib.get_long_stay_comment(2.99) is None
        result = ib.get_long_stay_comment(3.0)
        assert isinstance(result, str)

    def test_long_stay_over_10_minutes(self):
        ib = IdleBehavior()
        result = ib.get_long_stay_comment(15)
        assert isinstance(result, str) and len(result) > 0

    @patch("idle_behavior.time")
    def test_idle_interval_caps_at_90(self, mock_time):
        mock_time.time.return_value = 1000.0
        mock_time.localtime.return_value = time.localtime(1000.0)
        ib = IdleBehavior()
        # Fire enough actions to hit the cap
        for _ in range(30):
            mock_time.time.return_value += 200
            ib.get_idle_action()
        assert ib._idle_interval == 90


# ── TestIdleBehaviorGaps ─────────────────────────────────────────────────

class TestIdleBehaviorGaps:
    """Tests for previously untested functions: get_party_stage, get_time_observation, get_gossip_idle."""

    # -- get_party_stage tests --

    def test_party_stage_early(self):
        ib = IdleBehavior()
        result = ib.get_party_stage(15)
        assert isinstance(result, str) and len(result) > 0
        # 15 min falls in the <30 branch (early stage)
        assert result in [
            "The party just-a started! We're warming up!",
            "Still early! The best is yet to come, wahoo!",
        ]

    def test_party_stage_peak(self):
        ib = IdleBehavior()
        result = ib.get_party_stage(120)
        assert isinstance(result, str) and len(result) > 0
        # 120 min falls in the 120..240 branch (strong/marathon stage)
        assert result in [
            "The party's been going strong for hours! Legendary!",
            "Marathon party! Mario is-a impressed!",
        ]

    def test_party_stage_winding_down(self):
        ib = IdleBehavior()
        result = ib.get_party_stage(300)
        assert isinstance(result, str) and len(result) > 0
        # 300 min falls in the >=240 branch (eternal/late stage)
        assert result in [
            "This party is ETERNAL! We've been at it for hours!",
            "Are we... are we still partying? Mama mia, what a night!",
        ]

    def test_party_stage_zero_minutes(self):
        ib = IdleBehavior()
        result = ib.get_party_stage(0)
        assert isinstance(result, str) and len(result) > 0
        # 0 min falls in the <30 early branch
        assert result in [
            "The party just-a started! We're warming up!",
            "Still early! The best is yet to come, wahoo!",
        ]

    def test_party_stage_negative(self):
        ib = IdleBehavior()
        result = ib.get_party_stage(-10)
        assert isinstance(result, str) and len(result) > 0
        # Negative falls in the <30 early branch (no crash)
        assert result in [
            "The party just-a started! We're warming up!",
            "Still early! The best is yet to come, wahoo!",
        ]

    # -- get_time_observation tests --

    @patch("idle_behavior.datetime")
    def test_time_observation_returns_string_or_none(self, mock_dt):
        mock_dt.now.return_value = MagicMock(hour=22)
        ib = IdleBehavior()
        result = ib.get_time_observation()
        assert result is None or isinstance(result, str)

    @patch("idle_behavior.datetime")
    def test_time_observation_not_empty_string(self, mock_dt):
        # Pick an hour that always returns content (midnight)
        mock_dt.now.return_value = MagicMock(hour=0)
        ib = IdleBehavior()
        result = ib.get_time_observation()
        assert isinstance(result, str)
        assert len(result) > 0

    @patch("idle_behavior.datetime")
    def test_time_observation_changes_over_time(self, mock_dt):
        """Different hours should produce different observation pools."""
        ib = IdleBehavior()
        # Collect from midnight
        mock_dt.now.return_value = MagicMock(hour=0)
        midnight_results = {ib.get_time_observation() for _ in range(20)}
        # Collect from early morning
        mock_dt.now.return_value = MagicMock(hour=5)
        morning_results = {ib.get_time_observation() for _ in range(20)}
        # The two pools should be distinct
        assert midnight_results != morning_results

    # -- get_gossip_idle tests --

    @patch("idle_behavior.random.choice", side_effect=lambda x: x[0])
    def test_gossip_idle_returns_string_or_none(self, _choice):
        ib = IdleBehavior()
        with patch.dict("sys.modules", {"memory": MagicMock()}) as _:
            import sys
            mock_mem = sys.modules["memory"]
            mock_conn = MagicMock()
            mock_mem._get_conn.return_value = mock_conn
            mock_conn.execute.return_value.fetchall.return_value = [
                ("Luigi", "I just saw Bowser stealing mushrooms from the garden!"),
            ]
            result = ib.get_gossip_idle()
        assert result is None or isinstance(result, str)

    def test_gossip_idle_with_no_gossip_data(self):
        ib = IdleBehavior()
        with patch.dict("sys.modules", {"memory": MagicMock()}) as _:
            import sys
            mock_mem = sys.modules["memory"]
            mock_conn = MagicMock()
            mock_mem._get_conn.return_value = mock_conn
            mock_conn.execute.return_value.fetchall.return_value = []
            result = ib.get_gossip_idle()
        assert result is None


# ── TestLonelinessArc ────────────────────────────────────────────────────

class TestLonelinessArc:
    """Tests for the loneliness arc feature — lonely pools, actions, cooldown, visitor reset."""

    # -- Pool existence / size --

    def test_lonely_pools_exist(self):
        assert isinstance(LONELY_MILD, list) and len(LONELY_MILD) > 0
        assert isinstance(LONELY_MEDIUM, list) and len(LONELY_MEDIUM) > 0
        assert isinstance(LONELY_DEEP, list) and len(LONELY_DEEP) > 0

    def test_lonely_pools_minimum_size(self):
        assert len(LONELY_MILD) >= 6
        assert len(LONELY_MEDIUM) >= 6
        assert len(LONELY_DEEP) >= 6

    # -- get_lonely_action behaviour --

    def test_get_lonely_action_returns_none_early(self):
        ib = IdleBehavior()
        ib._alone_since = time.time()  # just now
        assert ib.get_lonely_action() is None

    def test_get_lonely_action_mild(self):
        ib = IdleBehavior()
        ib._alone_since = time.time() - 600  # 10 min ago
        ib._last_lonely_msg_time = 0
        result = ib.get_lonely_action()
        assert isinstance(result, str)
        assert result in LONELY_MILD

    def test_get_lonely_action_medium(self):
        ib = IdleBehavior()
        ib._alone_since = time.time() - 1200  # 20 min ago
        ib._last_lonely_msg_time = 0
        result = ib.get_lonely_action()
        assert isinstance(result, str)
        assert result in LONELY_MEDIUM

    def test_get_lonely_action_deep(self):
        ib = IdleBehavior()
        ib._alone_since = time.time() - 2400  # 40 min ago
        ib._last_lonely_msg_time = 0
        result = ib.get_lonely_action()
        assert isinstance(result, str)
        assert result in LONELY_DEEP

    # -- Cooldown --

    def test_lonely_cooldown(self):
        ib = IdleBehavior()
        ib._alone_since = time.time() - 600  # 10 min ago
        ib._last_lonely_msg_time = 0
        first = ib.get_lonely_action()
        assert first is not None
        # Second call within 90s should return None (cooldown)
        assert ib.get_lonely_action() is None

    # -- Visitor lifecycle --

    def test_visitor_arrived_resets_loneliness(self):
        ib = IdleBehavior()
        ib._alone_since = time.time() - 2400  # 40 min ago
        ib._last_lonely_msg_time = 0
        ib.visitor_arrived()
        assert ib._loneliness_level == 0

    def test_visitor_left_starts_timer(self):
        ib = IdleBehavior()
        before = time.time()
        ib.visitor_left()
        after = time.time()
        assert before <= ib._alone_since <= after
        assert ib._loneliness_level == 0

    # -- Greeting boost --

    def test_greeting_boost_none_when_not_alone(self):
        ib = IdleBehavior()
        ib._alone_since = time.time()  # just now
        assert ib.get_loneliness_greeting_boost() is None

    def test_greeting_boost_mild(self):
        ib = IdleBehavior()
        ib._alone_since = time.time() - 600  # 10 min alone
        result = ib.get_loneliness_greeting_boost()
        assert isinstance(result, str) and len(result) > 0

    def test_greeting_boost_deep(self):
        ib = IdleBehavior()
        ib._alone_since = time.time() - 2700  # 45 min alone
        result = ib.get_loneliness_greeting_boost()
        assert isinstance(result, str) and len(result) > 0


class TestIdleGossipRecap:
    def test_gossip_recap_none_when_no_gossip(self):
        ib = IdleBehavior()
        assert ib.get_idle_gossip_recap(None) is None

    def test_gossip_recap_none_with_empty_gossip(self):
        from party_gossip import PartyGossip
        ib = IdleBehavior()
        pg = PartyGossip()
        assert ib.get_idle_gossip_recap(pg) is None

    def test_gossip_recap_with_trending(self):
        from party_gossip import PartyGossip
        ib = IdleBehavior()
        pg = PartyGossip()
        pg._topic_mentions = {"pizza": {"a1", "b1"}}
        result = ib.get_idle_gossip_recap(pg)
        assert result is not None
        assert "pizza" in result.lower()

    def test_gossip_recap_with_rivalry(self):
        from party_gossip import PartyGossip
        ib = IdleBehavior()
        pg = PartyGossip()
        pg._rivalries = [("Alice", "Bob", "pizza")]
        result = ib.get_idle_gossip_recap(pg)
        assert result is not None
        assert "Alice" in result or "Bob" in result

    def test_gossip_recap_with_alliance(self):
        from party_gossip import PartyGossip
        ib = IdleBehavior()
        pg = PartyGossip()
        pg._alliances = [("Alice", "Carol", "music")]
        result = ib.get_idle_gossip_recap(pg)
        assert result is not None
        assert "Alice" in result or "Carol" in result

    def test_gossip_recap_with_title(self):
        from party_gossip import PartyGossip
        ib = IdleBehavior()
        pg = PartyGossip()
        pg._guest_titles = {"a1": "The Pizza Queen"}
        pg._guest_names = {"a1": "Alice"}
        result = ib.get_idle_gossip_recap(pg)
        assert result is not None
        assert "Alice" in result or "Pizza Queen" in result
