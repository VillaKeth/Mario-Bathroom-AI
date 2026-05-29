"""Test that switching characters via config works correctly."""
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.character_loader import CharacterLoader

CHARACTERS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "characters")


def test_load_test_bot():
    """TestBot loads with correct identity."""
    c = CharacterLoader(CHARACTERS_DIR, "test_bot")
    assert c.name == "TestBot"
    assert c.display_name == "Test Bot 🤖"
    assert c.voice_config["preferred_engine"] == "edge"
    assert c.collections["faces"] == "testbot_faces"


def test_test_bot_different_from_mario():
    """TestBot and Mario have different configurations."""
    mario = CharacterLoader(CHARACTERS_DIR, "mario")
    bot = CharacterLoader(CHARACTERS_DIR, "test_bot")
    
    assert mario.name != bot.name
    assert mario.display_name != bot.display_name
    assert mario.voice_config.get("preferred_engine") != bot.voice_config.get("preferred_engine") or \
           mario.voice_config.get("edge_voice") != bot.voice_config.get("edge_voice")
    assert mario.collections["faces"] != bot.collections["faces"]
    assert mario.theme_colors != bot.theme_colors


def test_test_bot_prompts():
    """TestBot has its own system and idle prompts."""
    c = CharacterLoader(CHARACTERS_DIR, "test_bot")
    system = c.get_system_prompt({})
    idle = c.get_idle_prompt()
    assert "TestBot" in system
    assert "TestBot" in idle


def test_test_bot_shared_games():
    """TestBot gets shared game pools (include_shared: true)."""
    c = CharacterLoader(CHARACTERS_DIR, "test_bot")
    shared_dir = os.path.join(CHARACTERS_DIR, "_shared")
    if os.path.exists(shared_dir):
        pools = c.get_game_pools(shared_dir)
        # Should have at least some pools if shared directory exists
        assert isinstance(pools, dict)
    else:
        # If no shared directory, just verify include_shared is True
        assert c.config["games"]["include_shared"] is True


def test_switch_back_to_mario():
    """After loading test_bot, Mario still loads correctly."""
    bot = CharacterLoader(CHARACTERS_DIR, "test_bot")
    mario = CharacterLoader(CHARACTERS_DIR, "mario")
    assert mario.name == "Mario"
    assert mario.display_name == "Mario AI 🍄"
    assert len(mario.emotion_sprite_map) == 37


def test_list_available_characters():
    """Characters directory contains expected characters."""
    available = []
    for d in os.listdir(CHARACTERS_DIR):
        if d.startswith("_") or d.startswith("."):
            continue
        char_yaml = os.path.join(CHARACTERS_DIR, d, "character.yaml")
        if os.path.exists(char_yaml):
            available.append(d)
    assert "mario" in available
    assert "pomni" in available
    assert "test_bot" in available
    assert len(available) >= 3


def test_switch_pomni():
    """Pomni character loads with correct identity."""
    c = CharacterLoader(CHARACTERS_DIR, "pomni")
    assert c.name == "Pomni"
    assert "Pomni" in c.display_name
    assert c.voice_config is not None
