import sys, os, types
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "client"))
from mario_display import MarioDisplay


def make_stub(text):
    d = types.SimpleNamespace()
    d._typewriter_text = text
    d._typewriter_pos = 0
    d._typewriter_speed = 2
    d._typewriter_audio_synced = False
    d._typewriter_span_target = None
    d._span_search_pos = 0
    d._span_stale_frames = 0
    d._speaking = True
    d.current_text = ""
    d._get_typewriter_speed = lambda n: 2  # fallback speed used after stale release
    return d


TEXT = "First sentence right here! Second sentence follows now. Third one ends it all."


def test_prepare_span_stream_holds_at_zero():
    d = make_stub(TEXT)
    MarioDisplay.prepare_span_stream(d)
    for _ in range(30):
        MarioDisplay._update_typewriter(d)
    assert int(d._typewriter_pos) == 0


def test_resolve_span_target_sequential():
    d = make_stub(TEXT)
    MarioDisplay.prepare_span_stream(d)
    t1 = MarioDisplay.resolve_span_target(d, "First sentence right here!")
    t2 = MarioDisplay.resolve_span_target(d, "Second sentence follows now.")
    assert t1 == len("First sentence right here!")
    assert t2 > t1
    assert TEXT[:t2].endswith("Second sentence follows now.")


def test_resolve_span_target_duplicate_sentences_advance():
    text = "Go go go, party people! Go go go, party people! The end of it all."
    d = make_stub(text)
    MarioDisplay.prepare_span_stream(d)
    t1 = MarioDisplay.resolve_span_target(d, "Go go go, party people!")
    t2 = MarioDisplay.resolve_span_target(d, "Go go go, party people!")
    assert t2 > t1


def test_resolve_span_target_miss_falls_back():
    d = make_stub(TEXT)
    MarioDisplay.prepare_span_stream(d)
    t = MarioDisplay.resolve_span_target(d, "totally different words that are absent")
    assert 0 < t <= len(TEXT)


def test_span_paces_and_holds():
    d = make_stub(TEXT)
    MarioDisplay.prepare_span_stream(d)
    target = MarioDisplay.resolve_span_target(d, "First sentence right here!")
    MarioDisplay.set_typewriter_span(d, target, 2.0)
    for _ in range(100):  # ~3.3s of frames — past the 2s clip, below the 8s stale release
        MarioDisplay._update_typewriter(d)
    assert int(d._typewriter_pos) == target  # held exactly at the span end


def test_span_is_monotonic():
    d = make_stub(TEXT)
    MarioDisplay.prepare_span_stream(d)
    MarioDisplay.set_typewriter_span(d, 56, 3.0)
    for _ in range(5):  # pos still climbing, well below 56
        MarioDisplay._update_typewriter(d)
    assert 0 < d._typewriter_pos < 56
    MarioDisplay.set_typewriter_span(d, 10, 3.0)  # stale lower target arrives mid-climb
    for _ in range(200):
        MarioDisplay._update_typewriter(d)
    # Reveal still reaches the higher target — not frozen at the stale lower one.
    assert int(d._typewriter_pos) == 56


def test_stale_span_releases_after_8s():
    d = make_stub(TEXT)
    MarioDisplay.prepare_span_stream(d)
    target = MarioDisplay.resolve_span_target(d, "First sentence right here!")
    MarioDisplay.set_typewriter_span(d, target, 0.5)
    for _ in range(1000):  # reach target, then sit stale well past 240 frames
        MarioDisplay._update_typewriter(d)
    assert d._typewriter_span_target is None          # limit released
    assert d._typewriter_pos > target                 # fallback speed resumed


def test_resolve_miss_on_earlier_text_never_moves_cursor_backward():
    text = "Go team go! Second sentence here. Third sentence ends."
    d = make_stub(text)
    MarioDisplay.prepare_span_stream(d)
    MarioDisplay.resolve_span_target(d, "Go team go!")
    t2 = MarioDisplay.resolve_span_target(d, "Second sentence here.")
    # Needle found only BEFORE the cursor (already consumed): the retry-from-0
    # path hits the early occurrence, but the search cursor must never regress —
    # a regressed cursor resolves later spans behind the reveal and stalls the
    # bubble until the 8s stale release.
    t3 = MarioDisplay.resolve_span_target(d, "Go team go!")
    assert t3 == len("Go team go!")  # return value is still the found end
    assert d._span_search_pos >= t2  # cursor did not move backward
    # The next real sentence still resolves forward to the end of the text.
    assert MarioDisplay.resolve_span_target(d, "Third sentence ends.") == len(text)


def test_legacy_path_without_spans_reveals_fully():
    d = make_stub(TEXT)  # span target stays None — every non-streamed reply runs this path
    for _ in range(300):
        MarioDisplay._update_typewriter(d)
    assert int(d._typewriter_pos) == len(TEXT)
    assert d.current_text == TEXT


def test_wav_duration_from_header():
    import io, wave, struct
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "client"))
    import audio_playback
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(24000)
        wf.writeframes(struct.pack("<h", 0) * 24000)  # exactly 1.0s of silence
    dur = audio_playback.wav_duration_s(buf.getvalue())
    assert abs(dur - 1.0) < 0.02


def test_wav_duration_garbage_falls_back():
    import audio_playback
    dur = audio_playback.wav_duration_s(b"RIFFgarbage-not-a-real-wav" * 100)
    assert dur > 0
