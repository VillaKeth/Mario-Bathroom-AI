"""In-memory recognition-event feed for the Recognition Inspector page, plus a
deterministic name->person_id helper for ad-hoc enrollment. Importable + pure so
it is unit-testable (server/main.py is not)."""
import hashlib
import time
from collections import deque

_events: deque = deque(maxlen=100)
_seq: int = 0


def push(kind: str, name, confidence: float, is_new: bool, source: str) -> dict:
    """Record one recognition event. kind: 'face'|'voice'. source: 'live'|'upload'."""
    global _seq
    _seq += 1
    evt = {
        "seq": _seq,
        "ts": time.time(),
        "kind": kind,
        "name": name,
        "confidence": round(float(confidence or 0.0), 3),
        "is_new": bool(is_new),
        "source": source,
    }
    _events.append(evt)
    return evt


def recent(since: int = 0) -> list:
    """Events with seq > since, oldest first."""
    return [e for e in _events if e["seq"] > since]


def person_id_for_name(name: str) -> int:
    """Stable positive person_id derived from the (case-insensitive) name, so
    re-enrolling the same name UPSERTs the same face_encodings row."""
    digest = hashlib.md5(name.strip().lower().encode("utf-8")).hexdigest()
    return int(digest[:8], 16)  # 0 .. ~4.29e9, positive
