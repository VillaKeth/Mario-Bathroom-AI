"""Tests for the two-stage voice consistency gate (spec W6)."""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

import speaker_id  # noqa: E402

RATE = 16000


def _tone(freq, seconds=3.0, amp=8000):
    t = np.arange(int(RATE * seconds)) / RATE
    return (amp * np.sin(2 * np.pi * freq * t)).astype(np.int16)


def _white_noise(seconds=3.0, amp=8000):
    return (np.random.default_rng(7).normal(0, amp, int(RATE * seconds))).astype(np.int16)


def test_spectral_flatness_noise_is_high():
    assert speaker_id.spectral_flatness(_white_noise().astype(np.float64)) > 0.4


def test_spectral_flatness_tone_is_low():
    assert speaker_id.spectral_flatness(_tone(220).astype(np.float64)) < 0.1


def test_stage_a_rejects_white_noise():
    assert speaker_id.stage_a_ok(_white_noise()) is False


def test_stage_a_accepts_tonal_signal():
    assert speaker_id.stage_a_ok(_tone(220)) is True


def test_stage_a_rejects_mostly_silent_chunk():
    chunk = _tone(220)
    chunk[len(chunk) // 3:] = 0          # only the first third has energy
    assert speaker_id.stage_a_ok(chunk) is False
