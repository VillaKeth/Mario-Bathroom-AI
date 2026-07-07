import os
import yaml
import random
import threading

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
        # Multiple worker threads can call next_joke() concurrently (idle loop
        # and command-handler path both run off-loop via run_in_executor), and
        # both draw from this same bag — guard refill+pop as one atomic step.
        self._lock = threading.Lock()
        self._last = None  # last-served joke, to avoid a back-to-back repeat across a refill

    def _draw_from_bag(self):
        with self._lock:
            if not self._pool:
                return None
            refilled = not self._bag
            if refilled:
                self._bag = list(self._pool)
                self._rng.shuffle(self._bag)
            choice = self._bag.pop()
            if refilled and choice == self._last and len(self._pool) > 1:
                # Fresh bag happened to start with the joke we just served —
                # swap it for a different one so it never repeats back-to-back.
                idx = self._rng.randrange(len(self._bag))
                self._bag.append(choice)
                choice = self._bag.pop(idx)
            self._last = choice
            return choice

    def next_joke(self):
        if self._llm_fn is not None and self._rng.random() < self._llm_chance:
            try:
                out = self._llm_fn()
                if out and out.strip():
                    return out.strip()
            except Exception:
                pass  # fall through to the cached bag
        return self._draw_from_bag()
