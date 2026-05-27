# server/tts_auditor.py
"""TTS Verification System — Auditor for detecting pronunciation and truncation issues.

Synthesizes text via TTS, transcribes back via STT, and compares to find
mismatches. Supports batch auditing and live debug monitoring.
"""

import io
import json
import logging
import os
import re
import wave
from dataclasses import dataclass, field, asdict
from datetime import datetime
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


@dataclass
class AuditResult:
    """Result of auditing a single TTS phrase."""
    intended: str
    actual: str
    word_error_rate: float
    truncated: bool
    missing_words: list = field(default_factory=list)
    wrong_words: list = field(default_factory=list)
    audio_duration_s: float = 0.0
    timestamp: str = ""
    status: str = "PASS"
    suggested_fix: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()
        if self.truncated:
            self.status = "TRUNCATED"
        elif self.word_error_rate > 0.1:
            self.status = "MISPRONOUNCED"
        else:
            self.status = "PASS"


def _normalize(text: str) -> str:
    """Normalize text for comparison: lowercase, strip punctuation (keep apostrophes/hyphens), collapse whitespace."""
    t = text.lower()
    t = re.sub(r"[^\w\s'\-]", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def calculate_wer(intended: str, actual: str) -> tuple:
    """Calculate Word Error Rate and extract mismatches.
    
    Returns: (wer: float, missing_words: list[str], wrong_words: list[tuple[str,str]])
    """
    intended_words = _normalize(intended).split()
    actual_words = _normalize(actual).split()

    if not intended_words:
        return (0.0, [], []) if not actual_words else (1.0, [], [])

    matcher = SequenceMatcher(None, intended_words, actual_words)
    substitutions = 0
    deletions = 0
    insertions = 0
    missing_words = []
    wrong_words = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "replace":
            substitutions += max(i2 - i1, j2 - j1)
            for iw, aw in zip(intended_words[i1:i2], actual_words[j1:j2]):
                wrong_words.append((iw, aw))
        elif tag == "delete":
            deletions += i2 - i1
            missing_words.extend(intended_words[i1:i2])
        elif tag == "insert":
            insertions += j2 - j1

    wer = (substitutions + deletions + insertions) / len(intended_words)
    return wer, missing_words, wrong_words


def is_truncated(intended: str, actual: str, audio_duration_s: float) -> bool:
    """Detect truncation using both word count and duration heuristics."""
    intended_words = _normalize(intended).split()
    actual_words = _normalize(actual).split()

    if not intended_words:
        return False

    word_ratio = len(actual_words) / len(intended_words)
    expected_duration = len(intended_words) / 2.5
    duration_ratio = audio_duration_s / max(0.1, expected_duration)

    return word_ratio < 0.75 and duration_ratio < 0.6
