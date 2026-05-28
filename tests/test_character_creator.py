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
from character_creator.sprite_generator import get_all_poses, EMOTION_SPRITES, SPECIAL_EMOTIONS, STATE_SPRITES

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
