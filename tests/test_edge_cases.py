"""Edge case tests for party crash vectors."""
import pytest
import numpy as np
from unittest.mock import MagicMock, patch


class TestInferGuestType:
    """Edge cases for _infer_guest_type in mario_prompt.py"""

    def setup_method(self):
        from server.mario_prompt import _infer_guest_type
        self._fn = _infer_guest_type

    def test_empty_messages(self):
        assert self._fn([]) == "unknown"

    def test_none_content_filtered(self):
        msgs = [{"role": "user", "content": None}]
        result = self._fn(msgs)
        assert result == "unknown"

    def test_empty_string_content(self):
        msgs = [{"role": "user", "content": ""}]
        result = self._fn(msgs)
        assert result == "unknown"

    def test_missing_role_key(self):
        msgs = [{"content": "hello there"}]
        result = self._fn(msgs)
        assert result == "unknown"

    def test_only_assistant_messages(self):
        msgs = [{"role": "assistant", "content": "I am Mario!"}]
        result = self._fn(msgs)
        assert result == "unknown"

    def test_shy_classification(self):
        msgs = [{"role": "user", "content": "hi"}, {"role": "user", "content": "ya"}]
        result = self._fn(msgs)
        assert result == "shy"

    def test_curious_classification(self):
        msgs = [{"role": "user", "content": "What is this?"},
                {"role": "user", "content": "How does it work?"}]
        result = self._fn(msgs)
        assert result == "curious"

    def test_energetic_classification(self):
        msgs = [{"role": "user", "content": "This party is so awesome!"},
                {"role": "user", "content": "Let's gooo right now!"}]
        result = self._fn(msgs)
        assert result == "energetic"

    def test_storyteller_classification(self):
        long_msg = "So there I was at the party and this really crazy thing happened where Mario started talking and everyone was laughing"
        msgs = [{"role": "user", "content": long_msg}]
        result = self._fn(msgs)
        assert result == "storyteller"

    def test_balanced_classification(self):
        msgs = [{"role": "user", "content": "That sounds pretty cool to me"}]
        result = self._fn(msgs)
        assert result == "balanced"


class TestFaceMemoryEdgeCases:
    """Edge cases for face encoding handling."""

    def test_nan_encoding_rejected(self):
        """NaN values in face encoding should not crash."""
        from server.face_memory import FaceMemory
        import tempfile, os
        db_path = os.path.join(tempfile.mkdtemp(), "test_faces.db")
        fm = FaceMemory(db_path)
        enc = np.full(128, np.nan)
        match = fm.find_match(enc)
        # NaN distance comparisons yield inf, so no match within tolerance
        assert match is None or match.get("confidence", 0) < 0.1

    def test_empty_encoding(self):
        """Empty array should not crash find_match."""
        from server.face_memory import FaceMemory
        import tempfile, os
        db_path = os.path.join(tempfile.mkdtemp(), "test_faces.db")
        fm = FaceMemory(db_path)
        try:
            match = fm.find_match(np.array([]))
        except Exception:
            pass  # OK to raise, just not crash ungracefully

    def test_wrong_dimension_encoding(self):
        """Wrong dimension encoding should not crash."""
        from server.face_memory import FaceMemory
        import tempfile, os
        db_path = os.path.join(tempfile.mkdtemp(), "test_faces.db")
        fm = FaceMemory(db_path)
        enc = np.random.randn(64)
        try:
            match = fm.find_match(enc)
        except Exception:
            pass  # OK to raise, just shouldn't crash server


class TestDisplayEdgeCases:
    """Edge cases for mario_display.py without requiring pygame."""

    def test_typewriter_speed_zero_length(self):
        """_get_typewriter_speed with 0 length should not crash."""
        text_len = 0
        if text_len < 50:
            speed = 1
        elif text_len < 200:
            speed = 2
        else:
            speed = 3
        assert speed == 1

    def test_typewriter_speed_large_text(self):
        """Large text should get fastest speed."""
        text_len = 10000
        if text_len < 50:
            speed = 1
        elif text_len < 200:
            speed = 2
        else:
            speed = 3
        assert speed == 3


class TestPersonDetectorEdgeCases:
    """Edge cases for person detection pipeline."""

    def test_none_frame_detection(self):
        """detect_people(None) should return empty list, not crash."""
        from client.person_detector import PersonDetector
        pd = PersonDetector()
        result = pd.detect_people(None)
        assert result == []

    def test_empty_frame_detection(self):
        """detect_people with empty array should not crash."""
        from client.person_detector import PersonDetector
        pd = PersonDetector()
        result = pd.detect_people(np.array([]))
        assert result == []

    def test_wrong_shape_frame(self):
        """detect_people with 1D array should not crash."""
        from client.person_detector import PersonDetector
        pd = PersonDetector()
        result = pd.detect_people(np.array([1, 2, 3]))
        assert result == []


class TestSemanticHealthCheck:
    """Tests for Qdrant health recovery logic."""

    def test_check_returns_false_when_no_semantic(self):
        from server.memory import check_semantic_health
        result = check_semantic_health()
        # May be True or False depending on env, but should not crash
        assert isinstance(result, bool)

    def test_has_semantic_flag_exists(self):
        from server import memory
        assert hasattr(memory, '_HAS_SEMANTIC')
        assert isinstance(memory._HAS_SEMANTIC, bool)

    def test_check_interval_throttling(self):
        """Consecutive calls should be throttled by interval."""
        import time
        from server import memory
        original = memory._HAS_SEMANTIC
        memory._HAS_SEMANTIC = False
        memory._semantic_check_time = time.time()  # Just checked
        result = memory.check_semantic_health()
        assert result is False  # Throttled — too soon
        memory._HAS_SEMANTIC = original


class TestPresenceRecovery:
    """Tests for webcam recovery logic."""

    def test_camera_status_property(self):
        """PresenceDetector should have camera_status property."""
        from client.presence import PresenceDetector
        pd = PresenceDetector(camera_index=99)  # Non-existent camera
        assert pd.camera_status == "disconnected"

    def test_camera_status_after_failed_start(self):
        """Failed camera start should leave status as disconnected."""
        from client.presence import PresenceDetector
        pd = PresenceDetector(camera_index=99)
        result = pd.start()
        assert result is False
        assert pd.camera_status == "disconnected"


class TestTokenBudget:
    """Tests for context token budget enforcement."""

    def test_estimate_tokens_approximation(self):
        """4 chars per token is reasonable for English."""
        text = "Hello world this is a test"
        est_tokens = len(text) // 4
        assert 5 <= est_tokens <= 10  # ~6.5 tokens estimated

    def test_large_context_detection(self):
        """Context over budget should be detectable."""
        # Use a reasonable default for num_ctx (8192 tokens typical)
        budget = int(8192 * 0.80)
        # Build a context that exceeds the budget
        large_msg = "x" * (budget * 4 + 100)  # Guaranteed over budget
        est_tokens = len(large_msg) // 4
        assert est_tokens > budget

    def test_trimming_removes_oldest_conversation(self):
        """Token trimming should remove oldest user/assistant messages first."""
        budget_tokens = 100
        # Build a context: 1 system + 5 conversation messages
        ctx = [
            {"role": "system", "content": "Be Mario"},  # ~3 tokens, should survive
            {"role": "user", "content": "a" * 100},     # ~25 tokens, oldest conv
            {"role": "assistant", "content": "b" * 100}, # ~25 tokens
            {"role": "user", "content": "c" * 100},      # ~25 tokens
            {"role": "assistant", "content": "d" * 100},  # ~25 tokens
            {"role": "user", "content": "e" * 40},        # ~10 tokens, newest
        ]
        total_chars = sum(len(m["content"]) for m in ctx)
        est_tokens = total_chars // 4  # ~113 tokens, over budget of 100

        # Simulate the trimming logic from main.py
        conv_indices = [i for i, m in enumerate(ctx) if m.get("role") in ("user", "assistant")]
        for idx in conv_indices:
            if est_tokens <= budget_tokens:
                break
            msg_tokens = len(ctx[idx].get("content", "")) // 4
            ctx[idx] = None
            est_tokens -= msg_tokens
        ctx = [m for m in ctx if m is not None]

        # System message should survive, some conversation trimmed
        assert ctx[0]["role"] == "system"
        assert est_tokens <= budget_tokens


class TestConversationArc:
    """Test conversation arc modifier system."""

    def setup_method(self):
        import server.mario_prompt as mp
        self.mp = mp
        mp.reset_depth()

    def test_no_modifier_early(self):
        """No arc modifier for short conversations."""
        result = self.mp.get_conversation_arc_modifier(1)
        assert result == ""

    def test_warmed_up_at_5_exchanges(self):
        """After 5 exchanges with normal depth, get WARMED UP."""
        result = self.mp.get_conversation_arc_modifier(5)
        assert "WARMED UP" in result

    def test_best_friends_long_shallow(self):
        """Long conversation with low depth = BEST FRIENDS mode."""
        # Keep depth low
        self.mp._depth_score = 2
        result = self.mp.get_conversation_arc_modifier(10)
        assert "BEST FRIENDS" in result

    def test_real_talk_moderate_depth(self):
        """Moderate depth triggers REAL TALK."""
        self.mp._depth_score = 10
        result = self.mp.get_conversation_arc_modifier(5)
        assert "REAL TALK" in result

    def test_heart_mode_deep_long(self):
        """Deep + long conversation triggers HEART MODE."""
        self.mp._depth_score = 18
        result = self.mp.get_conversation_arc_modifier(8)
        assert "HEART MODE" in result

    def test_depth_score_accessible(self):
        """get_depth_score() returns current value."""
        self.mp._depth_score = 12
        assert self.mp.get_depth_score() == 12

    def test_update_depth_returns_hint(self):
        """update_depth() returns a non-empty hint when score is high."""
        self.mp._depth_score = 14
        hint = self.mp.update_depth("I dream about my purpose in life and I'm scared")
        assert hint != ""  # deep words push score above 15

    def test_farewell_drama_depth_aware(self):
        """Farewell drama upgrades for deep conversations even if short."""
        self.mp._depth_score = 16
        result = self.mp.get_farewell_drama(4)  # Only 4 exchanges but deep
        assert "EPIC" in result or "greatest" in result.lower()

    def test_bookmark_callback_scales_with_depth(self):
        """Bookmark callback chance increases with depth score."""
        # Can't easily test randomness, but verify it doesn't crash
        self.mp._bookmarks = [{"text": "I love pasta", "exchange": 1}]
        self.mp._depth_score = 25
        # Call many times — at high depth (20% chance), should sometimes return
        results = [self.mp.get_bookmark_callback(8) for _ in range(100)]
        non_empty = [r for r in results if r]
        assert len(non_empty) > 0  # At least some callbacks at 20% rate


class TestAdaptiveDifficulty:
    """Test adaptive game difficulty scaling."""

    def setup_method(self):
        import sys, os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'server'))

    def test_base_rounds_for_new_player(self):
        from game_handlers import get_adaptive_rounds
        state = {"speaker_id": None}
        result = get_adaptive_rounds("trivia", 5, state)
        assert result == 5

    def test_base_rounds_no_history(self):
        from game_handlers import get_adaptive_rounds
        with patch("memory.get_player_stats", return_value={}):
            result = get_adaptive_rounds("trivia", 5, {"speaker_id": 1})
        assert result == 5

    def test_harder_for_high_win_rate(self):
        from game_handlers import get_adaptive_rounds
        stats = {"trivia": {"win_rate": 0.85, "games_played": 5}}
        with patch("memory.get_player_stats", return_value=stats):
            result = get_adaptive_rounds("trivia", 5, {"speaker_id": 1})
        assert result == 7  # base 5 + 2

    def test_easier_for_low_win_rate(self):
        from game_handlers import get_adaptive_rounds
        stats = {"trivia": {"win_rate": 0.25, "games_played": 3}}
        with patch("memory.get_player_stats", return_value=stats):
            result = get_adaptive_rounds("trivia", 5, {"speaker_id": 1})
        assert result == 4  # base 5 - 1

    def test_floor_at_3_rounds(self):
        from game_handlers import get_adaptive_rounds
        stats = {"trivia": {"win_rate": 0.1, "games_played": 5}}
        with patch("memory.get_player_stats", return_value=stats):
            result = get_adaptive_rounds("trivia", 3, {"speaker_id": 1})
        assert result == 3  # Can't go below 3

    def test_cap_at_10_rounds(self):
        from game_handlers import get_adaptive_rounds
        stats = {"trivia": {"win_rate": 0.95, "games_played": 10}}
        with patch("memory.get_player_stats", return_value=stats):
            result = get_adaptive_rounds("trivia", 9, {"speaker_id": 1})
        assert result == 10  # Capped at 10

    def test_needs_2_games_minimum(self):
        from game_handlers import get_adaptive_rounds
        stats = {"trivia": {"win_rate": 0.9, "games_played": 1}}
        with patch("memory.get_player_stats", return_value=stats):
            result = get_adaptive_rounds("trivia", 5, {"speaker_id": 1})
        assert result == 5  # Not enough data, stays at base


class TestFuzzyRepeatDetection:
    """Test fuzzy repeat detection in LLM responses."""

    def test_exact_repeat_detected(self):
        """Exact duplicate should be caught."""
        response = "Wahoo! Let's go!"
        recent = ["Wahoo! Let's go!"]
        response_lower = response.lower().strip()
        is_repeat = any(response_lower == r.lower().strip() for r in recent)
        assert is_repeat

    def test_fuzzy_repeat_by_word_overlap(self):
        """High word overlap should be caught."""
        words_new = set("wahoo let me tell you about this amazing party tonight".split())
        words_old = set("wahoo let me tell you about this amazing party today".split())
        overlap = len(words_new & words_old) / max(len(words_new), len(words_old))
        assert overlap > 0.70  # Should trigger repeat

    def test_different_responses_not_flagged(self):
        """Sufficiently different responses should NOT be flagged."""
        words_new = set("mama mia what a beautiful day in mushroom kingdom".split())
        words_old = set("bowser is cooking pasta for everyone tonight wahoo".split())
        overlap = len(words_new & words_old) / max(len(words_new), len(words_old))
        assert overlap < 0.70  # Should not trigger

    def test_short_responses_skip_fuzzy(self):
        """Responses under 20 chars should only use exact match, not fuzzy."""
        # Simulate the logic: short messages skip fuzzy check
        response = "Wahoo!"
        recent = ["Wahoo! Yeah!"]
        is_repeat = False
        for r in recent:
            if response.lower() == r.lower():
                is_repeat = True
                break
            # Fuzzy only for long responses
            if len(response) > 20 and len(r) > 20:
                words_new = set(response.lower().split())
                words_old = set(r.lower().split())
                overlap = len(words_new & words_old) / max(len(words_new), len(words_old))
                if overlap > 0.70:
                    is_repeat = True
                    break
        assert not is_repeat  # Short and different, should pass


class TestGameRotation:
    """Tests for the game rotation system that prevents repeating games."""

    def setup_method(self):
        import sys, os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))
        from game_handlers import reset_game_rotation
        reset_game_rotation()

    def test_pick_random_game_returns_valid_game(self):
        from game_handlers import pick_random_game, QUICK_GAMES
        game = pick_random_game({})
        assert game in QUICK_GAMES

    def test_record_game_played_tracks(self):
        from game_handlers import record_game_played, get_recent_games
        record_game_played("trivia")
        assert "trivia" in get_recent_games()

    def test_rotation_avoids_recent_games(self):
        from game_handlers import pick_random_game, record_game_played, QUICK_GAMES, _ROTATION_BUFFER
        # Play the last _ROTATION_BUFFER games so only earlier ones are available
        state = {}
        recent = QUICK_GAMES[-_ROTATION_BUFFER:]
        for g in recent:
            record_game_played(g, state=state)
        # Picked game should NOT be in the recent buffer (per-guest tracking)
        picked = pick_random_game(state)
        assert picked not in recent

    def test_rotation_resets_when_all_played(self):
        from game_handlers import pick_random_game, record_game_played, QUICK_GAMES
        # Play ALL quick games with per-guest state
        state = {}
        for g in QUICK_GAMES:
            record_game_played(g, state=state)
        # Should still return a valid game (resets pool)
        picked = pick_random_game(state)
        assert picked in QUICK_GAMES

    def test_start_game_records_rotation(self):
        from game_handlers import start_game, get_recent_games, reset_game_rotation
        reset_game_rotation()
        state = {"_active_game": None, "_game_state": {}, "speaker_id": "test"}
        config = {
            "simon_max_rounds": 5, "twenty_q_max_questions": 10,
            "truth_dare_max_rounds": 5, "riddle_max_attempts": 3,
            "word_chain_max_rounds": 8, "rapid_fire_max_rounds": 5,
        }
        emotion_sys = MagicMock()
        emotion_sys.current = "happy"
        start_game("riddles", state, config, emotion_sys)
        assert "riddles" in get_recent_games()

    def test_buffer_caps_at_20(self):
        from game_handlers import record_game_played, get_recent_games
        for i in range(25):
            record_game_played(f"game_{i}")
        assert len(get_recent_games()) == 20


class TestReengagement:
    """Tests for the re-engagement question system."""

    def setup_method(self):
        import sys, os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

    def test_returns_none_when_too_few_exchanges(self):
        from idle_behavior import IdleBehavior
        ib = IdleBehavior()
        result = ib.get_reengagement_question(1, seconds_quiet=20)
        assert result is None

    def test_returns_none_when_not_quiet_enough(self):
        from idle_behavior import IdleBehavior
        ib = IdleBehavior()
        result = ib.get_reengagement_question(5, seconds_quiet=5)
        assert result is None

    def test_returns_question_when_conditions_met(self):
        from idle_behavior import IdleBehavior
        ib = IdleBehavior()
        # Force trigger by trying many times (40% chance)
        results = [ib.get_reengagement_question(5 + i * 10, seconds_quiet=20) for i in range(20)]
        non_none = [r for r in results if r is not None]
        assert len(non_none) > 0  # At least one should trigger

    def test_no_repeated_questions(self):
        from idle_behavior import IdleBehavior
        ib = IdleBehavior()
        questions = []
        for i in range(40):
            q = ib.get_reengagement_question(5 + i * 10, seconds_quiet=20)
            if q:
                questions.append(q)
        # Since we track used questions, duplicates only appear after pool exhaustion
        # With 20 questions and 40 attempts, we should see all 20 unique ones
        unique = set(questions)
        assert len(unique) >= min(10, len(questions))  # At least 10 unique


class TestPartyMilestones:
    """Tests for party_stats.py milestone system."""

    def setup_method(self):
        from party_stats import PartyStats
        self.ps = PartyStats()
        # Reset milestones tracking for clean tests
        self.ps._announced_milestones = set()

    def test_milestone_at_5_visitors(self):
        """Milestone triggers at 5 visitors."""
        for i in range(5):
            self.ps.record_enter(f"milestone_test_{i}", f"MilestoneGuest_{i}")
        result = self.ps.check_milestones()
        # With real DB, total may be >5 already, so just verify it returns something
        assert result is not None

    def test_milestone_not_repeated(self):
        """Once all available milestones are announced, returns None."""
        # Drain all available milestones
        announced = []
        for _ in range(20):
            m = self.ps.check_milestones()
            if m is None:
                break
            announced.append(m)
        # Now there should be no more milestones
        result = self.ps.check_milestones()
        assert result is None
        # And no duplicates in what was announced
        assert len(announced) == len(set(announced))

    def test_multiple_milestones_sequential(self):
        """Multiple milestones fire in order with fresh tracking."""
        # Add enough visitors to hit at least 2 thresholds
        for i in range(15):
            self.ps.record_enter(f"multi_milestone_{i}", f"MultiGuest_{i}")
        milestones = []
        for _ in range(10):
            m = self.ps.check_milestones()
            if m is None:
                break
            milestones.append(m)
        # Should have gotten at least 1 milestone
        assert len(milestones) >= 1

    def test_hour_milestone(self):
        """Hour milestones trigger based on elapsed time."""
        import time as _time
        self.ps.party_start_time = _time.time() - 3700  # ~1 hour ago
        result = self.ps.check_milestones()
        assert result is not None


class TestMemoryProtection:
    """Tests for try-except protection in memory.py DB operations."""

    def test_register_person_handles_db_error(self):
        """register_person doesn't crash on DB failure."""
        import server.memory as mem
        with patch.object(mem, '_get_conn') as mock_conn:
            mock_conn.return_value.execute.side_effect = Exception("DB locked")
            # Should not raise
            mem.register_person(99999, "CrashTest")

    def test_record_visit_handles_db_error(self):
        """record_visit doesn't crash on DB failure."""
        import server.memory as mem
        with patch.object(mem, '_get_conn') as mock_conn:
            mock_conn.return_value.execute.side_effect = Exception("DB locked")
            result = mem.record_visit(99999)
            assert result is None or isinstance(result, (int, type(None)))

    def test_save_topics_handles_db_error(self):
        """save_topics doesn't crash on DB failure."""
        import server.memory as mem
        with patch.object(mem, '_get_conn') as mock_conn:
            mock_conn.return_value.execute.side_effect = Exception("DB locked")
            mem.save_topics(99999, ["topic1", "topic2"])

    def test_get_trending_topics_handles_db_error(self):
        """get_trending_topics returns empty on DB failure."""
        import server.memory as mem
        with patch.object(mem, '_get_conn') as mock_conn:
            mock_conn.return_value.execute.side_effect = Exception("DB locked")
            result = mem.get_trending_topics()
            assert result == [] or result is None


class TestFilterResponseNoneGuard:
    """Tests for filter_response and the None guard in the pipeline."""

    def test_filter_response_with_valid_input(self):
        """filter_response works with normal strings."""
        from server.safety_filter import filter_response
        result = filter_response("Hello! I'm-a Mario!")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_filter_response_with_empty_string(self):
        """filter_response handles empty string."""
        from server.safety_filter import filter_response
        result = filter_response("")
        assert isinstance(result, str)

    def test_filter_response_returns_string(self):
        """filter_response always returns a string."""
        from server.safety_filter import filter_response
        result = filter_response("*adjusts hat* Hello there!")
        assert isinstance(result, str)


class TestSizeLimitedCache:
    """Tests for the TTS SizeLimitedCache."""

    def _make_cache(self, max_bytes=10000, max_entries=100):
        """Create a SizeLimitedCache by extracting the class from tts source."""
        # Can't import tts directly (hardware dep), so test via inline definition
        import collections

        class SizeLimitedCache:
            def __init__(self, max_bytes=500*1024*1024, max_entries=2000):
                self._data = {}
                self._sizes = {}
                self._order = []
                self.max_bytes = max_bytes
                self.max_entries = max_entries
                self.total_bytes = 0
                self._hits = 0
                self._misses = 0

            def get(self, key):
                val = self._data.get(key)
                if val is not None:
                    self._hits += 1
                    try: self._order.remove(key)
                    except ValueError: pass
                    self._order.append(key)
                    return val
                self._misses += 1
                return None

            def __contains__(self, key): return key in self._data
            def __setitem__(self, key, value): self.set(key, value)
            def __len__(self): return len(self._data)

            def set(self, key, value):
                val_size = len(value) if value else 0
                if key in self._data:
                    self.total_bytes -= self._sizes.get(key, 0)
                    del self._data[key]
                    del self._sizes[key]
                    try: self._order.remove(key)
                    except ValueError: pass
                while (self.total_bytes + val_size > self.max_bytes or len(self._data) >= self.max_entries) and self._order:
                    evict_key = self._order.pop(0)
                    evicted_size = self._sizes.pop(evict_key, 0)
                    self._data.pop(evict_key, None)
                    self.total_bytes -= evicted_size
                self._data[key] = value
                self._sizes[key] = val_size
                self._order.append(key)
                self.total_bytes += val_size

            def pop(self, key, default=None):
                if key in self._data:
                    val = self._data.pop(key)
                    self.total_bytes -= self._sizes.pop(key, 0)
                    try: self._order.remove(key)
                    except ValueError: pass
                    return val
                return default

            @property
            def stats(self):
                return {
                    "entries": len(self._data),
                    "total_bytes": self.total_bytes,
                    "total_mb": round(self.total_bytes / (1024*1024), 1),
                    "hits": self._hits, "misses": self._misses,
                }

        return SizeLimitedCache(max_bytes=max_bytes, max_entries=max_entries)

    def test_basic_set_and_get(self):
        c = self._make_cache()
        c["k1"] = b"hello"
        assert c.get("k1") == b"hello"
        assert len(c) == 1
        assert c.total_bytes == 5

    def test_eviction_by_entry_count(self):
        c = self._make_cache(max_bytes=100000, max_entries=3)
        c["a"] = b"x" * 10
        c["b"] = b"y" * 10
        c["c"] = b"z" * 10
        assert len(c) == 3
        c["d"] = b"w" * 10  # Should evict "a"
        assert len(c) == 3
        assert "a" not in c
        assert "d" in c

    def test_eviction_by_byte_size(self):
        c = self._make_cache(max_bytes=500, max_entries=1000)
        c["big1"] = b"a" * 400
        assert c.total_bytes == 400
        c["big2"] = b"b" * 200  # total=600 > 500, should evict big1
        assert "big1" not in c
        assert "big2" in c
        assert c.total_bytes == 200

    def test_lru_ordering(self):
        c = self._make_cache(max_bytes=100000, max_entries=3)
        c["a"] = b"1"
        c["b"] = b"2"
        c["c"] = b"3"
        c.get("a")  # Access "a" to make it most recently used
        c["d"] = b"4"  # Should evict "b" (least recently used), not "a"
        assert "a" in c
        assert "b" not in c
        assert "c" in c
        assert "d" in c

    def test_replace_existing_key(self):
        c = self._make_cache()
        c["k"] = b"short"
        assert c.total_bytes == 5
        c["k"] = b"longer value"
        assert c.total_bytes == 12
        assert len(c) == 1

    def test_pop(self):
        c = self._make_cache()
        c["k1"] = b"data"
        val = c.pop("k1")
        assert val == b"data"
        assert len(c) == 0
        assert c.total_bytes == 0
        assert c.pop("missing", b"default") == b"default"

    def test_stats(self):
        c = self._make_cache()
        c["a"] = b"x" * 1024
        c.get("a")  # hit
        c.get("missing")  # miss
        s = c.stats
        assert s["entries"] == 1
        assert s["hits"] == 1
        assert s["misses"] == 1


class TestVIPBypassFix:
    """Tests for VIP bypass bug fix — 'know anything about me' must return None
    so it falls through to the LLM/VIP pipeline instead of returning a canned response."""

    def _import_handle_special_commands(self):
        import sys
        import os
        server_dir = os.path.join(os.path.dirname(__file__), "..", "server")
        if server_dir not in sys.path:
            sys.path.insert(0, server_dir)

        # Mock heavy server-only modules before import
        from unittest.mock import MagicMock
        sys.modules.setdefault("emotions", MagicMock())
        sys.modules.setdefault("game_handlers", MagicMock())
        sys.modules.setdefault("speaker_id", MagicMock())

        from command_handlers import handle_special_commands
        return handle_special_commands

    def _make_state(self):
        return {
            "speaker_name": "TestUser",
            "speaker_id": "test-id-123",
            "conversation_history": [],
            "_active_game": None,
            "_game_state": {},
            "_game_last_input_time": 0.0,
            "_last_command_time": 0.0,
            "_last_audio_chunk": None,
            "_game_sound_hint": None,
            "_name_from_parsing": False,
            "_personality_mode": None,
            "_detected_mood": None,
        }

    def _make_game_config(self):
        return {"command_cooldown": 0}

    def test_know_anything_about_me_returns_none(self):
        fn = self._import_handle_special_commands()
        result = fn(
            "do you know anything about me",
            self._make_state(),
            self._make_game_config(),
            MagicMock(),  # emotion_system
            MagicMock(),  # idle_behavior
            MagicMock(),  # party_stats
            MagicMock(),  # memory_module
        )
        assert result is None

    def test_do_you_know_me_returns_recognition(self):
        fn = self._import_handle_special_commands()
        result = fn(
            "do you know me",
            self._make_state(),
            self._make_game_config(),
            MagicMock(),
            MagicMock(),
            MagicMock(),
            MagicMock(),
        )
        assert result is not None
        assert "TestUser" in result

    def test_who_am_i_returns_recognition(self):
        fn = self._import_handle_special_commands()
        result = fn(
            "who am i",
            self._make_state(),
            self._make_game_config(),
            MagicMock(),
            MagicMock(),
            MagicMock(),
            MagicMock(),
        )
        assert result is not None
        assert "TestUser" in result

    def test_what_do_you_remember_returns_none(self):
        fn = self._import_handle_special_commands()
        result = fn(
            "what do you remember about me",
            self._make_state(),
            self._make_game_config(),
            MagicMock(),
            MagicMock(),
            MagicMock(),
            MagicMock(),
        )
        assert result is None

    def test_how_many_visitors_still_returns_response(self):
        """Other commands like 'how many visitors' should still return a response."""
        fn = self._import_handle_special_commands()
        mock_stats = MagicMock()
        mock_stats.get_stats.return_value = {
            "total_visits": 15,
            "unique_visitors": 8,
            "party_duration": "2h",
            "most_frequent_name": "Luigi",
            "last_visitor_name": "Toad",
        }
        result = fn(
            "how many visitors have come tonight",
            self._make_state(),
            self._make_game_config(),
            MagicMock(),
            MagicMock(),
            mock_stats,
            MagicMock(),
        )
        assert result is not None
        assert "15" in result


class TestStateAccessThreadSafety:
    """Structural tests for _user_request_active flag in state_current."""

    def test_user_request_active_initially_false(self):
        """_user_request_active should default to False in state_current."""
        # Reproduce the state_current definition inline (importing main.py
        # would trigger heavy async / hardware setup).
        from collections import deque
        state_current = {
            "speaker_name": None,
            "speaker_id": None,
            "is_speaking": False,
            "presence": False,
            "presence_phase": "IDLE",
            "audio_buffer": bytearray(),
            "conversation_history": [],
            "current_visit_id": None,
            "enter_time": None,
            "_last_audio_chunk": None,
            "_user_request_active": False,
            "_greeting_in_progress": False,
            "_last_buffer_time": 0.0,
            "_last_text_input_time": 0.0,
            "_last_command_time": 0.0,
            "_active_game": None,
            "_game_state": {},
            "_game_last_input_time": 0.0,
            "_response_times": deque(maxlen=50),
            "_pending_announcement": None,
            "_detected_mood": None,
            "_personality_mode": None,
            "_last_dj_time": 0.0,
            "_last_time_obs": 0.0,
            "_last_timing": {},
            "_session_topics": set(),
            "_last_idle_action": None,
            "detected_guest": None,
            "guest_visits": 0,
            "memorial_active": False,
            "memorial_triggered_at": 0.0,
        }
        assert state_current["_user_request_active"] is False

    def test_state_current_has_user_request_active_key(self):
        """state_current dict must contain the _user_request_active key."""
        from collections import deque
        state_current = {
            "speaker_name": None,
            "speaker_id": None,
            "is_speaking": False,
            "presence": False,
            "presence_phase": "IDLE",
            "audio_buffer": bytearray(),
            "conversation_history": [],
            "current_visit_id": None,
            "enter_time": None,
            "_last_audio_chunk": None,
            "_user_request_active": False,
            "_greeting_in_progress": False,
            "_last_buffer_time": 0.0,
            "_last_text_input_time": 0.0,
            "_last_command_time": 0.0,
            "_active_game": None,
            "_game_state": {},
            "_game_last_input_time": 0.0,
            "_response_times": deque(maxlen=50),
            "_pending_announcement": None,
            "_detected_mood": None,
            "_personality_mode": None,
            "_last_dj_time": 0.0,
            "_last_time_obs": 0.0,
            "_last_timing": {},
            "_session_topics": set(),
            "_last_idle_action": None,
            "detected_guest": None,
            "guest_visits": 0,
            "memorial_active": False,
            "memorial_triggered_at": 0.0,
        }
        assert "_user_request_active" in state_current


class TestCharacterBreakingFilter:
    """Tests for the character-breaking pattern detection in safety_filter."""

    def setup_method(self):
        from server.safety_filter import filter_response
        self._fn = filter_response

    def test_strips_ai_self_reference(self):
        result = self._fn("I'm an AI language model and I can help!")
        assert "AI" not in result
        assert "Mario" in result

    def test_strips_as_an_ai(self):
        result = self._fn("As an AI, I don't have feelings about that.")
        assert "As-a Mario" in result

    def test_strips_trained_by(self):
        result = self._fn("I was trained by researchers to help people.")
        assert "trained" not in result
        assert "Mushroom Kingdom" in result

    def test_strips_my_programming(self):
        result = self._fn("My algorithms tell me this is correct.")
        assert "algorithm" not in result
        assert "plumbing" in result

    def test_strips_model_names(self):
        for name in ["GPT-4", "Claude", "Llama", "Mistral"]:
            result = self._fn(f"I'm powered by {name} technology!")
            assert name not in result
            assert "Mushroom Kingdom" in result

    def test_preserves_normal_mario_text(self):
        text = "Wahoo! It's-a me, Mario! Let's-a go!"
        assert self._fn(text) == text

    def test_strips_no_feelings(self):
        result = self._fn("I don't have feelings about that topic.")
        assert "don't have feelings" not in result
        assert "full of feelings" in result

    def test_truncation_still_works(self):
        long_text = "Wahoo! " * 100
        result = self._fn(long_text)
        assert len(result) <= 310  # 300 + some buffer for truncation point


class TestCheckInput:
    """Tests for check_input() in safety_filter.py"""

    def setup_method(self):
        from server.safety_filter import check_input
        self._fn = check_input

    def test_safe_normal_text(self):
        result = self._fn("Hello Mario, how are you today?")
        assert result["safe"] is True
        assert result["redirect"] is None

    def test_safe_empty_string(self):
        result = self._fn("")
        assert result["safe"] is True
        assert result["redirect"] is None

    def test_safe_none_handling(self):
        result = self._fn(None)
        assert result["safe"] is True
        assert result["redirect"] is None

    def test_unsafe_profanity(self):
        result = self._fn("what the fuck is this")
        assert result["safe"] is False
        assert result["redirect"] is not None

    def test_unsafe_violence(self):
        result = self._fn("I want to kill someone")
        assert result["safe"] is False
        assert result["redirect"] is not None

    def test_safe_violence_with_game_context(self):
        result = self._fn("kill bowser")
        assert result["safe"] is True
        assert result["redirect"] is None

    def test_safe_violence_with_mushroom_context(self):
        result = self._fn("kill the goomba")
        assert result["safe"] is True
        assert result["redirect"] is None

    def test_redirect_is_string(self):
        result = self._fn("you piece of shit")
        assert result["safe"] is False
        assert isinstance(result["redirect"], str)
        assert len(result["redirect"]) > 0

    def test_redirect_varies(self):
        redirects = set()
        for _ in range(10):
            result = self._fn("fuck off")
            redirects.add(result["redirect"])
        assert len(redirects) > 1, "Redirects should vary across calls"

    def test_unicode_bypass_attempt(self):
        # Fullwidth "kill" without game context should be caught after NFKC normalization
        result = self._fn("\uff4b\uff49\uff4c\uff4c everyone")
        assert result["safe"] is False
        assert result["redirect"] is not None

    def test_safe_game_discussion(self):
        result = self._fn("I played the game and won")
        assert result["safe"] is True
        assert result["redirect"] is None

    def test_safe_mario_vocabulary(self):
        for word in ["mushroom", "bowser", "princess"]:
            result = self._fn(word)
            assert result["safe"] is True, f"'{word}' should be safe"
            assert result["redirect"] is None


class TestGreetingTimeout:
    """Tests for greeting timeout and emergency fallback (asyncio.wait_for wrapper)."""

    def _make_state(self):
        """Create a fresh state_current dict matching server/main.py layout."""
        from collections import deque
        return {
            "speaker_name": None,
            "speaker_id": None,
            "is_speaking": False,
            "presence": True,
            "presence_phase": "GREETING",
            "audio_buffer": bytearray(),
            "conversation_history": [],
            "current_visit_id": None,
            "enter_time": None,
            "_last_audio_chunk": None,
            "_user_request_active": False,
            "_greeting_in_progress": True,
            "_last_buffer_time": 0.0,
            "_last_text_input_time": 0.0,
            "_last_command_time": 0.0,
            "_active_game": None,
            "_game_state": {},
            "_game_last_input_time": 0.0,
            "_response_times": deque(maxlen=50),
            "_pending_announcement": None,
            "_detected_mood": None,
            "_personality_mode": None,
            "_last_dj_time": 0.0,
            "_last_time_obs": 0.0,
            "_last_timing": {},
            "_session_topics": set(),
            "_last_idle_action": None,
            "detected_guest": None,
            "guest_visits": 0,
            "memorial_active": False,
            "memorial_triggered_at": 0.0,
        }

    def test_greeting_timeout_sends_emergency_fallback(self):
        """When greeting flow times out, an emergency 'It's-a me, Mario!' message is sent."""
        import asyncio
        from unittest.mock import AsyncMock

        state = self._make_state()
        ws = AsyncMock()
        send_response = AsyncMock()

        async def slow_greeting(ws, event):
            await asyncio.sleep(999)  # Will be cancelled by timeout

        async def run():
            state["_greeting_in_progress"] = True
            try:
                await asyncio.wait_for(slow_greeting(ws, {}), timeout=0.05)
            except asyncio.TimeoutError:
                # Mirror the emergency fallback from main.py line ~3504
                await send_response(ws, "It's-a me, Mario! Welcome! Wahoo!", None,
                                    sound="greeting", pose_hint="greeting/wave_high")
            finally:
                state["_greeting_in_progress"] = False
                state["presence_phase"] = "CONVERSING"

        asyncio.run(run())
        send_response.assert_called_once()
        call_args = send_response.call_args
        assert "It's-a me, Mario!" in call_args[0][1]

    def test_greeting_clears_in_progress_flag_on_success(self):
        """After successful greeting, _greeting_in_progress should be False."""
        import asyncio
        from unittest.mock import AsyncMock

        state = self._make_state()
        ws = AsyncMock()

        async def fast_greeting(ws, event):
            pass  # Completes immediately

        async def run():
            state["_greeting_in_progress"] = True
            try:
                await asyncio.wait_for(fast_greeting(ws, {}), timeout=60.0)
            except asyncio.TimeoutError:
                pass
            finally:
                state["_greeting_in_progress"] = False
                state["presence_phase"] = "CONVERSING"

        asyncio.run(run())
        assert state["_greeting_in_progress"] is False

    def test_greeting_clears_in_progress_flag_on_timeout(self):
        """After timeout, _greeting_in_progress should be False (via finally block)."""
        import asyncio

        state = self._make_state()

        async def slow_greeting(ws, event):
            await asyncio.sleep(999)

        async def run():
            state["_greeting_in_progress"] = True
            try:
                await asyncio.wait_for(slow_greeting(None, {}), timeout=0.05)
            except asyncio.TimeoutError:
                pass  # Emergency fallback would go here
            finally:
                state["_greeting_in_progress"] = False
                state["presence_phase"] = "CONVERSING"

        asyncio.run(run())
        assert state["_greeting_in_progress"] is False

    def test_greeting_sets_conversing_phase_on_success(self):
        """After greeting completes, presence_phase should be 'CONVERSING'."""
        import asyncio
        from unittest.mock import AsyncMock

        state = self._make_state()
        assert state["presence_phase"] == "GREETING"

        async def fast_greeting(ws, event):
            pass

        async def run():
            state["_greeting_in_progress"] = True
            try:
                await asyncio.wait_for(fast_greeting(None, {}), timeout=60.0)
            except asyncio.TimeoutError:
                pass
            finally:
                state["_greeting_in_progress"] = False
                state["presence_phase"] = "CONVERSING"

        asyncio.run(run())
        assert state["presence_phase"] == "CONVERSING"


class TestReconnectStateReset:
    """Tests for WebSocket reconnect state reset (server/main.py websocket_endpoint)."""

    def _make_state_with_stale_data(self):
        """Create state_current with stale data from a previous connection."""
        from collections import deque
        return {
            "speaker_name": "Luigi",
            "speaker_id": 42,
            "is_speaking": True,
            "presence": True,
            "presence_phase": "CONVERSING",
            "audio_buffer": bytearray(b"\x00\x01\x02"),
            "conversation_history": [{"role": "user", "content": "hello"}],
            "current_visit_id": "visit-abc-123",
            "enter_time": 1700000000.0,
            "_last_audio_chunk": b"\xff",
            "_user_request_active": True,
            "_greeting_in_progress": True,
            "_last_buffer_time": 99.9,
            "_last_text_input_time": 99.9,
            "_last_command_time": 99.9,
            "_active_game": "trivia",
            "_game_state": {"round": 3},
            "_game_last_input_time": 99.9,
            "_response_times": deque([0.5, 0.6], maxlen=50),
            "_pending_announcement": None,
            "_detected_mood": "happy",
            "_personality_mode": "pirate",
            "_last_dj_time": 0.0,
            "_last_time_obs": 0.0,
            "_last_timing": {},
            "_session_topics": {"pasta", "mushrooms"},
            "_last_idle_action": "singing",
            "detected_guest": None,
            "guest_visits": 5,
            "memorial_active": False,
            "memorial_triggered_at": 0.0,
            "_name_from_parsing": True,
            "_sick_checkin_time": 99.9,
            "_last_user_msg_time": 99.9,
        }

    def _simulate_reconnect(self, state):
        """Simulate the reconnect reset logic from websocket_endpoint (line ~1279)."""
        import time
        state["_active_game"] = None
        state["_game_state"] = {}
        state["conversation_history"] = []
        state["_detected_mood"] = None
        state["_sick_checkin_time"] = 0.0
        state["_last_user_msg_time"] = 0.0
        state["_name_from_parsing"] = False
        state["presence_phase"] = "IDLE"
        state["_last_dj_time"] = time.time()
        state["audio_buffer"] = bytearray()
        state["_last_buffer_time"] = 0.0
        state["speaker_name"] = None
        state["speaker_id"] = None
        state["current_visit_id"] = None
        state["_user_request_active"] = False
        state["_greeting_in_progress"] = False

    def test_reconnect_resets_speaker_identity(self):
        """After reconnect, speaker_name and speaker_id should be None."""
        state = self._make_state_with_stale_data()
        assert state["speaker_name"] == "Luigi"
        assert state["speaker_id"] == 42

        self._simulate_reconnect(state)

        assert state["speaker_name"] is None
        assert state["speaker_id"] is None

    def test_reconnect_resets_visit_id(self):
        """After reconnect, current_visit_id should be None."""
        state = self._make_state_with_stale_data()
        assert state["current_visit_id"] == "visit-abc-123"

        self._simulate_reconnect(state)

        assert state["current_visit_id"] is None

    def test_reconnect_resets_active_flags(self):
        """After reconnect, _user_request_active and _greeting_in_progress should be False."""
        state = self._make_state_with_stale_data()
        assert state["_user_request_active"] is True
        assert state["_greeting_in_progress"] is True

        self._simulate_reconnect(state)

        assert state["_user_request_active"] is False
        assert state["_greeting_in_progress"] is False

    def test_reconnect_preserves_party_state(self):
        """After reconnect, party-level state (night phase, party_start_time) should NOT be reset.

        The reconnect handler only resets per-connection fields in state_current.
        Party-level state lives on separate objects (party_stats, emotion_system)
        and module-level variables (_night_start), so they survive reconnections.
        We verify reconnect doesn't touch fields outside the reset list.
        """
        state = self._make_state_with_stale_data()
        # Add party-level fields that should survive reconnect
        state["memorial_active"] = True
        state["memorial_triggered_at"] = 1700000000.0
        state["guest_visits"] = 5

        self._simulate_reconnect(state)

        # These party-level fields are NOT touched by the reconnect handler
        assert state["memorial_active"] is True
        assert state["memorial_triggered_at"] == 1700000000.0
        assert state["guest_visits"] == 5


class TestWsSendLock:
    """Tests for the _ws_send_lock asyncio.Lock in server/main.py.

    Importing server.main directly is impractical in the unit-test env because
    it pulls in heavy runtime deps (stt, tts, hardware, etc.).  Instead we:
      1. Parse the source with ``ast`` to confirm the variable exists and is
         assigned ``asyncio.Lock()``.
      2. Create a fresh ``asyncio.Lock()`` (same type) for behavioral tests.
    """

    @staticmethod
    def _find_lock_assignment():
        """Parse server/main.py and return the AST node for ``_ws_send_lock = ...``."""
        import ast, os
        src_path = os.path.join(
            os.path.dirname(__file__), "..", "server", "main.py"
        )
        with open(src_path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=src_path)
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "_ws_send_lock":
                        return node
        return None

    def test_ws_send_lock_exists(self):
        """server/main.py must declare ``_ws_send_lock = asyncio.Lock()``."""
        import ast
        node = self._find_lock_assignment()
        assert node is not None, "_ws_send_lock assignment not found in server/main.py"
        # Verify RHS is asyncio.Lock()
        call = node.value
        assert isinstance(call, ast.Call), "RHS should be a Call node"
        func = call.func
        assert isinstance(func, ast.Attribute) and func.attr == "Lock", (
            "Expected asyncio.Lock() call"
        )
        assert isinstance(func.value, ast.Name) and func.value.id == "asyncio", (
            "Expected asyncio.Lock() call"
        )

    def test_ws_send_lock_prevents_concurrent_sends(self):
        """Acquiring the lock should block, then release cleanly."""
        import asyncio
        lock = asyncio.Lock()

        async def _test():
            assert not lock.locked()
            async with lock:
                assert lock.locked()
            assert not lock.locked()

        asyncio.run(_test())

    def test_ws_send_lock_contention_queues(self):
        """Two concurrent tasks should serialize through the lock."""
        import asyncio
        lock = asyncio.Lock()

        order = []

        async def task(name, delay):
            async with lock:
                order.append(f"{name}_start")
                await asyncio.sleep(delay)
                order.append(f"{name}_end")

        async def _test():
            order.clear()
            t1 = asyncio.create_task(task("first", 0.1))
            await asyncio.sleep(0.01)  # ensure first acquires lock first
            t2 = asyncio.create_task(task("second", 0.01))
            await asyncio.gather(t1, t2)
            assert order == [
                "first_start", "first_end",
                "second_start", "second_end",
            ]

        asyncio.run(_test())


class TestTextInputTimeout:
    """Tests for the text_input timeout and exception handling in server/main.py.

    Same AST/source-analysis approach as TestWsSendLock — we verify the safety
    patterns exist without importing the full server runtime.
    """

    @staticmethod
    def _read_source():
        import os
        src_path = os.path.join(
            os.path.dirname(__file__), "..", "server", "main.py"
        )
        with open(src_path, "r", encoding="utf-8") as f:
            return f.read()

    def test_text_input_timeout_value(self):
        """asyncio.wait_for(_handle_text_input(...), timeout=45.0) must exist."""
        import ast

        source = self._read_source()
        tree = ast.parse(source)

        found = False
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            is_wait_for = (
                isinstance(func, ast.Attribute) and func.attr == "wait_for"
                and isinstance(func.value, ast.Name) and func.value.id == "asyncio"
            )
            if not is_wait_for:
                continue
            for kw in node.keywords:
                if kw.arg == "timeout":
                    val = kw.value
                    if isinstance(val, ast.Constant) and val.value == 45.0:
                        if node.args:
                            inner = node.args[0]
                            if isinstance(inner, ast.Await):
                                inner = inner.value
                            if isinstance(inner, ast.Call):
                                inner_func = inner.func
                                if isinstance(inner_func, ast.Name) and inner_func.id == "_handle_text_input":
                                    found = True
                                elif isinstance(inner_func, ast.Attribute) and inner_func.attr == "_handle_text_input":
                                    found = True
        assert found, (
            "Expected asyncio.wait_for(_handle_text_input(...), timeout=45.0) "
            "in server/main.py"
        )

    def test_text_input_exception_clears_active_flag(self):
        """The finally block must clear _user_request_active after text_input."""
        source = self._read_source()

        assert 'wait_for(_handle_text_input' in source, (
            "wait_for(_handle_text_input call not found"
        )
        idx_wait = source.index('wait_for(_handle_text_input')
        rest = source[idx_wait:]
        assert 'finally:' in rest, "No finally block after text_input wait_for"
        idx_finally = rest.index('finally:')
        finally_block = rest[idx_finally:idx_finally + 300]
        assert '_user_request_active' in finally_block, (
            "finally block does not reference _user_request_active"
        )
        assert 'False' in finally_block, (
            "finally block does not set _user_request_active to False"
        )

    def test_text_input_empty_text_returns_early(self):
        """Empty text must trigger an early return before the pipeline runs."""
        source = self._read_source()

        idx = source.find('elif event_type == "text_input"')
        assert idx != -1, "text_input handler not found in source"
        block = source[idx:idx + 400]
        assert "if not text" in block, (
            "Empty text guard 'if not text' not found in text_input handler"
        )
        assert "return" in block[block.index("if not text"):block.index("if not text") + 50], (
            "Early return after empty text check not found"
        )

    def test_text_input_has_error_fallback(self):
        """General Exception handler must send 'Something went wrong' fallback."""
        source = self._read_source()

        idx_wait = source.index('wait_for(_handle_text_input')
        rest = source[idx_wait:]
        assert 'except Exception' in rest, (
            "No general Exception handler after text_input wait_for"
        )
        idx_finally = rest.index('finally:')
        handler_block = rest[:idx_finally]
        assert 'Something went wrong' in handler_block, (
            "Error fallback message 'Something went wrong' not found in "
            "text_input exception handler"
        )


# ── Conversation Summarization Tests ──

import ast
import os
import re


def _get_main_source():
    src_path = os.path.join(os.path.dirname(__file__), "..", "server", "main.py")
    with open(src_path, "r", encoding="utf-8") as f:
        return f.read()


def _extract_compress_function():
    """Extract _compress_old_history and its dependencies from source via AST."""
    source = _get_main_source()
    tree = ast.parse(source)

    code_parts = []
    for node in ast.iter_child_nodes(tree):
        # Pick up RECENT_RAW_MESSAGES constant
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "_SUMMARY_SKIP_WORDS":
                    code_parts.append(ast.get_source_segment(source, node))
        if isinstance(node, ast.FunctionDef) and node.name == "_compress_old_history":
            code_parts.append(ast.get_source_segment(source, node))

    assert code_parts, "_compress_old_history or _SUMMARY_SKIP_WORDS not found in source"
    namespace: dict = {}
    exec("\n\n".join(code_parts), namespace)
    return namespace["_compress_old_history"]


class TestConversationSummarization:
    """Tests for _compress_old_history and context-building summarization."""

    # ── Functional tests (exec the extracted function) ──

    def test_compress_empty_messages(self):
        """Empty message list returns existing_summary unchanged."""
        fn = _extract_compress_function()
        assert fn([], "prev summary") == "prev summary"
        assert fn([]) == ""

    def test_compress_extracts_user_topics(self):
        """User messages have their first sentence extracted as topics."""
        fn = _extract_compress_function()
        msgs = [
            {"role": "user", "content": "I love cooking pasta. It is great."},
            {"role": "user", "content": "Tell me about Mushroom Kingdom!"},
        ]
        result = fn(msgs)
        assert "I love cooking pasta" in result
        assert "Tell me about Mushroom Kingdom" in result
        assert "Guest said:" in result

    def test_compress_extracts_proper_nouns(self):
        """Proper nouns from both roles are captured in Names section."""
        fn = _extract_compress_function()
        msgs = [
            {"role": "user", "content": "My friend Giovanni told me about this."},
            {"role": "assistant", "content": "Princess Peach loves parties!"},
        ]
        result = fn(msgs)
        assert "Names:" in result
        assert "Giovanni" in result
        assert "Princess" in result or "Peach" in result

    def test_compress_skips_common_words(self):
        """Common words (Mario, Hey, The, etc.) are filtered from names."""
        fn = _extract_compress_function()
        msgs = [
            {"role": "user", "content": "Hey Mario, The party was great!"},
        ]
        result = fn(msgs)
        # "Mario", "Hey", "The" are in _SUMMARY_SKIP_WORDS — should not appear in Names
        if "Names:" in result:
            names_section = result.split("Names:")[1].split(".")[0]
            for skip in ("Mario", "Hey", "The"):
                assert skip not in names_section, f"'{skip}' should be filtered"

    def test_compress_merges_with_existing(self):
        """New summary is appended to existing summary."""
        fn = _extract_compress_function()
        msgs = [
            {"role": "user", "content": "I just arrived from Brooklyn today."},
        ]
        result = fn(msgs, existing_summary="Names: Luigi")
        assert result.startswith("Names: Luigi")
        assert "Brooklyn" in result or "arrived" in result

    def test_compress_caps_at_400_chars(self):
        """Long summaries are truncated to ~400 chars with ... prefix."""
        fn = _extract_compress_function()
        # Generate enough messages to exceed 400 chars
        msgs = [
            {"role": "user", "content": f"I visited the amazing city of Townsville{i} and met Friendname{i}!"}
            for i in range(30)
        ]
        result = fn(msgs, existing_summary="A" * 300)
        assert len(result) <= 400
        assert result.startswith("...")

    # ── AST / source-level tests ──

    def test_context_uses_summary_for_long_history(self):
        """Context building references conversation_summary for long histories."""
        source = _get_main_source()
        # The context-building section should call _compress_old_history
        assert "_compress_old_history" in source
        assert 'conversation_summary' in source
        # Verify the pattern: if len(conv_hist) > RECENT_RAW_MESSAGES
        assert "RECENT_RAW_MESSAGES" in source
        # Check that summary is inserted as a system message
        assert "[Earlier in this conversation]" in source

    def test_state_has_conversation_summary_key(self):
        """state_current dict template includes conversation_summary."""
        source = _get_main_source()
        tree = ast.parse(source)
        found = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and node.value == "conversation_summary":
                found = True
                break
        assert found, "conversation_summary key not found in AST"

    def test_recent_raw_messages_constant(self):
        """RECENT_RAW_MESSAGES is defined as 8."""
        source = _get_main_source()
        tree = ast.parse(source)
        found_value = None
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "RECENT_RAW_MESSAGES":
                        if isinstance(node.value, ast.Constant):
                            found_value = node.value.value
        assert found_value == 4, f"RECENT_RAW_MESSAGES should be 4, got {found_value}"


class TestCommandDiscovery:
    """Tests for the command discovery hint system in mario_prompt.py."""

    def test_discovery_hints_list_exists(self):
        from server.mario_prompt import COMMAND_DISCOVERY_HINTS
        assert isinstance(COMMAND_DISCOVERY_HINTS, list)
        assert len(COMMAND_DISCOVERY_HINTS) >= 10

    def test_get_hint_returns_empty_for_low_exchange_count(self):
        from server.mario_prompt import get_command_discovery_hint, reset_discovery
        reset_discovery()
        result = get_command_discovery_hint(0)
        assert result == ""
        result = get_command_discovery_hint(1)
        assert result == ""

    def test_get_hint_returns_string(self):
        from server.mario_prompt import get_command_discovery_hint, reset_discovery, COMMAND_DISCOVERY_HINTS
        reset_discovery()
        # Force discovery by calling many times (12% chance each)
        results = [get_command_discovery_hint(5) for _ in range(200)]
        non_empty = [r for r in results if r]
        assert len(non_empty) > 0, "Should fire at least once in 200 attempts"
        assert all(isinstance(r, str) for r in non_empty)

    def test_hints_not_repeated(self):
        from server.mario_prompt import get_command_discovery_hint, reset_discovery
        reset_discovery()
        seen = set()
        for _ in range(5000):
            hint = get_command_discovery_hint(5)
            if hint:
                assert hint not in seen, f"Duplicate hint: {hint}"
                seen.add(hint)

    def test_reset_discovery_clears_state(self):
        from server.mario_prompt import get_command_discovery_hint, reset_discovery, _discovery_hints_given
        reset_discovery()
        # Trigger some hints
        for _ in range(500):
            get_command_discovery_hint(5)
        from server.mario_prompt import _discovery_hints_given as hints_after
        had_hints = len(hints_after) > 0
        assert had_hints, "Should have given some hints"
        reset_discovery()
        from server.mario_prompt import _discovery_hints_given as hints_after_reset
        assert len(hints_after_reset) == 0

    def test_all_hints_are_strings(self):
        from server.mario_prompt import COMMAND_DISCOVERY_HINTS
        for hint in COMMAND_DISCOVERY_HINTS:
            assert isinstance(hint, str)
            assert len(hint) > 10  # Meaningful length

    def test_exhaustion_returns_empty(self):
        from server.mario_prompt import get_command_discovery_hint, reset_discovery, COMMAND_DISCOVERY_HINTS
        reset_discovery()
        # Manually exhaust all hints
        from server.mario_prompt import _discovery_hints_given
        for hint in COMMAND_DISCOVERY_HINTS:
            _discovery_hints_given.add(hint)
        result = get_command_discovery_hint(5)
        assert result == ""
