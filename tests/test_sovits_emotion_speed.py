"""Emotion has never reached the fine-tuned voice. Wire it to speed_factor.

EMOTION_VOICE_MAP has always produced a rate per emotion -- THINKING is -15%,
EXCITED +30%, SLEEPY -25% -- and synthesize() has always taken it as an
argument and put it in the cache key. But only the Edge path ever read it. The
SoVITS path called _sovits_synthesize(text) and took the default speed of 1.0,
so on a fine-tuned character every emotion was delivered at exactly one pace.

That is the missing lever for "he should pause a bit longer on the thoughtful
line": THINKING already asks for slower, and the request was being dropped on
the floor.

The mapping is damped and clamped rather than passed through. Edge resynthesises
at the new rate; SoVITS time-stretches the waveform, which goes metallic well
before +30%.
"""
import os
import sys

import pytest

# Match the convention in test_tts_router.py: tts imports its siblings by bare
# name, so it has to be imported the same way or it loads a second time under a
# different module identity and monkeypatching the wrong copy silently no-ops.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

import tts  # noqa: E402


def test_neutral_rate_is_unchanged_speed():
    assert tts._rate_to_speed("+0%") == 1.0


def test_thinking_slows_the_voice_down():
    """The emotion the user's example calls for."""
    from emotions import EMOTION_VOICE_MAP, Emotion
    rate = EMOTION_VOICE_MAP[Emotion.THINKING]["rate"]
    assert tts._rate_to_speed(rate) < 1.0


def test_excited_speeds_it_up():
    from emotions import EMOTION_VOICE_MAP, Emotion
    assert tts._rate_to_speed(EMOTION_VOICE_MAP[Emotion.EXCITED]["rate"]) > 1.0


def test_every_mapped_emotion_stays_in_the_safe_band():
    """SoVITS time-stretches, so the full Edge range would sound metallic."""
    from emotions import EMOTION_VOICE_MAP
    for emo, params in EMOTION_VOICE_MAP.items():
        s = tts._rate_to_speed(params["rate"])
        assert 0.88 <= s <= 1.12, (emo, params["rate"], s)


def test_the_mapping_is_damped_not_passed_through():
    """+30% must not become speed 1.30."""
    assert abs(tts._rate_to_speed("+30%") - 1.0) < 0.30


def test_garbage_rate_falls_back_to_normal_speed():
    for bad in (None, "", "fast", "%", "+%"):
        assert tts._rate_to_speed(bad) == 1.0


def test_speed_is_recovered_from_a_cache_key():
    """The hybrid regen worker only has the key, not the original rate.

    Without this it would re-render at 1.0 and store the result under a key that
    promises a slowed-down take.
    """
    key = "charliekirk:en-US-AriaNeural:Let me think about that:-15%:+1Hz"
    assert tts._speed_from_cache_key(key) == tts._rate_to_speed("-15%")


def test_speed_from_a_malformed_key_is_normal_speed():
    assert tts._speed_from_cache_key("nonsense") == 1.0


def test_synthesize_hands_the_emotion_speed_to_sovits(monkeypatch):
    """The helper is worthless if the call site keeps passing the default."""
    seen = {}

    def fake_sovits(text, speed=1.0, _is_user=False):
        seen["speed"] = speed
        return b"RIFFfake"

    monkeypatch.setattr(tts, "should_try_sovits", lambda *a, **k: True)
    monkeypatch.setattr(tts, "_sovits_synthesize", fake_sovits)
    monkeypatch.setattr(tts, "_normalize_audio", lambda b: b)

    tts.synthesize("Let me think about that for a second.", rate="-15%",
                   pitch="+1Hz", nocache=True)

    assert seen.get("speed") == pytest.approx(tts._rate_to_speed("-15%"))
    assert seen["speed"] < 1.0
