"""Client-side mirror sender: push tagged JPEG frames + audio to the server.

Additive and opt-in. All network/encoding work is gated behind an 'active'
flag and wrapped so it can never break the pygame render loop.
"""
import io
import logging
import queue
import threading

from PIL import Image

logger = logging.getLogger(__name__)
DEBUG_MIRROR = True

TAG_VIDEO = b"\x01"
TAG_AUDIO = b"\x02"


def encode_frame(rgb_bytes: bytes, size, max_width: int = 640, quality: int = 55) -> bytes:
    """RGB pixel buffer -> downscaled JPEG bytes. Never upscales."""
    w, h = size
    img = Image.frombytes("RGB", (w, h), rgb_bytes)
    if w > max_width:
        new_h = max(1, int(h * max_width / w))
        img = img.resize((max_width, new_h), Image.BILINEAR)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


class MirrorSender:
    """Owns a background thread that connects to /mirror_ingest and sends
    tagged frames (latest-only) + audio (queued). Activated by the server's
    mirror_request signal via start()/stop()."""

    def __init__(self, ingest_url: str, max_width: int = 640, quality: int = 55, fps: int = 10):
        self.ingest_url = ingest_url
        self.max_width = max_width
        self.quality = quality
        self.frame_interval = 1.0 / max(1, fps)
        self._active = False
        self._latest = None          # (rgb_bytes, (w, h)) — 1-slot, newest wins
        self._latest_lock = threading.Lock()
        self._audio_q = queue.Queue(maxsize=32)
        self._stop = threading.Event()
        self._thread = None
        self._ws = None

    # --- called from the pygame render thread (must be cheap + never raise) ---
    def submit_rgb(self, rgb_bytes, size):
        if not self._active:
            return
        try:
            with self._latest_lock:
                self._latest = (rgb_bytes, size)
        except Exception:
            pass

    def send_audio(self, wav_bytes):
        if not self._active or not wav_bytes:
            return
        try:
            self._audio_q.put_nowait(wav_bytes)
        except queue.Full:
            pass

    # --- lifecycle (called from client wiring on mirror_request) ---
    def start(self):
        if self._active:
            return
        self._stop.clear()
        self._active = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        if DEBUG_MIRROR:
            logger.info("[mirror] sender started")

    def stop(self):
        self._active = False
        self._stop.set()
        try:
            if self._ws:
                self._ws.close()
        except Exception:
            pass
        self._ws = None
        with self._latest_lock:
            self._latest = None
        if DEBUG_MIRROR:
            logger.info("[mirror] sender stopped")

    def _run(self):
        import time
        import websocket  # websocket-client, already a client dependency
        try:
            self._ws = websocket.create_connection(self.ingest_url, timeout=5)
        except Exception as e:
            logger.error(f"[mirror] ingest connect failed (mirror disabled): {e}")
            self._active = False
            return
        last_frame = 0.0
        while not self._stop.is_set():
            sent_anything = False
            # Drain audio first (don't drop speech).
            try:
                while True:
                    wav = self._audio_q.get_nowait()
                    self._ws.send_binary(TAG_AUDIO + wav)
                    sent_anything = True
            except queue.Empty:
                pass
            except Exception as e:
                logger.error(f"[mirror] audio send failed: {e}")
                break
            # Then at most one frame per interval.
            now = time.time()
            if now - last_frame >= self.frame_interval:
                with self._latest_lock:
                    item = self._latest
                    self._latest = None
                if item is not None:
                    try:
                        jpeg = encode_frame(item[0], item[1], self.max_width, self.quality)
                        self._ws.send_binary(TAG_VIDEO + jpeg)
                        last_frame = now
                        sent_anything = True
                    except Exception as e:
                        logger.error(f"[mirror] frame send failed: {e}")
                        break
            if not sent_anything:
                time.sleep(0.01)
        try:
            if self._ws:
                self._ws.close()
        except Exception:
            pass
        self._ws = None
