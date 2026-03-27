#!/usr/bin/env python3
"""
Mario AI Party Bot — Autonomous Endurance Stress Test
Self-learning 6-hour party simulation with health monitoring and trend analysis.

Usage:
    python party_endurance_test.py                  # Default 6-hour run
    python party_endurance_test.py --hours 1        # 1-hour quick test
    python party_endurance_test.py --ralph           # Ralph loop: run until 3 consecutive perfect cycles
    python party_endurance_test.py --guests 8        # Simulate 8 unique guests per wave
    python party_endurance_test.py --verbose         # Show all messages
    python party_endurance_test.py --results out.json
    python party_endurance_test.py --load prev.json  # Load previous results for learning
"""

import argparse
import asyncio
import json
import logging
import math
import os
import random
import statistics
import sys
import time
import traceback
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests
import websockets

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SERVER_HTTP = "http://localhost:8765"
SERVER_WS = "ws://localhost:8765/ws"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(SCRIPT_DIR, "stress_test_logs")
os.makedirs(LOG_DIR, exist_ok=True)

# Thresholds for alerts
ALERT_RESPONSE_TIME_THRESHOLD = 5.0      # seconds
ALERT_CACHE_HIT_RATE_MIN = 80.0          # percent
ALERT_CONVERSATION_LENGTH_MAX = 50       # messages before concern
ALERT_HEALTH_FAIL_STREAK_MAX = 3         # consecutive failures

# Ralph mode thresholds
RALPH_PASS_RATE_MIN = 95.0               # percent
RALPH_AVG_RESPONSE_TIME_MAX = 30.0       # seconds (test-measured includes audio drain overhead)
RALPH_PERFECT_CYCLES_NEEDED = 3
RALPH_CYCLE_MINUTES = 30

# Timing
COOLDOWN_BETWEEN_TEXTS = 2.5             # seconds (server enforces 2s)
GAP_BETWEEN_GUESTS = 6.0                 # seconds for server cleanup
HEALTH_CHECK_INTERVAL = 30               # seconds

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
_log_file = os.path.join(LOG_DIR, f"endurance_{_ts}.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(_log_file, encoding="utf-8"),
    ],
)
log = logging.getLogger("endurance")

# ---------------------------------------------------------------------------
# Guest Profiles
# ---------------------------------------------------------------------------

GUEST_PROFILES = [
    {"name": "Luigi",      "personality": "casual",       "chattiness": 5, "game_prob": 0.3},
    {"name": "Peach",      "personality": "polite",       "chattiness": 7, "game_prob": 0.2},
    {"name": "Toad",       "personality": "energetic",    "chattiness": 8, "game_prob": 0.5},
    {"name": "Bowser",     "personality": "aggressive",   "chattiness": 4, "game_prob": 0.4},
    {"name": "Yoshi",      "personality": "shy",          "chattiness": 3, "game_prob": 0.1},
    {"name": "Wario",      "personality": "drunk",        "chattiness": 9, "game_prob": 0.6},
    {"name": "Waluigi",    "personality": "chaotic",      "chattiness": 10,"game_prob": 0.7},
    {"name": "DaisyFan42", "personality": "trivia-lover", "chattiness": 6, "game_prob": 0.8},
    {"name": "Rosalina",   "personality": "mysterious",   "chattiness": 4, "game_prob": 0.2},
    {"name": "DonkeyKong", "personality": "loud",         "chattiness": 7, "game_prob": 0.5},
    {"name": "Birdo",      "personality": "flirty",       "chattiness": 6, "game_prob": 0.3},
    {"name": "KoopaTroopa","personality": "nervous",      "chattiness": 3, "game_prob": 0.1},
    {"name": "ShyGuy",     "personality": "shy",          "chattiness": 2, "game_prob": 0.1},
    {"name": "BooGuest",   "personality": "spooky",       "chattiness": 5, "game_prob": 0.4},
    {"name": "ToadBro",    "personality": "game-player",  "chattiness": 6, "game_prob": 0.9},
    {"name": "PartyAnimal", "personality": "drunk",       "chattiness": 10,"game_prob": 0.5},
    {"name": "ProfGoom",   "personality": "intellectual",  "chattiness": 7, "game_prob": 0.6},
    {"name": "ChainChomp", "personality": "aggressive",   "chattiness": 4, "game_prob": 0.3},
    {"name": "LakituCam",  "personality": "casual",       "chattiness": 5, "game_prob": 0.2},
    {"name": "KingBoo",    "personality": "chaotic",      "chattiness": 8, "game_prob": 0.6},
    {"name": "HammerBro",  "personality": "loud",         "chattiness": 6, "game_prob": 0.4},
    {"name": "DiddyKong",  "personality": "energetic",    "chattiness": 7, "game_prob": 0.5},
    {"name": "PiantaJoe",  "personality": "casual",       "chattiness": 5, "game_prob": 0.2},
    {"name": "NokiSurf",   "personality": "polite",       "chattiness": 4, "game_prob": 0.3},
]

# ---------------------------------------------------------------------------
# Chat Message Pools (50+ messages)
# ---------------------------------------------------------------------------

CHAT_MESSAGES_GENERAL = [
    "Hey Mario! What's going on?",
    "Tell me about Princess Peach",
    "Do you know any jokes?",
    "What's your favorite food?",
    "Sing me a song!",
    "What do you think about Bowser?",
    "This bathroom is really something!",
    "How long have you been guarding this bathroom?",
    "Is Luigi here tonight?",
    "What's the craziest thing that happened today?",
    "Do you ever get lonely in here?",
    "Tell me a secret about the Mushroom Kingdom",
    "What's your opinion on pineapple pizza?",
    "Have you seen Toad around?",
    "What kind of music do you like?",
    "Do you miss the old days of stomping goombas?",
    "What's the weirdest thing a guest has said tonight?",
    "Are you having fun at the party?",
    "What's behind that pipe over there?",
    "Do you believe in ghosts?",
    "Tell me about your adventures!",
    "What's your favorite power-up?",
    "How do you stay so cheerful?",
    "Is it true you used to be a plumber?",
    "What does a fire flower taste like?",
    "Who's the best dancer at this party?",
]

CHAT_MESSAGES_TRIVIA = [
    "What year did Super Mario Bros come out?",
    "How many worlds are in the original game?",
    "What's Mario's full name?",
    "Who is Mario's nemesis?",
    "What color is Yoshi?",
    "How many coins for a 1-UP?",
    "What's the name of Mario's dinosaur friend?",
]

CHAT_MESSAGES_DRUNK = [
    "Marioooo you're my best friendddd",
    "I can't feel my legs hahaha",
    "This party is AMAZINGGGG",
    "Hey hey hey... you're a mushroom right?",
    "I love you man... no seriously",
    "Wait which bathroom am I in?",
    "One more drink and I'll fight Bowser myself!",
    "You know what... you're alright, Mario",
]

CHAT_MESSAGES_EMOTIONAL = [
    "I'm having a really rough day, Mario",
    "You always cheer me up!",
    "I feel like nobody listens to me",
    "This party is the best thing that happened to me this week",
    "I wish every night was this fun",
]

CHAT_MESSAGES_CHALLENGING = [
    "You're not the real Mario, are you?",
    "I bet Luigi is better than you",
    "Bowser told me you're scared of him",
    "This party is kind of boring honestly",
    "Can you say something actually funny?",
    "Are you just a robot?",
]

CHAT_MESSAGES_LORE = [
    "What happened at the last castle?",
    "Tell me about the Star Festival",
    "Is the Mushroom Kingdom real?",
    "How did you and Peach meet?",
    "What's it like in the Darklands?",
]

ALL_CHAT_MESSAGES = (
    CHAT_MESSAGES_GENERAL
    + CHAT_MESSAGES_TRIVIA
    + CHAT_MESSAGES_DRUNK
    + CHAT_MESSAGES_EMOTIONAL
    + CHAT_MESSAGES_CHALLENGING
    + CHAT_MESSAGES_LORE
)

PERSONALITY_MESSAGE_MAP = {
    "casual":       CHAT_MESSAGES_GENERAL,
    "polite":       CHAT_MESSAGES_GENERAL + CHAT_MESSAGES_EMOTIONAL,
    "energetic":    CHAT_MESSAGES_GENERAL + CHAT_MESSAGES_CHALLENGING,
    "aggressive":   CHAT_MESSAGES_CHALLENGING + CHAT_MESSAGES_GENERAL[:5],
    "shy":          CHAT_MESSAGES_GENERAL[:8],
    "drunk":        CHAT_MESSAGES_DRUNK + CHAT_MESSAGES_GENERAL[:5],
    "chaotic":      ALL_CHAT_MESSAGES,
    "trivia-lover": CHAT_MESSAGES_TRIVIA + CHAT_MESSAGES_LORE,
    "mysterious":   CHAT_MESSAGES_LORE + CHAT_MESSAGES_EMOTIONAL,
    "loud":         CHAT_MESSAGES_GENERAL + CHAT_MESSAGES_CHALLENGING,
    "flirty":       CHAT_MESSAGES_EMOTIONAL + CHAT_MESSAGES_GENERAL[:5],
    "nervous":      CHAT_MESSAGES_GENERAL[:6] + CHAT_MESSAGES_EMOTIONAL,
    "spooky":       CHAT_MESSAGES_LORE + CHAT_MESSAGES_CHALLENGING,
    "game-player":  CHAT_MESSAGES_GENERAL[:3],
    "intellectual": CHAT_MESSAGES_TRIVIA + CHAT_MESSAGES_LORE + CHAT_MESSAGES_GENERAL[:5],
}

GAME_COMMANDS = [
    "play 20 questions",
    "play truth or dare",
    "play riddles",
    "play simon says",
    "play rock paper scissors",
]

GAME_KEYWORDS = ["QUESTIONS", "DARE", "RIDDLE", "SIMON SAYS", "ROCK PAPER SCISSORS"]

GAME_FOLLOWUP = {
    "play 20 questions": ["Is it alive?", "Is it bigger than a breadbox?", "Is it an animal?", "give up"],
    "play truth or dare": ["truth", "dare", "truth"],
    "play riddles":       ["a mushroom", "I don't know", "a star?"],
    "play simon says":    ["simon says jump", "jump", "simon says clap"],
    "play rock paper scissors": ["rock", "paper", "scissors"],
}

# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------

@dataclass
class GuestResult:
    name: str
    personality: str
    messages_sent: int = 0
    responses_received: int = 0
    audio_chunks: int = 0
    response_times: List[float] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    game_started: bool = False
    game_completed: bool = False
    game_type: str = ""
    empty_responses: int = 0
    timeout_count: int = 0
    duration: float = 0.0

    def to_dict(self) -> dict:
        rt = self.response_times
        return {
            "name": self.name,
            "personality": self.personality,
            "messages_sent": self.messages_sent,
            "responses_received": self.responses_received,
            "audio_chunks": self.audio_chunks,
            "response_times": {
                "avg": round(statistics.mean(rt), 2) if rt else 0,
                "p50": round(statistics.median(rt), 2) if rt else 0,
                "p95": round(sorted(rt)[int(len(rt) * 0.95)] if len(rt) >= 2 else (rt[0] if rt else 0), 2),
                "max": round(max(rt), 2) if rt else 0,
            },
            "errors": self.errors,
            "game_started": self.game_started,
            "game_completed": self.game_completed,
            "game_type": self.game_type,
            "empty_responses": self.empty_responses,
            "timeout_count": self.timeout_count,
            "duration": round(self.duration, 1),
        }


@dataclass
class HealthSnapshot:
    timestamp: float
    status: str = "unknown"
    emotion: str = ""
    tts_cache_size: int = 0
    tts_cache_hit_rate: float = 0.0
    avg_response_time: float = 0.0
    total_responses: int = 0
    conversation_length: int = 0
    active_game: Optional[str] = None
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "status": self.status,
            "emotion": self.emotion,
            "tts_cache_size": self.tts_cache_size,
            "tts_cache_hit_rate": self.tts_cache_hit_rate,
            "avg_response_time": self.avg_response_time,
            "total_responses": self.total_responses,
            "conversation_length": self.conversation_length,
            "active_game": self.active_game,
            "error": self.error,
        }


@dataclass
class CycleResult:
    cycle_num: int
    start_time: str
    end_time: str
    duration_seconds: float = 0.0
    guests_simulated: int = 0
    messages_sent: int = 0
    responses_received: int = 0
    errors: int = 0
    avg_response_time: float = 0.0
    pass_rate: float = 0.0
    is_perfect: bool = False
    alerts: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "cycle_num": self.cycle_num,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_seconds": round(self.duration_seconds, 1),
            "guests_simulated": self.guests_simulated,
            "messages_sent": self.messages_sent,
            "responses_received": self.responses_received,
            "errors": self.errors,
            "avg_response_time": round(self.avg_response_time, 2),
            "pass_rate": round(self.pass_rate, 1),
            "is_perfect": self.is_perfect,
            "alerts": self.alerts,
        }


# ---------------------------------------------------------------------------
# Endurance Test Engine
# ---------------------------------------------------------------------------

class EnduranceTest:
    """Autonomous endurance stress test with health monitoring and self-learning."""

    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.hours = args.hours
        self.guests_per_wave = args.guests
        self.ralph_mode = args.ralph
        self.verbose = args.verbose
        self.results_path = args.results
        self.load_path = args.load

        # Cumulative metrics
        self.total_guests = 0
        self.total_messages_sent = 0
        self.total_responses_received = 0
        self.total_errors = 0
        self.error_types: Dict[str, int] = defaultdict(int)
        self.all_response_times: List[float] = []
        self.games_started = 0
        self.games_completed = 0

        # Health monitoring
        self.health_snapshots: List[HealthSnapshot] = []
        self.health_checks_total = 0
        self.health_checks_passed = 0
        self.health_checks_failed = 0
        self.health_fail_streak = 0
        self.alerts: List[Dict[str, Any]] = []

        # Per-guest results
        self.guest_results: List[GuestResult] = []

        # Cycle tracking (for ralph mode and trend analysis)
        self.cycles: List[CycleResult] = []

        # Self-learning
        self.learnings: List[Dict[str, Any]] = []
        self.slow_message_types: Dict[str, List[float]] = defaultdict(list)
        self.failing_game_types: Dict[str, int] = defaultdict(int)
        self.game_attempts: Dict[str, int] = defaultdict(int)
        self.previous_results: Optional[dict] = None

        # Runtime state
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.running = True
        self.health_monitor_task: Optional[asyncio.Task] = None

        # Ralph mode state
        self.ralph_perfect_streak = 0

    # ------------------------------------------------------------------
    # Previous results loading (self-learning)
    # ------------------------------------------------------------------

    def load_previous_results(self):
        path = self.load_path
        if not path:
            candidates = sorted(
                [f for f in os.listdir(SCRIPT_DIR) if f.startswith("endurance_results_") and f.endswith(".json")],
                reverse=True,
            )
            if candidates:
                path = os.path.join(SCRIPT_DIR, candidates[0])

        if path and os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self.previous_results = json.load(f)
                prev_learnings = self.previous_results.get("learnings", [])
                log.info(f"📚 Loaded previous results from {os.path.basename(path)} "
                         f"({len(prev_learnings)} learnings)")
                for learning in prev_learnings:
                    if learning.get("type") == "slow_message":
                        msg = learning.get("message", "")
                        self.slow_message_types[msg].append(learning.get("avg_time", 0))
                    elif learning.get("type") == "failing_game":
                        game = learning.get("game", "")
                        self.failing_game_types[game] += learning.get("failures", 0)
            except Exception as e:
                log.warning(f"⚠️ Could not load previous results: {e}")

    # ------------------------------------------------------------------
    # Health monitoring
    # ------------------------------------------------------------------

    async def health_monitor_loop(self):
        """Background task: poll /health and /stats every HEALTH_CHECK_INTERVAL seconds."""
        last_total_responses = 0
        stagnant_count = 0

        while self.running:
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            if not self.running:
                break

            snap = HealthSnapshot(timestamp=time.time())
            self.health_checks_total += 1

            try:
                r = requests.get(f"{SERVER_HTTP}/health", timeout=10)
                h = r.json()
                snap.status = h.get("status", "unknown")
                snap.emotion = h.get("emotion", "")
                snap.tts_cache_size = h.get("tts_cache_size", 0)
                snap.total_responses = h.get("total_responses", 0)
                snap.conversation_length = h.get("conversation_length", 0)
                snap.active_game = h.get("active_game")

                raw_hit_rate = h.get("tts_cache_hit_rate", "0%")
                try:
                    snap.tts_cache_hit_rate = float(str(raw_hit_rate).replace("%", ""))
                except (ValueError, TypeError):
                    snap.tts_cache_hit_rate = 0.0

                raw_rt = h.get("avg_response_time", "0s")
                try:
                    snap.avg_response_time = float(str(raw_rt).replace("s", ""))
                except (ValueError, TypeError):
                    snap.avg_response_time = 0.0

                self.health_checks_passed += 1
                self.health_fail_streak = 0

                # --- Alert checks ---
                if snap.avg_response_time > ALERT_RESPONSE_TIME_THRESHOLD:
                    self._add_alert("SLOW_RESPONSE",
                                    f"Avg response time {snap.avg_response_time:.1f}s > {ALERT_RESPONSE_TIME_THRESHOLD}s")

                if snap.tts_cache_hit_rate > 0 and snap.tts_cache_hit_rate < ALERT_CACHE_HIT_RATE_MIN:
                    self._add_alert("LOW_CACHE_HIT",
                                    f"TTS cache hit rate {snap.tts_cache_hit_rate:.0f}% < {ALERT_CACHE_HIT_RATE_MIN}%")

                if snap.conversation_length > ALERT_CONVERSATION_LENGTH_MAX:
                    self._add_alert("MEMORY_LEAK",
                                    f"Conversation length {snap.conversation_length} > {ALERT_CONVERSATION_LENGTH_MAX}")

                if snap.total_responses == last_total_responses and last_total_responses > 0:
                    stagnant_count += 1
                    if stagnant_count >= 3:
                        self._add_alert("STAGNANT_RESPONSES",
                                        f"total_responses stuck at {snap.total_responses} for {stagnant_count} checks")
                else:
                    stagnant_count = 0
                last_total_responses = snap.total_responses

            except Exception as e:
                snap.status = "error"
                snap.error = str(e)
                self.health_checks_failed += 1
                self.health_fail_streak += 1

                if self.health_fail_streak >= ALERT_HEALTH_FAIL_STREAK_MAX:
                    self._add_alert("HEALTH_DOWN",
                                    f"Health check failed {self.health_fail_streak}x consecutively: {e}")

            self.health_snapshots.append(snap)

            if self.verbose:
                status_icon = "✅" if snap.status == "ok" else "⚠️"
                log.info(f"  {status_icon} Health: status={snap.status} rt={snap.avg_response_time:.1f}s "
                         f"cache={snap.tts_cache_hit_rate:.0f}% responses={snap.total_responses} "
                         f"conv_len={snap.conversation_length} emotion={snap.emotion}")

    def _add_alert(self, alert_type: str, message: str):
        alert = {
            "type": alert_type,
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "elapsed_hours": (time.time() - (self.start_time or time.time())) / 3600,
        }
        self.alerts.append(alert)
        log.warning(f"🚨 ALERT [{alert_type}]: {message}")

    # ------------------------------------------------------------------
    # WebSocket guest simulation
    # ------------------------------------------------------------------

    async def simulate_guest(self, profile: dict) -> GuestResult:
        """Simulate a single guest's visit: arrive, chat, optionally play a game, leave."""
        name = profile["name"]
        personality = profile["personality"]
        chattiness = profile["chattiness"]
        game_prob = profile["game_prob"]

        result = GuestResult(name=name, personality=personality)
        guest_start = time.time()

        num_messages = random.randint(max(3, chattiness - 2), min(10, chattiness + 2))
        wants_game = random.random() < game_prob

        msg_pool = PERSONALITY_MESSAGE_MAP.get(personality, ALL_CHAT_MESSAGES)

        log.info(f"  👤 {name} ({personality}) entering — will send {num_messages} msgs"
                 f"{' + game' if wants_game else ''}")

        ws = None
        try:
            ws = await asyncio.wait_for(
                websockets.connect(SERVER_WS, max_size=10_000_000),
                timeout=15,
            )

            # --- Presence Enter ---
            await ws.send(json.dumps({"type": "presence_enter", "name": name}))
            result.messages_sent += 1
            greeting_responses, greeting_audio = await self._collect_responses(ws, timeout=30, quiet_gap=10.0)

            if greeting_responses:
                result.responses_received += 1
                result.audio_chunks += greeting_audio
                for r in greeting_responses:
                    rt = r.get("response_time")
                    if rt and isinstance(rt, (int, float)):
                        result.response_times.append(float(rt))
            else:
                result.empty_responses += 1
                result.errors.append("no_greeting_response")
                self.error_types["no_greeting"] += 1

            # --- Chat Messages ---
            selected_messages = random.sample(msg_pool, min(num_messages, len(msg_pool)))

            for msg_text in selected_messages:
                if not self.running:
                    break

                await asyncio.sleep(COOLDOWN_BETWEEN_TEXTS)

                try:
                    await ws.send(json.dumps({
                        "type": "text_input",
                        "text": msg_text,
                        "speaker_name": name,
                    }))
                    result.messages_sent += 1
                    msg_start = time.time()

                    responses, audio_count = await self._collect_responses(ws, timeout=50, quiet_gap=10.0)
                    msg_duration = time.time() - msg_start

                    mario_text = self._extract_mario_text(responses)

                    if mario_text:
                        result.responses_received += 1
                        result.audio_chunks += audio_count
                        for r in responses:
                            rt = r.get("response_time")
                            if rt and isinstance(rt, (int, float)):
                                result.response_times.append(float(rt))
                            elif mario_text:
                                result.response_times.append(msg_duration)

                        self.slow_message_types[msg_text].append(msg_duration)

                        if self.verbose:
                            preview = mario_text[:80].replace("\n", " ")
                            log.info(f"    💬 {name}: \"{msg_text[:50]}\" → \"{preview}\" ({msg_duration:.1f}s)")
                    else:
                        result.empty_responses += 1
                        result.errors.append(f"empty_response: {msg_text[:40]}")
                        self.error_types["empty_response"] += 1
                        if self.verbose:
                            log.warning(f"    ⚠️ {name}: \"{msg_text[:50]}\" → EMPTY ({msg_duration:.1f}s)")

                except asyncio.TimeoutError:
                    result.timeout_count += 1
                    result.errors.append(f"timeout: {msg_text[:40]}")
                    self.error_types["timeout"] += 1
                    log.warning(f"    ⏰ {name}: timeout on \"{msg_text[:40]}\"")
                except Exception as e:
                    result.errors.append(f"send_error: {e}")
                    self.error_types["send_error"] += 1

            # --- Game (optional) ---
            if wants_game and self.running:
                await self._simulate_game(ws, name, result)

            # --- Presence Exit ---
            try:
                await ws.send(json.dumps({"type": "presence_exit"}))
                farewell_responses, _ = await self._collect_responses(ws, timeout=20, quiet_gap=8.0)
                if farewell_responses:
                    result.responses_received += 1
            except Exception:
                pass

        except asyncio.TimeoutError:
            result.errors.append("connection_timeout")
            self.error_types["connection_timeout"] += 1
            log.error(f"    ❌ {name}: connection timeout")
        except websockets.exceptions.ConnectionClosedError as e:
            result.errors.append(f"ws_closed: {e}")
            self.error_types["ws_closed"] += 1
        except ConnectionRefusedError:
            result.errors.append("connection_refused")
            self.error_types["connection_refused"] += 1
            log.error(f"    ❌ {name}: connection refused — server down?")
        except Exception as e:
            result.errors.append(f"unexpected: {e}")
            self.error_types["unexpected"] += 1
            log.error(f"    ❌ {name}: unexpected error: {e}")
        finally:
            if ws:
                try:
                    await ws.close()
                except Exception:
                    pass

        result.duration = time.time() - guest_start
        self.guest_results.append(result)
        self.total_guests += 1
        self.total_messages_sent += result.messages_sent
        self.total_responses_received += result.responses_received
        self.total_errors += len(result.errors)
        self.all_response_times.extend(result.response_times)
        if result.game_started:
            self.games_started += 1
        if result.game_completed:
            self.games_completed += 1

        pass_icon = "✅" if not result.errors else "⚠️"
        avg_rt = statistics.mean(result.response_times) if result.response_times else 0
        log.info(f"  {pass_icon} {name} done: {result.responses_received}/{result.messages_sent} responses, "
                 f"avg_rt={avg_rt:.1f}s, errors={len(result.errors)}, duration={result.duration:.0f}s")

        return result

    async def _simulate_game(self, ws, name: str, result: GuestResult):
        """Simulate a guest starting and playing through a game."""
        game_cmd = random.choice(GAME_COMMANDS)
        game_type = game_cmd.replace("play ", "")
        result.game_type = game_type
        self.game_attempts[game_type] += 1

        await asyncio.sleep(COOLDOWN_BETWEEN_TEXTS)

        try:
            await ws.send(json.dumps({
                "type": "text_input",
                "text": game_cmd,
                "speaker_name": name,
            }))
            result.messages_sent += 1
            responses, audio = await self._collect_responses(ws, timeout=30, quiet_gap=10.0)
            mario_text = self._extract_mario_text(responses)

            if mario_text and any(kw in mario_text.upper() for kw in GAME_KEYWORDS):
                result.game_started = True
                result.responses_received += 1
                result.audio_chunks += audio

                if self.verbose:
                    log.info(f"    🎮 {name}: Game '{game_type}' started!")

                # Play 2-3 follow-up moves
                followups = GAME_FOLLOWUP.get(game_cmd, ["yes", "no"])
                num_moves = random.randint(1, min(3, len(followups)))
                game_moves_ok = 0

                for move in followups[:num_moves]:
                    await asyncio.sleep(COOLDOWN_BETWEEN_TEXTS)
                    await ws.send(json.dumps({
                        "type": "text_input",
                        "text": move,
                        "speaker_name": name,
                    }))
                    result.messages_sent += 1
                    move_resp, move_audio = await self._collect_responses(ws, timeout=30, quiet_gap=10.0)
                    move_text = self._extract_mario_text(move_resp)
                    if move_text:
                        result.responses_received += 1
                        result.audio_chunks += move_audio
                        game_moves_ok += 1

                result.game_completed = game_moves_ok > 0
                if not result.game_completed:
                    self.failing_game_types[game_type] += 1
            else:
                result.errors.append(f"game_not_started: {game_type}")
                self.error_types["game_not_started"] += 1
                self.failing_game_types[game_type] += 1
                if mario_text:
                    result.responses_received += 1

        except Exception as e:
            result.errors.append(f"game_error: {e}")
            self.error_types["game_error"] += 1
            self.failing_game_types[game_type] += 1

    async def _collect_responses(self, ws, timeout: float = 30, quiet_gap: float = 8.0):
        """Collect all WebSocket responses until silence or timeout."""
        responses = []
        audio_count = 0
        t0 = time.time()
        last_msg_time = t0

        while time.time() - t0 < timeout:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=4.0)
                last_msg_time = time.time()

                if isinstance(msg, bytes):
                    audio_count += 1
                else:
                    try:
                        data = json.loads(msg)
                        responses.append(data)
                    except json.JSONDecodeError:
                        pass

            except asyncio.TimeoutError:
                elapsed_quiet = time.time() - last_msg_time
                has_content = (
                    any(r.get("type") == "mario_response" for r in responses)
                    or audio_count > 0
                )
                if elapsed_quiet > quiet_gap and has_content:
                    break
                if elapsed_quiet > quiet_gap * 2:
                    break
            except websockets.exceptions.ConnectionClosed:
                break
            except Exception:
                break

        return responses, audio_count

    @staticmethod
    def _extract_mario_text(responses: list) -> str:
        """Extract combined mario_response text from a list of response dicts."""
        texts = []
        for r in responses:
            if r.get("type") == "mario_response":
                txt = r.get("text", "").strip()
                if txt:
                    texts.append(txt)
        return " ".join(texts)

    # ------------------------------------------------------------------
    # Wave simulation (a batch of guests)
    # ------------------------------------------------------------------

    async def run_guest_wave(self, wave_num: int, num_guests: int) -> List[GuestResult]:
        """Simulate a wave of guests arriving sequentially."""
        log.info(f"\n🌊 Wave {wave_num}: {num_guests} guests incoming")
        wave_results = []

        available = list(GUEST_PROFILES)
        random.shuffle(available)
        wave_profiles = available[:num_guests]

        for i, profile in enumerate(wave_profiles):
            if not self.running:
                break

            if i > 0:
                gap = random.uniform(GAP_BETWEEN_GUESTS, GAP_BETWEEN_GUESTS + 3)
                if self.verbose:
                    log.info(f"  ⏳ Waiting {gap:.0f}s between guests...")
                await asyncio.sleep(gap)

            result = await self.simulate_guest(profile)
            wave_results.append(result)

        return wave_results

    # ------------------------------------------------------------------
    # Self-learning analysis
    # ------------------------------------------------------------------

    def analyze_cycle(self, cycle_results: List[GuestResult], cycle_num: int) -> CycleResult:
        """Analyze a cycle's results, generate learnings, return CycleResult."""
        now_iso = datetime.now(timezone.utc).isoformat()

        total_msgs = sum(r.messages_sent for r in cycle_results)
        total_resp = sum(r.responses_received for r in cycle_results)
        total_err = sum(len(r.errors) for r in cycle_results)
        all_rt = []
        for r in cycle_results:
            all_rt.extend(r.response_times)

        pass_rate = (total_resp / total_msgs * 100) if total_msgs > 0 else 0
        avg_rt = statistics.mean(all_rt) if all_rt else 0

        is_perfect = (
            pass_rate >= RALPH_PASS_RATE_MIN
            and avg_rt <= RALPH_AVG_RESPONSE_TIME_MAX
            and total_err == 0
        )

        cycle = CycleResult(
            cycle_num=cycle_num,
            start_time=now_iso,
            end_time=now_iso,
            guests_simulated=len(cycle_results),
            messages_sent=total_msgs,
            responses_received=total_resp,
            errors=total_err,
            avg_response_time=avg_rt,
            pass_rate=pass_rate,
            is_perfect=is_perfect,
        )

        # --- Learnings ---
        # Find slow messages
        for msg, times in self.slow_message_types.items():
            if len(times) >= 2:
                avg_time = statistics.mean(times[-5:])
                if avg_time > ALERT_RESPONSE_TIME_THRESHOLD:
                    self.learnings.append({
                        "type": "slow_message",
                        "message": msg[:80],
                        "avg_time": round(avg_time, 2),
                        "samples": len(times),
                        "cycle": cycle_num,
                    })

        # Find failing games
        for game, failures in self.failing_game_types.items():
            attempts = self.game_attempts.get(game, 0)
            if attempts > 0 and failures / attempts > 0.3:
                self.learnings.append({
                    "type": "failing_game",
                    "game": game,
                    "failures": failures,
                    "attempts": attempts,
                    "failure_rate": round(failures / attempts * 100, 1),
                    "cycle": cycle_num,
                })

        # Find guests with most errors
        for r in cycle_results:
            if len(r.errors) >= 3:
                self.learnings.append({
                    "type": "problematic_guest",
                    "guest": r.name,
                    "personality": r.personality,
                    "error_count": len(r.errors),
                    "error_types": r.errors[:5],
                    "cycle": cycle_num,
                })

        # Empty response patterns
        empty_count = sum(r.empty_responses for r in cycle_results)
        if empty_count > 0 and total_msgs > 0 and empty_count / total_msgs > 0.1:
            self.learnings.append({
                "type": "high_empty_rate",
                "empty_count": empty_count,
                "total_messages": total_msgs,
                "rate": round(empty_count / total_msgs * 100, 1),
                "cycle": cycle_num,
            })

        self.cycles.append(cycle)
        return cycle

    # ------------------------------------------------------------------
    # Results persistence
    # ------------------------------------------------------------------

    def save_results(self):
        """Save all collected data to a JSON results file."""
        if not self.results_path:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.results_path = os.path.join(SCRIPT_DIR, f"endurance_results_{ts}.json")

        rt = self.all_response_times
        results = {
            "start_time": datetime.fromtimestamp(self.start_time, tz=timezone.utc).isoformat() if self.start_time else None,
            "end_time": datetime.fromtimestamp(self.end_time, tz=timezone.utc).isoformat() if self.end_time else None,
            "duration_hours": round((self.end_time - self.start_time) / 3600, 2) if self.start_time and self.end_time else 0,
            "total_guests": self.total_guests,
            "total_messages": self.total_messages_sent,
            "total_responses": self.total_responses_received,
            "response_times": {
                "avg": round(statistics.mean(rt), 2) if rt else 0,
                "p50": round(statistics.median(rt), 2) if rt else 0,
                "p95": round(sorted(rt)[int(len(rt) * 0.95)], 2) if len(rt) >= 2 else (round(rt[0], 2) if rt else 0),
                "max": round(max(rt), 2) if rt else 0,
            },
            "error_count": self.total_errors,
            "error_types": dict(self.error_types),
            "games_started": self.games_started,
            "games_completed": self.games_completed,
            "tts_cache_trend": [
                {"time": s.timestamp, "hit_rate": s.tts_cache_hit_rate, "size": s.tts_cache_size}
                for s in self.health_snapshots if s.status == "ok"
            ],
            "response_time_trend": [
                {"time": s.timestamp, "avg_rt": s.avg_response_time}
                for s in self.health_snapshots if s.status == "ok"
            ],
            "health_checks": {
                "total": self.health_checks_total,
                "passed": self.health_checks_passed,
                "failed": self.health_checks_failed,
            },
            "alerts": self.alerts,
            "guest_results": [g.to_dict() for g in self.guest_results],
            "cycles": [c.to_dict() for c in self.cycles],
            "learnings": self._deduplicate_learnings(),
        }

        try:
            with open(self.results_path, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2, default=str)
            log.info(f"💾 Results saved to {self.results_path}")
        except Exception as e:
            log.error(f"❌ Failed to save results: {e}")

        return results

    def _deduplicate_learnings(self) -> list:
        """Deduplicate learnings by type+key, keeping latest."""
        seen = {}
        for learning in self.learnings:
            key_parts = [learning.get("type", "")]
            if "message" in learning:
                key_parts.append(learning["message"][:40])
            if "game" in learning:
                key_parts.append(learning["game"])
            if "guest" in learning:
                key_parts.append(learning["guest"])
            key = "|".join(key_parts)
            seen[key] = learning
        return list(seen.values())

    # ------------------------------------------------------------------
    # Pre-flight health check
    # ------------------------------------------------------------------

    async def preflight_check(self) -> bool:
        """Verify server is healthy before starting the test."""
        log.info("🔍 Pre-flight health check...")
        try:
            r = requests.get(f"{SERVER_HTTP}/health", timeout=10)
            h = r.json()
            status = h.get("status", "unknown")
            cache = h.get("tts_cache_size", 0)
            log.info(f"  ✅ Server status={status}, cache={cache}, emotion={h.get('emotion', '?')}")

            if status != "ok":
                log.error(f"  ❌ Server status is '{status}', not 'ok'")
                return False

            return True
        except requests.ConnectionError:
            log.error(f"  ❌ Cannot connect to {SERVER_HTTP} — is the server running?")
            return False
        except Exception as e:
            log.error(f"  ❌ Pre-flight failed: {e}")
            return False

    # ------------------------------------------------------------------
    # Main timed run (standard mode)
    # ------------------------------------------------------------------

    async def run_timed(self):
        """Run the endurance test for self.hours hours."""
        duration_seconds = self.hours * 3600
        self.start_time = time.time()
        deadline = self.start_time + duration_seconds

        log.info(f"\n{'='*70}")
        log.info(f"🏁 ENDURANCE TEST — {self.hours} hours ({duration_seconds}s)")
        log.info(f"   Guests per wave: {self.guests_per_wave}")
        log.info(f"   Server: {SERVER_HTTP}")
        log.info(f"   Log: {_log_file}")
        log.info(f"{'='*70}\n")

        # Start health monitor
        self.health_monitor_task = asyncio.create_task(self.health_monitor_loop())

        wave_num = 0
        cycle_num = 0
        cycle_start = time.time()
        cycle_guests: List[GuestResult] = []

        try:
            while time.time() < deadline and self.running:
                wave_num += 1
                remaining = deadline - time.time()
                elapsed = time.time() - self.start_time
                hours_elapsed = elapsed / 3600
                pct = (elapsed / duration_seconds) * 100

                log.info(f"\n{'─'*50}")
                log.info(f"⏱️  {hours_elapsed:.1f}h elapsed ({pct:.0f}%) — {remaining/60:.0f} min remaining")
                log.info(f"   Totals: {self.total_guests} guests, {self.total_messages_sent} msgs, "
                         f"{self.total_errors} errors, {len(self.alerts)} alerts")

                wave_results = await self.run_guest_wave(wave_num, self.guests_per_wave)
                cycle_guests.extend(wave_results)

                # Analyze every ~30 minutes
                if time.time() - cycle_start >= RALPH_CYCLE_MINUTES * 60:
                    cycle_num += 1
                    cycle = self.analyze_cycle(cycle_guests, cycle_num)
                    self._print_cycle_summary(cycle)
                    cycle_guests = []
                    cycle_start = time.time()
                    self.save_results()

                # Inter-wave pause (simulate realistic inter-arrival gap)
                if time.time() < deadline:
                    inter_wave = random.uniform(30, 120)
                    inter_wave = min(inter_wave, deadline - time.time())
                    if inter_wave > 0:
                        if self.verbose:
                            log.info(f"  ⏳ Next wave in {inter_wave:.0f}s...")
                        await asyncio.sleep(inter_wave)

        except KeyboardInterrupt:
            log.info("\n⛔ Interrupted by user")
        except Exception as e:
            log.error(f"\n❌ Fatal error: {e}\n{traceback.format_exc()}")
        finally:
            self.running = False
            if self.health_monitor_task:
                self.health_monitor_task.cancel()
                try:
                    await self.health_monitor_task
                except asyncio.CancelledError:
                    pass

        # Final cycle analysis if anything pending
        if cycle_guests:
            cycle_num += 1
            cycle = self.analyze_cycle(cycle_guests, cycle_num)
            self._print_cycle_summary(cycle)

        self.end_time = time.time()
        self.save_results()
        self._print_final_summary()

    # ------------------------------------------------------------------
    # Ralph mode (continuous improvement)
    # ------------------------------------------------------------------

    async def run_ralph(self):
        """Run continuous 30-minute cycles until 3 consecutive perfect cycles."""
        self.start_time = time.time()

        log.info(f"\n{'='*70}")
        log.info(f"🔁 RALPH MODE — Continuous improvement until "
                 f"{RALPH_PERFECT_CYCLES_NEEDED} perfect cycles")
        log.info(f"   Cycle length: {RALPH_CYCLE_MINUTES} min")
        log.info(f"   Perfect = >{RALPH_PASS_RATE_MIN}% pass, <{RALPH_AVG_RESPONSE_TIME_MAX}s avg, 0 errors")
        log.info(f"   Guests per wave: {self.guests_per_wave}")
        log.info(f"   Server: {SERVER_HTTP}")
        log.info(f"{'='*70}\n")

        # Start health monitor
        self.health_monitor_task = asyncio.create_task(self.health_monitor_loop())
        cycle_num = 0
        max_runtime = self.hours * 3600  # Respect --hours even in ralph mode

        try:
            while (self.ralph_perfect_streak < RALPH_PERFECT_CYCLES_NEEDED
                   and self.running
                   and (time.time() - self.start_time) < max_runtime):
                cycle_num += 1
                cycle_deadline = time.time() + (RALPH_CYCLE_MINUTES * 60)
                cycle_guests: List[GuestResult] = []
                wave_num = 0

                log.info(f"\n{'='*50}")
                log.info(f"🔄 RALPH CYCLE {cycle_num} (perfect streak: "
                         f"{self.ralph_perfect_streak}/{RALPH_PERFECT_CYCLES_NEEDED})")
                log.info(f"{'='*50}")

                # Adjust density based on learnings
                effective_guests = self.guests_per_wave
                if self.ralph_perfect_streak == 0 and cycle_num > 1:
                    effective_guests = min(self.guests_per_wave + 2, len(GUEST_PROFILES))
                    log.info(f"   📈 Increasing test density: {effective_guests} guests/wave")

                while time.time() < cycle_deadline and self.running:
                    wave_num += 1
                    wave_results = await self.run_guest_wave(wave_num, effective_guests)
                    cycle_guests.extend(wave_results)

                    if time.time() < cycle_deadline:
                        inter_wave = random.uniform(20, 60)
                        inter_wave = min(inter_wave, cycle_deadline - time.time())
                        if inter_wave > 0:
                            await asyncio.sleep(inter_wave)

                # Analyze cycle
                cycle = self.analyze_cycle(cycle_guests, cycle_num)

                if cycle.is_perfect:
                    self.ralph_perfect_streak += 1
                    log.info(f"  ✨ PERFECT CYCLE! Streak: {self.ralph_perfect_streak}/{RALPH_PERFECT_CYCLES_NEEDED}")
                else:
                    if self.ralph_perfect_streak > 0:
                        log.info(f"  💔 Streak broken (was {self.ralph_perfect_streak})")
                    self.ralph_perfect_streak = 0
                    log.info(f"  ❌ Not perfect: pass={cycle.pass_rate:.1f}%, "
                             f"avg_rt={cycle.avg_response_time:.1f}s, errors={cycle.errors}")

                self._print_cycle_summary(cycle)
                self.save_results()

                # Health check between cycles
                if self.ralph_perfect_streak < RALPH_PERFECT_CYCLES_NEEDED:
                    log.info("  🩺 Inter-cycle health check...")
                    healthy = await self.preflight_check()
                    if not healthy:
                        log.warning("  ⚠️ Server unhealthy — waiting 30s before retry...")
                        await asyncio.sleep(30)
                        healthy = await self.preflight_check()
                        if not healthy:
                            self._add_alert("SERVER_DOWN_RALPH",
                                            f"Server unhealthy between cycles, cycle {cycle_num}")
                            log.error("  ❌ Server still unhealthy — aborting ralph mode")
                            break

        except KeyboardInterrupt:
            log.info("\n⛔ Interrupted by user")
        except Exception as e:
            log.error(f"\n❌ Fatal error: {e}\n{traceback.format_exc()}")
        finally:
            self.running = False
            if self.health_monitor_task:
                self.health_monitor_task.cancel()
                try:
                    await self.health_monitor_task
                except asyncio.CancelledError:
                    pass

        self.end_time = time.time()
        self.save_results()
        self._print_final_summary()

        if self.ralph_perfect_streak >= RALPH_PERFECT_CYCLES_NEEDED:
            log.info(f"\n🏆 RALPH SUCCESS: {RALPH_PERFECT_CYCLES_NEEDED} consecutive perfect cycles achieved!")
        else:
            log.info(f"\n⚠️ RALPH INCOMPLETE: streak was {self.ralph_perfect_streak}/{RALPH_PERFECT_CYCLES_NEEDED}")

    # ------------------------------------------------------------------
    # Summaries
    # ------------------------------------------------------------------

    def _print_cycle_summary(self, cycle: CycleResult):
        """Print a summary of a completed cycle."""
        icon = "✅" if cycle.is_perfect else "⚠️"
        log.info(f"\n  {icon} Cycle {cycle.cycle_num} Summary:")
        log.info(f"     Guests: {cycle.guests_simulated}")
        log.info(f"     Messages: {cycle.messages_sent} sent, {cycle.responses_received} received")
        log.info(f"     Pass rate: {cycle.pass_rate:.1f}%")
        log.info(f"     Avg response time: {cycle.avg_response_time:.2f}s")
        log.info(f"     Errors: {cycle.errors}")

    def _print_final_summary(self):
        """Print the comprehensive final summary."""
        duration = (self.end_time - self.start_time) if self.start_time and self.end_time else 0
        rt = self.all_response_times

        log.info(f"\n{'='*70}")
        log.info("🏁 ENDURANCE TEST — FINAL REPORT")
        log.info(f"{'='*70}")
        log.info(f"  Duration:          {duration/3600:.2f} hours ({duration:.0f}s)")
        log.info(f"  Total guests:      {self.total_guests}")
        log.info(f"  Total messages:    {self.total_messages_sent}")
        log.info(f"  Total responses:   {self.total_responses_received}")

        if self.total_messages_sent > 0:
            overall_pass = self.total_responses_received / self.total_messages_sent * 100
            log.info(f"  Pass rate:         {overall_pass:.1f}%")

        if rt:
            log.info(f"\n  Response Times:")
            log.info(f"    Average:  {statistics.mean(rt):.2f}s")
            log.info(f"    Median:   {statistics.median(rt):.2f}s")
            sorted_rt = sorted(rt)
            p95_idx = int(len(sorted_rt) * 0.95)
            log.info(f"    P95:      {sorted_rt[p95_idx] if p95_idx < len(sorted_rt) else sorted_rt[-1]:.2f}s")
            log.info(f"    Max:      {max(rt):.2f}s")

        log.info(f"\n  Errors:            {self.total_errors}")
        if self.error_types:
            for etype, count in sorted(self.error_types.items(), key=lambda x: -x[1]):
                log.info(f"    {etype}: {count}")

        log.info(f"\n  Games:             {self.games_started} started, {self.games_completed} completed")

        log.info(f"\n  Health Checks:     {self.health_checks_passed}/{self.health_checks_total} passed")
        log.info(f"  Alerts:            {len(self.alerts)}")
        for a in self.alerts[:10]:
            log.info(f"    [{a['type']}] {a['message']}")
        if len(self.alerts) > 10:
            log.info(f"    ... and {len(self.alerts) - 10} more")

        log.info(f"\n  Cycles:            {len(self.cycles)}")
        perfect_cycles = sum(1 for c in self.cycles if c.is_perfect)
        log.info(f"  Perfect cycles:    {perfect_cycles}/{len(self.cycles)}")

        unique_learnings = self._deduplicate_learnings()
        if unique_learnings:
            log.info(f"\n  Learnings ({len(unique_learnings)}):")
            for l in unique_learnings[:10]:
                if l["type"] == "slow_message":
                    log.info(f"    🐢 Slow msg: \"{l['message'][:50]}\" avg={l['avg_time']:.1f}s")
                elif l["type"] == "failing_game":
                    log.info(f"    🎮 Failing game: {l['game']} ({l['failure_rate']:.0f}% failure)")
                elif l["type"] == "high_empty_rate":
                    log.info(f"    📭 High empty rate: {l['rate']:.1f}% ({l['empty_count']}/{l['total_messages']})")
                elif l["type"] == "problematic_guest":
                    log.info(f"    👤 Problematic: {l['guest']} ({l['error_count']} errors)")

        log.info(f"\n  Results: {self.results_path}")
        log.info(f"  Log:     {_log_file}")
        log.info(f"{'='*70}")

        # Final verdict
        if self.total_errors == 0 and self.health_checks_failed == 0:
            log.info("🎉 VERDICT: PERFECT — Zero errors, zero health failures!")
        elif self.total_errors < 5 and self.health_checks_failed < 3:
            log.info("✅ VERDICT: GOOD — Minor issues only")
        elif self.total_errors < 20:
            log.info("⚠️ VERDICT: FAIR — Some issues need attention")
        else:
            log.info("❌ VERDICT: NEEDS WORK — Significant issues found")

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def run(self):
        """Main entry point — run pre-flight, load history, then start test."""
        self.load_previous_results()

        healthy = await self.preflight_check()
        if not healthy:
            log.error("❌ Pre-flight check failed. Start the server first!")
            log.error(f"   Expected: {SERVER_HTTP}")
            sys.exit(1)

        if self.ralph_mode:
            await self.run_ralph()
        else:
            await self.run_timed()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Mario AI Party Bot — Autonomous Endurance Stress Test",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python party_endurance_test.py                  # 6-hour endurance run
    python party_endurance_test.py --hours 1        # 1-hour quick test
    python party_endurance_test.py --ralph           # Ralph mode: 3 perfect cycles
    python party_endurance_test.py --guests 8        # 8 guests per wave
    python party_endurance_test.py --verbose         # Show all message details
    python party_endurance_test.py --load prev.json  # Learn from previous run
        """,
    )
    parser.add_argument("--hours", type=float, default=6.0,
                        help="Duration in hours (default: 6)")
    parser.add_argument("--ralph", action="store_true",
                        help="Ralph mode: run until 3 consecutive perfect cycles")
    parser.add_argument("--guests", type=int, default=5,
                        help="Number of guests per wave (default: 5)")
    parser.add_argument("--verbose", action="store_true",
                        help="Show all message details")
    parser.add_argument("--results", type=str, default=None,
                        help="Custom results file path")
    parser.add_argument("--load", type=str, default=None,
                        help="Load previous results JSON for learning context")
    return parser.parse_args()


def main():
    args = parse_args()

    log.info(f"🍄 Mario AI Party Bot — Endurance Stress Test")
    log.info(f"   Mode: {'Ralph (continuous)' if args.ralph else f'Timed ({args.hours}h)'}")
    log.info(f"   Guests/wave: {args.guests}")
    log.info(f"   Verbose: {args.verbose}")
    log.info(f"   Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    test = EnduranceTest(args)

    try:
        asyncio.run(test.run())
    except KeyboardInterrupt:
        log.info("\n⛔ Aborted by user — saving partial results...")
        test.end_time = time.time()
        test.save_results()
        test._print_final_summary()


if __name__ == "__main__":
    main()
