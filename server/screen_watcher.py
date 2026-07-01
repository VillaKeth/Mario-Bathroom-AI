"""Standalone screen-watch process: capture the screen, have llava describe the
game, POST the description to the server so Rudi can roast it. Run via
start_watching.bat. llava is loaded ONLY while this process runs and is
unloaded on exit."""
import base64
import cv2
import httpx
import numpy as np


_DESCRIBE_PROMPT = (
    "Describe this game screenshot in ONE short sentence: what game, what's "
    "happening, and how the player is doing (winning, losing, or in danger)."
)


def describe_frame(jpeg: bytes, ollama_url: str, model: str, keepalive: str = "3m") -> str:
    """Ask llava (via Ollama) to describe the frame. Returns a one-line description."""
    b64 = base64.b64encode(jpeg).decode("ascii")
    resp = httpx.post(
        f"{ollama_url}/api/chat",
        json={
            "model": model,
            "messages": [{"role": "user", "content": _DESCRIBE_PROMPT, "images": [b64]}],
            "stream": False,
            "keep_alive": keepalive,
        },
        timeout=120.0,
    )
    resp.raise_for_status()
    return (resp.json().get("message", {}).get("content", "") or "").strip()


def unload_llava(ollama_url: str, model: str) -> None:
    """Evict llava from Ollama immediately (keep_alive=0). Best-effort."""
    try:
        httpx.post(f"{ollama_url}/api/generate",
                   json={"model": model, "keep_alive": 0}, timeout=10.0)
    except Exception:
        pass


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
