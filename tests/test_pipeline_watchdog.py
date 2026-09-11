"""Pipeline watchdog — a slow-but-streaming turn must not be killed or contradicted.

Background: the text pipeline was wrapped in a fixed `asyncio.wait_for(...,
_PIPELINE_TIMEOUT)`. Audio is streamed to the client sentence-by-sentence, so on a
long reply the deadline expired while earlier chunks were still playing: the turn
was cancelled mid-speech AND "That took too long! Try again?" was spoken over it.

A fixed deadline cannot tell a HUNG turn from a slow-but-working one. These tests
pin the distinction: progress (an audio chunk actually reaching the client) extends
the deadline; only silence — or a runaway past the hard cap — ends the turn.
"""
import asyncio
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))


@pytest.fixture
def srv():
    import main as srv
    srv._reset_stream_progress()
    yield srv
    srv._reset_stream_progress()


# --- progress beacon -------------------------------------------------------

def test_no_audio_sent_before_any_chunk(srv):
    assert srv._stream_audio_sent() is False


def test_audio_sent_after_a_chunk_is_marked(srv):
    srv._mark_stream_progress()
    assert srv._stream_audio_sent() is True


def test_reset_clears_progress_between_turns(srv):
    srv._mark_stream_progress()
    srv._reset_stream_progress()
    assert srv._stream_audio_sent() is False


# --- watchdog --------------------------------------------------------------

async def test_returns_result_when_pipeline_finishes_quickly(srv):
    async def quick():
        return "done"

    got = await srv._run_with_stream_watchdog(quick(), idle_timeout=1.0, hard_cap=5.0)
    assert got == "done"


async def test_hung_pipeline_times_out(srv):
    """No progress ever reported — this is the case the timeout exists for."""
    async def hung():
        await asyncio.sleep(5.0)
        return "never"

    with pytest.raises(asyncio.TimeoutError):
        await srv._run_with_stream_watchdog(hung(), idle_timeout=0.2, hard_cap=5.0)


async def test_slow_pipeline_survives_while_it_streams_audio(srv):
    """THE BUG: total runtime far exceeds idle_timeout, but a chunk lands on the
    client every tick, so the turn is working and must be allowed to finish."""
    async def streaming():
        for _ in range(6):
            await asyncio.sleep(0.1)
            srv._mark_stream_progress()   # a chunk reached the client
        return "full story"

    got = await srv._run_with_stream_watchdog(streaming(), idle_timeout=0.25, hard_cap=10.0)
    assert got == "full story"


async def test_pipeline_that_stops_streaming_still_times_out(srv):
    """Progress then silence — a stall mid-reply must still be caught."""
    async def stalls():
        srv._mark_stream_progress()
        await asyncio.sleep(5.0)
        return "never"

    with pytest.raises(asyncio.TimeoutError):
        await srv._run_with_stream_watchdog(stalls(), idle_timeout=0.2, hard_cap=5.0)


async def test_hard_cap_stops_a_runaway_that_never_stops_streaming(srv):
    """Progress alone must not buy unlimited time."""
    async def forever():
        while True:
            await asyncio.sleep(0.05)
            srv._mark_stream_progress()

    with pytest.raises(asyncio.TimeoutError):
        await srv._run_with_stream_watchdog(forever(), idle_timeout=1.0, hard_cap=0.4)


async def test_timed_out_pipeline_is_cancelled(srv):
    """The turn must not keep running (and keep hogging TTS) after giving up."""
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def hung():
        started.set()
        try:
            await asyncio.sleep(5.0)
        except asyncio.CancelledError:
            cancelled.set()
            raise

    with pytest.raises(asyncio.TimeoutError):
        await srv._run_with_stream_watchdog(hung(), idle_timeout=0.2, hard_cap=5.0)
    assert started.is_set()
    assert cancelled.is_set()


async def test_pipeline_exception_propagates_unchanged(srv):
    """Watchdog must not swallow or reshape real failures."""
    async def boom():
        raise ValueError("pipeline blew up")

    with pytest.raises(ValueError, match="pipeline blew up"):
        await srv._run_with_stream_watchdog(boom(), idle_timeout=1.0, hard_cap=5.0)


# --- the timeout announcement ----------------------------------------------
# Cancelling a runaway turn is fine. Announcing "That took too long!" while the
# character is audibly mid-sentence is the bug the guest actually notices.

class _FakeWS:
    def __init__(self):
        self.json = []
        self.blobs = []

    async def send_json(self, payload):
        self.json.append(payload)

    async def send_bytes(self, data):
        self.blobs.append(data)


@pytest.fixture
def spoken(srv, monkeypatch):
    """Capture what send_response() would say to the guest."""
    said = []

    async def _capture(ws, text, audio=None, **kw):
        said.append(text)

    monkeypatch.setattr(srv, "send_response", _capture)
    monkeypatch.setattr(srv, "_PIPELINE_TIMEOUT", 0.2)
    monkeypatch.setattr(srv, "_PIPELINE_HARD_CAP", 5.0)
    return said


async def test_silent_hang_still_tells_the_guest(srv, spoken, monkeypatch):
    async def hung(ws, text):
        await asyncio.sleep(5.0)

    monkeypatch.setattr(srv, "_handle_text_input", hung)
    await srv._handle_text_input_with_timeout(_FakeWS(), "hello")
    assert spoken == [srv._generic_timeout_text()]


async def test_timeout_is_not_announced_over_audio_already_playing(srv, spoken, monkeypatch):
    """Chunks reached the guest, then the turn overran the hard cap. The guest is
    mid-sentence — saying 'That took too long' contradicts what they can hear."""
    monkeypatch.setattr(srv, "_PIPELINE_HARD_CAP", 0.4)

    async def streams_then_overruns(ws, text):
        while True:
            await asyncio.sleep(0.05)
            srv._mark_stream_progress()

    monkeypatch.setattr(srv, "_handle_text_input", streams_then_overruns)
    await srv._handle_text_input_with_timeout(_FakeWS(), "tell me the full story")
    assert spoken == []


async def test_slow_streaming_reply_is_never_cut_or_contradicted(srv, spoken, monkeypatch):
    """End to end: a reply that takes 10x the idle timeout but streams the whole
    way must finish on its own and say nothing extra."""
    finished = asyncio.Event()

    async def slow_story(ws, text):
        for _ in range(10):
            await asyncio.sleep(0.05)
            srv._mark_stream_progress()
        finished.set()

    monkeypatch.setattr(srv, "_handle_text_input", slow_story)
    await srv._handle_text_input_with_timeout(_FakeWS(), "tell me the full story")
    assert finished.is_set(), "slow-but-streaming reply was cut off"
    assert spoken == []


# --- the beacon must actually be wired to real sends ------------------------
# Without this the watchdog is inert in production: nothing ever reports progress,
# so every long reply still dies on the idle deadline.

async def test_sending_audio_marks_progress(srv):
    await srv.send_response(_FakeWS(), "hello", b"RIFFxxxx" + b"\0" * 64)
    assert srv._stream_audio_sent() is True


async def test_sending_text_without_audio_does_not_mark_progress(srv):
    """The timeout line itself goes out audio-less — it must not look like progress."""
    await srv.send_response(_FakeWS(), srv._generic_timeout_text(), None)
    assert srv._stream_audio_sent() is False


# --- long replies must be allowed to finish --------------------------------
# A reply's length is already bounded by response_char_ceiling, so the number of
# sentences — and therefore chunks — is finite. A total-time cap on top of that
# only ever cuts off a reply that is working. hard_cap=None means "no total cap";
# the idle timeout alone still catches a genuine hang.

async def test_hard_cap_none_lets_a_long_reply_finish(srv):
    async def long_but_streaming():
        for _ in range(12):
            await asyncio.sleep(0.05)
            srv._mark_stream_progress()
        return "the whole story"

    got = await srv._run_with_stream_watchdog(
        long_but_streaming(), idle_timeout=0.25, hard_cap=None)
    assert got == "the whole story"


async def test_hard_cap_none_still_catches_a_hang(srv):
    """No cap must not mean no protection — silence still ends the turn."""
    async def hung():
        await asyncio.sleep(5.0)

    with pytest.raises(asyncio.TimeoutError):
        await srv._run_with_stream_watchdog(hung(), idle_timeout=0.2, hard_cap=None)


def test_null_hard_cap_in_config_does_not_crash_the_arithmetic(srv):
    """A literal null in config.json must resolve to 'no cap', not None-in-min()."""
    assert srv._PIPELINE_HARD_CAP is None or isinstance(srv._PIPELINE_HARD_CAP, (int, float))
