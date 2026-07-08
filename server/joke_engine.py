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


def load_freaky_jokes(char_dir: str):
    """Return {'bravado': [...], 'explicit': [...]} from <char_dir>/jokes/freaky.yaml.
    Missing/malformed file -> empty lists (character stays clean)."""
    out = {"bravado": [], "explicit": []}
    path = os.path.join(char_dir, "jokes", "freaky.yaml")
    if not os.path.isfile(path):
        return out
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        for lane in ("bravado", "explicit"):
            vals = data.get(lane) or []
            if isinstance(vals, list):
                out[lane] = [str(v) for v in vals if str(v).strip()]
    except Exception:
        return {"bravado": [], "explicit": []}
    return out


def effective_freak_level(base_default, live_override=None):
    """Effective 0-1 freak level. Opt-in ONLY: base_default (the character's yaml
    freak_factor) <= 0 -> 0.0 no matter what the live override says, so a clean
    character can never be dialed freaky. Otherwise the live override (if numeric)
    scales it, clamped to [0,1]."""
    try:
        base = float(base_default or 0.0)
    except (TypeError, ValueError):
        base = 0.0
    if base <= 0.0:
        return 0.0
    if live_override is None:
        lvl = base
    else:
        try:
            lvl = float(live_override)
        except (TypeError, ValueError):
            lvl = base
    return max(0.0, min(1.0, lvl))


class JokeEngine:
    """Serves jokes: 10% live-LLM, else a level-blended shuffle-bag draw across
    clean / freaky-bravado / freaky-explicit pools. freak level 0 (default for
    every non-opted-in character) => only the clean pool is ever drawn."""

    def __init__(self, pool, freaky_pool=None, llm_fn=None, llm_chance=0.10,
                 freak_level_fn=None, explicit_ratio=0.25, rng=None):
        fp = freaky_pool or {}
        self._llm_fn = llm_fn
        self._llm_chance = llm_chance
        self._freak_level_fn = freak_level_fn
        self._explicit_ratio = explicit_ratio
        self._rng = rng or random.Random()
        # Multiple worker threads can call next_joke() concurrently (idle loop
        # and command-handler path both run off-loop via run_in_executor) — guard
        # every bag refill+pop as one atomic step.
        self._lock = threading.Lock()
        # Each bag is an independent no-repeat shuffle-bag over its source list.
        self._bags = {
            "clean":    {"src": list(pool or []),               "bag": [], "last": None},
            "bravado":  {"src": list(fp.get("bravado") or []),  "bag": [], "last": None},
            "explicit": {"src": list(fp.get("explicit") or []), "bag": [], "last": None},
        }

    def _draw(self, name):
        with self._lock:
            st = self._bags[name]
            src = st["src"]
            if not src:
                return None
            refilled = not st["bag"]
            if refilled:
                st["bag"] = list(src)
                self._rng.shuffle(st["bag"])
            choice = st["bag"].pop()
            if refilled and choice == st["last"] and len(src) > 1:
                # Fresh bag happened to start with the joke we just served — swap
                # it for a different one so it never repeats back-to-back.
                idx = self._rng.randrange(len(st["bag"]))
                st["bag"].append(choice)
                choice = st["bag"].pop(idx)
            st["last"] = choice
            return choice

    def _draw_from_bag(self):
        """Back-compat: draw from the clean pool only."""
        return self._draw("clean")

    def _freak_level(self):
        if self._freak_level_fn is None:
            return 0.0
        try:
            return max(0.0, min(1.0, float(self._freak_level_fn())))
        except Exception:
            return 0.0

    def _draw_blended(self):
        have_freaky = bool(self._bags["bravado"]["src"] or self._bags["explicit"]["src"])
        level = self._freak_level() if have_freaky else 0.0
        if level > 0 and self._rng.random() < level:
            if self._bags["explicit"]["src"] and self._rng.random() < self._explicit_ratio:
                out = self._draw("explicit")
                if out:
                    return out
            out = self._draw("bravado")
            if out:
                return out
        return self._draw("clean")

    def next_joke(self):
        if self._llm_fn is not None and self._rng.random() < self._llm_chance:
            try:
                out = self._llm_fn()
                if out and out.strip():
                    return out.strip()
            except Exception:
                pass  # fall through to the cached bag
        return self._draw_blended()
