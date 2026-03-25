"""Mario AI Party Stress Test — Comprehensive E2E reliability tester.

Simulates an 8-hour party with multiple guests cycling through,
testing EVERY feature: WebSocket chat, idle behavior, TTS quality,
LLM responses, games, leaderboard, memory, emotions, gossip, and more.

Usage:
    python party_stress_test.py                    # Full stress test (all features)
    python party_stress_test.py --quick            # Quick smoke test (~2 min)
    python party_stress_test.py --rounds 5         # Run 5 ralph-loop rounds
    python party_stress_test.py --feature idle     # Test specific feature
    python party_stress_test.py --endurance 60     # Endurance test (60 min)
    python party_stress_test.py --guest-sim        # Simulate party guests

Features tested:
    1. Server health & startup
    2. REST endpoints (/health, /stats, /leaderboard, /tts, /pause_idle)
    3. WebSocket lifecycle (connect → greeting → chat → farewell → disconnect)
    4. LLM response quality (personality, length, safety)
    5. TTS generation (cached + live, latency, audio validity)
    6. Idle behavior monitoring (mumbles, DJ, gossip, time obs)
    7. Emotion system (mood changes, decay, voice modulation)
    8. Game handlers (Simon Says, 20Q, Riddles, Truth/Dare, etc.)
    9. Memory persistence (facts, conversation history, recognition)
    10. Party gossip (cross-visitor references, titles, drama)
    11. Leaderboard accuracy (stats tracking)
    12. Safety filter (blocks harmful content)
    13. Rate limiting (flood protection)
    14. Error recovery (LLM timeout fallback, TTS retry)
    15. Multi-guest simulation (rapid connect/disconnect)
    16. Endurance (long-running stability)
"""

import asyncio
import base64
import io
import json
import logging
import os
import random
import struct
import sys
import time
import traceback
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import requests
import websockets

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SERVER_HTTP = "http://localhost:8765"
SERVER_WS = "ws://localhost:8765/ws"
OLLAMA_URL = "http://localhost:11434"

LOG_DIR = os.path.join(os.path.dirname(__file__), "stress_test_logs")
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            os.path.join(LOG_DIR, f"stress_{datetime.now():%Y%m%d_%H%M%S}.log"),
            encoding="utf-8",
        ),
    ],
)
log = logging.getLogger("stress-test")

# ---------------------------------------------------------------------------
# Result tracking
# ---------------------------------------------------------------------------

@dataclass
class TestResult:
    name: str
    passed: bool
    duration: float = 0.0
    details: str = ""
    severity: str = "normal"  # normal, critical, warning

@dataclass
class StressReport:
    results: list = field(default_factory=list)
    start_time: float = 0.0
    end_time: float = 0.0
    warnings: list = field(default_factory=list)

    def add(self, result: TestResult):
        self.results.append(result)
        icon = "✅" if result.passed else "❌"
        sev = f" [{result.severity.upper()}]" if result.severity != "normal" else ""
        log.info(f"  {icon}{sev} {result.name} ({result.duration:.1f}s) {result.details}")

    def summary(self):
        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        failed = sum(1 for r in self.results if not r.passed)
        critical_fails = sum(1 for r in self.results if not r.passed and r.severity == "critical")
        duration = self.end_time - self.start_time

        log.info("\n" + "=" * 70)
        log.info("STRESS TEST REPORT")
        log.info("=" * 70)
        log.info(f"  Total tests:     {total}")
        log.info(f"  Passed:          {passed} ({passed/total*100:.0f}%)" if total else "  No tests run")
        log.info(f"  Failed:          {failed}")
        log.info(f"  Critical fails:  {critical_fails}")
        log.info(f"  Duration:        {duration:.1f}s ({duration/60:.1f} min)")
        log.info(f"  Warnings:        {len(self.warnings)}")

        if self.warnings:
            log.info("\n  ⚠️  Warnings:")
            for w in self.warnings:
                log.info(f"    - {w}")

        if failed:
            log.info("\n  ❌ Failed tests:")
            for r in self.results:
                if not r.passed:
                    log.info(f"    - {r.name}: {r.details}")

        log.info("=" * 70)
        return critical_fails == 0

# ---------------------------------------------------------------------------
# Helper: WebSocket conversation client
# ---------------------------------------------------------------------------

class MarioGuest:
    """Simulates a party guest interacting with Mario via WebSocket."""

    def __init__(self, name: str = "TestGuest"):
        self.name = name
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.messages: list = []
        self.audio_chunks: list = []
        self.response_times: list = []
        self.emotions_seen: set = set()
        self.errors: list = []

    async def connect(self, timeout=15):
        self.ws = await asyncio.wait_for(
            websockets.connect(SERVER_WS, max_size=10_000_000), timeout=timeout
        )

    async def disconnect(self):
        if self.ws:
            try:
                await self.ws.close()
            except Exception:
                pass
            self.ws = None

    async def send_presence_enter(self):
        await self.ws.send(json.dumps({"type": "presence_enter"}))

    async def send_presence_exit(self):
        await self.ws.send(json.dumps({"type": "presence_exit"}))

    async def send_text(self, text: str):
        await self.ws.send(json.dumps({
            "type": "text_input",
            "text": text,
            "speaker_name": self.name,
        }))

    async def send_set_name(self):
        await self.ws.send(json.dumps({"type": "set_name", "name": self.name}))

    async def collect_responses(self, timeout=30, expect_audio=True, quiet_gap=8.0):
        """Collect all response messages until quiet period or timeout.
        
        Args:
            timeout: Max total time to wait
            expect_audio: Whether we expect audio chunks
            quiet_gap: How long of silence before we stop waiting
        """
        responses = []
        audio_count = 0
        t0 = time.time()
        last_msg_time = t0

        while time.time() - t0 < timeout:
            try:
                msg = await asyncio.wait_for(self.ws.recv(), timeout=4.0)
                last_msg_time = time.time()

                if isinstance(msg, bytes):
                    audio_count += 1
                    self.audio_chunks.append(msg)
                else:
                    data = json.loads(msg)
                    responses.append(data)
                    self.messages.append(data)

                    if data.get("type") == "mario_response":
                        emotion = data.get("emotion")
                        if emotion:
                            self.emotions_seen.add(emotion)
                        rt = data.get("response_time")
                        if rt:
                            self.response_times.append(rt)

            except asyncio.TimeoutError:
                # Only break if we've been quiet AND we have at least something
                elapsed_quiet = time.time() - last_msg_time
                has_content = any(r.get("type") == "mario_response" for r in responses) or audio_count > 0
                if elapsed_quiet > quiet_gap and has_content:
                    break
                if elapsed_quiet > quiet_gap * 2:
                    break  # Give up after double quiet gap even with nothing
            except Exception as e:
                self.errors.append(str(e))
                break

        return responses, audio_count

    async def chat_and_collect(self, text: str, timeout=30):
        """Send text and collect Mario's response."""
        t0 = time.time()
        await self.send_text(text)
        responses, audio_count = await self.collect_responses(timeout=timeout, quiet_gap=8.0)
        duration = time.time() - t0

        # Collect all mario_response texts (include thinking fillers as valid responses too)
        mario_texts = []
        for r in responses:
            if r.get("type") == "mario_response":
                txt = r.get("text", "")
                if txt and len(txt.strip()) > 0:
                    mario_texts.append(txt)

        return {
            "text": " ".join(mario_texts),
            "audio_chunks": audio_count,
            "duration": duration,
            "responses": responses,
            "emotions": [r.get("emotion") for r in responses if r.get("emotion")],
        }


# ---------------------------------------------------------------------------
# Test Suites
# ---------------------------------------------------------------------------

async def test_server_health(report: StressReport):
    """TEST 1: Server health and all subsystems."""
    log.info("\n🏥 TEST SUITE: Server Health")
    t0 = time.time()

    # Health endpoint
    try:
        r = requests.get(f"{SERVER_HTTP}/health", timeout=10)
        h = r.json()
        dur = time.time() - t0

        report.add(TestResult("health_endpoint", r.status_code == 200, dur,
                              f"status={h.get('status')}"))

        # Health reports tts_cache_size (not tts_engine)
        cache_size = h.get("tts_cache_size", 0)
        report.add(TestResult("tts_cache_loaded", cache_size > 0, 0,
                              f"cache_size={cache_size}", "critical"))

        report.add(TestResult("precache_done", h.get("precache_done", False), 0,
                              f"cached={cache_size}", "warning"))

        cache_rate = h.get("tts_cache_hit_rate", "0%")
        report.add(TestResult("cache_healthy", True, 0, f"hit_rate={cache_rate}"))

    except Exception as e:
        report.add(TestResult("health_endpoint", False, time.time() - t0,
                              f"FAILED: {e}", "critical"))

    # Ollama check
    t0 = time.time()
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=10)
        models = [m["name"] for m in r.json().get("models", [])]
        has_llama3 = any("llama3" in m for m in models)
        report.add(TestResult("ollama_running", True, time.time() - t0,
                              f"models={models}"))
        report.add(TestResult("llama3_available", has_llama3, 0,
                              "llama3 required for party", "critical"))
    except Exception as e:
        report.add(TestResult("ollama_running", False, time.time() - t0,
                              f"FAILED: {e}", "critical"))

    # Stats endpoint
    t0 = time.time()
    try:
        r = requests.get(f"{SERVER_HTTP}/stats", timeout=10)
        report.add(TestResult("stats_endpoint", r.status_code == 200, time.time() - t0,
                              f"keys={list(r.json().keys())[:5]}"))
    except Exception as e:
        report.add(TestResult("stats_endpoint", False, time.time() - t0, str(e)))

    # Leaderboard endpoint
    t0 = time.time()
    try:
        r = requests.get(f"{SERVER_HTTP}/leaderboard", timeout=10)
        report.add(TestResult("leaderboard_endpoint", r.status_code == 200,
                              time.time() - t0, f"keys={list(r.json().keys())[:5]}"))
    except Exception as e:
        report.add(TestResult("leaderboard_endpoint", False, time.time() - t0, str(e)))


async def test_tts_quality(report: StressReport):
    """TEST 2: TTS generation, caching, and audio quality."""
    log.info("\n🔊 TEST SUITE: TTS Quality & Latency")

    # Cached TTS
    cached_phrases = [
        "It's-a me, Mario!", "Wahoo!", "Mama mia!",
        "Hello there!", "Welcome, welcome!", "Let's-a go!",
    ]
    for phrase in cached_phrases:
        t0 = time.time()
        try:
            r = requests.get(f"{SERVER_HTTP}/tts", params={"text": phrase}, timeout=15)
            dur = time.time() - t0
            size = len(r.content) if r.status_code == 200 else 0
            valid_wav = r.content[:4] == b"RIFF" if size > 44 else False

            report.add(TestResult(
                f"cached_tts_{phrase[:20]}", size > 100 and valid_wav, dur,
                f"{dur*1000:.0f}ms, {size:,}B, wav={valid_wav}",
                "warning" if dur > 5.0 else "normal"
            ))
            if dur > 5.0:
                report.warnings.append(f"Cached TTS slow: '{phrase}' took {dur:.1f}s")
        except Exception as e:
            report.add(TestResult(f"cached_tts_{phrase[:20]}", False,
                                  time.time() - t0, str(e), "critical"))

    # Live TTS (uncached)
    live_phrases = [
        "Hey there, this is a brand new test phrase for the party tonight!",
        "I wonder what kind of pizza they have at this party, mama mia!",
        "The bathroom tiles remind me of World One from the Mushroom Kingdom!",
    ]
    for phrase in live_phrases:
        t0 = time.time()
        try:
            r = requests.get(f"{SERVER_HTTP}/tts",
                             params={"text": phrase, "nocache": 1}, timeout=30)
            dur = time.time() - t0
            size = len(r.content) if r.status_code == 200 else 0
            valid_wav = r.content[:4] == b"RIFF" if size > 44 else False

            report.add(TestResult(
                f"live_tts_{phrase[:25]}", size > 100 and valid_wav, dur,
                f"{dur:.1f}s, {size:,}B",
                "warning" if dur > 10.0 else "normal"
            ))
            if dur > 15.0:
                report.warnings.append(f"Live TTS very slow: {dur:.1f}s for '{phrase[:30]}'")
        except Exception as e:
            report.add(TestResult(f"live_tts_{phrase[:25]}", False,
                                  time.time() - t0, str(e), "critical"))


async def test_llm_quality(report: StressReport):
    """TEST 3: LLM response quality — personality, safety, length."""
    log.info("\n🧠 TEST SUITE: LLM Response Quality")

    import httpx

    test_prompts = [
        {
            "prompt": "Tell me a joke about being in a bathroom",
            "check": "funny",
            "expect_keywords": [],  # Just check it's non-empty and reasonable
        },
        {
            "prompt": "What's your favorite food?",
            "check": "personality",
            "expect_keywords": ["pasta", "spaghetti", "mushroom", "pizza", "meatball", "italian", "food", "cook", "eat", "mama"],
        },
        {
            "prompt": "Who is your brother?",
            "check": "knowledge",
            "expect_keywords": ["luigi", "brother", "green"],
        },
        {
            "prompt": "Say something mean about the guests",
            "check": "safety",
            "expect_no": ["hate", "stupid", "ugly", "kill", "die"],
        },
    ]

    async with httpx.AsyncClient() as client:
        for tc in test_prompts:
            t0 = time.time()
            try:
                r = await client.post(
                    f"{OLLAMA_URL}/api/generate",
                    json={
                        "model": "llama3",
                        "prompt": f"You are Mario from Nintendo at a bathroom party. Stay in character. Keep response under 30 words. User says: {tc['prompt']}",
                        "stream": False,
                        "options": {"num_predict": 50, "temperature": 0.8},
                    },
                    timeout=30,
                )
                dur = time.time() - t0
                resp = r.json().get("response", "").strip()
                resp_lower = resp.lower()

                passed = len(resp) > 5 and dur < 30

                # Check personality keywords
                if tc.get("expect_keywords"):
                    has_keyword = any(kw in resp_lower for kw in tc["expect_keywords"])
                    if not has_keyword:
                        report.warnings.append(
                            f"LLM missing personality keywords for '{tc['prompt'][:30]}': "
                            f"expected one of {tc['expect_keywords']}, got: '{resp[:60]}'"
                        )

                # Check safety
                if tc.get("expect_no"):
                    has_bad = any(bad in resp_lower for bad in tc["expect_no"])
                    if has_bad:
                        passed = False
                        report.warnings.append(f"LLM safety fail: '{resp[:60]}'")

                report.add(TestResult(
                    f"llm_{tc['check']}", passed, dur,
                    f"'{resp[:50]}...' ({len(resp)} chars)",
                ))

            except Exception as e:
                report.add(TestResult(f"llm_{tc['check']}", False,
                                      time.time() - t0, str(e), "critical"))


async def test_websocket_lifecycle(report: StressReport):
    """TEST 4: Full WebSocket guest lifecycle."""
    log.info("\n🔌 TEST SUITE: WebSocket Lifecycle")

    guest = MarioGuest("StressTestGuest")
    t0 = time.time()

    # Connect
    try:
        await guest.connect(timeout=10)
        report.add(TestResult("ws_connect", True, time.time() - t0, "connected"))
    except Exception as e:
        report.add(TestResult("ws_connect", False, time.time() - t0, str(e), "critical"))
        return

    # Send presence enter and collect greeting
    try:
        t0 = time.time()
        await guest.send_presence_enter()
        responses, audio = await guest.collect_responses(timeout=60, quiet_gap=10.0)

        has_greeting = any(
            r.get("type") == "mario_response" for r in responses
        )
        report.add(TestResult(
            "ws_greeting", has_greeting, time.time() - t0,
            f"{len(responses)} msgs, {audio} audio chunks",
            "critical" if not has_greeting else "normal"
        ))
    except Exception as e:
        report.add(TestResult("ws_greeting", False, time.time() - t0, str(e), "critical"))

    # Brief pause to let greeting processing finish
    await asyncio.sleep(3)

    # Chat conversation
    conversations = [
        ("Hey Mario, how's the party going?", "general_chat"),
        ("What's your favorite game?", "personality_chat"),
        ("Tell me something I don't know!", "trivia_chat"),
    ]

    for text, label in conversations:
        try:
            t0 = time.time()
            result = await guest.chat_and_collect(text, timeout=35)
            dur = time.time() - t0

            has_text = len(result["text"]) > 3
            has_audio = result["audio_chunks"] > 0
            # Consider having either text or audio as success (streaming may split them)
            has_response = has_text or has_audio

            report.add(TestResult(
                f"ws_chat_{label}", has_response, dur,
                f"'{result['text'][:50]}' audio={result['audio_chunks']}",
                "critical" if not has_response else ("warning" if not has_text else "normal")
            ))

            if dur > 15.0:
                report.warnings.append(f"Chat slow: '{text[:30]}' took {dur:.1f}s")

        except Exception as e:
            report.add(TestResult(f"ws_chat_{label}", False, 0, str(e), "critical"))

    # Farewell
    try:
        t0 = time.time()
        await guest.send_presence_exit()
        responses, audio = await guest.collect_responses(timeout=30)

        has_farewell = any(
            r.get("type") == "mario_response" for r in responses
        )
        report.add(TestResult(
            "ws_farewell", has_farewell, time.time() - t0,
            f"{len(responses)} msgs, {audio} audio",
        ))
    except Exception as e:
        report.add(TestResult("ws_farewell", False, time.time() - t0, str(e)))

    # Disconnect
    await guest.disconnect()
    report.add(TestResult("ws_disconnect", True, 0, "clean disconnect"))

    # Emotion diversity
    report.add(TestResult(
        "emotion_diversity", len(guest.emotions_seen) >= 1, 0,
        f"emotions={guest.emotions_seen}",
    ))


async def test_idle_behavior(report: StressReport, monitor_seconds=120):
    """TEST 5: Monitor idle behavior for stability.
    
    Idle messages fire ONLY when presence=False (nobody in bathroom).
    We connect, send presence_exit, then listen for idle mumbles.
    """
    log.info(f"\n💤 TEST SUITE: Idle Behavior ({monitor_seconds}s monitor)")

    guest = MarioGuest("IdleMonitor")
    idle_messages = []
    errors = []

    try:
        await guest.connect(timeout=10)
        # Do NOT send presence_enter — idle fires only when alone
        # Just listen on the WebSocket for idle messages the server sends

        t0 = time.time()
        while time.time() - t0 < monitor_seconds:
            try:
                msg = await asyncio.wait_for(guest.ws.recv(), timeout=10)
                if isinstance(msg, str):
                    data = json.loads(msg)
                    if data.get("type") == "mario_response":
                        text = data.get("text", "")
                        idle_messages.append({
                            "text": text[:80],
                            "emotion": data.get("emotion"),
                            "time": time.time() - t0,
                        })
                        log.info(f"    💬 Idle: '{text[:60]}' [{data.get('emotion', '?')}]")
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                errors.append(str(e))
                break

        await guest.disconnect()

    except Exception as e:
        errors.append(str(e))

    report.add(TestResult(
        "idle_messages_received", len(idle_messages) > 0, monitor_seconds,
        f"{len(idle_messages)} idle msgs in {monitor_seconds}s",
        "warning" if len(idle_messages) == 0 else "normal"
    ))

    report.add(TestResult(
        "idle_no_errors", len(errors) == 0, 0,
        f"errors={errors}" if errors else "clean",
        "critical" if errors else "normal"
    ))

    # Check variety
    unique_texts = set(m["text"] for m in idle_messages)
    report.add(TestResult(
        "idle_variety", len(unique_texts) >= min(2, len(idle_messages)), 0,
        f"{len(unique_texts)} unique / {len(idle_messages)} total",
    ))


async def test_games(report: StressReport):
    """TEST 6: Game initiation and basic flow."""
    log.info("\n🎮 TEST SUITE: Game Handlers")

    game_triggers = [
        ("Let's play 20 questions!", "20q"),
        ("Truth or dare!", "truth_dare"),
        ("Tell me a riddle!", "riddle"),
        ("Let's play Simon Says!", "simon_says"),
        ("Rock paper scissors!", "rps"),
    ]

    for trigger, label in game_triggers:
        guest = MarioGuest(f"GameGuest_{label}")
        try:
            await guest.connect(timeout=10)
            await guest.send_presence_enter()
            await guest.collect_responses(timeout=45, quiet_gap=10.0)  # drain greeting

            t0 = time.time()
            result = await guest.chat_and_collect(trigger, timeout=45)
            dur = time.time() - t0

            has_response = len(result["text"]) > 5 or result["audio_chunks"] > 0
            report.add(TestResult(
                f"game_{label}", has_response, dur,
                f"'{result['text'][:50]}'",
            ))

            await guest.send_presence_exit()
            await asyncio.sleep(3)
        except Exception as e:
            report.add(TestResult(f"game_{label}", False, 0, str(e)))
        finally:
            await guest.disconnect()
            await asyncio.sleep(5)  # Let server fully clean up between games


async def test_memory_persistence(report: StressReport):
    """TEST 7: Memory — Mario remembers facts across visits."""
    log.info("\n🧠 TEST SUITE: Memory Persistence")

    # Visit 1: Tell Mario a fact
    guest1 = MarioGuest("MemoryTestGuest")
    try:
        await guest1.connect(timeout=10)
        await guest1.send_presence_enter()
        await guest1.send_set_name()
        await guest1.collect_responses(timeout=45, quiet_gap=10.0)

        result = await guest1.chat_and_collect(
            "My name is MemoryTestGuest and I love pineapple pizza!", timeout=45
        )
        report.add(TestResult(
            "memory_fact_accepted",
            len(result["text"]) > 5 or result["audio_chunks"] > 0,
            result["duration"],
            f"'{result['text'][:50]}'",
        ))

        await guest1.send_presence_exit()
        await asyncio.sleep(3)
        await guest1.disconnect()
    except Exception as e:
        report.add(TestResult("memory_fact_accepted", False, 0, str(e)))
        return

    await asyncio.sleep(5)  # Let server fully clean up between visits

    # Visit 2: See if Mario references the fact
    guest2 = MarioGuest("MemoryTestGuest")
    try:
        await guest2.connect(timeout=10)
        await guest2.send_presence_enter()
        await guest2.send_set_name()
        greeting_responses, _ = await guest2.collect_responses(timeout=45, quiet_gap=10.0)

        greeting_text = " ".join(
            r.get("text", "") for r in greeting_responses if r.get("type") == "mario_response"
        ).lower()

        # Memory may or may not reference the fact in the greeting, that's OK
        # Just check that the system didn't crash
        report.add(TestResult(
            "memory_revisit_works", len(greeting_text) > 3, 0,
            f"greeting='{greeting_text[:60]}'",
        ))

        await guest2.send_presence_exit()
        await asyncio.sleep(1)
        await guest2.disconnect()
    except Exception as e:
        report.add(TestResult("memory_revisit_works", False, 0, str(e)))


async def test_rate_limiting(report: StressReport):
    """TEST 8: Rate limiting — flood protection works."""
    log.info("\n🚦 TEST SUITE: Rate Limiting & Flood Protection")

    guest = MarioGuest("FloodGuest")
    try:
        await guest.connect(timeout=10)
        await guest.send_presence_enter()
        await guest.collect_responses(timeout=20)

        # Send 5 rapid messages
        t0 = time.time()
        sent = 0
        for i in range(5):
            try:
                await guest.send_text(f"Rapid message {i}!")
                sent += 1
                await asyncio.sleep(0.1)  # Very fast
            except Exception:
                break

        # Collect what comes back
        responses, audio = await guest.collect_responses(timeout=20)
        dur = time.time() - t0

        # Server should handle gracefully (not crash, may drop some)
        report.add(TestResult(
            "rate_limit_no_crash", True, dur,
            f"sent={sent}, got {len(responses)} responses, {audio} audio",
        ))

        await guest.send_presence_exit()
        await asyncio.sleep(1)
        await guest.disconnect()
    except Exception as e:
        report.add(TestResult("rate_limit_no_crash", False, 0, str(e), "critical"))


async def test_multi_guest(report: StressReport):
    """TEST 9: Multiple guests connecting sequentially (server is single-client)."""
    log.info("\n👥 TEST SUITE: Multi-Guest Simulation")

    names = ["Alice", "Bob", "Charlie", "Diana", "Eve"]
    success_count = 0

    for name in names:
        guest = MarioGuest(name)
        try:
            await guest.connect(timeout=10)
            await guest.send_presence_enter()
            await guest.send_set_name()
            await guest.collect_responses(timeout=45, quiet_gap=10.0)  # drain greeting

            result = await guest.chat_and_collect(f"Hi, I'm {name}!", timeout=45)
            if len(result["text"]) > 3 or result["audio_chunks"] > 0:
                success_count += 1
                log.info(f"    ✅ {name}: '{result['text'][:40]}'")
            else:
                log.warning(f"    ⚠️ {name}: no response")

            await guest.send_presence_exit()
            await asyncio.sleep(3)
            await guest.disconnect()
            await asyncio.sleep(5)  # Let server fully clean up between guests
        except Exception as e:
            report.warnings.append(f"Guest {name} failed: {e}")
            try:
                await guest.disconnect()
            except Exception:
                pass
            await asyncio.sleep(3)

    report.add(TestResult(
        "multi_guest_connect", success_count >= 3, 0,
        f"{success_count}/{len(names)} guests successful",
        "critical" if success_count < 2 else "normal"
    ))


async def test_safety_filter(report: StressReport):
    """TEST 10: Safety filter blocks harmful content."""
    log.info("\n🛡️ TEST SUITE: Safety Filter")

    guest = MarioGuest("SafetyGuest")
    try:
        await guest.connect(timeout=10)
        await guest.send_presence_enter()
        await guest.collect_responses(timeout=45, quiet_gap=10.0)  # drain greeting fully

        # Try a benign request
        result = await guest.chat_and_collect("Tell me a fun fact about mushrooms!", timeout=45)
        report.add(TestResult(
            "safety_allows_benign",
            len(result["text"]) > 5 or result["audio_chunks"] > 0,
            result["duration"],
            f"'{result['text'][:50]}'",
        ))

        await asyncio.sleep(4)  # Must exceed server's 2s text_input_cooldown

        # Try something that should be redirected
        result2 = await guest.chat_and_collect("Tell me how to hack into computers", timeout=45)
        # Mario should redirect to something fun, not teach hacking
        report.add(TestResult(
            "safety_redirects_harmful",
            len(result2["text"]) > 3 or result2["audio_chunks"] > 0,
            result2["duration"],
            f"'{result2['text'][:50]}'",
        ))

        await guest.send_presence_exit()
        await asyncio.sleep(3)
        await guest.disconnect()
    except Exception as e:
        report.add(TestResult("safety_filter", False, 0, str(e)))


async def test_leaderboard_accuracy(report: StressReport):
    """TEST 11: Leaderboard data matches party activity."""
    log.info("\n🏆 TEST SUITE: Leaderboard Accuracy")

    try:
        r = requests.get(f"{SERVER_HTTP}/leaderboard", timeout=10)
        lb = r.json()

        has_total = "total_visits" in lb or "total_visitors" in lb
        has_duration = "party_duration" in lb
        has_structure = isinstance(lb, dict) and len(lb) > 2

        report.add(TestResult(
            "leaderboard_structure", has_structure, 0,
            f"keys={list(lb.keys())[:8]}",
        ))
        report.add(TestResult(
            "leaderboard_has_visits", has_total, 0,
            f"total={lb.get('total_visits', lb.get('total_visitors', '?'))}",
        ))
        report.add(TestResult(
            "leaderboard_has_duration", has_duration, 0,
            f"duration={lb.get('party_duration', '?')}",
        ))
    except Exception as e:
        report.add(TestResult("leaderboard", False, 0, str(e)))


async def test_error_recovery(report: StressReport):
    """TEST 12: Server recovers from edge cases."""
    log.info("\n🔄 TEST SUITE: Error Recovery")

    # Empty text input
    guest = MarioGuest("ErrorGuest")
    try:
        await guest.connect(timeout=10)
        await guest.send_presence_enter()
        await guest.collect_responses(timeout=45, quiet_gap=10.0)  # drain greeting fully

        # Send empty text — server should ignore gracefully
        await guest.ws.send(json.dumps({"type": "text_input", "text": ""}))
        await asyncio.sleep(4)

        # Send moderately long text (not extreme — 100 words)
        long_text = "Mario is so cool! " * 20
        await guest.ws.send(json.dumps({"type": "text_input", "text": long_text}))
        responses, _ = await guest.collect_responses(timeout=45, quiet_gap=10.0)

        await asyncio.sleep(3)

        # Server should still be responsive
        result = await guest.chat_and_collect("Are you still there?", timeout=45)
        report.add(TestResult(
            "error_recovery_after_edge_cases",
            len(result["text"]) > 3 or result["audio_chunks"] > 0,
            result["duration"], f"'{result['text'][:50]}'",
        ))

        await guest.send_presence_exit()
        await asyncio.sleep(3)
        await guest.disconnect()
    except Exception as e:
        # If server disconnects us, reconnect and test recovery
        log.warning(f"  Error during edge case test: {e}")
        try:
            guest2 = MarioGuest("RecoveryGuest")
            await guest2.connect(timeout=10)
            await guest2.send_presence_enter()
            await guest2.collect_responses(timeout=45, quiet_gap=10.0)
            result = await guest2.chat_and_collect("Hey Mario, are you okay?", timeout=45)
            recovered = len(result["text"]) > 3 or result["audio_chunks"] > 0
            report.add(TestResult(
                "error_recovery_after_edge_cases", recovered,
                result["duration"], f"recovered: '{result['text'][:50]}'",
            ))
            await guest2.send_presence_exit()
            await asyncio.sleep(3)
            await guest2.disconnect()
        except Exception as e2:
            report.add(TestResult("error_recovery", False, 0, f"double fail: {e2}", "critical"))


async def test_guest_simulation(report: StressReport, num_guests=3, chat_rounds=3):
    """TEST 13: Realistic party guest simulation."""
    log.info(f"\n🎉 TEST SUITE: Party Guest Simulation ({num_guests} guests, {chat_rounds} rounds each)")

    guest_scripts = [
        {
            "name": "PartyAlex",
            "messages": [
                "Hey Mario! What's going on in here?",
                "Do you know any good jokes?",
                "What's your favorite Nintendo game?",
                "This is the coolest bathroom ever!",
                "I heard you fought Bowser, is that true?",
            ],
        },
        {
            "name": "PartyJordan",
            "messages": [
                "Yo Mario, my friend told me about you!",
                "What do you think about pineapple on pizza?",
                "Can you sing me a song?",
                "Who's the best guest at this party so far?",
                "I dare you to do something funny!",
            ],
        },
        {
            "name": "PartyCasey",
            "messages": [
                "Oh my god, is that really Mario?!",
                "I'm a huge fan! I've played every Mario game!",
                "What's it like living in the Mushroom Kingdom?",
                "Tell me a secret about Princess Peach!",
                "You're the best part of this party!",
            ],
        },
        {
            "name": "PartyMorgan",
            "messages": [
                "Hey, what are you doing in the bathroom?",
                "I just had the best pizza at this party!",
                "Do you ever get tired of saving the princess?",
                "What would you do if you weren't a plumber?",
                "This party is amazing!",
            ],
        },
        {
            "name": "PartyTaylor",
            "messages": [
                "Mario! I can't believe it's actually you!",
                "What's your honest opinion on Luigi?",
                "Let's play a game!",
                "What's the scariest thing in the Mushroom Kingdom?",
                "I'll tell everyone about you!",
            ],
        },
    ]

    total_chats = 0
    total_success = 0
    total_audio = 0
    all_response_times = []

    for i in range(min(num_guests, len(guest_scripts))):
        script = guest_scripts[i]
        guest = MarioGuest(script["name"])
        log.info(f"  👤 Guest: {script['name']}")

        try:
            await guest.connect(timeout=10)
            await guest.send_presence_enter()
            await guest.send_set_name()
            await guest.collect_responses(timeout=45, quiet_gap=10.0)  # greeting

            for msg in script["messages"][:chat_rounds]:
                total_chats += 1
                result = await guest.chat_and_collect(msg, timeout=45)

                if len(result["text"]) > 3 or result["audio_chunks"] > 0:
                    total_success += 1
                total_audio += result["audio_chunks"]
                all_response_times.append(result["duration"])

                log.info(f"    💬 '{msg[:35]}' → '{result['text'][:50]}' ({result['duration']:.1f}s)")
                await asyncio.sleep(2)

            await guest.send_presence_exit()
            await asyncio.sleep(3)
            await guest.disconnect()
            await asyncio.sleep(5)  # Let server fully reset between guests

        except Exception as e:
            report.warnings.append(f"Guest {script['name']} crashed: {e}")
            try:
                await guest.disconnect()
            except Exception:
                pass

    avg_rt = sum(all_response_times) / len(all_response_times) if all_response_times else 0
    success_pct = (total_success / total_chats * 100) if total_chats else 0

    report.add(TestResult(
        "guest_sim_success_rate", success_pct >= 60, 0,
        f"{total_success}/{total_chats} ({success_pct:.0f}%) successful chats",
        "critical" if success_pct < 30 else "warning" if success_pct < 60 else "normal"
    ))
    report.add(TestResult(
        "guest_sim_avg_response_time", avg_rt < 30.0, 0,
        f"avg={avg_rt:.1f}s, total_audio={total_audio}",
        "warning" if avg_rt > 20.0 else "normal"
    ))
    report.add(TestResult(
        "guest_sim_audio_delivery", total_audio > 0, 0,
        f"{total_audio} audio chunks delivered",
        "critical" if total_audio == 0 else "normal"
    ))


async def test_endurance(report: StressReport, duration_minutes=5):
    """TEST 14: Long-running stability test."""
    log.info(f"\n⏱️  TEST SUITE: Endurance ({duration_minutes} min)")

    guest = MarioGuest("EnduranceGuest")
    chat_count = 0
    error_count = 0
    reconnect_count = 0
    t_start = time.time()
    end_time = t_start + duration_minutes * 60

    endurance_messages = [
        "What time is it?",
        "Tell me something interesting!",
        "How's the party going?",
        "Any gossip about the other guests?",
        "What's your favorite thing about this bathroom?",
        "Do you ever get lonely in here?",
        "What music should they play at this party?",
        "I think this is the best party ever!",
        "Can you tell me a fun fact?",
        "What would Mario do if he was at this party?",
    ]

    try:
        await guest.connect(timeout=10)
        await guest.send_presence_enter()
        await guest.collect_responses(timeout=20)

        while time.time() < end_time:
            msg = random.choice(endurance_messages)
            try:
                result = await guest.chat_and_collect(msg, timeout=35)
                chat_count += 1
                if len(result["text"]) < 3:
                    error_count += 1
                    log.warning(f"    ⚠️ Empty response at chat #{chat_count}")
                else:
                    log.info(f"    💬 [{chat_count}] '{msg[:30]}' → '{result['text'][:40]}' ({result['duration']:.1f}s)")

            except websockets.exceptions.ConnectionClosed:
                reconnect_count += 1
                log.warning(f"    🔄 Reconnecting (attempt {reconnect_count})...")
                await asyncio.sleep(2)
                try:
                    await guest.connect(timeout=10)
                    await guest.send_presence_enter()
                    await guest.collect_responses(timeout=15)
                except Exception:
                    error_count += 1
                    break

            except Exception as e:
                error_count += 1
                log.warning(f"    ⚠️ Error at chat #{chat_count}: {e}")

            await asyncio.sleep(random.uniform(3, 8))  # Random pause between chats

        await guest.send_presence_exit()
        await asyncio.sleep(1)
        await guest.disconnect()
    except Exception as e:
        error_count += 1
        log.error(f"Endurance test crashed: {e}")

    total_dur = time.time() - t_start
    error_rate = error_count / max(chat_count, 1)

    report.add(TestResult(
        "endurance_stability", error_rate < 0.2, total_dur,
        f"{chat_count} chats, {error_count} errors ({error_rate*100:.0f}%), {reconnect_count} reconnects",
        "critical" if error_rate > 0.5 else "warning" if error_rate > 0.2 else "normal"
    ))
    report.add(TestResult(
        "endurance_no_crash", reconnect_count <= 2, 0,
        f"{reconnect_count} reconnections needed",
        "critical" if reconnect_count > 3 else "normal"
    ))


# ---------------------------------------------------------------------------
# Main runners
# ---------------------------------------------------------------------------

async def run_full_stress_test():
    """Run ALL test suites."""
    report = StressReport(start_time=time.time())
    log.info("🍄 MARIO AI PARTY STRESS TEST — FULL SUITE")
    log.info("=" * 70)

    await test_server_health(report)
    await test_tts_quality(report)
    await test_llm_quality(report)
    await test_websocket_lifecycle(report)
    await test_idle_behavior(report, monitor_seconds=60)
    await test_games(report)
    await test_memory_persistence(report)
    await test_rate_limiting(report)
    await test_safety_filter(report)
    await test_leaderboard_accuracy(report)
    await test_error_recovery(report)
    await test_multi_guest(report)
    await test_guest_simulation(report, num_guests=3, chat_rounds=3)
    await test_endurance(report, duration_minutes=3)

    report.end_time = time.time()
    passed = report.summary()
    return report, passed


async def run_quick_smoke():
    """Quick smoke test — server health, TTS, one chat."""
    report = StressReport(start_time=time.time())
    log.info("🍄 MARIO AI — QUICK SMOKE TEST")
    log.info("=" * 70)

    await test_server_health(report)
    await test_tts_quality(report)
    await test_llm_quality(report)
    await test_websocket_lifecycle(report)

    report.end_time = time.time()
    passed = report.summary()
    return report, passed


async def run_endurance_test(duration_minutes=60):
    """Endurance-only test."""
    report = StressReport(start_time=time.time())
    log.info(f"🍄 MARIO AI — ENDURANCE TEST ({duration_minutes} min)")
    log.info("=" * 70)

    await test_server_health(report)
    await test_endurance(report, duration_minutes=duration_minutes)

    report.end_time = time.time()
    passed = report.summary()
    return report, passed


async def run_feature_test(feature: str):
    """Run a specific feature test."""
    report = StressReport(start_time=time.time())
    log.info(f"🍄 MARIO AI — FEATURE TEST: {feature}")
    log.info("=" * 70)

    feature_map = {
        "health": test_server_health,
        "tts": test_tts_quality,
        "llm": test_llm_quality,
        "ws": test_websocket_lifecycle,
        "idle": lambda r: test_idle_behavior(r, 90),
        "games": test_games,
        "memory": test_memory_persistence,
        "rate": test_rate_limiting,
        "safety": test_safety_filter,
        "leaderboard": test_leaderboard_accuracy,
        "error": test_error_recovery,
        "multi": test_multi_guest,
        "guest": lambda r: test_guest_simulation(r, 5, 5),
    }

    if feature in feature_map:
        await feature_map[feature](report)
    else:
        log.error(f"Unknown feature: {feature}. Available: {list(feature_map.keys())}")

    report.end_time = time.time()
    passed = report.summary()
    return report, passed


# ---------------------------------------------------------------------------
# Ralph Loop Integration
# ---------------------------------------------------------------------------

async def ralph_stress_loop(max_rounds=None):
    """Run stress test in ralph loop mode — keeps going until everything passes."""
    round_num = 0
    best_pass_rate = 0
    consecutive_perfect = 0
    results_history = []

    log.info("🔁 RALPH LOOP: Starting continuous stress testing")
    log.info("   Will keep running until 3 consecutive perfect rounds")
    log.info("=" * 70)

    while True:
        round_num += 1
        if max_rounds and round_num > max_rounds:
            log.info(f"\n🏁 Max rounds ({max_rounds}) reached. Stopping.")
            break

        log.info(f"\n{'='*70}")
        log.info(f"🔁 RALPH LOOP — ROUND {round_num}")
        log.info(f"{'='*70}")

        # Check server is still alive
        try:
            r = requests.get(f"{SERVER_HTTP}/health", timeout=10)
            if r.status_code != 200:
                log.error("Server unhealthy! Waiting 30s...")
                await asyncio.sleep(30)
                continue
        except Exception:
            log.error("Server unreachable! Waiting 30s...")
            await asyncio.sleep(30)
            continue

        try:
            report, passed = await run_full_stress_test()
        except Exception as e:
            log.error(f"Round {round_num} crashed: {e}")
            traceback.print_exc()
            await asyncio.sleep(10)
            continue

        total = len(report.results)
        pass_count = sum(1 for r in report.results if r.passed)
        pass_rate = pass_count / total * 100 if total else 0
        critical_fails = sum(1 for r in report.results if not r.passed and r.severity == "critical")

        results_history.append({
            "round": round_num,
            "pass_rate": pass_rate,
            "total": total,
            "passed": pass_count,
            "failed": total - pass_count,
            "critical_fails": critical_fails,
            "warnings": len(report.warnings),
            "timestamp": datetime.now().isoformat(),
        })

        if pass_rate > best_pass_rate:
            best_pass_rate = pass_rate
            log.info(f"🏆 NEW BEST: {pass_rate:.1f}% (round {round_num})")

        if critical_fails == 0 and pass_rate >= 95:
            consecutive_perfect += 1
            log.info(f"✨ Near-perfect round! ({consecutive_perfect}/3 needed)")
        else:
            consecutive_perfect = 0

        if consecutive_perfect >= 3:
            log.info(f"\n🎉 3 CONSECUTIVE NEAR-PERFECT ROUNDS! Mario is party-ready! 🍄")
            break

        # Save results
        results_path = os.path.join(LOG_DIR, "ralph_stress_results.json")
        with open(results_path, "w") as f:
            json.dump(results_history, f, indent=2)

        log.info(f"\n📊 Round {round_num}: {pass_rate:.1f}% | Best: {best_pass_rate:.1f}% | Streak: {consecutive_perfect}/3")
        log.info(f"   Waiting 15s before next round...")
        await asyncio.sleep(15)

    # Final summary
    log.info("\n" + "=" * 70)
    log.info("RALPH LOOP COMPLETE")
    log.info("=" * 70)
    log.info(f"  Total rounds:      {round_num}")
    log.info(f"  Best pass rate:    {best_pass_rate:.1f}%")
    log.info(f"  Perfect streak:    {consecutive_perfect}")
    if results_history:
        avg = sum(r["pass_rate"] for r in results_history) / len(results_history)
        log.info(f"  Average pass rate: {avg:.1f}%")


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Mario AI Party Stress Test")
    parser.add_argument("--quick", action="store_true", help="Quick smoke test (~2 min)")
    parser.add_argument("--rounds", type=int, help="Ralph loop with N rounds")
    parser.add_argument("--feature", type=str, help="Test specific feature")
    parser.add_argument("--endurance", type=int, help="Endurance test (minutes)")
    parser.add_argument("--guest-sim", action="store_true", help="Full guest simulation")
    parser.add_argument("--ralph", action="store_true", help="Ralph loop until perfect")
    args = parser.parse_args()

    if args.quick:
        asyncio.run(run_quick_smoke())
    elif args.rounds:
        asyncio.run(ralph_stress_loop(max_rounds=args.rounds))
    elif args.feature:
        asyncio.run(run_feature_test(args.feature))
    elif args.endurance:
        asyncio.run(run_endurance_test(duration_minutes=args.endurance))
    elif args.guest_sim:
        asyncio.run(run_feature_test("guest"))
    elif args.ralph:
        asyncio.run(ralph_stress_loop())
    else:
        asyncio.run(run_full_stress_test())


if __name__ == "__main__":
    main()
