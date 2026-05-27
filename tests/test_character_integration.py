import os
import sys
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
