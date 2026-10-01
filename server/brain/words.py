"""Behavior -> at most six words, grounded in what fired.

Every word the fly can say comes from a closed vocabulary (words.yaml), so the
reply path cannot leak another character's lines. The LLM only rephrases; its
answer is validated word by word and replaced by the lexicon line on any miss,
timeout or error. ESCAPE and NOTHING say nothing (the design: silence there).
"""
import asyncio
import random
import re

import yaml

SILENT = frozenset({"ESCAPE", "NOTHING"})
_THINK = re.compile(r"<think>.*?</think>", re.S | re.I)
_TOKEN = re.compile(r"[a-z]+")
POP_WORDS = {
    "sugar": "sweet taste neurons", "bitter": "bitter taste neurons",
    "ears": "hearing neurons", "antenna": "antenna wind and touch neurons",
    "loom": "looming shadow detector neurons",
    "feed": "proboscis extension motor neuron (feeding)",
    "groom": "antennal grooming command neurons", "escape": "giant fiber escape neuron",
    "startle": "startle descending neurons", "walk": "walking descending neurons",
    "backup": "backward walking neurons",
}


class FlyWords:
    def __init__(self, cfg, llm_fn=None, max_words=6, timeout_s=3.0, rng=None):
        self.vocab = frozenset(str(w).lower() for w in cfg.get("vocabulary") or [])
        self.lexicon = cfg.get("lexicon") or {}
        self.llm_fn = llm_fn
        self.max_words = int(max_words)
        self.timeout_s = float(timeout_s)
        self._rng = rng or random.Random()

    @classmethod
    def from_yaml(cls, path, **kw):
        with open(path, encoding="utf-8") as f:
            return cls(yaml.safe_load(f) or {}, **kw)

    def lexicon_line(self, behavior):
        if behavior.name in SILENT:
            return ""
        key = "WALK_back" if behavior.name == "WALK" and behavior.direction == "back" else behavior.name
        tiers = self.lexicon.get(key) or {}
        tier = "low" if behavior.intensity < 0.34 else "mid" if behavior.intensity < 0.67 else "high"
        options = tiers.get(tier) or tiers.get("low") or []
        return self._rng.choice(options) if options else ""

    def validate(self, raw):
        words = _TOKEN.findall(_THINK.sub(" ", str(raw or "")).lower())
        if not words or len(words) > self.max_words or any(w not in self.vocab for w in words):
            return None
        return " ".join(words) + "."

    def build_prompt(self, behavior, rates):
        fired = [f"{POP_WORDS.get(k, k)}: {v:.0f} Hz"
                 for k, v in sorted((rates or {}).items(), key=lambda kv: -kv[1]) if v >= 1.0]
        system = ("You are the inner voice of a fruit fly. The fly has no language; you turn what "
                  f"its neurons just did into at most {self.max_words} words. Use ONLY words from "
                  "this list: " + ", ".join(sorted(self.vocab)) + ". Lowercase, no names, no "
                  "punctuation except periods. Output only the words.")
        user = (f"Behavior: {behavior.name.lower()}"
                + (f" ({behavior.direction})" if behavior.direction else "")
                + f", intensity {behavior.intensity:.1f}. Neurons that fired: "
                + ("; ".join(fired) if fired else "almost nothing") + ".")
        return [{"role": "system", "content": system}, {"role": "user", "content": user}]

    async def speak(self, behavior, rates, use_llm=True):
        base = self.lexicon_line(behavior)
        if not base or not use_llm or self.llm_fn is None:
            return base
        try:
            raw = await asyncio.wait_for(self.llm_fn(self.build_prompt(behavior, rates)), self.timeout_s)
        except Exception:
            return base
        return self.validate(raw) or base


async def ollama_chat(messages, url, model, timeout=3.0):
    """Non-streaming Ollama chat; thinking disabled for reasoning models (Qwen3)."""
    import httpx
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(f"{url.rstrip('/')}/api/chat", json={
            "model": model, "messages": messages, "stream": False, "think": False,
            "options": {"num_predict": 32, "temperature": 0.9}})
        r.raise_for_status()
        return (r.json().get("message") or {}).get("content", "")
