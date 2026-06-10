# tests/test_character_creator.py
import pytest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from fastapi.testclient import TestClient
from character_creator.server import app

def test_server_serves_index():
    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Character Creator" in resp.text

def test_health_endpoint():
    client = TestClient(app)
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert data["status"] == "ok"

def test_hardware_endpoint():
    client = TestClient(app)
    resp = client.get("/api/hardware")
    assert resp.status_code == 200
    data = resp.json()
    assert "cpu_cores" in data
    assert "ram_gb" in data
    assert "gpu_vram_gb" in data
    assert "gpu_name" in data
    assert "tier" in data
    assert data["tier"] in ("ultra", "high", "medium", "low")

# Config Manager Tests
from character_creator.config_manager import read_model_config, write_model_config
import tempfile, json

def test_read_model_config():
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg_path = os.path.join(tmpdir, "config.json")
        with open(cfg_path, "w") as f:
            json.dump({"server": {"llm_quality_model": "llama3", "llm_fast_model": "llama3"}}, f)
        result = read_model_config(cfg_path)
        assert result["quality_model"] == "llama3"
        assert result["fast_model"] == "llama3"

def test_write_model_config_preserves_other_fields():
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg_path = os.path.join(tmpdir, "config.json")
        original = {"character": "mario", "server": {"port": 8765, "llm_quality_model": "llama3", "llm_fast_model": "llama3"}, "client": {"width": 480}}
        with open(cfg_path, "w") as f:
            json.dump(original, f)
        write_model_config(cfg_path, quality_model="gemma3:12b", fast_model="llama3.2:3b")
        with open(cfg_path) as f:
            updated = json.load(f)
        assert updated["character"] == "mario"
        assert updated["server"]["port"] == 8765
        assert updated["server"]["llm_quality_model"] == "gemma3:12b"
        assert updated["server"]["llm_fast_model"] == "llama3.2:3b"
        assert updated["client"]["width"] == 480

def test_write_model_config_skips_when_unchanged():
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg_path = os.path.join(tmpdir, "config.json")
        original = {"server": {"llm_quality_model": "llama3", "llm_fast_model": "llama3"}}
        with open(cfg_path, "w") as f:
            json.dump(original, f)
        write_model_config(cfg_path, quality_model=None, fast_model="phi3:mini")
        with open(cfg_path) as f:
            updated = json.load(f)
        assert updated["server"]["llm_quality_model"] == "llama3"
        assert updated["server"]["llm_fast_model"] == "phi3:mini"

def test_models_endpoint():
    client = TestClient(app)
    resp = client.get("/api/models")
    assert resp.status_code == 200
    data = resp.json()
    assert "models" in data
    assert "detected_vram" in data
    assert isinstance(data["models"], list)
    if data["models"]:
        m = data["models"][0]
        assert "name" in m
        assert "vram_gb" in m
        assert "compatibility" in m
        assert m["compatibility"] in ("compatible", "slow", "incompatible")

# Sprite Generator Tests
from character_creator.sprite_generator import get_all_poses, EMOTION_SPRITES, SPECIAL_EMOTIONS, STATE_SPRITES, expected_sprite_count

def test_sprite_poses_structure():
    data = get_all_poses()
    assert "emotions" in data
    assert "states" in data
    assert len(data["emotions"]) >= 25
    assert len(data["states"]) >= 9
    total_state_paths = sum(len(s["paths"]) for s in data["states"])
    assert total_state_paths >= 11

def test_known_character_lookup_found():
    client = TestClient(app)
    resp = client.get("/api/known-character/goku")
    assert resp.status_code == 200
    data = resp.json()
    assert data["found"] is True
    assert data["data"]["display_name"]
    assert data["data"]["description"]
    assert data["data"]["theme_colors"]

def test_known_character_lookup_not_found():
    client = TestClient(app)
    resp = client.get("/api/known-character/xyznotreal")
    assert resp.status_code == 200
    data = resp.json()
    assert data["found"] is False

# Voice Finder Tests
from character_creator.voice_finder import is_available, search

def test_voice_finder_is_available():
    result = is_available()
    assert isinstance(result, bool)

def test_voice_finder_search_returns_list():
    results = search("test query", max_results=1)
    assert isinstance(results, list)

def test_edge_voices_endpoint():
    client = TestClient(app)
    resp = client.get("/api/voice/edge-voices")
    assert resp.status_code == 200
    data = resp.json()
    assert "voices" in data
    assert isinstance(data["voices"], list)

# Voice Trainer Tests
from character_creator.voice_trainer import detect_available_engines

def test_detect_available_engines():
    engines = detect_available_engines()
    assert isinstance(engines, list)
    engine_names = [e["name"] for e in engines]
    assert "edge" in engine_names
    for engine in engines:
        assert "name" in engine
        assert "available" in engine
        assert "vram_required" in engine
        assert "status" in engine

def test_upload_audio_endpoint():
    import struct
    client = TestClient(app)
    sample_rate = 22050
    num_samples = sample_rate
    data_size = num_samples * 2
    header = struct.pack('<4sI4s4sIHHIIHH4sI',
        b'RIFF', 36 + data_size, b'WAVE',
        b'fmt ', 16, 1, 1, sample_rate, sample_rate * 2, 2, 16,
        b'data', data_size)
    wav_bytes = header + b'\x00' * data_size
    resp = client.post(
        "/api/upload/audio",
        files={"file": ("test.wav", wav_bytes, "audio/wav")},
        data={"character_name": "test_upload"}
    )
    assert resp.status_code == 200
    data_resp = resp.json()
    assert data_resp["success"] is True
    assert "_drafts" in data_resp["path"]

def test_sprite_generation_start():
    client = TestClient(app)
    resp = client.post("/api/sprites/generate", json={
        "character_name": "test_gen",
        "visual_description": "A friendly robot with blue eyes",
        "art_style": "3d_figurine",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "task_id" in data
    assert data["status"] == "started"
    assert data["total_poses"] == expected_sprite_count()

def test_generate_all_poses_uses_client_sprite_paths(monkeypatch, tmp_path):
    import asyncio
    from character_creator import sprite_generator as sg

    calls = []

    async def fake_generate_single_pose(char_name, visual_description, art_style,
                                        pose_name, pose_prompt, output_dir,
                                        output_key=None):
        calls.append((pose_name, output_key))
        # Real generate_single_pose writes the PNG; emulate that so the
        # coverage/repair-sweep logic sees the sprite as present on disk.
        out_path = os.path.join(output_dir, f"{output_key}.png")
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "wb") as f:
            f.write(b"\x89PNG\r\n\x1a\n" + b"0" * 4096)
        return {
            "pose": pose_name,
            "status": "done",
            "path": out_path,
            "backend": "test",
        }

    monkeypatch.setattr(sg, "generate_single_pose", fake_generate_single_pose)

    asyncio.run(sg.generate_all_poses(
        "test_task", "test_gen", "A friendly robot", "3d_figurine", str(tmp_path)
    ))

    output_keys = [output_key for _, output_key in calls]
    assert "neutral/idle" in output_keys
    assert "positive/happy" in output_keys
    assert "speech/talking" in output_keys
    assert "state_idle" not in output_keys
    assert "happy" not in output_keys
    assert len(output_keys) == len(set(output_keys))
    assert sg.get_task_status("test_task")["status"] == "completed"

def test_staged_sprite_merge_replaces_placeholders(tmp_path):
    from character_creator.server import _move_staged_files

    draft_dir = tmp_path / "_drafts" / "test_bot"
    char_dir = tmp_path / "characters" / "test_bot"
    draft_sprite = draft_dir / "sprites" / "positive" / "happy.png"
    placeholder_sprite = char_dir / "sprites" / "positive" / "happy.png"

    draft_sprite.parent.mkdir(parents=True)
    placeholder_sprite.parent.mkdir(parents=True)
    draft_sprite.write_bytes(b"generated")
    placeholder_sprite.write_bytes(b"placeholder")

    _move_staged_files(str(draft_dir), str(char_dir))

    assert placeholder_sprite.read_bytes() == b"generated"
    assert not (char_dir / "sprites" / "positive" / "positive").exists()
    assert not draft_dir.exists()

# Character Builder Tests
import tempfile
import yaml
from character_creator.character_builder import build_character

def test_build_character_creates_directory():
    with tempfile.TemporaryDirectory() as tmpdir:
        config = {
            "name": "TestBot",
            "display_name": "TestBot AI 🤖",
            "tagline": "Testing!",
            "description": "A test character",
            "theme_colors": {"primary": "#FF0000", "secondary": "#00FF00", "accent": "#0000FF", "text": "#FFFFFF"},
            "edge_voice": "en-US-GuyNeural",
            "voice_rate": "+10%",
            "voice_pitch": "+0Hz",
            "accent_markers": ["Speaks normally"],
            "catchphrases": ["Hello!"],
            "pronunciation": {},
            "preferred_engine": "edge",
        }
        char_dir = build_character(config, tmpdir)
        
        assert os.path.isdir(char_dir)
        assert os.path.isfile(os.path.join(char_dir, "character.yaml"))
        assert os.path.isdir(os.path.join(char_dir, "sprites"))
        assert os.path.isdir(os.path.join(char_dir, "prompts"))
        assert os.path.isfile(os.path.join(char_dir, "prompts", "system_prompt.md"))
        
        with open(os.path.join(char_dir, "character.yaml")) as f:
            data = yaml.safe_load(f)
        assert data["identity"]["name"] == "TestBot"
        assert data["voice"]["edge_voice"] == "en-US-GuyNeural"

def test_character_loader_compatibility():
    """Verify wizard output can be loaded by the real character_loader."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = {
            "name": "TestBot",
            "display_name": "TestBot AI 🤖",
            "tagline": "Testing!",
            "description": "A test character for loader compatibility",
            "theme_colors": {"primary": "#FF0000", "secondary": "#00FF00", "accent": "#0000FF", "text": "#FFFFFF"},
            "edge_voice": "en-US-GuyNeural",
            "voice_rate": "+10%",
            "voice_pitch": "+0Hz",
            "accent_markers": ["Speaks normally"],
            "catchphrases": ["Hello!", "Testing one two three!"],
            "pronunciation": {},
            "preferred_engine": "edge",
        }
        char_dir = build_character(config, tmpdir)
        char_name = os.path.basename(char_dir)
        
        # Load using the REAL character_loader
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "shared"))
        from character_loader import CharacterLoader
        loader = CharacterLoader(tmpdir, char_name)
        
        assert loader.name == "TestBot"
        assert loader.voice_config["edge_voice"] == "en-US-GuyNeural"
        assert loader.theme_colors is not None
        assert loader.emotion_sprite_map is not None
        assert loader.state_sprite_map is not None
        
        assert os.path.isfile(os.path.join(char_dir, "prompts", "system_prompt.md"))
        assert os.path.isfile(os.path.join(char_dir, "prompts", "idle_prompt.md"))
        assert os.path.isfile(os.path.join(char_dir, "prompts", "phases.yaml"))
        assert os.path.isfile(os.path.join(char_dir, "prompts", "greetings.yaml"))
        assert os.path.isfile(os.path.join(char_dir, "prompts", "guest_type_hints.yaml"))
        assert os.path.isfile(os.path.join(char_dir, "prompts", "time_flavors.yaml"))

def test_create_character_missing_name():
    client = TestClient(app)
    resp = client.post("/api/create-character", json={"display_name": "NoName"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is False
    assert "name" in data["error"].lower()

def test_create_character_with_no_sprites_still_valid():
    """Character with zero sprites should still be loadable (uses placeholder)."""
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        config = {
            "name": "NoSprites",
            "display_name": "NoSprites AI",
            "tagline": "No images!",
            "description": "Character without any sprites",
            "theme_colors": {"primary": "#FF0000", "secondary": "#00FF00", "accent": "#0000FF", "text": "#FFFFFF"},
            "edge_voice": "en-US-GuyNeural",
            "voice_rate": "+0%", "voice_pitch": "+0Hz",
            "accent_markers": ["Normal"], "catchphrases": ["Hi!"],
            "pronunciation": {}, "preferred_engine": "edge",
        }
        char_dir = build_character(config, tmpdir)
        assert os.path.isfile(os.path.join(char_dir, "character.yaml"))

def test_hardware_endpoint_returns_gracefully_without_gpu():
    """Hardware endpoint should never crash, even if GPU detection fails."""
    client = TestClient(app)
    resp = client.get("/api/hardware")
    assert resp.status_code == 200
    data = resp.json()
    assert data["tier"] in ("ultra", "high", "medium", "low")

def test_models_endpoint_handles_ollama_offline():
    """Models endpoint should return model list even if Ollama is unreachable."""
    client = TestClient(app)
    resp = client.get("/api/models")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data["models"], list)


# ─── Offline voice pipeline ──────────────────────────────────────────────────

def test_voice_search_youtube_default(monkeypatch):
    """YouTube clip finding is the DEFAULT voice source (no coding required).

    The endpoint delegates to voice_finder; we stub it so the test never hits
    the network but still verifies wiring + response shape.
    """
    from character_creator import voice_finder
    monkeypatch.setattr(voice_finder, "is_available", lambda: True)
    monkeypatch.setattr(voice_finder, "search",
                        lambda q, max_results=6: [{"id": "x", "title": "Clip", "duration": 12,
                                                   "url": "https://youtu.be/x"}])
    client = TestClient(app)
    resp = client.post("/api/voice/search", json={"query": "Jax voice lines"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["available"] is True
    assert len(data["results"]) == 1
    assert data["results"][0]["url"] == "https://youtu.be/x"


def test_prepare_voice_artifacts_offline(monkeypatch, tmp_path):
    """prepare_voice_artifacts transcribes locally (no LLM/cloud) and records
    modular per-character voice config in character.yaml."""
    import yaml
    from character_creator import voice_trainer, voice_transcribe

    # Stub transcription so the test is fast and deterministic (no Whisper load,
    # no network) — proves the pipeline path, not Whisper itself.
    monkeypatch.setattr(voice_transcribe, "transcribe_file",
                        lambda p, model_size="base": {"text": "hello it is me",
                                                       "language": "en", "available": True, "error": None})

    char_dir = tmp_path / "testchar"
    (char_dir / "voice").mkdir(parents=True)
    # A non-trivial fake reference clip (>1KB so it's treated as real).
    (char_dir / "voice" / "reference_audio.wav").write_bytes(b"RIFF" + b"0" * 4096)
    (char_dir / "character.yaml").write_text(
        "identity:\n  name: TestChar\nvoice:\n  preferred_engine: sovits\n"
        "  edge_voice: en-US-GuyNeural\n  rate: \"+0%\"\n  pitch: \"+0Hz\"\n",
        encoding="utf-8")

    result = voice_trainer.prepare_voice_artifacts({"preferred_engine": "sovits"}, str(char_dir))

    assert result["transcription"] == "ok"
    assert result["prompt_text"] == "hello it is me"
    assert result["reference_audio"] == "voice/reference_audio.wav"
    # reference transcript persisted for offline cloning
    assert (char_dir / "voice" / "reference_text.txt").read_text(encoding="utf-8") == "hello it is me"
    # yaml carries the modular voice config the runtime reads
    data = yaml.safe_load((char_dir / "character.yaml").read_text(encoding="utf-8"))
    assert data["voice"]["prompt_text"] == "hello it is me"
    assert data["voice"]["prompt_lang"] == "en"
    assert "edge" in data["voice"]["engines"]


def test_find_missing_sprites_detects_gaps(tmp_path):
    from character_creator import sprite_generator as sg
    plan = sg._generation_pose_plan()
    # Nothing on disk yet -> everything missing.
    assert len(sg.find_missing_sprites(str(tmp_path), plan)) == len(plan)
    # Create one valid sprite file -> it drops out of the missing list.
    first = plan[0]["sprite_path"]
    p = tmp_path / f"{first}.png"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 4096)
    missing = sg.find_missing_sprites(str(tmp_path), plan)
    assert first not in [m["sprite_path"] for m in missing]
    assert len(missing) == len(plan) - 1
