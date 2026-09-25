"""Party event -> stimulus for the fly brain. Deterministic; driven by
characters/fly/brain/senses.yaml. The fly cannot read: any text is sound on
its antennae, and some words stand in for things that physically happen to a
fly (something sweet, something bitter, a swatter coming down, a puff of air)."""
import random
import re
from dataclasses import asdict, dataclass

import yaml

_WORD = re.compile(r"[a-z']+")
_SHOUT = re.compile(r"\b[A-Z]{3,}\b")


@dataclass(frozen=True)
class Stimulus:
    pop: str
    rate: float
    side: str = "both"

    def to_dict(self):
        return asdict(self)


def _rate_range(r):
    if isinstance(r, (list, tuple)) and len(r) == 2:
        return float(r[0]), float(r[1])
    return float(r or 0), float(r or 0)


class SenseMapper:
    def __init__(self, cfg, rng=None):
        self._rng = rng or random.Random()
        sound = cfg.get("text_is_sound") or {}
        self.sound_pop = str(sound.get("pop", "ears"))
        self.sound_rate = float(sound.get("rate", 50))
        self.shout_rate = float(sound.get("shout_rate", 120))
        self.lexicons = []
        for name, lx in (cfg.get("lexicons") or {}).items():
            lo, hi = _rate_range(lx.get("rate"))
            words, phrases = set(), []
            for w in lx.get("words") or []:
                w = " ".join(_WORD.findall(str(w).lower()))
                if " " in w:
                    phrases.append(w)
                elif w:
                    words.add(w)
            self.lexicons.append({"name": name, "pop": str(lx["pop"]), "lo": lo, "hi": hi,
                                  "side": str(lx.get("side", "both")),
                                  "words": words, "phrases": phrases})
        self.events = {str(k): [dict(s) for s in v or []] for k, v in (cfg.get("events") or {}).items()}

    @classmethod
    def from_yaml(cls, path, rng=None):
        with open(path, encoding="utf-8") as f:
            return cls(yaml.safe_load(f) or {}, rng=rng)

    def _side(self, side):
        return self._rng.choice(("L", "R")) if side == "random" else side

    def from_text(self, text):
        text = text or ""
        tokens = _WORD.findall(text.lower())
        if not tokens:
            return []
        joined = " " + " ".join(tokens) + " "
        shouted = "!!" in text or bool(_SHOUT.search(text))
        best = {self.sound_pop: Stimulus(self.sound_pop, self.shout_rate if shouted else self.sound_rate)}
        for lx in self.lexicons:
            n = sum(1 for t in tokens if t in lx["words"])
            n += sum(joined.count(" " + p + " ") for p in lx["phrases"])
            if n <= 0:
                continue
            rate = lx["lo"] + (lx["hi"] - lx["lo"]) * min(1.0, (n - 1) / 2.0)
            stim = Stimulus(lx["pop"], round(rate, 1), self._side(lx["side"]))
            cur = best.get(stim.pop)
            if cur is None or stim.rate > cur.rate:
                best[stim.pop] = stim
        return list(best.values())

    def from_event(self, event):
        return [Stimulus(str(s["pop"]), float(s.get("rate", 0)), self._side(str(s.get("side", "both"))))
                for s in self.events.get(event, [])]
