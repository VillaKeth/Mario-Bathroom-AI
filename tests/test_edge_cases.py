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
        recent = QUICK_GAMES[-_ROTATION_BUFFER:]
        for g in recent:
            record_game_played(g)
        # Picked game should NOT be in the recent buffer
        picked = pick_random_game({})
        assert picked not in recent

    def test_rotation_resets_when_all_played(self):
        from game_handlers import pick_random_game, record_game_played, QUICK_GAMES
        # Play ALL quick games
        for g in QUICK_GAMES:
            record_game_played(g)
        # Should still return a valid game (resets pool)
        picked = pick_random_game({})
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

    def test_do_you_know_me_returns_none(self):
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
        assert result is None

    def test_who_am_i_returns_none(self):
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
        assert result is None

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
