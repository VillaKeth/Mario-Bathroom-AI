import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))
import tts


def test_display_sentences_are_verbatim_substrings():
    text = "First sentence here! Second one follows. And a third, with a comma?"
    sents = tts.split_display_sentences(text)
    assert len(sents) == 3
    cursor = 0
    for s in sents:
        idx = text.find(s, cursor)
        assert idx >= 0, f"sentence not found verbatim: {s!r}"
        cursor = idx + len(s)


def test_display_split_does_not_preclean():
    # split_into_sentences precleans "..." into ", " — the display splitter must NOT.
    text = "Wait for it... here it comes! Another sentence right here."
    joined = " ".join(tts.split_display_sentences(text))
    assert "..." in joined


def test_short_fragments_merge():
    text = "Yes! No! Okay fine, party people. And here is a second proper sentence for the test."
    sents = tts.split_display_sentences(text)
    assert len(sents) == 2
    assert sents[0].startswith("Yes! No!")  # shorts merged forward, not standalone
    assert all(len(s) >= 15 for s in sents)


def test_build_stream_chunks_pairs_display_and_tts():
    text = "The party is amazing tonight everyone! Let me tell you a longer story about it."
    chunks = tts.build_stream_chunks(text)
    assert len(chunks) == 2
    for c in chunks:
        assert c["display"].strip() and c["tts"].strip()


def test_emoji_only_sentence_merges_into_next_display():
    # The emoji run is ≥15 chars so it survives the short-chunk merge as its own
    # sentence, then cleans to empty TTS — exercising the carry-merge path.
    text = "Here is the first real sentence of all! " + "🎉" * 20 + "! And here is the second real one."
    chunks = tts.build_stream_chunks(text)
    # No chunk may have empty tts; all display text must survive, in order.
    assert all(c["tts"].strip() for c in chunks)
    combined = " ".join(c["display"] for c in chunks)
    assert "first real sentence" in combined and "second real one" in combined


def test_single_sentence_yields_single_chunk():
    chunks = tts.build_stream_chunks("Just one single sentence for the bubble tonight.")
    assert len(chunks) == 1
