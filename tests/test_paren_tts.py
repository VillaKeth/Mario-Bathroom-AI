"""Parenthetical content must be SPOKEN (the bubble keeps the brackets, but TTS
can't voice '(' / ')', so they become natural comma pauses). Regression: the
speech bubble showed text in parentheses that her voice silently dropped."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))
import tts  # noqa: E402


def test_preclean_speaks_parenthetical_content_without_brackets():
    out = tts._preclean_tts_text("Snap a photo (at 6pm, you said?) and smile")
    assert "(" not in out and ")" not in out          # brackets not vocalized
    assert "at 6pm" in out                             # words are kept (spoken)
    assert "you said" in out
    assert "smile" in out


def test_preclean_paren_leaves_no_comma_artifacts():
    out = tts._preclean_tts_text("Hello (waves) friend")
    assert ",," not in out
    assert not out.strip().startswith(",")
    assert "waves" in out and "friend" in out


def test_preclean_emoji_between_words_becomes_pause_not_runon():
    # Regression: an emoji used as a sentence separator was stripped to nothing,
    # producing run-on speech ("indie tunes What do you say"). It must leave a
    # comma pause instead.
    out = tts._preclean_tts_text("a playlist of catchy indie tunes \U0001F3B5 What do you say?")
    assert "tunes What" not in out
    assert "tunes, What" in out


def test_preclean_emoji_at_edges_leaves_no_stray_comma():
    out = tts._preclean_tts_text("\U0001F389 Welcome friend \U0001F38A")
    assert not out.strip().startswith(",")
    assert not out.strip().endswith(",")
    assert "Welcome friend" in out
