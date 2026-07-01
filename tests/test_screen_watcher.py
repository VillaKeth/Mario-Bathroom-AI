# tests/test_screen_watcher.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))
import numpy as np
import screen_watcher

def test_encode_jpeg_returns_downscaled_jpeg():
    frame = np.zeros((1080, 1920, 3), dtype=np.uint8)  # fake BGR screen
    frame[:, :, 1] = 128  # some green so it's not degenerate
    out = screen_watcher._encode_jpeg(frame, width=1024, quality=70)
    assert isinstance(out, (bytes, bytearray))
    assert out[:2] == b"\xff\xd8"          # JPEG SOI magic
    assert len(out) > 100
    # decode back and check it was downscaled to width 1024
    import cv2
    dec = cv2.imdecode(np.frombuffer(out, np.uint8), cv2.IMREAD_COLOR)
    assert dec.shape[1] == 1024


import base64


def test_describe_frame_sends_image_and_keepalive(monkeypatch):
    captured = {}
    class FakeResp:
        status_code = 200
        def raise_for_status(self): pass
        def json(self): return {"message": {"content": "Fortnite, low HP, being chased."}}
    def fake_post(url, json=None, timeout=None):
        captured["url"] = url; captured["json"] = json
        return FakeResp()
    monkeypatch.setattr(screen_watcher.httpx, "post", fake_post)
    out = screen_watcher.describe_frame(b"\xff\xd8fakejpeg", "http://x:11434", "llava-llama3:latest")
    assert out == "Fortnite, low HP, being chased."
    msg = captured["json"]["messages"][0]
    assert captured["json"]["keep_alive"] == "3m"
    assert base64.b64decode(msg["images"][0]) == b"\xff\xd8fakejpeg"  # image base64'd


def test_unload_llava_sends_keepalive_zero(monkeypatch):
    captured = {}
    class FakeResp:
        status_code = 200
        def raise_for_status(self): pass
        def json(self): return {}
    monkeypatch.setattr(screen_watcher.httpx, "post",
                        lambda url, json=None, timeout=None: (captured.update(json=json) or FakeResp()))
    screen_watcher.unload_llava("http://x:11434", "llava-llama3:latest")
    assert captured["json"]["keep_alive"] == 0


def test_run_watch_loop_ticks_and_unloads(monkeypatch):
    calls = {"desc": 0, "post": 0, "unload": 0, "sleep": 0}
    monkeypatch.setattr(screen_watcher, "capture_frame", lambda width=1024: b"\xff\xd8x")
    def fake_desc(*a, **k):
        calls["desc"] += 1
        if calls["desc"] == 2:
            raise RuntimeError("bad frame")  # a bad tick must not kill the loop
        return "scene"
    monkeypatch.setattr(screen_watcher, "describe_frame", fake_desc)
    monkeypatch.setattr(screen_watcher, "post_frame", lambda *a, **k: calls.update(post=calls["post"]+1) or True)
    monkeypatch.setattr(screen_watcher, "unload_llava", lambda *a, **k: calls.update(unload=calls["unload"]+1))
    monkeypatch.setattr(screen_watcher.time, "sleep", lambda s: calls.update(sleep=calls["sleep"]+1))
    cfg = {"ollama_url": "http://x:11434", "llava_model": "m", "server_url": "http://y:8765",
           "api_key": "", "interval": 0, "width": 1024, "keepalive": "3m"}
    screen_watcher.run_watch_loop(cfg, max_ticks=3)
    assert calls["desc"] == 3            # ran 3 ticks
    assert calls["post"] == 2            # tick 2 errored before post, others posted
    assert calls["unload"] == 1          # unloaded exactly once on exit
