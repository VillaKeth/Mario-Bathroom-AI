"""Unified TTS dispatcher with fallback chain and parallel synthesis.

Routes synthesis requests through a priority-ordered chain of TTS engines:
  Priority 0: Catchphrase bank (instant, pre-recorded)
  Priority 1: Fish Speech (0.3-0.8s)
  Priority 2: Edge TTS + RVC (0.4-1.2s, current pipeline)
  Priority 3: XTTS v2 if available (0.8-2s)
  Priority 4: Pre-recorded generic clips (instant fallback)

Supports sentence-level parallel synthesis with configurable concurrency.
"""

import asyncio
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class TTSEngine:
    """A registered TTS engine in the fallback chain.

    Attributes:
        name: Human-readable engine identifier.
        synthesize_fn: Sync callable (text, **kwargs) -> bytes | None.
        is_available_fn: Callable () -> bool.
        priority: Lower = tried first.
    """
    name: str
    synthesize_fn: Callable
    is_available_fn: Callable
    priority: int


class TTSRouter:
    """Unified TTS dispatcher with fallback chain and stats tracking.

    Tries each registered engine in priority order until one succeeds.
    Tracks per-engine success/failure counts for observability.
    """

    def __init__(self, max_parallel: int = 8):
        self._engines: list[TTSEngine] = []
        self.stats: dict[str, dict] = {}
        self._semaphore = asyncio.Semaphore(max_parallel)
        logger.debug(f"[tts_router] Initialized with max_parallel={max_parallel}")

    def register(self, engine: TTSEngine):
        """Register a TTS engine and sort the chain by priority."""
        self._engines.append(engine)
        # Stable sort: engines with same priority keep registration order
        self._engines.sort(key=lambda e: e.priority)
        self.stats.setdefault(engine.name, {"successes": 0, "failures": 0, "total_ms": 0})
        logger.debug(f"[tts_router] Registered engine: {engine.name} (priority={engine.priority})")

    def get_fallback_chain(self) -> list[TTSEngine]:
        """Return available engines sorted by priority (lower first)."""
        available = []
        for engine in self._engines:
            try:
                if engine.is_available_fn():
                    available.append(engine)
            except Exception as e:
                logger.debug(f"[tts_router] is_available check failed for {engine.name}: {e}")
        return available

    def synthesize(self, text: str, rate: str = None, pitch: str = None,
                   nocache: bool = False, **kwargs) -> Optional[bytes]:
        """Try each engine in priority order, return WAV bytes or None.

        Matches the existing tts.synthesize() signature for drop-in replacement.
        """
        chain = self.get_fallback_chain()
        if not chain:
            logger.debug("[tts_router] synthesize: no available engines")
            return None

        for engine in chain:
            t0 = time.monotonic()
            try:
                result = engine.synthesize_fn(text, rate=rate, pitch=pitch, nocache=nocache, **kwargs)
                elapsed_ms = (time.monotonic() - t0) * 1000
                if result is not None and result:  # Non-empty bytes
                    self.stats[engine.name]["successes"] += 1
                    self.stats[engine.name]["total_ms"] += elapsed_ms
                    logger.debug(
                        f"[tts_router] synthesize: {engine.name} succeeded in {elapsed_ms:.0f}ms "
                        f"({len(result)} bytes) for '{text[:40]}...'"
                    )
                    return result
                else:
                    # Engine returned empty/None — try next
                    logger.debug(f"[tts_router] synthesize: {engine.name} returned empty, trying next")
                    continue
            except Exception as e:
                elapsed_ms = (time.monotonic() - t0) * 1000
                self.stats[engine.name]["failures"] += 1
                logger.debug(f"[tts_router] synthesize: {engine.name} failed ({elapsed_ms:.0f}ms): {e}")
                continue

        logger.debug(f"[tts_router] synthesize: all engines exhausted for '{text[:40]}...'")
        return None

    def synthesize_user(self, text: str, rate: str = None, pitch: str = None,
                        nocache: bool = False, **kwargs) -> Optional[bytes]:
        """User-priority synthesis. Wraps synthesize() with priority signaling.

        If the original tts module's _user_tts_waiting event is available,
        sets it to pause background precaching during user synthesis.
        """
        try:
            import tts as _tts_module
            if hasattr(_tts_module, '_user_tts_waiting'):
                _tts_module._user_tts_waiting.set()
        except ImportError:
            pass

        try:
            return self.synthesize(text, rate=rate, pitch=pitch, nocache=nocache, **kwargs)
        finally:
            try:
                import tts as _tts_module
                if hasattr(_tts_module, '_user_tts_waiting'):
                    _tts_module._user_tts_waiting.clear()
            except ImportError:
                pass

    def split_sentences(self, text: str) -> list[str]:
        """Split text into speakable sentence chunks.

        Splits on sentence-ending punctuation (.!?) while keeping the
        punctuation attached to the sentence.
        """
        if not text or not text.strip():
            return []

        chunks = re.split(r'(?<=[.!?])\s+', text.strip())
        return [c.strip() for c in chunks if c.strip()]

    async def parallel_synthesize(self, text: str, rate: str = None,
                                  pitch: str = None) -> list[bytes]:
        """Split text into sentences and synthesize them in parallel.

        Uses asyncio.Semaphore to limit concurrency (default 8 workers).
        Returns list of WAV bytes in sentence order.
        First sentence is dispatched immediately for low-latency playback.
        """
        sentences = self.split_sentences(text)
        if not sentences:
            return []

        logger.debug(f"[tts_router] parallel_synthesize: {len(sentences)} sentences")

        loop = asyncio.get_event_loop()
        results: list[Optional[bytes]] = [None] * len(sentences)

        async def _synth_one(index: int, sentence: str):
            async with self._semaphore:
                logger.debug(f"[tts_router] parallel_synthesize: starting sentence {index+1}/{len(sentences)}")
                audio = await loop.run_in_executor(
                    None, lambda s=sentence: self.synthesize(s, rate=rate, pitch=pitch)
                )
                results[index] = audio

        tasks = [_synth_one(i, s) for i, s in enumerate(sentences)]
        await asyncio.gather(*tasks, return_exceptions=True)

        return [r for r in results if r is not None]

    def get_engine_stats(self) -> dict:
        """Return per-engine statistics for observability."""
        summary = {}
        for name, s in self.stats.items():
            total = s["successes"] + s["failures"]
            avg_ms = s["total_ms"] / max(1, s["successes"])
            summary[name] = {
                "successes": s["successes"],
                "failures": s["failures"],
                "total_calls": total,
                "avg_ms": round(avg_ms, 1),
                "success_rate": f"{s['successes'] / max(1, total) * 100:.0f}%",
            }
        return summary


# Module-level singleton for global access
_router: Optional[TTSRouter] = None


def get_router() -> Optional[TTSRouter]:
    """Get the global TTSRouter singleton."""
    return _router


def init_router(max_parallel: int = 8) -> TTSRouter:
    """Initialize and return the global TTSRouter singleton."""
    global _router
    _router = TTSRouter(max_parallel=max_parallel)
    logger.debug(f"[tts_router] Global router initialized (max_parallel={max_parallel})")
    return _router
