"""In-memory log ring for the debug MCP. Pure + thread-safe; no FastAPI import."""
import logging
import threading
from collections import deque

_LEVELS = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40, "CRITICAL": 50}


class LogRing:
    def __init__(self, maxlen: int = 2000):
        self._dq = deque(maxlen=maxlen)
        self._lock = threading.Lock()

    def append(self, msg: str, level: str = "INFO", name: str = ""):
        with self._lock:
            self._dq.append({"msg": msg, "level": level.upper(), "name": name})

    def snapshot(self, n: int = 200, grep: str = "", level: str = "DEBUG"):
        floor = _LEVELS.get(level.upper(), 0)
        with self._lock:
            items = list(self._dq)
        if grep:
            g = grep.lower()
            items = [l for l in items if g in l["msg"].lower()]
        items = [l for l in items if _LEVELS.get(l["level"], 0) >= floor]
        return items[-n:]

    def handler(self) -> logging.Handler:
        ring = self

        class _RingHandler(logging.Handler):
            def emit(self, record):
                try:
                    ring.append(record.getMessage(), record.levelname, record.name)
                except Exception:
                    pass

        h = _RingHandler()
        h.setLevel(logging.DEBUG)
        return h
