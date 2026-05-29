import importlib.util
import json
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pygame
import pytest

ROOT = Path(__file__).resolve().parents[1]
CLIENT_DIR = ROOT / "client"
for path in (ROOT, CLIENT_DIR):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

from client.mario_display import MarioDisplay


@pytest.fixture(scope="module", autouse=True)
def init_pygame():
    pygame.init()
    yield
    pygame.quit()


class DummyClock:
    def tick(self, _fps):
        return None


class DummyDisplay:
    def __init__(self):
        self.subtitle = None
        self.mario_text = None
        self.thinking_calls = []
        self.health_updates = []

    def set_subtitle(self, text):
        self.subtitle = text

    def set_mario_text(self, text):
        self.mario_text = text

    def set_thinking(self, value):
        self.thinking_calls.append(value)

    def update_health(self, data):
        self.health_updates.append(data)


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def read(self):
        return json.dumps(self._payload).encode("utf-8")


class StubClass:
    def __init__(self, *_args, **_kwargs):
        pass


@pytest.fixture
def display():
    mario_display = MarioDisplay()
    mario_display._running = True
    mario_display._clock = DummyClock()
    mario_display._draw = lambda: None
    mario_display._update_typewriter = lambda: None
    mario_display._update_transition = lambda: None
    return mario_display


@pytest.mark.parametrize(
    ("key", "prompt"),
    [
        (pygame.K_1, "Let's play Trivia!"),
        (pygame.K_2, "Let's play Rock Paper Scissors!"),
        (pygame.K_3, "Truth or Dare!"),
        (pygame.K_4, "Let's play Simon Says!"),
        (pygame.K_5, "Let's play 20 Questions!"),
        (pygame.K_6, "Tell me a joke!"),
        (pygame.K_7, "Sing me a song!"),
        (pygame.K_8, "Let's dance!"),
    ],
)
def test_number_keys_trigger_game_prompts_outside_keyboard_mode(display, monkeypatch, key, prompt):
    submitted = []
    display.on_keyboard_submit = submitted.append
    monkeypatch.setattr(
        pygame.event,
        "get",
        lambda: [pygame.event.Event(pygame.KEYDOWN, key=key, unicode=str(key))],
    )

    assert display.update() is True

    assert submitted == [prompt]
    entry = display._chat_history[-1]
    assert entry["role"] == "user"
    assert entry["text"] == prompt
    assert display.subtitle_text == f"🎮 {prompt}"


def test_number_keys_stay_as_text_in_keyboard_mode(display, monkeypatch):
    display.keyboard_mode = True
    submitted = []
    display.on_keyboard_submit = submitted.append
    monkeypatch.setattr(
        pygame.event,
        "get",
        lambda: [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_1, unicode="1")],
    )

    assert display.update() is True

    assert submitted == []
    assert display._keyboard_text == "1"


def test_f4_toggles_health_overlay(display, monkeypatch):
    events = iter(
        [
            [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_F4, unicode="")],
            [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_F4, unicode="")],
        ]
    )
    monkeypatch.setattr(pygame.event, "get", lambda: next(events))

    assert display.update() is True
    assert display._health_visible is True
    assert display.update() is True
    assert display._health_visible is False


def test_update_health_caches_overlay_data(display):
    data = {"status": "ok", "tts_engine": "edge"}

    display.update_health(data)

    assert display._health_data == data


def load_client_main(monkeypatch):
    module_name = "client_main_for_tests"
    sys.modules.pop(module_name, None)

    stub_modules = {
        "audio_capture": types.ModuleType("audio_capture"),
        "audio_playback": types.ModuleType("audio_playback"),
        "presence": types.ModuleType("presence"),
        "mario_display": types.ModuleType("mario_display"),
        "ws_client": types.ModuleType("ws_client"),
        "sound_effects": types.ModuleType("sound_effects"),
    }
    stub_modules["audio_capture"].AudioCapture = StubClass
    stub_modules["audio_playback"].AudioPlayback = StubClass
    stub_modules["presence"].PresenceDetector = StubClass
    stub_modules["mario_display"].MarioDisplay = StubClass
    stub_modules["mario_display"].STATE_IDLE = "idle"
    stub_modules["mario_display"].STATE_TALKING = "talking"
    stub_modules["mario_display"].STATE_LISTENING = "listening"
    stub_modules["mario_display"].STATE_THINKING = "thinking"
    stub_modules["mario_display"].STATE_GREETING = "greeting"
    stub_modules["mario_display"].STATE_ENTERING = "entering"
    stub_modules["mario_display"].STATE_EXITING = "exiting"
    stub_modules["ws_client"].MarioWSClient = StubClass
    stub_modules["sound_effects"].SoundEffects = StubClass

    for name, module in stub_modules.items():
        monkeypatch.setitem(sys.modules, name, module)

    spec = importlib.util.spec_from_file_location(module_name, CLIENT_DIR / "main.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def build_client(module):
    client = object.__new__(module.MarioClient)
    client.display = DummyDisplay()
    client.ws = SimpleNamespace(connected=True, server_url="ws://localhost:8765/ws", send_event=lambda event: None, send_health_ping=lambda: None)
    client._running = True
    return client


def test_keyboard_submit_routes_slash_commands_before_websocket(monkeypatch):
    module = load_client_main(monkeypatch)
    client = build_client(module)
    handled = []
    client._handle_admin_command = handled.append
    sent_events = []
    client.ws.send_event = sent_events.append

    module.MarioClient._on_keyboard_submit(client, "/pause")

    assert handled == ["/pause"]
    assert sent_events == []
    assert client.display.thinking_calls == []


def test_keyboard_submit_sends_normal_text_to_server(monkeypatch):
    module = load_client_main(monkeypatch)
    client = build_client(module)
    sent_events = []
    client.ws.send_event = sent_events.append

    module.MarioClient._on_keyboard_submit(client, "Hello Mario")

    assert client.display.subtitle == "Hello Mario"
    assert client.display.thinking_calls == [True]
    assert sent_events == [{"type": "text_input", "text": "Hello Mario"}]


def test_handle_admin_command_routes_requests_and_help(monkeypatch):
    module = load_client_main(monkeypatch)
    client = build_client(module)
    post_calls = []
    get_calls = []
    health_calls = []
    client._send_admin_post = lambda path, body=None: post_calls.append((path, body))
    client._send_admin_get = get_calls.append
    client._fetch_and_display_health = lambda: health_calls.append(True)

    module.MarioClient._handle_admin_command(client, "/announce Party time")
    assert post_calls[-1] == ("/admin/announce", {"text": "Party time"})
    assert client.display.subtitle == "📢 Announced: Party time"

    module.MarioClient._handle_admin_command(client, "/pause")
    assert get_calls[-1] == "/pause_idle"
    assert client.display.subtitle == "⏸️ Idle paused"

    module.MarioClient._handle_admin_command(client, "/help")
    assert "Commands:" in client.display.mario_text
    assert client.display.subtitle == "ℹ️ Admin commands"

    module.MarioClient._handle_admin_command(client, "/health")
    assert health_calls == [True]

    module.MarioClient._handle_admin_command(client, "/wat")
    assert client.display.subtitle == "❌ Unknown command: /wat"


def test_send_admin_post_uses_http_post(monkeypatch):
    module = load_client_main(monkeypatch)
    client = build_client(module)
    captured = {}

    def fake_urlopen(request, timeout=0):
        captured["url"] = request.full_url
        captured["method"] = request.get_method()
        captured["data"] = request.data
        captured["timeout"] = timeout
        return object()

    import urllib.request

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    module.MarioClient._send_admin_post(client, "/admin/reset")

    assert captured == {
        "url": "http://localhost:8765/admin/reset",
        "method": "POST",
        "data": b"{}",
        "timeout": 5,
    }


def test_send_admin_get_uses_http_get(monkeypatch):
    module = load_client_main(monkeypatch)
    client = build_client(module)
    captured = {}

    def fake_urlopen(url, timeout=0):
        captured["url"] = url
        captured["timeout"] = timeout
        return object()

    import urllib.request

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    module.MarioClient._send_admin_get(client, "/pause_idle")

    assert captured == {
        "url": "http://localhost:8765/pause_idle",
        "timeout": 5,
    }


def test_fetch_and_display_health_formats_overlay_text(monkeypatch):
    module = load_client_main(monkeypatch)
    client = build_client(module)
    payload = {
        "status": "ok",
        "uptime_seconds": 600,
        "tts": "edge",
        "llm": "llama",
        "tts_cache_size": 12,
        "memory_mb": 512,
    }

    import urllib.request

    monkeypatch.setattr(urllib.request, "urlopen", lambda url, timeout=0: FakeResponse(payload))

    module.MarioClient._fetch_and_display_health(client)

    assert client.display.mario_text == "Status: ok | Uptime: 600s | TTS: edge | LLM: llama | Cache: 12 entries | Memory: 512MB"
    assert client.display.subtitle == "📊 Server health"


def test_health_ping_loop_refreshes_display_health(monkeypatch):
    module = load_client_main(monkeypatch)
    client = build_client(module)
    payload = {
        "status": "ok",
        "uptime": "30m",
        "llm_model": "gemma",
        "tts_engine": "fish",
        "tts_cache_size": 7,
        "performance_tier": "high",
    }
    ping_calls = []
    url_calls = []
    client.ws.send_health_ping = lambda: ping_calls.append(True)

    def fake_sleep(_seconds):
        client._running = False

    def fake_urlopen(url, timeout=0):
        url_calls.append((url, timeout))
        return FakeResponse(payload)

    import urllib.request

    monkeypatch.setattr(module.time, "sleep", fake_sleep)
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    module.MarioClient._health_ping_loop(client)

    assert ping_calls == [True]
    assert url_calls == [("http://localhost:8765/health", 5)]
    assert client.display.health_updates == [payload]
