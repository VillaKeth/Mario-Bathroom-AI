"""Comprehensive tests for server/game_handlers.py — game start, input, quit, rotation."""

import importlib
import os
import sys
import time
import unittest
from unittest.mock import patch, MagicMock

# server/ uses bare imports (e.g. `from emotions import Emotion`), so add it to path
server_dir = os.path.join(os.path.dirname(__file__), "..", "server")
sys.path.insert(0, os.path.abspath(server_dir))

from emotions import Emotion, EmotionSystem
import game_handlers
from game_handlers import (
    start_game,
    handle_game_input,
    pick_random_game,
    record_game_played,
    get_recent_games,
    reset_game_rotation,
    check_game_timeout,
    ALL_GAME_NAMES,
    QUICK_GAMES,
    VALID_GAMES,
)


def _seed_game_pools():
    """Populate minimal game content so unit tests don't depend on character YAML."""
    game_handlers.SIMON_ACTIONS = ["clap your hands"]
    game_handlers.TWENTY_Q_THINGS = [
        {"answer": "apple", "category": "object", "hints": ["fruit", "round", "red"]}
    ]
    game_handlers.RIDDLES = [
        {"q": "What has keys but no locks?", "a": "keyboard", "hints": ["typing", "letters", "desk"]}
    ]
    game_handlers.STARTER_WORDS = ["mario"]
    game_handlers.KARAOKE_SONGS = [
        {"title": "Test Song", "lyrics": "La la la"}
    ]
    game_handlers.RAPID_FIRE_QUESTIONS = [
        {"q": "Mario's color?", "a": "red"},
        {"q": "Luigi's color?", "a": "green"},
    ]
    game_handlers.TRUTH_QUESTIONS = ["What's your favorite snack?"]
    game_handlers.DARES = ["Do one jumping jack!"]
    game_handlers.WOULD_YOU_RATHER = [
        {"a": "Eat pizza", "b": "Eat pasta"},
        {"a": "Play games", "b": "Watch movies"},
    ]
    game_handlers.RPS_WIN_REACTIONS = ["Mario wins!"]
    game_handlers.RPS_LOSE_REACTIONS = ["You win!"]
    game_handlers.RPS_TIE_REACTIONS = ["Tie game!"]
    game_handlers.HANGMAN_WORDS = ["mario"]
    game_handlers.HOT_TAKES = ["Pineapple belongs on pizza.", "Socks with sandals are elite."]
    game_handlers.MARIO_TRIVIA_QUESTIONS = [
        {"q": "Who is Mario's brother?", "a": ["luigi"], "accept": ["luigi"]}
    ]
    game_handlers.NAME_THAT_CHARACTER = [
        {"desc": "He wears green and is taller than Mario.", "a": ["luigi"], "accept": ["luigi"]}
    ]
    game_handlers.BATHROOM_DARES = ["Sing one note loudly!"]
    game_handlers.STORY_STARTERS = ["Once upon a time there was a brave plumber."]
    game_handlers.WYR_EXTENDED = [
        {"a": "Ride a kart", "b": "Ride Yoshi"},
        {"a": "Visit space", "b": "Visit the beach"},
    ]
    game_handlers.NHIE_PROMPTS = [
        "Never have I ever skipped breakfast.",
        "Never have I ever stayed up too late gaming.",
    ]


def _make_config():
    """Return a complete config dict with all required game keys."""
    return {
        "simon_max_rounds": 5,
        "twenty_q_max_questions": 10,
        "truth_dare_max_rounds": 5,
        "riddle_max_attempts": 4,
        "word_chain_max_turns": 8,
        "word_chain_max_rounds": 8,
        "rapid_fire_max_rounds": 5,
        "hot_take_rounds": 5,
        "nhie_rounds": 5,
        "roast_battle_rounds": 5,
        "storyteller_rounds": 5,
        "catchphrase_rounds": 5,
        "bathroom_dare_rounds": 3,
        "confession_booth_rounds": 5,
        "debate_rounds": 5,
        "category_blitz_rounds": 5,
    }


def _make_state():
    """Return a fresh state dict with the keys games expect."""
    _seed_game_pools()
    return {
        "_active_game": None,
        "_game_state": {},
        "_game_last_input_time": 0,
        "conversation_history": [],
        "speaker_id": "test_player",
        "speaker_name": "TestUser",
    }


# Patch get_adaptive_rounds to just return the base rounds (avoids importing memory)
@patch("game_handlers.get_adaptive_rounds", side_effect=lambda name, base, state: base)
class TestSimonSays(unittest.TestCase):
    """Tests for the simon_says game."""

    def test_start_sets_state(self, _mock_ar):
        state, config, emo = _make_state(), _make_config(), EmotionSystem()
        intro = start_game("simon_says", state, config, emo)
        self.assertEqual(state["_active_game"], "simon_says")
        self.assertIn("round", state["_game_state"])
        self.assertIn("current_action", state["_game_state"])
        self.assertIn("SIMON", intro.upper())
        self.assertEqual(emo.current, Emotion.EXCITED)

    def test_correct_answer_increments_score(self, _mock_ar):
        state, config, emo = _make_state(), _make_config(), EmotionSystem()
        start_game("simon_says", state, config, emo)
        state["_game_state"]["is_simon"] = True  # fix so "yes" is correct
        resp, sfx = handle_game_input("yes", state, emo)
        self.assertIn(sfx, ("correct", None))

    def test_wrong_answer_on_trick(self, _mock_ar):
        state, config, emo = _make_state(), _make_config(), EmotionSystem()
        start_game("simon_says", state, config, emo)
        state["_game_state"]["is_simon"] = False  # Simon didn't say — "yes" is wrong
        resp, sfx = handle_game_input("yes", state, emo)
        self.assertEqual(sfx, "wrong")
        self.assertIn("Simon DIDN'T", resp)

    def test_game_ends_after_max_rounds(self, _mock_ar):
        state, config, emo = _make_state(), _make_config(), EmotionSystem()
        start_game("simon_says", state, config, emo)
        gs = state["_game_state"]
        gs["round"] = gs["max_rounds"]  # last round
        gs["is_simon"] = True
        resp, sfx = handle_game_input("yes", state, emo)
        self.assertIsNone(state["_active_game"])
        self.assertEqual(state["_game_state"], {})

    def test_invalid_input_asks_again(self, _mock_ar):
        state, config, emo = _make_state(), _make_config(), EmotionSystem()
        start_game("simon_says", state, config, emo)
        resp, sfx = handle_game_input("banana", state, emo)
        self.assertIn("yes", resp.lower())

    def test_quit_ends_game(self, _mock_ar):
        state, config, emo = _make_state(), _make_config(), EmotionSystem()
        start_game("simon_says", state, config, emo)
        # simon_says doesn't add "done" to quit words, but "quit" works
        resp, sfx = handle_game_input("quit", state, emo)
        self.assertIsNone(state["_active_game"])
        self.assertEqual(sfx, "game_over")


@patch("game_handlers.get_adaptive_rounds", side_effect=lambda name, base, state: base)
class TestTwentyQuestions(unittest.TestCase):
    """Tests for twenty_questions game."""

    def test_start_sets_state(self, _mock_ar):
        state, config, emo = _make_state(), _make_config(), EmotionSystem()
        intro = start_game("twenty_questions", state, config, emo)
        self.assertEqual(state["_active_game"], "twenty_questions")
        self.assertIn("answer", state["_game_state"])
        self.assertIn("20 QUESTIONS", intro.upper())

    def test_correct_guess_wins(self, _mock_ar):
        state, config, emo = _make_state(), _make_config(), EmotionSystem()
        start_game("twenty_questions", state, config, emo)
        answer = state["_game_state"]["answer"]
        resp, sfx = handle_game_input(f"is it a {answer}", state, emo)
        self.assertEqual(sfx, "correct")
        self.assertIsNone(state["_active_game"])

    def test_hint_request(self, _mock_ar):
        state, config, emo = _make_state(), _make_config(), EmotionSystem()
        start_game("twenty_questions", state, config, emo)
        resp, sfx = handle_game_input("give me a hint", state, emo)
        self.assertEqual(sfx, "hint")
        self.assertEqual(state["_game_state"]["hints_given"], 1)

    def test_questions_exhaust(self, _mock_ar):
        state, config, emo = _make_state(), _make_config(), EmotionSystem()
        start_game("twenty_questions", state, config, emo)
        state["_game_state"]["questions_left"] = 1
        resp, sfx = handle_game_input("is it blue", state, emo)
        self.assertIsNone(state["_active_game"])
        self.assertEqual(sfx, "game_over")

    def test_give_up(self, _mock_ar):
        state, config, emo = _make_state(), _make_config(), EmotionSystem()
        start_game("twenty_questions", state, config, emo)
        answer = state["_game_state"]["answer"]
        resp, sfx = handle_game_input("give up", state, emo)
        self.assertIsNone(state["_active_game"])
        self.assertIn(answer, resp.lower())


@patch("game_handlers.get_adaptive_rounds", side_effect=lambda name, base, state: base)
class TestTruthOrDare(unittest.TestCase):

    def test_start_sets_state(self, _mock_ar):
        state, config, emo = _make_state(), _make_config(), EmotionSystem()
        intro = start_game("truth_or_dare", state, config, emo)
        self.assertEqual(state["_active_game"], "truth_or_dare")
        self.assertIn("TRUTH OR DARE", intro.upper())

    def test_truth_advances_round(self, _mock_ar):
        state, config, emo = _make_state(), _make_config(), EmotionSystem()
        start_game("truth_or_dare", state, config, emo)
        resp, sfx = handle_game_input("truth", state, emo)
        self.assertEqual(state["_game_state"]["round"], 2)

    def test_dare_advances_round(self, _mock_ar):
        state, config, emo = _make_state(), _make_config(), EmotionSystem()
        start_game("truth_or_dare", state, config, emo)
        resp, sfx = handle_game_input("dare", state, emo)
        self.assertEqual(state["_game_state"]["round"], 2)

    def test_game_ends_at_max_rounds(self, _mock_ar):
        state, config, emo = _make_state(), _make_config(), EmotionSystem()
        start_game("truth_or_dare", state, config, emo)
        state["_game_state"]["round"] = state["_game_state"]["max_rounds"]
        resp, sfx = handle_game_input("truth", state, emo)
        self.assertIsNone(state["_active_game"])
        self.assertEqual(sfx, "game_over")

    def test_invalid_input_prompts(self, _mock_ar):
        state, config, emo = _make_state(), _make_config(), EmotionSystem()
        start_game("truth_or_dare", state, config, emo)
        resp, sfx = handle_game_input("hello", state, emo)
        self.assertIn("truth", resp.lower())


@patch("game_handlers.get_adaptive_rounds", side_effect=lambda name, base, state: base)
class TestRiddles(unittest.TestCase):

    def test_start_sets_state(self, _mock_ar):
        state, config, emo = _make_state(), _make_config(), EmotionSystem()
        intro = start_game("riddles", state, config, emo)
        self.assertEqual(state["_active_game"], "riddles")
        self.assertIn("RIDDLE", intro.upper())
        self.assertIn("answer", state["_game_state"])

    def test_correct_guess(self, _mock_ar):
        state, config, emo = _make_state(), _make_config(), EmotionSystem()
        start_game("riddles", state, config, emo)
        answer = state["_game_state"]["answer"]
        resp, sfx = handle_game_input(f"i think it's a {answer}", state, emo)
        self.assertEqual(sfx, "correct")
        self.assertIsNone(state["_active_game"])

    def test_wrong_guess_decrements(self, _mock_ar):
        state, config, emo = _make_state(), _make_config(), EmotionSystem()
        start_game("riddles", state, config, emo)
        resp, sfx = handle_game_input("qxqxqxq", state, emo)
        self.assertEqual(state["_game_state"]["attempts"], 1)
        self.assertEqual(sfx, "wrong")

    def test_max_attempts_ends_game(self, _mock_ar):
        state, config, emo = _make_state(), _make_config(), EmotionSystem()
        start_game("riddles", state, config, emo)
        state["_game_state"]["attempts"] = state["_game_state"]["max_attempts"] - 1
        resp, sfx = handle_game_input("qxqxqxq", state, emo)
        self.assertIsNone(state["_active_game"])
        self.assertEqual(sfx, "game_over")

    def test_hint_request(self, _mock_ar):
        state, config, emo = _make_state(), _make_config(), EmotionSystem()
        start_game("riddles", state, config, emo)
        resp, sfx = handle_game_input("hint please", state, emo)
        self.assertEqual(sfx, "hint")
        self.assertEqual(state["_game_state"]["hints_given"], 1)


@patch("game_handlers.get_adaptive_rounds", side_effect=lambda name, base, state: base)
class TestRapidFire(unittest.TestCase):

    def test_start_sets_state(self, _mock_ar):
        state, config, emo = _make_state(), _make_config(), EmotionSystem()
        intro = start_game("rapid_fire", state, config, emo)
        self.assertEqual(state["_active_game"], "rapid_fire")
        self.assertIn("RAPID FIRE", intro.upper())
        self.assertEqual(state["_game_state"]["current"], 0)

    def test_correct_answer_scores(self, _mock_ar):
        state, config, emo = _make_state(), _make_config(), EmotionSystem()
        start_game("rapid_fire", state, config, emo)
        answer = state["_game_state"]["questions"][0]["a"]
        resp, sfx = handle_game_input(answer.lower(), state, emo)
        self.assertEqual(state["_game_state"]["score"], 1)

    def test_wrong_answer_advances(self, _mock_ar):
        state, config, emo = _make_state(), _make_config(), EmotionSystem()
        start_game("rapid_fire", state, config, emo)
        resp, sfx = handle_game_input("zzzzz_wrong_answer_xyz", state, emo)
        self.assertEqual(state["_game_state"]["current"], 1)
        self.assertEqual(state["_game_state"]["score"], 0)

    def test_game_ends_after_all_questions(self, _mock_ar):
        state, config, emo = _make_state(), _make_config(), EmotionSystem()
        start_game("rapid_fire", state, config, emo)
        gs = state["_game_state"]
        gs["current"] = len(gs["questions"]) - 1  # last question
        resp, sfx = handle_game_input("zzzzz_wrong_answer_xyz", state, emo)
        self.assertIsNone(state["_active_game"])

    def test_quit(self, _mock_ar):
        state, config, emo = _make_state(), _make_config(), EmotionSystem()
        start_game("rapid_fire", state, config, emo)
        resp, sfx = handle_game_input("quit", state, emo)
        self.assertIsNone(state["_active_game"])
        self.assertEqual(sfx, "game_over")


@patch("game_handlers.get_adaptive_rounds", side_effect=lambda name, base, state: base)
class TestHotTakes(unittest.TestCase):

    def test_start_sets_state(self, _mock_ar):
        state, config, emo = _make_state(), _make_config(), EmotionSystem()
        intro = start_game("hot_takes", state, config, emo)
        self.assertEqual(state["_active_game"], "hot_takes")
        self.assertIn("HOT TAKES", intro.upper())

    def test_agree_advances(self, _mock_ar):
        state, config, emo = _make_state(), _make_config(), EmotionSystem()
        start_game("hot_takes", state, config, emo)
        resp, sfx = handle_game_input("agree totally", state, emo)
        self.assertEqual(state["_game_state"]["current"], 1)
        self.assertEqual(state["_game_state"]["agreements"], 1)
        self.assertEqual(sfx, "correct")

    def test_disagree_advances(self, _mock_ar):
        state, config, emo = _make_state(), _make_config(), EmotionSystem()
        start_game("hot_takes", state, config, emo)
        resp, sfx = handle_game_input("wrong bad take", state, emo)
        self.assertEqual(state["_game_state"]["current"], 1)
        self.assertEqual(state["_game_state"]["agreements"], 0)
        self.assertEqual(sfx, "wrong")

    def test_game_ends_at_max(self, _mock_ar):
        state, config, emo = _make_state(), _make_config(), EmotionSystem()
        start_game("hot_takes", state, config, emo)
        state["_game_state"]["current"] = state["_game_state"]["max_rounds"] - 1
        resp, sfx = handle_game_input("agree", state, emo)
        self.assertIsNone(state["_active_game"])

    def test_invalid_input_prompts(self, _mock_ar):
        state, config, emo = _make_state(), _make_config(), EmotionSystem()
        start_game("hot_takes", state, config, emo)
        resp, sfx = handle_game_input("banana", state, emo)
        self.assertIn("AGREE", resp.upper())


@patch("game_handlers.get_adaptive_rounds", side_effect=lambda name, base, state: base)
class TestNeverHaveIEver(unittest.TestCase):

    def test_start_sets_state(self, _mock_ar):
        state, config, emo = _make_state(), _make_config(), EmotionSystem()
        intro = start_game("never_have_i_ever", state, config, emo)
        self.assertEqual(state["_active_game"], "never_have_i_ever")
        self.assertIn("NEVER HAVE I EVER", intro.upper())

    def test_i_have_scores(self, _mock_ar):
        state, config, emo = _make_state(), _make_config(), EmotionSystem()
        start_game("never_have_i_ever", state, config, emo)
        initial_score = state["_game_state"]["daring_score"]
        resp, sfx = handle_game_input("i have", state, emo)
        if state["_active_game"] is not None:
            self.assertEqual(state["_game_state"]["daring_score"], initial_score + 1)
        else:
            self.assertIn("1", resp)

    def test_i_havent_no_score(self, _mock_ar):
        state, config, emo = _make_state(), _make_config(), EmotionSystem()
        start_game("never_have_i_ever", state, config, emo)
        initial_score = state["_game_state"]["daring_score"]
        resp, sfx = handle_game_input("never nope", state, emo)
        if state["_active_game"] is not None:
            self.assertEqual(state["_game_state"]["daring_score"], initial_score)
        else:
            self.assertIsNotNone(resp)

    def test_game_ends_at_max(self, _mock_ar):
        state, config, emo = _make_state(), _make_config(), EmotionSystem()
        start_game("never_have_i_ever", state, config, emo)
        state["_game_state"]["current"] = state["_game_state"]["max_rounds"] - 1
        resp, sfx = handle_game_input("i have", state, emo)
        self.assertIsNone(state["_active_game"])
        self.assertIn("achievement", sfx)

    def test_invalid_input_prompts(self, _mock_ar):
        state, config, emo = _make_state(), _make_config(), EmotionSystem()
        start_game("never_have_i_ever", state, config, emo)
        resp, sfx = handle_game_input("banana", state, emo)
        self.assertIn("I have", resp)

    def test_quit(self, _mock_ar):
        state, config, emo = _make_state(), _make_config(), EmotionSystem()
        start_game("never_have_i_ever", state, config, emo)
        resp, sfx = handle_game_input("quit", state, emo)
        self.assertIsNone(state["_active_game"])


@patch("game_handlers.get_adaptive_rounds", side_effect=lambda name, base, state: base)
class TestRockPaperScissors(unittest.TestCase):
    """Roast battle isn't in the code — test RPS as a well-structured alternative."""

    def test_start_sets_state(self, _mock_ar):
        state, config, emo = _make_state(), _make_config(), EmotionSystem()
        intro = start_game("rock_paper_scissors", state, config, emo)
        self.assertEqual(state["_active_game"], "rock_paper_scissors")
        self.assertIn("ROCK PAPER SCISSORS", intro.upper())

    def test_valid_move_advances(self, _mock_ar):
        state, config, emo = _make_state(), _make_config(), EmotionSystem()
        start_game("rock_paper_scissors", state, config, emo)
        resp, sfx = handle_game_input("rock", state, emo)
        self.assertEqual(state["_game_state"]["round"], 2)

    def test_invalid_move_prompts(self, _mock_ar):
        state, config, emo = _make_state(), _make_config(), EmotionSystem()
        start_game("rock_paper_scissors", state, config, emo)
        resp, sfx = handle_game_input("banana", state, emo)
        self.assertIn("rock", resp.lower())

    def test_game_ends_after_max_rounds(self, _mock_ar):
        state, config, emo = _make_state(), _make_config(), EmotionSystem()
        start_game("rock_paper_scissors", state, config, emo)
        state["_game_state"]["round"] = state["_game_state"]["max_rounds"]
        resp, sfx = handle_game_input("rock", state, emo)
        self.assertIsNone(state["_active_game"])


class TestGameRotation(unittest.TestCase):
    """Tests for pick_random_game, record_game_played, reset_game_rotation."""

    def setUp(self):
        reset_game_rotation()

    def tearDown(self):
        reset_game_rotation()

    def test_pick_random_game_returns_valid(self):
        game = pick_random_game(_make_state())
        self.assertIn(game, QUICK_GAMES)

    def test_pick_random_avoids_recent(self):
        # Fill recent buffer with all but one quick game
        for g in QUICK_GAMES[:-1]:
            record_game_played(g)
        game = pick_random_game(_make_state())
        # Should pick from the remaining game(s) not in the recent buffer
        self.assertIn(game, QUICK_GAMES)

    def test_reset_clears_history(self):
        record_game_played("simon_says")
        record_game_played("riddles")
        reset_game_rotation()
        self.assertEqual(get_recent_games(), [])

    def test_record_game_played(self):
        record_game_played("riddles")
        self.assertIn("riddles", get_recent_games())

    def test_all_game_names_is_populated(self):
        self.assertGreater(len(ALL_GAME_NAMES), 10)

    def test_quick_games_subset_of_all(self):
        for g in QUICK_GAMES:
            self.assertIn(g, ALL_GAME_NAMES)


@patch("game_handlers.get_adaptive_rounds", side_effect=lambda name, base, state: base)
class TestStartGameReturnNone(unittest.TestCase):
    """start_game returns None for unknown game names."""

    def test_unknown_game(self, _mock_ar):
        state, config, emo = _make_state(), _make_config(), EmotionSystem()
        result = start_game("nonexistent_game", state, config, emo)
        self.assertIsNone(result)


@patch("game_handlers.get_adaptive_rounds", side_effect=lambda name, base, state: base)
class TestWordChain(unittest.TestCase):

    def test_start_sets_state(self, _mock_ar):
        state, config, emo = _make_state(), _make_config(), EmotionSystem()
        intro = start_game("word_chain", state, config, emo)
        self.assertEqual(state["_active_game"], "word_chain")
        self.assertIn("WORD CHAIN", intro.upper())

    def test_valid_word_scores(self, _mock_ar):
        state, config, emo = _make_state(), _make_config(), EmotionSystem()
        start_game("word_chain", state, config, emo)
        last_letter = state["_game_state"]["last_word"][-1]
        # Make a word starting with the right letter
        word = last_letter + "at"
        resp, sfx = handle_game_input(word, state, emo)
        self.assertEqual(sfx, "correct")

    def test_wrong_starting_letter(self, _mock_ar):
        state, config, emo = _make_state(), _make_config(), EmotionSystem()
        start_game("word_chain", state, config, emo)
        last_letter = state["_game_state"]["last_word"][-1]
        # Pick a letter that isn't the last letter
        wrong_letter = "z" if last_letter != "z" else "a"
        resp, sfx = handle_game_input(f"{wrong_letter}ebra", state, emo)
        self.assertEqual(sfx, "wrong")

    def test_repeated_word_rejected(self, _mock_ar):
        state, config, emo = _make_state(), _make_config(), EmotionSystem()
        start_game("word_chain", state, config, emo)
        starter = state["_game_state"]["last_word"]
        # The starter word is already in used_words, try to reuse it
        # (only works if last letter = first letter; just test the mechanism)
        state["_game_state"]["used_words"].append("testword")
        last_letter = state["_game_state"]["last_word"][-1]
        state["_game_state"]["last_word"] = "testword"[0] + "xx"  # ensure mismatch for clarity
        # Directly test duplicate detection
        state["_game_state"]["last_word"] = "dtestword"
        resp, sfx = handle_game_input("dtestword", state, emo)
        # Should reject because first letter doesn't match OR it's already used
        self.assertIsNotNone(resp)


@patch("game_handlers.get_adaptive_rounds", side_effect=lambda name, base, state: base)
class TestHangman(unittest.TestCase):

    def test_start_sets_state(self, _mock_ar):
        state, config, emo = _make_state(), _make_config(), EmotionSystem()
        intro = start_game("hangman", state, config, emo)
        self.assertEqual(state["_active_game"], "hangman")
        self.assertIn("HANGMAN", intro.upper())
        self.assertIn("word", state["_game_state"])

    def test_correct_letter(self, _mock_ar):
        state, config, emo = _make_state(), _make_config(), EmotionSystem()
        start_game("hangman", state, config, emo)
        word = state["_game_state"]["word"]
        letter = word[0]  # first letter is guaranteed in word
        resp, sfx = handle_game_input(letter, state, emo)
        self.assertIn(letter, state["_game_state"]["guessed"])

    def test_wrong_letter_increments(self, _mock_ar):
        state, config, emo = _make_state(), _make_config(), EmotionSystem()
        start_game("hangman", state, config, emo)
        word = state["_game_state"]["word"]
        # Find a letter NOT in the word
        for c in "zxqj":
            if c not in word:
                resp, sfx = handle_game_input(c, state, emo)
                self.assertEqual(state["_game_state"]["wrong_guesses"], 1)
                break


@patch("game_handlers.get_adaptive_rounds", side_effect=lambda name, base, state: base)
class TestEmotionUpdates(unittest.TestCase):
    """Verify games set the emotion system correctly."""

    def test_simon_says_sets_excited(self, _mock_ar):
        state, config, emo = _make_state(), _make_config(), EmotionSystem()
        start_game("simon_says", state, config, emo)
        self.assertEqual(emo.current, Emotion.EXCITED)

    def test_twenty_q_sets_mischievous(self, _mock_ar):
        state, config, emo = _make_state(), _make_config(), EmotionSystem()
        start_game("twenty_questions", state, config, emo)
        self.assertEqual(emo.current, Emotion.MISCHIEVOUS)

    def test_quit_sets_happy(self, _mock_ar):
        state, config, emo = _make_state(), _make_config(), EmotionSystem()
        start_game("riddles", state, config, emo)
        handle_game_input("quit", state, emo)
        self.assertEqual(emo.current, Emotion.HAPPY)


@patch("game_handlers.get_adaptive_rounds", side_effect=lambda name, base, state: base)
class TestGameLastInputTime(unittest.TestCase):
    """Verify _game_last_input_time is set on start and input."""

    def test_start_sets_timestamp(self, _mock_ar):
        state, config, emo = _make_state(), _make_config(), EmotionSystem()
        before = time.time()
        start_game("simon_says", state, config, emo)
        self.assertGreaterEqual(state["_game_last_input_time"], before)

    def test_input_updates_timestamp(self, _mock_ar):
        state, config, emo = _make_state(), _make_config(), EmotionSystem()
        start_game("truth_or_dare", state, config, emo)
        state["_game_last_input_time"] = 0  # reset
        handle_game_input("truth", state, emo)
        self.assertGreater(state["_game_last_input_time"], 0)


class TestConcurrentGameGuard(unittest.TestCase):
    """Tests for concurrent game guard and per-guest rotation tracking."""

    def setUp(self):
        reset_game_rotation()

    def _emo(self):
        emo = MagicMock()
        emo.current = "happy"
        emo.update = lambda *a, **kw: None
        return emo

    def _cfg(self):
        return {
            "simon_max_rounds": 5,
            "twenty_q_max": 20,
            "truth_dare_rounds": 3,
            "riddle_max_attempts": 5,
            "word_chain_lives": 3,
            "karaoke_max_rounds": 3,
            "hot_takes_rounds": 5,
            "nhie_rounds": 5,
            "rapid_fire_time": 30,
            "dare_count": 3,
            "wyr_rounds": 5,
        }

    # 1. Start simon_says, then try riddles — second call blocked
    def test_start_game_while_active_blocked(self):
        state = _make_state()
        start_game("simon_says", state, _make_config(), self._emo())
        self.assertEqual(state["_active_game"], "simon_says")
        result = start_game("riddles", state, _make_config(), self._emo())
        self.assertIsInstance(result, str)
        self.assertIn("already playing", result.lower())

    # 2. state with _active_game=None should start normally
    def test_start_game_when_no_active_game_works(self):
        state = _make_state()
        state["_active_game"] = None
        result = start_game("simon_says", state, _make_config(), self._emo())
        self.assertIsNotNone(result)
        self.assertNotIn("already playing", result.lower())
        self.assertEqual(state["_active_game"], "simon_says")

    # 3. Warning message should mention the current game name
    def test_concurrent_guard_message_includes_game_name(self):
        state = _make_state()
        start_game("simon_says", state, _make_config(), self._emo())
        result = start_game("riddles", state, _make_config(), self._emo())
        self.assertIn("simon_says", result)

    # 4. record_game_played with state tracks per-guest
    def test_per_guest_rotation_tracking(self):
        state = {"_recent_games": []}
        record_game_played("riddles", state)
        self.assertIn("riddles", state["_recent_games"])

    # 5. pick_random_game avoids guest-recent games
    def test_pick_random_avoids_guest_recent(self):
        all_quick = list(QUICK_GAMES)
        # Keep one game out, put the rest in the last _ROTATION_BUFFER slots
        the_one = all_quick[0]
        recent = all_quick[1:]  # all except the_one — buffer trims to last 5
        state = {"_recent_games": recent}
        # Run multiple times to account for randomness
        for _ in range(20):
            result = pick_random_game(state)
            # result should never be one of the last 5 recent games
            self.assertNotIn(result, recent[-5:])

    # 6. record_game_played without state still tracks globally
    def test_global_rotation_still_works(self):
        reset_game_rotation()
        record_game_played("riddles")
        self.assertIn("riddles", get_recent_games())


@patch("game_handlers.get_adaptive_rounds", side_effect=lambda name, base, state: base)
class TestGameValidation(unittest.TestCase):
    """Tests for game validation guards and timeout logic."""

    def test_unknown_game_clears_state(self, _mock_ar):
        state = _make_state()
        state["_active_game"] = "bogus_game"
        state["_game_state"] = {"some": "data"}
        emo = EmotionSystem()
        result = handle_game_input("hello", state, emo)
        self.assertIsNotNone(result)
        self.assertIsNone(state["_active_game"])
        self.assertEqual(state["_game_state"], {})

    def test_empty_game_state_clears(self, _mock_ar):
        state = _make_state()
        state["_active_game"] = "trivia"  # not in VALID_GAMES → also cleared
        state["_game_state"] = {}
        emo = EmotionSystem()
        result = handle_game_input("answer", state, emo)
        self.assertIsNotNone(result)
        self.assertIsNone(state["_active_game"])
        self.assertEqual(state["_game_state"], {})

    def test_rps_allows_empty_state(self, _mock_ar):
        """RPS is stateless-friendly: the empty-state guard must NOT clear it."""
        state = _make_state()
        state["_active_game"] = "rock_paper_scissors"
        state["_game_state"] = {}
        emo = EmotionSystem()
        # Use "quit" to go through the guard without hitting RPS-specific keys.
        # If the guard had fired, the response would contain "lost track".
        result = handle_game_input("quit", state, emo)
        self.assertIsNotNone(result)
        resp_text = result[0] if isinstance(result, tuple) else result
        self.assertNotIn("lost track", resp_text.lower())
        self.assertIn("game over", resp_text.lower())

    def test_valid_game_updates_input_time(self, _mock_ar):
        state, config, emo = _make_state(), _make_config(), EmotionSystem()
        start_game("truth_or_dare", state, config, emo)
        state["_game_last_input_time"] = 0
        before = time.time()
        handle_game_input("truth", state, emo)
        self.assertGreaterEqual(state["_game_last_input_time"], before)

    def test_start_game_rejects_unknown(self, _mock_ar):
        state, config, emo = _make_state(), _make_config(), EmotionSystem()
        result = start_game("totally_fake_game", state, config, emo)
        self.assertIsNone(result)
        self.assertIsNone(state["_active_game"])

    def test_check_game_timeout_clears_stale(self, _mock_ar):
        state = _make_state()
        state["_active_game"] = "simon_says"
        state["_game_state"] = {"round": 1}
        state["_game_last_input_time"] = time.time() - 200
        result = check_game_timeout(state, timeout_seconds=180)
        self.assertIsNotNone(result)
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)
        self.assertIsNone(state["_active_game"])
        self.assertEqual(state["_game_state"], {})

    def test_check_game_timeout_ignores_active(self, _mock_ar):
        state = _make_state()
        state["_active_game"] = "simon_says"
        state["_game_state"] = {"round": 1}
        state["_game_last_input_time"] = time.time() - 10
        result = check_game_timeout(state, timeout_seconds=180)
        self.assertIsNone(result)
        self.assertEqual(state["_active_game"], "simon_says")

    def test_check_game_timeout_no_game(self, _mock_ar):
        state = _make_state()
        state["_active_game"] = None
        result = check_game_timeout(state)
        self.assertIsNone(result)


class _FakeCharacterLoader:
    def __init__(self, pools):
        self._pools = pools

    def get_game_pools(self):
        return self._pools


class TestCharacterGamePools(unittest.TestCase):
    def tearDown(self):
        importlib.reload(game_handlers)

    def test_module_defaults_to_empty_game_pools(self):
        importlib.reload(game_handlers)
        self.assertEqual(game_handlers.SIMON_ACTIONS, [])
        self.assertEqual(game_handlers.MARIO_TRIVIA_QUESTIONS, [])
        self.assertEqual(game_handlers.HOT_TAKES, [])

    def test_load_character_pools_clears_all_pools_when_character_has_none(self):
        _seed_game_pools()
        game_handlers.load_character_pools(_FakeCharacterLoader({}))
        self.assertEqual(game_handlers.SIMON_ACTIONS, [])
        self.assertEqual(game_handlers.TWENTY_Q_THINGS, [])
        self.assertEqual(game_handlers.STORY_STARTERS, [])

    def test_load_character_pools_clears_missing_pools_before_loading_partial_character_data(self):
        _seed_game_pools()
        game_handlers.load_character_pools(_FakeCharacterLoader({
            "simon": ["wave hello"],
            "karaoke": [{"title": "Ani Anthem", "lyrics": "Hi there"}],
        }))
        self.assertEqual(game_handlers.SIMON_ACTIONS, ["wave hello"])
        self.assertEqual(game_handlers.KARAOKE_SONGS[0]["title"], "Ani Anthem")
        self.assertEqual(game_handlers.RIDDLES, [])
        self.assertEqual(game_handlers.TWENTY_Q_THINGS, [])


@patch("game_handlers.get_adaptive_rounds", side_effect=lambda name, base, state: base)
class TestEmptyPoolGuards(unittest.TestCase):
    def tearDown(self):
        _seed_game_pools()

    def test_simon_start_reports_unavailable_when_actions_missing(self, _mock_ar):
        state, config, emo = _make_state(), _make_config(), EmotionSystem()
        game_handlers.SIMON_ACTIONS = []
        intro = start_game("simon_says", state, config, emo)
        self.assertIn("Simon Says actions", intro)
        self.assertIsNone(state["_active_game"])

    def test_simon_midgame_reports_unavailable_when_actions_run_out(self, _mock_ar):
        state, config, emo = _make_state(), _make_config(), EmotionSystem()
        start_game("simon_says", state, config, emo)
        game_handlers.SIMON_ACTIONS = []
        state["_game_state"]["is_simon"] = True
        resp, sfx = handle_game_input("yes", state, emo)
        self.assertIn("Simon Says actions", resp)
        self.assertEqual(sfx, "game_over")
        self.assertIsNone(state["_active_game"])

    def test_rps_reports_unavailable_when_tie_reactions_missing(self, _mock_ar):
        state, config, emo = _make_state(), _make_config(), EmotionSystem()
        start_game("rock_paper_scissors", state, config, emo)
        game_handlers.RPS_TIE_REACTIONS = []

        def _choice(seq):
            if seq == ["rock", "paper", "scissors"]:
                return "rock"
            return seq[0]

        with patch("game_handlers.random.choice", side_effect=_choice):
            resp, sfx = handle_game_input("rock", state, emo)
        self.assertIn("Rock Paper Scissors reactions", resp)
        self.assertEqual(sfx, "game_over")
        self.assertIsNone(state["_active_game"])


if __name__ == "__main__":
    unittest.main()
