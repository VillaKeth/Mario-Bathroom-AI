"""Text-to-speech with RVC v2 Mario voice conversion.

Pipeline (FAST_MODE=True):  Edge TTS (fast base ~1s) → RVC v2 (Mario voice)
Pipeline (FAST_MODE=False): XTTS v2 (quality base ~10-60s) → RVC v2 (Mario voice)

RVC v2 converts any voice to match Charles Martinet's Mario (500 epoch TITAN model).
Edge TTS generates the base speech quickly; RVC does the heavy lifting for Mario's voice.

Speed optimizations:
- FAST_MODE skips XTTS loading entirely (saves 20s startup + 2GB VRAM)
- Uses 'pm' f0 method (Praat, fast) instead of 'rmvpe' (neural net, slow)
- Pre-loads RVC model at startup
"""

import io
import uuid
import wave
import logging
import asyncio
import tempfile
import os
import time
import threading
import numpy as np
import soundfile as sf
from scipy import signal as scipy_signal
from scipy.io import wavfile
from contextlib import nullcontext
import hardware

# PyTorch is required for RVC voice conversion but optional for Edge TTS fallback
_TORCH_AVAILABLE = False
try:
    import torch
    import torchaudio
    _TORCH_AVAILABLE = True
except ImportError:
    torch = None
    torchaudio = None
    logging.getLogger(__name__).warning(
        "[tts] PyTorch not installed — RVC Mario voice disabled. "
        "Edge TTS fallback will be used. Install with: pip install torch torchaudio"
    )

logger = logging.getLogger(__name__)

# Load debug flag from config (default: True)
def _load_debug_flag():
    try:
        _cfg_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")
        if os.path.exists(_cfg_path):
            import json as _json
            with open(_cfg_path, encoding="utf-8") as _f:
                return _json.load(_f).get("server", {}).get("debug_tts", True)
    except Exception:
        pass
    return True

DEBUG_TTS = _load_debug_flag()

# --- Monkey-patches (MUST run before importing TTS) ---
if _TORCH_AVAILABLE:
    _original_torch_load = torch.load
    def _patched_torch_load(*args, **kwargs):
        kwargs.setdefault("weights_only", False)
        return _original_torch_load(*args, **kwargs)
    torch.load = _patched_torch_load

    def _soundfile_torchaudio_load(filepath, *args, **kwargs):
        data, sr = sf.read(str(filepath), dtype="float32")
        if data.ndim == 1:
            data = data[np.newaxis, :]
        else:
            data = data.T
        return torch.from_numpy(data), sr
    torchaudio.load = _soundfile_torchaudio_load

# --- XTTS v2 state ---
_xtts_model = None
_xtts_available = False
_gpt_cond_latents = None
_speaker_embedding = None
XTTS_SAMPLE_RATE = 24000

# --- RVC state ---
_rvc_model = None
_rvc_available = False

# RVC model paths — Nintendo Switch Era Mario (Charles Martinet, trained on MK8/NSMBU/Odyssey/Party)
RVC_MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "mario_models_new", "MarioSwitch", "SuperMario-NintendoSwitchEra.pth")
RVC_INDEX_PATH = os.path.join(os.path.dirname(__file__), "..", "mario_models_new", "MarioSwitch", "added_IVF423_Flat_nprobe_1_SuperMario-NintendoSwitchEra_v2.index")

# Curated 30s reference — best quality segment from full sentences
MARIO_REF_PATH = os.path.join(os.path.dirname(__file__), "data", "mario_reference_sentences_30s.wav")
MARIO_REF_FALLBACK = os.path.join(os.path.dirname(__file__), "data", "mario_reference_sentences.wav")

# Post-synthesis tuning
MARIO_PITCH_SEMITONES = 0  # No pitch shift — let RVC model handle voice character
MARIO_SPEED_FACTOR = 1.0  # Normal speed
USE_RVC = True  # Use RVC for Mario voice conversion
RVC_F0_UP_KEY = 12  # Pitch UP 12 semitones (full octave) — aggressive Mario pitch
RVC_INDEX_RATE = 0.95  # Very high = max Mario character from training data
RVC_PROTECT = 0.15  # Low = aggressive voice conversion
RVC_F0_METHOD = "rmvpe"  # Deep learning pitch tracking — best quality

# --- GPT-SoVITS state ---
_sovits_process = None
_sovits_available = False
_sovits_lock = threading.Lock()
_sovits_restart_count = 0
_sovits_max_restarts = 10  # Auto-restart up to 10 times before giving up

# Background regeneration queue (replaces thread-per-request)
import queue as _queue_mod
_sovits_regen_queue = _queue_mod.Queue(maxsize=50)  # Cap pending regen jobs
_sovits_worker_thread = None  # Single worker consuming from queue

# GPU contention guard: bg worker only runs when main thread hasn't used GPU recently
_gpu_busy = threading.Event()  # Set = GPU free, Clear = GPU busy
_gpu_busy.set()  # Start as free
_last_synth_time = 0.0  # Timestamp of last Edge+RVC synthesis completion
# _GPU_IDLE_THRESHOLD set above via hardware.resolve()

# Precache state — allows user requests to preempt precache
_precache_done = threading.Event()  # Set when precache completes
_precache_active = False  # True while precache is synthesizing
_user_tts_waiting = threading.Event()  # Set when a user TTS call is waiting for RVC lock
_idle_precache_paused = threading.Event()  # Set to pause idle precache (e.g. during testing)
_idle_behavior_ref = None  # Set by main.py to provide character-specific idle pools for precache

# GPT-SoVITS venv python path
SOVITS_PYTHON = os.path.join(os.path.dirname(os.path.dirname(__file__)), "gpt_sovits_env", "Scripts", "python.exe")
SOVITS_SERVER_SCRIPT = os.path.join(os.path.dirname(__file__), "gpt_sovits_server.py")

# --- Modular GPT-SoVITS (per-character zero-shot) ---
# Characters with a fine-tuned model in mario_models_new/GPT_SoVITS_<Name>/ use it;
# everyone else uses the shared v2 base weights + their own reference clip + transcript.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
SOVITS_V2_BASE_DIR = os.path.join(_PROJECT_ROOT, "gpt_sovits_repo", "GPT_SoVITS",
                                  "pretrained_models", "gsv-v2final-pretrained")
SOVITS_V2_GPT = os.path.join(SOVITS_V2_BASE_DIR, "s1bert25hz-5kh-longer-epoch=12-step=369668.ckpt")
SOVITS_V2_SOVITS = os.path.join(SOVITS_V2_BASE_DIR, "s2G2333k.pth")

# Active character voice config (set by main.py via set_voice_config()).
_voice_cfg = {}
_voice_char_name = "mario"


def _voice_cache_tag() -> str:
    """Per-character timbre token for cache keys.

    Two characters can share the SAME Edge voice (e.g. Mario and Jax both use
    en-US-GuyNeural) yet have completely different final timbres because Mario
    runs RVC voice conversion and the others do not. Keying the cache on
    EDGE_VOICE alone makes them collide — a non-Mario character would replay
    Mario's RVC'd disk-cached clip (e.g. the "Let me think" filler). Including
    the character name guarantees each character only ever hits its own audio.
    """
    return _voice_char_name or "mario"


def set_voice_config(voice_config: dict, character_name: str = "mario"):
    """Wire the active character's voice config into the TTS engine so GPT-SoVITS
    clones THIS character (not Mario). Called once at character load."""
    global _voice_cfg, _voice_char_name, EDGE_VOICE, RATE, PITCH_OFFSET, USE_RVC
    _voice_cfg = voice_config or {}
    _voice_char_name = (character_name or "mario").lower()

    # Point the Edge fast path at THIS character's voice. Without this, the
    # Edge fallback + thinking fillers speak in Mario's default male voice
    # (GuyNeural) — making non-Mario characters' fillers sound Mario-esque.
    if _voice_cfg.get("edge_voice"):
        EDGE_VOICE = _voice_cfg["edge_voice"]
    if _voice_cfg.get("rate"):
        RATE = _voice_cfg["rate"]
    if _voice_cfg.get("pitch"):
        PITCH_OFFSET = _voice_cfg["pitch"]
    # RVC converts Edge audio to MARIO's timbre — only correct for Mario. Any
    # other character must skip RVC or every Edge/filler line sounds like Mario.
    USE_RVC = (_voice_char_name == "mario")

    logger.info(
        f"[TTS] voice config set for '{_voice_char_name}': "
        f"engine={_voice_cfg.get('preferred_engine')} edge_voice={EDGE_VOICE} "
        f"rvc={USE_RVC} ref={'yes' if _voice_cfg.get('reference_audio') else 'no'} "
        f"prompt={'yes' if _voice_cfg.get('prompt_text') else 'no'}"
    )

def _resolve_sovits_models(char_name: str):
    """Return (gpt_path, sovits_path, is_finetune) for the active character.
    A per-character fine-tune (e.g. Mario) wins; otherwise the v2 base weights.

    Tries exact GPT_SoVITS_<Name> first, then a PREFIX match so an identity name
    that differs from the model folder still resolves (e.g. identity 'March' ->
    'GPT_SoVITS_March7th'). Without the prefix fallback a mismatch silently fell
    back to the generic base voice instead of the trained one."""
    models_root = os.path.join(_PROJECT_ROOT, "mario_models_new")
    title = char_name.capitalize()
    candidates = [f"GPT_SoVITS_{title}"]
    if os.path.isdir(models_root):
        # Prefix match: GPT_SoVITS_March* catches GPT_SoVITS_March7th
        for d in sorted(os.listdir(models_root)):
            if d.lower().startswith(f"gpt_sovits_{char_name.lower()}") and d not in candidates:
                candidates.append(d)
    for name in candidates:
        ft_dir = os.path.join(models_root, name)
        if os.path.isdir(ft_dir):
            ckpts = [f for f in os.listdir(ft_dir) if f.endswith(".ckpt")]
            pths = [f for f in os.listdir(ft_dir) if f.endswith(".pth")]
            if ckpts and pths:
                return os.path.join(ft_dir, ckpts[0]), os.path.join(ft_dir, pths[0]), True
    return SOVITS_V2_GPT, SOVITS_V2_SOVITS, False

# --- Speed mode ---
# "hybrid" = Edge+RVC for instant response, GPT-SoVITS regenerates in background (RECOMMENDED)
# "sovits" = GPT-SoVITS only (best quality, ~3-10s latency)
# "edge" = Edge TTS + RVC only (fast, ~1.5s)
# Can be overridden via config.json: {"server": {"tts_mode": "hybrid"}}
_tts_config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")
_tts_config_fast = True
_tts_mode = "hybrid"
_tts_cfg = {}
if os.path.exists(_tts_config_path):
    try:
        import json as _json
        with open(_tts_config_path, encoding="utf-8") as _f:
            _tts_cfg = _json.load(_f).get("server", {})
            _tts_config_fast = _tts_cfg.get("tts_fast_mode", True)
            _tts_mode = _tts_cfg.get("tts_mode", "hybrid")
    except Exception:
        pass
FAST_MODE = _tts_config_fast
TTS_MODE = _tts_mode  # "hybrid", "sovits", "edge", or "xtts"

# Hardware-aware performance settings
_GPU_IDLE_THRESHOLD = hardware.resolve("gpu_idle_threshold", _tts_cfg.get("gpu_idle_threshold", "auto"))
_PRECACHE_PAUSE = hardware.resolve("precache_pause_seconds", _tts_cfg.get("precache_pause_seconds", "auto"))
_MAX_CACHE = hardware.resolve("max_cache_memory", _tts_cfg.get("max_cache_memory", "auto"))
logger.info(f"[TTS] Performance: gpu_idle={_GPU_IDLE_THRESHOLD}s, precache_pause={_PRECACHE_PAUSE}s, max_cache={_MAX_CACHE}")

# --- XTTS inference params (defaults — natural sounding) ---
XTTS_TEMPERATURE = 0.65
XTTS_TOP_K = 50
XTTS_TOP_P = 0.85
XTTS_REP_PENALTY = 2.0
XTTS_COND_LEN = 6

# --- Edge TTS settings (fallback only) ---
EDGE_VOICE = "en-US-GuyNeural"
EDGE_PITCH_SHIFT = 0
RATE = "+35%"  # Faster speech for Mario energy
PITCH_OFFSET = "+0Hz"

# --- Audio cache for instant playback (size-aware LRU) ---

class SizeLimitedCache:
    """LRU cache with total byte size limit, not just entry count."""

    def __init__(self, max_bytes: int = 500 * 1024 * 1024, max_entries: int = 2000):
        self._data: dict[str, bytes] = {}
        self._sizes: dict[str, int] = {}
        self._order: list[str] = []  # oldest-first for LRU eviction
        self.max_bytes = max_bytes
        self.max_entries = max_entries
        self.total_bytes = 0
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> bytes | None:
        val = self._data.get(key)
        if val is not None:
            self._hits += 1
            # Move to end (most recently used)
            try:
                self._order.remove(key)
            except ValueError:
                pass
            self._order.append(key)
            return val
        self._misses += 1
        return None

    def __contains__(self, key: str) -> bool:
        return key in self._data

    def __setitem__(self, key: str, value: bytes):
        self.set(key, value)

    def __getitem__(self, key: str) -> bytes:
        val = self._data.get(key)
        if val is None:
            raise KeyError(key)
        return val

    def __len__(self) -> int:
        return len(self._data)

    def set(self, key: str, value: bytes):
        val_size = len(value) if value else 0
        # Remove old if replacing
        if key in self._data:
            self.total_bytes -= self._sizes.get(key, 0)
            del self._data[key]
            del self._sizes[key]
            try:
                self._order.remove(key)
            except ValueError:
                pass

        # Evict LRU entries until we have space
        while (self.total_bytes + val_size > self.max_bytes or len(self._data) >= self.max_entries) and self._order:
            evict_key = self._order.pop(0)
            evicted_size = self._sizes.pop(evict_key, 0)
            self._data.pop(evict_key, None)
            self.total_bytes -= evicted_size

        self._data[key] = value
        self._sizes[key] = val_size
        self._order.append(key)
        self.total_bytes += val_size

    def pop(self, key: str, default=None):
        if key in self._data:
            val = self._data.pop(key)
            self.total_bytes -= self._sizes.pop(key, 0)
            try:
                self._order.remove(key)
            except ValueError:
                pass
            return val
        return default

    def keys(self):
        return self._data.keys()

    def clear(self):
        self._data.clear()
        self._sizes.clear()
        self._order.clear()
        self.total_bytes = 0

    @property
    def stats(self) -> dict:
        return {
            "entries": len(self._data),
            "total_bytes": self.total_bytes,
            "total_mb": round(self.total_bytes / (1024 * 1024), 1),
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(self._hits / max(1, self._hits + self._misses) * 100, 1),
        }


_audio_cache = SizeLimitedCache(max_bytes=500 * 1024 * 1024, max_entries=2000)
_cache_order = []  # Kept for backward compat but SizeLimitedCache handles ordering internally
MAX_CACHE_SIZE = _MAX_CACHE
_cache_hits = 0
_cache_misses = 0
_rvc_lock = threading.Lock()  # Serialize RVC GPU calls to prevent contention
_cache_lock = threading.Lock()  # Protects _audio_cache and _cache_order from concurrent access
_edge_executor = None  # Reusable executor for Edge TTS async-in-sync calls

# Tiny silent WAV for empty text guard (inline — _make_dummy_wav defined later)
def _make_silence_wav():
    _buf = io.BytesIO()
    with wave.open(_buf, "wb") as _wf:
        _wf.setnchannels(1); _wf.setsampwidth(2); _wf.setframerate(22050)
        _wf.writeframes(np.zeros(2205, dtype=np.int16).tobytes())
    return _buf.getvalue()
_EMERGENCY_SILENCE = _make_silence_wav()
del _make_silence_wav

# Disk cache for TTS audio persistence across restarts
_DISK_CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "server", "data", "tts_cache")

def _load_disk_cache():
    """Load cached TTS audio from disk at startup."""
    if not os.path.exists(_DISK_CACHE_DIR):
        return
    import hashlib
    loaded = 0
    for fname in os.listdir(_DISK_CACHE_DIR):
        if not fname.endswith(".wav"):
            continue
        key_file = os.path.join(_DISK_CACHE_DIR, fname.replace(".wav", ".key"))
        if not os.path.exists(key_file):
            continue
        try:
            with open(key_file, "r", encoding="utf-8") as f:
                cache_key = f.read().strip()
            with open(os.path.join(_DISK_CACHE_DIR, fname), "rb") as f:
                wav_bytes = f.read()
            if wav_bytes and cache_key:
                _audio_cache[cache_key] = wav_bytes
                _cache_order.append(cache_key)
                loaded += 1
        except Exception:
            continue
    if loaded > 0:
        logger.info(f"[DEBUG_TTS] disk cache: loaded {loaded} entries from {_DISK_CACHE_DIR}")


def purge_stale_cache() -> int:
    """Scan disk cache and delete entries whose text produces a different key after _preclean_tts_text().

    Returns the number of stale entries purged.
    """
    import hashlib
    if not os.path.exists(_DISK_CACHE_DIR):
        logger.info("[DEBUG_TTS] purge_stale_cache: no disk cache directory")
        return 0
    purged = 0
    for fname in os.listdir(_DISK_CACHE_DIR):
        if not fname.endswith(".key"):
            continue
        key_path = os.path.join(_DISK_CACHE_DIR, fname)
        wav_path = os.path.join(_DISK_CACHE_DIR, fname.replace(".key", ".wav"))
        try:
            with open(key_path, "r", encoding="utf-8") as f:
                original_key = f.read().strip()
            if not original_key:
                continue
            # Parse cache key. Current format is
            #   {char_tag}:{voice}:{text}:{rate}:{pitch}
            # but legacy entries are {voice}:{text}:{rate}:{pitch}. Rate and
            # pitch are always the last two segments; the prefix (everything
            # before the text) is preserved verbatim so the rebuilt key keeps
            # whatever tag/voice the original had — only the text is re-cleaned.
            parts = original_key.split(":")
            if len(parts) < 4:
                continue
            pitch = parts[-1]   # e.g. "+0Hz"
            rate = parts[-2]    # e.g. "+0%"
            # Detect a leading character tag: a 5+ part key whose 2nd segment
            # looks like an Edge voice (contains a hyphen, e.g. en-US-GuyNeural).
            if len(parts) >= 5 and "-" in parts[1]:
                prefix = f"{parts[0]}:{parts[1]}"   # char_tag:voice
                text = ":".join(parts[2:-2])
            else:
                prefix = parts[0]                   # legacy voice-only prefix
                text = ":".join(parts[1:-2])
            cleaned_text = _preclean_tts_text(text)
            rebuilt_key = f"{prefix}:{cleaned_text}:{rate}:{pitch}"
            if rebuilt_key != original_key:
                if os.path.exists(wav_path):
                    os.remove(wav_path)
                os.remove(key_path)
                purged += 1
        except Exception as e:
            logger.warning(f"[DEBUG_TTS] purge_stale_cache: error processing {fname}: {e}")
            continue
    logger.info(f"[DEBUG_TTS] purge_stale_cache: purged {purged} stale entries from disk cache")
    return purged


def clear_all_cache(include_disk: bool = False):
    """Clear all TTS caches (in-memory and optionally disk).

    Args:
        include_disk: If True, also delete all files in the disk cache directory.
    """
    global _cache_hits, _cache_misses
    _audio_cache.clear()
    _cache_order.clear()
    _cache_hits = 0
    _cache_misses = 0
    cleared_disk = 0
    if include_disk and os.path.exists(_DISK_CACHE_DIR):
        for fname in os.listdir(_DISK_CACHE_DIR):
            fpath = os.path.join(_DISK_CACHE_DIR, fname)
            try:
                os.remove(fpath)
                cleared_disk += 1
            except Exception:
                continue
    logger.info(
        f"[DEBUG_TTS] clear_all_cache: in-memory cache cleared, stats reset"
        + (f", {cleared_disk} disk files deleted" if include_disk else "")
    )


def _save_to_disk_cache(cache_key: str, wav_bytes: bytes):
    """Save a cache entry to disk for persistence across restarts."""
    try:
        import hashlib
        os.makedirs(_DISK_CACHE_DIR, exist_ok=True)
        key_hash = hashlib.md5(cache_key.encode()).hexdigest()[:16]
        wav_path = os.path.join(_DISK_CACHE_DIR, f"{key_hash}.wav")
        key_path = os.path.join(_DISK_CACHE_DIR, f"{key_hash}.key")
        with open(wav_path, "wb") as f:
            f.write(wav_bytes)
        with open(key_path, "w", encoding="utf-8") as f:
            f.write(cache_key)
    except Exception as e:
        if DEBUG_TTS:
            logger.warning(f"[DEBUG_TTS] disk cache: save failed: {e}")

def _is_disk_cached(cache_key: str) -> bool:
    """Check if a cache key has a disk cache entry (GPT-SoVITS quality)."""
    try:
        import hashlib
        key_hash = hashlib.md5(cache_key.encode()).hexdigest()[:16]
        return os.path.exists(os.path.join(_DISK_CACHE_DIR, f"{key_hash}.wav"))
    except Exception:
        return False
CACHED_PHRASES = [
    # Greetings
    "Hello there!",
    "Welcome, welcome!",
    "Hey, nice to see you!",
    "Good to see you again!",
    "Nice to meet you!",
    # Reactions/exclamations
    "Amazing!",
    "That caught me off guard!",
    "Oh no, not again!",
    "Wow, that's amazing!",
    "Ha ha ha, that's so funny!",
    "That's funny!",
    "Oh yeah, that's right!",
    "Yippee!",
    "Super!",
    "Fantastic!",
    # Game prompts
    "Correct!",
    "That's not right! Try again!",
    "Let's play!",
    "Let's do this!",
    "You got it!",
    "Try again!",
    "Great job!",
    "Your turn!",
    # Farewells
    "See you later!",
    "Bye bye!",
    "Until next time!",
    "Take care!",
    "See you soon, friend!",
    "Goodbye!",
    # Hand wash reminders
    "Don't forget to wash your hands!",
    "Wash those hands, it's important!",
    "Clean hands, happy party!",
    "Scrub scrub, nice and clean!",
    "Time to wash your hands!",
    # Common commands/responses
    "Alright!",
    "Here we go!",
    "Yes, that's correct!",
    "No way!",
    "Of course!",
    "I don't know about that.",
    "Tell me more!",
    "What do you think?",
    "That's a good question!",
    "Let me think about that.",
    "You're welcome!",
    "Thank you so much!",
    "I'm ready!",
    "One more time!",
    # Thinking filler phrases (played while LLM generates response)
    "Hmm, let me think!",
    "Alright, one moment!",
    # Party & birthday phrases
    "Welcome to the party bathroom!",
    "Oh yeah!",
    "What a party!",
    "Happy birthday!",
    "Take a shot!",
    "Let's get this party started!",
    "Who's next?",
    "That's what I'm talking about!",
    "You're a superstar!",
    "Time for some fun!",
    "Welcome back!",
    "Good to see you!",
    "Ha ha ha!",
    "Oh no!",
    # Lisa Webb memorial phrases
    "Let's take a moment of silence for someone very special.",
    "Now let's raise a glass to Aunt Lisa!",
    "Take a shot in her honor!",
    "To Aunt Lisa! She'll always be remembered.",
    "What a beautiful tribute to a beautiful person.",
    # Party-specific phrases
    "Happy birthday, superstar!",
    "The guest of honor is here!",
    "Who wants to play another game?",
    "That was a good one!",
    "You guys are awesome!",
]


def init_tts():
    """Initialize TTS — load base TTS engine and RVC Mario voice model."""
    global _xtts_model, _xtts_available, _gpt_cond_latents, _speaker_embedding
    global _rvc_model, _rvc_available, _edge_executor, _sovits_available

    if DEBUG_TTS:
        logger.info("[DEBUG_TTS] init_tts: START")

    # Load disk cache first for instant startup
    _load_disk_cache()

    # --- Load base TTS engine ---
    if FAST_MODE:
        logger.info("[DEBUG_TTS] init_tts: FAST_MODE — using Edge TTS base (skipping XTTS)")
        try:
            import edge_tts
            logger.info("[DEBUG_TTS] init_tts: Edge TTS available")
        except ImportError:
            logger.error("[DEBUG_TTS] init_tts: Edge TTS not installed! pip install edge-tts")
    else:
        os.environ["COQUI_TOS_AGREED"] = "1"
        ref_path = MARIO_REF_PATH if os.path.exists(MARIO_REF_PATH) else MARIO_REF_FALLBACK
        try:
            from TTS.api import TTS as CoquiTTS
            logger.info("[DEBUG_TTS] init_tts: loading XTTS v2 model...")
            start = time.time()
            _xtts_model = CoquiTTS("tts_models/multilingual/multi-dataset/xtts_v2")
            if _TORCH_AVAILABLE and torch.cuda.is_available():
                _xtts_model = _xtts_model.to("cuda")
                logger.info("[DEBUG_TTS] init_tts: XTTS v2 on CUDA GPU")
            else:
                logger.info("[DEBUG_TTS] init_tts: XTTS v2 on CPU (will be slow)")
            if not os.path.exists(ref_path):
                raise FileNotFoundError(f"Missing reference audio: {ref_path}")
            logger.info(f"[DEBUG_TTS] init_tts: pre-computing speaker latents...")
            _gpt_cond_latents, _speaker_embedding = _xtts_model.synthesizer.tts_model.get_conditioning_latents(
                audio_path=ref_path, max_ref_length=30, gpt_cond_len=XTTS_COND_LEN, gpt_cond_chunk_len=XTTS_COND_LEN,
            )
            _xtts_available = True
            logger.info(f"[DEBUG_TTS] init_tts: XTTS v2 ready in {time.time() - start:.1f}s")
        except Exception as e:
            logger.warning(f"[DEBUG_TTS] init_tts: XTTS v2 failed: {e}")
            _xtts_available = False

    # --- Load RVC Mario voice conversion model (if enabled) ---
    # RVC is needed as fallback even in sovits mode — when SoVITS fails,
    # Edge TTS + RVC still produces Mario's voice instead of generic voice
    if USE_RVC and os.path.exists(RVC_MODEL_PATH) and _TORCH_AVAILABLE:
        try:
            logger.info("[DEBUG_TTS] init_tts: loading RVC Mario model (Switch Era, Charles Martinet)...")
            rvc_start = time.time()
            from rvc_python.infer import RVCInference
            # In sovits mode, SoVITS owns the GPU — use CPU for RVC fallback
            # On small GPUs (≤4GB), CPU RVC avoids OOM and still converts voice
            if TTS_MODE == "sovits":
                _rvc_device = "cpu"
            else:
                _rvc_device = "cuda:0" if (_TORCH_AVAILABLE and torch.cuda.is_available()) else "cpu"
            _rvc_model = RVCInference(
                device=_rvc_device,
                index_path=RVC_INDEX_PATH if os.path.exists(RVC_INDEX_PATH) else "",
            )
            _rvc_model.load_model(RVC_MODEL_PATH)
            _rvc_model.set_params(
                f0method=RVC_F0_METHOD,
                f0up_key=RVC_F0_UP_KEY,
                index_rate=RVC_INDEX_RATE,
                protect=RVC_PROTECT,
            )
            _rvc_available = True
            rvc_time = time.time() - rvc_start
            logger.info(f"[DEBUG_TTS] init_tts: RVC loaded in {rvc_time:.1f}s (f0={RVC_F0_METHOD}, pitch={RVC_F0_UP_KEY})")

            # Pre-warm ContentVec + RVC pipeline with a tiny dummy WAV
            # This saves ~6s on the first real call
            logger.info("[DEBUG_TTS] init_tts: pre-warming RVC pipeline (ContentVec load)...")
            warmup_start = time.time()
            try:
                dummy_wav = _make_dummy_wav(0.5)
                tmp_in = os.path.join(tempfile.gettempdir(), "mario_rvc_warmup_in.wav")
                tmp_out = os.path.join(tempfile.gettempdir(), "mario_rvc_warmup_out.wav")
                with open(tmp_in, "wb") as f:
                    f.write(dummy_wav)
                _rvc_model.infer_file(tmp_in, tmp_out)
                try:
                    os.unlink(tmp_in)
                except OSError:
                    pass
                try:
                    if os.path.exists(tmp_out):
                        os.unlink(tmp_out)
                except OSError:
                    pass
                logger.info(f"[DEBUG_TTS] init_tts: RVC pipeline warmed in {time.time() - warmup_start:.1f}s")
            except Exception as e:
                logger.warning(f"[DEBUG_TTS] init_tts: RVC warmup failed (non-fatal): {e}")
        except Exception as e:
            logger.warning(f"[DEBUG_TTS] init_tts: RVC failed to load: {e}")
            _rvc_available = False
    else:
        logger.info("[DEBUG_TTS] init_tts: RVC model not found, skipping voice conversion")
        _rvc_available = False

    # --- GPT-SoVITS setup ---
    if TTS_MODE == "sovits":
        # Direct sovits mode: keep subprocess running permanently
        logger.info(f"[DEBUG_TTS] init_tts: TTS_MODE=sovits, launching GPT-SoVITS subprocess...")
        if _start_sovits_subprocess():
            try:
                warmup_start = time.time()
                _sovits_synthesize("Hello!")
                logger.info(f"[DEBUG_TTS] sovits: warmup done in {time.time() - warmup_start:.1f}s")
            except Exception as e:
                logger.warning(f"[DEBUG_TTS] sovits: warmup failed: {e}")
    elif TTS_MODE == "hybrid":
        # Hybrid mode: do NOT start subprocess now — bg worker starts it on-demand
        # This prevents VRAM contention between RVC and GPT-SoVITS on small GPUs
        logger.info("[DEBUG_TTS] init_tts: TTS_MODE=hybrid, GPT-SoVITS will start on-demand during idle")
        _sovits_available = True  # Mark as available so hybrid mode enqueues regen jobs
        _start_sovits_worker()

    if DEBUG_TTS:
        logger.info(f"[DEBUG_TTS] init_tts: END (mode={TTS_MODE}, fast={FAST_MODE}, xtts={_xtts_available}, rvc={_rvc_available}, sovits={_sovits_available})")


def _start_sovits_subprocess():
    """Launch GPT-SoVITS server as a subprocess (runs in separate venv)."""
    import subprocess as sp
    import json as _json
    global _sovits_process, _sovits_available

    if not os.path.exists(SOVITS_PYTHON):
        logger.warning(f"[DEBUG_TTS] sovits: venv python not found at {SOVITS_PYTHON}")
        return False
    if not os.path.exists(SOVITS_SERVER_SCRIPT):
        logger.warning(f"[DEBUG_TTS] sovits: server script not found at {SOVITS_SERVER_SCRIPT}")
        return False

    logger.info("[DEBUG_TTS] sovits: starting GPT-SoVITS subprocess...")
    start = time.time()
    try:
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"  # Prevent output buffering on Windows
        # Select per-character models + reference clip so the subprocess clones the
        # ACTIVE character zero-shot. Falls back to Mario defaults if unset.
        try:
            gpt_path, sovits_path, is_ft = _resolve_sovits_models(_voice_char_name)
            env["SOVITS_GPT_PATH"] = gpt_path
            env["SOVITS_SOVITS_PATH"] = sovits_path
            env["SOVITS_CHARACTER"] = _voice_char_name
            ref = _voice_cfg.get("reference_audio")
            if ref and os.path.exists(ref):
                env["SOVITS_REF_AUDIO"] = ref
            if _voice_cfg.get("prompt_text"):
                env["SOVITS_PROMPT_TEXT"] = _voice_cfg["prompt_text"]
            if _voice_cfg.get("prompt_lang"):
                env["SOVITS_PROMPT_LANG"] = _voice_cfg["prompt_lang"]
            logger.info(f"[DEBUG_TTS] sovits: models for '{_voice_char_name}' "
                        f"({'fine-tune' if is_ft else 'v2-base zero-shot'})")
        except Exception as _e:
            logger.warning(f"[DEBUG_TTS] sovits: could not resolve per-character models: {_e}")
        _sovits_process = sp.Popen(
            [SOVITS_PYTHON, SOVITS_SERVER_SCRIPT],
            stdin=sp.PIPE,
            stdout=sp.PIPE,
            stderr=sp.PIPE,  # Capture stderr separately (loading messages go here)
            cwd=os.path.dirname(os.path.dirname(__file__)),
            text=True,
            bufsize=1,
            env=env,
        )
        # Drain stderr in background to prevent pipe from filling up and blocking subprocess
        def _drain_stderr():
            try:
                for line in _sovits_process.stderr:
                    if DEBUG_TTS:
                        line = line.strip()
                        if line and '[sovits]' in line:
                            logger.info(f"[DEBUG_TTS] {line[:200]}")
                        elif line:
                            logger.debug(f"[DEBUG_TTS] sovits-stderr: {line[:200]}")
            except Exception:
                pass
        threading.Thread(target=_drain_stderr, daemon=True, name="sovits-stderr").start()

        # Wait for "ready" message (with timeout)
        import select
        deadline = time.time() + 120  # 2 min timeout for model loading
        while time.time() < deadline:
            line = _sovits_process.stdout.readline()
            if not line:
                break
            line = line.strip()
            if not line:
                continue
            try:
                msg = _json.loads(line)
                if msg.get("status") == "ready":
                    _sovits_available = True
                    logger.info(f"[DEBUG_TTS] sovits: ready in {time.time() - start:.1f}s")
                    return True
                elif msg.get("status") == "loading":
                    if DEBUG_TTS:
                        logger.info(f"[DEBUG_TTS] sovits: {msg.get('msg', 'loading...')}")
            except _json.JSONDecodeError:
                pass  # skip non-JSON startup output
        logger.warning("[DEBUG_TTS] sovits: subprocess did not become ready in time")
        return False
    except Exception as e:
        logger.error(f"[DEBUG_TTS] sovits: failed to start subprocess: {e}")
        return False


def _restart_sovits_subprocess():
    """Kill and restart the GPT-SoVITS subprocess to free GPU memory."""
    global _sovits_process, _sovits_available, _sovits_restart_count
    with _sovits_lock:
        if _sovits_process is not None:
            try:
                _sovits_process.kill()
                _sovits_process.wait(timeout=10)
            except Exception:
                pass
            _sovits_process = None
            _sovits_available = False
        _sovits_restart_count = 0
    logger.info("[DEBUG_TTS] sovits: subprocess killed, waiting for GPU memory release...")
    time.sleep(5)  # Let GPU driver fully reclaim VRAM
    if _start_sovits_subprocess():
        logger.info("[DEBUG_TTS] sovits: subprocess restarted OK")
    else:
        raise RuntimeError("Failed to restart GPT-SoVITS subprocess")


class _UserTTSPreempt(RuntimeError):
    """Raised when non-user TTS yields to a waiting user TTS request."""
    pass


def _sovits_synthesize(text: str, speed: float = 1.0, _is_user: bool = False) -> bytes:
    """Send text to GPT-SoVITS subprocess and get WAV bytes back.
    
    Auto-restarts subprocess on crash (up to _sovits_max_restarts times).
    When _is_user=False, yields to pending user TTS requests to reduce latency.
    """
    import json as _json
    global _sovits_process, _sovits_available, _sovits_restart_count

    # Non-user calls yield to pending user TTS (prevents idle/precache from blocking user)
    if not _is_user and _user_tts_waiting.is_set():
        raise _UserTTSPreempt("Yielding to user TTS request")

    # Check if subprocess is alive before trying
    if _sovits_process is not None and _sovits_process.poll() is not None:
        logger.warning(f"[DEBUG_TTS] sovits: subprocess exited (code={_sovits_process.poll()}), marking dead")
        _sovits_process = None
        _sovits_available = False

    if not _sovits_available or _sovits_process is None:
        # Try auto-restart if we haven't exceeded limit
        if _sovits_restart_count < _sovits_max_restarts:
            logger.info(f"[DEBUG_TTS] sovits: attempting auto-restart ({_sovits_restart_count + 1}/{_sovits_max_restarts})...")
            if _start_sovits_subprocess():
                _sovits_restart_count += 1
            else:
                raise RuntimeError("GPT-SoVITS subprocess not available and restart failed")
        else:
            raise RuntimeError("GPT-SoVITS subprocess not available (max restarts exceeded)")

    with _sovits_lock:
        # Inside lock: abort non-user calls if user TTS arrived while waiting for lock
        if not _is_user and _user_tts_waiting.is_set():
            raise _UserTTSPreempt("Yielding to user TTS request (acquired lock)")
        try:
            # Double-check process is still alive inside the lock
            if _sovits_process.poll() is not None:
                raise RuntimeError("GPT-SoVITS subprocess died before request")
            # Truncate long text to prevent extremely slow synthesis (87s+ for long strings)
            MAX_SOVITS_CHARS = 120
            if len(text) > MAX_SOVITS_CHARS:
                # Cut at last sentence boundary within limit
                truncated = text[:MAX_SOVITS_CHARS]
                for sep in ['. ', '! ', '? ', ', ']:
                    idx = truncated.rfind(sep)
                    if idx > 30:
                        truncated = truncated[:idx + 1]
                        break
                text = truncated.strip()
                if DEBUG_TTS:
                    logger.info(f"[DEBUG_TTS] sovits: truncated to {len(text)} chars")
            _req = {"text": text, "speed": speed}
            # Carry the active character's reference clip + transcript so cloning
            # targets THIS character even without a subprocess restart.
            _ref = _voice_cfg.get("reference_audio")
            if _ref and os.path.exists(_ref):
                _req["ref_audio"] = _ref
                if _voice_cfg.get("prompt_text"):
                    _req["prompt_text"] = _voice_cfg["prompt_text"]
                if _voice_cfg.get("prompt_lang"):
                    _req["prompt_lang"] = _voice_cfg["prompt_lang"]
            req = _json.dumps(_req) + "\n"
            _sovits_process.stdin.write(req)
            _sovits_process.stdin.flush()
            # Use a thread to read with timeout (prevent 87s+ blocking)
            import concurrent.futures
            def _read_line():
                return _sovits_process.stdout.readline().strip()
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(_read_line)
                line = future.result(timeout=30)  # 30s max per synthesis
            if not line:
                raise RuntimeError("GPT-SoVITS subprocess returned empty response")
            resp = _json.loads(line)
            if resp.get("status") != "ok":
                raise RuntimeError(f"GPT-SoVITS error: {resp.get('error', 'unknown')}")
            audio_path = resp["audio_path"]
            if DEBUG_TTS:
                logger.info(f"[DEBUG_TTS] sovits: generated {resp['duration']:.1f}s audio in {resp['elapsed']:.1f}s")
            with open(audio_path, "rb") as f:
                wav_bytes = f.read()
            try:
                os.unlink(audio_path)
            except OSError:
                pass
            # Reset restart counter on success
            _sovits_restart_count = 0
            return wav_bytes
        except Exception as e:
            # Mark subprocess as dead on any communication error — will auto-restart next call
            err_str = str(e)
            err_type = type(e).__name__
            if ("Broken pipe" in err_str or "BrokenPipeError" in err_type
                    or "Invalid argument" in err_str or "empty response" in err_str
                    or "OSError" in err_type or "IOError" in err_type
                    or "TimeoutError" in err_type or "timed out" in err_str.lower()):
                _sovits_available = False
                _sovits_process = None
                logger.error(f"[DEBUG_TTS] sovits: subprocess failed ({err_type}: {err_str}), will auto-restart on next call")
            raise


def _kill_sovits_subprocess():
    """Kill the GPT-SoVITS subprocess to free VRAM. Called after bg worker finishes a batch."""
    global _sovits_process, _sovits_available
    if _sovits_process is None:
        return
    try:
        # Send quit command gracefully
        try:
            _sovits_process.stdin.write('{"command":"quit"}\n')
            _sovits_process.stdin.flush()
        except Exception:
            pass
        _sovits_process.terminate()
        _sovits_process.wait(timeout=5)
    except Exception:
        try:
            _sovits_process.kill()
        except Exception:
            pass
    _sovits_process = None
    # Keep _sovits_available = True for hybrid mode so queue keeps accepting items
    if TTS_MODE == "hybrid":
        _sovits_available = True
    else:
        _sovits_available = False
    if DEBUG_TTS:
        logger.info("[DEBUG_TTS] sovits: subprocess killed (VRAM freed)")


def _sovits_bg_worker():
    """Background worker that processes GPT-SoVITS regen requests on-demand.
    
    Architecture (prevents GPU contention on small GPUs like Quadro P1000 4GB):
    1. Wait for items in the queue
    2. Wait until GPU has been idle for _GPU_IDLE_THRESHOLD seconds (no Edge+RVC activity)
    3. Start GPT-SoVITS subprocess (loads models, warms up CUDA)
    4. Drain ALL queued items (batch processing)
    5. Kill subprocess to free VRAM
    6. Go back to step 1
    
    Aborts immediately if _user_tts_waiting is set (kills subprocess to free VRAM).
    """
    while True:
        # Step 1: Wait for first item
        try:
            first_item = _sovits_regen_queue.get(timeout=10)
        except _queue_mod.Empty:
            continue
        except Exception:
            break

        # Step 2: Wait until GPU has been idle long enough AND no user TTS pending
        while True:
            if _user_tts_waiting.is_set():
                time.sleep(0.5)
                continue
            _gpu_busy.wait(timeout=5)
            idle_time = time.time() - _last_synth_time
            if idle_time >= _GPU_IDLE_THRESHOLD and not _user_tts_waiting.is_set():
                break
            time.sleep(0.5)

        # Step 3: Start subprocess (models load, CUDA warms up)
        if DEBUG_TTS:
            logger.info("[DEBUG_TTS] hybrid: bg worker starting GPT-SoVITS subprocess for batch regen...")
        if not _start_sovits_subprocess():
            logger.warning("[DEBUG_TTS] hybrid: bg worker could not start subprocess, dropping batch")
            _sovits_regen_queue.task_done()
            continue

        # Check if user request arrived during startup — abort immediately
        if _user_tts_waiting.is_set():
            if DEBUG_TTS:
                logger.info("[DEBUG_TTS] hybrid: user request detected during subprocess startup, killing subprocess")
            _kill_sovits_subprocess()
            try:
                _sovits_regen_queue.put_nowait(first_item)
            except _queue_mod.Full:
                pass
            continue

        # Warmup first call
        try:
            _sovits_synthesize("Hello!")
        except Exception:
            pass

        # Step 4: Process first item + drain rest of queue
        batch = [first_item]
        while not _sovits_regen_queue.empty():
            try:
                batch.append(_sovits_regen_queue.get_nowait())
            except _queue_mod.Empty:
                break

        if DEBUG_TTS:
            logger.info(f"[DEBUG_TTS] hybrid: bg worker processing {len(batch)} items...")

        for text, cache_key in batch:
            # Check if user request arrived — kill subprocess and re-queue remaining
            if _user_tts_waiting.is_set():
                idx = batch.index((text, cache_key))
                for remaining in batch[idx:]:
                    try:
                        _sovits_regen_queue.put_nowait(remaining)
                    except _queue_mod.Full:
                        pass
                if DEBUG_TTS:
                    logger.info(f"[DEBUG_TTS] hybrid: bg worker aborting — user request, re-queued {len(batch) - idx}, killing subprocess")
                _kill_sovits_subprocess()
                break

            # Check if main thread started using GPU — abort batch
            if time.time() - _last_synth_time < 1.0 and _last_synth_time > 0:
                idx = batch.index((text, cache_key))
                for remaining in batch[idx:]:
                    try:
                        _sovits_regen_queue.put_nowait(remaining)
                    except _queue_mod.Full:
                        pass
                if DEBUG_TTS:
                    logger.info(f"[DEBUG_TTS] hybrid: bg worker aborting batch — GPU busy, re-queued {len(batch) - idx} items")
                break

            try:
                wav_bytes = _sovits_synthesize(text)
                with _cache_lock:
                    _audio_cache[cache_key] = wav_bytes
                    if cache_key not in _cache_order:
                        _cache_order.append(cache_key)
                _save_to_disk_cache(cache_key, wav_bytes)
                if DEBUG_TTS:
                    logger.info(f"[DEBUG_TTS] hybrid: bg worker replaced cache for '{text[:40]}...'")
            except Exception as e:
                if DEBUG_TTS:
                    logger.warning(f"[DEBUG_TTS] hybrid: bg worker failed for '{text[:40]}': {e}")

        # Mark all items as done
        for _ in batch:
            try:
                _sovits_regen_queue.task_done()
            except ValueError:
                pass

        # Step 5: Kill subprocess to free VRAM for future RVC calls
        _kill_sovits_subprocess()
        if DEBUG_TTS:
            logger.info("[DEBUG_TTS] hybrid: bg worker batch complete, subprocess killed")


def _start_sovits_worker():
    """Start the background regeneration worker thread (idempotent)."""
    global _sovits_worker_thread
    if _sovits_worker_thread is not None and _sovits_worker_thread.is_alive():
        return
    _sovits_worker_thread = threading.Thread(target=_sovits_bg_worker, daemon=True, name="sovits-bg-worker")
    _sovits_worker_thread.start()
    if DEBUG_TTS:
        logger.info("[DEBUG_TTS] sovits: background regeneration worker started")


def precache_phrases():
    """Pre-cache common Mario phrases at startup for instant playback.
    
    Phase 1: Edge+RVC for all phrases (fast, ~2s each)
    Phase 2: GPT-SoVITS upgrade for top-priority phrases (hybrid mode only)
    Yields to user requests between phrases (checks _user_tts_waiting).
    """
    global _precache_active
    if not CACHED_PHRASES:
        _precache_done.set()
        return
    logger.info(f"[DEBUG_TTS] precache: warming {len(CACHED_PHRASES)} phrases with Edge+RVC...")
    cache_start = time.time()
    failed = []
    _precache_active = True
    for i, phrase in enumerate(CACHED_PHRASES):
        # Yield to user TTS requests — pause until user is done
        if _user_tts_waiting.is_set():
            logger.info(f"[DEBUG_TTS] precache: pausing for user request (at phrase {i+1}/{len(CACHED_PHRASES)})")
            while _user_tts_waiting.is_set():
                time.sleep(0.2)
            logger.info("[DEBUG_TTS] precache: resuming after user request")
        try:
            synthesize(phrase)
        except Exception as e:
            logger.warning(f"[DEBUG_TTS] precache: failed '{phrase[:30]}': {e}")
            failed.append(phrase)
    # Retry failed phrases once after a brief delay
    if failed:
        logger.info(f"[DEBUG_TTS] precache: retrying {len(failed)} failed phrases...")
        time.sleep(_PRECACHE_PAUSE)
        for phrase in failed:
            if _user_tts_waiting.is_set():
                while _user_tts_waiting.is_set():
                    time.sleep(0.2)
            try:
                synthesize(phrase)
            except Exception as e:
                logger.warning(f"[DEBUG_TTS] precache: retry failed '{phrase[:30]}': {e}")
    _precache_active = False
    with _cache_lock:
        _cached_count = len(_audio_cache)
    elapsed = time.time() - cache_start
    logger.info(f"[DEBUG_TTS] precache: Edge+RVC done in {elapsed:.1f}s ({_cached_count} cached)")
    _precache_done.set()

    # Phase 2: Queue top-priority phrases for bg GPT-SoVITS upgrade (hybrid mode)
    if TTS_MODE == "hybrid" and _sovits_available:
        priority_phrases = CACHED_PHRASES[:20]
        queued = 0
        for phrase in priority_phrases:
            _rate = "+0%"
            _pitch = "+0Hz"
            cache_key = f"{_voice_cache_tag()}:{EDGE_VOICE}:{phrase.strip()}:{_rate}:{_pitch}"
            with _cache_lock:
                if cache_key in _audio_cache and _is_disk_cached(cache_key):
                    continue
            try:
                _sovits_regen_queue.put_nowait((phrase, cache_key))
                queued += 1
            except _queue_mod.Full:
                break
        if queued > 0:
            logger.info(f"[DEBUG_TTS] precache: queued {queued} phrases for bg GPT-SoVITS upgrade")

    # Phase 3: Background idle phrase caching (runs slowly after main precache)
    _start_idle_precache()


def _start_idle_precache():
    """Pre-cache idle behavior phrases in background so idle TTS is instant."""
    def _idle_cache_worker():
        # Use character-specific pools from the idle behavior instance
        if _idle_behavior_ref is not None:
            all_idle = list(getattr(_idle_behavior_ref, '_mumbles', [])) + list(getattr(_idle_behavior_ref, '_dj_announcements', []))
        else:
            all_idle = []
        if not all_idle:
            logger.info("[DEBUG_TTS] idle_precache: no idle phrases to cache (empty pools)")
            return

        # Wait a bit before starting (let user get first response without contention)
        time.sleep(10)

        cached_count = 0
        skipped = 0
        for i, phrase in enumerate(all_idle):
            # Yield to user TTS requests
            if _user_tts_waiting.is_set():
                while _user_tts_waiting.is_set():
                    time.sleep(0.3)

            # Pause if idle precache is paused (e.g. during testing)
            if _idle_precache_paused.is_set():
                logger.info("[DEBUG_TTS] idle_precache: PAUSED")
                while _idle_precache_paused.is_set():
                    time.sleep(1.0)
                logger.info("[DEBUG_TTS] idle_precache: RESUMED")

            # Check if already cached
            from pose_analyzer import analyze_text
            analyzed = analyze_text(phrase)
            tts_text = analyzed.get("tts_text", phrase)
            if not tts_text or len(tts_text) <= 5:
                skipped += 1
                continue

            _rate = "+0%"
            _pitch = "+0Hz"
            cache_key = f"{_voice_cache_tag()}:{EDGE_VOICE}:{tts_text.strip()}:{_rate}:{_pitch}"
            with _cache_lock:
                if cache_key in _audio_cache:
                    skipped += 1
                    continue

            try:
                synthesize(tts_text)
                cached_count += 1
                consecutive_fails = 0
                if cached_count % 10 == 0:
                    logger.info(f"[DEBUG_TTS] idle_precache: {cached_count} generated, {skipped} skipped ({i+1}/{len(all_idle)})")
            except Exception as e:
                consecutive_fails = getattr(_idle_cache_worker, '_fails', 0) + 1
                _idle_cache_worker._fails = consecutive_fails
                logger.warning(f"[DEBUG_TTS] idle_precache: failed '{tts_text[:30]}...': {e}")
                # If too many consecutive failures, wait longer for subprocess to recover
                if consecutive_fails >= 3:
                    logger.warning(f"[DEBUG_TTS] idle_precache: {consecutive_fails} consecutive failures, waiting 30s...")
                    time.sleep(30)

            # Pause between phrases (scaled by hardware tier)
            time.sleep(_PRECACHE_PAUSE)

        logger.info(f"[DEBUG_TTS] idle_precache: DONE — {cached_count} generated, {skipped} already cached/skipped")

    t = threading.Thread(target=_idle_cache_worker, daemon=True, name="idle-precache")
    t.start()


def get_cached(text: str, rate: str = None, pitch: str = None) -> bytes | None:
    """Fast cache-only lookup — no generation, no locks that block. Returns None on miss."""
    _rate = rate or "+0%"
    _pitch = pitch or "+0Hz"
    cache_key = f"{_voice_cache_tag()}:{EDGE_VOICE}:{text.strip()}:{_rate}:{_pitch}"
    return _audio_cache.get(cache_key)


import re as _re_tts

_character_pronunciation = {}

def set_pronunciation(pronunciation: dict):
    """Set character-specific pronunciation substitutions."""
    global _character_pronunciation
    _character_pronunciation = pronunciation


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


def _preclean_tts_text(text: str) -> str:
    """Pre-clean text before any TTS engine sees it.

    Fixes ellipsis, smart quotes, and other characters that ALL TTS engines
    struggle with. Applied before cache key generation so cleaned text is cached.
    """
    t = text
    # Ellipsis variants → natural pause (comma + space)
    t = t.replace('…', ', ')                       # Smart ellipsis
    t = _re_tts.sub(r'\.{3,}', ', ', t)            # Three+ dots → pause
    t = _re_tts.sub(r'\.{2}', ', ', t)             # Two dots → pause
    # Smart quotes → straight (TTS reads curly quotes as words)
    t = t.replace('\u201c', '').replace('\u201d', '')  # " "
    t = t.replace('\u2018', "'").replace('\u2019', "'")  # ' '
    t = t.replace('"', '')
    # Em/en dashes → comma pause
    t = t.replace('—', ', ').replace('–', ', ')
    # Asterisks (action markers like *laughs*)
    t = t.replace('*', '')
    # Strip emoji / pictographs — TTS can't speak them, and removing them later
    # leaves a stray space before punctuation (e.g. display name "Reze 💣!" was
    # spoken as "Reze  !"). Remove here, then fix the spacing below.
    t = _re_tts.sub(
        r'[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF'
        r'♀-♂←-⇿⌀-⏿️‍]', '', t)
    # Clean up resulting artifacts: leading commas, double commas, etc.
    t = _re_tts.sub(r'^[\s,]+', '', t)             # Leading whitespace/commas
    t = _re_tts.sub(r',\s*,', ',', t)              # Double commas
    t = _re_tts.sub(r'([.!?])\s*,', r'\1', t)     # Comma after sentence-end punctuation
    t = _re_tts.sub(r',\s*([!?])', r'\1', t)       # Comma before ! or ? (from "...!")
    t = _re_tts.sub(r'\s+([!?.,;:])', r'\1', t)    # Space before punctuation (from stripped emoji)
    t = _re_tts.sub(r'[,\s]+$', '', t)             # Trailing commas/whitespace
    # Pronunciation rules — loaded from character YAML only (single source of truth)
    # Hardcoded rules were removed because they conflict with character-specific rules
    # and prevent the YAML rules from being effective.
    for word, phonetic in _character_pronunciation.items():
        t = _re_tts.sub(r'(?<!\w)' + _re_tts.escape(word) + r'(?!\w)', phonetic, t, flags=_re_tts.IGNORECASE)
    t = _re_tts.sub(r'\s+', ' ', t).strip()        # Collapse whitespace
    return t


def synthesize_user(text: str, rate: str = None, pitch: str = None, nocache: bool = False) -> bytes:
    """User-priority TTS synthesis. Pauses precache while this runs."""
    _user_tts_waiting.set()
    try:
        return synthesize(text, rate, pitch, nocache=nocache, _is_user=True)
    finally:
        _user_tts_waiting.clear()


def synthesize(text: str, rate: str = None, pitch: str = None, nocache: bool = False,
               _is_user: bool = False, force_fast: bool = False) -> bytes:
    """Convert text to Mario-voiced speech audio.

    Pipeline: Cache check → Base TTS (Edge or XTTS) → RVC voice conversion (Mario).

    force_fast=True skips GPT-SoVITS and uses the instant Edge path regardless of
    TTS_MODE — for thinking fillers, which must play immediately (slow sovits
    fillers lose the race to the real LLM response and get cut, leaving a text
    bubble with no speech).
    """
    # Guard: empty/whitespace text produces silence (prevents TTS engine errors)
    if not text or not text.strip():
        logger.debug("[DEBUG_TTS] synthesize: empty text, returning silence")
        return _EMERGENCY_SILENCE

    # Pre-clean ellipsis and problematic punctuation BEFORE cache key or any engine
    text = _preclean_tts_text(text)

    # After cleaning, text may be empty again
    if not text or not text.strip():
        logger.debug("[DEBUG_TTS] synthesize: text empty after pre-clean, returning silence")
        return _EMERGENCY_SILENCE

    # Check cache first for instant playback (key includes voice params)
    _rate = rate or "+0%"
    _pitch = pitch or "+0Hz"
    cache_key = f"{_voice_cache_tag()}:{EDGE_VOICE}:{text.strip()}:{_rate}:{_pitch}"
    global _cache_hits, _cache_misses
    if not nocache:
        with _cache_lock:
            cached = _audio_cache.get(cache_key)
            if cached is not None:
                # Move to end of LRU order on cache hit
                if cache_key in _cache_order:
                    _cache_order.remove(cache_key)
                    _cache_order.append(cache_key)
                _cache_hits += 1
                if DEBUG_TTS:
                    hit_rate = _cache_hits / max(1, _cache_hits + _cache_misses) * 100
                    logger.info(f"[DEBUG_TTS] synthesize: CACHE HIT '{text[:40]}...' (rate={hit_rate:.0f}%)")
                return cached

    _cache_misses += 1

    if DEBUG_TTS:
        logger.info(f"[DEBUG_TTS] synthesize: START text='{text[:50]}...' mode={TTS_MODE}")

    start = time.time()

    # GPT-SoVITS mode: direct synthesis, no RVC needed
    if TTS_MODE == "sovits" and _sovits_available and not force_fast:
        try:
            result = _normalize_audio(_sovits_synthesize(text, _is_user=_is_user))
            total = time.time() - start
            if DEBUG_TTS:
                logger.info(f"[DEBUG_TTS] synthesize: END (GPT-SoVITS) total={total:.1f}s")
            # Cache all phrases (GPT-SoVITS is slower, cache more aggressively)
            if len(text) < 200:
                with _cache_lock:
                    _audio_cache[cache_key] = result
                    if cache_key not in _cache_order:
                        _cache_order.append(cache_key)
                    if len(_cache_order) > MAX_CACHE_SIZE:
                        evict_key = _cache_order.pop(0)
                        _audio_cache.pop(evict_key, None)
                # Persist to disk for instant startup next time
                _save_to_disk_cache(cache_key, result)
            return result
        except Exception as e:
            logger.warning(f"[DEBUG_TTS] synthesize: GPT-SoVITS failed ({e}), falling back to Edge+RVC")

    # Step 1: Generate base speech (Edge TTS or XTTS)
    if FAST_MODE or force_fast:
        if DEBUG_TTS:
            logger.info(f"[DEBUG_TTS] synthesize: using Edge TTS ({'force_fast' if force_fast else 'FAST_MODE'})")
        base_wav = _synthesize_edge(text, rate, pitch)
    elif not _xtts_available:
        if DEBUG_TTS:
            logger.info("[DEBUG_TTS] synthesize: using Edge TTS (XTTS not available)")
        base_wav = _synthesize_edge(text, rate, pitch)
    else:
        try:
            base_wav = _synthesize_xtts_raw(text)
        except Exception as e:
            logger.error(f"[DEBUG_TTS] synthesize: XTTS failed ({type(e).__name__}: {e}), falling back to Edge TTS")
            base_wav = _synthesize_edge(text, rate, pitch)

    base_time = time.time() - start

    # Step 2: Convert voice to Mario via RVC (if enabled)
    # Signal GPU busy to pause background GPT-SoVITS worker
    _gpu_busy.clear()
    word_count = len(text.split())
    try:
        if USE_RVC:
            try:
                result = _apply_rvc(base_wav, word_count=word_count)
            except Exception as rvc_err:
                logger.warning(f"RVC voice conversion failed ({rvc_err}), retrying once...")
                try:
                    result = _apply_rvc(base_wav, word_count=word_count)
                except Exception:
                    logger.error("RVC retry also failed — using base audio (will sound wrong)")
                    result = base_wav
        else:
            result = base_wav
    finally:
        global _last_synth_time
        _last_synth_time = time.time()
        _gpu_busy.set()  # Signal GPU free

    total = time.time() - start
    if DEBUG_TTS:
        logger.info(f"[DEBUG_TTS] synthesize: END total={total:.1f}s (base={base_time:.1f}s + rvc={total - base_time:.1f}s)")

    # Cache short phrases for future instant playback (LRU eviction)
    if len(text) < 200:
        with _cache_lock:
            _audio_cache[cache_key] = result
            if cache_key not in _cache_order:
                _cache_order.append(cache_key)
            if len(_cache_order) > MAX_CACHE_SIZE:
                evict_key = _cache_order.pop(0)
                _audio_cache.pop(evict_key, None)

    # Hybrid mode: enqueue background GPT-SoVITS regeneration (deduped via queue)
    if TTS_MODE == "hybrid" and _sovits_available and len(text) < 200:
        try:
            _sovits_regen_queue.put_nowait((text, cache_key))
            if DEBUG_TTS:
                logger.info(f"[DEBUG_TTS] hybrid: queued bg regen for '{text[:40]}...' (queue={_sovits_regen_queue.qsize()})")
        except _queue_mod.Full:
            if DEBUG_TTS:
                logger.info(f"[DEBUG_TTS] hybrid: regen queue full, skipping '{text[:40]}...'")

    # Fire post-synthesis callbacks (debug monitor hook)
    for cb in _post_synthesis_callbacks:
        try:
            cb(text, result)
        except Exception as e:
            logger.warning(f"[DEBUG_TTS] post-synthesis callback failed: {e}")

    return result


# --- Sentence streaming helpers ---

DEBUG_STREAM = _load_debug_flag()  # Reuses debug_tts flag from config


def split_into_sentences(text: str) -> list[str]:
    """Split text into speakable chunks at sentence boundaries.

    Splits on .!? while keeping punctuation attached. Merges very short
    chunks (< 15 chars) with the next one to avoid choppy TTS output.
    """
    import re
    # Pre-clean ellipsis before splitting (prevents "..." creating empty fragments)
    text = _preclean_tts_text(text)
    if not text:
        return []
    chunks = re.split(r'(?<=[.!?])\s+', text)
    merged = []
    buffer = ""
    for chunk in chunks:
        buffer += (" " if buffer else "") + chunk
        if len(buffer) >= 15:
            merged.append(buffer)
            buffer = ""
    if buffer:
        if merged:
            merged[-1] += " " + buffer
        else:
            merged.append(buffer)
    return merged


async def synthesize_streaming(text: str, voice_params: dict = None):
    """Split text into sentences, synthesize each, yield WAV bytes as they complete.

    Yields (index, total, wav_bytes) tuples for each sentence chunk.
    Uses synthesize_user() so user-priority is maintained.
    """
    import asyncio
    sentences = split_into_sentences(text)
    if not sentences:
        return

    rate = voice_params.get("rate") if voice_params else None
    pitch = voice_params.get("pitch") if voice_params else None
    total = len(sentences)
    loop = asyncio.get_event_loop()

    for i, sentence in enumerate(sentences):
        stripped = sentence.strip()
        if not stripped:
            continue
        if DEBUG_STREAM:
            logger.info(f"[DEBUG_STREAM] Streaming sentence {i+1}/{total}: \"{stripped[:60]}\"")
        try:
            audio = await loop.run_in_executor(
                None, lambda s=stripped: synthesize_user(s, rate=rate, pitch=pitch))
            if audio and len(audio) > 44:
                yield (i, total, audio)
            else:
                if DEBUG_STREAM:
                    logger.warning(f"[DEBUG_STREAM] Sentence {i+1}/{total} produced empty audio, skipping")
        except Exception as e:
            logger.error(f"[DEBUG_STREAM] Sentence {i+1}/{total} TTS failed: {e}")
            # Continue with remaining sentences — don't break the whole stream


def _make_dummy_wav(duration: float = 0.5, sample_rate: int = 24000) -> bytes:
    """Generate a tiny silent WAV file for RVC pipeline warmup."""
    num_samples = int(duration * sample_rate)
    silence = np.zeros(num_samples, dtype=np.int16)
    wav_buffer = io.BytesIO()
    with wave.open(wav_buffer, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(silence.tobytes())
    wav_buffer.seek(0)
    return wav_buffer.read()


def _normalize_audio(wav_bytes: bytes, target_db: float = -3.0) -> bytes:
    """Normalize WAV audio to consistent peak volume.
    
    Prevents inconsistent volume across TTS outputs — some phrases
    come out quiet, some loud. Normalizes to target_db peak level.
    """
    try:
        with io.BytesIO(wav_bytes) as buf:
            with wave.open(buf, 'rb') as wf:
                params = wf.getparams()
                frames = wf.readframes(params.nframes)
        
        # Convert to numpy for processing
        dtype = np.int16 if params.sampwidth == 2 else np.int32
        samples = np.frombuffer(frames, dtype=dtype).astype(np.float32)
        
        if len(samples) == 0:
            return wav_bytes
        
        # Calculate current peak and target
        peak = np.max(np.abs(samples))
        if peak < 1.0:
            return wav_bytes
        
        target_peak = (2 ** (params.sampwidth * 8 - 1) - 1) * (10 ** (target_db / 20.0))
        gain = target_peak / peak
        
        # Apply gain with clipping protection
        samples = np.clip(samples * gain, -32768, 32767).astype(np.int16)
        
        # Write back to WAV
        out = io.BytesIO()
        with wave.open(out, 'wb') as wf:
            wf.setparams(params)
            wf.writeframes(samples.tobytes())
        return out.getvalue()
    except Exception as e:
        if DEBUG_TTS:
            logger.warning(f"[DEBUG_TTS] _normalize_audio: failed ({e}), returning original")
        return wav_bytes


RVC_SHORT_PHRASE_F0_UP_KEY = 6   # Gentler pitch for short phrases (half octave vs full)
RVC_SHORT_PHRASE_INDEX_RATE = 0.6  # Less aggressive voice matching for short phrases
RVC_SHORT_PHRASE_PROTECT = 0.4   # More protection for short phrases (preserve consonants)
RVC_SHORT_PHRASE_WORD_THRESHOLD = 4  # Phrases with fewer words get gentle treatment

def _get_word_count_from_wav(wav_bytes: bytes) -> float:
    """Estimate audio duration from WAV to detect short phrases."""
    try:
        with io.BytesIO(wav_bytes) as buf:
            with wave.open(buf, "rb") as wf:
                return wf.getnframes() / float(wf.getframerate())
    except Exception:
        return 999.0  # Assume long if we can't read

def _apply_rvc(wav_bytes: bytes, word_count: int = 999) -> bytes:
    """Convert voice to Mario using RVC model. Returns WAV bytes.
    
    Uses a threading lock to serialize GPU calls — prevents contention
    that would cause 1s calls to balloon to 30s+.
    
    For short phrases (< RVC_SHORT_PHRASE_WORD_THRESHOLD words), uses gentler
    RVC settings to avoid garbling short utterances.
    """
    if not _rvc_available or _rvc_model is None:
        return wav_bytes

    is_short = word_count < RVC_SHORT_PHRASE_WORD_THRESHOLD
    tmp_in = None
    tmp_out = None
    try:
        rvc_start = time.time()

        call_id = uuid.uuid4().hex[:12]
        tmp_in = os.path.join(tempfile.gettempdir(), f"mario_rvc_in_{call_id}.wav")
        tmp_out = os.path.join(tempfile.gettempdir(), f"mario_rvc_out_{call_id}.wav")
        with open(tmp_in, "wb") as f:
            f.write(wav_bytes)

        # Serialize RVC GPU access with timeout to prevent deadlocks
        acquired = _rvc_lock.acquire(timeout=30)
        if not acquired:
            logger.warning("[DEBUG_TTS] _apply_rvc: lock timeout — GPU busy, returning original")
            return wav_bytes
        try:
            if is_short:
                _rvc_model.set_params(
                    f0method=RVC_F0_METHOD,
                    f0up_key=RVC_SHORT_PHRASE_F0_UP_KEY,
                    index_rate=RVC_SHORT_PHRASE_INDEX_RATE,
                    protect=RVC_SHORT_PHRASE_PROTECT,
                )
                if DEBUG_TTS:
                    logger.info(f"[DEBUG_TTS] _apply_rvc: using GENTLE params for short phrase ({word_count} words)")
            _rvc_model.infer_file(tmp_in, tmp_out)
        finally:
            if is_short:
                _rvc_model.set_params(
                    f0method=RVC_F0_METHOD,
                    f0up_key=RVC_F0_UP_KEY,
                    index_rate=RVC_INDEX_RATE,
                    protect=RVC_PROTECT,
                )
            _rvc_lock.release()

        # Read output back
        with open(tmp_out, "rb") as f:
            result = f.read()

        rvc_time = time.time() - rvc_start
        if DEBUG_TTS:
            logger.info(f"[DEBUG_TTS] _apply_rvc: converted in {rvc_time:.1f}s (short={is_short})")

        return _normalize_audio(result)

    except Exception as e:
        logger.warning(f"[DEBUG_TTS] _apply_rvc: RVC conversion failed: {e}, returning original")
        return wav_bytes
    finally:
        # Always cleanup temp files
        for f in [tmp_in, tmp_out]:
            if f:
                try:
                    os.unlink(f)
                except OSError:
                    pass


# --- TTSRouter integration ---

def _edge_rvc_is_available() -> bool:
    """Check if Edge TTS + RVC pipeline is ready."""
    try:
        return _rvc_available or FAST_MODE
    except Exception:
        return False


def register_as_engine():
    """Register this module as the 'edge_rvc' engine in the TTSRouter.

    Returns a TTSEngine dataclass ready for router.register().
    """
    from tts_router import TTSEngine

    # Capture the original function object so the monkey-patch in main.py
    # (tts.synthesize = _tts_router.synthesize) doesn't cause infinite recursion.
    _direct_synthesize = synthesize
    def _synth_for_router(text, rate=None, pitch=None, nocache=False, **kwargs):
        # Forward the router's user-priority flag so GPT-SoVITS does not yield
        # to its own request (self-preempt -> unwanted Edge fallback).
        return _direct_synthesize(text, rate=rate, pitch=pitch, nocache=nocache,
                                  _is_user=kwargs.get("is_user", False))

    return TTSEngine(
        name="edge_rvc",
        synthesize_fn=_synth_for_router,
        is_available_fn=_edge_rvc_is_available,
        priority=2,
    )


def _synthesize_xtts_raw(text: str) -> bytes:
    """Generate speech using XTTS v2 (raw, without RVC — caller applies RVC)."""
    if DEBUG_TTS:
        logger.info("[DEBUG_TTS] _synthesize_xtts_raw: START")

    start = time.time()

    ctx = torch.amp.autocast("cuda") if (_TORCH_AVAILABLE and torch.cuda.is_available()) else nullcontext()
    with ctx:
        result = _xtts_model.synthesizer.tts_model.inference(
        text=text,
        language="en",
        gpt_cond_latent=_gpt_cond_latents,
        speaker_embedding=_speaker_embedding,
        temperature=XTTS_TEMPERATURE,
        length_penalty=1.0,
        repetition_penalty=XTTS_REP_PENALTY,
        top_k=XTTS_TOP_K,
        top_p=XTTS_TOP_P,
        speed=MARIO_SPEED_FACTOR,
        enable_text_splitting=True,
    )

    audio_data = result["wav"]
    if hasattr(audio_data, 'cpu'):
        audio_data = audio_data.cpu().numpy()
    else:
        audio_data = np.array(audio_data, dtype=np.float32)
    if audio_data.ndim > 1:
        audio_data = audio_data.squeeze()

    gen_time = time.time() - start

    # Post-synthesis pitch shift (only if RVC is not handling it)
    if MARIO_PITCH_SEMITONES != 0 and not _rvc_available:
        factor = 2 ** (MARIO_PITCH_SEMITONES / 12.0)
        new_length = int(len(audio_data) / factor)
        audio_data = scipy_signal.resample(audio_data, new_length).astype(np.float32)

    audio_int16 = (np.clip(audio_data, -1.0, 1.0) * 32767).astype(np.int16)

    wav_buffer = io.BytesIO()
    with wave.open(wav_buffer, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(XTTS_SAMPLE_RATE)
        wf.writeframes(audio_int16.tobytes())
    wav_buffer.seek(0)
    raw_wav = wav_buffer.read()

    if DEBUG_TTS:
        duration = len(audio_int16) / XTTS_SAMPLE_RATE
        logger.info(f"[DEBUG_TTS] _synthesize_xtts_raw: gen={gen_time:.1f}s audio={duration:.1f}s")

    return raw_wav


def _synthesize_edge(text: str, rate: str = None, pitch: str = None) -> bytes:
    """Fallback: generate speech using Edge TTS with pitch shifting."""
    global _edge_executor
    if DEBUG_TTS:
        logger.info("[DEBUG_TTS] _synthesize_edge: START (fallback)")

    try:
        loop = None
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            pass

        if loop and loop.is_running():
            import concurrent.futures
            if _edge_executor is None:
                _edge_executor = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="edge_tts")
            future = _edge_executor.submit(lambda: asyncio.run(_edge_async(text, rate, pitch)))
            return future.result(timeout=30) or b""
        else:
            return asyncio.run(_edge_async(text, rate, pitch)) or b""

    except Exception as e:
        logger.error(f"[DEBUG_TTS] _synthesize_edge: error: {e}")
        return b""


async def _edge_async(text: str, rate: str = None, pitch: str = None) -> bytes:
    """Generate speech using edge-tts."""
    import edge_tts

    communicate = edge_tts.Communicate(
        text,
        voice=EDGE_VOICE,
        rate=rate or RATE,
        pitch=pitch or PITCH_OFFSET,
    )

    tid = threading.current_thread().ident
    tmp_path = os.path.join(tempfile.gettempdir(), f"mario_tts_{tid}.mp3")
    await communicate.save(tmp_path)

    try:
        audio_data, sample_rate = sf.read(tmp_path)
        if audio_data.dtype != np.int16:
            audio_data = (audio_data * 32767).astype(np.int16)
        if len(audio_data.shape) > 1:
            audio_data = audio_data[:, 0]
        if EDGE_PITCH_SHIFT != 0:
            factor = 2 ** (EDGE_PITCH_SHIFT / 12.0)
            new_length = int(len(audio_data) / factor)
            audio_data = scipy_signal.resample(audio_data, new_length).astype(np.int16)

        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(audio_data.tobytes())
        wav_buffer.seek(0)
        return wav_buffer.read()

    except Exception as e:
        logger.warning(f"[DEBUG_TTS] _edge_async: conversion failed: {e}")
        with open(tmp_path, "rb") as f:
            return f.read()
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
