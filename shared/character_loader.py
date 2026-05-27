"""Character loader — reads a character directory and provides clean API access."""

import logging
import os
from pathlib import Path
from typing import Any

import yaml

from shared.character_errors import CharacterConfigError, CharacterNotFoundError

logger = logging.getLogger(__name__)


class CharacterLoader:
    """Loads a character from its directory and provides access to all properties."""

    def __init__(self, characters_dir: str, character_name: str):
        self._characters_dir = Path(characters_dir)
        self._character_name = character_name
        self._char_dir = self._characters_dir / character_name

        # Validate character directory exists
        if not self._char_dir.is_dir():
            available = [
                d.name for d in self._characters_dir.iterdir()
                if d.is_dir() and not d.name.startswith("_")
            ] if self._characters_dir.is_dir() else []
            raise CharacterNotFoundError(character_name, str(self._characters_dir), available)

        # Load character.yaml
        yaml_path = self._char_dir / "character.yaml"
        if not yaml_path.is_file():
            raise CharacterConfigError(
                "character.yaml not found", character_name=character_name
            )
        try:
            with open(yaml_path, "r", encoding="utf-8") as f:
                self._config = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise CharacterConfigError(
                f"Invalid YAML: {e}", character_name=character_name
            )

        # Validate required fields
        self._validate_required()

        # Parse identity
        identity = self._config["identity"]
        self.name: str = identity["name"]
        self.display_name: str = identity.get("display_name", self.name)
        self.tagline: str = identity.get("tagline", "")
        self.description: str = identity.get("description", "")
        self.character_dir: str = str(self._char_dir)

        # Parse voice config
        voice = self._config.get("voice", {})
        preferred_engine = voice.get("preferred_engine", "hybrid")
        valid_engines = {"hybrid", "sovits", "edge", "xtts"}
        if preferred_engine not in valid_engines:
            raise CharacterConfigError(
                f"voice.preferred_engine must be one of {valid_engines}, got '{preferred_engine}'",
                character_name=character_name,
            )
        self.voice_config: dict = {
            "preferred_engine": preferred_engine,
            "rvc_model": str(self._resolve_path(voice["rvc_model"])) if voice.get("rvc_model") else None,
            "reference_audio": str(self._resolve_path(voice["reference_audio"])) if voice.get("reference_audio") else None,
            "edge_voice": voice.get("edge_voice", "en-US-GuyNeural"),
            "rate": voice.get("rate", "+0%"),
            "pitch": voice.get("pitch", "+0Hz"),
        }
        self.pronunciation: dict = voice.get("pronunciation", {})

    def _validate_required(self):
        """Check that required fields exist in the config."""
        missing = []
        if "identity" not in self._config:
            missing.append("identity")
        else:
            identity = self._config["identity"]
            if not identity or not identity.get("name"):
                missing.append("identity.name")
        if missing:
            raise CharacterConfigError(
                f"Missing required fields: {', '.join(missing)}",
                character_name=self._character_name,
            )

    def _resolve_path(self, relative: str) -> Path:
        """Resolve a path relative to the character directory."""
        return self._char_dir / relative

    def _load_yaml_file(self, relative: str, default: Any = None) -> Any:
        """Load a YAML file relative to character directory. Returns default if missing."""
        path = self._resolve_path(relative)
        if not path.is_file():
            if default is not None:
                return default
            logger.warning(f"[character] Missing file: {path}")
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        except yaml.YAMLError as e:
            logger.warning(f"[character] Invalid YAML in {path}: {e}")
            return default
