"""Hot Reload — LiveConfig for runtime personality tuning."""

import json
import logging
import os
import threading
import time

logger = logging.getLogger("hot_reload")

DEBUG_HOT_RELOAD = True

LIVE_CONFIG_DEFAULTS = {
    "chaos_level": 5,
    "roast_cap": 2,
    "gossip_intensity": 5,
    "warmth": 7,
    "tts_engine": "auto",
}


class LiveConfig:
    """Live-reloadable config backed by a JSON file."""

    def __init__(self, path: str):
        self._path = path
        self._data: dict = {}
        self._lock = threading.Lock()
        self._last_mtime: float = 0.0

        if DEBUG_HOT_RELOAD:
            logger.debug("[DEBUG_HOT_RELOAD] __init__: path=%s", path)

        if os.path.exists(path):
            self.reload()
        else:
            self._data = dict(LIVE_CONFIG_DEFAULTS)
            self._save()

        if DEBUG_HOT_RELOAD:
            logger.debug("[DEBUG_HOT_RELOAD] __init__: loaded %d keys", len(self._data))

    def get(self, key: str, default=None):
        """Get a config value, auto-reloading if file changed."""
        self._check_file_changed()
        with self._lock:
            return self._data.get(key, default)

    def set(self, key: str, value):
        """Update a key and persist to disk."""
        with self._lock:
            self._data[key] = value
            if DEBUG_HOT_RELOAD:
                logger.debug("[DEBUG_HOT_RELOAD] set: %s = %r", key, value)
            self._save()

    def reload(self):
        """Re-read config from disk."""
        try:
            with open(self._path, "r") as f:
                data = json.load(f)
            with self._lock:
                self._data = data
                self._last_mtime = os.path.getmtime(self._path)
            if DEBUG_HOT_RELOAD:
                logger.debug("[DEBUG_HOT_RELOAD] reload: loaded %d keys from disk", len(data))
        except Exception as e:
            logger.error("Failed to reload live config: %s", e)

    def update(self, updates: dict):
        """Batch-update multiple keys and persist."""
        with self._lock:
            self._data.update(updates)
            self._save()

    def to_dict(self) -> dict:
        """Return a copy of current config."""
        with self._lock:
            return dict(self._data)

    def _check_file_changed(self):
        """Reload if the file has been modified externally."""
        try:
            mtime = os.path.getmtime(self._path)
            if mtime > self._last_mtime:
                self.reload()
        except OSError:
            pass

    def _save(self):
        """Write current config to disk."""
        try:
            with open(self._path, "w") as f:
                json.dump(self._data, f, indent=2)
            self._last_mtime = os.path.getmtime(self._path)
        except Exception as e:
            logger.error("Failed to save live config: %s", e)
