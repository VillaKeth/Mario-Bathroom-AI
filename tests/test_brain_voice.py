import numpy as np

from server.brain import voice as V


def _tone(seconds=0.5, sr=24000, hz=440.0):
    t = np.arange(int(seconds * sr)) / sr
    return V.write_wav(0.5 * np.sin(2 * np.pi * hz * t), sr)


def test_ring_mod_keeps_length_and_rate_and_changes_audio():
    dry = _tone()
    wet = V.ring_mod(dry)
    xd, srd = V.read_wav(dry)
    xw, srw = V.read_wav(wet)
    assert srd == srw == 24000 and len(xd) == len(xw)
    assert not np.allclose(xd, xw, atol=1e-3)
    assert 0.6 < float(np.max(np.abs(xw))) <= 0.72  # peak-normalized to -3 dB


def test_takeoff_buzz_is_valid_and_louder_with_level():
    loud, _ = V.read_wav(V.takeoff_buzz(0.5, level=1.0))
    soft, _ = V.read_wav(V.takeoff_buzz(0.5, level=0.2))
    assert len(loud) == 12000
    assert np.max(np.abs(loud)) > np.max(np.abs(soft)) * 2


def test_speak_caches_dry_edge_audio():
    calls = []

    def edge(text):
        calls.append(text)
        return _tone(0.3)
    fv = V.FlyVoice(edge)
    a = fv.speak("sweet.")
    b = fv.speak("sweet.")
    assert a and b and calls == ["sweet."]


def test_speak_falls_back_to_buzz_when_edge_fails():
    def dead(text):
        raise OSError("no network")
    out = V.FlyVoice(dead).speak("sweet sweet more.")
    x, sr = V.read_wav(out)
    assert sr == 24000 and len(x) > 0


def test_speak_survives_non_wav_bytes():
    out = V.FlyVoice(lambda t: b"ID3\x04 not a wav").speak("yuck.")
    assert V.read_wav(out)[1] == 24000


def test_empty_text_is_silent():
    assert V.FlyVoice(lambda t: _tone()).speak("  ") == b""
