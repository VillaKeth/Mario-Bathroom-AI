"""One reply must be spoken in one voice.

Each synthesize() call decided SoVITS-vs-Edge independently, and a streamed reply
makes one call per sentence. So when SoVITS was down for the first sentences (its
30s restart cooldown raises immediately -> Edge) and recovered partway through, the
character's voice CHANGED MID-REPLY — Edge for chunks 1-5, SoVITS for 6-7.

Observed 2026-09-11 12:39: cooldown -> Edge, then `sovits: auto-restart OK` at
12:39:34, then `synthesize: END (GPT-SoVITS)` for the remaining chunks of the same
answer.

The existing comment in synthesize() is right that a transient failure must never
latch the process onto Edge permanently. So the rule is per-TURN, not per-process:
once a turn falls back, it stays fallen back; the next turn retries SoVITS.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))


@pytest.fixture
def tts():
    import tts
    tts.end_tts_turn()          # known-clean state
    yield tts
    tts.end_tts_turn()


# --- the gate --------------------------------------------------------------

def test_sovits_is_tried_when_mode_is_sovits(tts):
    assert tts.should_try_sovits("sovits", force_fast=False, downgraded=False) is True


def test_edge_mode_never_tries_sovits(tts):
    assert tts.should_try_sovits("edge", force_fast=False, downgraded=False) is False


def test_force_fast_skips_sovits(tts):
    """Thinking fillers must stay instant."""
    assert tts.should_try_sovits("sovits", force_fast=True, downgraded=False) is False


def test_a_downgraded_turn_does_not_go_back_to_sovits(tts):
    """THE BUG: mid-reply recovery is what changed the voice."""
    assert tts.should_try_sovits("sovits", force_fast=False, downgraded=True) is False


# --- turn lifecycle --------------------------------------------------------

def test_a_fresh_turn_is_not_downgraded(tts):
    tts.begin_tts_turn()
    assert tts.turn_is_downgraded() is False


def test_a_fallback_downgrades_the_rest_of_the_turn(tts):
    tts.begin_tts_turn()
    tts._note_turn_downgrade()
    assert tts.turn_is_downgraded() is True


def test_the_next_turn_retries_sovits(tts):
    """A transient failure must not latch the process onto Edge forever."""
    tts.begin_tts_turn()
    tts._note_turn_downgrade()
    assert tts.turn_is_downgraded() is True

    tts.begin_tts_turn()
    assert tts.turn_is_downgraded() is False, (
        "a new turn must be free to try SoVITS again")


def test_ending_a_turn_clears_the_downgrade(tts):
    tts.begin_tts_turn()
    tts._note_turn_downgrade()
    tts.end_tts_turn()
    assert tts.turn_is_downgraded() is False


def test_downgrade_outside_a_turn_does_not_persist_into_one(tts):
    """Idle/precache synthesis must not poison the next user turn."""
    tts._note_turn_downgrade()
    tts.begin_tts_turn()
    assert tts.turn_is_downgraded() is False
