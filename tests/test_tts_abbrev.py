"""Abbreviations whose trailing period would be read as a sentence boundary (and
leave an unpronounceable stub) must be spelled out before TTS. Regression:
"St. Michael's" split into "...St." + "Michael's", so the voice dropped the "St."."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))
import tts  # noqa: E402


def test_st_before_name_becomes_saint():
    out = tts._preclean_tts_text("I love St. Michael's Elementary School!")
    assert "St." not in out
    assert "Saint Michael's" in out


def test_bare_st_becomes_street():
    out = tts._preclean_tts_text("Turn onto Main St. and stop.")
    assert "St." not in out
    assert "Main Street" in out


def test_dr_before_name_becomes_doctor():
    out = tts._preclean_tts_text("Go ask Dr. Ratio about it.")
    assert "Doctor Ratio" in out


def test_split_keeps_saint_name_together_not_a_bare_st_segment():
    segs = tts.split_into_sentences(
        "Jacob goes to St. Michael's Elementary School! It is really great!")
    assert all(not s.strip().endswith("St.") for s in segs)   # no stranded "St."
    assert any("Saint Michael's" in s for s in segs)


def test_does_not_corrupt_normal_words_containing_st():
    # "must." / "first" must be untouched (no word boundary before an inner "st").
    out = tts._preclean_tts_text("You must. Be first.")
    assert "Street" not in out and "Saint" not in out
    assert "must" in out and "first" in out
