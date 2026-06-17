"""Per-character safety toggle + slur tier (uncensor overhaul, 2026-06-16)."""
import os

from shared.character_loader import CharacterLoader


def _write_char(tmp_path, name, extra_yaml=""):
    """Write a minimal valid character.yaml and return a loaded CharacterLoader."""
    cdir = tmp_path / name
    cdir.mkdir()
    (cdir / "character.yaml").write_text(
        f"identity:\n  name: {name}\n{extra_yaml}", encoding="utf-8"
    )
    return CharacterLoader(str(tmp_path), name)


class TestCharacterSafetyConfig:
    def test_safety_defaults_on_when_absent(self, tmp_path):
        char = _write_char(tmp_path, "nobody")
        assert char.safety_enabled is True
        assert char.safety_block_slurs is True

    def test_safety_can_be_fully_disabled(self, tmp_path):
        char = _write_char(tmp_path, "wild",
                            "safety:\n  enabled: false\n  block_slurs: false\n")
        assert char.safety_enabled is False
        assert char.safety_block_slurs is False

    def test_block_slurs_independent_of_enabled(self, tmp_path):
        char = _write_char(tmp_path, "marchlike",
                            "safety:\n  enabled: false\n  block_slurs: true\n")
        assert char.safety_enabled is False
        assert char.safety_block_slurs is True
