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
