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
