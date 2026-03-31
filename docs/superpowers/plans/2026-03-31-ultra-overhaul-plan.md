# ULTRA Overhaul Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform Mario AI Party Bot from 8B LLM + GPT-SoVITS into a 70B + Fish Speech powerhouse with night progression, 8-hour reliability, and party-grade UX — all within 24GB VRAM on RTX 3090 Ti.

**Architecture:** Layered upgrade: LLM swap (Ollama model change + router), TTS engine swap (Fish Speech primary + fallback chain), night progression overlay (phase system injected into system prompt), reliability wrapper (watchdog + dashboard + canary), Pygame hardening (fullscreen + auto-reconnect + panic). Each layer is independently testable and rollback-safe.

**Tech Stack:** Python 3.11, FastAPI, Ollama (llama3.1:70b-q4_k_m + mixtral:8x7b), Fish Speech v2.2+, RVC v2, faster-whisper (CPU int8), Pygame 2.6, SQLite WAL, WebSockets

**Spec:** `docs/superpowers/specs/2026-03-31-ultra-overhaul-design.md`
**Rollback Tag:** `v1.0-pre-superpowers`

---

## File Structure

### New Files to Create

| File | Responsibility |
|------|---------------|
| `server/fish_speech_tts.py` | Fish Speech v2.2+ TTS engine wrapper |
| `server/tts_router.py` | Unified TTS dispatcher: Fish Speech → Edge+RVC → XTTS → pre-recorded |
| `server/llm_router.py` | Dual-model router: fast path (Mixtral) vs quality path (70B) |
| `server/night_progression.py` | Phase calculator, prompt modifiers, guest energy tracking |
| `server/watchdog.py` | Independent health monitor + auto-restart |
| `server/dashboard.py` | FastAPI routes for `/dashboard`, `/api/canary`, `/api/reload`, `/api/report` |
| `server/hot_reload.py` | Live config reload from `config_live.json` |
| `server/canary.py` | Pre-party self-test suite |
| `server/catchphrase_bank.py` | Pre-recorded catchphrase matcher + player |
| `server/birthday_vip.py` | Birthday person special treatment logic |
| `server/catchphrase_mirror.py` | Guest word frequency tracker + mirroring |
| `server/sound_events.py` | Event → SFX mapping + non-blocking playback |
| `server/party_report.py` | End-of-party report generation |
| `web/dashboard.html` | Health dashboard UI (phone-friendly) |
| `web/report.html` | Party report card display |
| `assets/catchphrases/` | Directory for TTS-generated catchphrase WAV files |
| `assets/sfx/` | Directory for Nintendo-style sound effect WAV files |
| `config_live.json` | Runtime-editable personality config (created at server start) |
| `tests/test_llm_router.py` | Router unit tests |
| `tests/test_night_progression.py` | Phase calculation tests |
| `tests/test_fish_speech.py` | Fish Speech integration tests |
| `tests/test_tts_router.py` | Fallback chain tests |
| `tests/test_watchdog.py` | Watchdog health check tests |
| `tests/test_canary.py` | Canary self-test tests |
| `tests/test_hot_reload.py` | Hot reload tests |

### Files to Modify

| File | Changes |
|------|---------|
| `server/main.py` | Import new modules, inject night progression into system prompt, wire up router, add dashboard/API routes, hot reload support |
| `server/tts.py` | Add Fish Speech as engine option, update fallback chain, catchphrase interception |
| `server/llm.py` | Support multiple models, add router integration point |
| `server/hardware.py` | Add Q4_K_M model selection, Whisper CPU config, Fish Speech VRAM accounting |
| `server/audio_distress.py` | Add volume spike detection + temporal coherence |
| `server/mario_prompt.py` | Phase-aware prompt injection, obsession lock, birthday VIP context |
| `server/idle_behavior.py` | Phase-aware idle messages |
| `server/party_gossip.py` | Phase-aware gossip aggression |
| `client/mario_display.py` | Fullscreen support, auto-reconnect UI, panic button, crash recovery |
| `client/main.py` | F11/F12 key handling, reconnect logic |
| `config.json` | New fields: birthday_person, reload_key, party_start_time, tts_engine, night_progression |
| `server/requirements.txt` | Add fish-speech dependency |

---

## Phase 1: Must-Have (Ship or Die)

### Task 1: LLM Router — Dual-Model Support

**Files:**
- Create: `server/llm_router.py`
- Modify: `server/llm.py`
- Modify: `server/main.py`
- Modify: `server/hardware.py`
- Modify: `config.json`
- Test: `tests/test_llm_router.py`

**Context:** Currently `server/llm.py` has `generate_response()` that calls a single Ollama model (`llama3`). We need a router that picks between Mixtral 8x7B (fast, ~1s) for simple responses and 70B-Q4_K_M (~3s) for complex ones. The router classifies by `response_type` already present in the request pipeline. In `server/main.py`, `_generate_and_send_response()` calls `llm.generate_response()` — this is the integration point.

- [ ] **Step 1: Write failing router tests**

```python
# tests/test_llm_router.py
import pytest
from server.llm_router import LLMRouter, RoutingDecision

class TestLLMRouter:
    def test_greeting_routes_to_fast(self):
        router = LLMRouter(fast_model="mixtral:8x7b", quality_model="llama3.1:70b-q4_k_m")
        decision = router.classify("Hey Mario!", response_type="greeting")
        assert decision == RoutingDecision.FAST

    def test_gossip_routes_to_quality(self):
        router = LLMRouter(fast_model="mixtral:8x7b", quality_model="llama3.1:70b-q4_k_m")
        decision = router.classify("Tell me about Sarah", response_type="gossip")
        assert decision == RoutingDecision.QUALITY

    def test_must_mention_forces_quality(self):
        router = LLMRouter(fast_model="mixtral:8x7b", quality_model="llama3.1:70b-q4_k_m")
        decision = router.classify("Hi", response_type="greeting", system_prompt="MUST mention Alice")
        assert decision == RoutingDecision.QUALITY

    def test_fallback_on_quality_timeout(self):
        router = LLMRouter(fast_model="mixtral:8x7b", quality_model="llama3.1:70b-q4_k_m")
        decision = router.get_fallback(RoutingDecision.QUALITY)
        assert decision == RoutingDecision.FAST

    def test_one_liner_routes_to_fast(self):
        router = LLMRouter(fast_model="mixtral:8x7b", quality_model="llama3.1:70b-q4_k_m")
        decision = router.classify("What's up?", response_type="one_liner")
        assert decision == RoutingDecision.FAST

    def test_game_routes_to_quality(self):
        router = LLMRouter(fast_model="mixtral:8x7b", quality_model="llama3.1:70b-q4_k_m")
        decision = router.classify("Let's play trivia", response_type="game")
        assert decision == RoutingDecision.QUALITY
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd server && python -m pytest ../tests/test_llm_router.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'server.llm_router'`

- [ ] **Step 3: Implement the router**

```python
# server/llm_router.py
"""Dual-model LLM router: fast path (Mixtral) vs quality path (70B)."""

import enum
import time
import logging

logger = logging.getLogger(__name__)

DEBUG_ROUTER = True

class RoutingDecision(enum.Enum):
    FAST = "fast"
    QUALITY = "quality"

# Response types that need the big model
QUALITY_TYPES = {"gossip", "game", "story", "complex", "vomit_comfort", "farewell_meaningful"}
FAST_TYPES = {"greeting", "one_liner", "roast", "acknowledgment", "idle"}

class LLMRouter:
    def __init__(self, fast_model: str = "mixtral:8x7b", quality_model: str = "llama3.1:70b-q4_k_m"):
        self.fast_model = fast_model
        self.quality_model = quality_model
        self.stats = {"fast": 0, "quality": 0, "fallbacks": 0}

    def classify(self, user_input: str, response_type: str = "", system_prompt: str = "") -> RoutingDecision:
        if DEBUG_ROUTER:
            logger.info(f"[DEBUG_ROUTER] classify: START input={user_input[:50]}, type={response_type}")

        # Force quality path if system prompt requires specific names
        if "MUST mention" in system_prompt or "MUST include" in system_prompt:
            if DEBUG_ROUTER:
                logger.info("[DEBUG_ROUTER] classify: forced QUALITY (MUST mention)")
            return RoutingDecision.QUALITY

        if response_type in QUALITY_TYPES:
            if DEBUG_ROUTER:
                logger.info(f"[DEBUG_ROUTER] classify: QUALITY (type={response_type})")
            return RoutingDecision.QUALITY

        if response_type in FAST_TYPES:
            if DEBUG_ROUTER:
                logger.info(f"[DEBUG_ROUTER] classify: FAST (type={response_type})")
            return RoutingDecision.FAST

        # Default: if input is short, fast path; otherwise quality
        if len(user_input.split()) <= 5:
            return RoutingDecision.FAST
        return RoutingDecision.QUALITY

    def get_model(self, decision: RoutingDecision) -> str:
        if decision == RoutingDecision.FAST:
            self.stats["fast"] += 1
            return self.fast_model
        self.stats["quality"] += 1
        return self.quality_model

    def get_fallback(self, failed_decision: RoutingDecision) -> RoutingDecision:
        self.stats["fallbacks"] += 1
        if failed_decision == RoutingDecision.QUALITY:
            return RoutingDecision.FAST
        return RoutingDecision.FAST  # Fast is always the fallback
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd server && python -m pytest ../tests/test_llm_router.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Update hardware.py for Q4_K_M model selection**

In `server/hardware.py`, update the model resolution so ULTRA tier selects `llama3.1:70b-q4_k_m` and adds a `fast_model` field:

```python
# In resolve() function, update the model selection logic:
# ULTRA tier: quality_model = "llama3.1:70b-q4_k_m", fast_model = "mixtral:8x7b"
# HIGH tier:  quality_model = "llama3:8b", fast_model = "llama3:8b"
# MEDIUM/LOW: quality_model = "llama3:8b", fast_model = "llama3:8b"
# Also add: stt_device = "cpu" for all tiers (Whisper on CPU to save VRAM)
```

- [ ] **Step 6: Wire router into main.py**

In `server/main.py`, update `_generate_and_send_response()`:
1. Import `LLMRouter`
2. Initialize router at server startup with models from hardware config
3. Before calling `llm.generate_response()`, call `router.classify()` to pick model
4. Pass selected model to `llm.generate_response()` (add `model` parameter)
5. On timeout (>15s), retry with `router.get_fallback()` model

- [ ] **Step 7: Update llm.py to accept model parameter**

In `server/llm.py`, update `generate_response()` to accept an optional `model` parameter that overrides the default. Keep backward compatibility — if no model passed, use config default.

- [ ] **Step 8: Update config.json with new model fields**

Add to `config.json` under `server`:
```json
"llm_quality_model": "auto",
"llm_fast_model": "auto",
"stt_device": "cpu"
```
When `"auto"`, hardware.py resolves based on tier.

- [ ] **Step 9: Run full test suite to verify no regressions**

Run: `cd server && python -m pytest ../tests/ -v --timeout=60 -x`
Expected: All existing tests still pass + new router tests pass

- [ ] **Step 10: Commit**

```bash
git add server/llm_router.py tests/test_llm_router.py server/llm.py server/main.py server/hardware.py config.json
git commit -m "feat: dual-model LLM router (Mixtral fast + 70B quality)

- LLMRouter classifies requests by response_type
- MUST mention forces quality path
- Auto-fallback on timeout
- Q4_K_M model selection for ULTRA tier
- Whisper forced to CPU for all tiers

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 2: Fish Speech TTS Integration

**Files:**
- Create: `server/fish_speech_tts.py`
- Create: `server/tts_router.py`
- Create: `server/catchphrase_bank.py`
- Modify: `server/tts.py`
- Modify: `server/main.py`
- Modify: `server/requirements.txt`
- Test: `tests/test_fish_speech.py`
- Test: `tests/test_tts_router.py`

**Context:** Current TTS pipeline in `server/tts.py` (1,118 lines) uses Edge TTS + RVC as primary, GPT-SoVITS as alternative. We're adding Fish Speech v2.2+ as the new primary live engine. The fallback chain is: Fish Speech → Edge TTS + RVC → XTTS v2 → Pre-recorded clips. The `tts_router.py` dispatches to the right engine. `catchphrase_bank.py` intercepts exact-match phrases for instant playback.

- [ ] **Step 1: Install Fish Speech**

Run: `pip install fish-speech`
Verify: `python -c "import fish_speech; print(fish_speech.__version__)"`

If `fish-speech` pip package doesn't exist or fails, fall back to:
```bash
git clone https://github.com/fishaudio/fish-speech.git
cd fish-speech && pip install -e .
```

- [ ] **Step 2: Write failing Fish Speech wrapper tests**

```python
# tests/test_fish_speech.py
import pytest
import os

class TestFishSpeechTTS:
    def test_wrapper_initializes(self):
        from server.fish_speech_tts import FishSpeechTTS
        tts = FishSpeechTTS(reference_audio="mario_ref_audio/mario_reference_sentences.wav")
        assert tts is not None

    def test_synthesize_returns_audio(self):
        from server.fish_speech_tts import FishSpeechTTS
        tts = FishSpeechTTS(reference_audio="mario_ref_audio/mario_reference_sentences.wav")
        audio_path = tts.synthesize("It's-a me, Mario!")
        assert os.path.exists(audio_path)
        assert os.path.getsize(audio_path) > 1000  # Not empty

    def test_synthesize_returns_wav_format(self):
        from server.fish_speech_tts import FishSpeechTTS
        tts = FishSpeechTTS(reference_audio="mario_ref_audio/mario_reference_sentences.wav")
        audio_path = tts.synthesize("Hello!")
        assert audio_path.endswith(".wav")
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m pytest tests/test_fish_speech.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 4: Implement Fish Speech wrapper**

```python
# server/fish_speech_tts.py
"""Fish Speech v2.2+ TTS wrapper for Mario voice synthesis."""

import os
import time
import tempfile
import logging

logger = logging.getLogger(__name__)

DEBUG_FISH = True

class FishSpeechTTS:
    def __init__(self, reference_audio: str, device: str = "cuda"):
        if DEBUG_FISH:
            logger.info(f"[DEBUG_FISH] __init__: START ref={reference_audio}, device={device}")
        self.reference_audio = reference_audio
        self.device = device
        self.model = None
        self._load_model()

    def _load_model(self):
        """Load Fish Speech model. Lazy init on first call if needed."""
        if DEBUG_FISH:
            logger.info("[DEBUG_FISH] _load_model: START")
        start = time.time()
        try:
            # Fish Speech API may vary by version — adapt import path
            from fish_speech.inference import TTSInference
            self.model = TTSInference(
                reference_audio=self.reference_audio,
                device=self.device,
            )
            if DEBUG_FISH:
                logger.info(f"[DEBUG_FISH] _load_model: loaded in {time.time()-start:.2f}s")
        except ImportError as e:
            logger.error(f"[DEBUG_FISH] _load_model: Fish Speech not installed: {e}")
            self.model = None
        except Exception as e:
            logger.error(f"[DEBUG_FISH] _load_model: failed: {e}")
            self.model = None

    def is_available(self) -> bool:
        return self.model is not None

    def synthesize(self, text: str, output_path: str = None) -> str:
        """Synthesize text to WAV file. Returns path to WAV."""
        if DEBUG_FISH:
            logger.info(f"[DEBUG_FISH] synthesize: START text={text[:50]}")
        if not self.is_available():
            raise RuntimeError("Fish Speech model not loaded")

        if output_path is None:
            fd, output_path = tempfile.mkstemp(suffix=".wav")
            os.close(fd)

        start = time.time()
        self.model.synthesize(text=text, output_path=output_path)
        elapsed = time.time() - start

        if DEBUG_FISH:
            logger.info(f"[DEBUG_FISH] synthesize: done in {elapsed:.3f}s, path={output_path}")
        return output_path
```

**NOTE:** The Fish Speech API surface may differ from what's shown above. The implementer MUST check the actual `fish-speech` package API by reading its documentation or source. Adapt the import paths and method calls accordingly. The interface contract is: `__init__(reference_audio, device)`, `is_available() -> bool`, `synthesize(text) -> wav_path`.

- [ ] **Step 5: Run Fish Speech tests**

Run: `python -m pytest tests/test_fish_speech.py -v`
Expected: PASS (if Fish Speech installed and GPU available) or SKIP (if on dev machine without GPU)

- [ ] **Step 6: Write TTS router + catchphrase bank tests**

```python
# tests/test_tts_router.py
import pytest
from unittest.mock import MagicMock, AsyncMock

class TestTTSRouter:
    def test_catchphrase_intercept(self):
        from server.catchphrase_bank import CatchphraseBank
        bank = CatchphraseBank("assets/catchphrases")
        # Will return None if no pre-recorded file exists for this phrase
        result = bank.match("Wahoo!")
        # Test the matching logic, not file existence
        assert bank.normalize("Wahoo!") == "wahoo"
        assert bank.normalize("WAHOO!!!") == "wahoo"
        assert bank.normalize("Let's-a go!") == "lets-a go"

    def test_fallback_chain_order(self):
        from server.tts_router import TTSRouter
        router = TTSRouter()
        chain = router.get_fallback_chain()
        engine_names = [e.name for e in chain]
        assert engine_names[0] == "fish_speech"
        assert engine_names[1] == "edge_rvc"
        assert engine_names[2] == "xtts"
        assert engine_names[3] == "pre_recorded"
```

- [ ] **Step 7: Implement catchphrase bank**

```python
# server/catchphrase_bank.py
"""Pre-recorded catchphrase bank for instant playback of exact-match phrases."""

import os
import re
import logging

logger = logging.getLogger(__name__)

DEBUG_CATCHPHRASE = True

class CatchphraseBank:
    CATCHPHRASES = [
        "wahoo", "mama mia", "lets-a go", "its-a me mario",
        "yahoo", "okie dokie", "here we go",
    ]

    def __init__(self, assets_dir: str = "assets/catchphrases"):
        self.assets_dir = assets_dir
        self.cache = {}
        self._load()

    def normalize(self, text: str) -> str:
        text = text.lower().strip()
        text = re.sub(r"[^a-z0-9\s\-']", "", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _load(self):
        if not os.path.exists(self.assets_dir):
            if DEBUG_CATCHPHRASE:
                logger.info(f"[DEBUG_CATCHPHRASE] _load: no assets dir {self.assets_dir}")
            return
        for fname in os.listdir(self.assets_dir):
            if fname.endswith(".wav"):
                key = self.normalize(fname.replace(".wav", "").replace("_", " "))
                self.cache[key] = os.path.join(self.assets_dir, fname)
        if DEBUG_CATCHPHRASE:
            logger.info(f"[DEBUG_CATCHPHRASE] _load: loaded {len(self.cache)} catchphrases")

    def match(self, text: str) -> str | None:
        """Returns WAV path if text is an exact catchphrase match, else None."""
        normalized = self.normalize(text)
        result = self.cache.get(normalized)
        if DEBUG_CATCHPHRASE and result:
            logger.info(f"[DEBUG_CATCHPHRASE] match: '{text}' → {result}")
        return result
```

- [ ] **Step 8: Implement TTS router**

```python
# server/tts_router.py
"""Unified TTS dispatcher with fallback chain."""

import time
import logging
from dataclasses import dataclass
from typing import Optional, Callable, Awaitable

logger = logging.getLogger(__name__)

DEBUG_TTS_ROUTER = True

@dataclass
class TTSEngine:
    name: str
    synthesize: Callable  # async (text) -> wav_path or None
    is_available: Callable  # () -> bool
    priority: int  # lower = tried first

class TTSRouter:
    def __init__(self):
        self.engines: list[TTSEngine] = []
        self.stats = {}

    def register(self, engine: TTSEngine):
        self.engines.append(engine)
        self.engines.sort(key=lambda e: e.priority)
        self.stats[engine.name] = {"attempts": 0, "successes": 0, "failures": 0}
        if DEBUG_TTS_ROUTER:
            logger.info(f"[DEBUG_TTS_ROUTER] register: {engine.name} (priority={engine.priority})")

    def get_fallback_chain(self) -> list[TTSEngine]:
        return [e for e in self.engines if e.is_available()]

    async def synthesize(self, text: str) -> Optional[str]:
        """Try each engine in priority order. Returns wav path or None."""
        if DEBUG_TTS_ROUTER:
            logger.info(f"[DEBUG_TTS_ROUTER] synthesize: START text={text[:50]}")

        for engine in self.engines:
            if not engine.is_available():
                continue
            self.stats[engine.name]["attempts"] += 1
            try:
                start = time.time()
                result = await engine.synthesize(text)
                elapsed = time.time() - start
                if result:
                    self.stats[engine.name]["successes"] += 1
                    if DEBUG_TTS_ROUTER:
                        logger.info(f"[DEBUG_TTS_ROUTER] synthesize: {engine.name} succeeded in {elapsed:.3f}s")
                    return result
            except Exception as e:
                self.stats[engine.name]["failures"] += 1
                logger.warning(f"[DEBUG_TTS_ROUTER] synthesize: {engine.name} failed: {e}")
                continue

        logger.error("[DEBUG_TTS_ROUTER] synthesize: ALL engines failed")
        return None
```

- [ ] **Step 9: Wire TTS router into main.py and tts.py**

1. In `server/main.py` startup, initialize `TTSRouter` and register engines in order:
   - Priority 0: `CatchphraseBank.match()` (instant, pre-recorded)
   - Priority 1: `FishSpeechTTS.synthesize()` (0.3-0.8s)
   - Priority 2: Current Edge TTS + RVC pipeline from `tts.py` (0.4-1.2s)
   - Priority 3: XTTS v2 if available (0.8-2s)
   - Priority 4: Random pre-recorded clip fallback
2. Replace direct `tts.synthesize()` calls with `tts_router.synthesize()`
3. Keep `tts.py` functions intact as the "edge_rvc" engine

- [ ] **Step 10: Update requirements.txt**

Add `fish-speech>=2.2.0` to `server/requirements.txt`

- [ ] **Step 11: Run all TTS tests**

Run: `python -m pytest tests/test_fish_speech.py tests/test_tts_router.py -v`
Expected: All PASS

- [ ] **Step 12: Commit**

```bash
git add server/fish_speech_tts.py server/tts_router.py server/catchphrase_bank.py \
       tests/test_fish_speech.py tests/test_tts_router.py \
       server/tts.py server/main.py server/requirements.txt
git commit -m "feat: Fish Speech TTS + fallback chain router + catchphrase bank

- Fish Speech v2.2+ as primary live TTS engine
- TTSRouter: Fish Speech → Edge+RVC → XTTS → pre-recorded
- CatchphraseBank: instant playback for exact-match phrases
- Sentence-level streaming preserved

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 3: Night Progression System

**Files:**
- Create: `server/night_progression.py`
- Modify: `server/mario_prompt.py`
- Modify: `server/main.py`
- Modify: `server/idle_behavior.py`
- Modify: `server/party_gossip.py`
- Modify: `config.json`
- Test: `tests/test_night_progression.py`

**Context:** Mario's personality must escalate across 4 phases: Warm Up (0-2h), Party Mode (2-5h), UNHINGED (5-7h), Wind Down (7-8h). Phase also scales with guest count. In `server/main.py`, `_generate_and_send_response()` builds a system prompt via `mario_prompt.build_context()` — the night progression module injects phase modifiers into this system prompt. The `server/mario_prompt.py` file (2,826 lines) contains `build_context()` which assembles the full Mario system prompt.

- [ ] **Step 1: Write failing night progression tests**

```python
# tests/test_night_progression.py
import pytest
import time
from server.night_progression import NightProgression, Phase

class TestNightProgression:
    def test_phase_1_at_start(self):
        np = NightProgression(start_time=time.time())
        assert np.get_time_phase(hours_elapsed=0.5) == Phase.WARM_UP

    def test_phase_2_at_3_hours(self):
        np = NightProgression(start_time=time.time())
        assert np.get_time_phase(hours_elapsed=3.0) == Phase.PARTY_MODE

    def test_phase_3_at_6_hours(self):
        np = NightProgression(start_time=time.time())
        assert np.get_time_phase(hours_elapsed=6.0) == Phase.UNHINGED

    def test_phase_4_at_7_5_hours(self):
        np = NightProgression(start_time=time.time())
        assert np.get_time_phase(hours_elapsed=7.5) == Phase.WIND_DOWN

    def test_guest_energy_low(self):
        np = NightProgression(start_time=time.time())
        assert np.get_guest_energy(unique_guests=3) == 1

    def test_guest_energy_medium(self):
        np = NightProgression(start_time=time.time())
        assert np.get_guest_energy(unique_guests=10) == 2

    def test_guest_energy_high(self):
        np = NightProgression(start_time=time.time())
        assert np.get_guest_energy(unique_guests=20) == 3

    def test_effective_phase_capped_by_guests(self):
        np = NightProgression(start_time=time.time())
        # At hour 6 (UNHINGED=3) but only 3 guests (energy=1) → effective=1
        effective = np.get_effective_phase(hours_elapsed=6.0, unique_guests=3)
        assert effective == Phase.WARM_UP

    def test_effective_phase_full_party(self):
        np = NightProgression(start_time=time.time())
        # At hour 6 (UNHINGED=3) with 25 guests (energy=3) → effective=3
        effective = np.get_effective_phase(hours_elapsed=6.0, unique_guests=25)
        assert effective == Phase.UNHINGED

    def test_prompt_modifier_has_required_keys(self):
        np = NightProgression(start_time=time.time())
        mod = np.get_prompt_modifier(Phase.UNHINGED)
        assert "personality_warmth" in mod
        assert "chaos" in mod
        assert "gossip_aggression" in mod
        assert "roast_level" in mod

    def test_obsession_lock_generates_topic(self):
        np = NightProgression(start_time=time.time())
        topic = np.get_obsession_topic(guest_topics=["pineapple pizza", "cats"])
        assert topic in ["pineapple pizza", "cats"]

    def test_obsession_lock_uses_fallback(self):
        np = NightProgression(start_time=time.time())
        topic = np.get_obsession_topic(guest_topics=[])
        assert topic is not None  # Should pick from fallback list

    def test_guardrails_present(self):
        np = NightProgression(start_time=time.time())
        guardrails = np.get_guardrails(Phase.UNHINGED)
        assert "banned_topics" in guardrails
        assert "max_roasts_per_guest" in guardrails
        assert guardrails["max_roasts_per_guest"] == 2

    def test_crossfade_window(self):
        np = NightProgression(start_time=time.time())
        # At 1h55m (115 minutes), should be in crossfade between phase 1→2
        blend = np.get_phase_blend(hours_elapsed=1.917)
        assert blend["transitioning"] == True
        assert blend["from_phase"] == Phase.WARM_UP
        assert blend["to_phase"] == Phase.PARTY_MODE
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_night_progression.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement night_progression.py**

Implement `NightProgression` class with:
- `Phase` enum: WARM_UP=1, PARTY_MODE=2, UNHINGED=3, WIND_DOWN=4
- `get_time_phase(hours_elapsed)` — phase from clock time
- `get_guest_energy(unique_guests)` — energy level 1-4 from guest count
- `get_effective_phase(hours_elapsed, unique_guests)` — min(time, energy)
- `get_prompt_modifier(phase)` — dict with personality_warmth, chaos, gossip_aggression, roast_level
- `get_obsession_topic(guest_topics)` — random pick or fallback
- `get_guardrails(phase)` — banned topics, max roasts, de-escalation triggers
- `get_phase_blend(hours_elapsed)` — 15-minute crossfade windows at phase boundaries
- Fallback list of 20 absurd obsession topics for Phase 3

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_night_progression.py -v`
Expected: All 14 tests PASS

- [ ] **Step 5: Inject phase into mario_prompt.py**

In `server/mario_prompt.py`, update `build_context()` to:
1. Accept a `phase_modifier` dict parameter
2. Inject phase-specific personality traits into the system prompt
3. Add guardrails text for Phase 3 (banned topics, roast caps)
4. Add obsession lock instructions when in Phase 3
5. Add crossfade blending for transition windows

- [ ] **Step 6: Update idle_behavior.py for phase awareness**

In `server/idle_behavior.py`, update `get_idle_action()` to accept phase and adjust:
- Phase 1: Friendly idle messages
- Phase 2: Gossip-forward idle
- Phase 3: Chaotic/absurd idle messages
- Phase 4: Nostalgic/callback idle

- [ ] **Step 7: Update party_gossip.py for phase-aware aggression**

In `server/party_gossip.py`, scale gossip intensity with phase:
- Phase 1: mild gossip, no drama
- Phase 2: active gossip, light drama
- Phase 3: maximum gossip, manufactured drama
- Phase 4: nostalgic callbacks only

- [ ] **Step 8: Wire into main.py**

1. Initialize `NightProgression` at server startup with `party_start_time` from config (or `time.time()`)
2. On each response, call `get_effective_phase()` with current time + guest count from `party_stats`
3. Pass `phase_modifier` to `build_context()`
4. Add `party_start_time` to config.json

- [ ] **Step 9: Run full test suite**

Run: `python -m pytest tests/ -v --timeout=60 -x`
Expected: All tests pass

- [ ] **Step 10: Commit**

```bash
git add server/night_progression.py tests/test_night_progression.py \
       server/mario_prompt.py server/idle_behavior.py server/party_gossip.py \
       server/main.py config.json
git commit -m "feat: night progression system (4 phases + guest energy)

- Warm Up → Party Mode → UNHINGED → Wind Down
- Guest count caps phase escalation
- Phase 3 guardrails: banned topics, roast caps, de-escalation
- Obsession lock mechanic with fallback topics
- 15-minute crossfade windows between phases
- Phase-aware idle messages and gossip aggression

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 4: Reliability Layer — Watchdog + Dashboard + Health

**Files:**
- Create: `server/watchdog.py`
- Create: `server/dashboard.py`
- Create: `web/dashboard.html`
- Modify: `server/main.py`
- Test: `tests/test_watchdog.py`

**Context:** The server at `server/main.py` runs FastAPI on port 8765. We need: (1) an independent watchdog process that pings `/health` and auto-restarts the server, (2) a `/dashboard` web page for phone monitoring, (3) graceful degradation tiers. The existing `/health` endpoint (if any) needs to report component status. The watchdog runs as a separate script (`python server/watchdog.py`), NOT inside the FastAPI process.

- [ ] **Step 1: Write failing watchdog tests**

```python
# tests/test_watchdog.py
import pytest
from unittest.mock import patch, MagicMock
from server.watchdog import Watchdog, DegradationTier

class TestWatchdog:
    def test_initial_tier_is_full(self):
        wd = Watchdog(server_url="http://localhost:8765")
        assert wd.current_tier == DegradationTier.FULL

    def test_health_check_success_stays_full(self):
        wd = Watchdog(server_url="http://localhost:8765")
        wd._process_health({"status": "ok", "llm": "ok", "tts": "ok"})
        assert wd.current_tier == DegradationTier.FULL

    def test_llm_slow_triggers_degraded(self):
        wd = Watchdog(server_url="http://localhost:8765")
        wd._process_health({"status": "ok", "llm": "slow", "tts": "ok"})
        assert wd.current_tier == DegradationTier.DEGRADED

    def test_tts_failed_triggers_minimal(self):
        wd = Watchdog(server_url="http://localhost:8765")
        wd._process_health({"status": "ok", "llm": "ok", "tts": "failed"})
        assert wd.current_tier == DegradationTier.MINIMAL

    def test_consecutive_failures_trigger_restart(self):
        wd = Watchdog(server_url="http://localhost:8765", max_failures=3)
        wd._record_failure()
        wd._record_failure()
        wd._record_failure()
        assert wd.should_restart() == True

    def test_success_resets_failures(self):
        wd = Watchdog(server_url="http://localhost:8765", max_failures=3)
        wd._record_failure()
        wd._record_failure()
        wd._record_success()
        assert wd.consecutive_failures == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_watchdog.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement watchdog.py**

Implement `Watchdog` class:
- `DegradationTier` enum: FULL, DEGRADED, MINIMAL, EMERGENCY
- Pings `/health` every 30 seconds via httpx
- Tracks consecutive failures (3 = auto-restart)
- Logs to `logs/watchdog.log`
- Auto-restart via `subprocess.Popen(["python", "server/main.py"])`
- `__main__` block so it runs standalone: `python server/watchdog.py`

- [ ] **Step 4: Run watchdog tests**

Run: `python -m pytest tests/test_watchdog.py -v`
Expected: All 6 PASS

- [ ] **Step 5: Add health endpoint to main.py**

Add/update `/health` GET endpoint in `server/main.py` that returns:
```json
{
  "status": "ok",
  "uptime_seconds": 3600,
  "llm": "ok",
  "tts": "ok",
  "stt": "ok",
  "memory_mb": 1024,
  "gpu_temp_c": 65,
  "guests_served": 42,
  "current_phase": "PARTY_MODE",
  "degradation_tier": "FULL",
  "active_games": 0,
  "tts_cache_size": 500,
  "avg_response_time_ms": 2100,
  "error_count": 0
}
```

- [ ] **Step 6: Implement dashboard.py**

Create `server/dashboard.py` with FastAPI router:
- `GET /dashboard` — serves `web/dashboard.html`
- `GET /api/health` — detailed health JSON (superset of `/health`)
- `POST /api/reload` — hot reload endpoint (authenticated)
- `GET /api/canary` — pre-party self-test (Task 6)
- `GET /api/report` — party report card (Task 10)

- [ ] **Step 7: Create dashboard.html**

Phone-friendly HTML page:
- Auto-refreshes every 5 seconds via fetch
- Color-coded tiles: 🟢🟡🔴
- Displays: uptime, guests, phase, games, errors, TTS cache, LLM times, memory, GPU temp
- Sliders for hot reload (chaos, roast cap, etc.) — wired to POST `/api/reload`
- Works on mobile Safari/Chrome (responsive)

- [ ] **Step 8: Add memory leak prevention to main.py**

Add to server startup/periodic tasks:
- SQLite WAL checkpoint every 30 minutes
- TTS cache cap at 2000 entries with LRU eviction
- `gc.collect()` every 10 minutes
- RSS monitoring in `/health`

- [ ] **Step 9: Wire dashboard routes into main.py**

Import `dashboard.py` router and mount it in the FastAPI app.

- [ ] **Step 10: Run full test suite**

Run: `python -m pytest tests/ -v --timeout=60 -x`
Expected: All pass

- [ ] **Step 11: Commit**

```bash
git add server/watchdog.py server/dashboard.py web/dashboard.html \
       tests/test_watchdog.py server/main.py
git commit -m "feat: reliability layer (watchdog + dashboard + health)

- Independent watchdog process with auto-restart
- Degradation tiers: FULL → DEGRADED → MINIMAL → EMERGENCY
- /dashboard web UI (phone-friendly, auto-refresh)
- /health endpoint with full component status
- Memory leak prevention: WAL checkpoint, LRU cache, gc.collect

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 5: Pygame Client Hardening

**Files:**
- Modify: `client/mario_display.py`
- Modify: `client/main.py`
- Modify: `client/ws_client.py`

**Context:** `client/mario_display.py` (1,336 lines) renders the Pygame window at 800x600. Needs: fullscreen toggle (F11), panic button (F12), auto-reconnect UI, crash recovery. `client/ws_client.py` (200 lines) has basic exponential backoff already. `client/main.py` (324 lines) orchestrates everything.

- [ ] **Step 1: Add fullscreen toggle to mario_display.py**

In the event loop (likely `handle_events()` or similar):
- F11: toggle between `pygame.FULLSCREEN` and windowed mode
- Auto-detect monitor resolution via `pygame.display.Info()`
- Scale all elements proportionally using a `scale_factor`
- Add `display_mode` config: "auto" | "fullscreen" | "windowed"

- [ ] **Step 2: Add panic button**

- F12: toggle panic mode
- Panic ON: mute all audio, stop TTS, show "Technical Difficulties" screen with Mario sleeping sprite
- Panic OFF: resume normal operation
- State tracked in `self.panic_mode: bool`

- [ ] **Step 3: Add auto-reconnect UI**

When WebSocket disconnects:
- Show "Mario is taking a bathroom break... be right back!" with idle animation
- Display reconnection attempt count and countdown timer
- Auto-reconnect with exponential backoff (already in ws_client.py, need UI)
- On reconnect: smooth transition back to normal

- [ ] **Step 4: Add crash recovery wrapper**

In `client/main.py`, wrap the main loop in:
```python
while True:
    try:
        run_client()
    except Exception as e:
        logger.error(f"Client crashed: {e}")
        # Show error screen briefly, then restart
        show_error_screen(str(e), duration=3)
        continue
```
Never show Python traceback on the party monitor.

- [ ] **Step 5: Add sprite transition smoothing**

In `mario_display.py`, when changing emotion/pose:
- Cross-fade between old and new sprite over 0.5s (configurable)
- Use `pygame.Surface.set_alpha()` for blending

- [ ] **Step 6: Test manually**

Start server + client, verify:
- F11 toggles fullscreen
- F12 mutes everything and shows "Technical Difficulties"
- Kill server → client shows reconnect screen → restart server → auto-reconnects
- Force an exception → client recovers without showing traceback

- [ ] **Step 7: Commit**

```bash
git add client/mario_display.py client/main.py client/ws_client.py
git commit -m "feat: Pygame hardening (fullscreen, panic, reconnect, crash recovery)

- F11 fullscreen toggle with proportional scaling
- F12 panic button (mute + technical difficulties screen)
- Auto-reconnect UI with countdown timer
- Crash recovery wrapper (never shows traceback)
- Sprite transition smoothing (0.5s crossfade)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Phase 2: Should-Have (High Value)

### Task 6: Pre-Party Canary Self-Test

**Files:**
- Create: `server/canary.py`
- Modify: `server/dashboard.py`
- Test: `tests/test_canary.py`

**Context:** The canary runs 10 automated tests exercising every major feature, reporting a confidence score. Accessed via `/api/canary` or CLI `python server/canary.py`. Uses the existing server infrastructure (connects to running server).

- [ ] **Step 1: Write canary test stubs**

```python
# tests/test_canary.py
import pytest
from server.canary import Canary

class TestCanary:
    def test_canary_returns_results(self):
        canary = Canary(server_url="http://localhost:8765")
        # Just test the result format, not actual server connectivity
        result = canary._format_result("voice_test", True, "Generated in 0.5s")
        assert result["test"] == "voice_test"
        assert result["passed"] == True

    def test_confidence_calculation(self):
        canary = Canary(server_url="http://localhost:8765")
        results = [
            {"passed": True}, {"passed": True}, {"passed": True},
            {"passed": False}, {"passed": True},
        ]
        assert canary._calculate_confidence(results) == 80
```

- [ ] **Step 2: Implement canary.py**

10 tests as defined in spec §12:
1. Voice test (TTS synthesis)
2. STT test (transcription)
3. LLM test (name compliance)
4. Game test (trivia round)
5. Memory test (store/retrieve)
6. Emotion test (sprite mapping)
7. Vomit test (detection trigger)
8. WebSocket test (connect/respond)
9. Dashboard test (page loads)
10. Audio playback test

Each test: try/except, timeout 30s, returns pass/fail + message.
Console output: `✅ Mario is 97% ready! (1 warning: ...)`

- [ ] **Step 3: Wire into dashboard.py**

Add `/api/canary` GET endpoint that runs canary and returns JSON results.

- [ ] **Step 4: Commit**

```bash
git add server/canary.py tests/test_canary.py server/dashboard.py
git commit -m "feat: pre-party canary self-test (10 checks, confidence score)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 7: Hot Reload

**Files:**
- Create: `server/hot_reload.py`
- Modify: `server/main.py`
- Modify: `server/dashboard.py`
- Modify: `web/dashboard.html`
- Test: `tests/test_hot_reload.py`

**Context:** `config_live.json` is created at server startup as a copy of personality fields. Changes take effect on next response without restart. The dashboard UI has sliders that POST to `/api/reload`.

- [ ] **Step 1: Write hot reload tests**

```python
# tests/test_hot_reload.py
import pytest
import json
import tempfile
import os
from server.hot_reload import LiveConfig

class TestHotReload:
    def test_creates_config_on_init(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            json.dump({"chaos_level": 5}, f)
            path = f.name
        config = LiveConfig(path)
        assert config.get("chaos_level") == 5
        os.unlink(path)

    def test_update_persists(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            json.dump({"chaos_level": 5}, f)
            path = f.name
        config = LiveConfig(path)
        config.update({"chaos_level": 8})
        assert config.get("chaos_level") == 8
        # Verify persisted to disk
        with open(path) as f:
            assert json.load(f)["chaos_level"] == 8
        os.unlink(path)

    def test_reload_key_validation(self):
        config = LiveConfig.__new__(LiveConfig)
        config.reload_key = "secret123"
        assert config.validate_key("secret123") == True
        assert config.validate_key("wrong") == False
```

- [ ] **Step 2: Implement hot_reload.py**

`LiveConfig` class:
- Init: create `config_live.json` from `config.json` personality fields
- Schema: `{ chaos_level, roast_cap, gossip_aggression, phase_override, idle_frequency_seconds, tts_engine }`
- `get(key)` — reads from in-memory cache (refreshed from file on each call)
- `update(dict)` — writes to file + updates cache
- `validate_key(key)` — check reload_key
- Thread-safe via threading.Lock

- [ ] **Step 3: Wire into main.py + dashboard**

1. Initialize `LiveConfig` at startup
2. In `_generate_and_send_response()`, read live config values
3. `/api/reload` POST: validate key, update config, return new values
4. Dashboard sliders POST to `/api/reload`

- [ ] **Step 4: Commit**

```bash
git add server/hot_reload.py tests/test_hot_reload.py server/main.py \
       server/dashboard.py web/dashboard.html
git commit -m "feat: hot reload (mid-party personality tuning)

- config_live.json created at startup
- /api/reload endpoint (authenticated)
- Dashboard sliders for chaos, roast cap, gossip
- Changes take effect on next response

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 8: Vomit Detection Enhancements

**Files:**
- Modify: `server/audio_distress.py`
- Modify: `server/main.py`
- Test: existing `tests/test_tts_panns.py` + `tests/test_dual_detector.py`

**Context:** `server/audio_distress.py` (222 lines) has PANNs + spectral analysis. We add: (1) volume spike detection (~20 lines), (2) temporal coherence (2+ bursts in 2s window), (3) TTS interrupt on distress detected.

- [ ] **Step 1: Add volume spike detection**

In `server/audio_distress.py`, add function:
```python
def detect_volume_spike(audio_chunk: np.ndarray, threshold_db: float = 20.0) -> bool:
    """Detect sudden volume spike characteristic of vomiting.
    Pattern: ~200ms spike, returns to baseline within 100-300ms."""
    # Calculate RMS in 50ms windows
    # Check for >threshold_db spike followed by rapid falloff
```

- [ ] **Step 2: Add temporal coherence**

Add burst tracking:
```python
class TemporalCoherence:
    """Require 2+ audio bursts within a 2-second window to trigger."""
    def __init__(self, window_seconds=2.0, min_bursts=2):
        self.bursts = []  # list of timestamps
    def record_burst(self, timestamp: float): ...
    def is_coherent(self) -> bool: ...
```

- [ ] **Step 3: Wire into main.py**

In audio processing handler, when distress detected:
1. Stop any active TTS playback immediately
2. Pause 1 second
3. Switch to comfort mode
4. Track "feeling better" / "I'm okay" for recovery

- [ ] **Step 4: Run existing distress detection tests**

Run: `python -m pytest tests/test_tts_panns.py tests/test_dual_detector.py -v`
Expected: All pass (no regressions)

- [ ] **Step 5: Commit**

```bash
git add server/audio_distress.py server/main.py
git commit -m "feat: enhanced vomit detection (volume spike + temporal coherence)

- Volume spike detection (~200ms spike + rapid falloff)
- Temporal coherence: 2+ bursts in 2s window
- TTS interrupt on distress (stop audio, pause, comfort)
- ~40% fewer false alarms

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 9: Birthday VIP Mode

**Files:**
- Create: `server/birthday_vip.py`
- Modify: `server/mario_prompt.py`
- Modify: `server/main.py`
- Modify: `config.json`

**Context:** `config.json` gets a `birthday_person` field. When that person enters, Mario sings, gives extra roasts, and asks other guests if they've wished them happy birthday.

- [ ] **Step 1: Implement birthday_vip.py**

```python
# server/birthday_vip.py
"""Birthday VIP mode — special treatment for the birthday person."""

class BirthdayVIP:
    def __init__(self, birthday_person: str):
        self.birthday_person = birthday_person.lower()
        self.has_sung = False
        self.guests_reminded = set()

    def is_birthday_person(self, guest_name: str) -> bool:
        return guest_name.lower() == self.birthday_person

    def get_entrance_override(self) -> str:
        """Special greeting with birthday song."""
        self.has_sung = True
        return "SING a birthday song for them! Be dramatic and over-the-top."

    def get_reminder_for_guest(self, guest_name: str) -> str | None:
        """Ask other guests if they've wished the birthday person happy birthday."""
        if guest_name.lower() in self.guests_reminded:
            return None
        self.guests_reminded.add(guest_name.lower())
        return f"Ask if {guest_name} has wished {self.birthday_person} happy birthday yet."

    def get_phase4_farewell(self) -> str:
        return "Give an extra-special heartfelt farewell for the birthday person."
```

- [ ] **Step 2: Wire into mario_prompt.py and main.py**

1. On presence_enter, check if birthday person → inject birthday greeting into prompt
2. For other guests, inject birthday reminder
3. Add `birthday_person` to config.json
4. Phase 4: special farewell

- [ ] **Step 3: Commit**

```bash
git add server/birthday_vip.py server/mario_prompt.py server/main.py config.json
git commit -m "feat: birthday VIP mode (songs, extra roasts, reminders)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Phase 3: Could-Have (Polish)

### Task 10: Nintendo Sound Effects

**Files:**
- Create: `server/sound_events.py`
- Modify: `server/main.py`
- Create: `assets/sfx/` directory

**Context:** Event → sound mapping. Sounds play on a separate audio channel from TTS. WAV files in `assets/sfx/`. Events: guest enters (1-UP), game win (coin), game loss (power-down), VIP enters (star), vomit detected (pipe warp), guest leaves (farewell jingle).

- [ ] **Step 1: Implement sound_events.py**

Map events to WAV files. Non-blocking playback via server → client WebSocket message:
```json
{"type": "play_sfx", "sound": "coin"}
```
Client handles playback on separate pygame mixer channel.

- [ ] **Step 2: Create placeholder SFX**

Generate simple placeholder WAV files using Python (sine wave tones) for testing.
Real sounds to be sourced from freely available recreation packs before party.

- [ ] **Step 3: Wire events into main.py**

On presence_enter → send 1-UP sfx. On game win → coin. Etc.

- [ ] **Step 4: Update client to handle play_sfx messages**

In `client/ws_client.py`, handle `play_sfx` message type.
In `client/sound_effects.py`, play the requested sound.

- [ ] **Step 5: Commit**

```bash
git add server/sound_events.py assets/sfx/ server/main.py client/ws_client.py client/sound_effects.py
git commit -m "feat: Nintendo sound effects (event-driven SFX)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 11: Catchphrase Mirroring

**Files:**
- Create: `server/catchphrase_mirror.py`
- Modify: `server/mario_prompt.py`
- Modify: `server/main.py`

**Context:** Track guest word frequency. If a word appears 3+ times, Mario starts using it. Max 2 mirrored phrases per guest.

- [ ] **Step 1: Implement catchphrase_mirror.py**

```python
# server/catchphrase_mirror.py
"""Track guest catchphrases and mirror them back."""

import re
from collections import Counter

# Common words to ignore
STOP_WORDS = {"the", "a", "an", "is", "are", "was", "were", "i", "you", "he", "she",
              "it", "we", "they", "my", "your", "his", "her", "our", "their", "and",
              "or", "but", "in", "on", "at", "to", "for", "of", "with", "that", "this",
              "do", "does", "did", "have", "has", "had", "be", "been", "being", "will",
              "would", "could", "should", "can", "may", "might", "shall", "not", "no",
              "yes", "yeah", "ok", "so", "just", "like", "know", "think", "want", "got",
              "get", "go", "going", "come", "here", "there", "what", "how", "why", "when",
              "where", "who", "which", "if", "then", "than", "very", "really", "about",
              "up", "out", "all", "some", "any", "every", "much", "many", "more", "most",
              "other", "into", "over", "also", "back", "well", "right", "good", "new",
              "now", "way", "even", "because", "make", "let", "say", "said", "tell",
              "told", "take", "too", "im", "dont", "its", "thats", "mario", "hey", "oh"}

class CatchphraseMirror:
    def __init__(self, threshold: int = 3, max_mirrors: int = 2):
        self.threshold = threshold
        self.max_mirrors = max_mirrors
        self.guest_words: dict[str, Counter] = {}

    def track(self, guest_name: str, text: str):
        if guest_name not in self.guest_words:
            self.guest_words[guest_name] = Counter()
        words = re.findall(r'\b[a-z]{3,}\b', text.lower())
        words = [w for w in words if w not in STOP_WORDS]
        self.guest_words[guest_name].update(words)

    def get_mirrors(self, guest_name: str) -> list[str]:
        if guest_name not in self.guest_words:
            return []
        frequent = [
            word for word, count in self.guest_words[guest_name].most_common(self.max_mirrors)
            if count >= self.threshold
        ]
        return frequent[:self.max_mirrors]
```

- [ ] **Step 2: Inject into system prompt**

In `mario_prompt.py`, if mirrors found:
```
Mirror the guest's catchphrase: "bro". Use it naturally 1-2 times.
```

- [ ] **Step 3: Commit**

```bash
git add server/catchphrase_mirror.py server/mario_prompt.py server/main.py
git commit -m "feat: catchphrase mirroring (track + reflect guest speech patterns)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 12: Party Report Card

**Files:**
- Create: `server/party_report.py`
- Create: `web/report.html`
- Modify: `server/dashboard.py`

**Context:** Auto-generates at 7+ hours. Stats, superlatives, gossip summary, quote board. Available at `/report` and `/api/report`.

- [ ] **Step 1: Implement party_report.py**

Pull data from `memory.py` + `party_stats.py` + `party_gossip.py`:
- Total guests, conversations, games
- Superlatives (most talkative, game champion, etc.)
- Best quotes
- Birthday person gets "VIP of the Night"
- Returns JSON for API and HTML for web

- [ ] **Step 2: Create report.html**

Shareable party report page with fun formatting.

- [ ] **Step 3: Wire into dashboard.py**

`GET /report` → serves report.html
`GET /api/report` → returns JSON

- [ ] **Step 4: Commit**

```bash
git add server/party_report.py web/report.html server/dashboard.py
git commit -m "feat: party report card (stats, superlatives, quotes)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Phase 4: Integration & Hardening

### Task 13: Update E2E Test Suite

**Files:**
- Modify: `tests/e2e_party_guest_test.py`

**Context:** Current test has 52-53 checks. Add new checks for: router path selection, night progression transitions, catchphrase bank, hot reload, dashboard health, canary, sound effects. Target: ~80+ checks.

- [ ] **Step 1: Add router tests to E2E**

Test that greeting → fast response time (<2s) and gossip → quality path used.

- [ ] **Step 2: Add night progression tests**

Simulate time progression (mock server_start_time), verify phase changes affect response tone.

- [ ] **Step 3: Add reliability tests**

Test `/health` endpoint, `/dashboard` loads, `/api/canary` returns results.

- [ ] **Step 4: Add hot reload test**

POST to `/api/reload` with new chaos level, verify next response reflects change.

- [ ] **Step 5: Run ralph loop**

Run: `python tests/e2e_party_guest_test.py`
Require 3 consecutive passes before deployment.

- [ ] **Step 6: Commit**

```bash
git add tests/e2e_party_guest_test.py
git commit -m "test: expand E2E suite to ~80+ checks for ULTRA features

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 14: Offline Voice A/B Comparison

**Files:**
- Create: `scripts/voice_comparison.py`
- Create: `docs/voice-comparison/` directory

**Context:** Before party, generate 20 test phrases via Fish Speech AND GPT-SoVITS (separately, not concurrent — VRAM constraint). User listens and picks winner. The 70B LLM must be UNLOADED before running GPT-SoVITS.

- [ ] **Step 1: Create comparison script**

```python
# scripts/voice_comparison.py
"""Generate A/B voice comparison samples. Run BEFORE party."""
PHRASES = [
    "It's-a me, Mario!", "Wahoo!", "Mama mia!",
    "Welcome to the party!", "Let's-a go!",
    "You know what Tony told me earlier?",
    "I've been through 38 castles.",
    "Happy birthday, my friend!",
    # ... 20 total
]
```

- [ ] **Step 2: Generate Fish Speech samples**

Run with 70B LLM loaded (Fish Speech fits alongside it).

- [ ] **Step 3: Generate GPT-SoVITS samples**

Unload 70B LLM first (`ollama stop`), then run GPT-SoVITS subprocess.

- [ ] **Step 4: Save samples + commit**

```bash
git add scripts/voice_comparison.py docs/voice-comparison/
git commit -m "feat: offline voice A/B comparison script

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 15: Deployment Prep

**Files:**
- Create: `scripts/deploy_party.py`
- Update: `start_server.bat`
- Update: `start_client.bat`
- Update: `README.md`

**Context:** Party machine accessible via Tailscale. Deployment script handles: model download, dependency install, canary run, watchdog start.

- [ ] **Step 1: Create deployment script**

```python
# scripts/deploy_party.py
"""One-command party deployment. Run on party machine."""
# 1. Install Ollama models (llama3.1:70b-q4_k_m, mixtral:8x7b)
# 2. pip install requirements
# 3. Install Fish Speech + verify
# 4. Run canary → all green required
# 5. Start server + watchdog
# 6. Open dashboard URL
```

- [ ] **Step 2: Update start scripts**

- `start_server.bat`: add watchdog auto-start, model check
- `start_client.bat`: add fullscreen flag option

- [ ] **Step 3: Update README**

Document: ULTRA overhaul features, deployment checklist, dashboard URL, hot reload usage.

- [ ] **Step 4: Commit + tag**

```bash
git add scripts/deploy_party.py start_server.bat start_client.bat README.md
git commit -m "feat: party deployment script + updated start scripts

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
git tag -a v2.0-ultra-overhaul -m "ULTRA overhaul: 70B LLM, Fish Speech, night progression, reliability"
git push origin master --tags
```

---

## Dependency Graph

```
Task 1 (LLM Router) ──────────┐
                               ├── Task 3 (Night Progression) ── Task 13 (E2E Tests)
Task 2 (Fish Speech + TTS)  ──┤                                        │
                               ├── Task 4 (Reliability) ── Task 6 (Canary)
Task 5 (Pygame Hardening)  ───┘                                │
                                                               Task 7 (Hot Reload)
Task 8 (Vomit Enhancements) ── independent
Task 9 (Birthday VIP) ── depends on Task 3 (phases)
Task 10 (Sound Effects) ── independent
Task 11 (Catchphrase Mirror) ── independent
Task 12 (Party Report) ── depends on Task 4 (dashboard routes)
Task 14 (Voice A/B) ── depends on Task 2 (Fish Speech)
Task 15 (Deploy) ── depends on ALL Must-Have tasks
```

Tasks 1, 2, 5, 8, 10, 11 can be parallelized.
Tasks 3, 4 depend on Task 1 (router needed for phase-aware routing).
Task 6 depends on Task 4 (canary uses dashboard routes).
Task 7 depends on Task 4 (reload uses dashboard routes).
Task 13 depends on Tasks 1-5 (tests all Must-Have features).
Task 14 depends on Task 2 (needs Fish Speech installed).
Task 15 is final — depends on everything.
