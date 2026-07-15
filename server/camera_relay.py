"""Pure decision logic for the remote-camera feature (guest camera over the tunnel).

Importable + side-effect-free so it is unit-testable (server/main.py is not).
main.py holds only the thin FastAPI wiring; every gate/throttle/cache decision
lives here. State is module-level and cleared by reset_state() for tests.
"""
import re
import time

DEBUG_CAMERA = True

_last_frame_ts: dict = {}      # client_id -> ts of last ACCEPTED frame
_frames: dict = {}             # client_id -> (jpeg_bytes, ts)
_wants_greet: set = set()      # client_ids awaiting a first vision greeting
_noface: dict = {}             # client_id -> consecutive no-face count
_last_vision_ts: float = 0.0   # global: last spontaneous/greeting vision comment


def reset_state():
    """Test helper: clear all module state."""
    global _last_frame_ts, _frames, _wants_greet, _noface, _last_vision_ts
    _last_frame_ts = {}
    _frames = {}
    _wants_greet = set()
    _noface = {}
    _last_vision_ts = 0.0


def allow_frame(client_id: str, now: float, min_interval: float) -> bool:
    """True if this client is allowed to submit a frame now (>= min_interval since
    its last accepted frame). Records the timestamp on allow."""
    last = _last_frame_ts.get(client_id)
    if last is not None and (now - last) < min_interval:
        return False
    _last_frame_ts[client_id] = now
    return True


def cache_frame(client_id: str, jpeg: bytes, now: float) -> None:
    """Stash the latest raw JPEG for this client (RAM only) for on-demand vision."""
    _frames[client_id] = (jpeg, now)


def get_cached_frame(client_id: str, now: float, ttl: float):
    """Return the cached JPEG if present and younger than ttl, else None."""
    item = _frames.get(client_id)
    if not item:
        return None
    jpeg, ts = item
    if (now - ts) > ttl:
        return None
    return jpeg


def clear_client(client_id: str) -> None:
    """Camera-off / disconnect: forget everything transient about this client."""
    _frames.pop(client_id, None)
    _last_frame_ts.pop(client_id, None)
    _noface.pop(client_id, None)
    _wants_greet.discard(client_id)


def request_greet(client_id: str) -> None:
    """Mark that this client should get a one-time vision greeting on its next face."""
    _wants_greet.add(client_id)


def take_greet(client_id: str) -> bool:
    """Consume the pending greeting for this client (True once, then False)."""
    if client_id in _wants_greet:
        _wants_greet.discard(client_id)
        return True
    return False


def vision_allowed(now: float, min_gap: float) -> bool:
    """True if a spontaneous vision comment is allowed now (global throttle)."""
    return (now - _last_vision_ts) >= min_gap


def mark_vision(now: float) -> None:
    global _last_vision_ts
    _last_vision_ts = now


def note_face(client_id: str, seen: bool) -> int:
    """Track consecutive no-face frames. Returns the current miss streak
    (0 right after a face is seen)."""
    if seen:
        _noface[client_id] = 0
        return 0
    _noface[client_id] = _noface.get(client_id, 0) + 1
    return _noface[client_id]


_VISION_INTENT = re.compile(
    r"\b(what do you see|see me|look at me|looking at me|how do i look|"
    r"do i look|my outfit|my hat|check .*out|can you see)\b",
    re.IGNORECASE,
)


def is_vision_request(text: str) -> bool:
    """True if the guest is explicitly asking the character to look at them."""
    return bool(text and _VISION_INTENT.search(text))
