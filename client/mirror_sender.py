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
