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
import torch
import torchaudio
import soundfile as sf
from scipy import signal as scipy_signal
from scipy.io import wavfile
from contextlib import nullcontext

logger = logging.getLogger(__name__)

# Load debug flag from config (default: True)
def _load_debug_flag():
    try:
        _cfg_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")
        if os.path.exists(_cfg_path):
            import json as _json
            with open(_cfg_path) as _f:
                return _json.load(_f).get("server", {}).get("debug_tts", True)
    except Exception:
        pass
    return True

DEBUG_TTS = _load_debug_flag()

# --- Monkey-patches (MUST run before importing TTS) ---
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
_sovits_max_restarts = 3  # Auto-restart up to 3 times before giving up

# Background regeneration queue (replaces thread-per-request)
import queue as _queue_mod
_sovits_regen_queue = _queue_mod.Queue(maxsize=50)  # Cap pending regen jobs
_sovits_worker_thread = None  # Single worker consuming from queue

# GPU contention guard: bg worker only runs when main thread hasn't used GPU recently
_gpu_busy = threading.Event()  # Set = GPU free, Clear = GPU busy
_gpu_busy.set()  # Start as free
_last_synth_time = 0.0  # Timestamp of last Edge+RVC synthesis completion
_GPU_IDLE_THRESHOLD = 3.0  # Seconds of idle before bg worker can use GPU

# Precache state — allows user requests to preempt precache
_precache_done = threading.Event()  # Set when precache completes
_precache_active = False  # True while precache is synthesizing
_user_tts_waiting = threading.Event()  # Set when a user TTS call is waiting for RVC lock

# GPT-SoVITS venv python path
SOVITS_PYTHON = os.path.join(os.path.dirname(os.path.dirname(__file__)), "gpt_sovits_env", "Scripts", "python.exe")
SOVITS_SERVER_SCRIPT = os.path.join(os.path.dirname(__file__), "gpt_sovits_server.py")

# --- Speed mode ---
# "hybrid" = Edge+RVC for instant response, GPT-SoVITS regenerates in background (RECOMMENDED)
# "sovits" = GPT-SoVITS only (best quality, ~3-10s latency)
# "edge" = Edge TTS + RVC only (fast, ~1.5s)
# Can be overridden via config.json: {"server": {"tts_mode": "hybrid"}}
_tts_config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")
_tts_config_fast = True
_tts_mode = "hybrid"
if os.path.exists(_tts_config_path):
    try:
        import json as _json
        with open(_tts_config_path) as _f:
            _tts_cfg = _json.load(_f).get("server", {})
            _tts_config_fast = _tts_cfg.get("tts_fast_mode", True)
            _tts_mode = _tts_cfg.get("tts_mode", "hybrid")
    except Exception:
        pass
FAST_MODE = _tts_config_fast
TTS_MODE = _tts_mode  # "hybrid", "sovits", "edge", or "xtts"

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

# --- Audio cache for instant playback (LRU with max entries) ---
_audio_cache = {}
_cache_order = []
MAX_CACHE_SIZE = 200
_cache_hits = 0
_cache_misses = 0
_rvc_lock = threading.Lock()  # Serialize RVC GPU calls to prevent contention
_cache_lock = threading.Lock()  # Protects _audio_cache and _cache_order from concurrent access
_edge_executor = None  # Reusable executor for Edge TTS async-in-sync calls

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
            with open(key_file, "r") as f:
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
        with open(key_path, "w") as f:
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
    "It's-a me, Mario!",
    "Hello there!",
    "Welcome, welcome!",
    "Hey, nice to see you!",
    "Good to see you again!",
    "Nice to meet-a you!",
    # Reactions/exclamations
    "Wahoo!",
    "Mama mia!",
    "Oh no!",
    "Wow, that's-a amazing!",
    "Ha ha ha!",
    "That's-a funny!",
    "Oh yeah!",
    "Yippee!",
    "Super!",
    "Fantastic!",
    # Game prompts
    "Correct!",
    "Wrong!",
    "Let's play!",
    "Let's-a go!",
    "You got it!",
    "Try again!",
    "Great job!",
    "Your turn!",
    # Farewells
    "See you later!",
    "Bye bye!",
    "Until next time!",
    "Take-a care!",
    "See you soon, friend!",
    "Goodbye!",
    # Hand wash reminders
    "Don't forget to wash-a your hands!",
    "Wash those hands, it's-a important!",
    "Clean hands, happy Mario!",
    "Scrub-a scrub-a, nice and clean!",
    "Time to wash-a your hands!",
    # Common commands/responses
    "Okie dokie!",
    "Here we go!",
    "Yes!",
    "No way!",
    "Of course!",
    "I don't-a know about that.",
    "Tell me more!",
    "What do you think?",
    "That's-a good question!",
    "Let me think about that.",
    "You're-a welcome!",
    "Thank you so much!",
    "I'm-a ready!",
    "One more time!",
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
            if torch.cuda.is_available():
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

    # --- Load RVC Mario voice conversion model (if enabled and not sovits-only mode) ---
    # In sovits mode, GPT-SoVITS already produces Mario's voice — skip RVC to save VRAM
    if USE_RVC and os.path.exists(RVC_MODEL_PATH) and TTS_MODE != "sovits":
        try:
            logger.info("[DEBUG_TTS] init_tts: loading RVC Mario model (Switch Era, Charles Martinet)...")
            rvc_start = time.time()
            from rvc_python.infer import RVCInference
            _rvc_model = RVCInference(
                device="cuda:0" if torch.cuda.is_available() else "cpu",
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
                        if line:
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


def _sovits_synthesize(text: str, speed: float = 1.0) -> bytes:
    """Send text to GPT-SoVITS subprocess and get WAV bytes back.
    
    Auto-restarts subprocess on crash (up to _sovits_max_restarts times).
    """
    import json as _json
    global _sovits_process, _sovits_available, _sovits_restart_count

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
        try:
            req = _json.dumps({"text": text, "speed": speed}) + "\n"
            _sovits_process.stdin.write(req)
            _sovits_process.stdin.flush()
            line = _sovits_process.stdout.readline().strip()
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
            if "Broken pipe" in str(e) or "BrokenPipeError" in str(type(e).__name__):
                _sovits_available = False
                logger.error("[DEBUG_TTS] sovits: subprocess crashed, will auto-restart on next call")
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
        time.sleep(2)
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
            cache_key = f"{EDGE_VOICE}:{phrase.strip().lower()}:{_rate}:{_pitch}"
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


def synthesize_user(text: str, rate: str = None, pitch: str = None) -> bytes:
    """User-priority TTS synthesis. Pauses precache while this runs."""
    _user_tts_waiting.set()
    try:
        return synthesize(text, rate, pitch)
    finally:
        _user_tts_waiting.clear()


def synthesize(text: str, rate: str = None, pitch: str = None) -> bytes:
    """Convert text to Mario-voiced speech audio.

    Pipeline: Cache check → Base TTS (Edge or XTTS) → RVC voice conversion (Mario).
    """
    # Check cache first for instant playback (key includes voice params)
    _rate = rate or "+0%"
    _pitch = pitch or "+0Hz"
    cache_key = f"{EDGE_VOICE}:{text.strip().lower()}:{_rate}:{_pitch}"
    global _cache_hits, _cache_misses
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
    if TTS_MODE == "sovits" and _sovits_available:
        try:
            result = _sovits_synthesize(text)
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
            return result
        except Exception as e:
            logger.warning(f"[DEBUG_TTS] synthesize: GPT-SoVITS failed ({e}), falling back to Edge+RVC")

    # Step 1: Generate base speech (Edge TTS or XTTS)
    if FAST_MODE:
        if DEBUG_TTS:
            logger.info("[DEBUG_TTS] synthesize: using Edge TTS (FAST_MODE=True)")
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
    try:
        if USE_RVC:
            result = _apply_rvc(base_wav)
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

    return result


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


def _apply_rvc(wav_bytes: bytes) -> bytes:
    """Convert voice to Mario using RVC model. Returns WAV bytes.
    
    Uses a threading lock to serialize GPU calls — prevents contention
    that would cause 1s calls to balloon to 30s+.
    """
    if not _rvc_available or _rvc_model is None:
        return wav_bytes

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
            _rvc_model.infer_file(tmp_in, tmp_out)
        finally:
            _rvc_lock.release()

        # Read output back
        with open(tmp_out, "rb") as f:
            result = f.read()

        rvc_time = time.time() - rvc_start
        if DEBUG_TTS:
            logger.info(f"[DEBUG_TTS] _apply_rvc: converted in {rvc_time:.1f}s")

        return result

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


def _synthesize_xtts_raw(text: str) -> bytes:
    """Generate speech using XTTS v2 (raw, without RVC — caller applies RVC)."""
    if DEBUG_TTS:
        logger.info("[DEBUG_TTS] _synthesize_xtts_raw: START")

    start = time.time()

    ctx = torch.amp.autocast("cuda") if torch.cuda.is_available() else nullcontext()
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
