"""Tests for the two-stage voice consistency gate (spec W6)."""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

import recognition_config  # noqa: E402
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


# ---------------------------------------------------------------------------
# Stage B: half-vs-half embedding agreement (server/speaker_id.py:220-236).
#
# Stage A above never calls the encoder, so none of the tests preceding this
# section reach Stage B at all. These tests monkeypatch `speaker_id._encoder`
# with a fake whose `embed_utterance` returns pre-baked vectors keyed to the
# EXACT array each real call site passes -- the first half, the second half,
# or the whole processed signal -- so the real halving / dot-product /
# threshold code inside `get_embedding` runs untouched; only the expensive DNN
# forward pass is replaced. Dispatch is by VALUE (np.array_equal against arrays
# precomputed with the identical arithmetic `get_embedding` itself performs),
# not by call order, so a bug that reuses one half for both embeddings (instead
# of embedding each half) changes which vectors get compared instead of
# silently matching. `preprocess_wav` is monkeypatched to an identity
# passthrough so the sample count reaching the halving logic is exactly the
# fixture's raw tone rescaled to float -- otherwise resemblyzer's own VAD
# trimming would make the post-preprocessing length unpredictable.
#
# All audio fixtures below are `_tone(221, ...)` -- 221 Hz rather than the 220 Hz
# used above, only so that frequency * half-duration is never a whole number of
# cycles (see _rig's identical-halves guard); otherwise the same clean tonal
# signal already proven above (test_stage_a_accepts_tonal_signal) to clear
# Stage A. Each test also asserts stage_a_ok() directly on its own fixture as a
# precondition, so a future Stage A retune that starts rejecting these fixtures
# fails loudly here instead of masquerading as a Stage B result.
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _fresh_recognition_config():
    """recognition_config caches tunables process-wide (module-global `_cache`),
    so a monkeypatched override left behind by another test file could otherwise
    leak into these tau-dependent outcomes. Mirrors the identical fixture in
    tests/test_recognition_margin.py: force a clean read of the real config.json
    (which sets neither voice_consistency_tau nor voice_max_flatness) before and
    after every test in this section.
    """
    recognition_config.reset_cache()
    yield
    recognition_config.reset_cache()


def _identity_preprocess(wav, source_sr=None):
    """Stand-in for resemblyzer.preprocess_wav: no resample, no VAD trim, so the
    test controls the exact sample count that reaches Stage B's halving logic."""
    return wav


PROBE = np.array([1.0, 0.0])


def _vec_at_similarity(similarity):
    """Unit 2D vector whose cosine similarity to PROBE=(1, 0) is exactly `similarity`
    (mirrors the identically-named helper in tests/test_recognition_margin.py)."""
    similarity = float(similarity)
    return np.array([similarity, (1.0 - similarity ** 2) ** 0.5])


VEC_FULL = np.array([0.123, 0.456])  # arbitrary marker vector: "the whole-signal embedding"


class _FakeEncoder:
    """Returns a pre-baked vector keyed to which real array it is asked to embed.

    Dispatch is by VALUE against the exact arrays the test precomputes, not by
    call order or object identity -- so a bug that embeds the same half twice,
    or that skips straight to the full signal, lands on a different branch (or
    none, raising) instead of silently matching. `self.calls` records the
    matched label in call order, so a test can also assert Stage B ran (or was
    skipped) rather than only checking the final accept/reject outcome.
    """

    def __init__(self, mapping):
        self._mapping = mapping  # list of (expected_array, vector_to_return, label)
        self.calls = []

    def embed_utterance(self, wav, return_partials=False, rate=1.3, min_coverage=0.75):
        for expected, vector, label in self._mapping:
            if wav.shape == expected.shape and np.array_equal(wav, expected):
                self.calls.append(label)
                return np.asarray(vector, dtype=np.float64)
        raise AssertionError(
            f"_FakeEncoder.embed_utterance got an array matching none of the "
            f"expected slices (len={len(wav)}) -- Stage B's halving logic changed"
        )


def _rig(monkeypatch, samples_int16, vec_first, vec_second, vec_full=VEC_FULL):
    """Wire the fake encoder + identity preprocessing for one get_embedding() call.

    Returns the fake encoder so the caller can also assert on `.calls`.
    """
    assert speaker_id.stage_a_ok(samples_int16) is True, (
        "fixture must clear Stage A, or this test proves nothing about Stage B"
    )
    full = samples_int16.astype(np.float32) / 32768.0  # exactly get_embedding's own arithmetic
    half = len(full) // 2
    first, second = full[:half], full[half:]
    assert not np.array_equal(first, second), (
        "fixture's two halves are numerically identical (a pure tone whose "
        "frequency times the half-duration is a whole number of cycles repeats "
        "exactly at the midpoint) -- _FakeEncoder cannot tell them apart by "
        "value, so this fixture cannot exercise Stage B at all. Pick a "
        "frequency/duration pair where freq * half_seconds is not an integer."
    )

    fake = _FakeEncoder([
        (first, vec_first, "first"),
        (second, vec_second, "second"),
        (full, vec_full, "full"),
    ])
    monkeypatch.setattr(speaker_id, "_encoder", fake)
    monkeypatch.setattr(speaker_id, "preprocess_wav", _identity_preprocess)
    return fake


def test_stage_b_rejects_when_halves_disagree(monkeypatch):
    """Below-tau half agreement -> get_embedding returns None (default tau=0.60).

    Catches: comparison inverted (agreement 0.30 would then NOT be rejected);
    a half-embedded-twice bug (self-agreement is always 1.0, so it would wrongly
    accept instead of reject).
    """
    samples = _tone(221, seconds=3.0)  # 221, not 220: see _rig's identical-halves guard
    fake = _rig(monkeypatch, samples, vec_first=PROBE, vec_second=_vec_at_similarity(0.30))

    result = speaker_id.get_embedding(samples.tobytes())

    assert result is None
    assert fake.calls == ["first", "second"]  # rejected before the final full-signal embed


def test_stage_b_accepts_when_halves_agree(monkeypatch):
    """Above-tau half agreement -> get_embedding returns the real embedding.

    Catches: comparison inverted (agreement 0.99 would then be wrongly rejected).
    """
    samples = _tone(221, seconds=3.0)  # 221, not 220: see _rig's identical-halves guard
    fake = _rig(monkeypatch, samples, vec_first=PROBE, vec_second=_vec_at_similarity(0.99))

    result = speaker_id.get_embedding(samples.tobytes())

    assert result is not None
    assert np.array_equal(result, VEC_FULL)
    assert fake.calls == ["first", "second", "full"]


def test_stage_b_short_half_is_accepted_not_rejected(monkeypatch):
    """A half under 1.0s is a SKIP, not a rejection -- a short clean utterance
    (e.g. an enrollment clip) must not be treated as evidence of two speakers.

    The halves are engineered to DISAGREE (agreement 0.0): if a future change
    ever removed or broke the 1.0s length guard, Stage B would run on them and
    reject, flipping this test's outcome and catching the mutation.
    """
    samples = _tone(221, seconds=1.5)  # 24000 samples -> each half is 12000 (0.75s) < 16000
    fake = _rig(monkeypatch, samples, vec_first=PROBE, vec_second=_vec_at_similarity(0.0))

    result = speaker_id.get_embedding(samples.tobytes())

    assert result is not None
    assert np.array_equal(result, VEC_FULL)
    assert fake.calls == ["full"]  # Stage B never ran -- first/second were never queried


def test_stage_b_reads_tau_from_config_not_hardcoded(monkeypatch):
    """tau must come from recognition_config.get("voice_consistency_tau") live,
    not a hardcoded literal, or Task 8's curve-based retuning would silently not
    take effect.

    Raises tau to 0.95 (from the code default 0.60) and engineers agreement at
    0.80 -- ABOVE the code default but BELOW the raised value. Any hardcoded
    threshold (0.60, or anything else <= 0.80) would wrongly accept; only a
    live config read rejects, as asserted here.
    """
    orig_get = recognition_config.get

    def fake_get(name):
        if name == "voice_consistency_tau":
            return 0.95
        return orig_get(name)

    monkeypatch.setattr(recognition_config, "get", fake_get)

    samples = _tone(221, seconds=3.0)  # 221, not 220: see _rig's identical-halves guard
    fake = _rig(monkeypatch, samples, vec_first=PROBE, vec_second=_vec_at_similarity(0.80))

    result = speaker_id.get_embedding(samples.tobytes())

    assert result is None
    assert fake.calls == ["first", "second"]
