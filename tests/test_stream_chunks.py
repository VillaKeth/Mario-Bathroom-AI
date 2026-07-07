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
    # sentence. NOTE: it does NOT exercise the carry-merge path — the trailing
    # "!" means analyze_text cleans it to a lone "!" (non-empty TTS), so it stays
    # a chunk of its own. What this pins: no chunk ends up with empty or
    # emoji-garbage TTS, and all display text survives, in order.
    text = "Here is the first real sentence of all! " + "🎉" * 20 + "! And here is the second real one."
    chunks = tts.build_stream_chunks(text)
    assert all(c["tts"].strip() for c in chunks)
    assert all("🎉" not in c["tts"] for c in chunks)
    combined = " ".join(c["display"] for c in chunks)
    assert "first real sentence" in combined and "second real one" in combined


def test_single_sentence_yields_single_chunk():
    chunks = tts.build_stream_chunks("Just one single sentence for the bubble tonight.")
    assert len(chunks) == 1


def test_trailing_emoji_run_display_survives_with_nonempty_tts():
    # A bare trailing emoji run (≥15 chars, no punctuation) splits off as the
    # final buffer and stays a sentence of its own. Verified path: it does NOT
    # take build_stream_chunks' carry-merge branch — analyze_text cleans it to
    # empty internally, then its own fallback ("tts_text if tts_text else text")
    # returns the RAW emoji run, so the chunk's tts is the emoji run itself
    # (non-empty). Downstream, synthesize_user's preclean empties it and returns
    # the emergency-silence WAV (4454 bytes > the 44-byte send gate), so the
    # chunk still ships with its display text and nothing garbled is spoken.
    # Pin the wire contract: every chunk has non-empty tts, the emoji display
    # text is not dropped, and it stays in order at the end.
    text = "First real sentence here tonight! Second real sentence lands after it. " + "🎉" * 20
    chunks = tts.build_stream_chunks(text)
    assert all(c["tts"].strip() for c in chunks)
    assert "🎉" in chunks[-1]["display"]  # emoji display text not dropped
    combined = " ".join(c["display"] for c in chunks)
    assert "First real sentence" in combined and "Second real sentence" in combined


def test_short_trailing_emoji_run_merges_into_last_sentence():
    # The realistic case: a reply ending in one or two emoji. The <15-char
    # trailing buffer merges into the last sentence inside the SPLITTER itself
    # (before analyze_text ever runs), so the emoji rides along in that chunk's
    # display while analyze_text strips it from the spoken tts. No standalone
    # emoji sentence — and no carry — is ever created for short runs.
    text = "First real sentence here tonight! Second real sentence lands after it. 🎉🎉"
    chunks = tts.build_stream_chunks(text)
    assert len(chunks) == 2
    assert "🎉" in chunks[-1]["display"]
    assert chunks[-1]["tts"].strip() and "🎉" not in chunks[-1]["tts"]


def test_newline_separator_survives_analyze_chain_findable():
    # Regression (reviewer find): a lone "\n" between sentences survives
    # analyze_text's display cleanup (its collapse only catches \s{2,}), so the
    # short-fragment merge must keep the REAL separator — a hardcoded " "
    # makes the merged chunk unfindable in the bubble text and breaks the
    # client's text.find() audio-gating.
    from pose_analyzer import analyze_text
    text = "Yes!\nNo! Okay fine, party people. And here is a second proper sentence for the test."
    disp = analyze_text(text)["display_text"]
    chunks = tts.build_stream_chunks(disp)
    assert "\n" in chunks[0]["display"]  # real separator preserved, not " "
    cursor = 0
    for c in chunks:
        idx = disp.find(c["display"], cursor)
        assert idx >= 0, f"chunk not verbatim-findable: {c['display']!r}"
        cursor = idx + len(c["display"])


def test_tab_separator_merged_chunk_stays_verbatim():
    # Same bug, "\t" flavor — straight through the splitter.
    text = "Ha!\tThat was a good one, friend. And here is the second full sentence for it."
    sents = tts.split_display_sentences(text)
    assert len(sents) == 2
    assert "\t" in sents[0]
    cursor = 0
    for s in sents:
        idx = text.find(s, cursor)
        assert idx >= 0, f"sentence not verbatim: {s!r}"
        cursor = idx + len(s)
