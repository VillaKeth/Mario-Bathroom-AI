import io
import wave

import numpy as np

from client.audio_playback import analyze_wav, AudioPlayback


def _wav(sr=32000, secs=0.5, amp=0.5):
    n = int(sr * secs)
    samples = (np.ones(n) * amp * 32767).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(samples.tobytes())
    return buf.getvalue()


def test_analyze_reports_sr_duration_peak_rms():
    a = analyze_wav(_wav(sr=32000, secs=0.5, amp=0.5))
    assert a["sample_rate"] == 32000
    assert abs(a["duration_s"] - 0.5) < 0.02
    assert 0.45 < a["peak"] <= 0.51
    assert a["engine_guess"] == "sovits"   # 32000 Hz


def test_analyze_engine_guess_edge_at_24k():
    assert analyze_wav(_wav(sr=24000))["engine_guess"] == "edge"


def test_ring_records_clips_newest_last():
    ap = AudioPlayback()
    ap._record_clip(_wav(), text="first")
    ap._record_clip(_wav(), text="second")
    snap = ap.audio_log_snapshot(n=5)
    assert [c["text"] for c in snap] == ["first", "second"]
    assert snap[-1]["played_ok"] is True
