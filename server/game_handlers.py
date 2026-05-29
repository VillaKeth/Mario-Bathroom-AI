"""Game handler module — all interactive game logic for Mario AI.

Extracted from main.py to keep the server module focused on WebSocket handling.
Each game mode has its content data, start logic, and input handling here.
"""

import json
import logging
import os
import random
import time
from emotions import Emotion

logger = logging.getLogger(__name__)

# Character name for game responses — set by main.py at startup
_CHARACTER_NAME = "Mario"
_CHARACTER_DISPLAY_NAME = "Mario"


def set_character(name: str, display_name: str):
    """Set the active character for game responses."""
    global _CHARACTER_NAME, _CHARACTER_DISPLAY_NAME
    _CHARACTER_NAME = name
    _CHARACTER_DISPLAY_NAME = display_name


_GAME_POOL_NAMES = (
    "SIMON_ACTIONS",
    "TWENTY_Q_THINGS",
    "RIDDLES",
    "STARTER_WORDS",
    "KARAOKE_SONGS",
    "RAPID_FIRE_QUESTIONS",
    "TRUTH_QUESTIONS",
    "DARES",
    "WOULD_YOU_RATHER",
    "RPS_WIN_REACTIONS",
    "RPS_LOSE_REACTIONS",
    "RPS_TIE_REACTIONS",
    "HANGMAN_WORDS",
    "HOT_TAKES",
    "MARIO_TRIVIA_QUESTIONS",
    "NAME_THAT_CHARACTER",
    "BATHROOM_DARES",
    "STORY_STARTERS",
    "WYR_EXTENDED",
    "NHIE_PROMPTS",
)


def _clear_game_pools():
    """Reset all character-loaded game pools so content never bleeds across characters."""
    for pool_name in _GAME_POOL_NAMES:
        globals()[pool_name].clear()


def _empty_pool_message(pool_label: str) -> str:
    """Return a generic unavailable-game message for empty character content pools."""
    return f"{_CHARACTER_DISPLAY_NAME} doesn't have any {pool_label} right now! Let's play something else!"


def _end_game_for_empty_pool(state: dict, emotion_sys, pool_label: str) -> tuple[str, str]:
    """Clear the active game when required pool data is unavailable mid-game."""
    state["_active_game"] = None
    state["_game_state"] = {}
    emotion_sys.current = Emotion.CONFUSED
    return (_empty_pool_message(pool_label), "game_over")


def load_character_pools(character_loader):
    """Load game content pools from a character's YAML files.

    Missing YAML keeps pools empty so characters never inherit another
    character's game content.
    """
    global SIMON_ACTIONS, TWENTY_Q_THINGS, RIDDLES, STARTER_WORDS, KARAOKE_SONGS
    global RAPID_FIRE_QUESTIONS, TRUTH_QUESTIONS, DARES, WOULD_YOU_RATHER
    global RPS_WIN_REACTIONS, RPS_LOSE_REACTIONS, RPS_TIE_REACTIONS
    global HANGMAN_WORDS, HOT_TAKES, MARIO_TRIVIA_QUESTIONS, NAME_THAT_CHARACTER
    global BATHROOM_DARES, STORY_STARTERS, WYR_EXTENDED, NHIE_PROMPTS

    pools = character_loader.get_game_pools()
    _clear_game_pools()
    if not pools:
        logger.info("[GAMES] No character game pools found; pools empty (no character game files)")
        return

    # Map YAML pool names to module-level variables
    _POOL_MAP = {
        "simon": ("SIMON_ACTIONS", SIMON_ACTIONS),
        "twenty_questions": ("TWENTY_Q_THINGS", TWENTY_Q_THINGS),
        "riddles": ("RIDDLES", RIDDLES),
        "word_chains": ("STARTER_WORDS", STARTER_WORDS),
        "karaoke": ("KARAOKE_SONGS", KARAOKE_SONGS),
        "rapid_fire": ("RAPID_FIRE_QUESTIONS", RAPID_FIRE_QUESTIONS),
        "truth_or_dare": ("_TRUTH_AND_DARE", None),  # special: split into truth/dare
        "would_you_rather": ("WOULD_YOU_RATHER", WOULD_YOU_RATHER),
        "reactions": ("_REACTIONS", None),  # special: split into win/lose/tie
        "hangman": ("HANGMAN_WORDS", HANGMAN_WORDS),
        "hot_takes": ("HOT_TAKES", HOT_TAKES),
        "trivia": ("MARIO_TRIVIA_QUESTIONS", MARIO_TRIVIA_QUESTIONS),
        "name_that_character": ("NAME_THAT_CHARACTER", NAME_THAT_CHARACTER),
        "story_starters": ("STORY_STARTERS", STORY_STARTERS),
        "wyr_extended": ("WYR_EXTENDED", WYR_EXTENDED),
        "nhie": ("NHIE_PROMPTS", NHIE_PROMPTS),
    }

    loaded = []
    for pool_name, (var_name, _default) in _POOL_MAP.items():
        if pool_name not in pools:
            continue
        data = pools[pool_name]
        if not data:
            continue

        # Handle special pools that need splitting
        if pool_name == "truth_or_dare":
            if isinstance(data, dict):
                if "truths" in data and data["truths"]:
                    TRUTH_QUESTIONS = data["truths"]
                    loaded.append("truths")
                if "dares" in data and data["dares"]:
                    DARES = data["dares"]
                    loaded.append("dares")
                if "bathroom_dares" in data and data["bathroom_dares"]:
                    BATHROOM_DARES = data["bathroom_dares"]
                    loaded.append("bathroom_dares")
            elif isinstance(data, list):
                # Split "Truth: ..." and "Dare: ..." from flat list
                _truths = [s.replace("Truth: ", "", 1) for s in data if s.startswith("Truth:")]
                _dares = [s.replace("Dare: ", "", 1) for s in data if s.startswith("Dare:")]
                if _truths:
                    TRUTH_QUESTIONS = _truths
                    loaded.append("truths")
                if _dares:
                    DARES = _dares
                    BATHROOM_DARES = _dares
                    loaded.append("dares")
            continue

        if pool_name == "reactions":
            if isinstance(data, dict):
                if "win" in data and data["win"]:
                    RPS_WIN_REACTIONS = data["win"]
                    loaded.append("rps_win")
                if "lose" in data and data["lose"]:
                    RPS_LOSE_REACTIONS = data["lose"]
                    loaded.append("rps_lose")
                if "tie" in data and data["tie"]:
                    RPS_TIE_REACTIONS = data["tie"]
                    loaded.append("rps_tie")
            elif isinstance(data, list):
                # Use same reactions for all RPS outcomes
                RPS_WIN_REACTIONS = data
                RPS_LOSE_REACTIONS = data
                RPS_TIE_REACTIONS = data
                loaded.append("reactions")
            continue

        # Simple list pools — validate format for structured data
        if isinstance(data, list) and data:
            # Trivia/rapid_fire need dicts with 'q' key; skip flat strings
            if pool_name in ("trivia", "rapid_fire") and isinstance(data[0], str):
                logger.debug(f"[GAMES] Skipping {pool_name}: flat strings, needs structured Q&A")
                continue
            # WYR pools need dicts with 'a'/'b' keys
            if pool_name in ("would_you_rather", "wyr_extended") and isinstance(data[0], str):
                logger.debug(f"[GAMES] Skipping {pool_name}: flat strings, needs a/b dicts")
                continue
            # Name that character needs dicts with 'answer'/'hints'
            if pool_name == "name_that_character" and isinstance(data[0], str):
                logger.debug(f"[GAMES] Skipping {pool_name}: flat strings, needs answer/hints dicts")
                continue
            globals()[var_name] = data
            loaded.append(pool_name)

    logger.info(f"[GAMES] Loaded {len(loaded)} character game pools: {loaded}")

# ---------------------------------------------------------------------------
# Valid game names — used for state validation
# ---------------------------------------------------------------------------

VALID_GAMES = frozenset({
    "simon_says", "twenty_questions", "truth_or_dare", "riddles",
    "word_chain", "karaoke", "rapid_fire", "would_you_rather",
    "rock_paper_scissors", "hangman", "hot_takes", "never_have_i_ever",
    "mario_trivia", "name_that_character", "bathroom_dare",
    "story_builder", "wyr_mario",
})


# ---------------------------------------------------------------------------
# Jacob Birthday Trivia Loader
# ---------------------------------------------------------------------------

_jacob_trivia_cache = None

def _load_jacob_trivia():
    """Load Jacob-specific birthday trivia questions."""
    global _jacob_trivia_cache
    if _jacob_trivia_cache is not None:
        return _jacob_trivia_cache
    try:
        trivia_path = os.path.join(os.path.dirname(__file__), "data", "jacob_trivia.json")
        with open(trivia_path, encoding="utf-8") as f:
            _jacob_trivia_cache = json.load(f)
        return _jacob_trivia_cache
    except Exception:
        return []


def _mix_jacob_trivia(mario_questions, count=5):
    """Mix Jacob birthday trivia into Mario trivia (1 Jacob per ~3 Mario).

    Returns a list of *count* questions with Jacob questions tagged
    ``is_birthday_special = True`` for bonus-point handling.
    """
    jacob_qs = _load_jacob_trivia()
    if not jacob_qs:
        return mario_questions[:count]

    jacob_pool = list(jacob_qs)
    random.shuffle(jacob_pool)
    # Target: ~1 Jacob question per 3 regular questions
    jacob_count = max(1, count // 3)
    mario_count = count - jacob_count

    mario_pool = list(mario_questions)
    random.shuffle(mario_pool)

    # Convert Jacob questions to the same format as Mario questions + tag them
    selected_jacob = []
    for jq in jacob_pool[:jacob_count]:
        selected_jacob.append({
            "q": f"BIRTHDAY SPECIAL! {jq['question']}  (Options: {', '.join(jq['options'])})",
            "a": [jq["answer"]],
            "accept": jq["accept"],
            "fun_fact": jq.get("fun_fact", ""),
            "is_birthday_special": True,
        })

    combined = mario_pool[:mario_count] + selected_jacob
    random.shuffle(combined)
    return combined


# ---------------------------------------------------------------------------
# Game Content Data
# ---------------------------------------------------------------------------

# Game content comes from character YAML files at startup.
# Keep these module-level pools empty by default so characters never
# inherit Mario-specific prompts when their own game YAML is missing.
SIMON_ACTIONS = []


TWENTY_Q_THINGS = []


RIDDLES = []


STARTER_WORDS = []


KARAOKE_SONGS = []


RAPID_FIRE_QUESTIONS = []


TRUTH_QUESTIONS = []


DARES = []


WOULD_YOU_RATHER = []


RPS_WIN_REACTIONS = []


RPS_LOSE_REACTIONS = []


RPS_TIE_REACTIONS = []


HANGMAN_WORDS = []


HOT_TAKES = []


# ---------------------------------------------------------------------------
# NEW MINI-GAME CONTENT — Mario Trivia, Name That Character, Bathroom Dares,
# Story Builder, enhanced Would-You-Rather
# ---------------------------------------------------------------------------

MARIO_TRIVIA_QUESTIONS = []


NAME_THAT_CHARACTER = []


BATHROOM_DARES = []


STORY_STARTERS = []


WYR_EXTENDED = []


NHIE_PROMPTS = []



# ---------------------------------------------------------------------------
# Adaptive Difficulty — scales game rounds based on player history
# ---------------------------------------------------------------------------

def get_adaptive_rounds(game_name: str, base_rounds: int, state: dict) -> int:
    """Scale game rounds based on player's historical performance.
    
    - High win rate (>70%): Add 2 extra rounds (harder)
    - Medium win rate (40-70%): Keep base rounds
    - Low win rate (<40%): Reduce by 1 round (easier, min 3)
    - New player: Use base rounds
    """
    try:
        from memory import get_player_stats
        person_id = state.get("speaker_id")
        if not person_id:
            return base_rounds
        
        stats = get_player_stats(person_id)
        game_stats = stats.get(game_name)
        if not game_stats or game_stats["games_played"] < 2:
            return base_rounds  # Not enough data
        
        win_rate = game_stats["win_rate"]
        if win_rate > 0.70:
            return min(base_rounds + 2, 10)  # Cap at 10
        elif win_rate < 0.40:
            return max(base_rounds - 1, 3)   # Floor at 3
        return base_rounds
    except Exception:
        return base_rounds


# ---------------------------------------------------------------------------
# Game Rotation — avoid repeating the same game for a guest
# ---------------------------------------------------------------------------

ALL_GAME_NAMES = [
    "simon_says", "twenty_questions", "truth_or_dare", "riddles",
    "word_chain", "karaoke", "rapid_fire", "would_you_rather",
    "rock_paper_scissors", "hangman", "hot_takes", "never_have_i_ever",
    "mario_trivia", "name_that_character", "bathroom_dare",
    "story_builder", "wyr_mario",
]

# Quick/easy games that work well as random picks for new guests
QUICK_GAMES = [
    "truth_or_dare", "would_you_rather", "riddles", "hot_takes",
    "never_have_i_ever", "rock_paper_scissors", "rapid_fire",
    "mario_trivia", "hangman",
]

_recent_games: list[str] = []  # Module-level recent game buffer
_ROTATION_BUFFER = 5  # Don't repeat within last 5 games


def pick_random_game(state: dict) -> str:
    """Pick a random game that hasn't been played recently by this guest.
    Prefers quick/party-friendly games for random selection."""
    guest_recent = state.get("_recent_games", [])
    available = [g for g in QUICK_GAMES if g not in guest_recent[-_ROTATION_BUFFER:]]
    if not available:
        available = list(QUICK_GAMES)  # Reset if all played
    return random.choice(available)


def record_game_played(game_name: str, state: dict = None):
    """Record that a game was played for rotation tracking."""
    _recent_games.append(game_name)
    if len(_recent_games) > 20:
        _recent_games[:] = _recent_games[-20:]
    # Also track per-guest if state provided
    if state is not None:
        if "_recent_games" not in state:
            state["_recent_games"] = []
        state["_recent_games"].append(game_name)
        if len(state["_recent_games"]) > 20:
            state["_recent_games"] = state["_recent_games"][-20:]


def get_recent_games() -> list[str]:
    """Get list of recently played games (for testing/dashboard)."""
    return list(_recent_games)


def reset_game_rotation():
    """Reset rotation tracking (for testing)."""
    _recent_games.clear()


# ---------------------------------------------------------------------------
# start_game — initialise a new game session
# ---------------------------------------------------------------------------

def start_game(game_name: str, state: dict, config: dict, emotion_sys) -> str | None:
    """Set up game state and return the intro text.

    Args:
        game_name: One of simon_says, twenty_questions, truth_or_dare,
                   riddles, word_chain, karaoke, rapid_fire.
        state:     Reference to ``state_current`` from main — mutations persist.
        config:    ``GAME_CONFIG`` dict from main.
        emotion_sys: ``EmotionSystem`` instance from main.
    """
    # Guard: don't start a new game while one is active
    if state.get("_active_game"):
        current = state["_active_game"]
        return f"Mama mia! We're already playing {current}! Say 'quit game' first if you want to switch!"
    import time as _time
    state["_game_last_input_time"] = _time.time()  # Start timeout clock
    record_game_played(game_name, state)  # Track for rotation

    if game_name not in VALID_GAMES:
        logger.warning(f"[GAME] Unknown game_name '{game_name}' passed to start_game")
        return None

    if game_name == "simon_says":
        if not SIMON_ACTIONS:
            return _empty_pool_message("Simon Says actions")
        state["_active_game"] = "simon_says"
        max_r = get_adaptive_rounds("simon_says", config["simon_max_rounds"], state)
        state["_game_state"] = {"round": 1, "score": 0, "max_rounds": max_r}
        action = random.choice(SIMON_ACTIONS)
        state["_game_state"]["current_action"] = action
        state["_game_state"]["is_simon"] = random.random() > 0.3
        emotion_sys.current = Emotion.EXCITED
        if state["_game_state"]["is_simon"]:
            return f"SIMON SAYS game! Round 1 of 5! Simon says... {action}! Did you do it? Say 'yes' or 'no'!"
        return f"SIMON SAYS game! Round 1 of 5! {action.capitalize()}! Ha! Did you do it? Say 'yes' or 'no'!"

    if game_name == "twenty_questions":
        if not TWENTY_Q_THINGS:
            return _empty_pool_message("20 Questions prompts")
        thing = random.choice(TWENTY_Q_THINGS)
        state["_active_game"] = "twenty_questions"
        state["_game_state"] = {
            "answer": thing["answer"],
            "category": thing["category"],
            "hints": thing["hints"],
            "questions_left": config["twenty_q_max_questions"],
            "hints_given": 0,
        }
        emotion_sys.current = Emotion.MISCHIEVOUS
        ql = config["twenty_q_max_questions"]
        return f"20 QUESTIONS! I'm-a thinking of a {thing['category']}! You have {ql} questions! Ask me yes or no questions, or say 'hint' for a clue! Say 'give up' to quit!"

    if game_name == "truth_or_dare":
        state["_active_game"] = "truth_or_dare"
        mr = get_adaptive_rounds("truth_or_dare", config["truth_dare_max_rounds"], state)
        state["_game_state"] = {"round": 1, "max_rounds": mr}
        emotion_sys.current = Emotion.MISCHIEVOUS
        return f"TRUTH OR DARE! Let's-a play! Round 1 of {mr}! Say 'truth' or 'dare'!"

    if game_name == "riddles":
        if not RIDDLES:
            return _empty_pool_message("riddles")
        riddle = random.choice(RIDDLES)
        state["_active_game"] = "riddles"
        state["_game_state"] = {
            "answer": riddle["a"],
            "hints": riddle["hints"],
            "hints_given": 0,
            "attempts": 0,
            "max_attempts": config["riddle_max_attempts"],
        }
        emotion_sys.current = Emotion.MISCHIEVOUS
        return f"RIDDLE TIME! Here's-a your riddle: {riddle['q']} Say 'hint' for a clue or try to guess!"

    if game_name == "word_chain":
        if not STARTER_WORDS:
            return _empty_pool_message("Word Chain starter words")
        word = random.choice(STARTER_WORDS)
        state["_active_game"] = "word_chain"
        state["_game_state"] = {
            "last_word": word,
            "used_words": [word],
            "score": 0,
            "max_rounds": config["word_chain_max_rounds"],
        }
        emotion_sys.current = Emotion.EXCITED
        return f"WORD CHAIN! I start with '{word.upper()}'! Now YOU say a word starting with the letter '{word[-1].upper()}'! We take turns!"

    if game_name == "karaoke":
        if not KARAOKE_SONGS:
            return _empty_pool_message("karaoke songs")
        song = random.choice(KARAOKE_SONGS)
        emotion_sys.current = Emotion.EXCITED
        return f"KARAOKE TIME! 🎤 Let's-a sing '{song['title']}'! Ready? ♪ {song['lyrics']} ♪ WAHOO! Your turn to sing something!"

    if game_name == "rapid_fire":
        questions = list(RAPID_FIRE_QUESTIONS)
        if not questions:
            return "Mama mia! I ran out of questions for Rapid Fire! Let's-a play something else!"
        random.shuffle(questions)
        max_r = get_adaptive_rounds("rapid_fire", config["rapid_fire_max_rounds"], state)
        max_r = min(max_r, len(questions))
        if max_r == 0:
            return "Mama mia! I ran out of questions for Rapid Fire! Let's-a play something else!"
        state["_active_game"] = "rapid_fire"
        state["_game_state"] = {
            "questions": questions[:max_r],
            "current": 0,
            "score": 0,
            "max_rounds": max_r,
            "start_time": time.time(),
        }
        emotion_sys.current = Emotion.EXCITED
        first_q = questions[0]["q"]
        return f"RAPID FIRE QUIZ! Answer as fast as you can! {max_r} questions, GO! Q1: {first_q}"

    if game_name == "would_you_rather":
        if not WOULD_YOU_RATHER:
            return "Mama mia! I ran out of Would You Rather questions! Let's-a play something else!"
        random.shuffle(WOULD_YOU_RATHER)
        max_rounds = min(config.get("truth_dare_max_rounds", 5), len(WOULD_YOU_RATHER))
        if max_rounds == 0:
            return "Mama mia! I ran out of Would You Rather questions! Let's-a play something else!"
        state["_active_game"] = "would_you_rather"
        state["_game_state"] = {
            "questions": WOULD_YOU_RATHER[:max_rounds],
            "current": 0,
            "max_rounds": max_rounds,
            "choices": [],
        }
        emotion_sys.current = Emotion.MISCHIEVOUS
        q = WOULD_YOU_RATHER[0]
        return f"WOULD YOU RATHER! Round 1 of {max_rounds}! Would you rather: A) {q['a']} OR B) {q['b']}? Say A or B!"

    if game_name == "rock_paper_scissors":
        state["_active_game"] = "rock_paper_scissors"
        state["_game_state"] = {
            "round": 1,
            "max_rounds": 3,
            "player_score": 0,
            "mario_score": 0,
        }
        emotion_sys.current = Emotion.EXCITED
        return "ROCK PAPER SCISSORS! Best of 3! Let's-a BATTLE! Say 'rock', 'paper', or 'scissors'! Let's-a GO!"

    if game_name == "hangman":
        if not HANGMAN_WORDS:
            return _empty_pool_message("Hangman words")
        word = random.choice(HANGMAN_WORDS)
        display = " ".join("_" for _ in word)
        state["_active_game"] = "hangman"
        state["_game_state"] = {
            "word": word,
            "guessed": [],
            "wrong_guesses": 0,
            "max_wrong": 6,
        }
        emotion_sys.current = Emotion.MISCHIEVOUS
        return f"HANGMAN! I'm-a thinking of a Mario word! {len(word)} letters! Here it is: {display} — Guess a letter! You get 6 wrong guesses before it's GAME OVER!"

    if game_name == "hot_takes":
        takes = list(HOT_TAKES)
        if not takes:
            return "Mama mia! I ran out of hot takes! Let's-a play something else!"
        random.shuffle(takes)
        ht_max = min(5, len(takes))
        state["_active_game"] = "hot_takes"
        state["_game_state"] = {
            "takes": takes[:ht_max],
            "current": 0,
            "max_rounds": ht_max,
            "agreements": 0,
        }
        emotion_sys.current = Emotion.MISCHIEVOUS
        first_take = takes[0]
        return f"HOT TAKES! Mario's-a got some SPICY opinions! Round 1 of {ht_max}! Here's my take: \"{first_take}\" Do you AGREE or DISAGREE?"

    if game_name == "never_have_i_ever":
        prompts = list(NHIE_PROMPTS)
        if not prompts:
            return "Mama mia! I ran out of Never Have I Ever prompts! Let's-a play something else!"
        random.shuffle(prompts)
        nhie_max = min(5, len(prompts))
        state["_active_game"] = "never_have_i_ever"
        state["_game_state"] = {
            "prompts": prompts[:nhie_max],
            "current": 0,
            "max_rounds": nhie_max,
            "daring_score": 0,
        }
        emotion_sys.current = Emotion.MISCHIEVOUS
        first_prompt = prompts[0]
        return f"NEVER HAVE I EVER! Let's-a see how DARING you are! Round 1 of {nhie_max}! {first_prompt} Say 'I have' or 'I haven't'!"

    # --- Mario Trivia ---
    if game_name == "mario_trivia":
        max_r = get_adaptive_rounds("mario_trivia", 5, state)
        questions = _mix_jacob_trivia(MARIO_TRIVIA_QUESTIONS, count=max_r)
        if not questions:
            return "I ran out of trivia questions! Let's play something else!"
        max_r = min(max_r, len(questions))
        if max_r == 0:
            return "I ran out of trivia questions! Let's play something else!"
        state["_active_game"] = "mario_trivia"
        state["_game_state"] = {
            "questions": questions[:max_r],
            "current": 0,
            "score": 0,
            "max_rounds": max_r,
        }
        emotion_sys.current = Emotion.EXCITED
        first_q = questions[0]["q"]
        has_birthday = any(q.get("is_birthday_special") for q in questions)
        intro = f"{_CHARACTER_DISPLAY_NAME.upper()} TRIVIA TIME!"
        if has_birthday:
            intro += " With BIRTHDAY SPECIAL questions about our guest of honor!"
        intro += f" {max_r} questions — let's see how smart you are! Question 1: {first_q}"
        return intro

    # --- Name That Character ---
    if game_name == "name_that_character":
        chars = list(NAME_THAT_CHARACTER)
        if not chars:
            return "I ran out of characters to describe! Let's play something else!"
        random.shuffle(chars)
        max_r = min(5, len(chars))
        state["_active_game"] = "name_that_character"
        state["_game_state"] = {
            "characters": chars[:max_r],
            "current": 0,
            "score": 0,
            "max_rounds": max_r,
            "start_time": time.time(),
            "round_start": time.time(),
        }
        emotion_sys.current = Emotion.EXCITED
        first_desc = chars[0]["desc"]
        return f"NAME THAT CHARACTER! I describe someone, you guess who! Speed matters — faster answers get bonus praise! Ready? Here we go! {first_desc}"

    # --- Bathroom Dare ---
    if game_name == "bathroom_dare":
        dares = list(BATHROOM_DARES)
        if not dares:
            return "I ran out of dares! Let's play something else!"
        random.shuffle(dares)
        max_r = 3
        state["_active_game"] = "bathroom_dare"
        state["_game_state"] = {
            "dares": dares[:max_r],
            "current": 0,
            "completed": 0,
            "max_rounds": max_r,
        }
        emotion_sys.current = Emotion.MISCHIEVOUS
        first_dare = dares[0]
        return f"BATHROOM DARE TIME! {_CHARACTER_DISPLAY_NAME}'s got some challenges for you! Dare 1 of {max_r}: {first_dare} Say 'done' when you finish, or 'skip' if you're chicken! Bawk bawk!"

    # --- Story Builder ---
    if game_name == "story_builder":
        if not STORY_STARTERS:
            return _empty_pool_message("story starters")
        starter = random.choice(STORY_STARTERS)
        state["_active_game"] = "story_builder"
        state["_game_state"] = {
            "story": [starter],
            "current_round": 1,
            "max_rounds": 5,
            "whose_turn": "player",
        }
        emotion_sys.current = Emotion.EXCITED
        return f"STORY BUILDER TIME! We take turns adding to a story! I'll start, you add the next part, then me, back and forth for 5 rounds! Here we go: {starter} ...NOW YOU! Add the next sentence!"

    # --- Would You Rather (Extended/Mario Edition) ---
    if game_name == "wyr_mario":
        combined = list(WYR_EXTENDED)
        if not combined:
            return "Mama mia! I ran out of Would You Rather scenarios! Let's-a play something else!"
        random.shuffle(combined)
        max_rounds = min(5, len(combined))
        state["_active_game"] = "wyr_mario"
        state["_game_state"] = {
            "questions": combined[:max_rounds],
            "current": 0,
            "max_rounds": max_rounds,
            "choices": [],
        }
        emotion_sys.current = Emotion.MISCHIEVOUS
        q = combined[0]
        return f"WOULD YOU RATHER — {_CHARACTER_DISPLAY_NAME.upper()} EDITION! The CRAZIEST choices! Round 1 of {max_rounds}! Would you rather: A) {q['a']} OR B) {q['b']}? Say A or B!"

    return None


# ---------------------------------------------------------------------------
# handle_game_input — process player input during an active game
# ---------------------------------------------------------------------------

def handle_game_input(lower: str, state: dict, emotion_sys) -> tuple[str, str] | None:
    """Handle input while a game mode is active. Returns (response, sound_hint) or None."""
    game = state.get("_active_game")
    if not game:
        return None

    # Validate game handler exists
    if game not in VALID_GAMES:
        logger.warning(f"[GAME] Unknown active game '{game}' — clearing")
        state["_active_game"] = None
        state["_game_state"] = {}
        return ("Hmm, I forgot what game we were playing! Want to start a new one?", "confused/thinking")

    # Validate game state exists (RPS doesn't need pre-existing state)
    game_state = state.get("_game_state", {})
    if not game_state and game != "rock_paper_scissors":
        logger.warning(f"[GAME] Empty game state for '{game}' — clearing")
        state["_active_game"] = None
        state["_game_state"] = {}
        return ("Oops, I lost track of the game! Let me know if you want to play something!", "confused/sad")

    # Track last input time for timeout
    state["_game_last_input_time"] = time.time()
    gs = state["_game_state"]

    # Universal quit (exclude "done" — used as valid input by bathroom_dare and simon_says)
    quit_words = ["quit", "stop", "give up", "end game", "exit"]
    if game not in ("bathroom_dare", "simon_says", "story_builder"):
        quit_words.append("done")
    if any(w in lower for w in quit_words):
        game_name = game.replace("_", " ")
        score = gs.get("score", 0)
        state["_active_game"] = None
        state["_game_state"] = {}
        emotion_sys.current = Emotion.HAPPY
        if game == "twenty_questions":
            return (f"The answer was '{gs.get('answer', '???')}'! Thanks for playing!", "game_over")
        return (f"Game over! Final score: {score}! Thanks for playing {game_name}!", "game_over")

    # --- Simon Says ---
    if game == "simon_says":
        did_it = any(w in lower for w in ["yes", "yeah", "yep", "yup", "did it", "done"])
        didnt = any(w in lower for w in ["no", "nope", "didn't", "nah"])

        if did_it or didnt:
            is_simon = gs["is_simon"]
            correct = (is_simon and did_it) or (not is_simon and didnt)
            if correct:
                gs["score"] += 1
                feedback = random.choice([
                        "CORRECT! Nice!",
                        "You got it! Smart cookie!",
                        "RIGHT! You're good at this!",
                        f"YES! {_CHARACTER_DISPLAY_NAME} is impressed!",
                ])
                sfx = "correct"
            else:
                if is_simon and didnt:
                    feedback = "Oops! Simon DID say it! You should have done it!"
                else:
                    feedback = "HA! Simon DIDN'T say it! You fell for my trick!"
                sfx = "wrong"

            gs["round"] += 1
            if gs["round"] > gs["max_rounds"]:
                state["_active_game"] = None
                final_score = gs["score"]
                state["_game_state"] = {}
                if final_score == gs["max_rounds"]:
                    return (f"{feedback} PERFECT SCORE! {final_score}/{gs['max_rounds']}! You're-a the CHAMPION!", "achievement")
                elif final_score >= 3:
                    return (f"{feedback} Game over! Score: {final_score}/{gs['max_rounds']}! Not bad at all!", "game_over")
                else:
                    return (f"{feedback} Game over! Score: {final_score}/{gs['max_rounds']}! Better luck next time!", "game_over")

            # Next round
            if not SIMON_ACTIONS:
                return _end_game_for_empty_pool(state, emotion_sys, "Simon Says actions")
            action = random.choice(SIMON_ACTIONS)
            gs["current_action"] = action
            gs["is_simon"] = random.random() > 0.3
            rnd = gs["round"]
            if gs["is_simon"]:
                return (f"{feedback} Round {rnd}! Simon says... {action}! Did you do it?", sfx)
            else:
                return (f"{feedback} Round {rnd}! {action.capitalize()}! Did you do it?", sfx)
        return ("Did you do it? Say 'yes' or 'no'!", None)

    # --- 20 Questions ---
    if game == "twenty_questions":
        answer = gs["answer"]

        # Hint request
        if "hint" in lower:
            idx = gs["hints_given"]
            if idx < len(gs["hints"]):
                gs["hints_given"] += 1
                hint = gs["hints"][idx]
                return (f"Here's a hint: {hint}! {gs['questions_left']} questions left!", "hint")
            return ("No more hints! You're-a on your own now! Ask a yes or no question!", None)

        # Check if they guessed it
        if answer in lower:
            state["_active_game"] = None
            ql = gs["questions_left"]
            state["_game_state"] = {}
            emotion_sys.current = Emotion.EXCITED
            return (f"YES! It's {answer}! You got it with {ql} questions left! You're a genius!", "correct")

        # Yes/no response to their question
        gs["questions_left"] -= 1
        if gs["questions_left"] <= 0:
            state["_active_game"] = None
            state["_game_state"] = {}
            emotion_sys.current = Emotion.MISCHIEVOUS
            return (f"Time's up! The answer was '{answer}'! Better luck next time! Ha ha!", "game_over")

        # Simple keyword matching for yes/no answers
        answer_words = answer.lower().split()
        if any(w in lower for w in ["is it", "does it", "can it", "would it", "has it"]):
            related = any(w in lower for w in answer_words)
            if related:
                return (f"Hmm, you're getting WARM! {gs['questions_left']} questions left! Keep guessing!", "hint")
            return (f"Hmm, not exactly! {gs['questions_left']} questions left!", None)

        return (f"Ask me a yes or no question! Or say 'hint'! {gs['questions_left']} questions left!", None)

    # --- Truth or Dare ---
    if game == "truth_or_dare":
        if "truth" in lower:
            if not TRUTH_QUESTIONS:
                return ("I ran out of truth questions! Let's play something else!", "game_over")
            truth = random.choice(TRUTH_QUESTIONS)
            gs["round"] += 1
            emotion_sys.current = Emotion.MISCHIEVOUS
            if gs["round"] > gs["max_rounds"]:
                state["_active_game"] = None
                state["_game_state"] = {}
                return (f"TRUTH! {truth} ...And that's the final round! Great game!", "game_over")
            return (f"TRUTH! {truth} Tell me your answer, then say 'truth' or 'dare' for round {gs['round']}!", None)

        if "dare" in lower:
            if not DARES:
                return ("I ran out of dares! Let's play something else!", "game_over")
            dare = random.choice(DARES)
            gs["round"] += 1
            emotion_sys.current = Emotion.EXCITED
            if gs["round"] > gs["max_rounds"]:
                state["_active_game"] = None
                state["_game_state"] = {}
                return (f"DARE! {dare} ...And that's the final round! You're brave!", "game_over")
            return (f"DARE! {dare} When you're done, say 'truth' or 'dare' for round {gs['round']}!", None)

        return ("Say 'truth' or 'dare'! Or 'quit' to stop playing!", None)

    # --- Riddles ---
    if game == "riddles":
        if "hint" in lower:
            idx = gs["hints_given"]
            if idx < len(gs["hints"]):
                gs["hints_given"] += 1
                remaining = gs["max_attempts"] - gs["attempts"]
                return (f"HINT: {gs['hints'][idx]}! You have {remaining} guesses left!", "hint")
            return ("No more hints! Use your brain power! You can do it!", None)

        gs["attempts"] += 1
        answer = gs["answer"]
        if answer in lower or any(w in lower for w in answer.split()):
            state["_active_game"] = None
            attempts = gs["attempts"]
            state["_game_state"] = {}
            emotion_sys.current = Emotion.EXCITED
            if attempts == 1:
                return (f"WAHOO! '{answer.upper()}'! You got it on the FIRST try! You're a GENIUS!", "correct")
            return (f"YES! The answer is '{answer.upper()}'! You got it in {attempts} guesses! Bravo!", "correct")

        if gs["attempts"] >= gs["max_attempts"]:
            state["_active_game"] = None
            state["_game_state"] = {}
            emotion_sys.current = Emotion.MISCHIEVOUS
            return (f"Time's up! The answer was '{answer.upper()}'! Better luck next riddle! Ha!", "game_over")

        remaining = gs["max_attempts"] - gs["attempts"]
        emotion_sys.current = Emotion.CONFUSED
        return (f"Nope! That's not it! {remaining} guesses left! Try again or say 'hint'!", "wrong")

    # --- Word Chain ---
    if game == "word_chain":
        words = lower.strip().split()
        player_word = words[-1] if words else ""
        last_letter = gs["last_word"][-1].lower()

        if not player_word or len(player_word) < 2:
            return (f"Say a word starting with '{last_letter.upper()}'! Keep the chain going!", None)

        if player_word[0] != last_letter:
            emotion_sys.current = Emotion.CONFUSED
            return (f"Nope! Your word needs to start with '{last_letter.upper()}'! '{gs['last_word']}' ends with '{last_letter}'! Try again!", "wrong")

        if player_word in gs["used_words"]:
            return (f"'{player_word}' was already used! Pick a different word starting with '{last_letter.upper()}'!", "wrong")

        gs["used_words"].append(player_word)
        gs["score"] += 1

        if gs["score"] >= gs["max_rounds"]:
            state["_active_game"] = None
            score = gs["score"]
            state["_game_state"] = {}
            emotion_sys.current = Emotion.EXCITED
            return (f"WAHOO! {score} words in the chain! You're the Word Chain CHAMPION! Incredible!", "achievement")

        # AI's turn
        ai_letter = player_word[-1]
        AI_WORDS = {
            "a": "adventure", "b": "brilliant", "c": "castle", "d": "daring", "e": "exciting",
            "f": "fantastic", "g": "galaxy", "h": "hero", "i": "invincible", "j": "jumping",
            "k": "kingdom", "l": "legendary", "m": "mystery", "n": "nimble", "o": "odyssey",
            "p": "powerful", "q": "quest", "r": "rainbow", "s": "starlight", "t": "triumph",
            "u": "unstoppable", "v": "victory", "w": "wonder", "x": "extreme", "y": "youthful", "z": "zap",
        }
        ai_word = AI_WORDS.get(ai_letter, f"{ai_letter}ario")
        while ai_word in gs["used_words"]:
            ai_word = ai_word + "s"
        gs["used_words"].append(ai_word)
        gs["last_word"] = ai_word
        next_letter = ai_word[-1].upper()
        emotion_sys.current = Emotion.HAPPY
        return (f"Nice! '{player_word}'! My turn: '{ai_word.upper()}'! Now you say a word starting with '{next_letter}'! Score: {gs['score']}!", "correct")

    # --- Rapid Fire Quiz ---
    if game == "rapid_fire":
        current_idx = gs["current"]
        if current_idx >= len(gs["questions"]):
            state["_active_game"] = None
            state["_game_state"] = {}
            return (f"Quiz over! Score: {gs['score']}/{gs['max_rounds']}!", "game_over")

        question = gs["questions"][current_idx]
        answer = question["a"].lower()

        answer_words = answer.split()
        got_it = any(w in lower for w in answer_words) or answer in lower

        gs["current"] += 1
        next_idx = gs["current"]

        if got_it:
            gs["score"] += 1
            if next_idx >= len(gs["questions"]):
                elapsed = time.time() - gs["start_time"]
                state["_active_game"] = None
                score = gs["score"]
                total = gs["max_rounds"]
                state["_game_state"] = {}
                emotion_sys.current = Emotion.EXCITED
                return (f"CORRECT! Final score: {score}/{total} in {elapsed:.0f}s! You're an expert!", "achievement")
            else:
                next_q = gs["questions"][next_idx]["q"]
                return (f"YES! Q{next_idx + 1}: {next_q}", "correct")
        else:
            if next_idx >= len(gs["questions"]):
                elapsed = time.time() - gs["start_time"]
                state["_active_game"] = None
                score = gs["score"]
                total = gs["max_rounds"]
                state["_game_state"] = {}
                emotion_sys.current = Emotion.HAPPY
                return (f"Nope, it was '{answer}'! Final score: {score}/{total} in {elapsed:.0f}s! Good try!", "game_over")
            else:
                next_q = gs["questions"][next_idx]["q"]
                return (f"Nope! It was '{answer}'! Q{next_idx + 1}: {next_q}", "wrong")

    # --- Would You Rather ---
    if game == "would_you_rather":
        chose_a = any(w in lower for w in ["a", "first", "option a", "first one"])
        chose_b = any(w in lower for w in ["b", "second", "option b", "second one"])
        if not chose_a and not chose_b:
            return ("Say A or B! Which would you rather?", None)

        choice = "A" if chose_a else "B"
        if gs["current"] >= len(gs["questions"]):
            state["_active_game"] = None
            state["_game_state"] = {}
            return ("Game over! Great choices!", "game_over")
        q = gs["questions"][gs["current"]]
        chosen_text = q["a"] if chose_a else q["b"]
        gs["choices"].append(choice)

        reactions = [
            f"Interesting! You chose: {chosen_text}! {_CHARACTER_DISPLAY_NAME} likes that answer!",
            f"{chosen_text}? Great choice! {_CHARACTER_DISPLAY_NAME} would pick the same!",
            f"Ooh, {chosen_text}! Bold move!",
            f"{chosen_text} — that's a spicy choice! I love it!",
        ]
        reaction = random.choice(reactions)

        gs["current"] += 1
        if gs["current"] >= gs["max_rounds"] or gs["current"] >= len(gs["questions"]):
            state["_active_game"] = None
            state["_game_state"] = {}
            emotion_sys.current = Emotion.HAPPY
            return (f"{reaction} Game over! Great choices! You're unique!", "game_over")
        else:
            next_q = gs["questions"][gs["current"]]
            next_round = gs["current"] + 1
            return (f"{reaction} Round {next_round}! Would you rather: A) {next_q['a']} OR B) {next_q['b']}?", "correct")

    # --- Rock Paper Scissors ---
    if game == "rock_paper_scissors":
        player_rock = any(w in lower for w in ["rock", "stone", "fist"])
        player_paper = any(w in lower for w in ["paper", "flat", "sheet"])
        player_scissors = any(w in lower for w in ["scissors", "cut", "snip"])

        if not player_rock and not player_paper and not player_scissors:
            return ("Say 'rock', 'paper', or 'scissors'! Let's battle!", None)

        if player_rock:
            player_choice = "rock"
        elif player_paper:
            player_choice = "paper"
        else:
            player_choice = "scissors"

        mario_choice = random.choice(["rock", "paper", "scissors"])
        rnd = gs["round"]

        if player_choice == mario_choice:
            if not RPS_TIE_REACTIONS:
                return _end_game_for_empty_pool(state, emotion_sys, "Rock Paper Scissors reactions")
            reaction = random.choice(RPS_TIE_REACTIONS)
            sfx = None
        elif (player_choice == "rock" and mario_choice == "scissors") or \
             (player_choice == "paper" and mario_choice == "rock") or \
             (player_choice == "scissors" and mario_choice == "paper"):
            if not RPS_LOSE_REACTIONS:
                return _end_game_for_empty_pool(state, emotion_sys, "Rock Paper Scissors reactions")
            gs["player_score"] += 1
            reaction = random.choice(RPS_LOSE_REACTIONS)
            sfx = "correct"
        else:
            if not RPS_WIN_REACTIONS:
                return _end_game_for_empty_pool(state, emotion_sys, "Rock Paper Scissors reactions")
            gs["mario_score"] += 1
            reaction = random.choice(RPS_WIN_REACTIONS)
            sfx = "wrong"

        status = f"You: {player_choice.upper()} vs {_CHARACTER_DISPLAY_NAME}: {mario_choice.upper()}! {reaction}"
        score_text = f"Score — You: {gs['player_score']} | {_CHARACTER_DISPLAY_NAME}: {gs['mario_score']}"

        gs["round"] += 1
        if gs["round"] > gs["max_rounds"]:
            state["_active_game"] = None
            p = gs["player_score"]
            m = gs["mario_score"]
            state["_game_state"] = {}
            if p > m:
                emotion_sys.current = Emotion.HAPPY
                return (f"{status} {score_text} — YOU WIN the battle! You're TOUGH!", "achievement")
            elif m > p:
                emotion_sys.current = Emotion.EXCITED
                return (f"{status} {score_text} — {_CHARACTER_DISPLAY_NAME.upper()} WINS! Ha ha! Better luck next time!", "game_over")
            else:
                emotion_sys.current = Emotion.SURPRISED
                return (f"{status} {score_text} — It's a DRAW! We're perfectly matched!", "game_over")

        return (f"{status} {score_text} | Round {gs['round']} of {gs['max_rounds']}! Say rock, paper, or scissors!", sfx)

    # --- Hangman ---
    if game == "hangman":
        word = gs["word"]
        guess = ""
        words = lower.strip().split()
        for w in words:
            if len(w) == 1 and w.isalpha():
                guess = w
                break
        if not guess:
            for w in words:
                if w.isalpha():
                    guess = w[0]
                    break

        if not guess:
            display = " ".join(ch.upper() if ch in gs["guessed"] else "_" for ch in word)
            return (f"Say a letter to guess! Current word: {display} | Wrong guesses: {gs['wrong_guesses']}/{gs['max_wrong']}", None)

        guess = guess.lower()
        if guess in gs["guessed"]:
            display = " ".join(ch.upper() if ch in gs["guessed"] else "_" for ch in word)
            return (f"You already guessed '{guess.upper()}'! Try a different letter! {display}", None)

        gs["guessed"].append(guess)

        if guess in word:
            display = " ".join(ch.upper() if ch in gs["guessed"] else "_" for ch in word)
            if "_" not in display:
                state["_active_game"] = None
                state["_game_state"] = {}
                emotion_sys.current = Emotion.EXCITED
                return (f"YES! '{guess.upper()}' is correct! The word is {word.upper()}! YOU WIN! You're a genius!", "achievement")
            count = word.count(guess)
            emotion_sys.current = Emotion.HAPPY
            return (f"YES! '{guess.upper()}' is in there {count} time{'s' if count > 1 else ''}! {display} | Wrong: {gs['wrong_guesses']}/{gs['max_wrong']} | Guess another letter!", "correct")
        else:
            gs["wrong_guesses"] += 1
            display = " ".join(ch.upper() if ch in gs["guessed"] else "_" for ch in word)
            if gs["wrong_guesses"] >= gs["max_wrong"]:
                state["_active_game"] = None
                state["_game_state"] = {}
                emotion_sys.current = Emotion.MISCHIEVOUS
                return (f"NOPE! '{guess.upper()}' is NOT in the word! GAME OVER! The word was {word.upper()}! Better luck next time!", "game_over")
            remaining = gs["max_wrong"] - gs["wrong_guesses"]
            emotion_sys.current = Emotion.CONFUSED
            return (f"Nope! '{guess.upper()}' is NOT in the word! {display} | {remaining} wrong guesses left! Try again!", "wrong")

    # --- Hot Takes ---
    if game == "hot_takes":
        agrees = any(w in lower for w in ["agree", "yes", "right", "true", "totally", "absolutely", "definitely", "correct", "for sure"])
        disagrees = any(w in lower for w in ["disagree", "no", "wrong", "false", "nah", "nope", "never", "bad take", "incorrect"])

        if not agrees and not disagrees:
            return ("Do you AGREE or DISAGREE with my take? Let me hear it!", None)

        if gs["current"] >= len(gs["takes"]):
            state["_active_game"] = None
            state["_game_state"] = {}
            return ("That's all my takes!", "game_over")
        current_take = gs["takes"][gs["current"]]

        if agrees:
            gs["agreements"] += 1
            defend_reactions = [
                f"YES! You GET it! \"{current_take}\" — that's just FACTS!",
                f"FINALLY someone with TASTE! {_CHARACTER_DISPLAY_NAME} KNEW you'd agree! We're soulmates!",
                f"See?! I TOLD everyone! Thank you for having a BRAIN! Ha ha!",
                f"That's RIGHT! You and {_CHARACTER_DISPLAY_NAME} are on the same wavelength! High five!",
                f"A person of CULTURE! I'm so happy right now!",
            ]
            reaction = random.choice(defend_reactions)
            emotion_sys.current = Emotion.EXCITED
            sfx = "correct"
        else:
            concede_reactions = [
                f"WHAT?! You DISAGREE with \"{current_take}\"?! We need to TALK!",
                f"Oh come ON! How can you not see the TRUTH?! {_CHARACTER_DISPLAY_NAME} is SHOCKED!",
                f"Fine fine, you're entitled to your WRONG opinion! Ha ha! Just kidding... mostly!",
                f"DISAGREE?! UNBELIEVABLE!",
                f"Okay okay, I RESPECT your view... but you're still WRONG! He he!",
            ]
            reaction = random.choice(concede_reactions)
            emotion_sys.current = Emotion.SURPRISED
            sfx = "wrong"

        gs["current"] += 1
        if gs["current"] >= gs["max_rounds"] or gs["current"] >= len(gs["takes"]):
            state["_active_game"] = None
            agreed = gs["agreements"]
            total = gs["max_rounds"]
            state["_game_state"] = {}
            if agreed == total:
                return (f"{reaction} That's all my takes! You agreed with ALL {total}! We're BEST FRIENDS now!", "achievement")
            elif agreed == 0:
                return (f"{reaction} That's all my takes! You disagreed with EVERYTHING! We're RIVALS! Ha ha!", "game_over")
            else:
                return (f"{reaction} That's all my takes! You agreed with {agreed} out of {total}! Not bad!", "game_over")

        next_take = gs["takes"][gs["current"]]
        next_round = gs["current"] + 1
        return (f"{reaction} Round {next_round} of {gs['max_rounds']}! Next take: \"{next_take}\" — AGREE or DISAGREE?", sfx)

    # --- Never Have I Ever ---
    if game == "never_have_i_ever":
        i_have = any(w in lower for w in ["i have", "have done", "guilty", "yeah", "yes", "yep"])
        i_havent = any(w in lower for w in ["i haven't", "i havent", "never", "nope", "no", "nah"])

        if i_have or i_havent:
            if gs["current"] >= len(gs["prompts"]):
                state["_active_game"] = None
                state["_game_state"] = {}
                return ("That's all the rounds!", "game_over")
            current_prompt = gs["prompts"][gs["current"]]

            if i_have:
                gs["daring_score"] += 1
                reactions_have = [
                    "Whoa! You actually did that?! Ha ha ha!",
                    "You're a WILD one! I can't believe it!",
                    f"NO WAY! You really did?! {_CHARACTER_DISPLAY_NAME} is SHOCKED!",
                    "Oh my! For real?! That's hilarious!",
                    "I knew you were brave but THAT brave?!",
                    "HA! You're crazier than I thought!",
                    "I'm speechless! Actually no I'm not — AMAZING!",
                ]
                reaction = random.choice(reactions_have)
                emotion_sys.current = Emotion.SURPRISED
                sfx = "coin"
            else:
                confessions = [
                    f"Smart choice! {_CHARACTER_DISPLAY_NAME} hasn't either... okay MAYBE once!",
                    "Same here! Well... actually... no comment! He he!",
                    "Good, good! Between you and me, I TOTALLY have though! Shh!",
                    "You haven't? Neither have I!",
                    "Wise choice! I wish I could say the same!",
                    "Ha! You're playing it safe! Unlike me at last Tuesday's party!",
                    "Neither have I! ...Or have I?!",
                ]
                reaction = random.choice(confessions)
                emotion_sys.current = Emotion.MISCHIEVOUS
                sfx = "powerup"

            gs["current"] += 1
            if gs["current"] >= gs["max_rounds"] or gs["current"] >= len(gs["prompts"]):
                state["_active_game"] = None
                score = gs["daring_score"]
                state["_game_state"] = {}
                if score <= 1:
                    rating = "You're CAUTIOUS! Playing it safe!"
                elif score <= 3:
                    rating = "You're ADVENTUROUS! A real explorer!"
                else:
                    rating = "You're WILD! Even I say 'WHOA, calm down!'"
                return (f"{reaction} That's all the rounds! You said 'I have' {score} times out of {gs['max_rounds']}! {rating}", "achievement")

            next_prompt = gs["prompts"][gs["current"]]
            next_round = gs["current"] + 1
            return (f"{reaction} Round {next_round} of {gs['max_rounds']}! {next_prompt} Say 'I have' or 'I haven't'!", sfx)

        prompt_text = gs["prompts"][gs["current"]] if gs["current"] < len(gs["prompts"]) else "..."
        return (f"Say 'I have' or 'I haven't'! {prompt_text}", "hint")

    # --- Mario Trivia ---
    if game == "mario_trivia":
        current_idx = gs["current"]
        if current_idx >= len(gs["questions"]):
            state["_active_game"] = None
            state["_game_state"] = {}
            return (f"Trivia over! Score: {gs['score']}/{gs['max_rounds']}!", "game_over")

        question = gs["questions"][current_idx]
        accepted = question["accept"]
        is_birthday = question.get("is_birthday_special", False)
        got_it = any(a in lower for a in accepted)

        gs["current"] += 1
        next_idx = gs["current"]

        fun_fact_line = ""
        if is_birthday and question.get("fun_fact"):
            fun_fact_line = f" Fun fact: {question['fun_fact']}"

        if got_it:
            # Birthday special questions award 2 points instead of 1
            points = 2 if is_birthday else 1
            gs["score"] += points
            if is_birthday:
                feedback = random.choice([
                    f"CORRECT! BIRTHDAY BONUS — {points} points! You know Jacob well!",
                    f"YES! That's RIGHT! Birthday bonus: {points} points! Wahoo!",
                    f"MAMA MIA! You nailed the birthday question! {points} points!",
                ])
            else:
                feedback = random.choice([
                    "CORRECT! You REALLY know your stuff!",
                    "YES! That's RIGHT! You're a true fan!",
                    "You got it! Impressive!",
                    "Correct! Are you secretly a scholar?!",
                ])
            feedback += fun_fact_line
            sfx = "correct"
        else:
            correct_answer = question["a"][0] if question.get("a") else "Unknown"
            if is_birthday:
                feedback = random.choice([
                    f"Ooh! The birthday answer was '{correct_answer}'!",
                    f"Not quite! It's '{correct_answer}'! Now you know about Jacob!",
                ])
            else:
                feedback = random.choice([
                    f"Ooh, not quite! The answer was '{correct_answer}'!",
                    f"Nope! It's '{correct_answer}'! Now you know!",
                    f"Sorry! The correct answer is '{correct_answer}'! Tricky one!",
                ])
            feedback += fun_fact_line
            sfx = "wrong"

        if next_idx >= len(gs["questions"]):
            score = gs["score"]
            total = gs["max_rounds"]
            state["_active_game"] = None
            state["_game_state"] = {}
            if score == total:
                return (f"{feedback} PERFECT SCORE! {score}/{total}! You're a MASTER!", "achievement")
            elif score >= 3:
                return (f"{feedback} Final score: {score}/{total}! Great job, you know your stuff!", "game_over")
            else:
                return (f"{feedback} Final score: {score}/{total}! Time to study up! Ha ha!", "game_over")
        else:
            next_q = gs["questions"][next_idx]["q"]
            return (f"{feedback} Question {next_idx + 1}: {next_q}", sfx)

    # --- Name That Character ---
    if game == "name_that_character":
        current_idx = gs["current"]
        if current_idx >= len(gs["characters"]):
            state["_active_game"] = None
            state["_game_state"] = {}
            return (f"Game over! Score: {gs['score']}/{gs['max_rounds']}!", "game_over")

        char = gs["characters"][current_idx]
        accepted = char["accept"]
        got_it = any(a in lower for a in accepted)
        elapsed = time.time() - gs["round_start"]

        gs["current"] += 1
        next_idx = gs["current"]

        if got_it:
            gs["score"] += 1
            if elapsed < 5:
                feedback = f"LIGHTNING FAST! {elapsed:.1f} seconds! You INSTANTLY knew it! INCREDIBLE!"
            elif elapsed < 15:
                feedback = f"Nice! {elapsed:.1f} seconds! Quick thinker!"
            else:
                feedback = f"You got it in {elapsed:.1f} seconds! A bit slow but CORRECT!"
            sfx = "correct"
        else:
            correct_answer = char["a"][0] if char.get("a") else "Unknown"
            feedback = f"Nope! It was {correct_answer.upper()}! {elapsed:.1f} seconds and no dice!"
            sfx = "wrong"

        if next_idx >= len(gs["characters"]):
            total_time = time.time() - gs["start_time"]
            score = gs["score"]
            total = gs["max_rounds"]
            state["_active_game"] = None
            state["_game_state"] = {}
            if score == total:
                return (f"{feedback} PERFECT! {score}/{total} in {total_time:.0f}s total! You know EVERYONE!", "achievement")
            elif score >= 3:
                return (f"{feedback} Final: {score}/{total} in {total_time:.0f}s! Not bad at all!", "game_over")
            else:
                return (f"{feedback} Final: {score}/{total} in {total_time:.0f}s! Time to study your characters!", "game_over")
        else:
            gs["round_start"] = time.time()
            next_desc = gs["characters"][next_idx]["desc"]
            return (f"{feedback} Character {next_idx + 1}: {next_desc}", sfx)

    # --- Bathroom Dare ---
    if game == "bathroom_dare":
        current_idx = gs["current"]
        if current_idx >= len(gs["dares"]):
            state["_active_game"] = None
            state["_game_state"] = {}
            return (f"All dares done! You completed {gs['completed']}/{gs['max_rounds']}! Wahoo!", "game_over")

        did_it = any(w in lower for w in ["done", "did it", "finished", "completed", "yes", "okay"])
        skipped = any(w in lower for w in ["skip", "pass", "no", "nope", "chicken", "next"])

        if did_it:
            gs["completed"] += 1
            reactions = [
                f"WAHOO! You actually DID it! {_CHARACTER_DISPLAY_NAME} is SO PROUD of you!",
                "INCREDIBLE! You're braver than most! Respect!",
                "YES! You're a CHAMPION! That took GUTS! Ha ha!",
                "You really did it?! You're AMAZING!",
                f"BRAVO! Standing ovation from {_CHARACTER_DISPLAY_NAME}! *clap clap clap*",
            ]
            reaction = random.choice(reactions)
            sfx = "correct"
            emotion_sys.current = Emotion.EXCITED
        elif skipped:
            reactions = [
                "Bawk bawk BAWK! Chicken! Ha ha, just kidding! It's okay!",
                "Skipped! Not everyone can be that brave!",
                "No worries! That one WAS pretty tough! Maybe next time!",
                "Oh come ON! ...Fine fine, we'll move on! Ha ha!",
            ]
            reaction = random.choice(reactions)
            sfx = "wrong"
            emotion_sys.current = Emotion.MISCHIEVOUS
        else:
            return (f"Did you do the dare? Say 'done' when you finish, or 'skip' to move on!", None)

        gs["current"] += 1
        next_idx = gs["current"]

        if next_idx >= len(gs["dares"]):
            completed = gs["completed"]
            total = gs["max_rounds"]
            state["_active_game"] = None
            state["_game_state"] = {}
            if completed == total:
                return (f"{reaction} ALL DARES COMPLETED! {completed}/{total}! You're the DARE CHAMPION!", "achievement")
            elif completed > 0:
                return (f"{reaction} Dares over! You completed {completed}/{total}! Not bad!", "game_over")
            else:
                return (f"{reaction} Dares over! You skipped them ALL?! Ha ha!", "game_over")

        next_dare = gs["dares"][next_idx]
        return (f"{reaction} Dare {next_idx + 1} of {gs['max_rounds']}: {next_dare} Say 'done' or 'skip'!", sfx)

    # --- Story Builder ---
    if game == "story_builder":
        if gs["whose_turn"] == "player":
            # Player just added their sentence
            player_addition = lower.strip()
            if len(player_addition) < 3:
                return ("Come on, add something to the story! Say a sentence to continue!", None)

            gs["story"].append(player_addition)
            gs["current_round"] += 1

            if gs["current_round"] > gs["max_rounds"]:
                full_story = " ".join(gs["story"])
                state["_active_game"] = None
                state["_game_state"] = {}
                emotion_sys.current = Emotion.HAPPY
                return (f"THE END! What a MASTERPIECE! Here's our story: {full_story} ...We should write a BOOK together!", "achievement")

            # AI adds its part
            ai_continuations = [
                "And THEN, out of NOWHERE, a mysterious figure appeared wearing sunglasses and said 'What's up?!'",
                "But WAIT! A villain showed up riding a skateboard and doing kickflips! Nobody expected THAT!",
                "Suddenly the ground started shaking and a GOLDEN treasure burst through the floor!",
                "Just when things couldn't get crazier, a stranger showed up with a BOOMBOX blasting music!",
                "And then — PLOT TWIST — it was all a dream! Just kidding! A butler in a tuxedo appeared!",
                "BUT the power activated and EVERYTHING turned to disco lights and funky music!",
                "Out of the shadows, a tiny hero appeared carrying the BIGGEST pizza anyone had ever seen!",
                "And in that exact moment, a flying machine flew by carrying a mysterious love letter!",
                "Then a wild card character crashed through the wall on a motorcycle yelling at the top of their lungs!",
                "Suddenly a portal opened and 50 gold coins came flying out like a golden fountain!",
            ]
            ai_part = random.choice(ai_continuations)
            gs["story"].append(ai_part)
            gs["whose_turn"] = "player"
            rnd = gs["current_round"]
            return (f"LOVE IT! My turn: {ai_part} ...Round {rnd} of {gs['max_rounds']}! YOUR turn! Add the next part!", "correct")

        return ("It's YOUR turn! Add a sentence to the story!", None)

    # --- Would You Rather (Mario Edition) ---
    if game == "wyr_mario":
        chose_a = any(w in lower for w in ["a", "first", "option a", "first one"])
        chose_b = any(w in lower for w in ["b", "second", "option b", "second one"])
        if not chose_a and not chose_b:
            return ("Say A or B! Which would you rather?", None)

        choice = "A" if chose_a else "B"
        if gs["current"] >= len(gs["questions"]):
            state["_active_game"] = None
            state["_game_state"] = {}
            return ("All rounds done!", "game_over")
        q = gs["questions"][gs["current"]]
        chosen_text = q["a"] if chose_a else q["b"]
        other_text = q["b"] if chose_a else q["a"]
        gs["choices"].append({"choice": choice, "text": chosen_text})

        dramatic_reactions = [
            f"Whoa! You chose '{chosen_text}' over '{other_text}'?! That says SO MUCH about you! Ha ha!",
            f"'{chosen_text}'?! REALLY?! {_CHARACTER_DISPLAY_NAME} would have picked '{other_text}'! We're so different!",
            f"Interesting! '{chosen_text}'! You know what, I RESPECT that choice! Bold move!",
            f"'{chosen_text}'! That's the choice of a TRUE adventurer! Or maybe a crazy person! Either way I love it!",
            f"'{chosen_text}'! Ooh ooh ooh! Great answer!",
        ]
        reaction = random.choice(dramatic_reactions)

        gs["current"] += 1
        if gs["current"] >= gs["max_rounds"] or gs["current"] >= len(gs["questions"]):
            state["_active_game"] = None
            choices_summary = ", ".join([c["choice"] for c in gs["choices"]])
            state["_game_state"] = {}
            emotion_sys.current = Emotion.HAPPY
            return (f"{reaction} All rounds done! Your choices were: {choices_summary}! You are TRULY one of a kind!", "game_over")
        else:
            next_q = gs["questions"][gs["current"]]
            next_round = gs["current"] + 1
            return (f"{reaction} Round {next_round}! Would you rather: A) {next_q['a']} OR B) {next_q['b']}?", "correct")

    return None


# ---------------------------------------------------------------------------
# check_game_timeout — detect stale games from idle loop
# ---------------------------------------------------------------------------

def check_game_timeout(state: dict, timeout_seconds: float = 180.0) -> tuple[str, str] | None:
    """Check if active game has timed out. Returns response tuple or None."""
    game = state.get("_active_game")
    if not game:
        return None
    last_input = state.get("_game_last_input_time", 0)
    if last_input and (time.time() - last_input) > timeout_seconds:
        logger.info(f"[GAME] Game '{game}' timed out after {timeout_seconds}s of inactivity")
        state["_active_game"] = None
        state["_game_state"] = {}
        state["_game_last_input_time"] = None
        return (
            "Looks like we forgot about our game! No worries — come back for another round anytime!",
            "neutral/friendly",
        )
    return None
