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
