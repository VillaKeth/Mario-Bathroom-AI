import importlib
import os
from pathlib import Path
import sys
import time
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from shared.character_loader import CharacterLoader

def test_mario_loads_from_character_dir():
    chars_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "characters")
    loader = CharacterLoader(chars_dir, "mario")
    assert loader.name == "Mario"
    assert loader.display_name == "Mario AI \U0001f344"
    prompt = loader.get_system_prompt()
    assert "Mario" in prompt or "mario" in prompt.lower()
    assert len(loader.get_phase_prompts()) == 4
    assert len(loader.get_greeting_prompts()) >= 15
    assert loader.collections["faces"] == "mario_faces"

def test_mario_idle_prompt():
    chars_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "characters")
    loader = CharacterLoader(chars_dir, "mario")
    idle = loader.get_idle_prompt()
    assert "Mario" in idle
    assert len(idle) > 50

def test_mario_time_flavors():
    chars_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "characters")
    loader = CharacterLoader(chars_dir, "mario")
    flavors = loader.get_time_flavors()
    assert "time" in flavors
    assert "day" in flavors
    assert "morning" in flavors["time"]
    assert "friday" in flavors["day"]

def test_mario_guest_type_hints():
    chars_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "characters")
    loader = CharacterLoader(chars_dir, "mario")
    hints = loader.get_guest_type_hints()
    assert "shy" in hints
    assert "curious" in hints

def test_mario_game_pools_load():
    chars_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "characters")
    shared_dir = os.path.join(chars_dir, "_shared")
    loader = CharacterLoader(chars_dir, "mario")
    pools = loader.get_game_pools(shared_dir)
    assert "trivia" in pools
    assert len(pools["trivia"]) >= 50
    assert "reactions" in pools
    assert "rps_win" in pools["reactions"]


def _load_server_module(module_name: str):
    server_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "server")
    if server_dir not in sys.path:
        sys.path.insert(0, server_dir)
    if module_name in sys.modules:
        return importlib.reload(sys.modules[module_name])
    return importlib.import_module(module_name)


def test_clean_response_never_amputates_long_replies():
    """No hardcoded length cap in code: length policy lives in config
    (response_char_ceiling via LiveConfig in main.py), so a long multi-sentence
    reply must pass through _clean_response intact. Regression: a buried
    300-char cap silently cut live ramble replies mid-sentence."""
    llm = _load_server_module("llm")
    story = " ".join(
        f"This is sentence number {i} of a long winding party story."
        for i in range(1, 13)
    )
    assert len(story) > 600  # well past any historic hardcoded cap (300/500)
    cleaned = llm._clean_response(story)
    assert cleaned == story


def test_llm_fallbacks_drop_mario_specific_text():
    llm = _load_server_module("llm")
    llm.set_character("ani", "Ani AI 💫")
    assert llm._clean_response("") == "Ani AI 💫 is here. What's on your mind?"
    assert all("Mario" not in response for response in llm.LLM_FALLBACKS)
    assert all("Mushroom Kingdom" not in response for response in llm.LLM_FALLBACKS)
    assert all("Wahoo" not in response for response in llm.LLM_FALLBACKS)


def test_safety_filter_uses_active_character_name():
    safety_filter = _load_server_module("safety_filter")
    safety_filter.set_character("ani", "Ani AI 💫")
    assert "Ani" in safety_filter.filter_response("I'm an AI language model")
    assert "Mario" not in safety_filter.filter_response("As an AI, I can help")
    redirect = safety_filter.check_input("what the fuck is this")["redirect"]
    assert redirect is not None
    assert "Mario" not in redirect
    assert "Mushroom Kingdom" not in redirect


def test_fallback_prompt_is_generic():
    mario_prompt = _load_server_module("mario_prompt")
    assert "friendly AI character" in mario_prompt.MARIO_SYSTEM_PROMPT
    assert "You ARE Mario" not in mario_prompt.MARIO_SYSTEM_PROMPT


def test_main_fallback_strings_are_not_hardcoded_to_mario():
    main_path = Path(os.path.dirname(os.path.dirname(__file__))) / "server" / "main.py"
    text = main_path.read_text(encoding="utf-8")
    assert '"message": "It\'s-a me, Mario!"' not in text
    assert '"It\'s-a me, Mario! Wahoo!"' not in text
    assert '"It\'s-a me, Mario! Welcome! Wahoo!"' not in text
    assert '"Mama mia, that took too long! Try again?"' not in text
    assert '"Mama mia! Something went wrong with that request!"' not in text


def test_party_report_uses_active_character_identity():
    party_report = _load_server_module("party_report")
    party_report.set_character("Ani", "Ani AI 💫")

    vip = MagicMock()
    vip.is_configured.return_value = True
    vip.name = "Taylor"
    vip.interaction_count = 2

    html = party_report.PartyReport(
        server_start_time=time.time() - 3600,
        birthday_vip=vip,
    ).to_html()

    assert "Ani chatted with them <b>2</b> times!" in html
    assert "<title>Ani AI 💫 — Party Report Card</title>" in html
    assert "Ani AI 💫 Party Report" in html
    assert "Generated by Ani AI 💫 Party Bot" in html
    assert "Mario chatted with them" not in html

    party_report.set_character("Mario", "Mario")


def test_party_stats_strings_are_generic(tmp_path):
    party_stats = _load_server_module("party_stats")
    party_stats.DB_PATH = str(tmp_path / "party_stats.db")
    party_stats.set_character("Ani", "Ani AI 💫")

    stats = party_stats.PartyStats()
    prompt = stats.get_stats_for_prompt()
    milestone_text = " ".join(party_stats.PartyStats.PARTY_MILESTONES.values())
    milestone_text += " " + " ".join(party_stats.PartyStats.HOUR_MILESTONES.values())

    assert "Mama mia" not in prompt
    assert "Mario approves" not in milestone_text
    assert "Mushroom Kingdom" not in milestone_text
    assert "Wahoo" not in milestone_text
    assert "Mama mia" not in milestone_text

    party_stats.set_character("Mario", "Mario")


def test_party_gossip_uses_character_name_and_generic_questions(monkeypatch):
    party_gossip = _load_server_module("party_gossip")
    party_gossip.set_character("Ani", "Ani AI 💫")

    pg = party_gossip.PartyGossip()
    pg._rivalries = [("Alex", "Jordan", "pizza")]
    monkeypatch.setattr(party_gossip.random, "choice", lambda seq: seq[5])
    hint = pg.get_rivalry_hint("guest", "pizza")
    seed_blob = " ".join(party_gossip._GOSSIP_SEED_QUESTIONS)

    assert hint is not None
    assert "Ani declares" in hint
    assert "Mario declares" not in hint
    assert "plumbing powers" not in seed_blob
    assert "I'm-a taking notes" not in seed_blob
    assert "I'm-a dealing with" not in seed_blob

    party_gossip.set_character("Mario", "Mario")


def test_catchphrase_mirror_templates_are_generic():
    catchphrase_mirror = _load_server_module("catchphrase_mirror")
    catchphrase_mirror.set_character("Ani", "Ani AI 💫")

    mirror = catchphrase_mirror.CatchphraseMirror(threshold=2)
    mirror.feed("Alex", "pizza pizza")
    phrase = mirror.get_mirror_phrase("Alex")

    assert phrase is not None
    assert "pizza" in phrase.lower()
    assert "Mama mia" not in phrase
    assert "You're-a" not in phrase
    assert "Mario" not in phrase

    catchphrase_mirror.set_character("Mario", "Mario")


def test_birthday_vip_greeting_uses_character_name():
    birthday_vip = _load_server_module("birthday_vip")
    birthday_vip.set_character("Ani", "Ani AI 💫")

    vip = birthday_vip.BirthdayVIP(name="Jordan", birthday_facts=["Loves cake"])
    greeting = vip.get_special_greeting("Jordan")

    assert greeting is not None
    assert "Jordan" in greeting
    assert "Ani" in greeting
    assert "Jacob" not in greeting
    assert "Carl" not in greeting
    assert "Stacy" not in greeting
    assert "earthquake prediction" not in greeting

    birthday_vip.set_character("Mario", "Mario")


def test_emotions_descriptions_are_generic_and_settable():
    emotions = _load_server_module("emotions")
    emotions.set_character("Ani", "Ani AI 💫")
    descriptions = " ".join(emotions.EMOTION_DESCRIPTIONS.values())

    assert "WAHOO" not in descriptions
    assert "Goomba" not in descriptions
    assert "Mario" not in descriptions
    assert "Luigi" not in descriptions
    assert "MAMA MIA" not in descriptions

    emotions.set_character("Mario", "Mario")


def test_night_progression_fallback_topics_are_generic():
    night_progression = _load_server_module("night_progression")
    night_progression.set_character("Ani", "Ani AI 💫")
    topics = " ".join(night_progression.FALLBACK_OBSESSION_TOPICS)

    for banned in ["Goomba", "Luigi", "Bowser", "Princess Peach", "Mushroom Kingdom", "Yoshi", "Waluigi", "Bob-ombs"]:
        assert banned not in topics

    night_progression.set_character("Mario", "Mario")


def test_tts_cached_phrases_remove_mario_specific_lines():
    tts_path = Path(os.path.dirname(os.path.dirname(__file__))) / "server" / "tts.py"
    text = tts_path.read_text(encoding="utf-8")

    for banned in [
        '"It\'s-a me, Mario!"',
        '"Mama mia!"',
        '"Let\'s-a go!"',
        '"Clean hands, happy Mario!"',
        '"Welcome to Mario\'s bathroom!"',
        '"Okie dokie!"',
        '"Wahoo!"',
        '"Take-a care!"',
        '"Happy birthday Jacob!"',
        '"The birthday boy is here!"',
    ]:
        assert banned not in text


def test_command_handlers_easter_eggs_use_active_character_name():
    command_handlers = _load_server_module("command_handlers")
    command_handlers.set_character("Ani", "Ani AI 💫")

    state = {
        "_last_command_time": 0,
        "_active_game": None,
        "_game_state": {},
        "speaker_name": None,
        "speaker_id": None,
        "conversation_history": [],
        "_personality_mode": None,
    }
    result = command_handlers.handle_special_commands(
        "bowser",
        state,
        {"command_cooldown": 0},
        MagicMock(current=None),
        MagicMock(),
        MagicMock(),
        MagicMock(),
    )

    assert result is not None
    assert "Ani" in result
    assert "Mario" not in result

    command_handlers.set_character("Mario", "Mario")
