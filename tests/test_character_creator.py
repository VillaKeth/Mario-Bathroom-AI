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
