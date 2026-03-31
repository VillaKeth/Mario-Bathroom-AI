"""Tests for TTS Router and Catchphrase Bank.

Validates fallback chain ordering, stats tracking,
sentence splitting, and catchphrase normalization/matching.
"""

import sys
import os
import asyncio
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))


class TestCatchphraseBank:
    """Catchphrase normalization and matching logic."""

    def test_normalize_strips_punctuation(self):
        from catchphrase_bank import CatchphraseBank

        bank = CatchphraseBank()
        assert bank.normalize("Wahoo!") == "wahoo"
        assert bank.normalize("WAHOO!!!") == "wahoo"
        assert bank.normalize("Let's-a go!") == "lets-a go"
        assert bank.normalize("It's-a me, Mario!") == "its-a me mario"

    def test_normalize_preserves_hyphens(self):
        from catchphrase_bank import CatchphraseBank

        bank = CatchphraseBank()
        assert bank.normalize("lets-a go") == "lets-a go"

    def test_normalize_strips_extra_whitespace(self):
        from catchphrase_bank import CatchphraseBank

        bank = CatchphraseBank()
        assert bank.normalize("  wahoo  ") == "wahoo"
        assert bank.normalize("mama   mia") == "mama mia"

    def test_match_returns_none_for_unknown(self):
        from catchphrase_bank import CatchphraseBank

        bank = CatchphraseBank()
        assert bank.match("random sentence here") is None
        assert bank.match("The weather is nice today") is None

    def test_match_returns_none_for_long_text(self):
        from catchphrase_bank import CatchphraseBank

        bank = CatchphraseBank()
        assert bank.match("This is a very long sentence that is definitely not a catchphrase") is None

    def test_match_returns_bytes_for_known_catchphrase_with_file(self, tmp_path):
        """When a WAV file exists for a catchphrase, match returns bytes."""
        import wave
        import struct

        from catchphrase_bank import CatchphraseBank

        # Create a minimal WAV file
        wav_path = tmp_path / "wahoo.wav"
        with wave.open(str(wav_path), "w") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(22050)
            wf.writeframes(struct.pack("<h", 0) * 100)

        bank = CatchphraseBank(assets_dir=str(tmp_path))
        result = bank.match("Wahoo!")
        assert result is not None
        assert isinstance(result, bytes)
        assert len(result) > 44  # WAV header + some data

    def test_catchphrase_list_has_expected_entries(self):
        from catchphrase_bank import CatchphraseBank

        bank = CatchphraseBank()
        expected = ["wahoo", "mama mia", "lets-a go", "its-a me mario", "yahoo", "okie dokie", "here we go"]
        for phrase in expected:
            assert phrase in bank.CATCHPHRASES


class TestTTSRouter:
    """TTS Router fallback chain, stats, and sentence splitting."""

    def test_fallback_chain_order(self):
        from tts_router import TTSRouter, TTSEngine

        router = TTSRouter()
        e1 = TTSEngine(name="fast", synthesize_fn=lambda t, **kw: b"audio", is_available_fn=lambda: True, priority=1)
        e2 = TTSEngine(name="slow", synthesize_fn=lambda t, **kw: b"audio", is_available_fn=lambda: True, priority=2)
        router.register(e2)  # Register out of order
        router.register(e1)
        chain = router.get_fallback_chain()
        assert chain[0].name == "fast"
        assert chain[1].name == "slow"

    def test_unavailable_engines_excluded_from_chain(self):
        from tts_router import TTSRouter, TTSEngine

        router = TTSRouter()
        e1 = TTSEngine(name="available", synthesize_fn=lambda t, **kw: b"audio", is_available_fn=lambda: True, priority=1)
        e2 = TTSEngine(name="broken", synthesize_fn=lambda t, **kw: b"audio", is_available_fn=lambda: False, priority=0)
        router.register(e1)
        router.register(e2)
        chain = router.get_fallback_chain()
        assert len(chain) == 1
        assert chain[0].name == "available"

    def test_synthesize_uses_first_available(self):
        from tts_router import TTSRouter, TTSEngine

        router = TTSRouter()
        e1 = TTSEngine(name="primary", synthesize_fn=lambda t, **kw: b"primary_audio", is_available_fn=lambda: True, priority=0)
        e2 = TTSEngine(name="fallback", synthesize_fn=lambda t, **kw: b"fallback_audio", is_available_fn=lambda: True, priority=1)
        router.register(e1)
        router.register(e2)
        result = router.synthesize("hello")
        assert result == b"primary_audio"

    def test_synthesize_falls_back_on_failure(self):
        from tts_router import TTSRouter, TTSEngine

        def failing_synth(text, **kw):
            raise RuntimeError("Engine failed")

        router = TTSRouter()
        e1 = TTSEngine(name="broken", synthesize_fn=failing_synth, is_available_fn=lambda: True, priority=0)
        e2 = TTSEngine(name="fallback", synthesize_fn=lambda t, **kw: b"fallback_audio", is_available_fn=lambda: True, priority=1)
        router.register(e1)
        router.register(e2)
        result = router.synthesize("hello")
        assert result == b"fallback_audio"

    def test_synthesize_falls_back_on_none_return(self):
        from tts_router import TTSRouter, TTSEngine

        router = TTSRouter()
        e1 = TTSEngine(name="empty", synthesize_fn=lambda t, **kw: None, is_available_fn=lambda: True, priority=0)
        e2 = TTSEngine(name="ok", synthesize_fn=lambda t, **kw: b"ok_audio", is_available_fn=lambda: True, priority=1)
        router.register(e1)
        router.register(e2)
        result = router.synthesize("hello")
        assert result == b"ok_audio"

    def test_synthesize_returns_none_when_all_fail(self):
        from tts_router import TTSRouter, TTSEngine

        def failing(text, **kw):
            raise RuntimeError("fail")

        router = TTSRouter()
        router.register(TTSEngine(name="a", synthesize_fn=failing, is_available_fn=lambda: True, priority=0))
        result = router.synthesize("hello")
        assert result is None

    def test_stats_tracking(self):
        from tts_router import TTSRouter, TTSEngine

        router = TTSRouter()
        engine = TTSEngine(name="test", synthesize_fn=lambda t, **kw: b"audio", is_available_fn=lambda: True, priority=0)
        router.register(engine)
        router.synthesize("hello")
        router.synthesize("world")
        assert router.stats["test"]["successes"] == 2
        assert router.stats["test"]["failures"] == 0

    def test_stats_tracks_failures(self):
        from tts_router import TTSRouter, TTSEngine

        def failing(text, **kw):
            raise RuntimeError("fail")

        router = TTSRouter()
        e1 = TTSEngine(name="bad", synthesize_fn=failing, is_available_fn=lambda: True, priority=0)
        e2 = TTSEngine(name="good", synthesize_fn=lambda t, **kw: b"ok", is_available_fn=lambda: True, priority=1)
        router.register(e1)
        router.register(e2)
        router.synthesize("test")
        assert router.stats["bad"]["failures"] == 1
        assert router.stats["good"]["successes"] == 1

    def test_sentence_splitting(self):
        from tts_router import TTSRouter

        router = TTSRouter()
        sentences = router.split_sentences("Hello there! How are you? I'm Mario.")
        assert len(sentences) == 3
        assert sentences[0] == "Hello there!"

    def test_sentence_splitting_handles_empty(self):
        from tts_router import TTSRouter

        router = TTSRouter()
        assert router.split_sentences("") == []
        assert router.split_sentences("   ") == []

    def test_sentence_splitting_single_sentence(self):
        from tts_router import TTSRouter

        router = TTSRouter()
        sentences = router.split_sentences("Just one sentence here.")
        assert len(sentences) == 1

    def test_register_same_priority_stable(self):
        """Engines with same priority maintain registration order."""
        from tts_router import TTSRouter, TTSEngine

        router = TTSRouter()
        e1 = TTSEngine(name="first", synthesize_fn=lambda t, **kw: None, is_available_fn=lambda: True, priority=1)
        e2 = TTSEngine(name="second", synthesize_fn=lambda t, **kw: None, is_available_fn=lambda: True, priority=1)
        router.register(e1)
        router.register(e2)
        chain = router.get_fallback_chain()
        assert chain[0].name == "first"

    def test_parallel_synthesize(self):
        """parallel_synthesize splits text and returns list of audio bytes."""
        from tts_router import TTSRouter, TTSEngine

        router = TTSRouter()
        engine = TTSEngine(
            name="fast",
            synthesize_fn=lambda t, **kw: f"audio:{t}".encode(),
            is_available_fn=lambda: True,
            priority=0,
        )
        router.register(engine)
        results = asyncio.get_event_loop().run_until_complete(
            router.parallel_synthesize("Hello! How are you? Great day.")
        )
        assert len(results) == 3
        assert all(isinstance(r, bytes) for r in results)

    def test_synthesize_passes_rate_and_pitch(self):
        """Router passes rate and pitch kwargs through to engines."""
        from tts_router import TTSRouter, TTSEngine

        captured = {}

        def capturing_synth(text, rate=None, pitch=None, **kw):
            captured["rate"] = rate
            captured["pitch"] = pitch
            return b"audio"

        router = TTSRouter()
        router.register(TTSEngine(name="cap", synthesize_fn=capturing_synth, is_available_fn=lambda: True, priority=0))
        router.synthesize("hi", rate="+20%", pitch="+5Hz")
        assert captured["rate"] == "+20%"
        assert captured["pitch"] == "+5Hz"
