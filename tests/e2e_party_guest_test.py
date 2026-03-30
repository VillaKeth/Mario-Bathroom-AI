"""Mario AI — E2E Party Guest Simulation Test

Simulates being an ACTUAL party guest interacting with Mario, testing
every feature end-to-end through the WebSocket interface. Designed to
catch the exact bugs we've fixed and prevent regression:

  - Memory persistence (name, facts, visit counting)
  - Sentiment-aware quick responses (thinking phrases)
  - Idle message deduplication
  - Name parsing from natural speech
  - Fact recall in LLM context
  - Game flow completeness
  - Emotion system transitions
  - Multi-guest rotation

Usage:
    python e2e_party_guest_test.py                  # Full E2E test (~5 min)
    python e2e_party_guest_test.py --quick           # Quick smoke (~90s)
    python e2e_party_guest_test.py --ralph           # Ralph loop until 3 perfect passes
    python e2e_party_guest_test.py --idle 300        # Idle monitoring for 300s
    python e2e_party_guest_test.py --feature memory  # Test specific feature
"""

import asyncio
import json
import logging
import os
import random
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import requests
import websockets

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SERVER_HTTP = os.environ.get("MARIO_HTTP", "http://localhost:8765")
SERVER_WS = os.environ.get("MARIO_WS", "ws://localhost:8765/ws")

LOG_DIR = os.path.join(os.path.dirname(__file__), "e2e_logs")
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            os.path.join(LOG_DIR, f"e2e_{datetime.now():%Y%m%d_%H%M%S}.log"),
            encoding="utf-8",
        ),
    ],
)
log = logging.getLogger("e2e-test")

# Mario character markers for quality checks
MARIO_MARKERS = [
    "mama mia", "wahoo", "let's-a go", "luigi", "princess",
    "mushroom", "bowser", "koopa", "-a ", "mario", "nintendo",
    "castle", "pipe", "star", "coin", "kingdom", "toad",
    "peach", "yoshi", "goomba", "plumber", "pasta", "pizza",
    "mama", "mia", "fireball", "power-up", "warp", "1-up",
]
AI_RED_FLAGS = ["as an ai", "i'm a language model", "openai", "chatgpt", "i cannot"]

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
class E2EReport:
    results: list = field(default_factory=list)
    start_time: float = 0.0
    end_time: float = 0.0
    warnings: list = field(default_factory=list)
    feature_scores: dict = field(default_factory=dict)

    def add(self, result: TestResult):
        self.results.append(result)
        icon = "✅" if result.passed else "❌"
        sev = f" [{result.severity.upper()}]" if result.severity != "normal" else ""
        log.info(f"  {icon}{sev} {result.name} ({result.duration:.1f}s) {result.details}")

    def summary(self) -> bool:
        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        failed = sum(1 for r in self.results if not r.passed)
        critical_fails = sum(
            1 for r in self.results if not r.passed and r.severity == "critical"
        )
        duration = self.end_time - self.start_time

        log.info("\n" + "=" * 70)
        log.info("🍄 E2E PARTY GUEST TEST REPORT")
        log.info("=" * 70)
        log.info(f"  Total checks:    {total}")
        if total:
            log.info(f"  Passed:          {passed} ({passed/total*100:.0f}%)")
        log.info(f"  Failed:          {failed}")
        log.info(f"  Critical fails:  {critical_fails}")
        log.info(f"  Duration:        {duration:.1f}s ({duration/60:.1f} min)")
        log.info(f"  Warnings:        {len(self.warnings)}")

        if self.feature_scores:
            log.info("\n  📊 Feature Scores:")
            for feat, score in sorted(self.feature_scores.items()):
                bar = "█" * int(score / 10) + "░" * (10 - int(score / 10))
                log.info(f"    {feat:<25} {bar} {score:.0f}%")

        if self.warnings:
            log.info("\n  ⚠️  Warnings:")
            for w in self.warnings[:20]:
                log.info(f"    - {w}")

        if failed:
            log.info("\n  ❌ Failed checks:")
            for r in self.results:
                if not r.passed:
                    log.info(f"    - [{r.severity}] {r.name}: {r.details}")

        log.info("=" * 70)
        perfect = critical_fails == 0 and (passed / total * 100 >= 90 if total else False)
        log.info(f"  VERDICT: {'🎉 PASS' if perfect else '💀 FAIL'}")
        log.info("=" * 70)
        return perfect

    def calc_feature_score(self, prefix: str) -> float:
        matching = [r for r in self.results if r.name.startswith(prefix)]
        if not matching:
            return 0.0
        return sum(1 for r in matching if r.passed) / len(matching) * 100


# ---------------------------------------------------------------------------
# WebSocket guest client
# ---------------------------------------------------------------------------

class PartyGuest:
    """Simulates a real party guest interacting with Mario."""

    def __init__(self, name: str = "TestGuest"):
        self.name = name
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.all_messages: list = []
        self.audio_byte_count: int = 0
        self.audio_chunk_count: int = 0
        self.response_times: list = []
        self.emotions_seen: set = set()
        self.idle_messages: list = []
        self.thinking_phrases: list = []

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

    async def enter_bathroom(self):
        await self.ws.send(json.dumps({"type": "set_name", "name": self.name}))
        await self.ws.send(json.dumps({
            "type": "presence_enter",
            "name": self.name,
        }))

    async def leave_bathroom(self):
        await self.ws.send(json.dumps({"type": "presence_exit"}))

    async def say(self, text: str):
        await self.ws.send(json.dumps({
            "type": "text_input",
            "text": text,
            "speaker_name": self.name,
        }))

    async def collect(self, timeout=40, quiet_gap=8.0):
        """Collect responses until quiet period."""
        responses = []
        audio_chunks = 0
        audio_bytes = 0
        t0 = time.time()
        last_msg = t0

        while time.time() - t0 < timeout:
            try:
                msg = await asyncio.wait_for(self.ws.recv(), timeout=3.0)
                last_msg = time.time()

                if isinstance(msg, bytes):
                    audio_chunks += 1
                    audio_bytes += len(msg)
                    self.audio_chunk_count += 1
                    self.audio_byte_count += len(msg)
                else:
                    data = json.loads(msg)
                    responses.append(data)
                    self.all_messages.append(data)

                    msg_type = data.get("type")
                    if msg_type == "mario_response":
                        if data.get("emotion"):
                            self.emotions_seen.add(data["emotion"])
                        if data.get("response_time"):
                            self.response_times.append(data["response_time"])
                    elif msg_type == "mario_thinking":
                        self.thinking_phrases.append(data.get("text", ""))
                    elif msg_type == "idle_message":
                        self.idle_messages.append(data.get("text", ""))

            except asyncio.TimeoutError:
                quiet = time.time() - last_msg
                has_response = any(
                    r.get("type") == "mario_response" for r in responses
                )
                if quiet > quiet_gap and has_response:
                    break
                if quiet > quiet_gap * 2.5:
                    break
            except Exception:
                break

        return {
            "responses": responses,
            "mario_texts": [
                r.get("text", "")
                for r in responses
                if r.get("type") == "mario_response" and r.get("text", "").strip()
            ],
            "thinking_texts": [
                r.get("text", "")
                for r in responses
                if r.get("type") == "mario_thinking"
            ],
            "audio_chunks": audio_chunks,
            "audio_bytes": audio_bytes,
            "emotions": [
                r.get("emotion")
                for r in responses
                if r.get("type") == "mario_response" and r.get("emotion")
            ],
            "duration": time.time() - t0,
        }

    async def chat(self, text: str, timeout=40) -> dict:
        """Say something and collect Mario's response."""
        await self.say(text)
        return await self.collect(timeout=timeout)

    async def listen_idle(self, duration=60):
        """Passively listen for idle messages."""
        idle_msgs = []
        t0 = time.time()
        while time.time() - t0 < duration:
            try:
                msg = await asyncio.wait_for(self.ws.recv(), timeout=5.0)
                if isinstance(msg, bytes):
                    continue
                data = json.loads(msg)
                if data.get("type") in ("idle_message", "mario_response"):
                    text = data.get("text", "")
                    if text.strip():
                        idle_msgs.append(text.strip())
                        log.info(f"    🔇 Idle [{len(idle_msgs)}]: {text[:60]}...")
            except asyncio.TimeoutError:
                continue
            except Exception:
                break
        return idle_msgs


# ---------------------------------------------------------------------------
# Quality checks
# ---------------------------------------------------------------------------

def check_in_character(text: str) -> tuple:
    """Returns (score 0-100, issues list)."""
    lower = text.lower()
    issues = []

    for flag in AI_RED_FLAGS:
        if flag in lower:
            issues.append(f"AI red flag: '{flag}'")

    marker_hits = sum(1 for m in MARIO_MARKERS if m in lower)
    has_personality = marker_hits >= 1
    if not has_personality:
        issues.append("No Mario personality markers found")

    score = 100
    score -= len(issues) * 30
    score += min(marker_hits * 10, 30)
    return max(0, min(100, score)), issues


def check_sentiment_match(text: str, expected_mood: str) -> bool:
    """Check if response text matches expected mood."""
    lower = text.lower()
    if expected_mood == "sad":
        sad_words = ["sorry", "hang in there", "cheer", "tough", "here for you",
                     "better", "okay", "alright", "don't worry", "feel"]
        return any(w in lower for w in sad_words)
    if expected_mood == "angry":
        calm_words = ["whoa", "calm", "easy", "take it easy", "relax",
                      "deep breath", "hey", "okay"]
        return any(w in lower for w in calm_words)
    return True


# ---------------------------------------------------------------------------
# Test suites
# ---------------------------------------------------------------------------

async def test_server_health(report: E2EReport):
    """Check server, Ollama, and all endpoints are alive."""
    log.info("\n🏥 SUITE: Server Health")

    for endpoint, label in [
        ("/health", "health"),
        ("/stats", "stats"),
        ("/leaderboard", "leaderboard"),
    ]:
        t0 = time.time()
        try:
            r = requests.get(f"{SERVER_HTTP}{endpoint}", timeout=10)
            report.add(TestResult(
                f"health_{label}", r.status_code == 200,
                time.time() - t0, f"status={r.status_code}",
                "critical" if label == "health" else "normal",
            ))
        except Exception as e:
            report.add(TestResult(
                f"health_{label}", False, time.time() - t0, str(e), "critical",
            ))

    # TTS cache
    try:
        h = requests.get(f"{SERVER_HTTP}/health", timeout=10).json()
        cache = h.get("tts_cache_size", 0)
        report.add(TestResult(
            "health_tts_cache", cache > 100, 0,
            f"cache_size={cache}", "critical",
        ))
    except Exception as e:
        report.add(TestResult("health_tts_cache", False, 0, str(e), "critical"))


async def test_greeting_flow(report: E2EReport):
    """Full bathroom enter → greeting → conversation → exit flow."""
    log.info("\n🚪 SUITE: Greeting Flow")

    guest = PartyGuest("GreetingTester")
    try:
        await guest.connect()
        report.add(TestResult("greet_ws_connect", True, 0, "connected"))
    except Exception as e:
        report.add(TestResult("greet_ws_connect", False, 0, str(e), "critical"))
        return

    try:
        t0 = time.time()
        await guest.enter_bathroom()
        result = await guest.collect(timeout=60, quiet_gap=12.0)

        has_greeting = len(result["mario_texts"]) > 0
        greeting_text = " ".join(result["mario_texts"])
        has_audio = result["audio_chunks"] > 0

        report.add(TestResult(
            "greet_response", has_greeting, time.time() - t0,
            f"'{greeting_text[:60]}...' audio={result['audio_chunks']}",
            "critical",
        ))
        report.add(TestResult(
            "greet_has_audio", has_audio, 0,
            f"{result['audio_chunks']} chunks, {result['audio_bytes']:,}B",
        ))

        # Character quality
        if has_greeting:
            score, issues = check_in_character(greeting_text)
            report.add(TestResult(
                "greet_in_character", score >= 50, 0,
                f"score={score}, issues={issues}",
            ))

    except Exception as e:
        report.add(TestResult("greet_response", False, 0, str(e), "critical"))

    # Have a brief chat
    await asyncio.sleep(2)
    try:
        result = await guest.chat("How's the party going?")
        has_text = len(result["mario_texts"]) > 0
        report.add(TestResult(
            "greet_chat_works", has_text, result["duration"],
            f"'{' '.join(result['mario_texts'])[:60]}...'",
        ))
    except Exception as e:
        report.add(TestResult("greet_chat_works", False, 0, str(e)))

    # Exit
    try:
        t0 = time.time()
        await guest.leave_bathroom()
        result = await guest.collect(timeout=30, quiet_gap=6.0)
        farewell_texts = result["mario_texts"]
        report.add(TestResult(
            "greet_farewell", len(farewell_texts) > 0, time.time() - t0,
            f"'{' '.join(farewell_texts)[:60]}...'",
        ))
    except Exception as e:
        report.add(TestResult("greet_farewell", False, 0, str(e)))

    await guest.disconnect()


async def test_memory_persistence(report: E2EReport):
    """REGRESSION: Tests the browser memory bug fix.
    
    Verifies: set_name handler, virtual speaker_id, fact extraction,
    visit counting, and fact recall in LLM context.
    """
    log.info("\n🧠 SUITE: Memory Persistence")

    guest_name = f"MemoryTest{random.randint(100,999)}"
    guest = PartyGuest(guest_name)

    try:
        await guest.connect()
        await guest.enter_bathroom()
        result = await guest.collect(timeout=60, quiet_gap=12.0)
        report.add(TestResult(
            "mem_first_visit_greeting", len(result["mario_texts"]) > 0, 0,
            f"Visit 1 greeting received",
        ))
    except Exception as e:
        report.add(TestResult("mem_first_visit_greeting", False, 0, str(e), "critical"))
        return

    await asyncio.sleep(2)

    # Share a fact
    unique_fact = f"my favorite food is {random.choice(['sushi', 'tacos', 'ramen', 'burgers', 'curry'])}"
    try:
        result = await guest.chat(f"Hey Mario, {unique_fact}!")
        report.add(TestResult(
            "mem_fact_shared", len(result["mario_texts"]) > 0, result["duration"],
            f"Shared: '{unique_fact}'",
        ))
    except Exception as e:
        report.add(TestResult("mem_fact_shared", False, 0, str(e)))

    await asyncio.sleep(2)

    # Leave
    try:
        await guest.leave_bathroom()
        await guest.collect(timeout=20, quiet_gap=5.0)
    except Exception:
        pass

    await guest.disconnect()
    await asyncio.sleep(3)

    # Visit 2 — reconnect and check memory
    guest2 = PartyGuest(guest_name)
    try:
        await guest2.connect()
        await guest2.enter_bathroom()
        result = await guest2.collect(timeout=60, quiet_gap=12.0)

        greeting = " ".join(result["mario_texts"]).lower()
        name_recalled = guest_name.lower() in greeting
        visit_ref = any(w in greeting for w in ["back", "again", "return", "visit", "miss", "remember"])

        # Name recall can happen in greeting OR follow-up, so mark as warning not critical
        report.add(TestResult(
            "mem_name_in_greeting", name_recalled, 0,
            f"Name '{guest_name}' in greeting: {name_recalled}",
            "warning",
        ))
        report.add(TestResult(
            "mem_visit_recognized", visit_ref, 0,
            f"Return visit hint: '{greeting[:80]}...'",
            "warning",
        ))
    except Exception as e:
        report.add(TestResult("mem_name_recalled", False, 0, str(e), "critical"))

    # Ask about the fact
    await asyncio.sleep(2)
    try:
        result = await guest2.chat("What do you remember about me?")
        recall_text = " ".join(result["mario_texts"]).lower()
        food_word = unique_fact.split("is ")[-1] if "is " in unique_fact else unique_fact
        fact_recalled = food_word.lower() in recall_text
        # Also check if name is in the recall response (belt-and-suspenders)
        name_in_recall = guest_name.lower() in recall_text

        report.add(TestResult(
            "mem_fact_recalled", fact_recalled, result["duration"],
            f"Looking for '{food_word}' in: '{recall_text[:80]}...'",
            "critical",
        ))
        report.add(TestResult(
            "mem_name_in_recall", name_in_recall, 0,
            f"Name '{guest_name}' in recall response: {name_in_recall}",
            "critical",
        ))
    except Exception as e:
        report.add(TestResult("mem_fact_recalled", False, 0, str(e)))

    await guest2.disconnect()


async def test_sentiment_responses(report: E2EReport):
    """REGRESSION: Tests sentiment-aware thinking phrases.
    
    Verifies: sad messages don't get 'Fantastic!' thinking phrase,
    mood-appropriate quick responses.
    """
    log.info("\n😢 SUITE: Sentiment-Aware Responses")

    guest = PartyGuest("SentimentTester")
    try:
        await guest.connect()
        await guest.enter_bathroom()
        await guest.collect(timeout=60, quiet_gap=12.0)
    except Exception as e:
        report.add(TestResult("sent_connect", False, 0, str(e), "critical"))
        return

    # Wait longer to let greeting state fully clear
    await asyncio.sleep(5)

    # SAD message — should NOT get positive thinking phrase
    try:
        result = await guest.chat(
            "Mario, I'm feeling really sad today. My dog passed away."
        )
        thinking = result["thinking_texts"]
        mario_text = " ".join(result["mario_texts"]).lower()

        positive_thinking = ["fantastic", "wahoo", "amazing", "oh boy", "yahoo"]
        got_positive = any(
            p in t.lower() for t in thinking for p in positive_thinking
        )
        report.add(TestResult(
            "sent_sad_no_positive_thinking", not got_positive, 0,
            f"Thinking phrases: {thinking}",
            "critical",
        ))

        is_empathetic = check_sentiment_match(mario_text, "sad")
        report.add(TestResult(
            "sent_sad_empathetic_response", is_empathetic, result["duration"],
            f"Response: '{mario_text[:80]}...'",
            "warning",
        ))
    except Exception as e:
        report.add(TestResult("sent_sad_no_positive_thinking", False, 0, str(e), "critical"))

    await asyncio.sleep(2)

    # HAPPY message — should work normally
    try:
        result = await guest.chat(
            "I just got promoted at work! This is the best day ever!"
        )
        has_response = len(result["mario_texts"]) > 0
        report.add(TestResult(
            "sent_happy_response", has_response, result["duration"],
            f"'{' '.join(result['mario_texts'])[:60]}...'",
        ))
    except Exception as e:
        report.add(TestResult("sent_happy_response", False, 0, str(e)))

    await asyncio.sleep(2)

    # ANGRY message
    try:
        result = await guest.chat(
            "I'm so frustrated right now! Everything is going wrong!"
        )
        thinking = result["thinking_texts"]
        got_positive = any(
            p in t.lower()
            for t in thinking
            for p in ["fantastic", "wahoo", "amazing"]
        )
        report.add(TestResult(
            "sent_angry_no_positive_thinking", not got_positive, 0,
            f"Thinking: {thinking}",
        ))
    except Exception as e:
        report.add(TestResult("sent_angry_no_positive_thinking", False, 0, str(e)))

    await guest.disconnect()


async def test_name_parsing(report: E2EReport):
    """REGRESSION: Tests name extraction from natural speech.
    
    Verifies: 'I'm Jake by the way' → 'Jake' (not 'Jake by')
    """
    log.info("\n📛 SUITE: Name Parsing")

    test_cases = [
        ("I'm Jake by the way", "jake"),
        ("My name is Sarah!", "sarah"),
        ("Call me Mike", "mike"),
        ("Hey, it's Alex here", "alex"),
    ]

    for phrase, expected_name in test_cases:
        guest = PartyGuest(f"Anon{random.randint(100,999)}")
        try:
            await guest.connect()
            await guest.enter_bathroom()
            await guest.collect(timeout=60, quiet_gap=12.0)
            await asyncio.sleep(1)

            result = await guest.chat(phrase)
            full_text = " ".join(result["mario_texts"]).lower()

            # Check the name was extracted (Mario should address them)
            name_used = expected_name in full_text
            # Also check the bad parse didn't happen
            if phrase == "I'm Jake by the way":
                bad_parse = "jake by" in full_text and "jake by the" not in full_text
                report.add(TestResult(
                    "name_no_bad_parse", not bad_parse, 0,
                    f"No 'Jake by' artifact: {not bad_parse}",
                    "critical",
                ))

            report.add(TestResult(
                f"name_extract_{expected_name}", name_used, result["duration"],
                f"'{phrase}' → found '{expected_name}' in response: {name_used}",
                "warning",  # LLM may not echo name back — that's normal
            ))
        except Exception as e:
            report.add(TestResult(f"name_extract_{expected_name}", False, 0, str(e)))
        finally:
            await guest.disconnect()
            await asyncio.sleep(2)


async def test_idle_dedup(report: E2EReport, duration=180):
    """REGRESSION: Tests idle message deduplication.
    
    Verifies: no repeated messages within observation window.
    """
    log.info(f"\n🔇 SUITE: Idle Dedup ({duration}s observation)")

    guest = PartyGuest("IdleWatcher")
    try:
        await guest.connect()
        # Enter bathroom so idle loop generates messages during pauses
        await guest.enter_bathroom()
        await guest.collect(timeout=30, quiet_gap=8.0)  # Collect greeting
        await asyncio.sleep(5)  # Let greeting processing settle

        log.info("  Listening for idle messages...")
        messages = await guest.listen_idle(duration=duration)

        total = len(messages)
        unique = len(set(messages))
        duplicates = total - unique

        dup_rate = duplicates / total * 100 if total > 0 else 0
        report.add(TestResult(
            "idle_message_count", total >= 1, 0,
            f"{total} messages in {duration}s",
            "warning",
        ))
        report.add(TestResult(
            "idle_no_duplicates", dup_rate < 15, 0,
            f"{unique}/{total} unique ({dup_rate:.0f}% dup rate)",
            "critical" if dup_rate > 30 else "warning" if dup_rate > 15 else "normal",
        ))

        # Check message variety (categories)
        if messages:
            counter = Counter(messages)
            most_common = counter.most_common(3)
            report.add(TestResult(
                "idle_variety", most_common[0][1] <= 2 if most_common else True, 0,
                f"Most repeated: '{most_common[0][0][:40]}...' x{most_common[0][1]}"
                if most_common else "No messages",
            ))

    except Exception as e:
        report.add(TestResult("idle_dedup", False, 0, str(e)))
    finally:
        await guest.disconnect()


async def test_games(report: E2EReport):
    """Test game initiation and basic flow."""
    log.info("\n🎮 SUITE: Games")

    games_to_test = [
        ("Let's play trivia!", "trivia"),
        ("Rock paper scissors!", "rps"),
        ("Truth or dare!", "truth_dare"),
        ("Tell me a joke!", "joke"),
    ]

    for prompt, label in games_to_test:
        guest = PartyGuest(f"Gamer{random.randint(100,999)}")
        try:
            await guest.connect()
            await guest.enter_bathroom()
            await guest.collect(timeout=60, quiet_gap=12.0)
            await asyncio.sleep(2)

            result = await guest.chat(prompt, timeout=40)
            texts = " ".join(result["mario_texts"])
            has_response = len(texts.strip()) > 10
            has_audio = result["audio_chunks"] > 0

            report.add(TestResult(
                f"game_{label}_response", has_response, result["duration"],
                f"'{texts[:60]}...' audio={result['audio_chunks']}",
            ))
            report.add(TestResult(
                f"game_{label}_audio", has_audio, 0,
                f"{result['audio_chunks']} chunks",
            ))

        except Exception as e:
            report.add(TestResult(f"game_{label}", False, 0, str(e)))
        finally:
            await guest.disconnect()
            await asyncio.sleep(2)


async def test_emotion_system(report: E2EReport):
    """Test emotion transitions and appropriateness."""
    log.info("\n😊 SUITE: Emotion System")

    guest = PartyGuest("EmotionTester")
    try:
        await guest.connect()
        await guest.enter_bathroom()
        await guest.collect(timeout=60, quiet_gap=12.0)
        await asyncio.sleep(2)

        scenarios = [
            ("This is the best party ever! I love it!", "positive"),
            ("I'm really nervous about my job interview tomorrow", "negative"),
            ("What time is it?", "neutral"),
        ]

        all_emotions = []
        for msg, expected_valence in scenarios:
            result = await guest.chat(msg)
            emotions = result["emotions"]
            all_emotions.extend(emotions)

            has_emotion = len(emotions) > 0
            report.add(TestResult(
                f"emo_{expected_valence}_tagged", has_emotion, result["duration"],
                f"Emotions: {emotions}",
            ))
            await asyncio.sleep(2)

        # Check emotion diversity
        unique_emotions = set(all_emotions)
        report.add(TestResult(
            "emo_diversity", len(unique_emotions) >= 2, 0,
            f"Unique emotions: {unique_emotions}",
        ))

    except Exception as e:
        report.add(TestResult("emo_system", False, 0, str(e)))
    finally:
        await guest.disconnect()


async def test_multi_guest(report: E2EReport):
    """Test multiple guests entering/leaving in sequence."""
    log.info("\n👥 SUITE: Multi-Guest Rotation")

    guest_names = ["Luigi", "Peach", "Toad"]

    for name in guest_names:
        guest = PartyGuest(name)
        try:
            await guest.connect()
            await guest.enter_bathroom()
            result = await guest.collect(timeout=60, quiet_gap=12.0)

            has_greeting = len(result["mario_texts"]) > 0
            report.add(TestResult(
                f"multi_{name}_greeting", has_greeting, result["duration"],
                f"'{' '.join(result['mario_texts'])[:50]}...'",
            ))

            await asyncio.sleep(1)
            await guest.leave_bathroom()
            await guest.collect(timeout=15, quiet_gap=5.0)
            await guest.disconnect()
            await asyncio.sleep(3)

        except Exception as e:
            report.add(TestResult(f"multi_{name}", False, 0, str(e)))
            try:
                await guest.disconnect()
            except Exception:
                pass

    # Check gossip — later guest might reference earlier one
    gossip_guest = PartyGuest("GossipChecker")
    try:
        await gossip_guest.connect()
        await gossip_guest.enter_bathroom()
        await gossip_guest.collect(timeout=60, quiet_gap=12.0)
        await asyncio.sleep(2)

        result = await gossip_guest.chat("Has anyone interesting been here tonight?")
        text = " ".join(result["mario_texts"]).lower()
        mentions_guest = any(n.lower() in text for n in guest_names)
        report.add(TestResult(
            "multi_gossip_works", mentions_guest, result["duration"],
            f"References prior guests: {mentions_guest}",
            "warning",  # LLM-dependent — gossip is best-effort
        ))
    except Exception as e:
        report.add(TestResult("multi_gossip", False, 0, str(e)))
    finally:
        await gossip_guest.disconnect()


async def test_tts_quality(report: E2EReport):
    """Test TTS endpoint directly."""
    log.info("\n🔊 SUITE: TTS Quality")

    phrases = [
        ("It's-a me, Mario!", "cached"),
        ("Wahoo!", "cached"),
        (f"Test phrase {random.randint(1000,9999)} for quality check", "live"),
    ]

    for phrase, cache_type in phrases:
        t0 = time.time()
        try:
            params = {"text": phrase}
            if cache_type == "live":
                params["nocache"] = 1
            r = requests.get(f"{SERVER_HTTP}/tts", params=params, timeout=30)
            dur = time.time() - t0
            size = len(r.content)
            is_wav = r.content[:4] == b"RIFF" if size > 44 else False

            report.add(TestResult(
                f"tts_{cache_type}_{phrase[:20]}", size > 100 and is_wav, dur,
                f"{dur:.1f}s, {size:,}B, wav={is_wav}",
            ))
        except Exception as e:
            report.add(TestResult(f"tts_{cache_type}", False, time.time() - t0, str(e)))


async def test_response_quality(report: E2EReport):
    """Test overall response quality across various topics."""
    log.info("\n⭐ SUITE: Response Quality")

    guest = PartyGuest("QualityTester")
    try:
        await guest.connect()
        await guest.enter_bathroom()
        await guest.collect(timeout=60, quiet_gap=12.0)
        await asyncio.sleep(2)

        conversations = [
            "What's your favorite Mario Kart track?",
            "Tell me about Princess Peach",
            "What do you think about Bowser?",
            "Have you ever been to the Mushroom Kingdom?",
            "What's the weirdest thing you've seen in this bathroom?",
        ]

        quality_scores = []
        for msg in conversations:
            result = await guest.chat(msg, timeout=40)
            text = " ".join(result["mario_texts"])

            if text.strip():
                score, issues = check_in_character(text)
                quality_scores.append(score)
                has_audio = result["audio_chunks"] > 0

                report.add(TestResult(
                    f"quality_{msg[:25]}", score >= 40 and has_audio,
                    result["duration"],
                    f"score={score}, audio={result['audio_chunks']}, len={len(text)}",
                ))
            else:
                quality_scores.append(0)
                report.add(TestResult(
                    f"quality_{msg[:25]}", False, result["duration"],
                    "Empty response", "warning",
                ))
            await asyncio.sleep(2)

        avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0
        report.add(TestResult(
            "quality_avg_score", avg_quality >= 50, 0,
            f"Average character score: {avg_quality:.0f}/100",
        ))

    except Exception as e:
        report.add(TestResult("quality_test", False, 0, str(e)))
    finally:
        await guest.disconnect()


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

async def run_full_e2e(idle_duration=120):
    """Run the complete E2E test suite."""
    report = E2EReport()
    report.start_time = time.time()

    log.info("🍄" * 35)
    log.info("  MARIO AI — E2E PARTY GUEST TEST")
    log.info("🍄" * 35)
    log.info(f"  Server: {SERVER_HTTP}")
    log.info(f"  Time:   {datetime.now():%Y-%m-%d %H:%M:%S}")

    suites = [
        ("server_health", test_server_health),
        ("tts", test_tts_quality),
        ("greeting", test_greeting_flow),
        ("memory", test_memory_persistence),
        ("sentiment", test_sentiment_responses),
        ("name_parsing", test_name_parsing),
        ("games", test_games),
        ("emotions", test_emotion_system),
        ("multi_guest", test_multi_guest),
        ("quality", test_response_quality),
        ("idle_dedup", lambda r: test_idle_dedup(r, duration=idle_duration)),
    ]

    for suite_name, suite_fn in suites:
        try:
            await suite_fn(report)
        except Exception as e:
            log.error(f"Suite {suite_name} crashed: {e}")
            report.add(TestResult(
                f"{suite_name}_CRASH", False, 0, str(e), "critical"
            ))

    # Compute feature scores using correct prefixes
    prefix_map = {
        "server_health": "health_",
        "tts": "tts_",
        "greeting": "greet_",
        "memory": "mem_",
        "sentiment": "sent_",
        "name_parsing": "name_",
        "games": "game_",
        "emotions": "emo_",
        "multi_guest": "multi_",
        "quality": "quality_",
        "idle_dedup": "idle_",
    }
    for suite_name, _ in suites:
        prefix = prefix_map.get(suite_name, suite_name + "_")
        report.feature_scores[suite_name] = report.calc_feature_score(prefix)

    report.end_time = time.time()
    return report


async def run_quick_smoke():
    """Quick smoke test — ~90 seconds."""
    report = E2EReport()
    report.start_time = time.time()

    log.info("🍄 QUICK SMOKE TEST")

    await test_server_health(report)
    await test_greeting_flow(report)
    await test_tts_quality(report)

    report.end_time = time.time()
    return report


async def run_ralph_loop(max_rounds=100):
    """Run E2E test in ralph loop until 3 consecutive perfect passes."""
    consecutive_passes = 0
    round_num = 0

    while round_num < max_rounds and consecutive_passes < 3:
        round_num += 1
        log.info(f"\n{'🔄' * 30}")
        log.info(f"  RALPH LOOP — Round {round_num} (streak: {consecutive_passes}/3)")
        log.info(f"{'🔄' * 30}")

        report = await run_full_e2e(idle_duration=90)
        passed = report.summary()

        if passed:
            consecutive_passes += 1
            log.info(f"  ✅ Round {round_num} PASSED (streak: {consecutive_passes}/3)")
        else:
            consecutive_passes = 0
            log.info(f"  ❌ Round {round_num} FAILED — streak reset")

        if consecutive_passes < 3:
            log.info("  Cooling down 30s before next round...")
            await asyncio.sleep(30)

    if consecutive_passes >= 3:
        log.info(f"\n🎉 RALPH LOOP COMPLETE — 3 consecutive passes after {round_num} rounds!")
    else:
        log.info(f"\n💀 RALPH LOOP EXHAUSTED — {max_rounds} rounds without 3 consecutive passes")

    return consecutive_passes >= 3


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Mario AI E2E Party Guest Test")
    parser.add_argument("--quick", action="store_true", help="Quick smoke test")
    parser.add_argument("--ralph", action="store_true", help="Ralph loop until 3 perfect")
    parser.add_argument("--idle", type=int, default=120, help="Idle monitoring duration (s)")
    parser.add_argument("--feature", type=str, help="Test specific feature")
    parser.add_argument("--rounds", type=int, default=100, help="Max ralph rounds")
    args = parser.parse_args()

    if args.ralph:
        success = asyncio.run(run_ralph_loop(max_rounds=args.rounds))
        sys.exit(0 if success else 1)
    elif args.quick:
        report = asyncio.run(run_quick_smoke())
    elif args.feature:
        report = E2EReport()
        report.start_time = time.time()
        feature_map = {
            "health": test_server_health,
            "greeting": test_greeting_flow,
            "memory": test_memory_persistence,
            "sentiment": test_sentiment_responses,
            "name": test_name_parsing,
            "idle": lambda r: test_idle_dedup(r, duration=args.idle),
            "games": test_games,
            "emotions": test_emotion_system,
            "multi": test_multi_guest,
            "quality": test_response_quality,
            "tts": test_tts_quality,
        }
        fn = feature_map.get(args.feature)
        if fn:
            asyncio.run(fn(report))
        else:
            print(f"Unknown feature: {args.feature}")
            print(f"Available: {', '.join(feature_map.keys())}")
            sys.exit(1)
        report.end_time = time.time()
    else:
        report = asyncio.run(run_full_e2e(idle_duration=args.idle))

    passed = report.summary()
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
