"""Speech-to-text using faster-whisper."""

import io
import logging
import numpy as np
from faster_whisper import WhisperModel

DEBUG_STT = True
logger = logging.getLogger(__name__)

# Global model instance
_model: WhisperModel = None


def init_model(model_size: str = "base", device: str = "auto", compute_type: str = "auto"):
    """Initialize the Whisper model.
    
    Args:
        model_size: Model size — 'tiny', 'base', 'small', 'medium', 'large-v3'
        device: 'cuda' for GPU, 'cpu' for CPU, 'auto' to detect
        compute_type: 'float16' for GPU, 'int8' for CPU, 'auto' to detect
    """
    global _model
    if DEBUG_STT:
        logger.info(f"[DEBUG_STT] init_model: START size={model_size} device={device}")

    if device == "auto":
        try:
            import torch
            if torch.cuda.is_available():
                device = "cuda"
            else:
                device = "cpu"
        except ImportError:
            device = "cpu"

    if compute_type == "auto":
        if device == "cuda":
            compute_type = "float16"
        else:
            compute_type = "int8"
    
    if DEBUG_STT:
        logger.info(f"[DEBUG_STT] init_model: using device={device} compute_type={compute_type}")

    try:
        _model = WhisperModel(model_size, device=device, compute_type=compute_type)
    except ValueError as e:
        # float16 not supported — fall back to cpu/int8
        logger.warning(f"[DEBUG_STT] init_model: {e}, falling back to cpu/int8")
        device = "cpu"
        compute_type = "int8"
        _model = WhisperModel(model_size, device=device, compute_type=compute_type)
    if DEBUG_STT:
        logger.info(f"[DEBUG_STT] init_model: loaded on {device} with {compute_type}")


def transcribe(audio_data: bytes, sample_rate: int = 16000) -> str:
    """Transcribe audio bytes to text.
    
    Args:
        audio_data: Raw PCM audio bytes (int16, mono)
        sample_rate: Audio sample rate (default 16000 for Whisper)
    
    Returns:
        Transcribed text string
    """
    if _model is None:
        raise RuntimeError("Whisper model not initialized. Call init_model() first.")

    if DEBUG_STT:
        logger.info(f"[DEBUG_STT] transcribe: START, audio_bytes={len(audio_data)}")

    # Convert bytes to numpy float32 array
    if len(audio_data) < 2:
        if DEBUG_STT:
            logger.info("[DEBUG_STT] transcribe: audio too small, skipping")
        return ""
    try:
        audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
    except ValueError as e:
        logger.warning(f"[DEBUG_STT] transcribe: invalid audio format: {e}")
        return ""

    if len(audio_np) < sample_rate * 0.5:
        if DEBUG_STT:
            logger.info("[DEBUG_STT] transcribe: audio too short, skipping")
        return ""

    segments, info = _model.transcribe(
        audio_np,
        beam_size=5,
        language="en",
        vad_filter=True,
        vad_parameters=dict(
            min_silence_duration_ms=500,
            speech_pad_ms=200,
        ),
    )

    text = " ".join(seg.text.strip() for seg in segments).strip()

    if DEBUG_STT:
        logger.info(f"[DEBUG_STT] transcribe: result='{text}' lang={info.language} prob={info.language_probability:.2f}")

    return text
