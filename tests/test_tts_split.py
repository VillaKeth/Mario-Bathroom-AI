import sys, os, io, wave
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))
import tts


def test_split_keeps_all_content():
    txt = "First sentence here. Second sentence is a bit longer than before! Third one. " * 3
    segs = tts._split_text_for_tts(txt, 120)
    assert all(len(s) <= 120 for s in segs)
    # No content dropped: concatenated alnum chars match original alnum chars.
    j = "".join(segs)
    assert "".join(c for c in j if c.isalnum()) == "".join(c for c in txt if c.isalnum())


def test_split_short_text_single():
    assert tts._split_text_for_tts("Hi there!", 120) == ["Hi there!"]


def _mk_wav(nframes=8000):
    b = io.BytesIO()
    with wave.open(b, 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
        w.writeframes(b"\x00\x01" * nframes)
    return b.getvalue()


def test_concat_wavs_sums_frames():
    a, b = _mk_wav(8000), _mk_wav(4000)
    out = tts._concat_wav_bytes([a, b])
    with wave.open(io.BytesIO(out), 'rb') as r:
        assert r.getnframes() == 12000
    assert tts._concat_wav_bytes([a]) == a
    assert tts._concat_wav_bytes([]) == b""
