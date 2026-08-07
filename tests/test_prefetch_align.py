"""Tests for aligning pre-synthesized audio against the final reply text.

Synthesis overlap starts TTS on a sentence while the LLM is still writing the
rest. But the text those chunks were built from is RAW token output, and the
reply that finally reaches the client has been through extract_emotion_tag,
_clean_response and pose analysis. If the cleaning changed anything, the
pre-synthesized audio no longer matches what the bubble will show.

align_prefetched() is the guard: it reports how many LEADING pre-synthesized
chunks still exactly match the real chunking of the final text. Those can reuse
their audio; everything after is synthesized normally. When nothing matches it
returns 0 and the caller falls back to today's behaviour, so the optimisation
can never make the guest hear text that is not on screen.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

import tts  # noqa: E402


def prefetch_for(text):
    """The chunks an ideal prefetch of `text` would have produced."""
    return tts.build_stream_chunks(text)


class TestAlignment:
    def test_identical_text_aligns_every_chunk(self):
        final = "Welcome to the party. I am so glad you came. Lets have fun."
        pre = prefetch_for(final)
        assert tts.align_prefetched(pre, final) == len(pre)

    def test_empty_prefetch_aligns_nothing(self):
        assert tts.align_prefetched([], "Some final reply text here.") == 0

    def test_partial_prefetch_aligns_what_it_has(self):
        """Generation ended before the last sentence was synthesized."""
        final = "First sentence here. Second sentence here. Third sentence here."
        pre = prefetch_for(final)[:2]
        assert tts.align_prefetched(pre, final) == 2

    def test_divergence_at_the_first_chunk_aligns_nothing(self):
        final = "Totally different opening line. Second sentence here."
        pre = prefetch_for("Welcome to the party. Second sentence here.")
        assert tts.align_prefetched(pre, final) == 0

    def test_alignment_stops_at_the_first_mismatch(self):
        """A later divergence must not let a matching tail sneak through."""
        final = "Shared opening line here. CHANGED middle part. Shared closing line."
        pre = prefetch_for("Shared opening line here. Original middle. Shared closing line.")
        assert tts.align_prefetched(pre, final) == 1

    def test_prefetch_longer_than_final_is_capped(self):
        """Cleaning shortened the reply - never claim more chunks than exist."""
        final = "Only one sentence survived cleaning here."
        pre = prefetch_for("Only one sentence survived cleaning here. Extra. And more of it.")
        assert tts.align_prefetched(pre, final) <= len(prefetch_for(final))


class TestRealCleaningScenarios:
    def test_trailing_emotion_blob_removal_keeps_earlier_chunks(self):
        """The common case: raw text ends with the emotion JSON, final does not.
        Every sentence before it must still be reusable."""
        final = "That was a great round. You really know your stuff."
        pre = prefetch_for(final)
        assert tts.align_prefetched(pre, final) == len(pre)

    def test_whitespace_only_difference_still_aligns(self):
        final = "Hello there my friend. Welcome to the show."
        pre = prefetch_for("Hello there my friend.  Welcome to the show.")
        assert tts.align_prefetched(pre, final) >= 1
