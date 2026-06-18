import json

from client.debug_server import route


class FakeProvider:
    def __init__(self):
        self.injected = None

    def debug_state(self):
        return {"state": "TALKING", "emotion": "happy"}

    def audio_log_snapshot(self, n=10):
        return [{"text": "hi", "played_ok": True}]

    def log_snapshot(self, n=200, grep="", level="DEBUG"):
        return [{"msg": "x", "level": "INFO"}]

    def latest_frame_png(self):
        return b"\x89PNG\r\n\x1a\n_fake_"

    def inject_frame_b64(self, b64):
        self.injected = b64
        return {"people": 1, "faces": 1}


def test_state_route_returns_json():
    status, ctype, body = route("GET", "/state", {}, b"", FakeProvider())
    assert status == 200 and ctype == "application/json"
    assert json.loads(body)["emotion"] == "happy"


def test_frame_route_returns_png_bytes():
    status, ctype, body = route("GET", "/frame.png", {}, b"", FakeProvider())
    assert status == 200 and ctype == "image/png" and body.startswith(b"\x89PNG")


def test_frame_route_503_when_no_frame():
    class P(FakeProvider):
        def latest_frame_png(self):
            return None
    status, _, _ = route("GET", "/frame.png", {}, b"", P())
    assert status == 503


def test_inject_frame_passes_b64():
    p = FakeProvider()
    body = json.dumps({"image_b64": "QUJD"}).encode()
    status, _, resp = route("POST", "/inject_frame", {}, body, p)
    assert status == 200 and p.injected == "QUJD"


def test_audio_route_returns_clips():
    status, _, body = route("GET", "/audio", {"n": ["5"]}, b"", FakeProvider())
    assert json.loads(body)["clips"][0]["text"] == "hi"


def test_unknown_route_404():
    status, _, _ = route("GET", "/nope", {}, b"", FakeProvider())
    assert status == 404
