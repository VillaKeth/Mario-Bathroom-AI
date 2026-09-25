import os
import random
import time

from server.brain.senses import SenseMapper, Stimulus

YAML = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "characters", "fly", "brain", "senses.yaml")


def _m():
    return SenseMapper.from_yaml(YAML, rng=random.Random(0))


def _by_pop(stims):
    return {s.pop: s for s in stims}


def test_plain_text_is_just_sound():
    assert _m().from_text("hello there") == [Stimulus("ears", 50.0)]


def test_shouting_is_louder():
    assert _by_pop(_m().from_text("HEY WHAT IS UP"))["ears"].rate == 120.0
    assert _by_pop(_m().from_text("hey!!"))["ears"].rate == 120.0
    assert _by_pop(_m().from_text("ok I am fine"))["ears"].rate == 50.0  # OK / I are not shouting


def test_food_scales_with_matches_and_caps():
    assert _by_pop(_m().from_text("have some candy"))["sugar"].rate == 100.0
    assert _by_pop(_m().from_text("candy and cake"))["sugar"].rate == 150.0
    assert _by_pop(_m().from_text("candy cake beer honey donut"))["sugar"].rate == 200.0


def test_affection_is_milder_sugar_and_max_wins():
    assert _by_pop(_m().from_text("you're so cute"))["sugar"].rate == 60.0
    assert _by_pop(_m().from_text("cute candy"))["sugar"].rate == 100.0  # food beats affection


def test_gross_and_profanity_are_bitter():
    assert _by_pop(_m().from_text("you are disgusting"))["bitter"].rate == 100.0
    assert "bitter" in _by_pop(_m().from_text("shut up"))


def test_threat_is_one_sided_looming():
    loom = _by_pop(_m().from_text("I'm gonna swat you"))["loom"]
    assert loom.rate == 150.0 and loom.side in ("L", "R")
    assert "loom" in _by_pop(_m().from_text("where is the fly swatter"))


def test_air_is_antenna():
    assert _by_pop(_m().from_text("blow on it"))["antenna"].rate == 100.0


def test_whole_words_only():
    assert set(_by_pop(_m().from_text("a classic scandal")).keys()) == {"ears"}


def test_emoji_only_is_silent():
    assert _m().from_text("🍰🍰🍰") == []
    assert _m().from_text("   ") == [] and _m().from_text(None) == []


def test_huge_text_is_capped_and_fast():
    t0 = time.perf_counter()
    stims = _by_pop(_m().from_text("candy " * 5000 + "swat " * 5000))
    assert time.perf_counter() - t0 < 0.5
    assert stims["sugar"].rate == 200.0 and stims["loom"].rate == 200.0


def test_events():
    arrival = _m().from_event("arrival")
    assert len(arrival) == 1 and arrival[0].pop == "loom" and arrival[0].side in ("L", "R")
    assert _m().from_event("retch") == [Stimulus("sugar", 150.0)]
    assert _m().from_event("unknown") == []
