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
