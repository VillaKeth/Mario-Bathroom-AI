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

DEBUG_TTS = True
logger = logging.getLogger(__name__)

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

# RVC model paths — Mario Super Show v2 (trained on Super Mario Bros. Super Show TV series)
RVC_MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "Mario_Super_Show_v2", "Mario_Super_Show_e220_s2420.pth")
RVC_INDEX_PATH = os.path.join(os.path.dirname(__file__), "..", "Mario_Super_Show_v2", "added_IVF255_Flat_nprobe_1_Mario_Super_Show_v2.index")

# Curated 30s reference — best quality segment from full sentences
MARIO_REF_PATH = os.path.join(os.path.dirname(__file__), "data", "mario_reference_sentences_30s.wav")
MARIO_REF_FALLBACK = os.path.join(os.path.dirname(__file__), "data", "mario_reference_sentences.wav")

# Post-synthesis tuning
MARIO_PITCH_SEMITONES = 0  # No pitch shift — let RVC model handle voice character
MARIO_SPEED_FACTOR = 1.0  # Normal speed
USE_RVC = True  # Use RVC for Mario voice conversion
RVC_F0_UP_KEY = 8  # Pitch UP 8 semitones — Mario has a VERY high-pitched voice
RVC_INDEX_RATE = 0.85  # High = more Mario character from training data
RVC_PROTECT = 0.33  # Lower = more voice character conversion
RVC_F0_METHOD = "pm"  # Fastest f0 method (~0.5s vs crepe ~3-10s)

# --- Speed mode ---
# False = XTTS v2 voice cloning (quality, ~10-30s), True = Edge TTS (fast, ~1.5s)
FAST_MODE = True

# --- XTTS inference params (defaults — natural sounding) ---
XTTS_TEMPERATURE = 0.65
XTTS_TOP_K = 50
XTTS_TOP_P = 0.85
XTTS_REP_PENALTY = 2.0
XTTS_COND_LEN = 6

# --- Edge TTS settings (fallback only) ---
EDGE_VOICE = "en-US-GuyNeural"
EDGE_PITCH_SHIFT = 0
RATE = "+20%"  # Faster speech for party energy
PITCH_OFFSET = "+0Hz"

# --- Audio cache for instant playback (LRU with max 50 entries) ---
_audio_cache = {}
_cache_order = []
MAX_CACHE_SIZE = 50
_rvc_lock = threading.Lock()  # Serialize RVC GPU calls to prevent contention
CACHED_PHRASES = [
    "It's-a me, Mario!",
    "Wahoo!",
    "Mama mia!",
    "Let's-a go!",
    "Don't forget to wash-a your hands!",
    "Nice to meet-a you!",
    "See you later!",
    "Okie dokie!",
    "Here we go!",
    "That's-a funny!",
]


def init_tts():
    """Initialize TTS — load base TTS engine and RVC Mario voice model."""
    global _xtts_model, _xtts_available, _gpt_cond_latents, _speaker_embedding
    global _rvc_model, _rvc_available

    if DEBUG_TTS:
        logger.info("[DEBUG_TTS] init_tts: START")

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

    # --- Load RVC Mario voice conversion model (if enabled) ---
    if USE_RVC and os.path.exists(RVC_MODEL_PATH):
        try:
            logger.info("[DEBUG_TTS] init_tts: loading RVC Mario model (TITAN 500 epoch)...")
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

    if DEBUG_TTS:
        logger.info(f"[DEBUG_TTS] init_tts: END (fast={FAST_MODE}, xtts={_xtts_available}, rvc={_rvc_available})")


def precache_phrases():
    """Pre-cache common Mario phrases at startup for instant playback."""
    if not CACHED_PHRASES:
        return
    logger.info(f"[DEBUG_TTS] precache: warming {len(CACHED_PHRASES)} phrases...")
    cache_start = time.time()
    for phrase in CACHED_PHRASES:
        try:
            audio = synthesize(phrase)
            _audio_cache[f"{EDGE_VOICE}:{phrase.strip().lower()}"] = audio
        except Exception as e:
            logger.warning(f"[DEBUG_TTS] precache: failed '{phrase[:30]}': {e}")
    logger.info(f"[DEBUG_TTS] precache: done in {time.time() - cache_start:.1f}s ({len(_audio_cache)} cached)")


def synthesize(text: str, rate: str = None, pitch: str = None) -> bytes:
    """Convert text to Mario-voiced speech audio.

    Pipeline: Cache check → Base TTS (Edge or XTTS) → RVC voice conversion (Mario).
    """
    # Check cache first for instant playback (key includes voice params)
    _rate = rate or "+0%"
    _pitch = pitch or "+0Hz"
    cache_key = f"{EDGE_VOICE}:{text.strip().lower()}:{_rate}:{_pitch}"
    if cache_key in _audio_cache:
        if DEBUG_TTS:
            logger.info(f"[DEBUG_TTS] synthesize: CACHE HIT '{text[:40]}...'")
        return _audio_cache[cache_key]

    if DEBUG_TTS:
        logger.info(f"[DEBUG_TTS] synthesize: START text='{text[:50]}...'")

    start = time.time()

    # Step 1: Generate base speech
    if FAST_MODE or not _xtts_available:
        base_wav = _synthesize_edge(text, rate, pitch)
    else:
        try:
            base_wav = _synthesize_xtts_raw(text)
        except Exception as e:
            logger.error(f"[DEBUG_TTS] synthesize: XTTS failed: {e}, falling back to Edge")
            base_wav = _synthesize_edge(text, rate, pitch)

    base_time = time.time() - start

    # Step 2: Convert voice to Mario via RVC (if enabled)
    if USE_RVC:
        result = _apply_rvc(base_wav)
    else:
        result = base_wav

    total = time.time() - start
    if DEBUG_TTS:
        logger.info(f"[DEBUG_TTS] synthesize: END total={total:.1f}s (base={base_time:.1f}s + rvc={total - base_time:.1f}s)")

    # Cache short phrases for future instant playback (LRU eviction)
    if len(text) < 60:
        _audio_cache[cache_key] = result
        if cache_key not in _cache_order:
            _cache_order.append(cache_key)
        if len(_cache_order) > MAX_CACHE_SIZE:
            evict_key = _cache_order.pop(0)
            _audio_cache.pop(evict_key, None)

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

        # Unique temp files per call (thread-safe)
        tid = threading.current_thread().ident
        tmp_in = os.path.join(tempfile.gettempdir(), f"mario_rvc_in_{tid}.wav")
        tmp_out = os.path.join(tempfile.gettempdir(), f"mario_rvc_out_{tid}.wav")
        with open(tmp_in, "wb") as f:
            f.write(wav_bytes)

        # Serialize RVC GPU access
        with _rvc_lock:
            _rvc_model.infer_file(tmp_in, tmp_out)

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
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(lambda: asyncio.run(_edge_async(text, rate, pitch)))
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

    tmp_path = os.path.join(tempfile.gettempdir(), "mario_tts_output.mp3")
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
