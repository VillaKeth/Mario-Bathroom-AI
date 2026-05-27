# Modular Character System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace all hardcoded Mario identity throughout the codebase with a modular character system loaded from `characters/mario/character.yaml`.

**Architecture:** A `CharacterLoader` class in `shared/character_loader.py` reads a character directory (YAML config + prompt files + sprites + voice + game pools + memories) and provides a clean API used by both server and client. Mario is extracted as the first character. The system merges character-specific content with shared content from `characters/_shared/`.

**Tech Stack:** Python 3.11+, PyYAML, pytest, existing server/client stack

**Spec:** `docs/superpowers/specs/2026-05-25-modular-character-system-design.md`

---

## File Structure

### New Files
| File | Responsibility |
|------|---------------|
| `shared/__init__.py` | Package init for shared module |
| `shared/character_loader.py` | CharacterLoader class — reads YAML, resolves paths, provides API |
| `shared/character_errors.py` | CharacterNotFoundError, CharacterConfigError exceptions |
| `characters/mario/character.yaml` | Mario's full YAML config |
| `characters/mario/prompts/system_prompt.md` | Core Mario persona |
| `characters/mario/prompts/idle_prompt.md` | Idle monologue prompt |
| `characters/mario/prompts/phases.yaml` | Party phase modifiers |
| `characters/mario/prompts/greetings.yaml` | Event-triggered prompts |
| `characters/mario/prompts/guest_type_hints.yaml` | Guest personality hints |
| `characters/mario/prompts/time_flavors.yaml` | Time-of-day flavor text |
| `characters/mario/games/trivia.yaml` | Mario trivia questions |
| `characters/mario/games/reactions.yaml` | RPS win/lose/tie reactions |
| `characters/mario/games/word_chains.yaml` | Word chain starter words |
| `characters/mario/games/simon.yaml` | Simon Says actions |
| `characters/mario/games/twenty_questions.yaml` | 20 Questions items |
| `characters/mario/games/riddles.yaml` | Riddle Q&A |
| `characters/mario/games/karaoke.yaml` | Karaoke songs |
| `characters/mario/games/rapid_fire.yaml` | Rapid fire questions |
| `characters/mario/games/truth_or_dare.yaml` | Truths, dares, bathroom dares |
| `characters/mario/games/would_you_rather.yaml` | WYR prompts |
| `characters/mario/games/wyr_extended.yaml` | Extended WYR |
| `characters/mario/games/hangman.yaml` | Hangman words |
| `characters/mario/games/hot_takes.yaml` | Hot take prompts |
| `characters/mario/games/name_that_character.yaml` | Character guessing |
| `characters/mario/games/story_starters.yaml` | Story opener prompts |
| `characters/mario/games/nhie.yaml` | Never Have I Ever |
| `characters/_shared/games/would_you_rather.yaml` | Shared WYR (character-neutral subset) |
| `characters/_shared/games/truth_or_dare.yaml` | Shared truth/dare |
| `characters/_shared/games/nhie.yaml` | Shared NHIE |
| `characters/_shared/events/shot_events.json` | Shot events (copied from server/data/) |
| `tests/test_character_loader.py` | Unit tests for CharacterLoader |
| `tests/test_character_integration.py` | Integration tests — Mario through loader |

### Modified Files
| File | Changes |
|------|---------|
| `config.json` | Add top-level `"character": "mario"` field |
| `server/main.py` | Use CharacterLoader for TTS setup, catchphrases, prompt assembly, Qdrant collections |
| `server/mario_prompt.py` | Keep helper functions, remove hardcoded prompts/constants (they move to YAML) |
| `server/game_handlers.py` | Accept pools dict at init instead of hardcoded constants |
| `server/tts.py` | Accept pronunciation dict in `_preclean_tts_text` |
| `server/face_memory.py` | Accept collection name parameter instead of hardcoded `"mario_faces"` |
| `server/speaker_id.py` | Accept collection name parameter instead of hardcoded `"mario_voices"` |
| `server/memory_semantic.py` | Accept collection name parameter instead of hardcoded `"mario_memories"` |
| `client/mario_display.py` | Load sprites, theme colors, window title from CharacterLoader |
| `client/main.py` | Load character config, pass to display |
| `server/requirements.txt` | Add `PyYAML>=6.0` |
| `client/requirements.txt` | Add `PyYAML>=6.0` (client imports shared.character_loader) |
| `server/mario_prompt.py` | Refactor `build_context()` to use CharacterLoader prompts; remove hardcoded prompt constants |
| `server/vip_knowledge.py` | Wire VIP profile loading from character directory |

---

## Task 1: Install PyYAML and Create Shared Package

**Files:**
- Create: `shared/__init__.py`
- Create: `shared/character_errors.py`
- Modify: `server/requirements.txt`
- Modify: `client/requirements.txt`

- [ ] **Step 1: Add PyYAML to requirements**

```
# Append to server/requirements.txt:
PyYAML>=6.0

# Append to client/requirements.txt:
PyYAML>=6.0
```

- [ ] **Step 2: Install PyYAML**

Run: `pip install PyYAML>=6.0`
Expected: Successfully installed

- [ ] **Step 3: Create shared package**

Create `shared/__init__.py`:
```python
"""Shared modules used by both server and client."""
```

Create `shared/character_errors.py`:
```python
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
```

- [ ] **Step 4: Write error tests**

Create `tests/test_character_errors.py`:
```python
from shared.character_errors import CharacterNotFoundError, CharacterConfigError

def test_not_found_lists_available():
    err = CharacterNotFoundError("sonic", "/chars", ["mario", "luigi"])
    assert "sonic" in str(err)
    assert "mario, luigi" in str(err)

def test_not_found_empty_available():
    err = CharacterNotFoundError("sonic", "/chars", [])
    assert "none" in str(err)

def test_config_error_with_name():
    err = CharacterConfigError("missing identity.name", character_name="mario")
    assert "mario" in str(err)
    assert "missing identity.name" in str(err)

def test_config_error_without_name():
    err = CharacterConfigError("invalid YAML syntax")
    assert "invalid YAML syntax" in str(err)
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/test_character_errors.py -v`
Expected: 4 passed

- [ ] **Step 6: Commit**

```bash
git add shared/ server/requirements.txt tests/test_character_errors.py
git commit -m "feat: create shared package with character error types"
```

---

## Task 2: Build CharacterLoader Core (Identity + Path Resolution)

**Files:**
- Create: `shared/character_loader.py`
- Create: `tests/test_character_loader.py`
- Create: `characters/mario/character.yaml` (identity section only to start)

- [ ] **Step 1: Create minimal character.yaml for testing**

Create `characters/mario/character.yaml`:
```yaml
identity:
  name: "Mario"
  display_name: "Mario AI 🍄"
  tagline: "It's-a me!"
  description: "The famous plumber from the Mushroom Kingdom"
```

- [ ] **Step 2: Write failing tests for CharacterLoader init**

Create `tests/test_character_loader.py`:
```python
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
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_character_loader.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'shared.character_loader'`

- [ ] **Step 4: Implement CharacterLoader core**

Create `shared/character_loader.py`:
```python
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

    def _validate_required(self):
        """Check that required fields exist in the config."""
        missing = []
        identity = self._config.get("identity")
        if not identity:
            missing.append("identity")
        elif not identity.get("name"):
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_character_loader.py -v`
Expected: 5 passed

- [ ] **Step 6: Commit**

```bash
git add shared/character_loader.py characters/mario/character.yaml tests/test_character_loader.py
git commit -m "feat: CharacterLoader core with identity loading and validation"
```

---

## Task 3: Add Voice and Pronunciation Config to CharacterLoader

**Files:**
- Modify: `shared/character_loader.py`
- Modify: `characters/mario/character.yaml`
- Modify: `tests/test_character_loader.py`

- [ ] **Step 1: Add voice section to Mario's character.yaml**

Append to `characters/mario/character.yaml`:
```yaml
voice:
  preferred_engine: "hybrid"
  rvc_model: "voice/rvc_model.pth"
  reference_audio: "voice/reference_audio.wav"
  edge_voice: "en-US-GuyNeural"
  rate: "+10%"
  pitch: "+0Hz"
  pronunciation:
    "wahoo": "wah-hoo"
    "whoa": "woah"
    "yippee": "yip-pee"
    "mamma mia": "mama mee-ah"
    "mama mia": "mama mee-ah"
    "okie dokie": "oh-key doh-key"
    "ha ha ha": "hah hah hah"
    "ha ha": "hah hah"
```

- [ ] **Step 2: Write failing tests for voice config**

Add to `tests/test_character_loader.py`:
```python
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
```

- [ ] **Step 3: Run tests — expect failure**

Run: `pytest tests/test_character_loader.py::test_voice_config -v`
Expected: FAIL — `AttributeError: 'CharacterLoader' object has no attribute 'voice_config'`

- [ ] **Step 4: Implement voice config parsing**

Add to `CharacterLoader.__init__()` after identity parsing:
```python
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
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/test_character_loader.py -v`
Expected: All passed

- [ ] **Step 6: Commit**

```bash
git add shared/character_loader.py characters/mario/character.yaml tests/test_character_loader.py
git commit -m "feat: add voice config and pronunciation to CharacterLoader"
```

---

## Task 4: Add Visuals Config to CharacterLoader

**Files:**
- Modify: `shared/character_loader.py`
- Modify: `characters/mario/character.yaml`
- Modify: `tests/test_character_loader.py`

- [ ] **Step 1: Add visuals section to character.yaml**

Append to `characters/mario/character.yaml` the full visuals section from the spec (emotion_sprite_map with all 37 emotions, state_sprite_map with 9 states, theme_colors, particle_colors, fallback_sprites). Extract values from `client/mario_display.py:61-112`.

- [ ] **Step 2: Write failing tests**

Add to `tests/test_character_loader.py`:
```python
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
```

- [ ] **Step 3: Implement visuals parsing**

Add to `CharacterLoader.__init__()`:
```python
        # Parse visuals
        visuals = self._config.get("visuals", {})
        self.sprite_dir: str = str(self._resolve_path(visuals.get("sprite_dir", "sprites/")))
        self.ai_poses_dir: str = str(self._resolve_path(visuals.get("ai_poses_dir", "sprites/ai_poses/")))
        size = visuals.get("ai_pose_size", [250, 250])
        self.ai_pose_size: tuple = tuple(size) if isinstance(size, list) else (250, 250)
        self.emotion_sprite_map: dict = visuals.get("emotion_sprite_map", {})
        self.state_sprite_map: dict = visuals.get("state_sprite_map", {})
        self.fallback_sprites: dict = visuals.get("fallback_sprites", {})
        self.theme_colors: dict = visuals.get("theme_colors", {
            "primary": "#FFFFFF", "secondary": "#CCCCCC",
            "accent": "#FFD700", "text": "#FFFFFF",
        })
        self.particle_colors: list = visuals.get("particle_colors", [])
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_character_loader.py -v`
Expected: All passed

- [ ] **Step 5: Commit**

```bash
git add shared/character_loader.py characters/mario/character.yaml tests/test_character_loader.py
git commit -m "feat: add visuals config to CharacterLoader (37 emotions, 9 states)"
```

---

## Task 5: Add Prompt System to CharacterLoader

**Files:**
- Modify: `shared/character_loader.py`
- Create: `characters/mario/prompts/system_prompt.md`
- Create: `characters/mario/prompts/idle_prompt.md`
- Create: `characters/mario/prompts/phases.yaml`
- Create: `characters/mario/prompts/greetings.yaml`
- Create: `characters/mario/prompts/guest_type_hints.yaml`
- Create: `characters/mario/prompts/time_flavors.yaml`
- Modify: `tests/test_character_loader.py`

- [ ] **Step 1: Extract prompts from mario_prompt.py to files**

Extract `MARIO_SYSTEM_PROMPT` (line 44-57) → `characters/mario/prompts/system_prompt.md`
Extract `_LLM_IDLE_SYSTEM_PROMPT` (server/main.py:2166) → `characters/mario/prompts/idle_prompt.md`
Extract `PHASE_PROMPTS` (line 59-78) → `characters/mario/prompts/phases.yaml`
Extract `GREETING_PROMPTS` (line 117-134) → `characters/mario/prompts/greetings.yaml`
Extract `GUEST_TYPE_HINTS` (line 108-115) → `characters/mario/prompts/guest_type_hints.yaml`
Extract `_TIME_FLAVORS` + `_DAY_FLAVORS` (line 137-151) → `characters/mario/prompts/time_flavors.yaml`

These are direct copies of the existing content into YAML/Markdown files. The `system_prompt.md` keeps the exact text from `MARIO_SYSTEM_PROMPT`.

- [ ] **Step 2: Write failing tests**

Add to `tests/test_character_loader.py`:
```python
def test_get_system_prompt(tmp_chars):
    prompts_dir = tmp_chars / "test_char" / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "system_prompt.md").write_text("You are {{character_name}}, {{description}}.")
    loader = CharacterLoader(str(tmp_chars), "test_char")
    prompt = loader.get_system_prompt({"character_name": "TestBot", "description": "a bot"})
    assert prompt == "You are TestBot, a bot."

def test_get_system_prompt_missing_file(tmp_chars):
    loader = CharacterLoader(str(tmp_chars), "test_char")
    prompt = loader.get_system_prompt({})
    assert prompt == ""

def test_get_phase_prompts(tmp_chars):
    prompts_dir = tmp_chars / "test_char" / "prompts"
    prompts_dir.mkdir(exist_ok=True)
    phases = {"WARM_UP": "Be warm", "PARTY_MODE": "Go wild"}
    (prompts_dir / "phases.yaml").write_text(yaml.dump(phases))
    loader = CharacterLoader(str(tmp_chars), "test_char")
    result = loader.get_phase_prompts()
    assert result["WARM_UP"] == "Be warm"

def test_get_greeting_prompts(tmp_chars):
    prompts_dir = tmp_chars / "test_char" / "prompts"
    prompts_dir.mkdir(exist_ok=True)
    greetings = {"enter_known": "Welcome back {name}!", "idle": "Talking to self"}
    (prompts_dir / "greetings.yaml").write_text(yaml.dump(greetings))
    loader = CharacterLoader(str(tmp_chars), "test_char")
    result = loader.get_greeting_prompts()
    assert "enter_known" in result

def test_build_context_returns_list_of_dicts(tmp_chars):
    prompts_dir = tmp_chars / "test_char" / "prompts"
    prompts_dir.mkdir(exist_ok=True)
    (prompts_dir / "system_prompt.md").write_text("You are {{character_name}}.")
    loader = CharacterLoader(str(tmp_chars), "test_char")
    ctx = loader.build_context(
        phase_modifier={"personality_warmth": 0.9, "chaos": 0.1, "gossip_aggression": 0.1, "roast_level": 0.1},
        last_emotion="happy",
    )
    assert isinstance(ctx, list)
    assert all(isinstance(m, dict) for m in ctx)
    assert ctx[0]["role"] == "system"
    assert "TestBot" in ctx[0]["content"]
    # Phase should show warmth hint
    phase_msgs = [m for m in ctx if "warm" in m["content"].lower()]
    assert len(phase_msgs) == 1
    # Emotion should be present
    emotion_msgs = [m for m in ctx if "happy" in m["content"]]
    assert len(emotion_msgs) == 1

def test_build_context_with_guest_and_event(tmp_chars):
    prompts_dir = tmp_chars / "test_char" / "prompts"
    prompts_dir.mkdir(exist_ok=True)
    (prompts_dir / "system_prompt.md").write_text("You are {{character_name}}.")
    greetings = {"enter_known": "Welcome back!"}
    (prompts_dir / "greetings.yaml").write_text(yaml.dump(greetings))
    loader = CharacterLoader(str(tmp_chars), "test_char")
    ctx = loader.build_context(speaker_name="Alice", memories=["Met at party"], event="enter_known")
    contents = [m["content"] for m in ctx]
    assert any("Alice" in c for c in contents)
    assert any("Welcome back" in c for c in contents)

def test_build_context_empty_when_no_prompts(tmp_chars):
    loader = CharacterLoader(str(tmp_chars), "test_char")
    ctx = loader.build_context()
    assert ctx == []
```

- [ ] **Step 3: Implement prompt loading methods**

Add to `CharacterLoader`:
```python
    def get_system_prompt(self, context: dict = None) -> str:
        """Read system_prompt.md and substitute {{variables}}."""
        path = self._resolve_path("prompts/system_prompt.md")
        if not path.is_file():
            logger.warning(f"[character] No system_prompt.md for {self.name}")
            return ""
        text = path.read_text(encoding="utf-8")
        if context:
            for key, value in context.items():
                text = text.replace("{{" + key + "}}", str(value))
        return text

    def get_idle_prompt(self) -> str:
        """Read idle_prompt.md."""
        path = self._resolve_path("prompts/idle_prompt.md")
        if not path.is_file():
            return ""
        return path.read_text(encoding="utf-8")

    def get_phase_prompts(self) -> dict:
        """Read phases.yaml — party phase modifier text."""
        return self._load_yaml_file("prompts/phases.yaml", default={})

    def get_greeting_prompts(self) -> dict:
        """Read greetings.yaml — event-triggered prompt templates."""
        return self._load_yaml_file("prompts/greetings.yaml", default={})

    def get_guest_type_hints(self) -> dict:
        """Read guest_type_hints.yaml."""
        return self._load_yaml_file("prompts/guest_type_hints.yaml", default={})

    def get_time_flavors(self) -> dict:
        """Read time_flavors.yaml — time-of-day/day-of-week flavor text."""
        return self._load_yaml_file("prompts/time_flavors.yaml", default={})

    def build_context(self, speaker_name: str = None, memories: list = None,
                      event: str = None, phase_modifier: dict = None,
                      guest_context: str = None, **kwargs) -> list[dict]:
        """Build the full LLM context (system messages) from character prompts.

        Matches the signature of server/mario_prompt.py:build_context() so it
        can be a drop-in replacement. Returns list[dict] of system messages.

        Args:
            speaker_name: Guest name (will be sanitized)
            memories: Guest memory list from semantic memory
            event: Event type key for greeting prompts (e.g. "enter_known")
            phase_modifier: Dict from NightProgression with personality_warmth,
                chaos, gossip_aggression, roast_level (all 0.0-1.0)
            guest_context: Pre-formatted guest context string
            **kwargs: visit_count, last_topic, last_emotion, vip_info, guest_type,
                      time_flavor (if None, auto-derived from time_flavors.yaml)
        """
        import re as _re
        from datetime import datetime

        # Sanitize speaker_name (same logic as mario_prompt._sanitize_input)
        if speaker_name:
            speaker_name = speaker_name.strip()[:20]
            speaker_name = _re.sub(r'[\x00-\x1f\x7f]', '', speaker_name)
            speaker_name = _re.sub(r'[{}()\[\]<>]', '', speaker_name)
            if not speaker_name:
                speaker_name = "friend"

        messages = []

        # 1. System prompt
        system_prompt = self.get_system_prompt({
            "character_name": self.name,
            "description": self.description,
        })
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        # 2. Phase modifier (uses same logic as mario_prompt.py:208-240)
        if phase_modifier:
            warmth = phase_modifier.get("personality_warmth", 0.5)
            chaos = phase_modifier.get("chaos", 0.2)
            gossip = phase_modifier.get("gossip_aggression", 0.2)
            roast = phase_modifier.get("roast_level", 0.2)
            phase_hints = []
            if warmth > 0.7:
                phase_hints.append("Be extra warm, welcoming, and friendly")
            if chaos > 0.7:
                phase_hints.append("Be UNHINGED and chaotic — wild tangents, absurd energy")
            if gossip > 0.6:
                phase_hints.append("Be gossipy — tease, prod, stir drama playfully")
            if roast > 0.6:
                phase_hints.append("Roast mode — playful burns, trash talk, comedic insults")
            if phase_hints:
                messages.append({"role": "system", "content": "Phase vibes: " + "; ".join(phase_hints)})

        # 3. Time flavor — use provided or auto-derive from time_flavors.yaml
        time_flavor = kwargs.get("time_flavor")
        if not time_flavor:
            flavors = self.get_time_flavors()
            if flavors:
                now = datetime.now()
                hour = now.hour
                day_name = now.strftime("%A")
                time_keys = flavors.get("time", {})
                day_keys = flavors.get("day", {})
                # Match hour ranges from YAML (e.g. "late_night": "After midnight...")
                if hour >= 0 and hour < 6 and "late_night" in time_keys:
                    time_flavor = time_keys["late_night"]
                elif hour >= 6 and hour < 12 and "morning" in time_keys:
                    time_flavor = time_keys["morning"]
                elif hour >= 12 and hour < 17 and "afternoon" in time_keys:
                    time_flavor = time_keys["afternoon"]
                elif hour >= 17 and hour < 21 and "evening" in time_keys:
                    time_flavor = time_keys["evening"]
                elif "night" in time_keys:
                    time_flavor = time_keys["night"]
                # Add day flavor if available
                if day_name.lower() in day_keys:
                    time_flavor = (time_flavor or "") + " " + day_keys[day_name.lower()]
        if time_flavor:
            messages.append({"role": "system", "content": time_flavor.strip()})

        # 4. Emotion context
        last_emotion = kwargs.get("last_emotion")
        if last_emotion:
            messages.append({"role": "system", "content": f"Your current emotion: {last_emotion}"})

        # 5. VIP context
        vip_info = kwargs.get("vip_info")
        if vip_info:
            messages.append({"role": "system", "content": vip_info})

        # 6. Guest context + memories
        if guest_context:
            messages.append({"role": "system", "content": guest_context})
        elif speaker_name and memories:
            mem_text = "\n".join(str(m) for m in memories)
            messages.append({"role": "system", "content": f"Guest: {speaker_name}\nMemories:\n{mem_text}"})

        # 7. Event greeting prompt
        if event:
            greetings = self.get_greeting_prompts()
            if event in greetings:
                messages.append({"role": "system", "content": greetings[event]})

        # 8. Guest type hints
        guest_type = kwargs.get("guest_type")
        if guest_type:
            hints = self.get_guest_type_hints()
            if guest_type in hints:
                messages.append({"role": "system", "content": hints[guest_type]})

        return messages
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_character_loader.py -v`
Expected: All passed

- [ ] **Step 5: Commit**

```bash
git add shared/character_loader.py characters/mario/prompts/ tests/test_character_loader.py
git commit -m "feat: add prompt system to CharacterLoader (system, idle, phases, greetings)"
```

---

## Task 6: Add Game Pool Loading to CharacterLoader

**Files:**
- Modify: `shared/character_loader.py`
- Create: all game YAML files in `characters/mario/games/`
- Create: shared game files in `characters/_shared/games/`
- Create: `characters/_shared/events/shot_events.json`
- Modify: `tests/test_character_loader.py`

- [ ] **Step 1: Extract game pools from game_handlers.py to YAML**

Extract each constant from `server/game_handlers.py` to its corresponding YAML file. This is a mechanical extraction — copy the Python list/dict content into YAML format.

Key pools and their source lines:
- `SIMON_ACTIONS` (88) → `games/simon.yaml`
- `TWENTY_Q_THINGS` (122) → `games/twenty_questions.yaml`
- `RIDDLES` (154) → `games/riddles.yaml`
- `STARTER_WORDS` (187) → `games/word_chains.yaml`
- `KARAOKE_SONGS` (194) → `games/karaoke.yaml`
- `RAPID_FIRE_QUESTIONS` (222) → `games/rapid_fire.yaml`
- `TRUTH_QUESTIONS` (255) → `games/truth_or_dare.yaml` (truths key)
- `DARES` (288) → `games/truth_or_dare.yaml` (dares key)
- `WOULD_YOU_RATHER` (317) → `games/would_you_rather.yaml`
- `RPS_WIN_REACTIONS` (346) → `games/reactions.yaml` (rps_win key)
- `RPS_LOSE_REACTIONS` (369) → `games/reactions.yaml` (rps_lose key)
- `RPS_TIE_REACTIONS` (392) → `games/reactions.yaml` (rps_tie key)
- `HANGMAN_WORDS` (415) → `games/hangman.yaml`
- `HOT_TAKES` (424) → `games/hot_takes.yaml`
- `MARIO_TRIVIA_QUESTIONS` (472) → `games/trivia.yaml`
- `NAME_THAT_CHARACTER` (533) → `games/name_that_character.yaml`
- `BATHROOM_DARES` (561) → `games/truth_or_dare.yaml` (bathroom_dares key)
- `STORY_STARTERS` (589) → `games/story_starters.yaml`
- `WYR_EXTENDED` (622) → `games/wyr_extended.yaml`
- `NHIE_PROMPTS` (650) → `games/nhie.yaml`

Also create `characters/_shared/events/shot_events.json` by copying `server/data/shot_events.json`.

- [ ] **Step 2: Write failing tests**

Add to `tests/test_character_loader.py`:
```python
def test_get_game_pools_character_only(tmp_chars):
    games_dir = tmp_chars / "test_char" / "games"
    games_dir.mkdir()
    trivia = [{"question": "Test?", "answer": "Yes"}]
    (games_dir / "trivia.yaml").write_text(yaml.dump(trivia))
    config_path = tmp_chars / "test_char" / "character.yaml"
    config = yaml.safe_load(config_path.read_text())
    config["games"] = {"pools_dir": "games/", "include_shared": False}
    config_path.write_text(yaml.dump(config))
    loader = CharacterLoader(str(tmp_chars), "test_char")
    pools = loader.get_game_pools(str(tmp_chars / "_shared"))
    assert len(pools["trivia"]) == 1
    assert pools["trivia"][0]["question"] == "Test?"

def test_get_game_pools_merges_shared(tmp_chars):
    # Character has 1 trivia item
    games_dir = tmp_chars / "test_char" / "games"
    games_dir.mkdir()
    (games_dir / "trivia.yaml").write_text(yaml.dump([{"question": "Char?", "answer": "Yes"}]))
    # Shared has 1 trivia item
    shared_games = tmp_chars / "_shared" / "games"
    shared_games.mkdir(parents=True)
    (shared_games / "trivia.yaml").write_text(yaml.dump([{"question": "Shared?", "answer": "No"}]))
    config_path = tmp_chars / "test_char" / "character.yaml"
    config = yaml.safe_load(config_path.read_text())
    config["games"] = {"pools_dir": "games/", "include_shared": True}
    config_path.write_text(yaml.dump(config))
    loader = CharacterLoader(str(tmp_chars), "test_char")
    pools = loader.get_game_pools(str(tmp_chars / "_shared"))
    assert len(pools["trivia"]) == 2

def test_get_game_pools_empty(tmp_chars):
    loader = CharacterLoader(str(tmp_chars), "test_char")
    pools = loader.get_game_pools(str(tmp_chars / "_shared"))
    assert pools == {}
```

- [ ] **Step 3: Implement game pool loading**

Add to `CharacterLoader`:
```python
    def get_game_pools(self, shared_dir: str = None) -> dict:
        """Load game pools from character directory, optionally merging with shared."""
        pools = {}
        games_cfg = self._config.get("games", {})
        pools_rel = games_cfg.get("pools_dir", "games/")
        include_shared = games_cfg.get("include_shared", True)

        # Load shared pools first (if enabled)
        if include_shared and shared_dir:
            shared_games = Path(shared_dir) / "games"
            if shared_games.is_dir():
                for yaml_file in shared_games.glob("*.yaml"):
                    pool_name = yaml_file.stem
                    data = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
                    if data:
                        pools[pool_name] = data

        # Load character-specific pools (merge with shared)
        char_games = self._resolve_path(pools_rel)
        if char_games.is_dir():
            for yaml_file in char_games.glob("*.yaml"):
                pool_name = yaml_file.stem
                data = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
                if data is None:
                    continue
                if pool_name in pools:
                    existing = pools[pool_name]
                    if isinstance(existing, list) and isinstance(data, list):
                        pools[pool_name] = existing + data
                    elif isinstance(existing, dict) and isinstance(data, dict):
                        existing.update(data)
                    else:
                        pools[pool_name] = data
                else:
                    pools[pool_name] = data

        return pools
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_character_loader.py -v`
Expected: All passed

- [ ] **Step 5: Commit**

```bash
git add shared/character_loader.py characters/ tests/test_character_loader.py
git commit -m "feat: add game pool loading with shared content merging"
```

---

## Task 7: Add Memory and Speech Config to CharacterLoader

**Files:**
- Modify: `shared/character_loader.py`
- Modify: `characters/mario/character.yaml`
- Modify: `tests/test_character_loader.py`

- [ ] **Step 1: Add memory and speech sections to character.yaml**

Append to `characters/mario/character.yaml`:
```yaml
speech:
  accent_markers:
    - "Uses Italian-accented English"
    - "Adds '-a' to words: 'it's-a me', 'let's-a go'"
    - "Catchphrases: Wahoo!, Mama mia!, Okie dokie!"
  catchphrase_dir: "catchphrases/"

games:
  pools_dir: "games/"
  include_shared: true

memory:
  collections:
    faces: "mario_faces"
    voices: "mario_voices"
    memories: "mario_memories"
  vip_profiles_dir: "memories/vip_profiles/"
  lore_file: "memories/lore.yaml"
```

- [ ] **Step 2: Write tests and implement**

Add memory/speech parsing to `CharacterLoader.__init__()`:
```python
        # Parse speech
        speech = self._config.get("speech", {})
        self.accent_markers: list = speech.get("accent_markers", [])
        self.catchphrase_dir: str = str(self._resolve_path(speech.get("catchphrase_dir", "catchphrases/")))

        # Parse memory
        memory = self._config.get("memory", {})
        self.collections: dict = memory.get("collections", {
            "faces": f"{self.name.lower()}_faces",
            "voices": f"{self.name.lower()}_voices",
            "memories": f"{self.name.lower()}_memories",
        })
        self.vip_profiles_dir: str = str(self._resolve_path(memory.get("vip_profiles_dir", "memories/vip_profiles/")))
        self.lore_file: str = str(self._resolve_path(memory.get("lore_file", "memories/lore.yaml")))
```

Add tests for these fields.

- [ ] **Step 3: Run tests**

Run: `pytest tests/test_character_loader.py -v`
Expected: All passed

- [ ] **Step 4: Add logging summary**

Add at the end of `__init__()`:
```python
        # Log load summary
        logger.info(
            f"Loaded character '{self.name}': "
            f"{len(self.emotion_sprite_map)} emotions, "
            f"{len(self.pronunciation)} pronunciation rules, "
            f"engine={self.voice_config['preferred_engine']}"
        )
```

- [ ] **Step 5: Commit**

```bash
git add shared/character_loader.py characters/mario/character.yaml tests/test_character_loader.py
git commit -m "feat: add memory, speech config and load summary to CharacterLoader"
```

---

## Task 8: Extract Mario Prompts to Character Files

**Files:**
- Create: `characters/mario/prompts/system_prompt.md`
- Create: `characters/mario/prompts/idle_prompt.md`
- Create: `characters/mario/prompts/phases.yaml`
- Create: `characters/mario/prompts/greetings.yaml`
- Create: `characters/mario/prompts/guest_type_hints.yaml`
- Create: `characters/mario/prompts/time_flavors.yaml`

- [ ] **Step 1: Extract system prompt**

Copy the exact text of `MARIO_SYSTEM_PROMPT` from `server/mario_prompt.py:44-57` to `characters/mario/prompts/system_prompt.md`.

- [ ] **Step 2: Extract idle prompt**

Copy the exact text of `_LLM_IDLE_SYSTEM_PROMPT` from `server/main.py:2166` to `characters/mario/prompts/idle_prompt.md`.

- [ ] **Step 3: Extract phase prompts, greetings, guest hints, time flavors**

Convert each Python dict to YAML format:
- `PHASE_PROMPTS` (mario_prompt.py:59-78) → `phases.yaml`
- `GREETING_PROMPTS` (mario_prompt.py:117-134) → `greetings.yaml`
- `GUEST_TYPE_HINTS` (mario_prompt.py:108-115) → `guest_type_hints.yaml`
- `_TIME_FLAVORS` + `_DAY_FLAVORS` (mario_prompt.py:137-151) → `time_flavors.yaml`

- [ ] **Step 4: Write integration test**

Create `tests/test_character_integration.py`:
```python
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from shared.character_loader import CharacterLoader

def test_mario_loads_from_character_dir():
    chars_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "characters")
    loader = CharacterLoader(chars_dir, "mario")
    assert loader.name == "Mario"
    assert loader.display_name == "Mario AI 🍄"
    assert "Italian" in (loader.get_system_prompt() or "")
    assert len(loader.get_phase_prompts()) == 4
    assert len(loader.get_greeting_prompts()) >= 15
    assert loader.collections["faces"] == "mario_faces"
```

- [ ] **Step 5: Run integration test**

Run: `pytest tests/test_character_integration.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add characters/mario/prompts/ tests/test_character_integration.py
git commit -m "feat: extract Mario prompts to character directory files"
```

---

## Task 9: Extract Game Pools to YAML Files

**Files:**
- Create: all 16 game YAML files in `characters/mario/games/`
- Create: shared game files

- [ ] **Step 1: Write extraction script**

Create a temporary Python script that reads each constant from `server/game_handlers.py` and writes it as YAML to the corresponding file in `characters/mario/games/`. Run it once and delete it.

- [ ] **Step 2: Verify extraction**

Run: `python -c "import yaml; data = yaml.safe_load(open('characters/mario/games/trivia.yaml')); print(f'Trivia: {len(data)} items')"`
Expected: Trivia: 50 items (matching MARIO_TRIVIA_QUESTIONS count)

- [ ] **Step 3: Create shared game files**

Copy character-neutral games (would_you_rather, truth_or_dare, nhie) to `characters/_shared/games/` as well. These will be the shared baseline for all future characters.

- [ ] **Step 4: Add game pool integration test**

Add to `tests/test_character_integration.py`:
```python
def test_mario_game_pools_load():
    chars_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "characters")
    shared_dir = os.path.join(chars_dir, "_shared")
    loader = CharacterLoader(chars_dir, "mario")
    pools = loader.get_game_pools(shared_dir)
    assert "trivia" in pools
    assert len(pools["trivia"]) >= 50
    assert "reactions" in pools
    assert "rps_win" in pools["reactions"]
```

- [ ] **Step 5: Run test**

Run: `pytest tests/test_character_integration.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add characters/mario/games/ characters/_shared/ tests/test_character_integration.py
git commit -m "feat: extract 20 game pools to YAML (608+ items)"
```

---

## Task 10: Copy Mario Assets to Character Directory

**Files:**
- Copy: sprites, voice model, catchphrases, VIP profiles to `characters/mario/`

- [ ] **Step 1: Copy VIP profiles**

```powershell
New-Item -ItemType Directory -Force -Path characters\mario\memories\vip_profiles
Copy-Item server\data\vip_profiles\*.json characters\mario\memories\vip_profiles\
```

- [ ] **Step 2: Copy catchphrase WAV files (if they exist)**

```powershell
New-Item -ItemType Directory -Force -Path characters\mario\catchphrases
if (Test-Path server\assets\catchphrases\*.wav) {
    Copy-Item server\assets\catchphrases\*.wav characters\mario\catchphrases\
} else {
    Write-Host "No catchphrases to copy"
}
```

- [ ] **Step 3: Symlink or copy sprite assets**

The AI poses are large. Create a symlink from `characters/mario/sprites/ai_poses/` → `mario_3d_assets/ai_poses_transparent/` to avoid duplicating large image files. Or update `character.yaml` to point to the existing directory.

Update `characters/mario/character.yaml` visuals section:
```yaml
visuals:
  ai_poses_dir: "../../mario_3d_assets/ai_poses_transparent/"
```

- [ ] **Step 4: Copy shot events to shared**

```powershell
New-Item -ItemType Directory -Force -Path characters\_shared\events
Copy-Item server\data\shot_events.json characters\_shared\events\
```

- [ ] **Step 5: Commit**

```bash
git add characters/mario/memories/ characters/mario/catchphrases/ characters/_shared/events/
git commit -m "feat: copy Mario assets (VIP profiles, catchphrases, events) to character dir"
```

---

## Task 11: Wire Server to Use CharacterLoader

**Files:**
- Modify: `server/main.py`
- Modify: `config.json`

- [ ] **Step 1: Add "character" to config.json**

Add at top level of `config.json`:
```json
{
  "character": "mario",
  "server": { ... }
}
```

- [ ] **Step 2: Load CharacterLoader in server startup**

In `server/main.py`, near the top imports and in the startup function (around line 645):
```python
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from shared.character_loader import CharacterLoader

# In startup, after config loading:
_characters_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "characters")
_shared_dir = os.path.join(_characters_dir, "_shared")
_character_name = config.get("character", "mario")
_character = CharacterLoader(_characters_dir, _character_name)
logger.info(f"Character loaded: {_character.name} ({_character.display_name})")
```

- [ ] **Step 3: Wire TTS config from character**

Replace ALL hardcoded TTS config with character values. Wire every voice setting:
```python
# Edge TTS settings
tts.EDGE_VOICE = _character.voice_config["edge_voice"]
tts.RATE = _character.voice_config["rate"]
tts.PITCH = _character.voice_config["pitch"]

# RVC model path (if character provides one)
if _character.voice_config["rvc_model"]:
    tts.RVC_MODEL_PATH = _character.voice_config["rvc_model"]

# Reference audio for Fish Speech / GPT-SoVITS
if _character.voice_config["reference_audio"]:
    tts.REFERENCE_AUDIO = _character.voice_config["reference_audio"]

# TTS engine selection
tts.PREFERRED_ENGINE = _character.voice_config["preferred_engine"]
```

Audit `server/tts.py` and `server/main.py` for any remaining Mario-specific TTS settings (Fish Speech speaker ID, SoVITS model paths, etc.) and wire them from `voice_config` or the character directory.

Wire catchphrase bank (line 667):
```python
# Before:
catchphrase_bank = CatchphraseBank(assets_dir=os.path.join(os.path.dirname(__file__), "assets", "catchphrases"))

# After:
catchphrase_bank = CatchphraseBank(assets_dir=_character.catchphrase_dir)
```

- [ ] **Step 4: Wire pronunciation from character**

Modify `server/tts.py` `_preclean_tts_text` to accept a pronunciation dict:
```python
import re

_character_pronunciation = {}

def set_pronunciation(pronunciation: dict):
    global _character_pronunciation
    _character_pronunciation = pronunciation

def _preclean_tts_text(text: str) -> str:
    # ... existing cleanup ...
    # Replace hardcoded pronunciation subs with character-loaded ones:
    for word, phonetic in _character_pronunciation.items():
        t = re.sub(r'(?<!\w)' + re.escape(word) + r'(?!\w)', phonetic, t, flags=re.IGNORECASE)
    # ... rest of function ...
```

In server startup: `tts.set_pronunciation(_character.pronunciation)`

- [ ] **Step 5: Wire system prompt and build_context from character**

Replace all references to `mario_prompt.MARIO_SYSTEM_PROMPT` with `_character.get_system_prompt()`.
Replace `mario_prompt.PHASE_PROMPTS` with `_character.get_phase_prompts()`.
Replace `mario_prompt.GREETING_PROMPTS` with `_character.get_greeting_prompts()`.
Refactor `mario_prompt.build_context()` calls to use `_character.build_context()`, passing the same phase/guest/emotion parameters. Ensure `build_context()` returns `list[dict]` format.

- [ ] **Step 6: Wire game pools from character**

In server startup, load game pools and pass to game_handlers:
```python
_game_pools = _character.get_game_pools(_shared_dir)

# Replace hardcoded constants in game_handlers.py:
# game_handlers now accepts pools dict at init
import server.game_handlers as game_handlers
game_handlers.set_game_pools(_game_pools)
```

Add `set_game_pools()` function to `server/game_handlers.py`:
```python
# Module-level pools (defaults to existing hardcoded values for backward compat)
_pools = None

def set_game_pools(pools: dict):
    """Override hardcoded game pools with character-loaded pools."""
    global _pools
    _pools = pools
    # Update module-level constants from pools
    global MARIO_TRIVIA_QUESTIONS, SIMON_ACTIONS, TWENTY_Q_THINGS, ...
    if "trivia" in pools:
        MARIO_TRIVIA_QUESTIONS = pools["trivia"]
    # ... etc for all 20 pool constants
```

- [ ] **Step 7: Wire VIP profiles and lore from character**

In `server/main.py` and `server/mario_prompt.py`, replace hardcoded VIP profile paths with `_character.vip_profiles_dir`. Update any references to `server/data/vip_profiles/` to use the character directory path.

If `server/vip_knowledge.py` exists, parameterize it to accept a `vip_dir` path from character config.

- [ ] **Step 8: Wire idle prompt from character**

Replace the hardcoded `_LLM_IDLE_SYSTEM_PROMPT` string in `server/main.py` with:
```python
_idle_prompt = _character.get_idle_prompt()
```
Then update the idle LLM call (around line 2166+) to use `_idle_prompt` instead of the hardcoded string.

- [ ] **Step 9: Smoke test**

Start server and verify it loads without errors:
```bash
cd server && python main.py
```
Expected: "Character loaded: Mario (Mario AI 🍄)" in logs, no crashes.

- [ ] **Step 7: Commit**

```bash
git add server/main.py server/tts.py config.json
git commit -m "feat: wire server to load character from CharacterLoader"
```

---

## Task 12: Wire Memory Systems to Use Character Collections

**Files:**
- Modify: `server/face_memory.py`
- Modify: `server/speaker_id.py`
- Modify: `server/memory_semantic.py`
- Modify: `server/main.py`

- [ ] **Step 1: Parameterize face_memory.py**

Change hardcoded `"mario_faces"` to accept a `collection_name` parameter in the `FaceMemory` class `__init__()`. The server instantiates `FaceMemory(db_path)` directly (not via a module-level `init()` function), so add `collection_name` as an optional parameter to `FaceMemory.__init__()`:
```python
class FaceMemory:
    def __init__(self, db_path, collection_name="mario_faces"):
        self._collection_name = collection_name
        ...
```
Replace all internal uses of the hardcoded `"mario_faces"` string with `self._collection_name`.

- [ ] **Step 2: Parameterize speaker_id.py**

Change hardcoded `"mario_voices"` to accept a `collection_name` parameter. Replace all occurrences (lines 94, 96, 177, 216).

- [ ] **Step 3: Parameterize memory_semantic.py**

Change `COLLECTION_NAME = "mario_memories"` to a module-level variable set from character config. Replace the constant with a function `set_collection_name(name)`.

- [ ] **Step 4: Wire from server startup**

In `server/main.py` startup, pass collection names to constructors:
```python
# FaceMemory accepts collection_name in constructor
_face_memory = FaceMemory(_face_db_path, collection_name=_character.collections["faces"])

# SpeakerID — pass collection_name to init or constructor
speaker_id.init_speaker_id(collection_name=_character.collections["voices"])

# Semantic memory
memory_semantic.set_collection_name(_character.collections["memories"])
```

- [ ] **Step 5: Test existing memory tests still pass**

Run: `pytest tests/test_face_memory.py tests/test_person_id.py -v`
Expected: All pass (backwards compatible — defaults to original names)

- [ ] **Step 6: Commit**

```bash
git add server/face_memory.py server/speaker_id.py server/memory_semantic.py server/main.py
git commit -m "feat: parameterize Qdrant collection names from character config"
```

---

## Task 13: Wire Client to Use CharacterLoader

**Files:**
- Modify: `client/main.py`
- Modify: `client/mario_display.py`

- [ ] **Step 1: Load character in client main.py**

In `client/main.py`, load the character config:
```python
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from shared.character_loader import CharacterLoader

# Load character from config.json
_config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")
with open(_config_path) as f:
    _config = json.load(f)
_chars_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "characters")
_character = CharacterLoader(_chars_dir, _config.get("character", "mario"))
```

Pass `_character` to the display constructor.

- [ ] **Step 2: Update mario_display.py to accept character**

Modify `MarioDisplay.__init__()` to accept a `character` parameter. Since `SPRITE_DIR` and `AI_POSES_DIR` are module-level constants (line 53, 56) used throughout the module, override them at the **module level** before constructing MarioDisplay:
```python
# In client/main.py, BEFORE constructing MarioDisplay:
import client.mario_display as mario_display_module
if _character:
    mario_display_module.SPRITE_DIR = _character.sprite_dir
    mario_display_module.AI_POSES_DIR = _character.ai_poses_dir
    # Update the module-level sprite maps too
    if _character.emotion_sprite_map:
        mario_display_module.EMOTION_SPRITE_MAP = _character.emotion_sprite_map
    if _character.state_sprite_map:
        mario_display_module.STATE_SPRITE_MAP = _character.state_sprite_map
```

Then also pass `character` to `MarioDisplay.__init__()` for any instance-level config (theme colors, particle colors, window title, ai_pose_size):
```python
def __init__(self, ..., character=None):
    self._character = character
    if character:
        self._theme_colors = character.theme_colors
        self._particle_colors = character.particle_colors
        self._ai_pose_size = character.ai_pose_size
```

- [ ] **Step 3: Wire window title from character**

Replace hardcoded `pygame.display.set_caption("Mario AI 🍄")` with:
```python
pygame.display.set_caption(character.display_name if character else "Mario AI 🍄")
```

- [ ] **Step 4: Wire theme colors from character**

Replace hardcoded color constants with character theme colors where used in UI drawing code.

- [ ] **Step 5: Launch Pygame on Desktop 2 and verify visually**

Start client, verify:
- Window title shows character name
- Sprites load correctly
- Theme colors apply
- All existing functionality works

- [ ] **Step 6: Commit**

```bash
git add client/main.py client/mario_display.py
git commit -m "feat: wire client display to load character from CharacterLoader"
```

---

## Task 14: End-to-End Verification

**Files:**
- No new files — testing only

- [ ] **Step 1: Run all existing tests**

Run: `pytest tests/ -v --timeout=30`
Expected: All tests pass (no regressions)

- [ ] **Step 2: Start server with character system**

Verify server logs show:
- "Character loaded: Mario (Mario AI 🍄)"
- TTS engine uses character voice config
- Catchphrase bank loads from character directory
- Game pools loaded from YAML

- [ ] **Step 3: Start client on Desktop 2**

Verify:
- Window title: "Mario AI 🍄"
- Sprites load from character directory
- All F-key shortcuts still work
- Health overlay shows correct data

- [ ] **Step 4: Test conversation**

Send messages and verify:
- System prompt uses character persona
- Pronunciation fixes work (wahoo, mama mia)
- Emotions trigger correct sprites
- Games work with character-specific pools

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: modular character system complete — Mario loaded from character directory"
```

---

## Task 15: Create Test Character to Validate Modularity

**Files:**
- Create: `characters/test_bot/character.yaml`
- Create: `characters/test_bot/prompts/system_prompt.md`

- [ ] **Step 1: Create minimal test character**

Create `characters/test_bot/character.yaml` with different identity, colors, and voice settings to prove the system is truly modular.

- [ ] **Step 2: Switch config.json to test_bot**

Change `"character": "test_bot"` in config.json.

- [ ] **Step 3: Start server + client and verify different character loads**

Verify window title, system prompt, colors all differ from Mario.

- [ ] **Step 4: Switch back to Mario**

Change `"character": "mario"` in config.json. Verify Mario works again.

- [ ] **Step 5: Tag, commit, and push**

```bash
git add characters/test_bot/
git commit -m "feat: add test_bot character to validate modular system"
git tag -a v2.0-modular-characters -m "Modular character system — characters loaded from YAML config"
git push origin master --tags
```
