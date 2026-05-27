"""Custom exceptions for the character loading system."""


class CharacterNotFoundError(Exception):
    """Raised when a character directory doesn't exist."""

    def __init__(self, name: str, characters_dir: str, available: list[str]):
        self.name = name
        self.characters_dir = characters_dir
        self.available = available
        avail_str = ", ".join(available) if available else "none"
        super().__init__(
            f"Character '{name}' not found in '{characters_dir}'. "
            f"Available characters: {avail_str}"
        )


class CharacterConfigError(Exception):
    """Raised when character.yaml is missing or invalid."""

    def __init__(self, message: str, character_name: str = None):
        self.character_name = character_name
        prefix = f"Character '{character_name}': " if character_name else ""
        super().__init__(f"{prefix}{message}")
