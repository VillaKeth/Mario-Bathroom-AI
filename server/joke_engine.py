import os
import yaml
import random

def load_curated_jokes(char_dir: str, fallback=None):
    """Return the curated joke list from <char_dir>/jokes/curated.yaml, or fallback."""
    fallback = fallback or []
    path = os.path.join(char_dir, "jokes", "curated.yaml")
    if not os.path.isfile(path):
        return fallback
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        jokes = data.get("jokes") or []
        return jokes if jokes else fallback
    except Exception:
        return fallback


class JokeEngine:
    """Serves jokes: 90% shuffle-bag over the pool, 10% live-LLM."""

    def __init__(self, pool, llm_fn=None, llm_chance=0.10, rng=None):
        self._pool = list(pool or [])
        self._llm_fn = llm_fn
        self._llm_chance = llm_chance
        self._rng = rng or random.Random()
        self._bag = []

    def _draw_from_bag(self):
        if not self._pool:
            return None
        if not self._bag:
            self._bag = list(self._pool)
            self._rng.shuffle(self._bag)
        return self._bag.pop()

    def next_joke(self):
        if self._llm_fn is not None and self._rng.random() < self._llm_chance:
            try:
                out = self._llm_fn()
                if out and out.strip():
                    return out.strip()
            except Exception:
                pass  # fall through to the cached bag
        return self._draw_from_bag()
