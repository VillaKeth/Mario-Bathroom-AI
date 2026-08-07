"""Tests for the incremental sentence buffer that drives token-streaming TTS.

The non-streamed path waits for the WHOLE LLM reply, then calls
tts.build_stream_chunks() to split it. TokenSentenceBuffer does the same job
incrementally: tokens go in as Ollama produces them, and a chunk comes out the
moment its sentence is provably finished — so the first audio starts while the
model is still writing the rest.

"Provably finished" is the whole point. A '.' alone is not a boundary: the very
next token could be a decimal digit or the rest of an abbreviation. Only
punctuation FOLLOWED BY whitespace settles a sentence, which is exactly the
boundary split_display_sentences uses on the complete text.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

import tts  # noqa: E402


def feed_all(buf, tokens):
    """Feed tokens in order, returning every chunk emitted along the way."""
    out = []
    for t in tokens:
        out.extend(buf.feed(t))
    return out


class TestBoundaryDetection:
    def test_holds_text_until_a_boundary_is_proven(self):
        buf = tts.TokenSentenceBuffer()
        assert feed_all(buf, ["Hey", " there", " friend"]) == []

    def test_trailing_period_alone_is_not_a_boundary(self):
        """'.' with nothing after it could still be a decimal or abbreviation."""
        buf = tts.TokenSentenceBuffer()
        assert feed_all(buf, ["Welcome to the party."]) == []

    def test_emits_sentence_once_whitespace_settles_it(self):
        buf = tts.TokenSentenceBuffer()
        chunks = feed_all(buf, ["Welcome to the party.", " Come on in."])
        assert [c["display"] for c in chunks] == ["Welcome to the party."]

    def test_decimal_number_does_not_split(self):
        buf = tts.TokenSentenceBuffer()
        chunks = feed_all(buf, ["The score is 3.5 points for you now.", " Nice."])
        assert [c["display"] for c in chunks] == ["The score is 3.5 points for you now."]

    def test_emits_multiple_sentences_in_order(self):
        buf = tts.TokenSentenceBuffer()
        chunks = feed_all(buf, ["First one here. Second one here. Third one here.", " x"])
        assert [c["display"] for c in chunks] == [
            "First one here.", "Second one here.", "Third one here."]


class TestShortFragmentMerging:
    def test_short_fragment_merges_forward(self):
        """A bare 'Wow!' is too short to be worth its own synthesis round-trip."""
        buf = tts.TokenSentenceBuffer(min_chars=12)
        chunks = feed_all(buf, ["Wow! That was really something.", " More text here."])
        assert [c["display"] for c in chunks] == ["Wow! That was really something."]

    def test_short_fragment_alone_is_never_emitted_early(self):
        buf = tts.TokenSentenceBuffer(min_chars=12)
        assert feed_all(buf, ["Hi! ", "Ok! "]) == []


class TestEmotionBlobSuppression:
    """The LLM appends a {"emotion": ..., "energy": ...} blob that
    extract_emotion_tag() strips from the final text. Streaming must never
    hand that JSON to TTS - the guest would hear it read aloud."""

    def test_emotion_json_is_not_spoken(self):
        buf = tts.TokenSentenceBuffer()
        chunks = feed_all(buf, [
            'Welcome to the party my friend. ',
            '{"emotion": "happy", "energy": 0.9} ',
            'Lets play a game now. ',
        ])
        spoken = " ".join(c["tts"] for c in chunks)
        assert "emotion" not in spoken
        assert "0.9" not in spoken

    def test_emotion_json_in_flush_is_not_spoken(self):
        buf = tts.TokenSentenceBuffer()
        feed_all(buf, ['That was a great round of trivia. '])
        tail = buf.flush('{"emotion": "excited", "energy": 0.8}')
        assert all("emotion" not in c["tts"] for c in tail)


class TestFlush:
    def test_flush_returns_the_unterminated_tail(self):
        buf = tts.TokenSentenceBuffer()
        feed_all(buf, ["All done here now. ", "and one last thought"])
        assert [c["display"] for c in buf.flush()] == ["and one last thought"]

    def test_flush_is_empty_when_everything_already_emitted(self):
        buf = tts.TokenSentenceBuffer()
        feed_all(buf, ["A complete sentence here. ", "Another one here. "])
        assert buf.flush() == []

    def test_flush_twice_does_not_repeat_the_tail(self):
        buf = tts.TokenSentenceBuffer()
        feed_all(buf, ["trailing words with no stop"])
        assert len(buf.flush()) == 1
        assert buf.flush() == []


class TestVerbatimDisplay:
    """The client locates each chunk's display text inside the bubble string to
    gate the typewriter to real audio. A chunk that is not a verbatim substring
    of the reply is unfindable and desyncs the bubble."""

    def test_every_display_chunk_is_a_substring_of_the_reply(self):
        reply = "Hello there friend. I am so glad you came. Lets have fun tonight."
        buf = tts.TokenSentenceBuffer()
        chunks = feed_all(buf, list(reply)) + buf.flush()
        for c in chunks:
            assert c["display"] in reply

    def test_chunks_concatenate_back_to_the_whole_reply(self):
        reply = "One sentence here. Two sentences here. Three sentences here."
        buf = tts.TokenSentenceBuffer()
        chunks = feed_all(buf, list(reply)) + buf.flush()
        assert " ".join(c["display"] for c in chunks) == reply


class TestSpeakableFiltering:
    def test_chunk_that_cleans_to_nothing_is_not_emitted(self):
        """Emoji-only fragments have no TTS text; they must not produce a
        synthesis call, and their display text must survive into a later chunk
        so the bubble still shows them."""
        buf = tts.TokenSentenceBuffer()
        chunks = feed_all(buf, ["\U0001F604 \U0001F389 ", "Now a real sentence here. ", "x"])
        assert all(c["tts"].strip() for c in chunks)
        assert any("Now a real sentence here." in c["display"] for c in chunks)
