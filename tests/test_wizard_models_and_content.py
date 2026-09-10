"""Endpoint tests for the wizard's model detection and content-generation guard.

Covers two failures that let the wizard hand back a broken character:

* /api/models reported a model as installed when only a sibling of the same
  family was pulled, so picking it produced a character pointing at weights
  that were never downloaded.
* /api/content/generate answered an invalid character directory with a JSON
  body while the client was reading the response as an SSE stream, so the
  progress panel hung on "Waiting..." with no error surfaced.

Guard: skip the module if the server can't be imported cleanly, matching
test_wizard_voice_endpoints.py — CI only has the base venv.
"""
import json

import pytest

try:
    from character_creator import server as _srv
    from fastapi.testclient import TestClient
    _CLIENT = TestClient(_srv.app)
    _SKIP = False
except Exception as _e:  # pragma: no cover - import guard
    _SKIP = True
    _SKIP_REASON = str(_e)

pytestmark = pytest.mark.skipif(_SKIP, reason=_SKIP_REASON if _SKIP else "")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


class _FakeAsyncClient:
    """Stands in for httpx.AsyncClient as an async context manager."""

    payload = {"models": []}
    status_code = 200
    raise_on_get = False

    def __init__(self, *a, **kw):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def get(self, url, *a, **kw):
        if type(self).raise_on_get:
            raise RuntimeError("connection refused")
        return _FakeResponse(type(self).payload, type(self).status_code)


def _patch_ollama(monkeypatch, models, status_code=200, unreachable=False):
    _FakeAsyncClient.payload = {"models": models}
    _FakeAsyncClient.status_code = status_code
    _FakeAsyncClient.raise_on_get = unreachable
    monkeypatch.setattr(_srv.httpx, "AsyncClient", _FakeAsyncClient)


def _patch_hardware(monkeypatch, vram_gb=4, ram_gb=32):
    monkeypatch.setattr(
        _srv.hardware,
        "detect_hardware",
        lambda: {
            "cpu_cores": 24,
            "ram_gb": ram_gb,
            "gpu_vram_gb": vram_gb,
            "gpu_name": "Test GPU",
        },
    )


def _by_name(models):
    return {m["name"]: m for m in models}


# ---------------------------------------------------------------------------
# /api/models — install detection
# ---------------------------------------------------------------------------

def test_sibling_model_is_not_reported_installed(monkeypatch):
    """gemma3:4b being pulled must not mark gemma3:27b as installed."""
    _patch_hardware(monkeypatch)
    _patch_ollama(monkeypatch, [{"name": "gemma3:4b", "size": 3_338_801_804}])

    models = _by_name(_CLIENT.get("/api/models").json()["models"])

    assert models["gemma3:4b"]["installed"] is True
    assert models["gemma3:27b"]["installed"] is False
    assert models["gemma3:12b"]["installed"] is False


def test_family_prefix_does_not_leak_across_models(monkeypatch):
    """llama3.2:3b must not mark llama3.1:70b installed via prefix overlap."""
    _patch_hardware(monkeypatch)
    _patch_ollama(monkeypatch, [{"name": "llama3.2:3b", "size": 2_019_393_189}])

    models = _by_name(_CLIENT.get("/api/models").json()["models"])

    assert models["llama3.2:3b"]["installed"] is True
    assert models["llama3.1:70b"]["installed"] is False
    assert models["llama3.1:8b"]["installed"] is False


def test_bare_catalog_name_matches_latest_tag(monkeypatch):
    """Ollama's 'llama3:latest' is the catalog's bare 'llama3'."""
    _patch_hardware(monkeypatch)
    _patch_ollama(monkeypatch, [{"name": "llama3:latest", "size": 4_661_224_676}])

    data = _CLIENT.get("/api/models").json()
    names = [m["name"] for m in data["models"]]

    # Listed once, under the name Ollama actually reports.
    assert "llama3:latest" in names
    assert names.count("llama3:latest") == 1
    assert "llama3" not in names
    assert _by_name(data["models"])["llama3:latest"]["installed"] is True


def test_installed_models_outside_catalog_are_listed(monkeypatch):
    """A pulled model our VRAM catalog never heard of must still be selectable."""
    _patch_hardware(monkeypatch)
    _patch_ollama(monkeypatch, [
        {"name": "hermes3:8b", "size": 4_661_227_243},
        {"name": "goekdenizguelmez/JOSIEFIED-Qwen3:8b", "size": 5_027_787_856},
    ])

    models = _by_name(_CLIENT.get("/api/models").json()["models"])

    assert models["hermes3:8b"]["installed"] is True
    assert models["goekdenizguelmez/JOSIEFIED-Qwen3:8b"]["installed"] is True
    # VRAM estimated from on-disk size rather than defaulting to zero.
    assert models["hermes3:8b"]["vram_gb"] >= 4


def test_recommendation_prefers_an_installed_model(monkeypatch):
    """Recommending a model the user hasn't pulled sends them into a dead end."""
    _patch_hardware(monkeypatch, vram_gb=8)
    _patch_ollama(monkeypatch, [{"name": "llama3.2:3b", "size": 2_019_393_189}])

    models = _CLIENT.get("/api/models").json()["models"]
    recommended = [m for m in models if m["recommended"]]

    assert len(recommended) == 1
    assert recommended[0]["installed"] is True


def test_ollama_down_reports_nothing_installed(monkeypatch):
    _patch_hardware(monkeypatch)
    _patch_ollama(monkeypatch, [], unreachable=True)

    data = _CLIENT.get("/api/models").json()

    assert data["ollama_running"] is False
    assert data["installed_models"] == []
    assert all(m["installed"] is False for m in data["models"])
    # The catalog still renders so the user can see what's worth pulling.
    assert len(data["models"]) > 0


def test_ollama_up_sets_running_flag(monkeypatch):
    _patch_hardware(monkeypatch)
    _patch_ollama(monkeypatch, [{"name": "gemma3:4b", "size": 3_338_801_804}])

    data = _CLIENT.get("/api/models").json()

    assert data["ollama_running"] is True
    assert data["installed_models"] == ["gemma3:4b"]


# ---------------------------------------------------------------------------
# /api/content/generate — the guard must speak SSE
# ---------------------------------------------------------------------------

def _sse_events(text):
    events = []
    for chunk in text.split("\n\n"):
        chunk = chunk.strip()
        if chunk.startswith("data: "):
            events.append(json.loads(chunk[6:]))
    return events


def test_missing_char_dir_streams_an_error_event():
    """A JSON body here would hang the client's SSE reader forever."""
    resp = _CLIENT.post("/api/content/generate", json={
        "character_name": "wiztest",
        "description": "d",
        "personality": "p",
        "char_dir": None,
        "categories": ["idle"],
    })

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")

    events = _sse_events(resp.text)
    assert len(events) == 1
    assert events[0]["type"] == "error"
    assert events[0]["error"]


def test_nonexistent_char_dir_streams_an_error_event(tmp_path):
    missing = str(tmp_path / "does_not_exist")
    resp = _CLIENT.post("/api/content/generate", json={
        "character_name": "wiztest",
        "description": "d",
        "personality": "p",
        "char_dir": missing,
        "categories": ["idle"],
    })

    assert resp.headers["content-type"].startswith("text/event-stream")
    events = _sse_events(resp.text)
    assert events[0]["type"] == "error"


# ---------------------------------------------------------------------------
# Auto voice pull — must not hijack an original character's chosen voice
# ---------------------------------------------------------------------------

def _run_prepare(monkeypatch, tmp_path, config):
    """Call prepare_voice_artifacts, recording any YouTube search it attempts."""
    from character_creator import voice_trainer, voice_finder

    searches = []

    def _fake_search(query, max_results=6):
        searches.append(query)
        return []

    monkeypatch.setattr(voice_finder, "is_available", lambda: True)
    monkeypatch.setattr(voice_finder, "search", _fake_search)
    monkeypatch.setattr(voice_finder, "download_clip", lambda *a, **kw: None)

    char_dir = tmp_path / config.get("name", "c")
    (char_dir / "voice").mkdir(parents=True, exist_ok=True)

    voice_trainer.prepare_voice_artifacts(config, str(char_dir))
    return searches


def test_original_character_does_not_pull_a_youtube_voice(monkeypatch, tmp_path):
    """An original character has no voice lines — searching finds a stranger."""
    searches = _run_prepare(monkeypatch, tmp_path, {
        "name": "wiztest",
        "char_type": "original",
        "preferred_engine": "edge",
        "edge_voice": "en-US-GuyNeural",
    })

    assert searches == []


def test_known_character_still_pulls_a_youtube_voice(monkeypatch, tmp_path):
    """The zero-effort path for famous characters must keep working."""
    searches = _run_prepare(monkeypatch, tmp_path, {
        "name": "Goku",
        "char_type": "known",
        "preferred_engine": "edge",
    })

    assert len(searches) == 1
    assert "Goku" in searches[0]


def test_explicit_auto_voice_overrides_the_char_type_default(monkeypatch, tmp_path):
    searches = _run_prepare(monkeypatch, tmp_path, {
        "name": "wiztest",
        "char_type": "original",
        "auto_voice": True,
        "preferred_engine": "edge",
    })

    assert len(searches) == 1


def test_auto_voice_false_disables_pull_for_known_character(monkeypatch, tmp_path):
    searches = _run_prepare(monkeypatch, tmp_path, {
        "name": "Goku",
        "char_type": "known",
        "auto_voice": False,
        "preferred_engine": "edge",
    })

    assert searches == []


# ---------------------------------------------------------------------------
# Recommendation must not default a chat character to a vision model
# ---------------------------------------------------------------------------

def test_text_model_recommended_over_larger_vision_model(monkeypatch):
    """A vision model was winning the recommendation purely on size."""
    _patch_hardware(monkeypatch, vram_gb=8)
    _patch_ollama(monkeypatch, [
        {"name": "qwen2.5vl:3b", "size": 3_200_627_168},
        {"name": "llama3.2:3b", "size": 2_019_393_189},
    ])

    models = _CLIENT.get("/api/models").json()["models"]
    recommended = [m for m in models if m["recommended"]]

    assert len(recommended) == 1
    assert recommended[0]["vision"] is False


def test_vision_models_are_flagged_but_still_listed(monkeypatch):
    """Flagging must not remove them — the user may want one deliberately."""
    _patch_hardware(monkeypatch, vram_gb=8)
    _patch_ollama(monkeypatch, [
        {"name": "llava-llama3:latest", "size": 5_545_682_182,
         "details": {"families": ["llama", "clip"]}},
        {"name": "llama3.2:3b", "size": 2_019_393_189},
    ])

    models = _by_name(_CLIENT.get("/api/models").json()["models"])

    assert models["llava-llama3:latest"]["vision"] is True
    assert models["llava-llama3:latest"]["installed"] is True
    assert models["llama3.2:3b"]["vision"] is False


def test_vision_model_still_recommended_when_it_is_the_only_option(monkeypatch):
    _patch_hardware(monkeypatch, vram_gb=8)
    _patch_ollama(monkeypatch, [{"name": "qwen2.5vl:3b", "size": 3_200_627_168}])

    models = _CLIENT.get("/api/models").json()["models"]
    recommended = [m for m in models if m["recommended"] and m["installed"]]

    assert len(recommended) == 1
    assert recommended[0]["name"] == "qwen2.5vl:3b"


# ---------------------------------------------------------------------------
# Content generation must honour the model chosen in the Hardware step
# ---------------------------------------------------------------------------

def _backend_for(monkeypatch, tmp_path, config):
    import json as _json
    from character_creator import content_generator as cg

    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(_json.dumps(config), encoding="utf-8")
    monkeypatch.setattr(cg, "PROJECT_ROOT", str(tmp_path))
    return cg.get_llm_backend()


def test_content_backend_uses_the_selected_quality_model(monkeypatch, tmp_path):
    """Reading a top-level quality_model never matched; it always used llama3."""
    backend = _backend_for(monkeypatch, tmp_path, {
        "server": {"llm_quality_model": "hermes3:8b", "llm_model": "other:8b"},
    })

    assert backend["type"] == "ollama"
    assert backend["model"] == "hermes3:8b"


def test_content_backend_skips_the_auto_sentinel(monkeypatch, tmp_path):
    """'auto' means let the runtime decide — it is not a model name."""
    backend = _backend_for(monkeypatch, tmp_path, {
        "server": {"llm_quality_model": "auto", "llm_model": "hermes3:8b"},
    })

    assert backend["model"] == "hermes3:8b"


def test_content_backend_falls_back_when_nothing_configured(monkeypatch, tmp_path):
    backend = _backend_for(monkeypatch, tmp_path, {"server": {}})

    assert backend["model"] == "llama3"
