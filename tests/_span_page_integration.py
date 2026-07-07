"""Manual integration check: audio-gated spans drive REAL bubble pagination.

Simulates the exact client flow for a 6-sentence streamed reply: text lands
(prepare_span_stream holds the typewriter), then each sentence's "clip" starts
(resolve_span_target + set_typewriter_span) and frames advance. Asserts the
bubble page NEVER runs ahead of the spoken span and that it flips forward as
later sentences play. Exits 0 on success, 1 on failure (prints evidence).

Run: venv\\Scripts\\python tests\\_span_page_integration.py
"""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")  # no window needed
import pygame  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "client"))
from mario_display import MarioDisplay  # noqa: E402

SENTENCES = [
    "Let me tell you the whole story of the greatest adventure of my life!",
    "It started on a Tuesday when the bathroom door refused to open for anyone.",
    "I gathered every guest at the party and we formed a heroic rescue squad.",
    "We battled brave and true through puddles, plungers, and questionable smells.",
    "At the very end the door swung open and the crowd went absolutely wild.",
    "And that is why they still call me the legend of the porcelain kingdom!",
]
FULL = " ".join(SENTENCES)
CLIP_SECONDS = 3.0
FRAMES_PER_CLIP = int(CLIP_SECONDS * 30)

pygame.init()
d = MarioDisplay()
d.init()
d.connected = True

failures = []

d.set_mario_text(FULL)
d._speaking = True
d.prepare_span_stream()

# Hold phase: no audio started yet — nothing may reveal.
for f in range(30):
    d._frame = f
    d._update_typewriter()
    d._draw()
if int(d._typewriter_pos) != 0:
    failures.append(f"hold violated: pos={d._typewriter_pos} before any clip started")

frame = 30
page_seen = []
for i, sent in enumerate(SENTENCES):
    target = d.resolve_span_target(sent)
    d.set_typewriter_span(target, CLIP_SECONDS)
    for _ in range(FRAMES_PER_CLIP):
        frame += 1
        d._frame = frame
        d._update_typewriter()
        d._draw()
        # Core gate: reveal must never pass the current span target.
        if d._typewriter_pos > target + 0.001:
            failures.append(
                f"gate violated during clip {i}: pos={d._typewriter_pos} > target={target}")
            break
    if int(d._typewriter_pos) != target:
        failures.append(
            f"clip {i}: pos={int(d._typewriter_pos)} did not reach its span target={target}")
    page_seen.append(d._current_page)
    print(f"clip {i}: span_end={target:4d}  page={d._current_page}  "
          f"pages_total={len(d._text_pages)}")

if len(d._text_pages) < 2:
    failures.append(
        f"text produced only {len(d._text_pages)} page(s) — enlarge FULL to force pagination")
if page_seen[-1] <= page_seen[0]:
    failures.append(f"page never advanced: first-clip page={page_seen[0]}, last={page_seen[-1]}")
if sorted(page_seen) != page_seen:
    failures.append(f"page went backward: {page_seen}")
if int(d._typewriter_pos) != len(FULL):
    failures.append(f"final reveal incomplete: {int(d._typewriter_pos)}/{len(FULL)}")

pygame.quit()
if failures:
    print("FAIL")
    for f in failures:
        print(" -", f)
    sys.exit(1)
print(f"OK — pages advanced with speech: {page_seen}, total_pages={len(d._text_pages)}")
sys.exit(0)
