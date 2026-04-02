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

    def test_synthesize_returns_silence_when_all_fail(self):
        from tts_router import TTSRouter, TTSEngine

        def failing(text, **kw):
            raise RuntimeError("fail")

        router = TTSRouter()
        router.register(TTSEngine(name="a", synthesize_fn=failing, is_available_fn=lambda: True, priority=0))
        result = router.synthesize("hello")
        # Emergency silence fallback returns valid WAV bytes, not None
        assert result is not None
        assert result[:4] == b"RIFF"  # Valid WAV header

    def test_stats_tracking(self):
        from tts_router import TTSRouter, TTSEngine

        router = TTSRouter()
        engine = TTSEngine(name="test", synthesize_fn=lambda t, **kw: b"audio", is_available_fn=lambda: True, priority=0)
        router.register(engine)
        router.synthesize("hello")
        router.synthesize("world")
        assert router.stats["test"]["successes"] == 2
        assert router.stats["test"]["failures"] == 0
        assert router.stats["test"]["attempts"] == 2

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
        results = asyncio.run(
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

    def test_parallel_synthesize_partial_failures(self):
        """Partial failures in parallel synthesis return successful results and log errors."""
        import asyncio
        from tts_router import TTSRouter, TTSEngine

        call_count = 0

        def flaky_synth(t, **kw):
            nonlocal call_count
            call_count += 1
            if call_count % 2 == 0:
                raise RuntimeError("GPU hiccup")
            return f"audio:{t}".encode()

        router = TTSRouter()
        router.register(TTSEngine(name="flaky", synthesize_fn=flaky_synth, is_available_fn=lambda: True, priority=0))
        results = asyncio.run(
            router.parallel_synthesize("One. Two. Three.")
        )
        # Sentences 1 and 3 succeed (odd calls), sentence 2 fails (even call)
        assert len(results) >= 1  # At least some succeed
        assert all(isinstance(r, bytes) for r in results)

    def test_synthesize_user_sets_and_clears_event(self):
        """synthesize_user sets priority event before synthesis and clears after."""
        import threading
        from tts_router import TTSRouter, TTSEngine

        event = threading.Event()
        event_was_set_during_synth = False

        def check_event_synth(text, **kw):
            nonlocal event_was_set_during_synth
            event_was_set_during_synth = event.is_set()
            return b"audio"

        router = TTSRouter(user_priority_event=event)
        router.register(TTSEngine(name="checker", synthesize_fn=check_event_synth, is_available_fn=lambda: True, priority=0))

        assert not event.is_set()
        router.synthesize_user("hello")
        assert event_was_set_during_synth, "Event should be set during synthesis"
        assert not event.is_set(), "Event should be cleared after synthesis"

    def test_synthesize_user_clears_event_on_exception(self):
        """synthesize_user clears event even if all engines fail."""
        import threading
        from tts_router import TTSRouter, TTSEngine

        event = threading.Event()

        def failing_synth(text, **kw):
            raise RuntimeError("fail")

        router = TTSRouter(user_priority_event=event)
        router.register(TTSEngine(name="fail", synthesize_fn=failing_synth, is_available_fn=lambda: True, priority=0))

        result = router.synthesize_user("hello")
        # Emergency silence fallback returns valid WAV, not None
        assert result is not None
        assert result[:4] == b"RIFF"
        assert not event.is_set(), "Event must be cleared even on failure"


# --- Audio Normalization ---

class TestAudioNormalization:
    """Verify peak normalization produces consistent volume."""

    def _make_wav(self, peak_value=2000, n_samples=1000, sample_rate=22050):
        import wave, struct, io
        buf = io.BytesIO()
        with wave.open(buf, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(struct.pack(f'<{n_samples}h', *([peak_value] * n_samples)))
        return buf.getvalue()

    def test_quiet_audio_is_boosted(self):
        import io, wave
        import numpy as np
        from tts import _normalize_audio

        quiet = self._make_wav(peak_value=2000)
        normalized = _normalize_audio(quiet)

        with wave.open(io.BytesIO(quiet), 'rb') as wf:
            orig = np.max(np.abs(np.frombuffer(wf.readframes(wf.getnframes()), np.int16)))
        with wave.open(io.BytesIO(normalized), 'rb') as wf:
            normed = np.max(np.abs(np.frombuffer(wf.readframes(wf.getnframes()), np.int16)))

        assert normed > orig, "Quiet audio should be boosted"
        assert normed > 20000, "Should be near -3dB target"

    def test_loud_audio_is_reduced(self):
        import io, wave
        import numpy as np
        from tts import _normalize_audio

        loud = self._make_wav(peak_value=32000)
        normalized = _normalize_audio(loud)

        with wave.open(io.BytesIO(normalized), 'rb') as wf:
            normed = np.max(np.abs(np.frombuffer(wf.readframes(wf.getnframes()), np.int16)))

        assert normed < 32000, "Loud audio peak should be reduced to -3dB target"

    def test_returns_original_on_empty(self):
        from tts import _normalize_audio
        assert _normalize_audio(b"not a wav") == b"not a wav"

    def test_output_is_valid_wav(self):
        from tts import _normalize_audio
        wav = self._make_wav(peak_value=5000)
        result = _normalize_audio(wav)
        assert result[:4] == b"RIFF"


# --- TTS Preprocessing ---

class TestTTSPreprocessing:
    """Verify GPT-SoVITS text cleaning handles new character names."""

    def test_peach_pronunciation(self):
        from gpt_sovits_server import clean_text_for_tts
        assert "Peech" in clean_text_for_tts("Princess Peach is great!")

    def test_luigi_pronunciation(self):
        from gpt_sovits_server import clean_text_for_tts
        assert "Looigi" in clean_text_for_tts("Luigi is my brother!")

    def test_yoshi_pronunciation(self):
        from gpt_sovits_server import clean_text_for_tts
        result = clean_text_for_tts("Yoshi is the best!")
        assert "Yoh shee" in result

    def test_year_conversion(self):
        from gpt_sovits_server import clean_text_for_tts
        result = clean_text_for_tts("Back in 2024 it was great")
        assert "2024" not in result
        assert "twenty" in result.lower()

    def test_existing_bowser_replacement(self):
        from gpt_sovits_server import clean_text_for_tts
        result = clean_text_for_tts("Bowser is evil!")
        assert "owsir" in result.lower()

    def test_hoppenstedt_pronunciation(self):
        from gpt_sovits_server import clean_text_for_tts
        assert "Hoppenstead" in clean_text_for_tts("Jacob Hoppenstedt is here!")

    def test_ellipsis_stripped_no_leading_comma(self):
        """Ellipsis at start/end should NOT produce leading commas."""
        from gpt_sovits_server import clean_text_for_tts
        result = clean_text_for_tts("...Hello there!")
        assert not result.startswith(","), f"Leading comma in: {result}"
        assert "hello" in result.lower()

    def test_ellipsis_mid_sentence(self):
        from gpt_sovits_server import clean_text_for_tts
        result = clean_text_for_tts("Let me...think about...that")
        assert "..." not in result
        assert "let me" in result.lower()

    def test_only_ellipsis_returns_empty(self):
        from gpt_sovits_server import clean_text_for_tts
        assert clean_text_for_tts("...") == ""

    def test_empty_text_synthesize_returns_silence(self):
        """Empty text should return emergency silence, not crash."""
        from tts import synthesize
        result = synthesize("")
        assert result is not None
        assert len(result) > 0


# --- TTS Pre-clean ---

class TestPrecleanTtsText:
    """Verify _preclean_tts_text strips problematic chars for TTS engines."""

    def test_ellipsis_three_dots(self):
        from tts import _preclean_tts_text
        assert _preclean_tts_text("Hello... world") == "Hello, world"

    def test_ellipsis_smart(self):
        from tts import _preclean_tts_text
        assert _preclean_tts_text("Hello\u2026 world") == "Hello, world"

    def test_ellipsis_two_dots(self):
        from tts import _preclean_tts_text
        assert _preclean_tts_text("Hello.. world") == "Hello, world"

    def test_ellipsis_at_end(self):
        from tts import _preclean_tts_text
        assert _preclean_tts_text("Mama mia...") == "Mama mia"

    def test_ellipsis_at_start(self):
        from tts import _preclean_tts_text
        assert _preclean_tts_text("...Ready?") == "Ready?"

    def test_smart_quotes_removed(self):
        from tts import _preclean_tts_text
        assert _preclean_tts_text("\u201cHello\u201d") == "Hello"

    def test_em_dash_to_comma(self):
        from tts import _preclean_tts_text
        assert _preclean_tts_text("Hello\u2014world") == "Hello, world"

    def test_asterisks_removed(self):
        from tts import _preclean_tts_text
        assert _preclean_tts_text("*laughs* hello") == "laughs hello"

    def test_comma_after_punctuation(self):
        from tts import _preclean_tts_text
        assert _preclean_tts_text("Wahoo! ...Ready?") == "Wahoo! Ready?"

    def test_only_ellipsis(self):
        from tts import _preclean_tts_text
        assert _preclean_tts_text("...") == ""

    def test_double_commas_collapsed(self):
        from tts import _preclean_tts_text
        assert _preclean_tts_text("Hello,, world") == "Hello, world"

    def test_multiple_issues(self):
        from tts import _preclean_tts_text
        assert _preclean_tts_text("Hello... *laughs*... world") == "Hello, laughs, world"

    def test_normal_text_unchanged(self):
        from tts import _preclean_tts_text
        assert _preclean_tts_text("Hello world!") == "Hello world!"

    def test_trailing_comma_removed(self):
        from tts import _preclean_tts_text
        assert _preclean_tts_text("Hello world,") == "Hello world"
