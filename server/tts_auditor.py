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


def suggest_fix(intended: str, actual: str) -> dict | None:
    """Suggest pronunciation rules based on word-level alignment.
    
    Compares intended vs actual word-by-word and suggests the STT-heard
    version as a phonetic hint for words that don't match.
    """
    intended_words = _normalize(intended).split()
    actual_words = _normalize(actual).split()
    matcher = SequenceMatcher(None, intended_words, actual_words)
    suggestions = {}
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "replace":
            # Handle 1:1 or 1:N replacements
            if (i2 - i1) == 1:
                word = intended_words[i1]
                if len(word) > 2:
                    # Join the actual words that replaced this intended word
                    actual_phrase = " ".join(actual_words[j1:j2])
                    suggestions[word] = actual_phrase
    return suggestions if suggestions else None


class TTSAuditor:
    """Audits TTS output by synthesizing, transcribing, and comparing."""

    def __init__(self):
        self._results: list[AuditResult] = []
        self._audit_log_path = os.path.join(
            os.path.dirname(__file__), "data", "tts_audit_log.json"
        )

    def audit_phrase(self, text: str) -> AuditResult:
        """Synthesize text, transcribe result, compare."""
        import tts
        import stt

        # Ensure STT is ready
        if not stt._HAS_WHISPER:
            raise RuntimeError("STT (faster-whisper) not available — install faster-whisper to use auditor")
        if stt._model is None:
            stt.init_model(model_size="base", device="auto")

        # 1. Synthesize
        wav_bytes = tts.synthesize(text)

        # 2. Extract PCM from WAV
        with io.BytesIO(wav_bytes) as buf:
            with wave.open(buf, "rb") as wf:
                pcm_data = wf.readframes(wf.getnframes())
                sample_rate = wf.getframerate()
                audio_duration = wf.getnframes() / float(wf.getframerate())

        # 3. Transcribe
        actual_text = stt.transcribe(pcm_data, sample_rate)

        # 4. Compare
        wer, missing, wrong = calculate_wer(text, actual_text)
        truncated = is_truncated(text, actual_text, audio_duration)
        fix = suggest_fix(text, actual_text)

        result = AuditResult(
            intended=text,
            actual=actual_text,
            word_error_rate=round(wer, 3),
            truncated=truncated,
            missing_words=missing,
            wrong_words=wrong,
            audio_duration_s=round(audio_duration, 2),
            suggested_fix=fix or {},
        )
        self._results.append(result)
        return result

    def audit_batch(self, phrases: list[str]) -> dict:
        """Audit a list of phrases, return aggregate report."""
        results = []
        for phrase in phrases:
            try:
                result = self.audit_phrase(phrase)
                results.append(result)
            except Exception as e:
                logger.warning(f"Audit failed for '{phrase[:40]}': {e}")
                results.append(AuditResult(
                    intended=phrase, actual=f"ERROR: {e}",
                    word_error_rate=1.0, truncated=False,
                    status="ERROR",
                ))
        
        passed = sum(1 for r in results if r.status == "PASS")
        failed = sum(1 for r in results if r.status != "PASS")
        truncated = sum(1 for r in results if r.truncated)
        
        # Aggregate suggested fixes
        all_fixes = {}
        for r in results:
            all_fixes.update(r.suggested_fix)
        
        return {
            "total": len(results),
            "passed": passed,
            "failed": failed,
            "truncated": truncated,
            "results": [asdict(r) for r in results],
            "suggested_fixes": all_fixes,
        }

    def get_results(self, limit: int = 50) -> dict:
        """Get recent audit results for dashboard."""
        recent = self._results[-limit:]
        return {
            "results": [asdict(r) for r in recent],
            "summary": {
                "total": len(recent),
                "passed": sum(1 for r in recent if r.status == "PASS"),
                "failed": sum(1 for r in recent if r.status != "PASS"),
            },
        }

    def _log_mismatch(self, result: AuditResult):
        """Append mismatch to audit log file."""
        os.makedirs(os.path.dirname(self._audit_log_path), exist_ok=True)
        entry = asdict(result)
        try:
            with open(self._audit_log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            logger.warning(f"Failed to write audit log: {e}")
