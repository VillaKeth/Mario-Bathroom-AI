"""Tests for the audio-energy gate in speaker_id (F5).

A near-silent / no-speech chunk must not produce a voice match or enrollment.
These test the pure RMS helpers and need no VoiceEncoder model.
"""
import sys
import os
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

import speaker_id  # noqa: E402


def _pcm(samples):
    return np.asarray(samples, dtype=np.int16).tobytes()


def test_audio_rms_of_silence_is_zero():
    assert speaker_id._audio_rms(_pcm([0] * 16000)) == 0.0


def test_audio_rms_of_loud_signal_is_large():
    rms = speaker_id._audio_rms(_pcm([8000, -8000] * 8000))
    assert rms > 1000.0


def test_audio_rms_empty_bytes_is_zero():
    assert speaker_id._audio_rms(b"") == 0.0


def test_has_speech_energy_rejects_silence():
    assert speaker_id._has_speech_energy(_pcm([0] * 16000)) is False


def test_has_speech_energy_accepts_normal_speech_level():
    # ~600 RMS is a quiet-but-real speech level; must pass the gate.
    assert speaker_id._has_speech_energy(_pcm([600, -600] * 8000)) is True


def test_has_speech_energy_respects_explicit_floor():
    sig = _pcm([300, -300] * 8000)  # RMS ~300
    assert speaker_id._has_speech_energy(sig, min_rms=100) is True
    assert speaker_id._has_speech_energy(sig, min_rms=1000) is False
