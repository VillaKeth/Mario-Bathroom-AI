"""Light endpoint tests for the voice fine-tune routes added to the wizard server.

Uses FastAPI TestClient so no real network or hardware is needed — all
heavy calls (voice_finetune, voice_finder) are monkeypatched.

Guard: if the server module itself cannot be imported (side-effect imports like
pygame, edge_tts not present), the whole module is skipped gracefully so it
never breaks the CI that only has the base venv.
"""
import os
import sys
import pytest

# ---------------------------------------------------------------------------
# Import guard — skip the whole module if server can't be imported cleanly.
# ---------------------------------------------------------------------------
try:
    from character_creator import server as _srv
    from fastapi.testclient import TestClient
    _CLIENT = TestClient(_srv.app)
    _SKIP = False
except Exception as _e:
    _SKIP = True
    _SKIP_REASON = str(_e)


pytestmark = pytest.mark.skipif(_SKIP, reason=_SKIP_REASON if _SKIP else "")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _patch_can_finetune(monkeypatch, ok=True):
    """Monkeypatch voice_finetune.can_finetune in the module already imported by server."""
    import character_creator.voice_finetune as vf
    monkeypatch.setattr(vf, "_gpu_vram_gb", lambda: 6.0 if ok else 0.0)
    monkeypatch.setattr(vf, "_sovits_installed", lambda: True)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_can_finetune_200_with_ok_key(monkeypatch):
    """GET /api/voice/can_finetune must return 200 and include an 'ok' key."""
    _patch_can_finetune(monkeypatch, ok=True)
    resp = _CLIENT.get("/api/voice/can_finetune")
    assert resp.status_code == 200
    data = resp.json()
    assert "ok" in data
    assert data["ok"] is True


def test_can_finetune_false_without_gpu(monkeypatch):
    """can_finetune returns ok=False when no CUDA GPU is detected."""
    _patch_can_finetune(monkeypatch, ok=False)
    resp = _CLIENT.get("/api/voice/can_finetune")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is False


def test_download_full_for_edit_missing_params():
    """POST /api/voice/download_full_for_edit with empty body returns error."""
    resp = _CLIENT.post("/api/voice/download_full_for_edit", json={})
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("success") is False
    assert "error" in data


def test_download_full_for_edit_ytdlp_unavailable(monkeypatch):
    """Returns error when yt-dlp is not installed."""
    import character_creator.voice_finder as vf
    monkeypatch.setattr(vf, "is_available", lambda: False)
    resp = _CLIENT.post("/api/voice/download_full_for_edit",
                        json={"url": "https://youtube.com/watch?v=abc", "character_name": "test"})
    assert resp.status_code == 200
    assert resp.json().get("success") is False


def test_download_full_for_edit_success(monkeypatch, tmp_path):
    """Happy-path: download_full succeeds, returns edit_id and url."""
    import character_creator.voice_finder as vf

    fake_wav = str(tmp_path / "fake.wav")
    # Write a tiny file so the serve route could read it
    with open(fake_wav, "wb") as f:
        f.write(b"\x00" * 100)

    monkeypatch.setattr(vf, "is_available", lambda: True)
    monkeypatch.setattr(vf, "download_full", lambda url, out_path: fake_wav)

    resp = _CLIENT.post("/api/voice/download_full_for_edit",
                        json={"url": "https://youtube.com/watch?v=abc",
                              "character_name": "sparkle_hsr"})
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("success") is True
    assert "edit_id" in data
    assert data["url"].startswith("/api/voice/edit_cache/")


def test_edit_cache_serve_after_download(monkeypatch, tmp_path):
    """After a successful download_full_for_edit, the edit_id is serveable."""
    import character_creator.voice_finder as vf

    fake_wav = str(tmp_path / "serve_test.wav")
    with open(fake_wav, "wb") as f:
        f.write(b"RIFF" + b"\x00" * 40)  # minimal valid-looking bytes

    monkeypatch.setattr(vf, "is_available", lambda: True)
    monkeypatch.setattr(vf, "download_full", lambda url, out_path: fake_wav)

    # First download to get an edit_id
    post_resp = _CLIENT.post("/api/voice/download_full_for_edit",
                             json={"url": "https://youtube.com/watch?v=xyz",
                                   "character_name": "test_char"})
    assert post_resp.json().get("success") is True
    edit_url = post_resp.json()["url"]

    # Now serve it
    get_resp = _CLIENT.get(edit_url)
    assert get_resp.status_code == 200
    assert get_resp.headers["content-type"].startswith("audio/wav")


def test_edit_cache_serve_unknown_id():
    """Serving an unknown edit_id returns 404."""
    resp = _CLIENT.get("/api/voice/edit_cache/nonexistent-id")
    assert resp.status_code == 404


def test_build_dataset_missing_params():
    """POST /api/voice/build_dataset with empty body returns error."""
    resp = _CLIENT.post("/api/voice/build_dataset", json={})
    assert resp.status_code == 200
    assert resp.json().get("success") is False


def test_build_dataset_success(monkeypatch, tmp_path):
    """build_dataset resolves edit_id from cache and calls build_dataset_from_picks."""
    import character_creator.voice_finder as vf
    import character_creator.voice_finetune as finetune_mod

    # Inject a known edit_id into the server's _edit_cache
    fake_wav = str(tmp_path / "edit_audio.wav")
    with open(fake_wav, "wb") as f:
        f.write(b"\x00" * 200)

    edit_id = "testid000001"
    _srv._edit_cache[edit_id] = {"path": fake_wav, "char": "test_char"}

    # Monkeypatch build_dataset_from_picks to return a fixed count
    monkeypatch.setattr(finetune_mod, "build_dataset_from_picks",
                        lambda char, picks, char_root=None: 5)

    resp = _CLIENT.post("/api/voice/build_dataset", json={
        "char": "test_char",
        "picks": [{"edit_id": edit_id, "regions": [{"start": 0.0, "end": 2.0}]}],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("success") is True
    assert data["segments"] == 5
    assert "seconds" in data


def test_train_missing_char():
    """POST /api/voice/train with no char returns error."""
    resp = _CLIENT.post("/api/voice/train", json={})
    assert resp.status_code == 200
    assert resp.json().get("success") is False


def test_train_success(monkeypatch, tmp_path):
    """POST /api/voice/train calls start_training and returns its dict."""
    import character_creator.voice_finetune as finetune_mod
    monkeypatch.setattr(finetune_mod, "start_training",
                        lambda char, char_root=None: {
                            "started": True, "log": "/tmp/finetune.log",
                            "already_running": False})
    resp = _CLIENT.post("/api/voice/train", json={"char": "sparkle_hsr"})
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("success") is True
    assert data["started"] is True


def test_train_status_missing_char():
    """GET /api/voice/train_status without char= returns error."""
    resp = _CLIENT.get("/api/voice/train_status")
    assert resp.status_code == 200
    assert resp.json().get("success") is False


def test_train_status_success(monkeypatch):
    """GET /api/voice/train_status?char= calls training_status."""
    import character_creator.voice_finetune as finetune_mod
    monkeypatch.setattr(finetune_mod, "training_status",
                        lambda char, char_root=None: {
                            "stage": "s2", "epoch": 3, "total": 12,
                            "pct": 25, "done": False,
                            "log": "/tmp/finetune.log"})
    resp = _CLIENT.get("/api/voice/train_status?char=sparkle_hsr")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("success") is True
    assert data["stage"] == "s2"
    assert data["done"] is False
