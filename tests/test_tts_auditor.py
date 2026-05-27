# tests/test_tts_auditor.py
"""Tests for TTS Auditor comparison engine."""
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "server"))

from tts_auditor import _normalize, calculate_wer, is_truncated, AuditResult


class TestNormalize:
    def test_lowercase(self):
        assert _normalize("Hello World") == "hello world"
    
    def test_strip_punctuation(self):
        assert _normalize("Hello, World!") == "hello world"
    
    def test_collapse_whitespace(self):
        assert _normalize("Hello   World") == "hello world"
    
    def test_apostrophes_preserved(self):
        assert _normalize("it's-a me") == "it's-a me"


class TestCalculateWER:
    def test_perfect_match(self):
        wer, missing, wrong = calculate_wer("hello world", "hello world")
        assert wer == 0.0
        assert missing == []
        assert wrong == []
    
    def test_case_insensitive(self):
        wer, _, _ = calculate_wer("Hello World", "hello world")
        assert wer == 0.0
    
    def test_substitution(self):
        wer, missing, wrong = calculate_wer("hello world", "hello word")
        assert wer > 0
        assert ("world", "word") in wrong
    
    def test_deletion(self):
        wer, missing, wrong = calculate_wer("hello beautiful world", "hello world")
        assert wer > 0
        assert "beautiful" in missing
    
    def test_insertion(self):
        wer, _, _ = calculate_wer("hello world", "hello big world")
        assert wer > 0
    
    def test_empty_intended(self):
        wer, _, _ = calculate_wer("", "")
        assert wer == 0.0
    
    def test_complete_mismatch(self):
        wer, _, _ = calculate_wer("alpha beta", "gamma delta")
        assert wer == 1.0


class TestIsTruncated:
    def test_not_truncated(self):
        assert not is_truncated("hello world", "hello world", 1.0)
    
    def test_truncated_short_audio(self):
        # 10 words intended, 3 actual, very short audio
        intended = "one two three four five six seven eight nine ten"
        actual = "one two three"
        assert is_truncated(intended, actual, 0.5)
    
    def test_not_truncated_similar_length(self):
        intended = "hello world foo"
        actual = "hello world"
        # 66% words but audio is proportional → not truncated
        assert not is_truncated(intended, actual, 1.0)
