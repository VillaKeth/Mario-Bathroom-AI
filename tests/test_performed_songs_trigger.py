import sys
import os
import json
import wave
import struct
import types
import importlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))


def _tiny_wav(path):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(struct.pack("<800h", *([0] * 800)))


def _load_registry(tmp_path):
    import performed_songs
    importlib.reload(performed_songs)
    _tiny_wav(os.path.join(tmp_path, "my_way.wav"))
    with open(os.path.join(tmp_path, "my_way.json"), "w", encoding="utf-8") as f:
        json.dump({"id": "my_way", "title": "My Way",
                   "triggers": ["sing my way", "my way"], "wav": "my_way.wav"}, f)
    performed_songs.load_songs(str(tmp_path))
    return performed_songs


def _base_state(**over):
    state = {
        "_last_command_time": 0, "_active_game": None, "_game_state": {},
        "speaker_id": None, "speaker_name": None, "_detected_mood": None,
        "_performing_song_until": 0.0,
    }
    state.update(over)
    return state


def test_trigger_returns_sentinel(tmp_path):
    ps = _load_registry(tmp_path)
    import command_handlers
    importlib.reload(command_handlers)
    command_handlers.performed_songs = ps

    out = command_handlers._handle_special_commands_impl(
        "sing my way", _base_state(), {"command_cooldown": 0},
        types.SimpleNamespace(current=None), None, None, None)
    assert out == "__PERFORMED_SONG__:my_way"


def test_unrelated_does_not_trigger_song(tmp_path):
    ps = _load_registry(tmp_path)
    import command_handlers
    importlib.reload(command_handlers)
    command_handlers.performed_songs = ps

    out = command_handlers._handle_special_commands_impl(
        "what is the capital of france", _base_state(), {"command_cooldown": 0},
        types.SimpleNamespace(current=None), None, None, None)
    assert out != "__PERFORMED_SONG__:my_way"


def test_stop_during_song_returns_stop_sentinel(tmp_path):
    ps = _load_registry(tmp_path)
    import command_handlers
    importlib.reload(command_handlers)
    command_handlers.performed_songs = ps

    out = command_handlers._handle_special_commands_impl(
        "stop", _base_state(_performing_song_until=9e18), {"command_cooldown": 0},
        types.SimpleNamespace(current=None), None, None, None)
    assert out == "__STOP_SONG__"
