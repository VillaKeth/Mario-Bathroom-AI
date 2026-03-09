"""Mario AI Server — FastAPI WebSocket server.

Handles all heavy AI processing:
- Speech-to-text (faster-whisper)
- Speaker identification (resemblyzer)
- LLM conversation (Ollama)
- Text-to-speech (Edge TTS)
- Memory management (SQLite)
- Emotion system
- Party statistics
- Safety filtering
- Idle behavior / autonomous actions
"""

import asyncio
import base64
import json
import logging
import os
import random
import re
import time
import threading
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from contextlib import asynccontextmanager
from collections import deque
from concurrent.futures import ThreadPoolExecutor

import stt
import tts
import llm
import speaker_id
import memory
import mario_prompt
from emotions import EmotionSystem, Emotion
from party_stats import PartyStats
from safety_filter import filter_response, check_input
from idle_behavior import IdleBehavior
from pose_analyzer import analyze_text
import command_handlers

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("mario-server")

# Load config
CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")
config = {}
if os.path.exists(CONFIG_PATH):
    with open(CONFIG_PATH) as f:
        config = json.load(f)
    logger.info(f"Loaded config from {CONFIG_PATH}")
else:
    logger.warning(f"Config not found at {CONFIG_PATH} — using defaults")
server_config = config.get("server", {})

DEBUG_SERVER = os.environ.get("DEBUG_MODE", "").lower() == "true" or server_config.get("debug_server", True)

# Game configuration from config.json (with defaults)
GAME_CONFIG = {
    "simon_max_rounds": server_config.get("game_max_rounds_simon", 5),
    "truth_dare_max_rounds": server_config.get("game_max_rounds_truth_dare", 5),
    "twenty_q_max_questions": server_config.get("game_max_questions_20q", 10),
    "riddle_max_attempts": server_config.get("game_max_attempts_riddle", 5),
    "word_chain_max_rounds": server_config.get("game_max_rounds_word_chain", 10),
    "rapid_fire_max_rounds": server_config.get("game_max_rounds_rapid_fire", 15),
    "conversation_history_limit": server_config.get("conversation_history_limit", 28),
    "command_cooldown": server_config.get("command_cooldown_seconds", 1.0),
    "text_input_cooldown": server_config.get("text_input_cooldown_seconds", 2.0),
    "llm_timeout": server_config.get("llm_timeout_seconds", 30),
    "admin_api_key": server_config.get("admin_api_key", ""),
}

# Validate critical config values
_required_keys = {"llm_model": str, "tts_rate": str, "tts_voice": str}
for key, expected_type in _required_keys.items():
    val = server_config.get(key)
    if val is not None and not isinstance(val, expected_type):
        logger.warning(f"Config '{key}' should be {expected_type.__name__}, got {type(val).__name__}")
if not server_config.get("llm_model"):
    logger.warning("Config 'llm_model' not set — using default 'qwen2:1.5b'")
if not server_config.get("tts_voice"):
    logger.warning("Config 'tts_voice' not set — using default Edge TTS voice")


def _validate_config(cfg):
    """Validate config has required keys with correct types."""
    required = {
        "server": {"host": str, "port": int},
    }
    warnings = []
    server_cfg = cfg.get("server", {})
    if not server_cfg:
        warnings.append("Missing 'server' section in config")
    if not isinstance(server_cfg.get("port", 8765), int):
        warnings.append("server.port must be an integer")
    if "llm" in cfg:
        llm_cfg = cfg["llm"]
        if "model" in llm_cfg and not isinstance(llm_cfg["model"], str):
            warnings.append("llm.model must be a string")
        if "num_predict" in llm_cfg and not isinstance(llm_cfg["num_predict"], int):
            warnings.append("llm.num_predict must be an integer")
    for w in warnings:
        logger.warning(f"[CONFIG] {w}")
    return len(warnings) == 0


_validate_config(config)

# Systems
emotion_system = EmotionSystem()
party_stats = PartyStats()
idle_behavior = IdleBehavior()

# Lock for state_current to prevent race conditions across async handlers
_state_lock = asyncio.Lock()

# Track current conversation state
state_current = {
    "speaker_name": None,
    "speaker_id": None,
    "is_speaking": False,
    "presence": False,
    "presence_phase": "IDLE",  # State machine: IDLE → GREETING → CONVERSING → FAREWELL → IDLE
    "audio_buffer": bytearray(),
    "conversation_history": [],
    "current_visit_id": None,
    "enter_time": None,
    "_last_audio_chunk": None,
    "_user_request_active": False,  # Prevents idle TTS during user requests
    "_greeting_in_progress": False,  # Prevents presence_exit from clearing state mid-greeting
    "_last_buffer_time": 0.0,  # Timestamp of last audio buffer append
    "_last_text_input_time": 0.0,  # Rate limit text_input handler
    "_last_command_time": 0.0,  # Rate limit special commands (1s cooldown)
    "_active_game": None,  # Active game mode (simon_says, twenty_questions, truth_or_dare)
    "_game_state": {},  # Game-specific state data
    "_response_times": deque(maxlen=50),  # Track last 50 response times for metrics
    "_pending_announcement": None,  # Admin-queued announcement text
    "_detected_mood": None,  # Sentiment detection: drunk/sad/angry/None
    "_personality_mode": None,  # Personality mode: scary/dj/therapist/pirate/None
    "_last_dj_time": 0.0,  # Timestamp of last DJ announcement
    "_last_timing": {},  # Last response time breakdown (stt/llm/tts/total)
}

# Dedicated single-thread executor for TTS (prevents GPU contention)
_tts_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="tts")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize all AI models on startup."""
    logger.info("=== Mario AI Server Starting ===")

    logger.info("Loading speech-to-text model...")
    stt.init_model(
        model_size=server_config.get("stt_model_size", "base"),
        device=server_config.get("stt_device", "auto"),
    )

    logger.info("Loading TTS engine...")
    if server_config.get("tts_voice"):
        tts.EDGE_VOICE = server_config["tts_voice"]
    if server_config.get("tts_rate"):
        tts.RATE = server_config["tts_rate"]
    tts.init_tts()

    logger.info("Loading speaker identification...")
    speaker_id.init_speaker_id()

    logger.info("Initializing memory system...")
    memory.init_memory()

    # Archive old conversations on startup
    memory.archive_old_conversations(days_old=30)

    logger.info("Checking Ollama connection...")
    if server_config.get("llm_model"):
        llm.MODEL_NAME = server_config["llm_model"]
    has_model = await llm.check_ollama()
    if not has_model:
        logger.warning(f"⚠ Ollama model '{llm.MODEL_NAME}' not found! Run: ollama pull {llm.MODEL_NAME}")

    # Pre-cache common phrases in background (truly non-blocking)
    threading.Thread(target=tts.precache_phrases, daemon=True).start()
    logger.info("Pre-caching common Mario phrases in background...")

    logger.info("=== Mario AI Server Ready! Let's-a go! ===")
    yield
    logger.info("=== Mario AI Server Shutting Down ===")
    _tts_executor.shutdown(wait=False)
    if tts._edge_executor:
        tts._edge_executor.shutdown(wait=False)
    logger.info("=== Server shutdown complete ===")


app = FastAPI(title="Mario AI Server", lifespan=lifespan)


@app.get("/health")
async def health():
    stats = party_stats.get_stats()
    total_cache_requests = tts._cache_hits + tts._cache_misses
    cache_hit_rate = (tts._cache_hits / max(1, total_cache_requests)) * 100
    resp_times = state_current["_response_times"]
    avg_response = sum(resp_times) / max(1, len(resp_times)) if resp_times else 0
    return {
        "status": "ok",
        "message": "It's-a me, Mario!",
        "emotion": emotion_system.current,
        "emotion_intensity": emotion_system.intensity,
        "total_visits": stats["total_visits"],
        "unique_visitors": stats["unique_visitors"],
        "party_duration": stats["party_duration"],
        "current_hour": stats["current_hour"],
        "tts_cache_size": len(tts._audio_cache),
        "tts_cache_hits": tts._cache_hits,
        "tts_cache_misses": tts._cache_misses,
        "tts_cache_hit_rate": f"{cache_hit_rate:.0f}%",
        "avg_response_time": f"{avg_response:.1f}s",
        "total_responses": len(resp_times),
        "conversation_length": len(state_current["conversation_history"]),
        "user_active": state_current["_user_request_active"],
        "active_game": state_current["_active_game"],
        "llm_model": llm.MODEL_NAME,
        "last_timing": state_current.get("_last_timing", {}),
    }


@app.post("/config/reload")
async def reload_config():
    """Hot-reload config.json without restarting server."""
    global server_config
    try:
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")
        with open(config_path) as f:
            full_config = json.load(f)
        server_config = full_config.get("server", {})
        GAME_CONFIG.update({
            "simon_max_rounds": server_config.get("game_max_rounds_simon", 5),
            "truth_dare_max_rounds": server_config.get("game_max_rounds_truth_dare", 5),
            "twenty_q_max_questions": server_config.get("game_max_questions_20q", 10),
            "riddle_max_attempts": server_config.get("game_max_attempts_riddle", 5),
            "word_chain_max_rounds": server_config.get("game_max_rounds_word_chain", 10),
            "rapid_fire_max_rounds": server_config.get("game_max_rounds_rapid_fire", 15),
            "conversation_history_limit": server_config.get("conversation_history_limit", 28),
            "command_cooldown": server_config.get("command_cooldown_seconds", 1.0),
            "admin_api_key": server_config.get("admin_api_key", ""),
        })
        logger.info("Config reloaded successfully")
        return {"status": "ok", "message": "Config reloaded!"}
    except Exception as e:
        logger.error(f"Config reload failed: {e}")
        return {"status": "error", "message": str(e)}


# --- Sentiment Detection ---
_DRUNK_WORDS = {"drunk", "wasted", "hammered", "smashed", "tipsy", "buzzed", "sloshed", "trashed", "plastered", "lit", "faded"}
_SAD_WORDS = {"sad", "depressed", "lonely", "crying", "upset", "heartbroken", "miserable", "unhappy", "down", "broken", "hurting"}
_ANGRY_WORDS = {"angry", "mad", "furious", "pissed", "annoyed", "frustrated", "hate", "stupid", "idiot", "sucks"}


def detect_sentiment(text: str) -> str | None:
    """Detect if user is drunk/sad/angry from their text. Returns mood or None."""
    words = set(text.lower().split())
    # Check for slurred patterns (repeated chars, all caps yelling)
    slurred = bool(re.search(r'(.)\1{3,}', text)) or (len(text) > 10 and text == text.upper())
    if words & _DRUNK_WORDS or slurred:
        return "drunk"
    # Enhanced drunk detection heuristics
    word_list = text.split()
    if len(word_list) >= 3:
        elongated_words = sum(1 for w in word_list if re.search(r'(.)\1{3,}', w))
        if elongated_words >= 2:
            return "drunk"
        caps_words = sum(1 for w in word_list if w.isupper() and len(w) > 2)
        if caps_words >= 3:
            return "drunk"
        short_words = sum(1 for w in word_list if len(w) <= 2)
        if len(word_list) >= 5 and short_words / len(word_list) > 0.6:
            return "drunk"
    if words & _SAD_WORDS:
        return "sad"
    if words & _ANGRY_WORDS:
        return "angry"
    return None


# --- Holiday Detection ---
def detect_holiday() -> str | None:
    """Return the current holiday/special day name, or None."""
    now = datetime.now()
    m, d = now.month, now.day
    holidays = {
        (1, 1): "New Year's Day",
        (2, 14): "Valentine's Day",
        (3, 10): "Mario Day (MAR10)",
        (3, 17): "St. Patrick's Day",
        (4, 1): "April Fools' Day",
        (7, 4): "Fourth of July",
        (10, 31): "Halloween",
        (12, 25): "Christmas Day",
        (12, 31): "New Year's Eve",
    }
    return holidays.get((m, d))


# --- Scheduled Events ---
_scheduled_messages = {
    "midnight": {"hour": 0, "text": "Mama mia, it's MIDNIGHT! The witching hour! Are there-a any Boos around?!"},
    "one_am": {"hour": 1, "text": "It's-a 1 AM! The party warriors are still going! Wahoo!"},
    "two_am": {"hour": 2, "text": "2 AM already?! Even Bowser is asleep by now!"},
    "half_hour": {"hour": None, "minute": 30, "text": None},  # Generic half-hour marker
}
_last_scheduled_hour = -1


def check_scheduled_events() -> str | None:
    """Check if any scheduled event should trigger now."""
    global _last_scheduled_hour
    now = datetime.now()
    hour = now.hour
    if hour == _last_scheduled_hour:
        return None
    _last_scheduled_hour = hour
    for key, ev in _scheduled_messages.items():
        if ev.get("hour") == hour and ev.get("text"):
            return ev["text"]
    # Holiday announcement (once per hour at most)
    holiday = detect_holiday()
    if holiday and hour in (12, 18, 21):  # Announce at noon, 6pm, 9pm
        return f"Hey everyone! Happy {holiday}! Let's-a celebrate! Wahoo!"
    return None


# --- Stats Endpoint ---
@app.get("/stats")
async def stats_endpoint():
    """Analytics endpoint with detailed party stats."""
    stats = party_stats.get_stats()
    resp_times = state_current["_response_times"]
    avg_response = sum(resp_times) / max(1, len(resp_times)) if resp_times else 0
    trending = memory.get_trending_topics(limit=10)
    return {
        "party": {
            "total_visits": stats["total_visits"],
            "unique_visitors": stats["unique_visitors"],
            "party_duration": stats["party_duration"],
            "current_hour": stats["current_hour"],
            "busiest_hour": stats.get("busiest_hour"),
            "avg_visit_duration": stats.get("avg_visit_duration"),
            "longest_visitor": stats.get("longest_visitor"),
        },
        "performance": {
            "avg_response_time": f"{avg_response:.1f}s",
            "total_responses": len(resp_times),
            "tts_cache_size": len(tts._audio_cache),
            "tts_cache_hits": tts._cache_hits,
            "tts_cache_misses": tts._cache_misses,
        },
        "conversation": {
            "active_game": state_current["_active_game"],
            "conversation_length": len(state_current["conversation_history"]),
            "presence_phase": state_current["presence_phase"],
            "current_speaker": state_current["speaker_name"],
            "emotion": emotion_system.current,
        },
        "trending_topics": trending,
        "holiday": detect_holiday(),
    }


@app.get("/leaderboard")
async def leaderboard_endpoint():
    """Return party leaderboard data."""
    stats = party_stats.get_stats()
    people = party_stats.get_all_visitors()
    return {
        "total_visits": stats.get("total_visits", 0),
        "unique_visitors": stats.get("unique_visitors", 0),
        "longest_visit": stats.get("longest_visit_seconds", 0),
        "most_talkative": stats.get("most_frequent_name", "nobody"),
        "visitors": people[:10],
    }


# --- Admin Endpoints ---
@app.post("/admin/reset")
async def admin_reset(request_body: dict = {}):
    """Admin: Reset party stats. Requires admin_api_key if configured."""
    api_key = GAME_CONFIG.get("admin_api_key", "")
    if api_key and request_body.get("api_key") != api_key:
        return {"status": "error", "message": "Invalid API key"}
    party_stats.reset_party()
    return {"status": "ok", "message": "Party reset!"}


@app.post("/admin/set_emotion")
async def admin_set_emotion(request_body: dict = {}):
    """Admin: Set Mario's current emotion."""
    api_key = GAME_CONFIG.get("admin_api_key", "")
    if api_key and request_body.get("api_key") != api_key:
        return {"status": "error", "message": "Invalid API key"}
    new_emotion = request_body.get("emotion", "").lower()
    valid_emotions = {v for k, v in vars(Emotion).items() if not k.startswith("_")}
    if new_emotion in valid_emotions:
        emotion_system.current = new_emotion
        return {"status": "ok", "emotion": emotion_system.current}
    return {"status": "error", "message": f"Invalid emotion: {new_emotion}. Valid: {', '.join(sorted(valid_emotions))}"}


@app.post("/admin/announce")
async def admin_announce(request_body: dict = {}):
    """Admin: Queue a custom announcement for Mario to say."""
    api_key = GAME_CONFIG.get("admin_api_key", "")
    if api_key and request_body.get("api_key") != api_key:
        return {"status": "error", "message": "Invalid API key"}
    text = request_body.get("text", "")
    if not text or len(text) > 200:
        return {"status": "error", "message": "Text required (max 200 chars)"}
    state_current["_pending_announcement"] = text
    return {"status": "ok", "message": f"Announcement queued: {text[:50]}..."}


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    logger.info("Client connected!")

    # Reset per-connection state (games, conversation, etc.)
    state_current["_active_game"] = None
    state_current["_game_state"] = {}
    state_current["conversation_history"] = []
    state_current["_detected_mood"] = None
    state_current["presence_phase"] = "IDLE"

    # Send initial greeting (with 30s timeout to prevent blocking)
    loop = asyncio.get_event_loop()
    try:
        greeting_ctx = mario_prompt.build_context(event="startup")
        greeting_ctx.append({"role": "system", "content": emotion_system.get_prompt_addition()})
        greeting_text = await asyncio.wait_for(llm.generate_response(greeting_ctx), timeout=30.0)
        greeting_text = filter_response(greeting_text)
        analyzed = analyze_text(greeting_text)
        greeting_audio = await loop.run_in_executor(_tts_executor, lambda: tts.synthesize(analyzed["tts_text"]))
        await send_response(ws, analyzed["display_text"], greeting_audio, sound="greeting",
                            pose_hint=analyzed["pose_hint"])
    except asyncio.TimeoutError:
        logger.error("Startup greeting timed out after 30s")
        try:
            fallback_audio = await loop.run_in_executor(_tts_executor, lambda: tts.synthesize("Wahoo!"))
            await send_response(ws, "It's-a me, Mario! Wahoo!", fallback_audio, sound="greeting",
                                pose_hint="positive/excited_jump")
        except Exception:
            pass
    except Exception as e:
        logger.error(f"Startup greeting failed: {e}")
        try:
            fallback_audio = await loop.run_in_executor(_tts_executor, lambda: tts.synthesize("Wahoo!"))
            await send_response(ws, "It's-a me, Mario! Wahoo!", fallback_audio, sound="greeting",
                                pose_hint="positive/excited_jump")
        except Exception:
            pass

    # Start idle behavior loop
    idle_task = asyncio.create_task(_idle_loop(ws))
    heartbeat_task = asyncio.create_task(_heartbeat_loop(ws))
    emotion_decay_task = asyncio.create_task(_emotion_decay_loop())

    try:
        while True:
            data = await ws.receive()

            if "bytes" in data and data["bytes"]:
                audio_bytes = data["bytes"]
                if len(audio_bytes) > 5 * 1024 * 1024:  # 5MB max audio
                    logger.warning(f"[VALIDATION] Audio too large: {len(audio_bytes)} bytes")
                    continue
                try:
                    async with _state_lock:
                        await handle_audio(ws, audio_bytes)
                except Exception as e:
                    logger.error(f"handle_audio error: {e}")
            elif "text" in data and data["text"]:
                text_data = data["text"]
                if len(text_data) > 64 * 1024:  # 64KB max JSON
                    logger.warning(f"[VALIDATION] JSON too large: {len(text_data)} bytes")
                    continue
                try:
                    async with _state_lock:
                        await handle_event(ws, json.loads(text_data))
                except json.JSONDecodeError as e:
                    logger.warning(f"Invalid JSON from client: {e}")
                except Exception as e:
                    logger.error(f"handle_event error: {e}")

    except WebSocketDisconnect:
        logger.info("Client disconnected")
    except Exception as e:
        if "disconnect" in str(e).lower():
            logger.info("Client disconnected")
        else:
            logger.error(f"WebSocket error: {e}")
    finally:
        idle_task.cancel()
        try:
            await idle_task
        except asyncio.CancelledError:
            pass
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass
        emotion_decay_task.cancel()
        try:
            await emotion_decay_task
        except asyncio.CancelledError:
            pass


async def _heartbeat_loop(ws: WebSocket):
    """Send periodic heartbeat pings to detect dead connections."""
    _missed_pongs = 0
    while True:
        await asyncio.sleep(30)
        try:
            await ws.send_json({"type": "heartbeat", "server_time": time.time()})
            _missed_pongs = 0
        except Exception:
            _missed_pongs += 1
            if _missed_pongs >= 3:
                logger.warning("[HEARTBEAT] 3 consecutive heartbeats failed — connection may be dead")
                break


async def _emotion_decay_loop():
    """Gradually decay emotion intensity back to neutral when idle."""
    while True:
        await asyncio.sleep(300)  # Every 5 minutes
        if not state_current.get("_user_request_active"):
            emotion_system.update()  # Triggers natural decay in EmotionSystem
            if DEBUG_SERVER:
                logger.info(f"[EMOTION_DECAY] Emotion: {emotion_system.current}, intensity: {emotion_system.intensity:.2f}")


async def _idle_loop(ws: WebSocket):
    """Background loop for idle behavior — Mario mumbles/sings when alone."""
    loop = asyncio.get_event_loop()
    while True:
        await asyncio.sleep(random.uniform(3, 8))

        # Skip idle TTS when a user request is being processed (prevents GPU contention)
        async with _state_lock:
            user_active = state_current.get("_user_request_active")
        if user_active:
            continue

        # Check for admin announcements (priority)
        async with _state_lock:
            announcement = state_current.pop("_pending_announcement", None)
        if announcement:
            try:
                analyzed = analyze_text(announcement)
                audio = await loop.run_in_executor(_tts_executor, lambda: tts.synthesize(analyzed["tts_text"]))
                await send_response(ws, analyzed["display_text"], audio,
                                    sound="announcement", pose_hint=analyzed["pose_hint"] or "positive/excited_jump")
            except Exception as e:
                logger.error(f"Announcement failed: {e}")
            continue

        # Check scheduled time-based events
        scheduled_msg = check_scheduled_events()
        if scheduled_msg:
            try:
                analyzed = analyze_text(scheduled_msg)
                audio = await loop.run_in_executor(_tts_executor, lambda: tts.synthesize(analyzed["tts_text"]))
                await send_response(ws, analyzed["display_text"], audio,
                                    sound="coin", pose_hint=analyzed["pose_hint"] or "positive/excited_jump")
            except Exception as e:
                logger.error(f"Scheduled event failed: {e}")
            continue

        async with _state_lock:
            has_presence = state_current["presence"]
            enter_time = state_current["enter_time"] if has_presence else None
        if has_presence:
            if enter_time:
                minutes = (time.time() - enter_time) / 60
                comment = idle_behavior.get_long_stay_comment(minutes)
                if comment:
                    analyzed = analyze_text(comment)
                    audio = await loop.run_in_executor(_tts_executor, lambda: tts.synthesize(analyzed["tts_text"]))
                    try:
                        await send_response(ws, analyzed["display_text"], audio,
                                            sound="coin", pose_hint=analyzed["pose_hint"])
                    except Exception:
                        pass
            continue

        # DJ announcements when nobody is around (every 20+ minutes)
        async with _state_lock:
            last_dj = state_current.get("_last_dj_time", 0.0)
        if time.time() - last_dj >= 20 * 60:
            from idle_behavior import DJ_ANNOUNCEMENTS
            dj_msg = random.choice(DJ_ANNOUNCEMENTS)
            try:
                analyzed = analyze_text(dj_msg)
                audio = await loop.run_in_executor(_tts_executor, lambda: tts.synthesize(analyzed["tts_text"]))
                await send_response(ws, analyzed["display_text"], audio,
                                    sound="announcement", pose_hint=analyzed["pose_hint"] or "positive/excited_jump")
                async with _state_lock:
                    state_current["_last_dj_time"] = time.time()
            except Exception as e:
                logger.error(f"DJ announcement failed: {e}")
            continue

        # Time-specific party observations (every ~15 minutes)
        async with _state_lock:
            last_obs = state_current.get("_last_time_obs", 0.0)
        if time.time() - last_obs >= 15 * 60:
            obs = idle_behavior.get_time_observation()
            if obs:
                try:
                    analyzed = analyze_text(obs)
                    audio = await loop.run_in_executor(_tts_executor, lambda: tts.synthesize(analyzed["tts_text"]))
                    await send_response(ws, analyzed["display_text"], audio,
                                        pose_hint=analyzed["pose_hint"] or "positive/excited_jump")
                    async with _state_lock:
                        state_current["_last_time_obs"] = time.time()
                except Exception as e:
                    logger.error(f"Time observation failed: {e}")
                continue

        action = idle_behavior.get_idle_action()
        # Occasionally inject time-aware comments
        time_comment = idle_behavior.get_time_comment()
        if time_comment and random.random() < 0.15:
            action = time_comment
        if action:
            emotion_system.update()
            analyzed = analyze_text(action)
            try:
                # If it's purely an action (no spoken text after stripping), just send pose change
                # Voice ALL idle messages that have enough text
                if analyzed["tts_text"] and len(analyzed["tts_text"]) > 5:
                    audio = await loop.run_in_executor(
                        _tts_executor, lambda: tts.synthesize(analyzed["tts_text"])
                    )
                    await send_response(ws, analyzed["display_text"], audio,
                                        pose_hint=analyzed["pose_hint"])
                else:
                    # No TTS needed — just send text + pose change
                    msg = {
                        "type": "mario_response",
                        "text": analyzed["display_text"],
                        "has_audio": False,
                        "emotion": emotion_system.current,
                        "is_idle": True,
                    }
                    if analyzed["pose_hint"]:
                        msg["pose_hint"] = analyzed["pose_hint"]
                    await ws.send_json(msg)
            except asyncio.CancelledError:
                logger.info("Idle loop cancelled")
                return
            except Exception as e:
                logger.error(f"Idle loop error: {e}")
                await asyncio.sleep(10)  # Back off on error, don't kill idle permanently


async def handle_audio(ws: WebSocket, audio_bytes: bytes):
    """Process incoming audio from the client microphone."""
    if DEBUG_SERVER:
        logger.info(f"[DEBUG_SERVER] handle_audio: received {len(audio_bytes)} bytes")

    state_current["audio_buffer"].extend(audio_bytes)
    state_current["_last_buffer_time"] = time.time()

    CHUNK_SIZE = 96000
    MIN_PROCESS_SIZE = 16000  # Minimum buffer to process on timeout
    BUFFER_TIMEOUT = 5.0  # Process partial buffer after 5s
    # Prevent unbounded buffer growth (max 500KB)
    MAX_BUFFER = 500000
    if len(state_current["audio_buffer"]) > MAX_BUFFER:
        state_current["audio_buffer"] = state_current["audio_buffer"][-CHUNK_SIZE:]

    buf_len = len(state_current["audio_buffer"])
    buf_age = time.time() - state_current["_last_buffer_time"]

    # Process if we have a full chunk OR if buffer has been sitting for 5s with enough data
    if buf_len < CHUNK_SIZE:
        if buf_len < MIN_PROCESS_SIZE or buf_age < BUFFER_TIMEOUT:
            return

    process_size = min(buf_len, CHUNK_SIZE)
    audio_chunk = bytes(state_current["audio_buffer"][:process_size])
    state_current["audio_buffer"] = state_current["audio_buffer"][process_size:]
    state_current["_last_audio_chunk"] = audio_chunk  # Save for name registration

    state_current["_user_request_active"] = True
    try:
        await _process_audio(ws, audio_chunk)
    finally:
        # Keep guard active for 3s after response to prevent idle TTS during audio playback
        await asyncio.sleep(3.0)
        state_current["_user_request_active"] = False


async def _generate_and_send_response(ws: WebSocket, text: str, source: str = "audio", start_time: float = None):
    """Shared response pipeline for both audio and text input.

    Handles: safety check, emotion update, sentiment detection, special commands,
    LLM context building, response filtering, TTS synthesis with sentence streaming,
    conversation history, and memory saving.
    """
    if start_time is None:
        start_time = time.time()
    loop = asyncio.get_event_loop()

    # Safety check
    safety = check_input(text)
    if not safety["safe"]:
        logger.warning(f"[SAFETY] Unsafe input from {state_current.get('speaker_name', 'unknown')}: redirecting")
        redirect_audio = await loop.run_in_executor(_tts_executor, lambda: tts.synthesize(safety["redirect"]))
        await send_response(ws, safety["redirect"], redirect_audio)
        return

    # Emotion + idle reset
    emotion_system.update(event="speech_detected", transcript=text)
    idle_behavior.reset_timer()

    # Sentiment detection
    mood = detect_sentiment(text)
    if mood and mood != state_current.get("_detected_mood"):
        state_current["_detected_mood"] = mood
        logger.info(f"[SENTIMENT] Detected mood shift: {mood}")

    # Special commands
    response_text = await _handle_special_commands(text)
    if response_text is None:
        # Build LLM context
        memories = []
        if state_current["speaker_id"]:
            memories = memory.get_memories_for_context(state_current["speaker_id"])

        ctx = mario_prompt.build_context(
            speaker_name=state_current["speaker_name"],
            memories=memories,
        )
        ctx.append({"role": "system", "content": emotion_system.get_prompt_addition()})
        ctx.append({"role": "system", "content": party_stats.get_stats_for_prompt()})

        # Mood context
        detected_mood = state_current.get("_detected_mood")
        if detected_mood == "drunk":
            ctx.append({"role": "system", "content": "The person seems tipsy/drunk. Be extra funny, keep them safe, suggest water. Don't judge them — be supportive and playful."})
        elif detected_mood == "sad":
            ctx.append({"role": "system", "content": "The person seems sad or upset. Be extra kind and supportive. Cheer them up gently. You're their friend."})
        elif detected_mood == "angry":
            ctx.append({"role": "system", "content": "The person seems frustrated or angry. Be calm, empathetic, and try to lighten the mood gently. Don't escalate."})

        # Conversation history (12 messages = 6 exchanges) — validate each entry
        for msg in state_current["conversation_history"][-12:]:
            if isinstance(msg, dict) and "role" in msg and "content" in msg:
                ctx.append(msg)

        await send_thinking(ws, subtitle=text)
        response_text = await llm.generate_response(ctx, text)

    response_text = filter_response(response_text)
    analyzed = analyze_text(response_text)
    logger.info(f"Mario says: '{analyzed['tts_text']}' (pose={analyzed['pose_hint']})")

    # Trim BEFORE appending to stay within limit
    _hist_limit = GAME_CONFIG["conversation_history_limit"]
    _hist = state_current["conversation_history"]
    if len(_hist) >= _hist_limit - 1:
        state_current["conversation_history"] = _hist[-(_hist_limit - 2):]
    state_current["conversation_history"].append({"role": "user", "content": text})
    state_current["conversation_history"].append({"role": "assistant", "content": response_text})

    # Save to memory (conversations sync, facts/topics in background)
    if state_current["speaker_id"]:
        memory.save_conversation(state_current["speaker_id"], "user", text)
        memory.save_conversation(state_current["speaker_id"], "mario", response_text)
        _speaker_id = state_current["speaker_id"]
        async def _bg_extract():
            try:
                for fact in memory.extract_facts(text):
                    memory.save_fact(_speaker_id, fact)
                    logger.info(f"Learned fact: {fact}")
                topics = memory.extract_topics(text)
                if topics:
                    memory.save_topics(topics, _speaker_id)
            except Exception as e:
                logger.error(f"Background fact extraction failed: {e}")
        asyncio.create_task(_bg_extract())

    # TTS with sentence streaming
    voice_params = emotion_system.get_voice_params()
    game_sound = state_current.pop("_game_sound_hint", None)
    tts_text = analyzed["tts_text"]
    sentences = re.split(r'(?<=[.!?])\s+', tts_text, maxsplit=1)
    streamed = False

    if len(sentences) >= 2 and len(sentences[0]) >= 12 and len(sentences[1]) >= 10:
        try:
            first_audio = await loop.run_in_executor(
                _tts_executor, lambda: tts.synthesize(sentences[0], rate=voice_params.get("rate"), pitch=voice_params.get("pitch")))
            await send_response(ws, analyzed["display_text"], first_audio,
                sound=game_sound, emotion=emotion_system.current,
                pose_hint=analyzed["pose_hint"], response_time=time.time() - start_time)

            rest_audio = await loop.run_in_executor(
                _tts_executor, lambda: tts.synthesize(sentences[1], rate=voice_params.get("rate"), pitch=voice_params.get("pitch")))
            if rest_audio and len(rest_audio) > 44:
                await ws.send_bytes(rest_audio)
            streamed = True
        except Exception as e:
            logger.error(f"Streaming TTS failed, falling back: {e}")

    if not streamed:
        try:
            response_audio = await loop.run_in_executor(
                _tts_executor, lambda: tts.synthesize(tts_text, rate=voice_params.get("rate"), pitch=voice_params.get("pitch")))
        except Exception as e:
            logger.error(f"TTS failed: {e} — sending text only")
            response_audio = None
        await send_response(ws, analyzed["display_text"], response_audio,
            sound=game_sound, emotion=emotion_system.current,
            pose_hint=analyzed["pose_hint"], response_time=time.time() - start_time)

    # Track response time
    total_time = time.time() - start_time
    state_current["_response_times"].append(total_time)
    logger.info(f"⏱ {source} response time: {total_time:.1f}s")


async def _process_audio(ws: WebSocket, audio_chunk: bytes):
    """Inner audio processing — STT + speaker ID, then shared pipeline."""
    _response_start = time.time()
    loop = asyncio.get_event_loop()

    # STT + Speaker ID in parallel
    transcript_task = loop.run_in_executor(None, stt.transcribe, audio_chunk)
    speaker_task = loop.run_in_executor(None, speaker_id.identify_speaker, audio_chunk)
    try:
        transcript, speaker_info = await asyncio.wait_for(
            asyncio.gather(transcript_task, speaker_task), timeout=30.0)
    except asyncio.TimeoutError:
        logger.error("[DEBUG_SERVER] STT + speaker ID timed out after 30s")
        return

    if not transcript or transcript.strip() == "":
        if DEBUG_SERVER:
            logger.info("[DEBUG_SERVER] handle_audio: empty transcript (no speech detected in audio)")
        return
    if len(transcript.strip()) < 2:
        logger.info(f"[DEBUG_SERVER] handle_audio: transcript too short to process: '{transcript}'")
        return

    logger.info(f"Heard: '{transcript}' from {speaker_info.get('name', 'unknown')}")

    # Send thinking
    try:
        await ws.send_json({"type": "state", "thinking": True, "subtitle": transcript})
    except Exception:
        pass

    # Update speaker state
    if speaker_info and not speaker_info["is_new"]:
        state_current["speaker_name"] = speaker_info["name"]
        state_current["speaker_id"] = speaker_info["speaker_id"]
    elif speaker_info and speaker_info["is_new"] and state_current["speaker_name"] is None:
        pass

    await _generate_and_send_response(ws, transcript, source="audio", start_time=_response_start)


async def _handle_special_commands(transcript: str) -> str:
    """Handle special commands/requests in the transcript. Returns response text or None."""
    return command_handlers.handle_special_commands(
        transcript, state_current, GAME_CONFIG, emotion_system,
        idle_behavior, party_stats, memory
    )


async def handle_event(ws: WebSocket, event: dict):
    """Handle events from the client (presence, commands, etc.)."""
    event_type = event.get("type")

    # --- Input validation ---
    VALID_EVENT_TYPES = {
        "presence_enter", "presence_exit", "text_input",
        "set_name", "audio_level", "ping",
        "register_speaker", "vad_start", "vad_stop",
        "health_ping", "heartbeat",
    }
    if event_type not in VALID_EVENT_TYPES:
        logger.warning(f"[VALIDATION] Unknown event type: {event_type}")
        return
    # Validate text_input has text field
    if event_type == "text_input" and not isinstance(event.get("text"), str):
        logger.warning("[VALIDATION] text_input event missing 'text' string")
        return
    # Validate set_name has name field
    if event_type == "set_name" and not isinstance(event.get("name"), str):
        logger.warning("[VALIDATION] set_name event missing 'name' string")
        return

    if DEBUG_SERVER:
        logger.info(f"[DEBUG_SERVER] handle_event: {event_type}")

    if event_type == "presence_enter":
        if state_current["presence_phase"] not in ("IDLE", "FAREWELL"):
            logger.info(f"[STATE] Ignoring presence_enter during {state_current['presence_phase']}")
            return
        state_current["presence_phase"] = "GREETING"
        state_current["presence"] = True
        state_current["conversation_history"] = []
        state_current["enter_time"] = time.time()
        state_current["_greeting_in_progress"] = True
        emotion_system.update(event="presence_enter")
        idle_behavior.reset_timer()

        try:
            # Try to identify by audio
            if event.get("audio"):
                audio_data = base64.b64decode(event["audio"])
                info = speaker_id.identify_speaker(audio_data)
                if not info["is_new"]:
                    state_current["speaker_name"] = info["name"]
                    state_current["speaker_id"] = info["speaker_id"]
                    memory.record_visit(info["speaker_id"])

            # Record visit in party stats
            visit_id = party_stats.record_enter(
                person_id=state_current["speaker_id"],
                person_name=state_current["speaker_name"],
            )
            state_current["current_visit_id"] = visit_id
            party_stats.record_event("enter", state_current["speaker_name"])

            # Detect crew (groups of people who arrive together)
            crews = party_stats.detect_crew()
            crew_ctx = None
            if crews and state_current["speaker_name"]:
                for crew in crews:
                    if state_current["speaker_name"] in crew and len(crew) > 1:
                        crew_names = ", ".join(n for n in crew[:3] if n != state_current["speaker_name"])
                        if crew_names:
                            crew_ctx = f"This person arrived as part of a crew/group with: {crew_names}. Acknowledge their crew!"
                        break

            # Check for milestone visits
            stats = party_stats.get_stats()
            total = stats.get("total_visits", 0)
            event_type_greeting = "enter_unknown"

            if state_current["speaker_name"]:
                event_type_greeting = "enter_known"
                memories = memory.get_memories_for_context(state_current["speaker_id"])
                person_info = memory.get_person_info(state_current["speaker_id"])
                actual_visits = person_info["visit_count"] if person_info else 1
                last_emotion = memory.get_last_emotion(state_current["speaker_id"])
                ctx = mario_prompt.build_context(
                    speaker_name=state_current["speaker_name"],
                    memories=memories,
                    event="enter_known",
                    visit_count=actual_visits,
                    last_topic=memories[-1] if memories else "nothing special",
                    last_emotion=last_emotion,
                )
                # Visit-count-specific greeting hints
                if actual_visits == 1:
                    visit_hint = "This is their FIRST time meeting you! Be welcoming and ask their name."
                elif actual_visits <= 3:
                    visit_hint = f"They've visited {actual_visits} times. They're becoming a regular! Acknowledge this."
                elif actual_visits <= 10:
                    visit_hint = f"They've visited {actual_visits} times! They're a loyal fan! Reference past conversations."
                elif actual_visits <= 25:
                    visit_hint = f"They've visited {actual_visits} times! They're practically family! Give them a special nickname."
                else:
                    visit_hint = f"They've visited {actual_visits} times! They're a LEGEND! Treat them like royalty!"
                ctx.append({"role": "system", "content": visit_hint})
            elif total == 1:
                ctx = mario_prompt.build_context(event="first_visitor")
            elif total in (10, 25, 50, 100):
                ctx = mario_prompt.build_context(event="milestone_visit", count=total)
            else:
                ctx = mario_prompt.build_context(event="enter_unknown")

            ctx.append({"role": "system", "content": emotion_system.get_prompt_addition()})
            if crew_ctx:
                ctx.append({"role": "system", "content": crew_ctx})

            response_text = await asyncio.wait_for(llm.generate_response(ctx), timeout=30.0)
            response_text = filter_response(response_text)

            if not state_current["speaker_name"]:
                response_text += " What's-a your name, friend?"

            analyzed = analyze_text(response_text)
            loop = asyncio.get_event_loop()
            voice_params = emotion_system.get_voice_params()
            response_audio = await loop.run_in_executor(_tts_executor, lambda: tts.synthesize(
                analyzed["tts_text"], rate=voice_params.get("rate"), pitch=voice_params.get("pitch")))
            # Send with retry on failure
            for _attempt in range(2):
                try:
                    await send_response(ws, analyzed["display_text"], response_audio, sound="greeting",
                                        emotion=emotion_system.current, pose_hint=analyzed["pose_hint"] or "greeting/wave_high")
                    break
                except Exception as send_err:
                    if _attempt == 0:
                        logger.warning(f"[GREETING] Send failed, retrying: {send_err}")
                        await asyncio.sleep(0.5)
                    else:
                        logger.error(f"[GREETING] Send failed after retry: {send_err}")
        except Exception as e:
            logger.error(f"[DEBUG_SERVER] presence_enter greeting failed: {e}")
        finally:
            state_current["_greeting_in_progress"] = False
            state_current["presence_phase"] = "CONVERSING"

    elif event_type == "presence_exit":
        # Don't process exit while greeting is still being generated
        if state_current.get("_greeting_in_progress"):
            logger.warning("[DEBUG_SERVER] Ignoring presence_exit — greeting still in progress")
            return
        state_current["presence_phase"] = "FAREWELL"

        # Auto-cleanup active game if user leaves mid-game
        if state_current["_active_game"]:
            logger.info(f"[STATE] Cleaning up active game '{state_current['_active_game']}' on presence_exit")
            state_current["_active_game"] = None
        state_current["_game_state"] = {}  # Always clear to prevent stale state

        state_current["presence"] = False
        emotion_system.update(event="presence_exit")

        if state_current["current_visit_id"]:
            party_stats.record_exit(state_current["current_visit_id"])
        party_stats.record_event("exit", state_current["speaker_name"])

        try:
            if state_current["speaker_name"]:
                ctx = mario_prompt.build_context(
                    speaker_name=state_current["speaker_name"],
                    event="exit_known",
                )
            else:
                ctx = mario_prompt.build_context(event="exit_unknown")

            ctx.append({"role": "system", "content": emotion_system.get_prompt_addition()})

            response_text = await asyncio.wait_for(llm.generate_response(ctx), timeout=30.0)
            response_text = filter_response(response_text)

            # Always add hand wash reminder on exit
            wash_reminder = idle_behavior.get_hand_wash_reminder()
            response_text = f"{response_text} {wash_reminder}"

            analyzed = analyze_text(response_text)
            loop = asyncio.get_event_loop()
            voice_params = emotion_system.get_voice_params()
            response_audio = await loop.run_in_executor(_tts_executor, lambda: tts.synthesize(
                analyzed["tts_text"], rate=voice_params.get("rate"), pitch=voice_params.get("pitch")))
            await send_response(ws, analyzed["display_text"], response_audio, sound="goodbye",
                                emotion=emotion_system.current, pose_hint=analyzed["pose_hint"] or "greeting/farewell")
        except Exception as e:
            logger.error(f"[DEBUG_SERVER] presence_exit farewell failed: {e}")

        # Save emotion memory before exit
        if state_current["speaker_id"]:
            memory.save_emotion(state_current["speaker_id"], emotion_system.current)

        # Reset state
        state_current["speaker_name"] = None
        state_current["speaker_id"] = None
        state_current["conversation_history"] = []
        state_current["current_visit_id"] = None
        state_current["enter_time"] = None
        state_current["presence_phase"] = "IDLE"

    elif event_type == "register_speaker":
        name = event.get("name", "Friend")
        audio_data = event.get("audio")
        if audio_data:
            audio_bytes_data = base64.b64decode(audio_data)
            new_id = speaker_id.register_speaker(name, audio_bytes_data)
            memory.register_person(new_id, name)
            state_current["speaker_name"] = name
            state_current["speaker_id"] = new_id
            await ws.send_json({"type": "speaker_registered", "name": name, "id": new_id})

            # Mario celebrates registering a new friend
            celebrate = f"Wahoo! Nice to meet-a you, {name}! I'll-a remember your voice! Let's-a go!"
            loop = asyncio.get_event_loop()
            celebrate_audio = await loop.run_in_executor(_tts_executor, lambda: tts.synthesize(celebrate))
            await send_response(ws, celebrate, celebrate_audio, sound="oneup", emotion="excited")

    elif event_type == "vad_start":
        state_current["is_speaking"] = True
        await ws.send_json({"type": "state", "listening": True})

    elif event_type == "vad_stop":
        state_current["is_speaking"] = False
        await ws.send_json({"type": "state", "listening": False})

    elif event_type == "text_input":
        # Handle keyboard-typed text (same pipeline as audio, but skip STT)
        text = event.get("text", "").strip()
        if not text:
            return

        state_current["_user_request_active"] = True
        try:
            await _handle_text_input(ws, text)
        finally:
            state_current["_user_request_active"] = False

    elif event_type == "health_ping":
        # Respond to client health pings
        try:
            await ws.send_json({
                "type": "health_pong",
                "server_time": time.time(),
                "client_time": event.get("timestamp", 0),
                "emotion": emotion_system.current,
                "active_game": state_current["_active_game"],
            })
        except Exception:
            pass


async def _handle_text_input(ws: WebSocket, text: str):
    """Process text input — rate-limited, then delegates to shared pipeline."""
    now = time.time()
    if now - state_current["_last_text_input_time"] < 2.0:
        logger.warning(f"Text input rate-limited: '{text[:50]}'")
        return
    state_current["_last_text_input_time"] = now

    logger.info(f"Text input: '{text}'")

    try:
        await ws.send_json({"type": "state", "thinking": True, "subtitle": text})
    except Exception:
        pass

    await _generate_and_send_response(ws, text, source="text", start_time=now)


async def send_thinking(ws: WebSocket, subtitle: str = None):
    """Notify client that Mario is thinking (waiting for LLM)."""
    try:
        msg = {"type": "state", "thinking": True}
        if subtitle:
            msg["subtitle"] = subtitle
        await ws.send_json(msg)
    except Exception:
        pass


async def send_response(ws: WebSocket, text: str, audio: bytes = None,
                        sound: str = None, emotion: str = None,
                        pose_hint: str = None, response_time: float = None):
    """Send Mario's response (text + audio + metadata) to the client."""
    try:
        msg = {
            "type": "mario_response",
            "text": text,
            "has_audio": audio is not None and len(audio) > 0,
            "sound_effect": sound,
            "emotion": emotion or emotion_system.current,
            "animation": emotion_system.animation_state,
        }
        if pose_hint:
            msg["pose_hint"] = pose_hint
        if response_time is not None:
            msg["response_time"] = round(response_time, 1)

        await ws.send_json(msg)

        if audio and len(audio) > 0:
            await ws.send_bytes(audio)
    except Exception as e:
        logger.error(f"send_response failed: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=server_config.get("host", "0.0.0.0"),
        port=server_config.get("port", 8765),
    )
