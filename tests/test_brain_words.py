import asyncio
import os
import random

from server.brain.behavior import Behavior
from server.brain.words import FlyWords

YAML = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "characters", "fly", "brain", "words.yaml")


def _w(llm=None, timeout=3.0):
    return FlyWords.from_yaml(YAML, llm_fn=llm, timeout_s=timeout, rng=random.Random(0))


def test_every_lexicon_phrase_passes_the_validator():
    w = _w()
    for key, tiers in w.lexicon.items():
        for tier, phrases in tiers.items():
            for p in phrases:
                assert w.validate(p) is not None, (key, tier, p)


def test_silent_behaviors_say_nothing():
    assert asyncio.run(_w().speak(Behavior("ESCAPE", 1.0), {})) == ""
    assert asyncio.run(_w().speak(Behavior("NOTHING"), {})) == ""


def test_lexicon_tiers_and_backward_walk():
    w = _w()
    assert w.lexicon_line(Behavior("FEED", 0.1)) in w.lexicon["FEED"]["low"]
    assert w.lexicon_line(Behavior("FEED", 0.9)) in w.lexicon["FEED"]["high"]
    assert w.lexicon_line(Behavior("WALK", 0.5, "back")) in w.lexicon["WALK_back"]["mid"]


def test_validate_rules():
    w = _w()
    assert w.validate("Sweet. Sweet MORE!") == "sweet sweet more."
    assert w.validate("<think>the user wants</think> sweet") == "sweet."
    assert w.validate("sweet mario") is None               # out of vocabulary
    assert w.validate("sweet " * 7) is None                 # more than six words
    assert w.validate("") is None and w.validate(None) is None


def test_speak_uses_valid_llm_answer():
    async def llm(messages):
        assert "sweet" in messages[0]["content"] and "feed" in messages[1]["content"].lower()
        return "yum. more sweet."
    assert asyncio.run(_w(llm).speak(Behavior("FEED", 0.9), {"feed": 249.0, "sugar": 150.0})) == "yum more sweet."


def test_speak_falls_back_on_bad_answer_timeout_or_error():
    async def bad(messages):
        return "Mario says it's-a me"

    async def slow(messages):
        await asyncio.sleep(5)
        return "sweet"

    async def boom(messages):
        raise RuntimeError("ollama down")

    for llm, t in ((bad, 3.0), (slow, 0.1), (boom, 3.0)):
        out = asyncio.run(_w(llm, timeout=t).speak(Behavior("FEED", 0.9), {"feed": 249.0}))
        assert out in _w().lexicon["FEED"]["high"]


def test_speak_without_llm_flag_skips_llm():
    called = []

    async def llm(messages):
        called.append(1)
        return "sweet"
    asyncio.run(_w(llm).speak(Behavior("GROOM", 0.5), {}, use_llm=False))
    assert called == []
