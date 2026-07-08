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

def test_freak_factor_parses_from_yaml(tmp_chars):
    config_path = tmp_chars / "test_char" / "character.yaml"
    config = yaml.safe_load(config_path.read_text())
    config["personality"] = {"freak_factor": 0.85}
    config_path.write_text(yaml.dump(config))
    loader = CharacterLoader(str(tmp_chars), "test_char")
    assert abs(loader.freak_factor - 0.85) < 1e-9

def test_freak_factor_defaults_zero_when_absent(tmp_chars):
    loader = CharacterLoader(str(tmp_chars), "test_char")
    assert loader.freak_factor == 0.0

def test_get_freak_prompt_zero_is_empty(tmp_chars):
    loader = CharacterLoader(str(tmp_chars), "test_char")
    assert loader.get_freak_prompt(0.0) == ""
    assert loader.get_freak_prompt(-1) == ""

def test_get_freak_prompt_escalates_and_keeps_guardrail(tmp_chars):
    config_path = tmp_chars / "test_char" / "character.yaml"
    config = yaml.safe_load(config_path.read_text())
    config["personality"] = {"freak_factor": 0.85}
    config_path.write_text(yaml.dump(config))
    loader = CharacterLoader(str(tmp_chars), "test_char")
    low, high = loader.get_freak_prompt(0.2), loader.get_freak_prompt(0.9)
    assert low and high
    assert "[FREAK]" in high
    # explicit only unlocked at high level
    assert "explicit" in high.lower()
    assert "explicit" not in low.lower()
    # guardrail present at every non-empty tier
    for txt in (low, high):
        assert "slur" in txt.lower()
        assert "minor" in txt.lower() or "underage" in txt.lower()

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
    phase_msgs = [m for m in ctx if "warm" in m["content"].lower()]
    assert len(phase_msgs) == 1
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
    games_dir = tmp_chars / "test_char" / "games"
    games_dir.mkdir()
    (games_dir / "trivia.yaml").write_text(yaml.dump([{"question": "Char?", "answer": "Yes"}]))
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

def test_speech_config(tmp_chars):
    config_path = tmp_chars / "test_char" / "character.yaml"
    config = yaml.safe_load(config_path.read_text())
    config["speech"] = {
        "accent_markers": ["Italian accent", "Adds -a to words"],
        "catchphrase_dir": "catchphrases/",
    }
    config_path.write_text(yaml.dump(config))
    loader = CharacterLoader(str(tmp_chars), "test_char")
    assert len(loader.accent_markers) == 2
    assert "Italian" in loader.accent_markers[0]

def test_speech_defaults(tmp_chars):
    loader = CharacterLoader(str(tmp_chars), "test_char")
    assert loader.accent_markers == []

def test_memory_config(tmp_chars):
    config_path = tmp_chars / "test_char" / "character.yaml"
    config = yaml.safe_load(config_path.read_text())
    config["memory"] = {
        "collections": {
            "faces": "test_faces",
            "voices": "test_voices",
            "memories": "test_memories",
        },
        "vip_profiles_dir": "memories/vip/",
        "lore_file": "memories/lore.yaml",
    }
    config_path.write_text(yaml.dump(config))
    loader = CharacterLoader(str(tmp_chars), "test_char")
    assert loader.collections["faces"] == "test_faces"
    assert loader.collections["voices"] == "test_voices"

def test_memory_defaults(tmp_chars):
    loader = CharacterLoader(str(tmp_chars), "test_char")
    assert loader.collections["faces"] == "testbot_faces"
    assert loader.collections["voices"] == "testbot_voices"
    assert loader.collections["memories"] == "testbot_memories"


# ---- Wardrobe / outfit system -------------------------------------------

def _write_visuals(tmp_chars, visuals):
    config_path = tmp_chars / "test_char" / "character.yaml"
    config = yaml.safe_load(config_path.read_text())
    config["visuals"] = visuals
    config_path.write_text(yaml.dump(config))


def test_outfits_parsed(tmp_chars):
    _write_visuals(tmp_chars, {
        "ai_poses_dir": "sprites/",
        "outfits": {
            "tuxedo": {"dir": "outfits/tuxedo/", "display": "Black Tie",
                       "fallback": "neutral/idle"},
        },
    })
    loader = CharacterLoader(str(tmp_chars), "test_char")
    assert "tuxedo" in loader.outfits
    assert loader.outfits["tuxedo"]["display"] == "Black Tie"
    assert loader.has_outfit("tuxedo") is True
    # Resolved poses dir points at the outfit subtree under the character dir.
    d = loader.outfit_poses_dir("tuxedo").replace("\\", "/")
    assert d.endswith("test_char/outfits/tuxedo")
    assert loader.outfit_fallback("tuxedo") == "neutral/idle"


def test_active_outfit_parsed(tmp_chars):
    _write_visuals(tmp_chars, {
        "ai_poses_dir": "sprites/",
        "active_outfit": "tuxedo",
        "outfits": {"tuxedo": {"dir": "outfits/tuxedo/"}},
    })
    loader = CharacterLoader(str(tmp_chars), "test_char")
    assert loader.active_outfit == "tuxedo"


def test_outfits_default_when_absent(tmp_chars):
    loader = CharacterLoader(str(tmp_chars), "test_char")
    assert loader.outfits == {}
    assert loader.active_outfit is None
    assert loader.has_outfit("tuxedo") is False
    # No/None/"default" outfit resolves to the default sprite tree.
    assert loader.outfit_poses_dir(None) == loader.ai_poses_dir
    assert loader.outfit_poses_dir("default") == loader.ai_poses_dir


def test_unknown_outfit_resolves_to_default(tmp_chars):
    _write_visuals(tmp_chars, {
        "ai_poses_dir": "sprites/",
        "outfits": {"tuxedo": {"dir": "outfits/tuxedo/"}},
    })
    loader = CharacterLoader(str(tmp_chars), "test_char")
    # An unknown outfit name never crashes — it falls back to the default tree.
    assert loader.outfit_poses_dir("clown_suit") == loader.ai_poses_dir


def test_outfit_fallback_defaults_to_neutral_idle(tmp_chars):
    _write_visuals(tmp_chars, {
        "ai_poses_dir": "sprites/",
        # No explicit fallback on the outfit, no fallback_sprites block.
        "outfits": {"tuxedo": {"dir": "outfits/tuxedo/"}},
    })
    loader = CharacterLoader(str(tmp_chars), "test_char")
    assert loader.outfit_fallback("tuxedo") == "neutral/idle"


def test_outfit_fallback_uses_character_fallback_sprites(tmp_chars):
    _write_visuals(tmp_chars, {
        "ai_poses_dir": "sprites/",
        "fallback_sprites": {"state": "neutral/rest", "emotion": "neutral/rest"},
        "outfits": {"tuxedo": {"dir": "outfits/tuxedo/"}},
    })
    loader = CharacterLoader(str(tmp_chars), "test_char")
    # With no per-outfit fallback, defer to the character's own fallback pose.
    assert loader.outfit_fallback("tuxedo") == "neutral/rest"
