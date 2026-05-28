"""Known character database — auto-fill data for popular characters."""
import json
import os

_DB_PATH = os.path.join(os.path.dirname(__file__), "known_characters.json")
_cache = None

def _load():
    global _cache
    if _cache is None:
        with open(_DB_PATH, "r", encoding="utf-8") as f:
            _cache = json.load(f)
    return _cache

def lookup(name: str) -> dict | None:
    db = _load()
    key = name.lower().strip().replace(" ", "_")
    return db.get(key)

def list_all() -> list[str]:
    return list(_load().keys())
