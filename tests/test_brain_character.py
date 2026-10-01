import os

import yaml

from shared.character_loader import CharacterLoader

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHARS = os.path.join(ROOT, "characters")


def test_fly_loads_with_brain_section():
    c = CharacterLoader(CHARS, "fly")
    assert c.brain["enabled"] is True and c.brain["gain"] == 0.65
    assert c.voice_config["preferred_engine"] == "edge"
    assert isinstance(c.state_sprite_map["talking"], list) and c.state_sprite_map["talking"]


def test_other_characters_have_no_brain():
    assert CharacterLoader(CHARS, "ani").brain == {}


def test_fly_maps_every_server_emotion_to_a_sprite():
    from server.emotions import Emotion
    c = CharacterLoader(CHARS, "fly")
    for k, v in vars(Emotion).items():
        if k.isupper():
            assert v in c.emotion_sprite_map, v


def test_fly_poses_cover_every_behavior_pose():
    from server.brain.behavior import POSE
    with open(os.path.join(CHARS, "fly", "sprite_prompts.txt"), encoding="utf-8") as f:
        text = f.read()
    for pose in set(POSE.values()) | {"speech/talking"}:
        assert f"sprites/{pose}.png" in text, pose


def test_fly_yaml_has_no_mario():
    with open(os.path.join(CHARS, "fly", "character.yaml"), encoding="utf-8") as f:
        assert "mario" not in f.read().lower()
