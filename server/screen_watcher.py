"""Standalone screen-watch process: capture the screen, have llava describe the
game, POST the description to the server so Rudi can roast it. Run via
start_watching.bat. llava is loaded ONLY while this process runs and is
unloaded on exit."""
import cv2
import numpy as np


def _encode_jpeg(frame_bgr, width: int = 1024, quality: int = 70) -> bytes:
    """Downscale a BGR frame to `width` (keeping aspect) and JPEG-encode it."""
    h, w = frame_bgr.shape[:2]
    if w > width:
        scale = width / float(w)
        frame_bgr = cv2.resize(frame_bgr, (width, int(h * scale)), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", frame_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not ok:
        raise RuntimeError("JPEG encode failed")
    return buf.tobytes()


def capture_frame(width: int = 1024) -> bytes:
    """Grab the primary monitor and return a downscaled JPEG."""
    import mss  # imported lazily so the encoder is testable without a display
    with mss.mss() as sct:
        shot = sct.grab(sct.monitors[1])  # monitors[1] = primary
    frame = np.array(shot)[:, :, :3]      # BGRA -> BGR
    return _encode_jpeg(frame, width=width)
