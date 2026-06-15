"""Tests for speaker_id graceful-degrade paths.

These deliberately exercise the NO-encoder path (resemblyzer absent OR
init_speaker_id() not yet called) so they run in any environment without
loading the VoiceEncoder model. We do NOT call init_speaker_id() here, so
`_encoder` stays None and is_available() returns False — the exact state the
live server degrades into when resemblyzer is missing.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

import speaker_id  # noqa: E402


def test_is_available_returns_bool_and_does_not_raise():
    """is_available() must return a plain bool and never raise, even when the
    encoder has not been initialized."""
    result = speaker_id.is_available()
    assert isinstance(result, bool)


def test_is_available_false_without_encoder():
    """With no init_speaker_id() call, _encoder is None -> not available."""
    # Guard against test-order side effects: if some other test initialized the
    # encoder, this assertion is skipped rather than failing spuriously.
    if speaker_id._encoder is None:
        assert speaker_id.is_available() is False


def test_identify_speaker_graceful_when_not_initialized():
    """identify_speaker() on an uninitialized encoder returns a graceful dict
    with is_new=True instead of raising."""
    if speaker_id._encoder is not None:
        # Encoder somehow loaded (another test) — the graceful path under test
        # only applies when it's None, so skip to avoid a real model call.
        import pytest
        pytest.skip("encoder initialized; graceful-degrade path not applicable")

    result = speaker_id.identify_speaker(b"\x00\x00" * 8000)
    assert isinstance(result, dict)
    assert result["is_new"] is True
    assert result["name"] is None
    assert result["speaker_id"] is None
    assert result["confidence"] == 0.0
