"""Tests for Fish Speech TTS wrapper.

Validates graceful degradation when fish-speech is not installed,
and correct behavior of the wrapper API.
"""

import sys
import os
import pytest

# Add server directory to path so we can import modules directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))


class TestFishSpeechTTS:
    """Fish Speech wrapper must not crash even if the package is missing."""

    def test_wrapper_initializes_gracefully(self):
        """Should not crash even if fish-speech not installed."""
        from fish_speech_tts import FishSpeechTTS

        tts = FishSpeechTTS(reference_audio="mario_ref_audio/mario_reference_sentences.wav")
        # Must not raise — graceful init even if lib missing

    def test_is_available_returns_bool(self):
        """is_available() must always return a bool, never crash."""
        from fish_speech_tts import FishSpeechTTS

        tts = FishSpeechTTS(reference_audio="nonexistent.wav")
        result = tts.is_available()
        assert isinstance(result, bool)

    def test_is_available_false_when_no_model(self):
        """Without a valid model/ref audio, is_available should be False."""
        from fish_speech_tts import FishSpeechTTS

        tts = FishSpeechTTS(reference_audio="nonexistent_file_that_does_not_exist.wav")
        assert tts.is_available() is False

    def test_synthesize_returns_none_when_unavailable(self):
        """synthesize() returns None when engine is not available."""
        import asyncio
        from fish_speech_tts import FishSpeechTTS

        tts = FishSpeechTTS(reference_audio="nonexistent.wav")
        result = asyncio.run(tts.synthesize("Hello"))
        assert result is None

    def test_device_parameter_accepted(self):
        """Constructor accepts device parameter without error."""
        from fish_speech_tts import FishSpeechTTS

        tts_cpu = FishSpeechTTS(reference_audio="test.wav", device="cpu")
        tts_cuda = FishSpeechTTS(reference_audio="test.wav", device="cuda")
        assert not tts_cpu.is_available()
        assert not tts_cuda.is_available()

    def test_engine_name(self):
        """Wrapper exposes its engine name."""
        from fish_speech_tts import FishSpeechTTS

        tts = FishSpeechTTS(reference_audio="test.wav")
        assert tts.engine_name == "fish_speech"
