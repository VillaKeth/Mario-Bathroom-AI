import sys
import os
import json
import wave
import struct
import importlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))


def _tiny_wav(path):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(struct.pack("<800h", *([0] * 800)))  # 0.1s silence


def _write_song(d, sid="my_way", triggers=None, wav=True):
    triggers = triggers if triggers is not None else ["sing my way", "my way"]
    if wav:
        _tiny_wav(os.path.join(d, f"{sid}.wav"))
    with open(os.path.join(d, f"{sid}.json"), "w", encoding="utf-8") as f:
        json.dump({"id": sid, "title": "My Way", "triggers": triggers,
                   "wav": f"{sid}.wav",
                   "lyric_pages": ["And now, the end is near"]}, f)


def _fresh():
    import performed_songs
    importlib.reload(performed_songs)
    return performed_songs


def test_load_and_match(tmp_path):
    ps = _fresh()
    _write_song(tmp_path)
    assert ps.load_songs(str(tmp_path)) == 1
    assert ps.match("hey mario sing my way please") == "my_way"
    assert ps.match("my way") == "my_way"


def test_no_match_for_unrelated_or_too_long(tmp_path):
    ps = _fresh()
    _write_song(tmp_path)
    ps.load_songs(str(tmp_path))
    assert ps.match("what is your favorite game") is None
    # >8 words never matches even if it contains a trigger
    assert ps.match("could you possibly find it in your heart to sing my way for us") is None


def test_get_returns_bytes_and_bubble(tmp_path):
    ps = _fresh()
    _write_song(tmp_path)
    ps.load_songs(str(tmp_path))
    ps.set_character("mario", "Mario")
    song = ps.get("my_way")
    assert song["title"] == "My Way"
    assert isinstance(song["wav_bytes"], bytes) and len(song["wav_bytes"]) > 44
    assert "Mario" in song["bubble"] and "My Way" in song["bubble"]


def test_missing_wav_is_skipped(tmp_path):
    ps = _fresh()
    _write_song(tmp_path, wav=False)
    assert ps.load_songs(str(tmp_path)) == 0
    assert ps.match("my way") is None


def test_empty_or_none_dir_is_empty_pool(tmp_path):
    ps = _fresh()
    assert ps.load_songs(None) == 0
    assert ps.load_songs(str(tmp_path)) == 0   # empty dir
    assert ps.match("my way") is None


def test_non_mario_bubble_uses_display_name(tmp_path):
    ps = _fresh()
    _write_song(tmp_path)
    ps.load_songs(str(tmp_path))
    ps.set_character("rudi", "Rudi")
    assert "Rudi" in ps.get("my_way")["bubble"]
