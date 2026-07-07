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
    MarioDisplay.set_typewriter_span(d, 40, 0.5)
    for _ in range(120):
        MarioDisplay._update_typewriter(d)
    pos_before = d._typewriter_pos
    MarioDisplay.set_typewriter_span(d, 10, 1.0)  # lower target must not rewind
    MarioDisplay._update_typewriter(d)
    assert d._typewriter_pos >= pos_before


def test_stale_span_releases_after_8s():
    d = make_stub(TEXT)
    MarioDisplay.prepare_span_stream(d)
    target = MarioDisplay.resolve_span_target(d, "First sentence right here!")
    MarioDisplay.set_typewriter_span(d, target, 0.5)
    for _ in range(1000):  # reach target, then sit stale well past 240 frames
        MarioDisplay._update_typewriter(d)
    assert d._typewriter_span_target is None          # limit released
    assert d._typewriter_pos > target                 # fallback speed resumed
