"""Mid-stream gap grace — the bubble must not clear while the reply is still coming.

Streamed replies arrive sentence-by-sentence. Between chunks the client's audio
playback goes idle, so `_wait_for_audio_complete` waits a grace window for more
audio before clearing the speech bubble. That window was a flat 4s.

Measured GPT-SoVITS synthesis on the dev box (115 samples from server logs) is
median 5.7s and max 21.4s per sentence, so a normal inter-chunk gap routinely
exceeded the 4s grace: the bubble cleared and the talking pose dropped while the
character was still mid-reply, then snapped back when the next chunk landed.

The grace only exists to stop the bubble wedging forever on a stream that DIED.
It must therefore outlast a slow synthesis, not race it.
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (ROOT, os.path.join(ROOT, "client")):
    if p not in sys.path:
        sys.path.insert(0, p)


@pytest.fixture(scope="module")
def cm():
    import client.main as cm
    return cm


# Slowest single-sentence synthesis observed in server logs (seconds).
OBSERVED_MAX_SYNTH = 21.4


def test_finished_stream_clears_promptly(cm):
    """is_last seen — nothing more is coming, so don't hold the bubble open."""
    assert cm.stream_gap_grace(is_last_seen=True) <= 1.0


def test_unfinished_stream_outlasts_the_slowest_observed_synthesis(cm):
    """THE BUG: a 4s window loses to a 5.7s median gap, let alone a 21.4s one."""
    assert cm.stream_gap_grace(is_last_seen=False) > OBSERVED_MAX_SYNTH


def test_unfinished_stream_still_clears_eventually(cm):
    """A dead stream must not wedge the bubble open forever."""
    grace = cm.stream_gap_grace(is_last_seen=False)
    assert grace != float("inf")
    assert grace <= 120.0


def test_unfinished_window_is_longer_than_finished_window(cm):
    assert cm.stream_gap_grace(is_last_seen=False) > cm.stream_gap_grace(is_last_seen=True)
