# TTS Verification System Design

**Status:** Draft
**Date:** 2026-05-27
**Author:** Copilot

## Problem

Mario's TTS output has two critical issues:
1. **Truncation** — Mario sometimes doesn't finish saying what he's supposed to say (words/sentences cut off)
2. **Mispronunciation** — Specific words are said incorrectly (Italian phrases, names, catchphrases)

There is no automated way to detect or fix these issues. Currently, a human must listen and manually add pronunciation rules to `character.yaml`.

## Solution

A closed-loop TTS verification system with two modes:

1. **Batch Audit Mode** — On-demand testing of phrase lists through an admin endpoint
2. **Debug Monitor Mode** — Background transcription of live TTS output during development

Both modes use the existing `faster-whisper` STT engine to transcribe Mario's audio output, then compare against the intended text to detect truncation and mispronunciation.

## Architecture

```
Intended Text → TTS Engine → WAV Audio → STT Transcribe → Compare → Report
                                                              ↓
                                                    Suggest pronunciation fix
                                                              ↓
                                                    Human approves → Update character.yaml
```

## Components

### 1. TTS Auditor (`server/tts_auditor.py`)

Core module that handles the synthesize → transcribe → compare loop.

```python
class TTSAuditor:
    def __init__(self):
        self._stt_model = None  # Lazy-loaded faster-whisper
        self._results = []      # Audit results history
    
    def audit_phrase(self, text: str) -> AuditResult:
        """Synthesize text, transcribe result, compare."""
        # 1. Synthesize via tts.synthesize()
        # 2. Save WAV to temp file
        # 3. Transcribe via stt.transcribe()
        # 4. Compare intended vs actual
        # 5. Return AuditResult
    
    def audit_batch(self, phrases: list[str]) -> BatchReport:
        """Audit a list of phrases, return aggregate report."""
    
    def suggest_fix(self, intended: str, actual: str) -> dict | None:
        """Suggest a pronunciation rule if a word is consistently wrong."""
```

**AuditResult dataclass:**
```python
@dataclass
class AuditResult:
    intended: str           # What Mario should have said
    actual: str             # What STT heard Mario say
    word_error_rate: float  # 0.0 = perfect, 1.0 = completely wrong
    truncated: bool         # True if actual is significantly shorter
    missing_words: list[str]  # Words in intended but not in actual
    wrong_words: list[tuple[str, str]]  # (intended_word, actual_word) pairs
    audio_duration_s: float # Length of generated audio
    timestamp: str          # ISO timestamp
```

### 2. Comparison Engine

Word-level diff using `difflib.SequenceMatcher`:
- Normalize both strings: lowercase, strip punctuation, collapse whitespace
- Compute word-level alignment
- **Truncation detection**: if actual has <80% of intended word count, flag as truncated
- **Mispronunciation detection**: aligned words that don't match
- **Word Error Rate (WER)**: standard metric — (substitutions + insertions + deletions) / total intended words

### 3. Batch Audit Endpoint (`POST /admin/tts_audit`)

**Request:**
```json
{
  "phrases": ["It's-a me, Mario!", "Mamma mia!", "Let's-a go!"],
  "use_builtin": true  // Also include built-in test phrases
}
```

If `phrases` is empty and `use_builtin` is true, uses a curated list of ~30 test phrases covering:
- Mario catchphrases (wahoo, yippee, mamma mia, etc.)
- Italian-style phrases
- Common game text (trivia questions, game introductions)
- Tricky words from existing pronunciation rules
- Long sentences (truncation testing)

**Response:**
```json
{
  "total": 30,
  "passed": 26,
  "failed": 4,
  "truncated": 1,
  "results": [
    {
      "intended": "Mamma mia, that's amazing!",
      "actual": "mama mee ah that's amazing",
      "word_error_rate": 0.2,
      "truncated": false,
      "missing_words": [],
      "wrong_words": [["mamma", "mama"], ["mia", "mee ah"]],
      "suggested_fix": {"mamma mia": "mama mee-ah"},
      "status": "MISPRONOUNCED"
    }
  ],
  "suggested_fixes": {
    "wahoo": "wah-hoo",
    "yippee": "yip-pee"
  }
}
```

### 4. Debug Monitor Mode

Toggled via `config_live.json`:
```json
{
  "tts_debug_transcribe": false
}
```

When enabled:
- After each TTS synthesis in the main pipeline, spawn a background thread
- Transcribe the audio that was just generated
- Compare against intended text
- If mismatch detected, log to `server/data/tts_audit_log.json`
- **Zero overhead when disabled** — the check is a simple boolean guard

Log format:
```json
{
  "timestamp": "2026-05-27T12:30:00",
  "intended": "Let's-a go!",
  "actual": "let's a go",
  "word_error_rate": 0.1,
  "truncated": false,
  "tts_engine": "sovits",
  "audio_duration_s": 1.2
}
```

### 5. Built-in Test Phrases

Stored in `characters/mario/test_phrases.yaml`:
```yaml
catchphrases:
  - "It's-a me, Mario!"
  - "Wahoo!"
  - "Mamma mia!"
  - "Let's-a go!"
  - "Yippee!"
  - "Here we go!"
  - "Oh yeah!"

italian_phrases:
  - "Buongiorno, amico!"
  - "Grazie mille!"
  - "Bellissimo!"

game_text:
  - "Welcome to Mario's Trivia Challenge!"
  - "That's correct! You're doing great!"
  - "Time for a game! Who wants to play?"

long_sentences:
  - "Did you know that the first Mario game was released in 1985, and it completely revolutionized the gaming industry?"
  - "Welcome to the party, everyone! I hope you're all ready for some fun, games, and maybe even a few surprises along the way!"

tricky_words:
  - "The plumber fixed the pipe with his wrench."
  - "Princess Peach was rescued from Bowser's castle."
```

### 6. Dashboard Integration

Add a section to the existing dashboard showing:
- Last audit results (pass/fail count)
- Current pronunciation rules from character.yaml
- Link to trigger batch audit
- Live monitor status (enabled/disabled)

## Semi-Auto Fix Flow

When the auditor detects a mispronunciation:
1. Log the issue with intended vs actual
2. Generate a suggested phonetic spelling
3. Present to user via the audit report
4. User approves → system adds to `character.yaml` pronunciation section
5. TTS cache for affected phrase is invalidated
6. Re-audit to confirm fix works

**Initial implementation**: fixes are shown in the audit report. User manually applies approved fixes. Full auto-apply is a future enhancement once trust is established.

## File Changes

| File | Change |
|------|--------|
| `server/tts_auditor.py` | New — core audit engine |
| `server/main.py` | Add `/admin/tts_audit` endpoint, wire debug monitor |
| `server/tts.py` | Add hook for debug monitor (post-synthesis callback) |
| `characters/mario/test_phrases.yaml` | New — curated test phrases |
| `server/dashboard.py` | Add audit results section |
| `config_live.json` | Add `tts_debug_transcribe` flag |

## Dependencies

- `faster-whisper` — already installed (stt.py)
- `difflib` — Python stdlib
- No new dependencies required

## Success Criteria

1. Batch audit detects known pronunciation issues (wahoo, mamma mia, yippee)
2. Truncation is detected when TTS cuts off early
3. Debug monitor logs issues without impacting normal performance
4. Suggested fixes, when applied, resolve the pronunciation issue on re-audit
5. System works end-to-end: audit → detect → fix → verify
