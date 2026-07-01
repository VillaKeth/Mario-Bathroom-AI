"""Standalone screen-watch process: capture the screen, have llava describe the
game, POST the description to the server so Rudi can roast it. Run via
start_watching.bat. llava is loaded ONLY while this process runs and is
unloaded on exit."""
import base64
import cv2
import httpx
import json
import numpy as np
import os
import time


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


def post_frame(server_url: str, description: str, api_key: str, guest: str = None) -> bool:
    # guest is None from the watch loop; the server falls back to state_current["speaker_name"].
    # The param is reserved for future direct callers.
    try:
        r = httpx.post(f"{server_url}/admin/watch_frame",
                       json={"description": description, "api_key": api_key, "guest": guest},
                       timeout=15.0)
        return r.status_code == 200
    except Exception as e:
        print(f"[watch] post failed: {e}")
        return False


def run_watch_loop(cfg: dict, max_ticks: int = None) -> None:
    """Capture -> describe -> post every cfg['interval'] s until killed or
    watch_max_minutes elapses. Unloads llava on exit. Per-tick errors are logged
    and skipped (one bad frame never kills the session)."""
    started = time.monotonic()
    max_secs = cfg.get("max_minutes", 30) * 60
    ticks = 0
    try:
        while True:
            if max_ticks is not None and ticks >= max_ticks:
                break
            if max_ticks is None and (time.monotonic() - started) >= max_secs:
                print("[watch] max session time reached, exiting")
                break
            ticks += 1
            try:
                jpeg = capture_frame(width=cfg["width"])
                desc = describe_frame(jpeg, cfg["ollama_url"], cfg["llava_model"], cfg["keepalive"])
                if desc:
                    post_frame(cfg["server_url"], desc, cfg["api_key"])
            except Exception as e:
                print(f"[watch] tick failed (continuing): {e}")
            time.sleep(cfg["interval"])
    finally:
        unload_llava(cfg["ollama_url"], cfg["llava_model"])
        print("[watch] llava unloaded, watcher stopped")


def _load_cfg() -> dict:
    root = os.path.dirname(os.path.dirname(__file__))
    try:
        with open(os.path.join(root, "config.json"), encoding="utf-8") as f:
            s = json.load(f).get("server", {})
    except Exception:
        s = {}
    return {
        "ollama_url": os.environ.get("OLLAMA_URL", s.get("ollama_url", "http://localhost:11434")),
        "server_url": os.environ.get("MARIO_SERVER_URL", "http://localhost:8765"),
        "llava_model": s.get("llava_model", "llava-llama3:latest"),
        "api_key": s.get("admin_api_key", ""),
        "interval": s.get("watch_interval_seconds", 20),
        "max_minutes": s.get("watch_max_minutes", 30),
        "width": s.get("watch_jpeg_width", 1024),
        "keepalive": s.get("watch_keepalive", "3m"),
    }


def main():
    cfg = _load_cfg()
    print(f"[watch] starting — every {cfg['interval']}s, llava={cfg['llava_model']} "
          f"(loads now, unloads on exit). Ctrl+C to stop.")
    try:
        run_watch_loop(cfg)
    except KeyboardInterrupt:
        print("[watch] interrupted")


if __name__ == "__main__":
    main()
