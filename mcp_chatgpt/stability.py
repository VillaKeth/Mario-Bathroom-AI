"""Pure done-detection loop. No playwright, no wall-clock — both injected."""
from dataclasses import dataclass
from typing import Awaitable, Callable


@dataclass
class ProbeResult:
    is_generating: bool   # True while the Stop button is present (model streaming)
    text: str             # current text of the last assistant turn
    image_count: int      # number of <img> in the last assistant turn
    images_ready: bool    # True when all those <img> have loaded bytes


@dataclass
class WaitOutcome:
    text: str
    timed_out: bool
    had_image: bool


async def wait_for_response(
    probe: Callable[[], Awaitable[ProbeResult]],
    *,
    sleep: Callable[[float], Awaitable[None]],
    stable_window: int = 4,
    max_polls: int = 240,
    poll_interval: float = 0.5,
) -> WaitOutcome:
    """Poll `probe` until the assistant reply is complete or `max_polls` is hit.

    Done = not generating AND (no pending image bytes) AND text unchanged for
    `stable_window` consecutive polls. Returns partial text with timed_out=True
    on exhaustion. Never raises for slowness.
    """
    stable = 0
    last_text: str | None = None
    saw_image = False

    for _ in range(max_polls):
        r = await probe()
        if r.image_count > 0:
            saw_image = True

        if r.is_generating or (saw_image and not r.images_ready):
            stable = 0
            last_text = r.text
            await sleep(poll_interval)
            continue

        # No content yet — neither text nor a new image. This covers both the
        # pre-generation blank turn AND the gap after generation ends but before
        # a generated image has rendered (image-gen lags the Stop button). Never
        # mistake an empty turn for a finished reply: keep waiting until real text
        # or an image appears (or the overall timeout fires).
        if not r.text and r.image_count == 0:
            stable = 0
            last_text = r.text
            await sleep(poll_interval)
            continue

        if r.text == last_text:
            stable += 1
        else:
            stable = 0
            last_text = r.text

        if stable >= stable_window:
            return WaitOutcome(text=r.text, timed_out=False, had_image=saw_image)

        await sleep(poll_interval)

    return WaitOutcome(text=last_text or "", timed_out=True, had_image=saw_image)
