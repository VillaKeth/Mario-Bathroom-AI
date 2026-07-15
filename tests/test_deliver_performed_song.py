import sys
import os
import io
import asyncio
import importlib
import wave
import struct

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))


def _tiny_wav_bytes(seconds=1.0, rate=8000):
    b = io.BytesIO()
    with wave.open(b, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(struct.pack(f"<{int(rate*seconds)}h", *([0] * int(rate * seconds))))
    return b.getvalue()


class FakeWS:
    def __init__(self):
        self.jsons = []
        self.blobs = []

    async def send_json(self, m):
        self.jsons.append(m)

    async def send_bytes(self, b):
        self.blobs.append(b)


def test_deliver_sets_guard_and_sends(monkeypatch):
    import performed_songs
    importlib.reload(performed_songs)
    import main

    wavb = _tiny_wav_bytes()
    monkeypatch.setattr(main.performed_songs, "get", lambda sid: {
        "id": sid, "title": "My Way", "lyric_pages": [],
        "bubble": "🎤 Mario sings My Way ♪", "wav_bytes": wavb})
    main.state_current["_performing_song_until"] = 0.0

    ws = FakeWS()
    asyncio.run(main._deliver_performed_song(ws, "my_way"))

    # bubble json + audio bytes both went out
    assert any(j.get("type") == "mario_response" for j in ws.jsons)
    assert ws.blobs and ws.blobs[0] == wavb
    # bubble text is the song bubble
    resp = [j for j in ws.jsons if j.get("type") == "mario_response"][0]
    assert "My Way" in resp["text"]
    # guard set into the future (song is ~1s + tail)
    assert main.state_current["_performing_song_until"] > main.time.time()


def test_deliver_unknown_song_is_noop(monkeypatch):
    import main
    monkeypatch.setattr(main.performed_songs, "get", lambda sid: None)
    main.state_current["_performing_song_until"] = 0.0
    ws = FakeWS()
    asyncio.run(main._deliver_performed_song(ws, "nope"))
    assert ws.jsons == [] and ws.blobs == []
    assert main.state_current["_performing_song_until"] == 0.0
