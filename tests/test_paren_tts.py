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


def test_preclean_emoji_before_capital_becomes_period():
    # Regression: an emoji used as a sentence separator was stripped to nothing,
    # producing run-on speech ("indie tunes What do you say"). A capitalized word
    # after the emoji means a new sentence -> restore the intended period.
    out = tts._preclean_tts_text("a playlist of catchy indie tunes \U0001F3B5 What do you say?")
    assert "tunes What" not in out
    assert "tunes. What" in out


def test_preclean_emoji_at_edges_leaves_no_stray_punct():
    out = tts._preclean_tts_text("\U0001F389 Welcome friend \U0001F38A")
    assert not out.strip().startswith((",", "."))
    assert "Welcome friend" in out


# pose_analyzer.analyze_text is the stripper on the REAL response path (runs
# before _preclean). It must apply the same rule AND keep emoji in display_text.
import pose_analyzer  # noqa: E402


def test_analyze_text_emoji_before_capital_becomes_period_in_speech():
    a = pose_analyzer.analyze_text("catchy indie tunes \U0001F3B5 What do you say?")
    assert "tunes. What" in a["tts_text"]      # spoken: sentence break restored
    assert "tunes What" not in a["tts_text"]


def test_analyze_text_keeps_emoji_in_display_text():
    a = pose_analyzer.analyze_text("Say cheese \U0001F4F8 Smile!")
    assert "\U0001F4F8" in a["display_text"]   # bubble keeps the emoji
    assert "\U0001F4F8" not in a["tts_text"]   # voice does not
    assert "cheese. Smile" in a["tts_text"]    # period restored before capital
