import os
import pytest
import tempfile
import shutil
import yaml
from shared.character_loader import CharacterLoader
from shared.character_errors import CharacterNotFoundError, CharacterConfigError

@pytest.fixture
def tmp_chars(tmp_path):
    """Create a temporary characters directory with a minimal character."""
    char_dir = tmp_path / "test_char"
    char_dir.mkdir()
    config = {
        "identity": {
            "name": "TestBot",
            "display_name": "TestBot AI",
            "tagline": "Hello!",
            "description": "A test character",
        }
    }
    (char_dir / "character.yaml").write_text(yaml.dump(config))
    return tmp_path

def test_load_identity(tmp_chars):
    loader = CharacterLoader(str(tmp_chars), "test_char")
    assert loader.name == "TestBot"
    assert loader.display_name == "TestBot AI"
    assert loader.tagline == "Hello!"

def test_character_not_found(tmp_chars):
    with pytest.raises(CharacterNotFoundError) as exc:
        CharacterLoader(str(tmp_chars), "nonexistent")
    assert "nonexistent" in str(exc.value)
    assert "test_char" in str(exc.value)

def test_missing_yaml(tmp_chars):
    (tmp_chars / "empty_char").mkdir()
    with pytest.raises(CharacterConfigError):
        CharacterLoader(str(tmp_chars), "empty_char")

def test_missing_identity_name(tmp_chars):
    bad_dir = tmp_chars / "bad_char"
    bad_dir.mkdir()
    (bad_dir / "character.yaml").write_text(yaml.dump({"identity": {}}))
    with pytest.raises(CharacterConfigError) as exc:
        CharacterLoader(str(tmp_chars), "bad_char")
    assert "identity.name" in str(exc.value)

def test_character_dir_path(tmp_chars):
    loader = CharacterLoader(str(tmp_chars), "test_char")
    assert os.path.isdir(loader.character_dir)

def test_voice_config(tmp_chars):
    config_path = tmp_chars / "test_char" / "character.yaml"
    config = yaml.safe_load(config_path.read_text())
    config["voice"] = {
        "preferred_engine": "hybrid",
        "edge_voice": "en-US-GuyNeural",
        "rate": "+10%",
        "pitch": "+0Hz",
        "pronunciation": {"wahoo": "wah-hoo"},
    }
    config_path.write_text(yaml.dump(config))
    loader = CharacterLoader(str(tmp_chars), "test_char")
    assert loader.voice_config["preferred_engine"] == "hybrid"
    assert loader.pronunciation == {"wahoo": "wah-hoo"}

def test_voice_config_defaults(tmp_chars):
    loader = CharacterLoader(str(tmp_chars), "test_char")
    assert loader.voice_config["preferred_engine"] == "hybrid"
    assert loader.pronunciation == {}

def test_voice_config_invalid_engine(tmp_chars):
    config_path = tmp_chars / "test_char" / "character.yaml"
    config = yaml.safe_load(config_path.read_text())
    config["voice"] = {"preferred_engine": "invalid_engine"}
    config_path.write_text(yaml.dump(config))
    with pytest.raises(CharacterConfigError) as exc:
        CharacterLoader(str(tmp_chars), "test_char")
    assert "preferred_engine" in str(exc.value)

def test_visuals_config(tmp_chars):
    config_path = tmp_chars / "test_char" / "character.yaml"
    config = yaml.safe_load(config_path.read_text())
    config["visuals"] = {
        "sprite_dir": "sprites/",
        "ai_poses_dir": "sprites/ai_poses/",
        "ai_pose_size": [250, 250],
        "emotion_sprite_map": {"happy": "positive/happy", "sad": "negative/sad"},
        "state_sprite_map": {"idle": "neutral/idle", "talking": ["speech/talking"]},
        "theme_colors": {"primary": "#E52521", "secondary": "#049CD8", "accent": "#FBD000", "text": "#FFFFFF"},
        "particle_colors": ["#FFD700", "#E52521"],
    }
    config_path.write_text(yaml.dump(config))
    loader = CharacterLoader(str(tmp_chars), "test_char")
    assert loader.emotion_sprite_map["happy"] == "positive/happy"
    assert loader.state_sprite_map["idle"] == "neutral/idle"
    assert loader.theme_colors["primary"] == "#E52521"
    assert loader.ai_pose_size == (250, 250)

def test_visuals_defaults(tmp_chars):
    loader = CharacterLoader(str(tmp_chars), "test_char")
    assert loader.emotion_sprite_map == {}
    assert loader.state_sprite_map == {}
    assert loader.theme_colors == {"primary": "#FFFFFF", "secondary": "#CCCCCC", "accent": "#FFD700", "text": "#FFFFFF"}
