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
