"""Stage directions (*dramatic gasp*, *mischievous grin*) must appear in the speech
BUBBLE but never be SPOKEN. analyze_text() is where display_text and tts_text diverge.

Root cause of the bug this pins: analyze_text used to set tts_text = _strip_md_asterisks(text),
which strips the * markers but KEEPS the words, so the TTS engine voiced the stage direction
literally ("dramatic gasp"). Emphasis words (*so*, *don't*) must still be spoken.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

from pose_analyzer import analyze_text


def _tts(text):
    return analyze_text(text)["tts_text"]


def _disp(text):
    return analyze_text(text)["display_text"]


def test_multiword_stage_direction_not_spoken_but_shown():
    a = analyze_text("*dramatic gasp* Nice hat!")
    assert "gasp" not in a["tts_text"].lower()      # not spoken
    assert "Nice hat!" in a["tts_text"]             # the real line survives
    assert "gasp" in a["display_text"].lower()      # bubble still shows the action


def test_all_reported_wild_examples_not_spoken():
    # exactly the ones heard at the party
    for phrase, action_word in [
        ("*dramatic gasp* hello", "gasp"),
        ("*dramatic pause* hello", "pause"),
        ("*mischievous grin* hello", "grin"),
        ("*taps foot impatiently* hello", "taps"),
    ]:
        t = _tts(phrase).lower()
        assert "hello" in t, phrase
        assert action_word not in t, phrase


def test_single_word_action_verb_not_spoken():
    assert "laughs" not in _tts("*laughs* okay then").lower()
    assert "okay then" in _tts("*laughs* okay then")
    assert "sighs" not in _tts("*sighs* fine").lower()
    assert "grinning" not in _tts("*grinning* yes").lower()   # -ing gerund


def test_emphasis_single_word_still_spoken():
    assert "so" in _tts("That's *so* good").lower().split()


def test_critical_emphasis_word_never_dropped():
    # dropping *don't* / *not* would INVERT meaning — must survive into speech
    assert "don't" in _tts("*don't* touch that").lower()
    assert "not" in _tts("that is *not* okay").lower().split()


def test_bold_name_emphasis_kept():
    assert "rudi" in _tts("It's **Rudi** time").lower()


def test_plain_text_unchanged():
    assert _tts("It's-a me, let's go!").lower().startswith("it")
    assert "gasp" not in _tts("Hello there friend").lower()
