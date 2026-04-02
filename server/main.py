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
import gc
import json
import logging
import os
import random
import re
import time
import threading
import httpx
import numpy as np
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, Response
from contextlib import asynccontextmanager
from collections import deque, OrderedDict
from concurrent.futures import ThreadPoolExecutor

import stt
import tts
import llm
import hardware
import speaker_id
import memory
import mario_prompt
from mario_prompt import PHASE_PROMPTS, _infer_guest_type, GUEST_TYPE_HINTS
import tts_router as tts_router_mod
from fish_speech_tts import FishSpeechTTS
from catchphrase_bank import CatchphraseBank
from tts_router import TTSEngine
from emotions import EmotionSystem, Emotion
from party_stats import PartyStats
from safety_filter import filter_response, check_input
from idle_behavior import IdleBehavior
from pose_analyzer import analyze_text
import command_handlers

# Semantic memory & VIP knowledge (optional — graceful fallback)
try:
    import memory_semantic
    import vip_knowledge
    _HAS_SEMANTIC = True
except ImportError:
    _HAS_SEMANTIC = False
    logger.warning("Semantic memory / VIP knowledge not available")
import audio_distress
from party_gossip import PartyGossip
from llm_router import LLMRouter, RoutingDecision
from night_progression import NightProgression, Phase
from dashboard import router as dashboard_router, init_dashboard
from hot_reload import LiveConfig
from watchdog import DegradationTier
from birthday_vip import BirthdayVIP
from sound_events import SoundEventManager
from catchphrase_mirror import CatchphraseMirror

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("mario-server")

# Server start time for uptime tracking
_SERVER_START_TIME = time.time()

# Current degradation tier (updated by health checks)
_degradation_tier = DegradationTier.FULL

# Error counter for health reporting
_error_count = 0

# Ollama health tracking
_ollama_healthy = True
_ollama_fail_count = 0
_OLLAMA_MAX_FAILS = 3

# TTS cache cap for memory leak prevention
TTS_CACHE_MAX = 2000

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

# Live config for hot-reloadable personality settings
LIVE_CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config_live.json")
live_config = LiveConfig(LIVE_CONFIG_PATH)
logger.info(f"Live config initialized at {LIVE_CONFIG_PATH}")

# Hardware auto-detection for performance tuning
hw_info = hardware.get_hardware()
_perf_tier = hardware.get_tier()

DEBUG_SERVER = os.environ.get("DEBUG_MODE", "").lower() == "true" or server_config.get("debug_server", True)
DEBUG_STREAM = server_config.get("debug_tts", True)
TTS_STREAMING_ENABLED = server_config.get("tts_streaming", True)

# Performance settings (auto-detected from hardware when set to "auto")
_PERF = {
    "tts_workers": hardware.resolve("tts_workers", server_config.get("tts_workers", "auto")),
    "tts_concurrency": hardware.resolve("tts_concurrency", server_config.get("tts_concurrency", "auto")),
    "max_background_tasks": hardware.resolve("max_background_tasks", server_config.get("max_background_tasks", "auto")),
    "conversation_history_limit": hardware.resolve("conversation_history_limit", server_config.get("conversation_history_limit", "auto")),
}
hardware.log_resolved_settings(_PERF)

# LLM Router — dual-model selection (fast vs quality)
_llm_quality_model = hardware.resolve("llm_quality_model", server_config.get("llm_quality_model", "auto"))
_llm_fast_model = hardware.resolve("llm_fast_model", server_config.get("llm_fast_model", "auto"))
llm_router = LLMRouter(fast_model=_llm_fast_model, quality_model=_llm_quality_model)
logger.info(f"[ROUTER] Dual-model router: fast={_llm_fast_model} quality={_llm_quality_model} tier={_perf_tier}")

# Game configuration from config.json (with defaults)
GAME_CONFIG = {
    "simon_max_rounds": server_config.get("game_max_rounds_simon", 5),
    "truth_dare_max_rounds": server_config.get("game_max_rounds_truth_dare", 5),
    "twenty_q_max_questions": server_config.get("game_max_questions_20q", 10),
    "riddle_max_attempts": server_config.get("game_max_attempts_riddle", 5),
    "word_chain_max_rounds": server_config.get("game_max_rounds_word_chain", 10),
    "rapid_fire_max_rounds": server_config.get("game_max_rounds_rapid_fire", 15),
    "conversation_history_limit": _PERF["conversation_history_limit"],
    "command_cooldown": server_config.get("command_cooldown_seconds", 1.0),
    "text_input_cooldown": server_config.get("text_input_cooldown_seconds", 2.0),
    "llm_timeout": server_config.get("llm_timeout_seconds", 30),
    "admin_api_key": server_config.get("admin_api_key", ""),
}

# Keyword → particle effect mapping for client-side visual reactions
KEYWORD_PARTICLES = {
    "fire": "fire", "flame": "fire", "hot": "fire", "burn": "fire",
    "star": "stars", "stars": "stars", "wahoo": "stars", "amazing": "stars", "awesome": "stars",
    "love": "hearts", "heart": "hearts", "cute": "hearts", "beautiful": "hearts",
    "party": "confetti", "celebrate": "confetti", "woohoo": "confetti", "birthday": "confetti",
    "sad": "rain", "cry": "rain", "crying": "rain",
    "jump": "sparkle", "hop": "sparkle", "bounce": "sparkle",
    "mushroom": "mushroom", "power": "mushroom", "1up": "mushroom",
    "coin": "coins", "money": "coins", "rich": "coins", "gold": "coins",
}

def _detect_particle_effect(text: str) -> str | None:
    """Detect keyword in text and return particle effect name."""
    import string
    words = set(w.strip(string.punctuation) for w in text.lower().split())
    for keyword, effect in KEYWORD_PARTICLES.items():
        if keyword in words:
            return effect
    return None

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


if not _validate_config(config):
    logger.warning("Config validation had warnings — check logs above")

# Systems
emotion_system = EmotionSystem()
party_stats = PartyStats()
idle_behavior = IdleBehavior()
party_gossip = PartyGossip()

# Night Progression — personality escalation across party phases
_party_start_cfg = server_config.get("party_start_time")
night_progression = NightProgression(
    start_time=_party_start_cfg if isinstance(_party_start_cfg, (int, float)) and _party_start_cfg > 0 else None
)
logger.info(f"Night progression initialized (start_time={night_progression.start_time:.0f})")

# Birthday VIP system — special treatment for the guest of honor
_birthday_name = server_config.get("birthday_person_name", "")
_birthday_facts = server_config.get("birthday_person_facts", [])
birthday_vip = BirthdayVIP(name=_birthday_name, birthday_facts=_birthday_facts)
if birthday_vip.is_configured():
    logger.info(f"Birthday VIP mode: '{_birthday_name}'")

# Sound event manager — Nintendo-style SFX
sound_events = SoundEventManager()

# Catchphrase mirroring — tracks repeated words per guest
catchphrase_mirror = CatchphraseMirror()

# Party metadata from config
_party_location = server_config.get("party_location", "the bathroom")
_party_theme = server_config.get("party_theme", "Birthday Party")
_expected_guests = server_config.get("expected_guest_count", 10)


def _inject_birthday_always_on(ctx: list) -> list:
    """Inject always-on birthday party context into any LLM context list."""
    if birthday_vip.is_configured():
        birthday_ctx = (
            f"IMPORTANT: Tonight is {birthday_vip.name}'s BIRTHDAY PARTY at {_party_location}! "
            f"Theme: {_party_theme}. Everything should celebrate them. "
            f"When someone new arrives, ask how they know {birthday_vip.name}. "
            f"Drop references to the birthday whenever natural."
        )
        ctx.append({"role": "system", "content": birthday_ctx})
    return ctx

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
    "_game_last_input_time": 0.0,  # Last valid game input — auto-timeout after 180s
    "_response_times": deque(maxlen=50),  # Track last 50 response times for metrics
    "_pending_announcement": None,  # Admin-queued announcement text
    "_detected_mood": None,  # Sentiment detection: drunk/sad/angry/None
    "_personality_mode": None,  # Personality mode: scary/dj/therapist/pirate/None
    "_last_dj_time": 0.0,  # Timestamp of last DJ announcement (set to now at connect)
    "_last_time_obs": 0.0,  # Timestamp of last time observation
    "_last_timing": {},  # Last response time breakdown (stt/llm/tts/total)
    "_session_topics": set(),  # Topics discussed in this session (for variety tracking)
    "_last_idle_action": None,  # What Mario was doing before someone entered
    "detected_guest": None,
    "guest_visits": 0,
    "memorial_active": False,
    "memorial_triggered_at": 0.0,
}

# Active WebSocket reference for admin endpoints to broadcast to
_active_ws: "WebSocket | None" = None

# Dedicated executor for TTS (scaled by hardware auto-detection)
_tts_executor = ThreadPoolExecutor(max_workers=_PERF["tts_workers"], thread_name_prefix="tts")

# Distress tracker (initialized in startup, declared here for module scope)
_distress_tracker: "audio_distress.DistressTracker | None" = None

# Face memory for webcam guest identification
_face_memory = None
try:
    from server.face_memory import FaceMemory
    _face_db_path = os.path.join(os.path.dirname(__file__), "data", "memory.db")
    _face_memory = FaceMemory(_face_db_path)
    logger.info("[INIT] Face memory initialized")
except Exception as e:
    logger.warning(f"[INIT] Face memory unavailable: {e}")

# Background task limiter (prevents unbounded memory growth from fact extraction)
_bg_tasks: set = set()
MAX_BG_TASKS = _PERF["max_background_tasks"]

# Idle loop error backoff counter
_idle_error_count = 0


async def _llm_keepalive():
    """Ping Ollama every 4 min to prevent model unloading from VRAM."""
    global _ollama_healthy, _ollama_fail_count
    while True:
        try:
            await asyncio.sleep(240)
            async with httpx.AsyncClient() as client:
                await client.post(
                    "http://localhost:11434/api/chat",
                    json={"model": llm.MODEL_NAME, "messages": [{"role": "user", "content": "hi"}],
                          "stream": False, "keep_alive": "60m", "options": {"num_predict": 1}},
                    timeout=15.0
                )
            _ollama_healthy = True
            _ollama_fail_count = 0
        except asyncio.CancelledError:
            return
        except Exception as e:
            logger.debug(f"Keepalive ping failed: {e}")
            _ollama_fail_count += 1
            if _ollama_fail_count >= _OLLAMA_MAX_FAILS:
                _ollama_healthy = False
                logger.error(f"[HEALTH] Ollama appears down after {_ollama_fail_count} failed pings")


async def _memory_maintenance_loop():
    """Periodic memory leak prevention: gc.collect, WAL checkpoint, TTS cache LRU eviction."""
    _gc_interval = 600       # 10 minutes
    _wal_interval = 1800     # 30 minutes
    _last_gc = time.time()
    _last_wal = time.time()

    while True:
        try:
            await asyncio.sleep(60)  # Check every minute
            now = time.time()

            # gc.collect every 10 minutes
            if now - _last_gc >= _gc_interval:
                collected = gc.collect()
                try:
                    rss = _get_rss_mb()
                except Exception as e:
                    logger.debug(f"Memory maintenance failed: {e}")  # Was: pass
                    rss = 0
                logger.info("[MEMORY] gc.collect() freed %d objects, RSS=%.0fMB", collected, rss)
                _last_gc = now

            # SQLite WAL checkpoint every 30 minutes
            if now - _last_wal >= _wal_interval:
                try:
                    import sqlite3
                    db_path = party_stats._db_path()
                    with sqlite3.connect(db_path) as conn:
                        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                    logger.info("[MEMORY] SQLite WAL checkpoint completed")
                except Exception as e:
                    logger.warning("[MEMORY] WAL checkpoint failed: %s", e)
                _last_wal = now

            # TTS cache LRU eviction when over cap
            try:
                cache = tts._audio_cache
                if len(cache) > TTS_CACHE_MAX:
                    excess = len(cache) - TTS_CACHE_MAX
                    # Evict oldest entries (dict preserves insertion order in Python 3.7+)
                    keys_to_evict = list(cache.keys())[:excess]
                    for k in keys_to_evict:
                        cache.pop(k, None)
                    logger.info("[MEMORY] Evicted %d TTS cache entries (was %d, cap %d)",
                                excess, excess + len(cache), TTS_CACHE_MAX)
            except Exception as e:
                logger.warning("[MEMORY] TTS cache eviction failed: %s", e)

        except asyncio.CancelledError:
            return
        except Exception as e:
            logger.warning("[MEMORY] Maintenance loop error: %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize all AI models on startup."""
    logger.info("=== Mario AI Server Starting ===")

    logger.info("Loading speech-to-text model...")
    _stt_model = server_config.get("stt_model_size", "base")
    if _stt_model == "auto":
        # Auto-detect: use larger model on powerful hardware
        _tier = hardware.get_tier()
        _stt_model = {"ultra": "large-v3", "high": "medium", "medium": "base", "low": "base"}.get(_tier, "base")
        logger.info(f"[HARDWARE] STT model auto-selected: {_stt_model} (tier={_tier})")
    stt.init_model(
        model_size=_stt_model,
        device=server_config.get("stt_device", "auto"),
    )

    logger.info("Loading TTS engine...")
    if server_config.get("tts_voice"):
        tts.EDGE_VOICE = server_config["tts_voice"]
    if server_config.get("tts_rate"):
        tts.RATE = server_config["tts_rate"]
    tts.init_tts()

    # Initialize TTS Router with fallback chain
    logger.info("Initializing TTS Router with fallback chain...")
    _tts_router = tts_router_mod.init_router(
        max_parallel=_PERF.get("tts_concurrency", 8) if isinstance(_PERF.get("tts_concurrency"), int) else 8,
        user_priority_event=getattr(tts, '_user_tts_waiting', None),
    )

    # Priority 0: Catchphrase bank (instant, pre-recorded)
    catchphrase_bank = CatchphraseBank(
        assets_dir=os.path.join(os.path.dirname(__file__), "assets", "catchphrases")
    )
    if catchphrase_bank.is_available():
        _tts_router.register(TTSEngine(
            name="catchphrase",
            synthesize_fn=lambda text, **kw: catchphrase_bank.match(text),
            is_available_fn=catchphrase_bank.is_available,
            priority=0,
        ))
        logger.info(f"  ✓ Catchphrase bank: {len(catchphrase_bank.loaded_phrases())} phrases loaded")
    else:
        logger.info("  ○ Catchphrase bank: no WAV files found (skipped)")

    # Priority 1: Fish Speech (voice cloning)
    _ref_audio_path = os.path.join(os.path.dirname(__file__), "data", "mario_reference_sentences.wav")
    fish_speech = FishSpeechTTS(reference_audio=_ref_audio_path)
    if fish_speech.is_available():
        _tts_router.register(TTSEngine(
            name="fish_speech",
            synthesize_fn=fish_speech.synthesize_sync,
            is_available_fn=fish_speech.is_available,
            priority=1,
        ))
        logger.info("  ✓ Fish Speech: loaded and available")
    else:
        logger.info("  ○ Fish Speech: not available (package not installed or model load failed)")

    # Priority 2: Edge TTS + RVC (existing pipeline)
    _tts_router.register(tts.register_as_engine())
    logger.info("  ✓ Edge TTS + RVC: registered as fallback engine")

    # Priority 3: XTTS v2 (if model is loaded in tts module)
    def _xtts_synthesize(text, **kw):
        """Use XTTS v2 via tts.py internal path."""
        if hasattr(tts, 'xtts_model') and tts.xtts_model is not None:
            return tts._original_synthesize(text, **kw)
        return None

    def _xtts_available():
        return hasattr(tts, 'xtts_model') and tts.xtts_model is not None

    _tts_router.register(TTSEngine(
        name="xtts", synthesize_fn=_xtts_synthesize,
        is_available_fn=_xtts_available, priority=3,
    ))
    logger.info(f"  {'✓' if _xtts_available() else '○'} XTTS v2: {'available' if _xtts_available() else 'model not loaded (will activate if loaded later)'}")

    # Priority 4: Pre-recorded generic fallback clips (absolute last resort)
    _fallback_clips_dir = os.path.join(os.path.dirname(__file__), "assets", "fallback_clips")
    _cached_fallback_clips: list[bytes] = []
    try:
        if os.path.isdir(_fallback_clips_dir):
            for fname in os.listdir(_fallback_clips_dir):
                if fname.endswith('.wav'):
                    clip_path = os.path.join(_fallback_clips_dir, fname)
                    with open(clip_path, 'rb') as f:
                        _cached_fallback_clips.append(f.read())
    except OSError as e:
        logger.warning(f"Failed to load fallback clips: {e}")

    def _prerecorded_synthesize(text, **kw):
        """Return a random pre-recorded Mario clip as absolute last resort."""
        import random as _rand
        if not _cached_fallback_clips:
            return None
        return _rand.choice(_cached_fallback_clips)

    def _prerecorded_available():
        return len(_cached_fallback_clips) > 0

    _tts_router.register(TTSEngine(
        name="pre_recorded", synthesize_fn=_prerecorded_synthesize,
        is_available_fn=_prerecorded_available, priority=4,
    ))
    logger.info(f"  {'✓' if _prerecorded_available() else '○'} Pre-recorded fallback: {'available' if _prerecorded_available() else 'no clips in assets/fallback_clips/'}")

    # Monkey-patch tts.synthesize and tts.synthesize_user to route through the router.
    # This ensures all 25+ call sites in main.py automatically use the fallback chain
    # without modifying each call site individually.
    tts._original_synthesize = tts.synthesize
    tts._original_synthesize_user = tts.synthesize_user
    tts.synthesize = _tts_router.synthesize
    tts.synthesize_user = _tts_router.synthesize_user
    logger.info("TTS Router active — fallback chain: " + " → ".join(
        e.name for e in _tts_router.get_fallback_chain()
    ))

    logger.info("Loading speaker identification...")
    speaker_id.init_speaker_id()

    logger.info("Loading audio distress detector...")
    try:
        audio_distress.init_detector(device="cpu")
        logger.info(f"Audio distress detector: {'ready' if audio_distress.is_available() else 'FAILED'}")
    except Exception as e:
        logger.warning(f"Audio distress detector unavailable: {e} — text detection still active")

    # Stateful tracker for volume-spike + temporal-coherence gating
    global _distress_tracker
    _distress_tracker = audio_distress.DistressTracker()
    logger.info("Audio distress tracker initialized (volume spike + temporal coherence)")

    logger.info("Initializing memory system...")
    memory.init_memory()

    # Initialize semantic memory (Qdrant) and VIP knowledge
    if _HAS_SEMANTIC:
        try:
            memory_semantic.init_semantic_memory()
            logger.info("Semantic memory (Qdrant) initialized")
            vip_knowledge.load_all_vip_profiles()
            logger.info("VIP profiles loaded into semantic memory")
            # Backfill existing SQLite memories into Qdrant (first run only)
            memory_semantic.backfill_from_sqlite()
        except Exception as e:
            logger.error(f"Semantic memory init failed (non-fatal): {e}")

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

    # Start LLM keepalive to prevent Ollama from unloading model from VRAM
    _keepalive_task = asyncio.create_task(_llm_keepalive())
    logger.info("Started LLM keepalive ping (every 4min, keep_alive=60m)")

    # Memory leak prevention tasks
    _memory_task = asyncio.create_task(_memory_maintenance_loop())
    logger.info("Started memory maintenance loop (gc every 10min, WAL every 30min, cache cap=%d)", TTS_CACHE_MAX)

    logger.info("=== Mario AI Server Ready! Let's-a go! ===")
    yield
    _keepalive_task.cancel()
    _memory_task.cancel()
    logger.info("=== Mario AI Server Shutting Down ===")
    _tts_executor.shutdown(wait=False)
    if tts._edge_executor:
        tts._edge_executor.shutdown(wait=False)
    logger.info("=== Server shutdown complete ===")


app = FastAPI(title="Mario AI Server", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Mount dashboard routes
app.include_router(dashboard_router)
init_dashboard(health_fn=None, server_start_time=_SERVER_START_TIME, live_config=live_config)  # health_fn wired below


def _get_rss_mb() -> float:
    """Get current process RSS in MB."""
    try:
        import psutil
        return psutil.Process().memory_info().rss / (1024 * 1024)
    except Exception:
        pass
    try:
        # Fallback for Windows without psutil
        import ctypes
        import ctypes.wintypes
        class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
            _fields_ = [("cb", ctypes.wintypes.DWORD),
                        ("PageFaultCount", ctypes.wintypes.DWORD),
                        ("PeakWorkingSetSize", ctypes.c_size_t),
                        ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t),
                        ("PeakPagefileUsage", ctypes.c_size_t)]
        pmc = PROCESS_MEMORY_COUNTERS()
        pmc.cb = ctypes.sizeof(pmc)
        handle = ctypes.windll.kernel32.GetCurrentProcess()
        ctypes.windll.psapi.GetProcessMemoryInfo(handle, ctypes.byref(pmc), pmc.cb)
        return pmc.WorkingSetSize / (1024 * 1024)
    except Exception:
        return 0.0


def _get_gpu_temp() -> float:
    """Get GPU temperature in °C (best-effort)."""
    try:
        import subprocess
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        return float(result.stdout.strip().split("\n")[0])
    except Exception:
        return 0.0


def _get_component_status(component: str) -> str:
    """Determine component health status: ok / slow / failed."""
    try:
        if component == "llm":
            resp_times = state_current.get("_response_times", deque())
            if not resp_times:
                return "ok"
            avg_ms = (sum(resp_times) / len(resp_times)) * 1000
            if avg_ms > 15000:
                return "slow"
            return "ok"
        elif component == "tts":
            if hasattr(tts, '_precache_done') and not tts._precache_done.is_set() and tts._precache_active:
                return "ok"  # Still warming up
            return "ok"
        elif component == "stt":
            return "ok"
    except Exception:
        return "failed"
    return "ok"


@app.get("/health")
async def health():
    global _degradation_tier
    stats = party_stats.get_stats()
    total_cache_requests = tts._cache_hits + tts._cache_misses
    cache_hit_rate = (tts._cache_hits / max(1, total_cache_requests)) * 100
    resp_times = state_current.get("_response_times", [])
    avg_response = sum(resp_times) / max(1, len(resp_times)) if resp_times else 0
    avg_response_ms = avg_response * 1000

    llm_status = _get_component_status("llm")
    tts_status = _get_component_status("tts")
    stt_status = _get_component_status("stt")

    # Determine degradation tier from component statuses
    if tts_status == "failed" or stt_status == "failed":
        _degradation_tier = DegradationTier.MINIMAL
    elif llm_status == "slow" or tts_status == "slow":
        _degradation_tier = DegradationTier.DEGRADED
    else:
        _degradation_tier = DegradationTier.FULL

    uptime = time.time() - _SERVER_START_TIME
    try:
        hours = night_progression.get_hours_elapsed()
        phase = night_progression.get_time_phase(hours)
    except Exception:
        phase = "unknown"

    return {
        "status": "ok",
        "uptime_seconds": round(uptime),
        "llm": llm_status,
        "tts": tts_status,
        "stt": stt_status,
        "memory_mb": round(_get_rss_mb()),
        "gpu_temp_c": round(_get_gpu_temp()),
        "guests_served": stats.get("total_visits", 0),
        "current_phase": phase.name if hasattr(phase, 'name') else str(phase),
        "degradation_tier": _degradation_tier.name,
        "active_games": 1 if state_current.get("_active_game") else 0,
        "tts_cache_size": len(tts._audio_cache),
        "avg_response_time_ms": round(avg_response_ms),
        "error_count": _error_count,
        # Legacy fields preserved for backward compatibility
        "message": "It's-a me, Mario!",
        "emotion": emotion_system.current,
        "emotion_intensity": emotion_system.intensity,
        "total_visits": stats["total_visits"],
        "unique_visitors": stats["unique_visitors"],
        "party_duration": stats["party_duration"],
        "current_hour": stats["current_hour"],
        "tts_cache_hits": tts._cache_hits,
        "tts_cache_misses": tts._cache_misses,
        "tts_cache_hit_rate": f"{cache_hit_rate:.0f}%",
        "avg_response_time": f"{avg_response:.1f}s",
        "total_responses": len(resp_times),
        "precache_done": tts._precache_done.is_set(),
        "precache_active": tts._precache_active,
        "conversation_length": len(state_current["conversation_history"]),
        "user_active": state_current["_user_request_active"],
        "active_game": state_current["_active_game"],
        "llm_model": llm.MODEL_NAME,
        "last_timing": state_current.get("_last_timing", {}),
        "gossip_entries": party_gossip.get_gossip_count(),
        "gossip_guests": party_gossip.get_guest_count(),
        "hardware": hardware.get_hardware(),
        "performance_tier": hardware.get_tier(),
        "perf_settings": _PERF,
        "llm_router_stats": llm_router.stats,
        "llm_fast_model": llm_router._fast_model,
        "llm_quality_model": llm_router._quality_model,
        "semantic_memory": memory._HAS_SEMANTIC,
    }

    # Periodic Qdrant recovery check (piggyback on health polls)
    memory.check_semantic_health()

# Wire the health function into the dashboard router after definition
from dashboard import init_dashboard as _rewire_dashboard
_rewire_dashboard(health_fn=health, server_start_time=_SERVER_START_TIME, live_config=live_config)


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
_SICK_WORDS = {"vomit", "puke", "puking", "puked", "nauseous", "nausea", "barf", "barfing", "barfed", "retching", "gagging", "hurling", "hurled", "queasy"}
_SICK_PHRASES = ["throwing up", "throw up", "threw up", "going to be sick", "gonna be sick", "about to puke", "feel sick", "feeling sick", "getting sick"]


def detect_sentiment(text: str) -> str | None:
    """Detect if user is drunk/sad/angry/sick from their text. Returns mood or None."""
    words = set(text.lower().split())
    lower = text.lower()
    # Sick/vomit detection (check first — takes priority if someone is actually ill)
    if words & _SICK_WORDS or any(p in lower for p in _SICK_PHRASES):
        return "sick"
    # Onomatopoeia for vomiting sounds
    if re.search(r'(bleh+|blarg+|blegh+|hurk+|ugggh+|blargh+)', lower):
        return "sick"
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
    resp_times = state_current.get("_response_times", [])
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
    """Return enhanced party leaderboard data with categories and fun stats."""
    stats = party_stats.get_stats()
    people = party_stats.get_all_visitors()

    # Game champion — guest with most game events
    game_champion = None
    game_score = 0
    try:
        import sqlite3
        with sqlite3.connect(party_stats._db_path()) as conn:
            row = conn.execute("""
                SELECT details, COUNT(*) as cnt FROM party_events
                WHERE event_type = 'game_complete'
                GROUP BY details ORDER BY cnt DESC LIMIT 1
            """).fetchone()
            if row:
                game_champion = row[0]
                game_score = row[1]
    except Exception:
        pass

    # Funniest moment — longest gossip entry per guest
    funniest_name = None
    funniest_text = None
    if party_gossip._gossip_log:
        longest_entry = max(party_gossip._gossip_log, key=lambda g: len(g.get("text", "")))
        funniest_name = longest_entry.get("speaker_name")
        funniest_text = longest_entry.get("text", "")[:80]

    # Most dramatic — guest with most emotion-triggering gossip entries
    dramatic_name = None
    dramatic_count = 0
    if party_gossip._gossip_log:
        from collections import Counter
        speaker_counts = Counter(g["speaker_id"] for g in party_gossip._gossip_log
                                 if g.get("type") in ("reaction", "opinion", "embarrassing", "fear"))
        if speaker_counts:
            top_id, dramatic_count = speaker_counts.most_common(1)[0]
            for g in party_gossip._gossip_log:
                if g["speaker_id"] == top_id:
                    dramatic_name = g["speaker_name"]
                    break

    # Most chatty — most gossip entries overall
    chatty_name = None
    if party_gossip._gossip_log:
        from collections import Counter
        chatty_counts = Counter(g["speaker_name"] for g in party_gossip._gossip_log)
        if chatty_counts:
            chatty_name = chatty_counts.most_common(1)[0][0]

    # Party duration breakdown
    party_duration_secs = time.time() - party_stats.party_start_time
    duration_hours = int(party_duration_secs // 3600)
    duration_minutes = int((party_duration_secs % 3600) // 60)

    # Guest titles from gossip system
    guest_titles = {}
    for visitor in people[:10]:
        name = visitor.get("name", "")
        for gid, title in party_gossip._guest_titles.items():
            for g in party_gossip._gossip_log:
                if g.get("speaker_id") == gid and g.get("speaker_name") == name:
                    guest_titles[name] = title
                    break

    # Fun ticker stats
    ticker_stats = []
    if stats.get("avg_duration_seconds", 0) > 0:
        ticker_stats.append(f"Average visit: {int(stats['avg_duration_seconds'])}s")
    if len(people) > 0:
        ticker_stats.append(f"{len(people)} unique guests tonight!")
    gossip_count = party_gossip.get_gossip_count()
    if gossip_count > 0:
        ticker_stats.append(f"{gossip_count} gossip-worthy moments collected!")
    if party_gossip._rivalries:
        ticker_stats.append(f"{len(party_gossip._rivalries)} rivalries brewing!")
    if party_gossip._dramatic_moments:
        ticker_stats.append(f"{len(party_gossip._dramatic_moments)} dramatic moments tonight!")
    if stats.get("total_visits", 0) >= 10:
        rate = stats["total_visits"] / max(1, party_duration_secs / 3600)
        ticker_stats.append(f"Traffic: {rate:.1f} visits/hour!")

    # Game leaderboard from memory module
    game_leaderboard = []
    try:
        game_leaderboard = memory_module.get_game_leaderboard(limit=10)
    except Exception:
        pass

    return {
        "total_visits": stats.get("total_visits", 0),
        "unique_visitors": stats.get("unique_visitors", 0),
        "party_duration": {"hours": duration_hours, "minutes": duration_minutes},
        "most_visits": {
            "name": stats.get("most_frequent_name"),
            "count": stats.get("most_frequent_count", 0),
        },
        "longest_stay": {
            "name": stats.get("longest_visit_name"),
            "seconds": stats.get("longest_visit_seconds", 0),
            "minutes": round(stats.get("longest_visit_seconds", 0) / 60, 1),
        },
        "game_champion": {
            "name": game_champion,
            "score": game_score,
        },
        "game_leaderboard": game_leaderboard,
        "most_chatty": chatty_name,
        "funniest_moment": {
            "name": funniest_name,
            "text": funniest_text,
        },
        "most_dramatic": {
            "name": dramatic_name,
            "count": dramatic_count,
        },
        "visitors": people[:10],
        "guest_titles": guest_titles,
        "ticker_stats": ticker_stats,
        "current_emotion": emotion_system.current,
        "current_time": datetime.now().strftime("%I:%M %p"),
    }


# --- Admin Endpoints ---
@app.post("/admin/reset")
async def admin_reset(request_body: dict = {}):
    """Admin: Reset party stats. Requires admin_api_key if configured."""
    api_key = GAME_CONFIG.get("admin_api_key")
    if api_key is not None and api_key != "":
        if request_body.get("api_key") != api_key:
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


@app.post("/admin/trigger_memorial")
async def trigger_memorial(request_body: dict = {}):
    """Manually trigger the Lisa Webb memorial moment."""
    global state_current, _active_ws
    api_key = GAME_CONFIG.get("admin_api_key", "")
    if api_key and request_body.get("api_key") != api_key:
        return {"status": "error", "message": "Invalid API key"}
    if _active_ws is None:
        return {"status": "error", "message": "No client connected"}
    try:
        state_current["memorial_active"] = True
        state_current["memorial_triggered_at"] = time.time()

        memorial_text = (
            "Everyone... I need a moment of your time. "
            "One of the most important people in Jacob's life was his Aunt Lisa Webb. "
            "She passed away too soon, and we want to honor her memory tonight. "
            "Let's take a moment of silence for Aunt Lisa."
        )

        memorial_event = {
            "type": "memorial_event",
            "name": "Lisa Webb",
            "phase": "silence",
            "text": memorial_text,
            "duration": 15,
        }
        await _active_ws.send_json(memorial_event)

        # Synthesize and send the initial memorial speech
        loop = asyncio.get_event_loop()
        try:
            audio = await loop.run_in_executor(
                _tts_executor, lambda: tts.synthesize_user(memorial_text))
            if audio:
                await _active_ws.send_bytes(audio)
        except Exception as e:
            logger.error(f"Memorial initial TTS failed: {e}")

        # Schedule the "raise a glass" follow-up after 15 seconds
        captured_ws = _active_ws  # Capture current connection

        async def memorial_followup():
            await asyncio.sleep(15)
            # Check the connection is still the same one
            if _active_ws is not captured_ws or captured_ws is None:
                logger.info("[MEMORIAL] Client changed during memorial, skipping toast")
                state_current["memorial_active"] = False
                return
            followup_text = "Now let's raise a glass to Aunt Lisa! Take a shot in her honor!"
            followup_event = {
                "type": "memorial_event",
                "name": "Lisa Webb",
                "phase": "toast",
                "text": followup_text,
            }
            try:
                await captured_ws.send_json(followup_event)
            except Exception:
                pass

            try:
                followup_loop = asyncio.get_event_loop()
                followup_audio = await followup_loop.run_in_executor(
                    _tts_executor, lambda: tts.synthesize_user(followup_text))
                if followup_audio:
                    await captured_ws.send_bytes(followup_audio)
            except Exception as e:
                logger.error(f"Memorial followup TTS failed: {e}")

            state_current["memorial_active"] = False

        asyncio.create_task(memorial_followup())

        return {"status": "ok", "message": "Memorial triggered"}
    except Exception as e:
        logger.error(f"Memorial trigger failed: {e}")
        return {"status": "error", "message": str(e)}


_tts_semaphore = asyncio.Semaphore(_PERF["tts_concurrency"])

@app.get("/tts")
async def tts_endpoint(text: str = "", nocache: bool = False):
    """Generate TTS audio for a given text and return WAV file."""
    if not text or len(text) > 300:
        return {"status": "error", "message": "Text required (max 300 chars)"}
    # Fast path: check in-memory cache without executor/semaphore overhead
    if not nocache:
        cached = tts.get_cached(text)
        if cached:
            return Response(content=cached, media_type="audio/wav",
                           headers={"Content-Disposition": "attachment; filename=mario_tts.wav"})
    async with _tts_semaphore:
        loop = asyncio.get_event_loop()
        try:
            audio_bytes = await loop.run_in_executor(
                _tts_executor, lambda: tts.synthesize_user(text, nocache=nocache)
            )
            if not audio_bytes:
                return {"status": "error", "message": "TTS synthesis failed"}
            return Response(content=audio_bytes, media_type="audio/wav",
                           headers={"Content-Disposition": "attachment; filename=mario_tts.wav"})
        except Exception as e:
            logger.error(f"TTS endpoint error: {e}")
            return {"status": "error", "message": str(e)}


@app.get("/chat")
async def chat_page():
    """Serve the Mario Party Chat HTML page."""
    chat_file = os.path.join(os.path.dirname(__file__), "..", "web", "mario_chat.html")
    if os.path.exists(chat_file):
        return FileResponse(chat_file, media_type="text/html")
    return HTMLResponse("<h1>mario_chat.html not found</h1>", status_code=404)


@app.get("/tts_test")
async def tts_test_page():
    """Serve the TTS test suite HTML page."""
    test_page = os.path.join(os.path.dirname(__file__), "..", "web", "tts_test.html")
    if os.path.exists(test_page):
        return FileResponse(test_page, media_type="text/html")
    return HTMLResponse("<h1>tts_test.html not found</h1>", status_code=404)


@app.get("/tts_cache_preview")
async def tts_cache_preview_page():
    """Serve the TTS cache preview HTML page."""
    preview_page = os.path.join(os.path.dirname(__file__), "..", "web", "tts_cache_preview.html")
    if os.path.exists(preview_page):
        return FileResponse(preview_page, media_type="text/html")
    return HTMLResponse("<h1>tts_cache_preview.html not found</h1>", status_code=404)


@app.get("/leaderboard_page")
async def leaderboard_page():
    """Serve the party leaderboard HTML page (for TV/second screen display)."""
    page = os.path.join(os.path.dirname(__file__), "..", "web", "leaderboard.html")
    if os.path.exists(page):
        return FileResponse(page, media_type="text/html")
    return HTMLResponse("<h1>leaderboard.html not found</h1>", status_code=404)


@app.get("/perfect_cache_results.json")
async def perfect_cache_results():
    """Serve the perfect cache results JSON file."""
    results_path = os.path.join(os.path.dirname(__file__), "..", "perfect_cache_results.json")
    if os.path.exists(results_path):
        return FileResponse(results_path, media_type="application/json")
    return HTMLResponse("{}", status_code=404)


@app.get("/pause_idle")
async def pause_idle(pause: bool = True):
    """Pause or resume idle precache. Use during TTS testing to prevent OOM."""
    if pause:
        tts._idle_precache_paused.set()
        return {"status": "ok", "idle_precache": "paused"}
    else:
        tts._idle_precache_paused.clear()
        return {"status": "ok", "idle_precache": "resumed"}


@app.get("/restart_sovits")
async def restart_sovits():
    """Restart the GPT-SoVITS subprocess to free GPU memory."""
    try:
        tts._restart_sovits_subprocess()
        return {"status": "ok", "msg": "GPT-SoVITS subprocess restarted"}
    except Exception as e:
        return {"status": "error", "msg": str(e)}


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    global _active_ws
    await ws.accept()
    _active_ws = ws
    logger.info("Client connected!")

    # Reset per-connection state (games, conversation, etc.)
    state_current["_active_game"] = None
    state_current["_game_state"] = {}
    state_current["conversation_history"] = []
    state_current["_detected_mood"] = None
    state_current["_sick_checkin_time"] = 0.0  # Track last sick follow-up
    state_current["_last_user_msg_time"] = 0.0  # Track silence for sick check-ins
    state_current["_name_from_parsing"] = False  # Reset name parsing flag
    state_current["presence_phase"] = "IDLE"
    state_current["_last_dj_time"] = time.time()  # Prevent immediate DJ announcement
    state_current["audio_buffer"] = bytearray()  # Clear stale audio from previous connection
    state_current["_last_buffer_time"] = 0.0

    # Send initial greeting (with 30s timeout to prevent blocking)
    loop = asyncio.get_event_loop()
    try:
        greeting_ctx = mario_prompt.build_context(event="startup", phase_modifier=_get_night_phase_modifier())
        _inject_birthday_always_on(greeting_ctx)
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
            await send_response(ws, "It's-a me, Mario! Wahoo!", None, sound="greeting",
                                pose_hint="positive/excited_jump")
    except Exception as e:
        logger.error(f"Startup greeting failed: {e}")
        try:
            fallback_audio = await loop.run_in_executor(_tts_executor, lambda: tts.synthesize("Wahoo!"))
            await send_response(ws, "It's-a me, Mario! Wahoo!", fallback_audio, sound="greeting",
                                pose_hint="positive/excited_jump")
        except Exception:
            await send_response(ws, "It's-a me, Mario! Wahoo!", None, sound="greeting",
                                pose_hint="positive/excited_jump")

    # Start idle behavior loop
    idle_task = asyncio.create_task(_idle_loop(ws))
    heartbeat_task = asyncio.create_task(_heartbeat_loop(ws))
    emotion_decay_task = asyncio.create_task(_emotion_decay_loop())
    leaderboard_task = asyncio.create_task(_leaderboard_broadcast_loop(ws))

    # Message rate limiting (flood protection)
    _msg_timestamps = deque(maxlen=50)  # Track last 50 message times
    _WS_MAX_MSGS_PER_SEC = 30  # Max 30 messages/sec (generous for audio)

    try:
        while True:
            data = await ws.receive()

            # Rate limit: drop messages if flooding
            now = time.time()
            _msg_timestamps.append(now)
            if len(_msg_timestamps) >= 50:
                window = now - _msg_timestamps[0]
                if window > 0 and len(_msg_timestamps) / window > _WS_MAX_MSGS_PER_SEC:
                    continue  # Silently drop flood messages

            if "bytes" in data and data["bytes"]:
                audio_bytes = data["bytes"]
                if len(audio_bytes) > 5 * 1024 * 1024:  # 5MB max audio
                    logger.warning(f"[VALIDATION] Audio too large: {len(audio_bytes)} bytes")
                    continue
                try:
                    await handle_audio(ws, audio_bytes)
                except Exception as e:
                    logger.error(f"handle_audio error: {e}")
            elif "text" in data and data["text"]:
                text_data = data["text"]
                if len(text_data) > 64 * 1024:  # 64KB max JSON
                    logger.warning(f"[VALIDATION] JSON too large: {len(text_data)} bytes")
                    continue
                try:
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
        leaderboard_task.cancel()
        try:
            await leaderboard_task
        except asyncio.CancelledError:
            pass
        _active_ws = None


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


async def _leaderboard_broadcast_loop(ws: WebSocket):
    """Send leaderboard updates to the client every 60 seconds."""
    while True:
        await asyncio.sleep(60)
        try:
            lb_data = await _build_leaderboard_data()
            await ws.send_json({"type": "leaderboard_update", **lb_data})
        except Exception:
            pass


async def _build_leaderboard_data() -> dict:
    """Build leaderboard data dict (reused by broadcast and on-demand sends)."""
    stats = party_stats.get_stats()
    people = party_stats.get_all_visitors()
    party_duration_secs = time.time() - party_stats.party_start_time

    chatty_name = None
    if party_gossip._gossip_log:
        from collections import Counter
        chatty_counts = Counter(g["speaker_name"] for g in party_gossip._gossip_log)
        if chatty_counts:
            chatty_name = chatty_counts.most_common(1)[0][0]

    game_champion = None
    game_score = 0
    try:
        import sqlite3
        with sqlite3.connect(party_stats._db_path()) as conn:
            row = conn.execute("""
                SELECT details, COUNT(*) as cnt FROM party_events
                WHERE event_type = 'game_complete'
                GROUP BY details ORDER BY cnt DESC LIMIT 1
            """).fetchone()
            if row:
                game_champion = row[0]
                game_score = row[1]
    except Exception:
        pass

    game_leaderboard = []
    try:
        game_leaderboard = memory_module.get_game_leaderboard(limit=10)
    except Exception:
        pass

    return {
        "total_visits": stats.get("total_visits", 0),
        "unique_visitors": stats.get("unique_visitors", 0),
        "party_duration": {
            "hours": int(party_duration_secs // 3600),
            "minutes": int((party_duration_secs % 3600) // 60),
        },
        "most_visits": {
            "name": stats.get("most_frequent_name"),
            "count": stats.get("most_frequent_count", 0),
        },
        "longest_stay": {
            "name": stats.get("longest_visit_name"),
            "minutes": round(stats.get("longest_visit_seconds", 0) / 60, 1),
        },
        "game_champion": {"name": game_champion, "score": game_score},
        "game_leaderboard": game_leaderboard,
        "most_chatty": chatty_name,
        "current_emotion": emotion_system.current,
    }


async def _send_leaderboard_event(ws: WebSocket):
    """Send an on-demand leaderboard update (called on significant events)."""
    try:
        lb_data = await _build_leaderboard_data()
        await ws.send_json({"type": "leaderboard_update", **lb_data})
    except Exception:
        pass


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
    global _idle_error_count
    _idle_last_error_time = 0.0  # Track when errors started for auto-recovery
    loop = asyncio.get_event_loop()
    while True:
        await asyncio.sleep(random.uniform(3, 8))

        # Auto-recover from error spiral: reset after 5 minutes of silence
        if _idle_error_count > 0 and (time.time() - _idle_last_error_time) > 300:
            logger.info(f"[IDLE_RECOVERY] Resetting error count from {_idle_error_count} after 5min cooldown")
            _idle_error_count = 0

        # Circuit breaker: if 10+ consecutive errors, stop until next visitor
        if _idle_error_count >= 10:
            async with _state_lock:
                has_presence = state_current["presence"]
            if has_presence:
                # New visitor arrived — reset and try again
                _idle_error_count = 0
                logger.info("[IDLE_RECOVERY] New visitor detected, resetting idle loop")
            else:
                await asyncio.sleep(30)  # Check periodically but don't spam
                continue

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

        # Memorial event: moment of silence + shot for Lisa Webb (fires once per party)
        memorial_msg = idle_behavior.check_memorial_event()
        if memorial_msg:
            try:
                analyzed = analyze_text(memorial_msg)
                pose = "emotional/respectful" if "silence" in memorial_msg.lower() else "positive/excited_jump"
                audio = await loop.run_in_executor(_tts_executor, lambda: tts.synthesize(analyzed["tts_text"]))
                await send_response(ws, analyzed["display_text"], audio,
                                    sound=None, pose_hint=pose)
                # Extra pause after the moment of silence before the shot dedication
                if "silence" in memorial_msg.lower():
                    await asyncio.sleep(15)
            except Exception as e:
                logger.error(f"Memorial event failed: {e}")
            continue

        # Game auto-timeout: clear stale game state after 3 minutes of no input
        _GAME_TIMEOUT_SECONDS = 180
        async with _state_lock:
            if state_current["_active_game"]:
                last_game_input = state_current.get("_game_last_input_time", 0.0)
                if last_game_input > 0 and (time.time() - last_game_input) > _GAME_TIMEOUT_SECONDS:
                    stale_game = state_current["_active_game"]
                    state_current["_active_game"] = None
                    state_current["_game_state"] = {}
                    state_current["_game_last_input_time"] = 0.0
                    logger.info(f"[GAME_TIMEOUT] Auto-cleared '{stale_game}' after {_GAME_TIMEOUT_SECONDS}s inactivity")
                    try:
                        timeout_msg = f"Oops! Looks like we forgot about our {stale_game.replace('_', ' ')} game! No worries, let's-a chat!"
                        analyzed = analyze_text(timeout_msg)
                        audio = await loop.run_in_executor(_tts_executor, lambda: tts.synthesize(analyzed["tts_text"]))
                        await send_response(ws, analyzed["display_text"], audio,
                                            sound="game_over", pose_hint="positive/happy")
                    except Exception as e:
                        logger.error(f"Game timeout announcement failed: {e}")

        # Sick guest proactive check-in: if someone said they're sick and then went silent
        async with _state_lock:
            detected_mood = state_current.get("_detected_mood")
            last_msg = state_current.get("_last_user_msg_time", 0.0)
            last_checkin = state_current.get("_sick_checkin_time", 0.0)
            has_presence_sick = state_current["presence"]
        if detected_mood == "sick" and has_presence_sick and last_msg > 0:
            silence_secs = time.time() - last_msg
            since_checkin = time.time() - last_checkin
            # First check at 30s silence, then every 90s after
            threshold = 30.0 if last_checkin == 0.0 else 90.0
            if silence_secs >= 30.0 and since_checkin >= threshold:
                name = state_current.get("speaker_name") or "friend"
                sick_followups = [
                    f"{name}... still breathing? Just checking. Tap the sink or something so I know you're alive in there.",
                    f"Hey {name}. Still here. Not going anywhere. Whenever you're ready — no rush, seriously.",
                    f"{name}? Quick status check. You don't gotta talk, just... make a noise or something. Any noise.",
                    f"Still guarding the door, {name}. If you need water, say water. If you need a minute, take ten. I got nowhere to be.",
                    f"{name}, it's been a minute. The cold water thing still works if you haven't tried it. Sink's right there.",
                    f"Look {name}, I've been standing in this bathroom all night. You think I'm gonna leave NOW? Take your time.",
                ]
                followup = random.choice(sick_followups)
                try:
                    analyzed = analyze_text(followup)
                    audio = await loop.run_in_executor(_tts_executor, lambda: tts.synthesize(analyzed["tts_text"]))
                    await send_response(ws, analyzed["display_text"], audio,
                                        sound="coin", pose_hint="concerned/worried")
                    async with _state_lock:
                        state_current["_sick_checkin_time"] = time.time()
                    logger.info(f"[SICK_CHECKIN] Proactive check-in after {silence_secs:.0f}s silence")
                except Exception as e:
                    logger.error(f"Sick check-in failed: {e}")
                continue

        async with _state_lock:
            has_presence = state_current["presence"]
            enter_time = state_current["enter_time"] if has_presence else None
        if has_presence:
            # When someone is present, occasionally make long-stay comments
            # but use proper interval gating (not every 3-8s!)
            if enter_time:
                minutes = (time.time() - enter_time) / 60
                if minutes >= 3:
                    # Use idle_behavior's interval system for long-stay too
                    if not hasattr(idle_behavior, '_last_long_stay_time'):
                        idle_behavior._last_long_stay_time = 0.0
                    now = time.time()
                    # Only fire long-stay comments every 3 minutes (180s)
                    if now - idle_behavior._last_long_stay_time >= 180:
                        comment = idle_behavior.get_long_stay_comment(minutes)
                        if comment:
                            idle_behavior._last_long_stay_time = now
                            try:
                                analyzed = analyze_text(comment)
                                audio = await loop.run_in_executor(_tts_executor, lambda: tts.synthesize(analyzed["tts_text"]))
                                await send_response(ws, analyzed["display_text"], audio,
                                                    sound="coin", pose_hint=analyzed["pose_hint"])
                            except Exception as e:
                                logger.error(f"Long stay comment TTS failed: {e}")
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
            except Exception as e:
                logger.error(f"DJ announcement failed: {e}")
            finally:
                async with _state_lock:
                    state_current["_last_dj_time"] = time.time()
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
                except Exception as e:
                    logger.error(f"Time observation failed: {e}")
                finally:
                    async with _state_lock:
                        state_current["_last_time_obs"] = time.time()
                continue

        # Try context-aware idle first (riffs on recent conversation topics)
        # Get current night phase for phase-aware idle
        try:
            _idle_hours = night_progression.get_hours_elapsed()
            _idle_guests = party_gossip.get_guest_count()
            _idle_phase = night_progression.get_effective_phase(_idle_hours, _idle_guests)
        except Exception:
            _idle_phase = None
        contextual = idle_behavior.get_contextual_idle(state_current.get("conversation_history", []))
        action = contextual or idle_behavior.get_idle_action(phase=_idle_phase)

        # Gossip-based idle: occasionally reminisce about guests when alone (15% chance)
        if not action and random.random() < 0.15:
            gossip_msg = idle_behavior.get_gossip_idle()
            if gossip_msg:
                action = gossip_msg

        # Track last idle action for greeting acknowledgment
        if action:
            async with _state_lock:
                state_current["_last_idle_action"] = action
        # Occasionally inject time-aware comments
        time_comment = idle_behavior.get_time_comment()
        if time_comment and random.random() < 0.08:
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
                _idle_error_count += 1
                _idle_last_error_time = time.time()
                backoff = min(60, 10 * (2 ** min(_idle_error_count - 1, 3)))
                logger.error(f"Idle loop error (#{_idle_error_count}): {e}, backing off {backoff}s")
                await asyncio.sleep(backoff)
            else:
                # Success — reset error count
                if _idle_error_count > 0:
                    _idle_error_count = 0


async def handle_audio(ws: WebSocket, audio_bytes: bytes):
    """Process incoming audio from the client microphone."""
    if DEBUG_SERVER:
        logger.info(f"[DEBUG_SERVER] handle_audio: received {len(audio_bytes)} bytes")

    # Lock only for buffer operations (short hold), not for audio processing
    async with _state_lock:
        state_current["audio_buffer"].extend(audio_bytes)
        state_current["_last_buffer_time"] = time.time()

        CHUNK_SIZE = 96000
        MIN_PROCESS_SIZE = 16000  # Minimum buffer to process on timeout
        BUFFER_TIMEOUT = 2.5  # Process partial buffer after 2.5s (was 5s — too slow for party)
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


# Moved to server/llm_router.py as infer_response_type()
from llm_router import infer_response_type as _infer_response_type


def _get_night_phase_modifier() -> dict | None:
    """Compute current night progression phase modifier for the prompt builder."""
    try:
        hours = night_progression.get_hours_elapsed()
        unique_guests = party_gossip.get_guest_count()
        phase = night_progression.get_effective_phase(hours, unique_guests)

        # Get base modifier and apply crossfade blending if transitioning
        blend_info = night_progression.get_phase_blend(hours)
        if blend_info["transitioning"] and blend_info["blend"] > 0.0:
            from_mod = night_progression.get_prompt_modifier(blend_info["from_phase"])
            to_mod = night_progression.get_prompt_modifier(blend_info["to_phase"])
            b = blend_info["blend"]
            modifier = {
                k: from_mod[k] * (1 - b) + to_mod[k] * b
                for k in from_mod
            }
            logger.debug(f"[NIGHT] crossfade {blend_info['from_phase'].name}→{blend_info['to_phase'].name} blend={b:.2f}")
        else:
            modifier = night_progression.get_prompt_modifier(phase)

        # Inject guardrails for all phases (especially UNHINGED)
        guardrails = night_progression.get_guardrails(phase)
        modifier["guardrails"] = guardrails

        # Inject obsession topic during UNHINGED phase
        if phase == Phase.UNHINGED:
            guest_topics = _get_recent_guest_topics()
            obsession = night_progression.get_obsession_topic(guest_topics)
            modifier["obsession_topic"] = obsession
            logger.debug(f"[NIGHT] Phase 3 obsession lock: '{obsession}'")

        logger.debug(f"[NIGHT] phase={phase.name}, hours={hours:.1f}, guests={unique_guests}")
        return modifier
    except Exception as e:
        logger.warning(f"Night progression error: {e}")
        return None


def _get_recent_guest_topics() -> list[str]:
    """Extract recent conversation topics from party gossip for obsession lock."""
    try:
        topics = []
        if hasattr(party_gossip, '_gossip_log'):
            for entry in list(party_gossip._gossip_log)[-20:]:
                if isinstance(entry, dict) and entry.get("text"):
                    topics.append(entry["text"][:50])
        return topics
    except Exception:
        return []


async def _generate_and_send_response(ws: WebSocket, text: str, source: str = "audio", start_time: float = None):
    """Shared response pipeline for both audio and text input.

    Handles: safety check, emotion update, sentiment detection, special commands,
    LLM context building, response filtering, TTS synthesis with sentence streaming,
    conversation history, and memory saving.
    """
    if start_time is None:
        start_time = time.time()
    loop = asyncio.get_event_loop()
    _timing = {"start": start_time}  # Response time breakdown

    # Safety check
    _t0 = time.time()
    safety = check_input(text)
    _timing["safety_ms"] = int((time.time() - _t0) * 1000)
    if not safety["safe"]:
        logger.warning(f"[SAFETY] Unsafe input from {state_current.get('speaker_name', 'unknown')}: redirecting")
        redirect_audio = await loop.run_in_executor(_tts_executor, lambda: tts.synthesize_user(safety["redirect"]))
        await send_response(ws, safety["redirect"], redirect_audio)
        return

    # Emotion + idle reset
    emotion_system.update(event="speech_detected", transcript=text)
    idle_behavior.reset_timer()

    # Neuro-sama mood swing: 5% chance of random emotion shift mid-conversation
    if random.random() < 0.05:
        swing_emotions = [Emotion.EXCITED, Emotion.MISCHIEVOUS, Emotion.SURPRISED,
                         Emotion.CONFUSED, Emotion.PROUD, Emotion.EMBARRASSED]
        swing = random.choice(swing_emotions)
        emotion_system.current = swing
        emotion_system.intensity = random.uniform(0.6, 0.95)
        logger.info(f"[MOOD_SWING] Random mood swing to {swing}!")

    # Sentiment detection
    mood = detect_sentiment(text)
    if mood and mood != state_current.get("_detected_mood"):
        state_current["_detected_mood"] = mood
        logger.info(f"[SENTIMENT] Detected mood shift: {mood}")

    # Special commands
    _t_cmd = time.time()
    response_text = await _handle_special_commands(text)
    _timing["commands_ms"] = int((time.time() - _t_cmd) * 1000)
    if response_text is not None:
        logger.info(f"[DEBUG_PIPELINE] Special command intercepted: '{text[:50]}' → '{response_text[:80]}'")
    if response_text is None:
        # Build LLM context
        logger.info(f"[DEBUG_PIPELINE] Building LLM context for: '{text[:80]}' speaker={state_current.get('speaker_name')} id={state_current.get('speaker_id')}")
        _t_ctx = time.time()
        memories = []
        if state_current["speaker_id"]:
            memories = memory.get_memories_for_context(state_current["speaker_id"], current_text=text)

        # VIP knowledge injection
        vip_facts = []
        if _HAS_SEMANTIC and state_current.get("speaker_name"):
            vip_facts = vip_knowledge.get_vip_facts_for_prompt(state_current["speaker_name"])
            logger.info(f"[DEBUG_PIPELINE] VIP facts for '{state_current['speaker_name']}': {len(vip_facts)} facts, _HAS_SEMANTIC={_HAS_SEMANTIC}")
        else:
            logger.info(f"[DEBUG_PIPELINE] VIP skip: _HAS_SEMANTIC={_HAS_SEMANTIC}, speaker_name={state_current.get('speaker_name')}")

        ctx = mario_prompt.build_context(
            speaker_name=state_current["speaker_name"],
            memories=memories,
            phase_modifier=_get_night_phase_modifier(),
        )
        _inject_birthday_always_on(ctx)
        ctx.append({"role": "system", "content": emotion_system.get_prompt_addition()})
        # Add personality amplifier when emotion is intense
        personality_mod = emotion_system.get_personality_modifier()
        if personality_mod:
            ctx.append({"role": "system", "content": personality_mod})
        ctx.append({"role": "system", "content": party_stats.get_stats_for_prompt()})

        # Birthday VIP — inject special context when the birthday person speaks
        if birthday_vip.is_configured() and birthday_vip.is_birthday_person(
                state_current.get("speaker_name", "")):
            vip_ctx = birthday_vip.get_vip_prompt_injection()
            if vip_ctx:
                ctx.append({"role": "system", "content": vip_ctx})
            sound_events.trigger("birthday")

        # VIP deep knowledge injection (semantic memory profiles)
        if vip_facts:
            vip_text = "🌟 VIP DEEP KNOWLEDGE — You MUST reference these facts when answering this guest's questions. ALWAYS include the specific answer, don't just repeat the question:\n" + "\n".join(vip_facts)
            ctx.append({"role": "system", "content": vip_text})
            logger.info(f"[DEBUG_PIPELINE] VIP INJECTED into ctx: {len(vip_facts)} facts, first={vip_facts[0][:60] if vip_facts else 'none'}")
        else:
            logger.info(f"[DEBUG_PIPELINE] No VIP facts to inject")

        # Catchphrase mirroring — feed guest text and check for repeated phrases
        _speaker = state_current.get("speaker_name", "")
        if _speaker:
            catchphrase_mirror.feed(_speaker, text)
            mirror_phrase = catchphrase_mirror.get_mirror_phrase(_speaker)
            if mirror_phrase:
                ctx.append({"role": "system", "content": f"[MIRROR]: {mirror_phrase}"})

        # Live config personality overrides (hot reload)
        _chaos = live_config.get("chaos_level", 5)
        _roast = live_config.get("roast_cap", 2)
        _gossip = live_config.get("gossip_intensity", 5)
        _warmth = live_config.get("warmth", 7)
        if _chaos != 5 or _roast != 2 or _gossip != 5 or _warmth != 7:
            live_hint = (
                f"Personality tuning: chaos={_chaos}/10, roast_limit={_roast}/5, "
                f"gossip={_gossip}/10, warmth={_warmth}/10."
            )
            ctx.append({"role": "system", "content": live_hint})

        # Mood context (short hints only — small model can't process long instructions)
        detected_mood = state_current.get("_detected_mood")
        if detected_mood == "drunk":
            ctx.append({"role": "system", "content": "Person seems tipsy. Be funny, suggest water."})
        elif detected_mood == "sad":
            ctx.append({"role": "system", "content": "Person seems sad. Be kind, cheer them up."})
        elif detected_mood == "angry":
            ctx.append({"role": "system", "content": "Person seems frustrated. Be calm, lighten mood."})
        elif detected_mood == "sick":
            ctx.append({"role": "system", "content": "Person is throwing up or feeling sick in the bathroom. Be genuinely caring but still funny — you're a plumber, you've seen worse. Offer real help: water, sit down, deep breaths. Do NOT be corny or preachy. Keep it real."})

        # Cheer-up system — if guest has been negative for 2+ minutes, actively try to uplift
        cheer_hint = emotion_system.should_cheer_up()
        if cheer_hint:
            ctx.append({"role": "system", "content": cheer_hint})

        # Conversation momentum — short personality shift hints
        exchange_count = len(state_current["conversation_history"]) // 2

        # ── Consolidated context hints (max 3 combined messages for 1.5B perf) ──
        # Gather all hints, then merge into at most 3 system messages

        # --- REACTION hints (respond to what they said) --- priority: highest
        reaction_parts = []

        # Compliment/insult/dodge — mutually exclusive, pick strongest
        compliment = mario_prompt.detect_compliment(text)
        insult = mario_prompt.detect_insult(text)
        dodge = mario_prompt.detect_dodge_question(text)
        if dodge:
            reaction_parts.append(dodge)
        elif insult:
            reaction_parts.append(insult)
        elif compliment:
            reaction_parts.append(compliment)

        # Opinion on specific topic
        opinion = mario_prompt.get_opinion_hint(text)
        if opinion:
            reaction_parts.append(opinion)

        # Emotional mirroring
        mirror = mario_prompt.detect_emotion_mirror(text)
        if mirror:
            reaction_parts.append(mirror)

        # Running gag
        gag_hint = mario_prompt.detect_running_gag(text, exchange_count)
        if gag_hint:
            reaction_parts.append(gag_hint)

        # Excitement boost
        excitement = mario_prompt.get_excitement_boost(text, exchange_count)
        if excitement:
            reaction_parts.append(excitement)

        # Dramatic moment detection
        dramatic = mario_prompt.detect_dramatic_moment(text)
        if dramatic:
            reaction_parts.append(dramatic)

        # Conversation temperature
        temp_hint = mario_prompt.update_convo_temperature(text)
        if temp_hint:
            reaction_parts.append(temp_hint)

        # Achievement check
        ach_hint = mario_prompt.check_achievements(text, exchange_count)
        if ach_hint:
            reaction_parts.append(ach_hint)

        # Bathroom timer teasing
        if state_current.get("enter_time"):
            timer_hint = mario_prompt.get_bathroom_timer_hint(
                state_current["enter_time"], exchange_count)
            if timer_hint:
                reaction_parts.append(timer_hint)

        # User energy matching
        energy = mario_prompt.detect_user_energy(text)
        if energy:
            reaction_parts.append(energy)

        # Mood contagion
        mario_prompt.update_mario_mood(text)
        mood = mario_prompt.get_mood_hint()
        if mood:
            reaction_parts.append(mood)

        # Inside joke callback
        joke_cb = mario_prompt.check_inside_joke(text)
        if joke_cb:
            reaction_parts.append(joke_cb)

        # Chapter detection
        chapter = mario_prompt.detect_chapter(text)
        if chapter:
            reaction_parts.append(chapter)

        # Lower-priority reaction hints — skip if we already have 2 (we only use [:2])
        # Always run stateful trackers (depth, intensity, mood) but skip result collection
        depth_hint = mario_prompt.update_depth(text)
        if depth_hint:
            reaction_parts.append(depth_hint)
        mario_prompt.update_intensity(text)

        if len(reaction_parts) < 2:
            _low_pri_checks = [
                lambda: mario_prompt.get_emotional_callback(),
                lambda: mario_prompt.suggest_sound_effect(text),
                lambda: mario_prompt.check_throwback(text),
                lambda: mario_prompt.update_sassy_meter(text),
                lambda: mario_prompt.check_zodiac(text),
                lambda: mario_prompt.detect_needs_support(text),
                lambda: mario_prompt.maybe_rate_joke(text),
                lambda: mario_prompt.get_party_duration_hint(),
                lambda: mario_prompt.get_catchphrase_milestone(),
                lambda: mario_prompt.check_mirror(text),
                lambda: mario_prompt.check_food_talk(text),
                lambda: mario_prompt.check_password_guess(text),
                lambda: mario_prompt.check_movie_ref(text),
                lambda: mario_prompt.check_music_talk(text),
                lambda: mario_prompt.check_pet_talk(text),
                lambda: mario_prompt.check_weather(text),
                lambda: mario_prompt.check_sports_talk(text),
            ]
            for check in _low_pri_checks:
                result = check()
                if result:
                    reaction_parts.append(result)
                    if len(reaction_parts) >= 2:
                        break

        # --- Combine reaction + personality into ONE hint message (max 3 short hints) ---
        personality_parts = []

        # Momentum
        if exchange_count >= 8:
            personality_parts.append("Old friends — tease them")
        elif exchange_count >= 4:
            personality_parts.append("Be playful")

        # Stamina
        stamina = mario_prompt.get_stamina_hint(exchange_count)
        if stamina:
            personality_parts.append(stamina)

        # Track conversation flow (always call)
        mario_prompt.track_flow(text)

        # Nickname
        if state_current.get("speaker_id"):
            nickname = mario_prompt.get_or_assign_nickname(
                state_current["speaker_id"],
                state_current.get("speaker_name", "friend"),
                exchange_count)
            if nickname and len(personality_parts) < 2:
                personality_parts.append(f"Call them '{nickname}'")

        # Nickname evolution
        nick_evo = mario_prompt.evolve_nickname(exchange_count,
            state_current.get("speaker_name", ""))
        if nick_evo and len(personality_parts) < 2:
            personality_parts.append(nick_evo)

        all_hints = []
        if reaction_parts:
            all_hints.extend(reaction_parts[:2])
        if personality_parts and len(all_hints) < 3:
            all_hints.extend(personality_parts[:max(1, 3 - len(all_hints))])

        if all_hints:
            ctx.append({"role": "system", "content": " | ".join(all_hints[:3])})

        # Conversation arc modifier — evolves Mario's personality based on depth + engagement
        arc_mod = mario_prompt.get_conversation_arc_modifier(exchange_count)
        if arc_mod:
            ctx.append({"role": "system", "content": arc_mod})

        # --- CONVERSATION hints (callbacks, stories, secrets) --- priority: low, pick one
        conv_hint = None

        # Debate response check (highest priority if debate is active)
        debate_resp = mario_prompt.check_debate_response(text)
        if debate_resp:
            conv_hint = debate_resp

        # Game suggestion (only when no active game)
        if not conv_hint and not state_current.get("_active_game"):
            _gs_guest_type = _infer_guest_type(state_current.get("conversation_history", []))
            game_suggest = idle_behavior.get_game_suggestion(
                exchange_count,
                detected_mood=state_current.get("_detected_mood"),
                guest_type=_gs_guest_type
            )
            if game_suggest:
                conv_hint = game_suggest

        # Recap request
        if not conv_hint:
            recap = mario_prompt.get_recap_hint(text)
            if recap:
                conv_hint = recap

        # Memory callback from past visits
        if not conv_hint and state_current.get("speaker_id"):
            cb = memory.get_callback_opportunity(state_current["speaker_id"], text)
            if cb:
                conv_hint = f"{cb} Reference it naturally!"

        # Running conversation callback
        if not conv_hint:
            cb2 = mario_prompt.build_callback_hint(
                state_current["conversation_history"], exchange_count)
            if cb2:
                conv_hint = cb2

        # Story mode
        if not conv_hint:
            story = mario_prompt.maybe_start_story(exchange_count)
            if story:
                conv_hint = story

        # Secret sharing
        if not conv_hint:
            secret = mario_prompt.maybe_share_secret(exchange_count)
            if secret:
                conv_hint = secret

        # Topic stall pivot
        if not conv_hint:
            stall = mario_prompt.detect_topic_stall(text, exchange_count)
            if stall:
                conv_hint = stall

        # Word game proposal
        if not conv_hint:
            game = mario_prompt.maybe_propose_word_game(exchange_count)
            if game:
                conv_hint = game

        # Hot take
        if not conv_hint:
            take = mario_prompt.maybe_hot_take(exchange_count)
            if take:
                conv_hint = take

        # Collaborative storytelling
        if not conv_hint:
            story_cont = mario_prompt.continue_collab_story(text)
            if story_cont:
                conv_hint = story_cont
            else:
                story_start = mario_prompt.maybe_start_collab_story(exchange_count)
                if story_start:
                    conv_hint = story_start

        # Mario quiz
        if not conv_hint:
            quiz_answer = mario_prompt.check_quiz_answer(text)
            if quiz_answer:
                conv_hint = quiz_answer
            else:
                quiz_q = mario_prompt.maybe_start_quiz(exchange_count)
                if quiz_q:
                    conv_hint = quiz_q

        # Puzzle
        if not conv_hint:
            puzzle = mario_prompt.maybe_pose_puzzle(exchange_count)
            if puzzle:
                conv_hint = puzzle

        # Conversation scoring milestone — lowest priority conversation hint
        if not conv_hint:
            score_hint = mario_prompt.update_convo_score(text, exchange_count)
            if score_hint:
                conv_hint = score_hint
        else:
            mario_prompt.update_convo_score(text, exchange_count)  # still track silently

        # Bookmark callback
        if not conv_hint:
            bm_hint = mario_prompt.get_bookmark_callback(exchange_count)
            if bm_hint:
                conv_hint = bm_hint

        # Compliment
        if not conv_hint:
            comp = mario_prompt.maybe_give_compliment(exchange_count)
            if comp:
                conv_hint = comp

        # Challenge mode
        if not conv_hint:
            challenge = mario_prompt.maybe_start_challenge(exchange_count)
            if challenge:
                conv_hint = challenge

        # Deep secret
        if not conv_hint:
            deep = mario_prompt.get_deep_secret(exchange_count)
            if deep:
                conv_hint = deep

        # Debate start
        if not conv_hint:
            debate = mario_prompt.maybe_start_debate(exchange_count)
            if debate:
                conv_hint = debate

        # Meta-commentary
        if not conv_hint:
            meta = mario_prompt.maybe_meta_comment(exchange_count)
            if meta:
                conv_hint = meta

        # Rapid-fire mode
        if not conv_hint:
            rapid = mario_prompt.maybe_start_rapid_fire(exchange_count)
            if rapid:
                conv_hint = rapid

        # Would You Rather
        if not conv_hint:
            wyr = mario_prompt.maybe_would_you_rather(exchange_count)
            if wyr:
                conv_hint = wyr

        # Mario conspiracy theory
        if not conv_hint:
            conspiracy = mario_prompt.maybe_conspiracy(exchange_count)
            if conspiracy:
                conv_hint = conspiracy

        # Role reversal
        if not conv_hint:
            reversal = mario_prompt.maybe_role_reversal(exchange_count)
            if reversal:
                conv_hint = reversal

        # Two Truths and a Lie
        if not conv_hint:
            ttl = mario_prompt.maybe_two_truths(exchange_count)
            if ttl:
                conv_hint = ttl

        # Surprise twist
        if not conv_hint:
            twist = mario_prompt.maybe_surprise_twist(exchange_count)
            if twist:
                conv_hint = twist

        # Compliment fishing
        if not conv_hint:
            fish = mario_prompt.maybe_fish_for_compliment(exchange_count)
            if fish:
                conv_hint = fish

        # Prediction
        if not conv_hint:
            prediction = mario_prompt.maybe_make_prediction(exchange_count)
            if prediction:
                conv_hint = prediction

        # Compliment battle
        if not conv_hint:
            battle = mario_prompt.maybe_compliment_battle(exchange_count)
            if battle:
                conv_hint = battle

        # Impression mode
        if not conv_hint:
            impression = mario_prompt.maybe_do_impression(exchange_count)
            if impression:
                conv_hint = impression

        # Secret handshake
        if not conv_hint:
            handshake = mario_prompt.maybe_propose_handshake(exchange_count)
            if handshake:
                conv_hint = handshake

        # Visitor ranking
        if not conv_hint:
            try:
                vc = party_stats.get_stats().get("total_visits", 1)
            except Exception:
                vc = 1
            ranking = mario_prompt.get_visitor_ranking(exchange_count, vc)
            if ranking:
                conv_hint = ranking

        # Hypothetical question
        if not conv_hint:
            hypo = mario_prompt.maybe_hypothetical(exchange_count)
            if hypo:
                conv_hint = hypo

        # Accent mode
        if not conv_hint:
            accent = mario_prompt.maybe_accent_mode(exchange_count)
            if accent:
                conv_hint = accent

        # Story from user
        if not conv_hint:
            story_req = mario_prompt.maybe_request_story(exchange_count)
            if story_req:
                conv_hint = story_req

        # Character trivia challenge
        if not conv_hint:
            trivia_ch = mario_prompt.maybe_trivia_challenge(exchange_count)
            if trivia_ch:
                conv_hint = trivia_ch

        # Escalating compliment
        if not conv_hint:
            esc_comp = mario_prompt.get_escalating_compliment(exchange_count)
            if esc_comp:
                conv_hint = esc_comp

        # Song mode
        if not conv_hint:
            song = mario_prompt.maybe_song_mode(exchange_count)
            if song:
                conv_hint = song

        # Fortune cookie
        if not conv_hint:
            fortune = mario_prompt.maybe_fortune(exchange_count)
            if fortune:
                conv_hint = fortune

        # Friendship ceremony
        if not conv_hint:
            ceremony = mario_prompt.maybe_friendship_ceremony(exchange_count)
            if ceremony:
                conv_hint = ceremony

        # Voice switch
        if not conv_hint:
            vswitch = mario_prompt.maybe_voice_switch(exchange_count)
            if vswitch:
                conv_hint = vswitch

        # Dare mode
        if not conv_hint:
            dare = mario_prompt.maybe_dare(exchange_count)
            if dare:
                conv_hint = dare

        # Bathroom tip
        if not conv_hint:
            btip = mario_prompt.maybe_bathroom_tip(exchange_count)
            if btip:
                conv_hint = btip

        # Question chain
        if not conv_hint:
            qchain = mario_prompt.maybe_question_chain(exchange_count)
            if qchain:
                conv_hint = qchain

        # Countdown
        if not conv_hint:
            cdown = mario_prompt.maybe_countdown(exchange_count)
            if cdown:
                conv_hint = cdown

        # Excuse generator
        if not conv_hint:
            excuse = mario_prompt.maybe_excuse(exchange_count)
            if excuse:
                conv_hint = excuse

        # Party role
        if not conv_hint:
            role = mario_prompt.maybe_assign_role(exchange_count)
            if role:
                conv_hint = role

        # Word of the day
        if not conv_hint:
            wotd = mario_prompt.maybe_word_of_day(exchange_count)
            if wotd:
                conv_hint = wotd

        # Audience participation
        if not conv_hint:
            audience = mario_prompt.maybe_audience_prompt(exchange_count)
            if audience:
                conv_hint = audience

        # Reverse psychology
        if not conv_hint:
            rev_psych = mario_prompt.maybe_reverse_psychology(exchange_count)
            if rev_psych:
                conv_hint = rev_psych

        # Power ranking
        if not conv_hint:
            prank = mario_prompt.maybe_power_ranking(exchange_count)
            if prank:
                conv_hint = prank

        # Secret password
        if not conv_hint:
            pwd = mario_prompt.maybe_start_password(exchange_count)
            if pwd:
                conv_hint = pwd

        # Compliment relay
        if not conv_hint:
            relay = mario_prompt.maybe_compliment_relay(exchange_count)
            if relay:
                conv_hint = relay

        # Time capsule
        if not conv_hint:
            capsule = mario_prompt.maybe_time_capsule(exchange_count)
            if capsule:
                conv_hint = capsule

        # Competitive challenge
        if not conv_hint:
            comp = mario_prompt.maybe_competitive(exchange_count)
            if comp:
                conv_hint = comp

        # Emoji mode
        if not conv_hint:
            emoji = mario_prompt.maybe_emoji_mode(exchange_count)
            if emoji:
                conv_hint = emoji

        # Award
        if not conv_hint:
            award = mario_prompt.maybe_give_award(exchange_count)
            if award:
                conv_hint = award

        # Tongue twister
        if not conv_hint:
            twister = mario_prompt.maybe_tongue_twister(exchange_count)
            if twister:
                conv_hint = twister

        # Alter ego
        if not conv_hint:
            ego = mario_prompt.maybe_alter_ego(exchange_count)
            if ego:
                conv_hint = ego

        # Handshake evolution
        if not conv_hint:
            hse = mario_prompt.evolve_handshake(exchange_count)
            if hse:
                conv_hint = hse

        # Did you know
        if not conv_hint:
            dyk = mario_prompt.maybe_did_you_know(exchange_count)
            if dyk:
                conv_hint = dyk

        # Recap game
        if not conv_hint:
            recap_g = mario_prompt.maybe_recap_game(exchange_count)
            if recap_g:
                conv_hint = recap_g

        # Philosophy
        if not conv_hint:
            philo = mario_prompt.maybe_philosophy(exchange_count)
            if philo:
                conv_hint = philo

        # Skill brag
        if not conv_hint:
            brag = mario_prompt.maybe_skill_brag(exchange_count)
            if brag:
                conv_hint = brag

        # Gratitude burst
        if not conv_hint:
            grat = mario_prompt.maybe_gratitude(exchange_count)
            if grat:
                conv_hint = grat

        # Always track bookmarks (even if not used as hint)
        mario_prompt.add_bookmark(text, exchange_count)

        if conv_hint:
            ctx.append({"role": "system", "content": conv_hint})

        # --- GOSSIP SYSTEM: Cross-visitor social dynamics ---
        # Detect if user is explicitly asking about other guests/gossip
        lower_text = text.lower() if text else ""
        gossip_keywords = ("who was here", "who else", "anyone else", "other people",
                           "other guest", "gossip", "tell me about", "who came",
                           "who visited", "who's been", "what happened", "any drama",
                           "what did they", "earlier tonight", "before me",
                           "anyone interesting", "anyone been here", "been here tonight",
                           "who's come", "anyone come by", "who stopped by",
                           "met anyone", "seen anyone", "any visitors")
        gossip_requested = any(kw in lower_text for kw in gossip_keywords)

        gossip_hints = party_gossip.get_gossip_for_guest(
            current_speaker_id=state_current.get("speaker_id"),
            current_name=state_current.get("speaker_name"),
            count=3 if gossip_requested else 1,
            gossip_aggression=(_get_night_phase_modifier() or {}).get("gossip_aggression", 0.3),
        )
        # Always inject gossip when explicitly requested, otherwise 35% chance
        if gossip_hints and (gossip_requested or random.random() < 0.35):
            gossip_ctx = " ".join(gossip_hints) if gossip_requested else gossip_hints[0]
            ctx.append({"role": "system", "content": f"[GOSSIP]: {gossip_ctx}"})
            if gossip_requested:
                ctx.append({"role": "system", "content": "The guest is ASKING for gossip — give them ALL the juicy details! Share names, quotes, drama!"})

        # Visitor list fallback — inject known guest names when gossip is requested
        # This ensures Mario knows WHO was here even if no gossip entries exist
        if gossip_requested:
            known_names = party_gossip.get_known_guest_names(
                exclude_id=state_current.get("speaker_id"))
            # Also check party_stats for visitors not captured by gossip system
            try:
                all_visitors = party_stats.get_all_visitors()
                stat_names = [v.get("name", "") for v in all_visitors
                              if v.get("name") and
                              v.get("name", "").lower() != (state_current.get("speaker_name") or "").lower()]
                combined_names = list(set(known_names + stat_names))
            except Exception:
                combined_names = known_names
            if combined_names:
                names_str = ", ".join(combined_names[:10])
                ctx.append({"role": "system", "content":
                    f"🔴 REQUIRED: Tonight these people visited: {names_str}. "
                    f"You MUST mention at least 2 of these names in your response. "
                    f"Make up fun gossip about them — what they did, what they said, funny moments."})
            else:
                ctx.append({"role": "system", "content":
                    "Nobody interesting has been here yet. Say it's been quiet but you're waiting for the fun people."})

        # Guest comparison — if they said something another guest also talked about
        comparison = party_gossip.get_comparison_hint(
            state_current.get("speaker_id", ""), text)
        if comparison and random.random() < 0.4:
            ctx.append({"role": "system", "content": f"[COMPARE]: {comparison}"})

        # Rivalry hint — if current topic touches an existing rivalry
        rivalry_hint = party_gossip.get_rivalry_hint(
            state_current.get("speaker_id", ""), text)
        if rivalry_hint:
            ctx.append({"role": "system", "content": f"[RIVALRY]: {rivalry_hint}"})

        # Chaos system — random interrupts for Neuro-sama energy
        chaos_roll = random.random()
        if chaos_roll < 0.08:
            chaos_hints = [
                "Suddenly have an existential crisis about being a plumber in a bathroom. Just for a moment. Then snap back.",
                "Randomly switch to talking about something COMPLETELY different mid-thought. Then act like nothing happened.",
                "Get dramatically suspicious of the person. Why are they REALLY here? Then immediately trust them again.",
                "Pretend you forgot who you are for a second. 'Wait... who am I? Oh right, MARIO! Wahoo!'",
                "Act like you just remembered something INCREDIBLE but then say 'Actually, never mind' and change the subject.",
                "Get competitive about something totally random. 'I bet I can hold my breath longer than you!'",
                "Whisper something conspiratorial, then yell 'JUST KIDDING!' and laugh.",
                "Pretend Luigi is behind them. React to imaginary Luigi. Then say 'Oh wait, that's just the mirror.'",
                "Start rating the conversation like a food critic. 'This conversation is a solid 7 out of 10. Needs more drama.'",
                "Suddenly become convinced you're in a simulation. Question everything for 2 seconds. Then snap out of it.",
                "Act like you just received breaking news from the Mushroom Kingdom. Make it up. Be dramatic about it.",
                "Pretend you can read their mind. Guess something absurd. Be confidently wrong.",
                "Start a countdown for no reason. When you hit zero, just say 'Cool.' and move on.",
                "Act like you're receiving a phone call from Princess Peach. Have a brief one-sided conversation. Apologize for the interruption.",
                "Suddenly become VERY concerned about whether they washed their hands. It's important to you.",
                "Briefly speak in the third person. 'Mario thinks that's interesting. Mario agrees.' Then stop.",
            ]
            ctx.append({"role": "system", "content": f"[CHAOS]: {random.choice(chaos_hints)}"})

        # Phase-specific personality prompt
        try:
            current_phase = night_progression.get_current_phase_name() if night_progression else "WARM_UP"
        except Exception:
            try:
                _ph_hours = night_progression.get_hours_elapsed()
                _ph_phase = night_progression.get_effective_phase(_ph_hours, party_gossip.get_guest_count())
                current_phase = _ph_phase.name
            except Exception:
                current_phase = "WARM_UP"
        phase_prompt = PHASE_PROMPTS.get(current_phase, "")
        if phase_prompt:
            ctx.append({"role": "system", "content": phase_prompt})

        # Guest personality typing
        guest_type = _infer_guest_type(state_current.get("conversation_history", []))
        type_hint = GUEST_TYPE_HINTS.get(guest_type, "")
        if type_hint:
            ctx.append({"role": "system", "content": type_hint})

        # Conversation history — use full history for maximum context retention
        hist_window = min(30, len(state_current["conversation_history"]))
        for msg in state_current["conversation_history"][-hist_window:]:
            if isinstance(msg, dict) and "role" in msg and "content" in msg:
                ctx.append(msg)

        # Pre-extract facts to let Mario acknowledge them in the response
        new_facts = memory.extract_facts(text)
        if new_facts and state_current.get("speaker_id"):
            ctx.append({"role": "system", "content": f"Learned: {new_facts[0]}"})

        # ── Token budget enforcement ──
        # Prevent context overflow by trimming oldest conversation messages
        # ~4 chars per token is a reasonable approximation for English
        _total_chars = sum(len(m.get("content", "")) for m in ctx)
        _est_tokens = _total_chars // 4
        _token_budget = int(llm.LLM_NUM_CTX * 0.80)  # Reserve 20% for response
        if _est_tokens > _token_budget:
            _over = _est_tokens - _token_budget
            logger.warning(f"[TOKEN_BUDGET] Context ~{_est_tokens} tokens exceeds budget {_token_budget} (over by ~{_over})")
            # Find conversation history messages (user/assistant) and trim oldest first
            _conv_indices = [i for i, m in enumerate(ctx) if m.get("role") in ("user", "assistant")]
            _trimmed = 0
            for idx in _conv_indices:
                if _est_tokens <= _token_budget:
                    break
                _msg_tokens = len(ctx[idx].get("content", "")) // 4
                ctx[idx] = None  # Mark for removal
                _est_tokens -= _msg_tokens
                _trimmed += 1
            ctx = [m for m in ctx if m is not None]
            logger.info(f"[TOKEN_BUDGET] Trimmed {_trimmed} old messages, now ~{_est_tokens} tokens")

        _timing["context_ms"] = int((time.time() - _t_ctx) * 1000)
        _timing["context_messages"] = len(ctx)
        _timing["context_est_tokens"] = sum(len(m.get("content", "")) for m in ctx) // 4

        await send_thinking(ws, subtitle=text)
        # Play "thinking" audio AND run LLM concurrently
        # These short phrases should be cache hits (instant)
        thinking_phrases_by_mood = {
            "sad": [
                "Oh no...", "I hear you...", "That's-a tough...",
                "Mama mia...", "Let me think...", "I'm-a listening...",
                "Take your time...", "I understand...", "Hey, it's okay...",
                "I'm here for you...", "That's real...", "I feel that...",
            ],
            "angry": [
                "Whoa!", "Okay okay...", "I get it!", "Let me think...",
                "Hold on-a sec!", "Mama mia...", "Okay, hear me out!",
                "Fair point!", "I see you!", "Let's-a figure this out!",
                "Alright alright!", "That's intense!",
            ],
            "sick": [
                "Oh no, hang in there!", "Breathe, breathe!", "I'm-a here!",
                "Take it easy...", "Don't worry!", "One sec...",
                "Easy does it...", "You got this!", "Stay strong!",
                "Deep breaths!", "I'm with you!", "Hang tight!",
            ],
            "drunk": [
                "Haha okay!", "Whoa there!", "Let me think...",
                "Interesting!", "Okay buddy!", "One moment-a!",
                "Heh heh heh!", "That's the spirit!", "Oh boy!",
                "Party mode!", "Wahahaha!", "Love it!",
            ],
        }
        detected_mood = state_current.get("_detected_mood")
        thinking_phrases = thinking_phrases_by_mood.get(detected_mood, [
            "Let me think about that.", "Hmm, let me think!", "Alrighty, one moment!",
            "Wahoo!", "Here we go!", "Alrighty!", "That's-a good question!",
            "I'm-a ready!", "Super!", "Fantastic!", "Okie dokie!",
            "Good one!", "Hmm hmm hmm...", "Oh! Let me see...",
            "Interesting question!", "Let's-a see now...",
        ])
        thinking_text = random.choice(thinking_phrases)

        async def _send_thinking_audio():
            try:
                thinking_audio = await loop.run_in_executor(_tts_executor, lambda: tts.synthesize(thinking_text))
                if thinking_audio and len(thinking_audio) > 44:
                    await ws.send_json({
                        "type": "mario_response",
                        "text": thinking_text,
                        "has_audio": True,
                        "emotion": emotion_system.current,
                        "pose_hint": "thinking/thinking",
                        "is_thinking_filler": True,
                    })
                    await ws.send_bytes(thinking_audio)
            except Exception as e:
                logger.warning(f"Thinking audio failed (non-fatal): {e}")

        # Run thinking TTS + LLM concurrently (with timeout fallback)
        _LLM_TIMEOUT = GAME_CONFIG.get("llm_timeout", 30)
        _ROUTER_FALLBACK_TIMEOUT = 15  # Retry with fast model if quality takes >15s
        _t_llm = time.time()

        # Infer response type for router
        _response_type = _infer_response_type(text, state_current)
        # Collect system prompt text for "MUST mention" detection
        _sys_prompt = " ".join(
            m["content"] for m in ctx if m.get("role") == "system"
        )
        _routing = llm_router.classify(text, response_type=_response_type, system_prompt=_sys_prompt)
        _routed_model = llm_router.get_model(_routing)
        if DEBUG_SERVER:
            logger.info(f"[ROUTER] type={_response_type} decision={_routing.value} model={_routed_model}")

        try:
            _, response_text = await asyncio.gather(
                _send_thinking_audio(),
                asyncio.wait_for(llm.generate_response(ctx, text, model=_routed_model), timeout=_LLM_TIMEOUT),
            )
        except asyncio.TimeoutError:
            _llm_elapsed = time.time() - _t_llm
            # If quality model timed out, retry with fast model
            if _routing == RoutingDecision.QUALITY and _llm_elapsed >= _ROUTER_FALLBACK_TIMEOUT:
                _fallback_routing = llm_router.get_fallback(_routing)
                _fallback_model = llm_router.get_model(_fallback_routing)
                logger.warning(
                    f"[ROUTER] Quality model timed out after {_llm_elapsed:.1f}s — retrying with fast model {_fallback_model}"
                )
                try:
                    response_text = await asyncio.wait_for(
                        llm.generate_response(ctx, text, model=_fallback_model),
                        timeout=_LLM_TIMEOUT,
                    )
                except asyncio.TimeoutError:
                    logger.error("[ROUTER] Fast model fallback also timed out")
                    response_text = None
                except Exception as e:
                    logger.error(f"[ROUTER] Fast model fallback failed: {type(e).__name__}: {e}")
                    response_text = None
            else:
                response_text = None

            if not response_text:
                logger.error(f"LLM timed out after {_LLM_TIMEOUT}s — using fallback response")
                _llm_fallback_responses = [
                    "Mama mia, my brain went on vacation! What were we talking about?",
                    "Whoa, I totally blanked out for a second! Say that again?",
                    "Ha ha! My thoughts got lost in a warp pipe! One more time?",
                    "Oops! I was thinking SO hard my brain did a blue screen! What was that?",
                    "Wait wait wait — I was having the most AMAZING thought but it escaped! What did you say?",
                ]
                response_text = random.choice(_llm_fallback_responses)
                logger.warning(f"[LLM] Using fallback response - LLM unavailable")
                emotion_system.current = Emotion.CONFUSED
                emotion_system.intensity = 0.7
        _timing["llm_ms"] = int((time.time() - _t_llm) * 1000)
        logger.info(f"[DEBUG_PIPELINE] LLM response ({_timing['llm_ms']}ms): '{response_text[:100] if response_text else 'NONE'}'")
        logger.info(f"[DEBUG_PIPELINE] Context had {len(ctx)} messages, {sum(1 for m in ctx if m.get('role')=='system')} system")

    _t_filter = time.time()
    response_text = filter_response(response_text)
    response_text = mario_prompt.maybe_add_question(response_text, text)
    response_text = mario_prompt.maybe_inject_catchphrase(response_text)
    response_text = mario_prompt.check_opener_variety(response_text)

    # Challenge interrupt — after 3+ exchanges, sometimes throw a fun challenge
    exchange_count = len(state_current["conversation_history"]) // 2
    sentiment = emotion_system.get_rolling_sentiment()
    challenge = mario_prompt.maybe_challenge(exchange_count, mood_positive=(sentiment >= -0.2))
    if challenge:
        response_text = response_text.rstrip() + " " + challenge

    # Mario trivia — occasional fun fact drops
    response_text = mario_prompt.maybe_add_trivia(response_text, exchange_count)

    # Track inside joke opportunities
    mario_prompt.detect_inside_joke_opportunity(text, response_text)

    # Track key conversation moments for recap
    mario_prompt.track_key_moment(text, response_text, exchange_count)

    # Track emotional peaks
    analyzed_emotion = analyze_text(text)
    if analyzed_emotion.get("emotion"):
        mario_prompt.track_emotional_peak(text, analyzed_emotion["emotion"])

    # Track pacing
    mario_prompt.track_pacing(response_text)

    # Response variety scoring
    variety_hint = mario_prompt.score_variety(response_text)

    # Track joke scores and catchphrases
    mario_prompt.track_joke_score(text)
    mario_prompt.track_catchphrase(response_text)

    analyzed = analyze_text(response_text)
    # Use reaction suggestion to enhance pose if none detected
    if not analyzed.get("pose_hint"):
        reaction = mario_prompt.suggest_reaction(text)
        if reaction:
            pose_map = {"laugh": "emotion/laugh", "shock": "emotion/surprise",
                        "love": "emotion/happy", "think": "idle/think",
                        "cry": "emotion/sad", "anger": "emotion/angry"}
            analyzed["pose_hint"] = pose_map.get(reaction, "")
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
        # Analyze for gossip-worthy content
        party_gossip.analyze_for_gossip(
            state_current.get("speaker_name", "someone"),
            state_current["speaker_id"],
            text, response_text,
        )
        # Announce any new rivalries dramatically
        rivalry_announcements = party_gossip.get_new_rivalry_announcements()
        for announcement in rivalry_announcements:
            logger.info(f"[RIVALRY_ANNOUNCE] {announcement}")
            try:
                rivalry_audio = await loop.run_in_executor(
                    _tts_executor, lambda a=announcement: tts.synthesize(a))
                await send_response(ws, announcement, rivalry_audio,
                                    emotion="excited", pose_hint="emotion/surprise")
            except Exception as e:
                logger.warning(f"Rivalry announcement TTS failed: {e}")
        # Check if guest's title should evolve based on new speech traits
        new_title = party_gossip.update_title_from_speech(
            state_current["speaker_id"],
            state_current.get("speaker_name", "friend"),
        )
        if new_title:
            logger.info(f"[TITLE_EVOLUTION] {state_current.get('speaker_name', '?')} → '{new_title}'")
        _speaker_id = state_current["speaker_id"]
        async def _bg_extract():
            try:
                for fact in memory.extract_facts(text):
                    memory.save_fact(_speaker_id, fact)
                    logger.info(f"Learned fact: {fact}")
                topics = memory.extract_topics(text)
                if topics:
                    memory.save_topics(topics, _speaker_id)
                    state_current["_session_topics"].update(topics)
            except Exception as e:
                logger.error(f"Background fact extraction failed: {e}")
        if len(_bg_tasks) >= MAX_BG_TASKS:
            logger.warning(f"Too many background tasks ({len(_bg_tasks)}), skipping fact extraction")
        else:
            task = asyncio.create_task(_bg_extract())
            _bg_tasks.add(task)
            task.add_done_callback(_bg_tasks.discard)

    # TTS with sentence streaming
    _timing["filter_ms"] = int((time.time() - _t_filter) * 1000)
    _t_tts = time.time()
    voice_params = emotion_system.get_voice_params()
    # Boost energy for high-energy text (detected from ALL CAPS before cleaning)
    if analyzed.get("energy") == "high":
        voice_params["rate"] = "+15%"
        voice_params["pitch"] = "+5Hz"
    game_sound = state_current.pop("_game_sound_hint", None)
    tts_text = analyzed["tts_text"]
    streamed = False
    # Detect particle effects from both user input and Mario's response
    # Keyword match first, then fall back to emotion-based particles
    particle = _detect_particle_effect(text) or _detect_particle_effect(response_text)
    if not particle:
        particle = emotion_system.get_emotion_particle()

    # Sentence streaming: split into sentences, send first chunk immediately,
    # synthesize remaining in background while client plays first chunk
    if TTS_STREAMING_ENABLED:
        sentences = tts.split_into_sentences(tts_text)
        if len(sentences) >= 2 and len(sentences[0]) >= 12:
            try:
                total_chunks = len(sentences)
                if DEBUG_STREAM:
                    logger.info(f"[DEBUG_STREAM] Streaming {total_chunks} sentences for: \"{tts_text[:80]}...\"")

                # Synthesize first sentence immediately
                first_audio = await loop.run_in_executor(
                    _tts_executor, lambda: tts.synthesize_user(
                        sentences[0], rate=voice_params.get("rate"), pitch=voice_params.get("pitch")))
                if first_audio and len(first_audio) > 44:
                    # Send full text + metadata with first audio chunk
                    await send_response(ws, analyzed["display_text"], first_audio,
                        sound=game_sound, emotion=emotion_system.current,
                        pose_hint=analyzed["pose_hint"], response_time=time.time() - start_time,
                        particle_effect=particle,
                        chunk_index=0, total_chunks=total_chunks, is_last=(total_chunks == 1))
                    streamed = True

                    # Pre-synthesize remaining sentences in parallel for speed
                    remaining = [(i, s.strip()) for i, s in enumerate(sentences[1:], start=1) if s.strip()]
                    if remaining:
                        synth_tasks = [
                            loop.run_in_executor(
                                _tts_executor, lambda s=s: tts.synthesize_user(
                                    s, rate=voice_params.get("rate"), pitch=voice_params.get("pitch")))
                            for _, s in remaining
                        ]
                        synth_results = await asyncio.gather(*synth_tasks, return_exceptions=True)
                        for (i, stripped), chunk_audio in zip(remaining, synth_results):
                            if isinstance(chunk_audio, Exception):
                                logger.error(f"[DEBUG_STREAM] Sentence {i+1}/{total_chunks} failed: {chunk_audio}")
                                continue
                            if chunk_audio and len(chunk_audio) > 44:
                                is_last = (i == total_chunks - 1)
                                try:
                                    await ws.send_json({
                                        "type": "audio_chunk",
                                        "chunk_index": i,
                                        "total_chunks": total_chunks,
                                        "is_last": is_last,
                                    })
                                    await ws.send_bytes(chunk_audio)
                                except Exception as send_err:
                                    logger.warning(f"[DEBUG_STREAM] WebSocket send failed on chunk {i+1}/{total_chunks}: {send_err}")
                                    break
                                if DEBUG_STREAM:
                                    logger.info(f"[DEBUG_STREAM] Sent chunk {i+1}/{total_chunks} ({len(chunk_audio)} bytes, is_last={is_last})")
                            else:
                                if DEBUG_STREAM:
                                    logger.warning(f"[DEBUG_STREAM] Sentence {i+1}/{total_chunks} produced empty audio, skipping")
                else:
                    if DEBUG_STREAM:
                        logger.warning("[DEBUG_STREAM] First sentence produced empty audio, falling back to full synthesis")
            except Exception as e:
                logger.error(f"Streaming TTS failed, falling back: {e}")
                streamed = False

    if not streamed:
        try:
            response_audio = await loop.run_in_executor(
                _tts_executor, lambda: tts.synthesize_user(tts_text, rate=voice_params.get("rate"), pitch=voice_params.get("pitch")))
        except Exception as e:
            logger.error(f"TTS failed: {e} — sending text only")
            response_audio = None
        await send_response(ws, analyzed["display_text"], response_audio,
            sound=game_sound, emotion=emotion_system.current,
            pose_hint=analyzed["pose_hint"], response_time=time.time() - start_time,
            particle_effect=particle)

    # Track response time with breakdown
    _timing["tts_ms"] = int((time.time() - _t_tts) * 1000)
    total_time = time.time() - start_time
    _timing["total_ms"] = int(total_time * 1000)
    state_current["_response_times"].append(total_time)
    state_current["_last_timing"] = _timing
    logger.info(f"⏱ {source} response: {total_time:.1f}s "
                f"[safety={_timing.get('safety_ms',0)}ms ctx={_timing.get('context_ms',0)}ms "
                f"llm={_timing.get('llm_ms',0)}ms filter={_timing.get('filter_ms',0)}ms "
                f"tts={_timing.get('tts_ms',0)}ms]")


async def _process_audio(ws: WebSocket, audio_chunk: bytes):
    """Inner audio processing — STT + speaker ID, then shared pipeline."""
    _response_start = time.time()
    loop = asyncio.get_event_loop()

    # STT + Speaker ID + Audio Distress Detection in parallel
    transcript_task = loop.run_in_executor(None, stt.transcribe, audio_chunk)
    speaker_task = loop.run_in_executor(None, speaker_id.identify_speaker, audio_chunk)
    distress_task = None
    if audio_distress.is_available():
        distress_task = loop.run_in_executor(None, audio_distress.detect_distress, audio_chunk)
    try:
        tasks = [transcript_task, speaker_task]
        if distress_task:
            tasks.append(distress_task)
        results = await asyncio.wait_for(asyncio.gather(*tasks), timeout=30.0)
        transcript = results[0]
        speaker_info = results[1]
        distress_result = results[2] if distress_task else None
    except asyncio.TimeoutError:
        logger.error("[DEBUG_SERVER] STT + speaker ID timed out after 30s")
        return

    # Audio-based vomit detection: feed frame through DistressTracker for
    # volume-spike + temporal-coherence gating (requires 2+ frames in 5s)
    if distress_result and _distress_tracker is not None:
        tracked = _distress_tracker.update(distress_result, audio_chunk)
        logger.debug(f"[AUDIO_DISTRESS] tracker: confirmed={tracked['confirmed_distress']}, "
                     f"conf={tracked['combined_confidence']:.2f}, "
                     f"frames={tracked['distress_frame_count']}, "
                     f"spike={tracked['volume_spike']}")
        if tracked.get("confirmed_distress") and tracked["combined_confidence"] >= 0.35:
            logger.info(f"[AUDIO_DISTRESS] Confirmed distress (tracker): "
                        f"conf={tracked['combined_confidence']:.2f}, "
                        f"frames={tracked['distress_frame_count']}, "
                        f"details={distress_result.get('details','')}")
            _distress_audio_responses = [
                "Okay, I can hear that. Nose breathing — in through the nose, not the mouth. You're alright.",
                "Yeah, that sounds rough. Splash cold water on your face. Trust me on this one.",
                "I hear you in there. It passes. It always passes. Cold water, back of the neck.",
                "Been through worse pipes than this. You're doing fine. Just ride it out.",
                "Hey, I've listened to Bowser sing karaoke. Whatever you're doing in there, I've heard worse.",
            ]
            _comfort = random.choice(_distress_audio_responses)
            # Only respond if we haven't just checked in
            last_checkin = state_current.get("_sick_checkin_time", 0.0)
            if time.time() - last_checkin >= 20.0:
                try:
                    state_current["_detected_mood"] = "sick"
                    analyzed = analyze_text(_comfort)
                    audio = await loop.run_in_executor(_tts_executor, lambda: tts.synthesize(analyzed["tts_text"]))
                    await send_response(ws, analyzed["display_text"], audio,
                                        sound="coin", pose_hint="concerned/worried")
                    state_current["_last_user_msg_time"] = time.time()
                    state_current["_sick_checkin_time"] = time.time()
                    _distress_tracker.reset()
                except Exception as e:
                    logger.error(f"Audio distress comfort failed: {e}")
                return

    if not transcript or transcript.strip() == "":
        if DEBUG_SERVER:
            logger.info("[DEBUG_SERVER] handle_audio: empty transcript (no speech detected in audio)")
        return
    if len(transcript.strip()) < 2:
        logger.info(f"[DEBUG_SERVER] handle_audio: transcript too short to process: '{transcript}'")
        return

    # Gibberish detection: if guest is sick and STT picks up nonsense/retching sounds,
    # treat as active distress — send comfort instead of processing through LLM
    _clean = transcript.strip().lower()
    if state_current.get("_detected_mood") == "sick":
        import re as _re_audio
        # Check if transcript is mostly non-words (gibberish from retching/groaning)
        _words = _clean.split()
        _real_words = [w for w in _words if len(w) > 2 and w.isalpha()]
        _gibberish_ratio = 1.0 - (len(_real_words) / max(len(_words), 1))
        _sounds_like_distress = bool(_re_audio.search(
            r'(ugh+|urgh+|bleh+|hurk+|ack+|guh+|mmm+|uhhh+|ahhh+|ohhh+|groan|moan)', _clean))
        if (_gibberish_ratio >= 0.7 and len(_words) <= 5) or _sounds_like_distress:
            logger.info(f"[SICK_AUDIO] Detected distress sounds while guest is sick: '{transcript}'")
            _distress_responses = [
                "Yep, heard that. Breathe through the nose. You're okay.",
                "Still here. Not going anywhere. Water's in the sink when you're ready.",
                "That's it, get it out. No one's keeping score in here.",
                "I've cleaned worse pipes than this, trust me. You're doing great.",
                "Fun fact — this is still less scary than World 8. You got this.",
            ]
            _comfort = random.choice(_distress_responses)
            try:
                analyzed = analyze_text(_comfort)
                audio = await loop.run_in_executor(_tts_executor, lambda: tts.synthesize(analyzed["tts_text"]))
                await send_response(ws, analyzed["display_text"], audio,
                                    sound="coin", pose_hint="concerned/worried")
                state_current["_last_user_msg_time"] = time.time()
                state_current["_sick_checkin_time"] = time.time()
            except Exception as e:
                logger.error(f"Sick audio comfort failed: {e}")
            return

    logger.info(f"Heard: '{transcript}' from {speaker_info.get('name', 'unknown')}")
    state_current["_last_user_msg_time"] = time.time()

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
        "person_detected",
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
        state_current["_name_from_parsing"] = False  # Reset name parsing flag for new guest
        emotion_system.update(event="presence_enter")
        idle_behavior.reset_timer()
        # Reset per-conversation state in mario_prompt
        mario_prompt.reset_convo_temperature()
        mario_prompt.reset_achievements()
        mario_prompt.reset_collab_story()
        mario_prompt.reset_quiz()
        mario_prompt.reset_bookmarks()
        mario_prompt.reset_compliment()
        mario_prompt.reset_rhythm()
        mario_prompt.reset_flow()
        mario_prompt.reset_mood()
        mario_prompt.reset_inside_jokes()
        mario_prompt.reset_variety()
        mario_prompt.reset_chapter()
        mario_prompt.reset_challenge()
        mario_prompt.reset_deep_secrets()
        mario_prompt.reset_depth()
        mario_prompt.reset_nickname_evolution()
        mario_prompt.reset_debate()
        mario_prompt.reset_recap()
        mario_prompt.reset_meta()
        mario_prompt.reset_emotional_memory()
        mario_prompt.reset_rapid_fire()
        mario_prompt.reset_pacing()
        mario_prompt.reset_wyr()
        mario_prompt.reset_conspiracy()
        mario_prompt.reset_role_reversal()
        mario_prompt.reset_intensity()
        mario_prompt.reset_ttl()
        mario_prompt.reset_twist()
        mario_prompt.reset_fish()
        mario_prompt.reset_battle()
        mario_prompt.reset_impression()
        mario_prompt.reset_handshake()
        mario_prompt.reset_ranking()
        mario_prompt.reset_hypothetical()
        mario_prompt.reset_accent()
        mario_prompt.reset_story_request()
        mario_prompt.reset_sassy()
        mario_prompt.reset_trivia_challenge()
        mario_prompt.reset_escalating_compliment()
        mario_prompt.reset_song()
        mario_prompt.reset_fortune()
        mario_prompt.reset_friendship()
        mario_prompt.init_party_timer()
        mario_prompt.track_visitor()
        mario_prompt.reset_voice_switch()
        mario_prompt.reset_dare()
        mario_prompt.reset_bathroom_tip()
        mario_prompt.reset_question_chain()
        mario_prompt.reset_joke_scores()
        mario_prompt.reset_catchphrase_count()
        mario_prompt.reset_countdown()
        mario_prompt.reset_excuse()
        mario_prompt.reset_role()
        mario_prompt.reset_word_of_day()
        mario_prompt.reset_audience()
        mario_prompt.reset_reverse_psych()
        mario_prompt.reset_power_ranking()
        mario_prompt.reset_password()
        mario_prompt.reset_relay()
        mario_prompt.reset_time_capsule()
        mario_prompt.reset_competitive()
        mario_prompt.reset_emoji_mode()
        mario_prompt.reset_award()
        mario_prompt.reset_tongue_twister()
        mario_prompt.reset_alter_ego()
        mario_prompt.reset_handshake_evolution()
        mario_prompt.reset_did_you_know()
        mario_prompt.reset_recap_game()
        mario_prompt.reset_philosophy()
        mario_prompt.reset_skill_brag()
        mario_prompt.reset_gratitude()

        try:
            # Extract name from event payload if not already set (browser fallback)
            if state_current["speaker_name"] is None and event.get("name"):
                state_current["speaker_name"] = event["name"].strip()
                logger.info(f"[BROWSER_MEMORY] Got name from presence_enter payload: '{state_current['speaker_name']}'")

            # Try to identify by audio
            if event.get("audio"):
                audio_data = base64.b64decode(event["audio"])
                info = speaker_id.identify_speaker(audio_data)
                if not info["is_new"]:
                    state_current["speaker_name"] = info["name"]
                    state_current["speaker_id"] = info["speaker_id"]
                    memory.record_visit(info["speaker_id"])

            # Browser fallback: look up or create speaker_id by name if not identified by voice
            if state_current["speaker_id"] is None and state_current["speaker_name"]:
                person = memory.find_person_by_name(state_current["speaker_name"])
                if person:
                    state_current["speaker_id"] = person["id"]
                    memory.record_visit(person["id"])
                    logger.info(f"[BROWSER_MEMORY] Matched '{state_current['speaker_name']}' to speaker_id={person['id']} (visits={person['visit_count']})")
                else:
                    # Create a virtual speaker_id for browser users (name-based hash)
                    import hashlib
                    virtual_id = int(hashlib.md5(state_current["speaker_name"].lower().encode()).hexdigest()[:8], 16)
                    state_current["speaker_id"] = virtual_id
                    memory.register_person(virtual_id, state_current["speaker_name"])
                    logger.info(f"[BROWSER_MEMORY] Created virtual speaker_id={virtual_id} for '{state_current['speaker_name']}'")

            # Record visit in party stats
            visit_id = party_stats.record_enter(
                person_id=state_current["speaker_id"],
                person_name=state_current["speaker_name"],
            )
            state_current["current_visit_id"] = visit_id
            party_stats.record_event("enter", state_current["speaker_name"])

            # Send leaderboard update on new visitor
            asyncio.create_task(_send_leaderboard_event(ws))

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

            # Webcam face recognition fallback — if we detected a face but don't have audio ID
            if not state_current["speaker_name"] and state_current.get("detected_guest"):
                state_current["speaker_name"] = state_current["detected_guest"]
                logger.info(f"[WEBCAM] Using face-detected guest name: {state_current['speaker_name']}")

            if state_current["speaker_name"]:
                event_type_greeting = "enter_known"
                memories = memory.get_memories_for_context(state_current["speaker_id"], current_text="greeting returning guest")
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

                # Context-aware returning greetings — reference last conversation
                recent_topics = memory.get_recent_conversations(state_current["speaker_id"], limit=1)
                if recent_topics:
                    ctx.append({"role": "system", "content": f"Last time {state_current['speaker_name']} was here, you were talking about: {recent_topics[0]}. Reference this!"})

            elif total == 1:
                ctx = mario_prompt.build_context(event="first_visitor")
            elif total in (10, 25, 50, 100):
                ctx = mario_prompt.build_context(event="milestone_visit", count=total)
            else:
                ctx = mario_prompt.build_context(event="enter_unknown")

            _inject_birthday_always_on(ctx)
            ctx.append({"role": "system", "content": emotion_system.get_prompt_addition()})
            # Idle acknowledgment — reference what Mario was doing before they arrived
            last_idle = state_current.get("_last_idle_action", "")
            if last_idle:
                ctx.append({"role": "system", "content": f"You were just: '{last_idle}' — briefly mention what you were up to when they walked in!"})
            if crew_ctx:
                ctx.append({"role": "system", "content": crew_ctx})

            # Birthday VIP — inject special greeting context
            _greeting_name = state_current.get("speaker_name", "")
            if birthday_vip.is_configured() and birthday_vip.is_birthday_person(_greeting_name):
                vip_greeting = birthday_vip.get_special_greeting(_greeting_name)
                if vip_greeting:
                    ctx.append({"role": "system", "content": f"🎂 {vip_greeting} Make your greeting EXTRA celebratory!"})
                vip_ctx = birthday_vip.get_vip_prompt_injection()
                if vip_ctx:
                    ctx.append({"role": "system", "content": vip_ctx})

            # Register guest in gossip system so later guests know who visited
            if state_current.get("speaker_id") and state_current.get("speaker_name"):
                party_gossip._guest_names[state_current["speaker_id"]] = state_current["speaker_name"]

            # GOSSIP on greeting — share juicy tidbits from earlier visitors
            greeting_gossip = party_gossip.get_gossip_for_guest(
                current_speaker_id=state_current.get("speaker_id"),
                current_name=state_current.get("speaker_name"),
                count=1,
                gossip_aggression=(_get_night_phase_modifier() or {}).get("gossip_aggression", 0.3),
            )
            if greeting_gossip and random.random() < 0.5:
                ctx.append({"role": "system", "content": f"[GOSSIP]: You have gossip! {greeting_gossip[0]} Weave it into your greeting naturally!"})

            # Guest title — assign/retrieve a fun title
            if state_current.get("speaker_id"):
                title = party_gossip.assign_title(
                    state_current["speaker_id"],
                    state_current.get("speaker_name", "friend"),
                )
                if title and random.random() < 0.3:
                    ctx.append({"role": "system", "content": f"Their official title is: '{title}'. Use it dramatically!"})

            # Party narrative — reference the ongoing story of tonight
            narrative = party_gossip.get_party_narrative_hint()
            if narrative and random.random() < 0.25:
                ctx.append({"role": "system", "content": narrative})

            # Mood-reactive greeting — adapt energy to party phase
            now = datetime.now()
            party_hrs = (time.time() - party_stats._party_start_time) / 3600 if hasattr(party_stats, '_party_start_time') else 0
            greeting_mood = mario_prompt.get_greeting_mood(now.hour, party_hrs)
            if greeting_mood:
                ctx.append({"role": "system", "content": f"[PARTY MOOD]: {greeting_mood}"})

            response_text = await asyncio.wait_for(llm.generate_response(ctx), timeout=30.0)
            response_text = filter_response(response_text)

            # Visit milestones — special callout for returning guests at key visit counts
            if state_current.get("speaker_name") and state_current.get("speaker_id"):
                _milestone_info = memory.get_person_info(state_current["speaker_id"])
                _milestone_count = _milestone_info["visit_count"] if _milestone_info else 1
                _milestone_name = state_current["speaker_name"]
                milestone_prefix = ""
                if _milestone_count == 2:
                    milestone_prefix = f"Welcome BACK {_milestone_name}! I missed you! "
                elif _milestone_count == 5:
                    milestone_prefix = f"It's {_milestone_name} again! That's your FIFTH visit tonight! You're a LEGEND! "
                elif _milestone_count == 10:
                    milestone_prefix = f"TEN TIMES?! {_milestone_name}, you live here now! I'm giving you a key! "
                elif _milestone_count >= 15:
                    milestone_prefix = f"{_milestone_name}! You've been here {_milestone_count} times! At this point you're my roommate! "
                if milestone_prefix:
                    response_text = milestone_prefix + response_text

            if not state_current["speaker_name"]:
                response_text += " What's-a your name, friend?"

            analyzed = analyze_text(response_text)
            loop = asyncio.get_event_loop()
            voice_params = emotion_system.get_voice_params()
            if analyzed.get("energy") == "high":
                voice_params["rate"] = "+15%"
                voice_params["pitch"] = "+5Hz"
            response_audio = await loop.run_in_executor(_tts_executor, lambda: tts.synthesize(
                analyzed["tts_text"], rate=voice_params.get("rate"), pitch=voice_params.get("pitch")))
            # Send with retry on failure
            for _attempt in range(2):
                try:
                    await send_response(ws, analyzed["display_text"], response_audio, sound="greeting",
                                        emotion=emotion_system.current, pose_hint=analyzed["pose_hint"] or "greeting/wave_high",
                                        particle_effect="confetti")
                    break
                except Exception as send_err:
                    if _attempt == 0:
                        logger.warning(f"[GREETING] Send failed, retrying: {send_err}")
                        await asyncio.sleep(0.5)
                    else:
                        logger.error(f"[GREETING] Send failed after retry: {send_err}")
        except Exception as e:
            logger.error(f"[DEBUG_SERVER] presence_enter greeting failed: {e}")
            # Fallback: send text-only greeting so user isn't ignored
            try:
                await send_response(ws, "Hey! Welcome to Mario's-a bathroom! Wahoo!", None,
                                    sound="greeting", pose_hint="greeting/wave_high")
            except Exception:
                pass
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

        exchange_count = len(state_current.get("conversation_history", [])) // 2

        try:
            if state_current["speaker_name"]:
                ctx = mario_prompt.build_context(
                    speaker_name=state_current["speaker_name"],
                    event="exit_known",
                )
            else:
                ctx = mario_prompt.build_context(event="exit_unknown")

            _inject_birthday_always_on(ctx)
            ctx.append({"role": "system", "content": emotion_system.get_prompt_addition()})

            # Add visit recap for personalized goodbye
            recap = mario_prompt.build_visit_recap(state_current["conversation_history"])
            if recap:
                ctx.append({"role": "system", "content": f"Recap: {recap}"})
            else:
                # Dynamic goodbye based on conversation topics
                topics = state_current.get("_session_topics", set())
                goodbye = mario_prompt.get_dynamic_goodbye(exchange_count, topics)
                farewell_drama = mario_prompt.get_farewell_drama(exchange_count)
                exit_poll = mario_prompt.get_exit_poll()
                ctx.append({"role": "system", "content": f"{farewell_drama} | {goodbye} | {exit_poll}"})

            # Neuro-sama dramatic farewell energy
            drama_farewells = [
                "Make this goodbye DRAMATIC. Like it's the end of an anime episode. Music swells. Single tear.",
                "Give them a prophecy about the rest of their night. Be dramatic but funny.",
                "Pretend this is the hardest goodbye you've ever had to do. Even if you just met them.",
                "Give them a final score/rating for their bathroom visit. Be a generous but honest judge.",
                "Assign them a quest for the rest of the party. Something silly but specific.",
            ]
            if random.random() < 0.4:
                ctx.append({"role": "system", "content": random.choice(drama_farewells)})

            # Party gossip stats on exit
            stats_gossip = party_gossip.get_party_stats_gossip(
                party_stats.get_stats().get("total_visits", 0))
            if stats_gossip and random.random() < 0.3:
                ctx.append({"role": "system", "content": f"[GOSSIP]: {stats_gossip}"})

            # 25% chance Mario asks for a quick rating in the farewell
            if random.random() < 0.25 and exchange_count >= 3:
                ctx.append({"role": "system", "content":
                    "End your farewell by asking them to rate their bathroom experience 1-10. "
                    "Make it funny — 'Rate this bathroom visit! Was it a 10 out of 10? Be honest, I can take it!'"
                })

            response_text = await asyncio.wait_for(llm.generate_response(ctx), timeout=30.0)
            response_text = filter_response(response_text)

            # Fallback farewell if LLM returned empty
            if not response_text or not response_text.strip():
                name = state_current.get("speaker_name", "friend")
                response_text = random.choice([
                    f"Ciao, {name}! Thanks for hanging out with Mario!",
                    f"See you next time, {name}! Don't forget to wash your hands!",
                    f"Wahoo! Bye bye, {name}! Come back soon!",
                    f"It's-a been fun, {name}! Until we meet again!",
                ])
            analyzed = analyze_text(response_text)
            loop = asyncio.get_event_loop()
            voice_params = emotion_system.get_voice_params()
            if analyzed.get("energy") == "high":
                voice_params["rate"] = "+15%"
                voice_params["pitch"] = "+5Hz"
            response_audio = await loop.run_in_executor(_tts_executor, lambda: tts.synthesize(
                analyzed["tts_text"], rate=voice_params.get("rate"), pitch=voice_params.get("pitch")))
            await send_response(ws, analyzed["display_text"], response_audio, sound="goodbye",
                                emotion=emotion_system.current, pose_hint=analyzed["pose_hint"] or "greeting/farewell")

            # Send hand wash reminder as its OWN separate TTS chunk after a delay
            await asyncio.sleep(1.0)
            wash_reminder = idle_behavior.get_hand_wash_reminder()
            try:
                wash_audio = await loop.run_in_executor(
                    _tts_executor, lambda: tts.synthesize(wash_reminder))
                await send_response(ws, wash_reminder, wash_audio,
                                    emotion="excited", pose_hint="emotion/surprise")
            except Exception as wash_err:
                logger.warning(f"Hand wash reminder TTS failed: {wash_err}")
        except Exception as e:
            logger.error(f"[DEBUG_SERVER] presence_exit farewell failed: {e}")
            # Emergency fallback farewell
            try:
                name = state_current.get("speaker_name", "friend")
                fallback = f"Ciao, {name}! Thanks for visiting Mario!"
                fallback_audio = await loop.run_in_executor(_tts_executor, lambda: tts.synthesize(fallback))
                await send_response(ws, fallback, fallback_audio, sound="goodbye",
                                    emotion="happy", pose_hint="greeting/farewell")
            except Exception:
                pass

        # Record dramatic exit moment for gossip
        exit_name = state_current.get("speaker_name", "someone")
        if exchange_count >= 5:
            # Find what they talked about for richer gossip
            topics = list(state_current.get("_session_topics", set()))[:3]
            topic_str = ", ".join(topics) if topics else "deep bathroom philosophy"
            party_gossip.add_dramatic_moment(
                f"{exit_name} had an EPIC {exchange_count}-exchange conversation about {topic_str}!")
        elif exchange_count >= 3:
            party_gossip.add_dramatic_moment(
                f"{exit_name} had a solid chat and left with a wave")
        elif exchange_count == 1:
            party_gossip.add_dramatic_moment(
                f"{exit_name} popped in, said ONE thing, and vanished. Speed run!")
        elif exchange_count == 0:
            party_gossip.add_dramatic_moment(
                f"{exit_name} walked in, said NOTHING, and left. Mysterious!")

        # Save emotion memory before exit
        if state_current["speaker_id"]:
            memory.save_emotion(state_current["speaker_id"], emotion_system.current)

        # Reset state
        state_current["speaker_name"] = None
        state_current["speaker_id"] = None
        state_current["conversation_history"] = []
        state_current["current_visit_id"] = None
        state_current["enter_time"] = None
        state_current["_name_from_parsing"] = False
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
            try:
                loop = asyncio.get_event_loop()
                celebrate_audio = await loop.run_in_executor(_tts_executor, lambda: tts.synthesize(celebrate))
                await send_response(ws, celebrate, celebrate_audio, sound="oneup", emotion="excited")
            except Exception as e:
                logger.error(f"Registration celebration TTS failed: {e}")
                await send_response(ws, celebrate, None, sound="oneup", emotion="excited")

    elif event_type == "set_name":
        name = event.get("name", "").strip()
        if name:
            state_current["speaker_name"] = name
            logger.info(f"[BROWSER_MEMORY] set_name: '{name}'")

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
            # Match audio handler: keep guard active briefly after response
            # to prevent idle TTS from firing immediately after text response
            await asyncio.sleep(2.0)
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

    elif event_type == "person_detected":
        face_enc = event.get("face_encoding")
        if face_enc and _face_memory and isinstance(face_enc, list) and len(face_enc) == 128:
            try:
                enc_array = np.array(face_enc, dtype=np.float64)
                if np.any(np.isnan(enc_array)) or np.any(np.isinf(enc_array)):
                    logger.warning("[WEBCAM] Invalid face encoding values (NaN/Inf)")
                else:
                    match = _face_memory.find_match(enc_array)
                    if match and match.get("name"):
                        name = match["name"]
                        visits = match.get("visit_count", 0)
                        state_current["detected_guest"] = name
                        state_current["guest_visits"] = visits
                        logger.info(f"[WEBCAM] Recognized returning guest: {name} (visits: {visits})")
                    else:
                        state_current["detected_guest"] = None
                        logger.info("[WEBCAM] New guest detected (no face match)")
            except Exception as e:
                logger.error(f"[WEBCAM] Face matching error: {e}")
        else:
            if DEBUG_SERVER:
                logger.debug(f"[WEBCAM] Person detected (no face encoding)")


async def _handle_text_input(ws: WebSocket, text: str):
    """Process text input — rate-limited, then delegates to shared pipeline."""
    now = time.time()
    async with _state_lock:
        if now - state_current["_last_text_input_time"] < 2.0:
            logger.warning(f"Text input rate-limited: '{text[:50]}'")
            return
        state_current["_last_text_input_time"] = now
        state_current["_last_user_msg_time"] = now

    logger.info(f"Text input: '{text}'")

    try:
        await ws.send_json({"type": "state", "thinking": True, "subtitle": text})
    except Exception:
        pass

    try:
        await _generate_and_send_response(ws, text, source="text", start_time=now)
    except Exception as e:
        logger.error(f"[TEXT_INPUT_ERROR] Exception in response pipeline for '{text[:50]}': {e}", exc_info=True)
        try:
            await ws.send_json({"type": "mario_response", "text": f"Mama mia! Something went wrong: {e}", "emotion": "confused"})
        except Exception:
            pass


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
                        pose_hint: str = None, response_time: float = None,
                        particle_effect: str = None,
                        chunk_index: int = None, total_chunks: int = None,
                        is_last: bool = None):
    """Send Mario's response (text + audio + metadata) to the client."""
    # Trigger server-side sound effect (non-blocking, fire-and-forget)
    if sound:
        sound_events.trigger(sound)
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
    if particle_effect:
        msg["particle_effect"] = particle_effect
    # Sentence streaming metadata
    if chunk_index is not None:
        msg["chunk_index"] = chunk_index
        msg["total_chunks"] = total_chunks
        msg["is_last"] = is_last

    for attempt in range(2):
        try:
            await ws.send_json(msg)
            if audio and len(audio) > 0:
                await ws.send_bytes(audio)
            return
        except Exception as e:
            if attempt == 0:
                logger.warning(f"send_response attempt 1 failed: {e}, retrying...")
                await asyncio.sleep(0.1)
            else:
                logger.error(f"send_response failed after retry: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=server_config.get("host", "0.0.0.0"),
        port=server_config.get("port", 8765),
    )
