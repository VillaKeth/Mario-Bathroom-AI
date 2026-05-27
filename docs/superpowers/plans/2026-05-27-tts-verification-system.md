# TTS Verification System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a closed-loop TTS verification system that detects truncation and mispronunciation in Mario's speech output using STT-based transcription and comparison.

**Architecture:** Core auditor module (`tts_auditor.py`) with WER comparison engine, batch audit endpoint, and optional debug monitor mode. Uses existing faster-whisper STT to transcribe TTS WAV output, then word-level diff to detect issues.

**Tech Stack:** Python, faster-whisper (existing), difflib (stdlib), PyYAML (existing), FastAPI (existing)

---

### Task 1: Create TTS Auditor Core — Comparison Engine

**Files:**
- Create: `server/tts_auditor.py`
- Create: `tests/test_tts_auditor.py`

This task builds the pure comparison logic (no TTS/STT dependency), making it fully testable with mocked inputs.

- [ ] **Step 1: Write failing tests for comparison engine**

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd C:\Users\Vketh\Desktop\Mario_AI && python -m pytest tests/test_tts_auditor.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tts_auditor'`

- [ ] **Step 3: Implement comparison engine**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd C:\Users\Vketh\Desktop\Mario_AI && python -m pytest tests/test_tts_auditor.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
cd C:\Users\Vketh\Desktop\Mario_AI
git add server/tts_auditor.py tests/test_tts_auditor.py
git commit -m "feat: add TTS auditor comparison engine (WER, truncation detection)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 2: Add Suggest-Fix and Audit-Phrase Methods

**Files:**
- Modify: `server/tts_auditor.py`
- Modify: `tests/test_tts_auditor.py`

Adds `suggest_fix()` and the `TTSAuditor` class with `audit_phrase()`. The `audit_phrase()` method calls `tts.synthesize()` and `stt.transcribe()` — tests will mock those.

- [ ] **Step 1: Write failing tests for suggest_fix and TTSAuditor**

Add to `tests/test_tts_auditor.py`:

```python
from unittest.mock import patch, MagicMock
from tts_auditor import suggest_fix, TTSAuditor


def _create_test_wav(duration_s: float = 1.0, sample_rate: int = 16000) -> bytes:
    """Helper: build a valid WAV file with silence for testing."""
    import struct
    samples = [0] * int(sample_rate * duration_s)
    pcm_data = struct.pack(f"<{len(samples)}h", *samples)
    wav_buf = io.BytesIO()
    with wave.open(wav_buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data)
    return wav_buf.getvalue()


class TestSuggestFix:
    def test_single_word_replacement(self):
        result = suggest_fix("wahoo lets go", "wah hoo lets go")
        assert result is not None
        assert "wahoo" in result
    
    def test_no_fix_needed(self):
        result = suggest_fix("hello world", "hello world")
        assert result is None
    
    def test_ignores_short_words(self):
        result = suggest_fix("I am here", "I am here")
        assert result is None


class TestTTSAuditor:
    @patch("tts_auditor.stt")
    @patch("tts_auditor.tts")
    def test_audit_phrase_pass(self, mock_tts, mock_stt):
        """Perfect transcription → PASS."""
        mock_tts.synthesize.return_value = _create_test_wav()
        mock_stt._HAS_WHISPER = True
        mock_stt._model = MagicMock()
        mock_stt.transcribe.return_value = "hello world"
        
        auditor = TTSAuditor()
        result = auditor.audit_phrase("Hello world!")
        assert result.status == "PASS"
        assert result.word_error_rate < 0.1

    @patch("tts_auditor.stt")
    @patch("tts_auditor.tts")
    def test_audit_phrase_mispronounced(self, mock_tts, mock_stt):
        """Wrong word → MISPRONOUNCED."""
        mock_tts.synthesize.return_value = _create_test_wav()
        mock_stt._HAS_WHISPER = True
        mock_stt._model = MagicMock()
        mock_stt.transcribe.return_value = "mama maya that's amazing"
        
        auditor = TTSAuditor()
        result = auditor.audit_phrase("Mamma mia, that's amazing!")
        assert result.status == "MISPRONOUNCED"
        assert result.word_error_rate > 0
```

- [ ] **Step 2: Run tests to verify new tests fail**

Run: `cd C:\Users\Vketh\Desktop\Mario_AI && python -m pytest tests/test_tts_auditor.py::TestSuggestFix -v`
Expected: FAIL — `suggest_fix` not found

- [ ] **Step 3: Implement suggest_fix and TTSAuditor class**

Add to `server/tts_auditor.py`:

```python
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
        if tag == "replace" and (i2 - i1) == 1 and (j2 - j1) == 1:
            word = intended_words[i1]
            if len(word) > 2:
                suggestions[word] = actual_words[j1]
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
```

- [ ] **Step 4: Run all auditor tests**

Run: `cd C:\Users\Vketh\Desktop\Mario_AI && python -m pytest tests/test_tts_auditor.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
cd C:\Users\Vketh\Desktop\Mario_AI
git add server/tts_auditor.py tests/test_tts_auditor.py
git commit -m "feat: add TTSAuditor class with audit_phrase, batch, suggest_fix

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 3: Create Test Phrases YAML

**Files:**
- Create: `characters/mario/test_phrases.yaml`

- [ ] **Step 1: Create the test phrases file**

```yaml
# characters/mario/test_phrases.yaml
# Curated phrases for TTS verification auditing.
# Each category tests different pronunciation/truncation scenarios.

catchphrases:
  - "It's-a me, Mario!"
  - "Wahoo!"
  - "Mamma mia!"
  - "Let's-a go!"
  - "Yippee!"
  - "Here we go!"
  - "Oh yeah!"
  - "Okie dokie!"
  - "Ha ha ha!"
  - "Yahoo!"

italian_phrases:
  - "Buongiorno, amico!"
  - "Grazie mille!"
  - "Bellissimo!"
  - "Magnifico!"
  - "Bravo!"

game_text:
  - "Welcome to Mario's Trivia Challenge!"
  - "That's correct! You're doing great!"
  - "Time for a game! Who wants to play?"
  - "Let me think of a good riddle for you."
  - "Rock, paper, scissors, shoot!"

long_sentences:
  - "Did you know that the first Mario game was released in 1985, and it completely revolutionized the gaming industry?"
  - "Welcome to the party, everyone! I hope you're all ready for some fun, games, and maybe even a few surprises along the way!"
  - "That reminds me of the time I rescued Princess Peach from Bowser's castle. It was quite the adventure, let me tell you!"

existing_pronunciation_rules:
  - "Okie dokie, let's start the game!"
  - "Ha ha ha, that's really funny!"
  - "Whoa, that's incredible!"
  - "Wahoo! We did it!"
  - "Yippee! That's the right answer!"
  - "Mamma mia, what a great party!"
```

- [ ] **Step 2: Commit**

```bash
cd C:\Users\Vketh\Desktop\Mario_AI
git add characters/mario/test_phrases.yaml
git commit -m "feat: add curated TTS test phrases for Mario

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 4: Add TTS Post-Synthesis Callback Hook

**Files:**
- Modify: `server/tts.py` — callback registry near line 1135, hook at line 1316

Add callback registry to `tts.py` so the debug monitor can hook into synthesis without tight coupling.

- [ ] **Step 1: Add callback registry to tts.py**

Near the top of `tts.py` (after `set_pronunciation()`, around line 1135), add:

```python
# Post-synthesis callback registry (for debug monitor)
_post_synthesis_callbacks = []

def register_post_synthesis_callback(callback):
    """Register a callback called after each TTS synthesis.
    
    Callback signature: callback(text: str, wav_bytes: bytes)
    Callbacks run in a try/except — failures are logged, not propagated.
    """
    _post_synthesis_callbacks.append(callback)

def clear_post_synthesis_callbacks():
    """Remove all post-synthesis callbacks."""
    _post_synthesis_callbacks.clear()
```

Then in the `synthesize()` function, just before the final `return result` on line 1316 (NOT the early return at line 1249 inside the try block), add:

```python
    # Fire post-synthesis callbacks (debug monitor hook)
    for cb in _post_synthesis_callbacks:
        try:
            cb(text, result)
        except Exception as e:
            logger.warning(f"[DEBUG_TTS] post-synthesis callback failed: {e}")

    return result
```

**IMPORTANT:** There are TWO `return result` in synthesize(). Line 1249 is an early return inside a `try` block for cached GPT-SoVITS — do NOT add callbacks there. Line 1316 is the final return at function end — add callbacks BEFORE this one only.

- [ ] **Step 2: Run existing tests to verify no regression**

Run: `cd C:\Users\Vketh\Desktop\Mario_AI && python -m pytest tests/test_tts_auditor.py tests/test_character_loader.py -v`
Expected: All PASS

- [ ] **Step 3: Commit**

```bash
cd C:\Users\Vketh\Desktop\Mario_AI
git add server/tts.py
git commit -m "feat: add post-synthesis callback registry to TTS

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 5: Add Batch Audit Endpoint and Debug Monitor Toggle

**Files:**
- Modify: `server/main.py` — add endpoint after `/admin/party_summary` (~line 1845)

- [ ] **Step 1: Add the batch audit endpoint and debug monitor wiring**

In `server/main.py`, add imports at the top (near other imports around line 56):

```python
import yaml
from tts_auditor import TTSAuditor
```

Add module-level auditor instance (near `_character = None`, around line 115):

```python
_tts_auditor = TTSAuditor()
```

Add the endpoint after `/admin/party_summary` (after line ~1845, at the end of the admin endpoints block):

```python
@app.post("/admin/tts_audit")
async def admin_tts_audit(request_body: dict = {}):
    """Run batch TTS audit — synthesize phrases, transcribe, compare."""
    phrases = list(request_body.get("phrases", []))
    use_builtin = request_body.get("use_builtin", not phrases)
    
    if use_builtin and _character:
        # Load test phrases from character directory
        test_phrases_path = os.path.join(_character.character_dir, "test_phrases.yaml")
        if os.path.exists(test_phrases_path):
            with open(test_phrases_path, "r", encoding="utf-8") as f:
                categories = yaml.safe_load(f) or {}
            for category_phrases in categories.values():
                if isinstance(category_phrases, list):
                    phrases.extend(category_phrases)
    
    if not phrases:
        return {"status": "error", "message": "No phrases to audit. Provide phrases or create test_phrases.yaml"}
    
    # Run audit in thread pool to avoid blocking event loop
    import asyncio
    report = await asyncio.to_thread(_tts_auditor.audit_batch, phrases)
    return report


@app.get("/admin/tts_audit/results")
async def get_tts_audit_results(limit: int = 50):
    """Get recent audit results."""
    return _tts_auditor.get_results(limit)
```

Add debug monitor toggle after the character loading section. Note: `live_config` is already initialized at line 111 of main.py via `LiveConfig(LIVE_CONFIG_PATH)`, so it's available everywhere:

```python
# Wire TTS debug monitor if enabled
if live_config.get("tts_debug_transcribe", False):
    import asyncio as _asyncio
    import tts as tts_module
    
    def _debug_monitor_callback(text: str, wav_bytes: bytes):
        """Non-blocking audit callback — fires STT in background thread."""
        def _do_audit():
            try:
                import io as _io, wave as _wave
                with _io.BytesIO(wav_bytes) as buf:
                    with _wave.open(buf, "rb") as wf:
                        pcm_data = wf.readframes(wf.getnframes())
                        sample_rate = wf.getframerate()
                        duration = wf.getnframes() / float(wf.getframerate())
                actual = stt.transcribe(pcm_data, sample_rate)
                from tts_auditor import calculate_wer, is_truncated, AuditResult
                wer, missing, wrong = calculate_wer(text, actual)
                if wer > 0.1 or is_truncated(text, actual, duration):
                    result = AuditResult(
                        intended=text, actual=actual, word_error_rate=round(wer, 3),
                        truncated=is_truncated(text, actual, duration),
                        missing_words=missing, wrong_words=wrong,
                        audio_duration_s=round(duration, 2),
                    )
                    _tts_auditor._log_mismatch(result)
                    logger.warning(f"[TTS_AUDIT] Mismatch: '{text[:40]}' → '{actual[:40]}' (WER={wer:.2f})")
            except Exception as e:
                logger.warning(f"[TTS_AUDIT] Debug monitor error: {e}")
        
        # Run in thread pool to avoid blocking TTS synthesis
        try:
            loop = _asyncio.get_running_loop()
            loop.run_in_executor(None, _do_audit)
        except RuntimeError:
            import threading
            threading.Thread(target=_do_audit, daemon=True).start()
    
    tts_module.register_post_synthesis_callback(_debug_monitor_callback)
    logger.info("[TTS_AUDIT] Debug monitor enabled — transcribing all TTS output")
```

- [ ] **Step 2: Test endpoint is reachable (manual check after server is running)**

Run: `curl -X POST http://localhost:8765/admin/tts_audit -H "Content-Type: application/json" -d "{\"phrases\":[\"Hello world\"]}" 2>&1`

Expected: JSON response with audit results

- [ ] **Step 3: Commit**

```bash
cd C:\Users\Vketh\Desktop\Mario_AI
git add server/main.py
git commit -m "feat: add /admin/tts_audit endpoint and debug monitor

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 6: End-to-End Verification

**Files:** None (testing only)

Start the server and client on Desktop 2, run the batch audit, and verify results.

- [ ] **Step 1: Start server**

```bash
cd C:\Users\Vketh\Desktop\Mario_AI\server
python -u main.py
```

Wait for `WebSocket server started` message.

- [ ] **Step 2: Start client on Desktop 2**

```bash
cd C:\Users\Vketh\Desktop\Mario_AI\client
python -u main.py
```

Verify window opens on Desktop 2 with title "Mario AI 🍄".

- [ ] **Step 3: Run batch audit with a few phrases**

```bash
curl -X POST http://localhost:8765/admin/tts_audit -H "Content-Type: application/json" -d "{\"phrases\":[\"Hello there!\",\"It's-a me, Mario!\",\"Wahoo!\"]}"
```

Expected: JSON with pass/fail results for each phrase.

- [ ] **Step 4: Run full built-in audit**

```bash
curl -X POST http://localhost:8765/admin/tts_audit -H "Content-Type: application/json" -d "{\"use_builtin\":true}"
```

Expected: JSON with results for all ~30 built-in phrases.

- [ ] **Step 5: Check results endpoint**

```bash
curl http://localhost:8765/admin/tts_audit/results
```

Expected: Summary of audit results.

- [ ] **Step 6: Commit final TODO update**

Update `TODO.md` to mark TTS verification system as complete.

```bash
cd C:\Users\Vketh\Desktop\Mario_AI
git add TODO.md
git commit -m "docs: add TTS verification system to TODO

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```
