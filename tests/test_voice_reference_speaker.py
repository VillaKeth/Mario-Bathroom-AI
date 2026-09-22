"""The reference clip must be the CHARACTER, not whoever else is on the tape.

charlie_kirk shipped for weeks with a reference_audio.wav containing six seconds
of the interviewer asking Kirk a question. GPT-SoVITS conditions every synthesis
on that clip, so every render, every A/B and every quality judgement built on
them was conditioned on the wrong speaker.

Two code paths can produce that, and neither checked who was talking:
  - the wizard concatenates the user's cropped sections verbatim
  - _trim_reference picks the LOUDEST 8s window, and a studio-mic host is
    routinely louder than a remote guest, so loudness selects for the intruder

These tests pin the fix. The speaker scorer is injected rather than real, so
they run without resemblyzer, a GPU, or two-speaker fixtures.
"""
import os
import struct
import wave

import pytest

from character_creator import voice_trainer as vt


def _write_wav(path, blocks, sr=32000):
    """blocks: list of (seconds, amplitude). Writes a 16-bit mono wav."""
    frames = bytearray()
    for secs, amp in blocks:
        n = int(sr * secs)
        for i in range(n):
            # alternating sign gives a nonzero RMS without needing numpy here
            frames += struct.pack("<h", int(amp * 32767) * (1 if i % 2 else -1))
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(bytes(frames))
    return path


def test_trim_prefers_matching_speaker_over_louder_intruder(tmp_path, monkeypatch):
    """The loud stretch is the wrong speaker; the quieter one is the character.

    Pure argmax-over-energy picks the intruder. The fix must not.
    """
    voice = tmp_path / "voice"
    voice.mkdir()
    # 0-9s loud (intruder), 9-20s quieter (the character)
    _write_wav(str(voice / "reference_audio.wav"), [(9.0, 0.9), (11.0, 0.25)])

    picked = {}

    def fake_ffmpeg_cut(src, start, dur, dst):
        picked["start"] = start
        return True

    # scorer: anything starting before 9s is the intruder
    monkeypatch.setattr(vt, "_speaker_scorer",
                        lambda seg_dir: (lambda start, dur: 0.50 if start < 9.0 else 0.95))
    monkeypatch.setattr(vt, "_cut_window", fake_ffmpeg_cut)

    changed = vt._trim_reference(str(voice))
    assert changed is True
    assert picked["start"] >= 9.0, (
        f"picked {picked['start']:.1f}s -- that is the louder intruder, not the character")


def test_trim_falls_back_to_loudest_when_no_scorer(tmp_path, monkeypatch):
    """No dataset or no resemblyzer must not break the wizard -- old behaviour."""
    voice = tmp_path / "voice"
    voice.mkdir()
    _write_wav(str(voice / "reference_audio.wav"), [(9.0, 0.9), (11.0, 0.25)])

    picked = {}
    monkeypatch.setattr(vt, "_speaker_scorer", lambda seg_dir: None)
    monkeypatch.setattr(vt, "_cut_window",
                        lambda src, start, dur, dst: picked.update(start=start) or True)

    assert vt._trim_reference(str(voice)) is True
    assert picked["start"] < 9.0, "with no scorer it should still take the loudest window"


def test_short_reference_is_left_alone(tmp_path, monkeypatch):
    """Under 10s there is nothing to trim -- this is the path charlie_kirk took."""
    voice = tmp_path / "voice"
    voice.mkdir()
    _write_wav(str(voice / "reference_audio.wav"), [(6.6, 0.5)])
    monkeypatch.setattr(vt, "_speaker_scorer", lambda seg_dir: None)
    assert vt._trim_reference(str(voice)) is False


def test_verify_flags_a_wrong_speaker_reference(tmp_path, monkeypatch):
    """verify_reference_speaker reports a verdict the wizard can surface."""
    voice = tmp_path / "voice"
    (voice / "dataset" / "segments").mkdir(parents=True)
    _write_wav(str(voice / "reference_audio.wav"), [(6.0, 0.5)])

    monkeypatch.setattr(vt, "_speaker_scorer",
                        lambda seg_dir: (lambda start, dur: 0.61))
    monkeypatch.setattr(vt, "_speaker_floor", lambda seg_dir: 0.90)

    v = vt.verify_reference_speaker(str(voice))
    assert v["ok"] is False
    assert v["score"] == pytest.approx(0.61)
    assert "floor" in v and v["floor"] == pytest.approx(0.90)
    assert v["reason"]


def test_verify_passes_a_matching_reference(tmp_path, monkeypatch):
    voice = tmp_path / "voice"
    (voice / "dataset" / "segments").mkdir(parents=True)
    _write_wav(str(voice / "reference_audio.wav"), [(6.0, 0.5)])
    monkeypatch.setattr(vt, "_speaker_scorer",
                        lambda seg_dir: (lambda start, dur: 0.94))
    monkeypatch.setattr(vt, "_speaker_floor", lambda seg_dir: 0.90)
    assert vt.verify_reference_speaker(str(voice))["ok"] is True


def test_verify_is_inconclusive_without_a_scorer(tmp_path, monkeypatch):
    """No resemblyzer or no dataset must read as 'unknown', never as 'ok'."""
    voice = tmp_path / "voice"
    voice.mkdir()
    _write_wav(str(voice / "reference_audio.wav"), [(6.0, 0.5)])
    monkeypatch.setattr(vt, "_speaker_scorer", lambda seg_dir: None)
    v = vt.verify_reference_speaker(str(voice))
    assert v["ok"] is None, "unknown must not be reported as a pass"
