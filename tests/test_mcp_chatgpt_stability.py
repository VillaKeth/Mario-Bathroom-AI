import asyncio

from mcp_chatgpt.stability import ProbeResult, WaitOutcome, wait_for_response


def _run(coro):
    return asyncio.run(coro)


async def _noop_sleep(_seconds):
    return None


def _scripted_probe(results):
    """Return an async probe that yields each ProbeResult in turn, repeating the last."""
    seq = list(results)

    async def probe():
        return seq.pop(0) if len(seq) > 1 else seq[0]

    return probe


def test_text_completes_after_stable_window():
    probe = _scripted_probe([
        ProbeResult(is_generating=True, text="Hel", image_count=0, images_ready=True),
        ProbeResult(is_generating=True, text="Hello", image_count=0, images_ready=True),
        ProbeResult(is_generating=False, text="Hello world", image_count=0, images_ready=True),
        ProbeResult(is_generating=False, text="Hello world", image_count=0, images_ready=True),
        ProbeResult(is_generating=False, text="Hello world", image_count=0, images_ready=True),
    ])
    out = _run(wait_for_response(probe, sleep=_noop_sleep,
                                 stable_window=2, max_polls=20, poll_interval=0.0))
    assert isinstance(out, WaitOutcome)
    assert out.text == "Hello world"
    assert out.timed_out is False
    assert out.had_image is False


def test_timeout_returns_partial():
    probe = _scripted_probe([
        ProbeResult(is_generating=True, text="partial...", image_count=0, images_ready=True),
    ])
    out = _run(wait_for_response(probe, sleep=_noop_sleep,
                                 stable_window=2, max_polls=5, poll_interval=0.0))
    assert out.timed_out is True
    assert out.text == "partial..."


def test_waits_for_image_bytes_before_done():
    probe = _scripted_probe([
        ProbeResult(is_generating=False, text="", image_count=1, images_ready=False),
        ProbeResult(is_generating=False, text="", image_count=1, images_ready=False),
        ProbeResult(is_generating=False, text="", image_count=1, images_ready=True),
        ProbeResult(is_generating=False, text="", image_count=1, images_ready=True),
        ProbeResult(is_generating=False, text="", image_count=1, images_ready=True),
    ])
    out = _run(wait_for_response(probe, sleep=_noop_sleep,
                                 stable_window=2, max_polls=20, poll_interval=0.0))
    assert out.had_image is True
    assert out.timed_out is False


def test_no_complete_on_empty_before_generation():
    # Long pre-generation gap (not generating, empty text, no image) must NOT be
    # treated as a finished empty reply. Wait through the gap, capture the real
    # answer once it streams and stabilises. Regression: follow-up send returned "".
    probe = _scripted_probe(
        [ProbeResult(is_generating=False, text="", image_count=0, images_ready=True)] * 6
        + [
            ProbeResult(is_generating=True, text="4", image_count=0, images_ready=True),
            ProbeResult(is_generating=True, text="42", image_count=0, images_ready=True),
            ProbeResult(is_generating=False, text="It was 42.", image_count=0, images_ready=True),
            ProbeResult(is_generating=False, text="It was 42.", image_count=0, images_ready=True),
            ProbeResult(is_generating=False, text="It was 42.", image_count=0, images_ready=True),
            ProbeResult(is_generating=False, text="It was 42.", image_count=0, images_ready=True),
            ProbeResult(is_generating=False, text="It was 42.", image_count=0, images_ready=True),
        ]
    )
    out = _run(wait_for_response(probe, sleep=_noop_sleep,
                                 stable_window=4, max_polls=40, poll_interval=0.0))
    assert out.text == "It was 42."
    assert out.timed_out is False


def test_lagging_image_after_text_not_cut_off():
    # Text streams + settles with NO image, THEN a generated image lags in. With a
    # no-image grace window, must keep waiting and catch the image (not return the
    # text early as "no image"). Regression for: real render cut off as refused.
    probe = _scripted_probe(
        [ProbeResult(is_generating=True, text="Here:", image_count=0, images_ready=True)]
        + [ProbeResult(is_generating=False, text="Here you go:", image_count=0, images_ready=True)] * 3
        + [
            ProbeResult(is_generating=False, text="Here you go:", image_count=1, images_ready=False),
            ProbeResult(is_generating=False, text="Here you go:", image_count=1, images_ready=True),
            ProbeResult(is_generating=False, text="Here you go:", image_count=1, images_ready=True),
            ProbeResult(is_generating=False, text="Here you go:", image_count=1, images_ready=True),
        ]
    )
    out = _run(wait_for_response(probe, sleep=_noop_sleep, stable_window=2,
                                 no_image_stable_window=8, max_polls=40, poll_interval=0.0))
    assert out.had_image is True
    assert out.timed_out is False


def test_text_only_still_completes_after_no_image_window():
    # A genuine text-only reply (e.g. a guardrail refusal) still finishes — just
    # after the longer no-image stable window instead of the short one.
    probe = _scripted_probe(
        [ProbeResult(is_generating=False, text="refused.", image_count=0, images_ready=True)] * 30
    )
    out = _run(wait_for_response(probe, sleep=_noop_sleep, stable_window=2,
                                 no_image_stable_window=8, max_polls=40, poll_interval=0.0))
    assert out.text == "refused."
    assert out.had_image is False
    assert out.timed_out is False


def test_waits_for_image_appearing_after_generation_ends():
    # Image generation: Stop button (is_generating) clears BEFORE the <img> renders.
    # The gap is empty (no text, no image). Must not complete empty — wait for the
    # image to appear and load. Regression: image new_thread returned no images.
    probe = _scripted_probe(
        [ProbeResult(is_generating=True, text="", image_count=0, images_ready=True)] * 2
        + [ProbeResult(is_generating=False, text="", image_count=0, images_ready=True)] * 4
        + [
            ProbeResult(is_generating=False, text="", image_count=1, images_ready=False),
            ProbeResult(is_generating=False, text="", image_count=1, images_ready=True),
            ProbeResult(is_generating=False, text="", image_count=1, images_ready=True),
            ProbeResult(is_generating=False, text="", image_count=1, images_ready=True),
        ]
    )
    out = _run(wait_for_response(probe, sleep=_noop_sleep,
                                 stable_window=2, max_polls=40, poll_interval=0.0))
    assert out.had_image is True
    assert out.timed_out is False
