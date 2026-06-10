"""Offline reference-audio transcription using faster-whisper.

Zero-shot voice cloners (GPT-SoVITS, Fish Speech) need the transcript of the
reference clip (the "prompt_text") to clone a voice. This produces it fully
locally — no cloud service, no LLM query. This is the piece that lets the whole
voice pipeline run independently and offline.
"""
import logging
import os

logger = logging.getLogger(__name__)

_model = None

try:
    from faster_whisper import WhisperModel
    _HAS_WHISPER = True
except ImportError:  # pragma: no cover - exercised only when dep missing
    WhisperModel = None
    _HAS_WHISPER = False
    logger.warning(
        "[voice_transcribe] faster-whisper not installed — reference clips "
        "cannot be auto-transcribed. Install with: pip install faster-whisper"
    )


def is_available() -> bool:
    return _HAS_WHISPER


def _get_model(model_size: str = "base"):
    """Lazily load a single shared Whisper model (GPU if available, else CPU)."""
    global _model
    if _model is not None:
        return _model
    device, compute = "cpu", "int8"
    try:
        import torch
        if torch.cuda.is_available():
            device, compute = "cuda", "float16"
    except Exception:
        pass
    try:
        _model = WhisperModel(model_size, device=device, compute_type=compute)
    except ValueError as e:
        logger.warning(f"[voice_transcribe] {e} — falling back to cpu/int8")
        _model = WhisperModel(model_size, device="cpu", compute_type="int8")
    logger.info(f"[voice_transcribe] Whisper '{model_size}' loaded on {device}/{compute}")
    return _model


def transcribe_file(audio_path: str, model_size: str = "base") -> dict:
    """Transcribe an audio file to text. faster-whisper decodes via PyAV, so the
    file extension does not need to match the real format (wav/mp3/webm all work).

    Returns {"text": str, "language": str, "available": bool, "error": str|None}.
    """
    if not _HAS_WHISPER:
        return {"text": "", "language": None, "available": False,
                "error": "faster-whisper not installed"}
    if not audio_path or not os.path.exists(audio_path):
        return {"text": "", "language": None, "available": True,
                "error": f"audio file not found: {audio_path}"}
    try:
        model = _get_model(model_size)
        try:
            segments, info = model.transcribe(audio_path, beam_size=5, vad_filter=True)
            segments = list(segments)
        except (ValueError, RuntimeError, ImportError) as vad_err:
            # VAD needs the optional onnxruntime package; transcribe without it.
            logger.info(f"[voice_transcribe] VAD unavailable ({vad_err}); retrying without VAD")
            segments, info = model.transcribe(audio_path, beam_size=5, vad_filter=False)
            segments = list(segments)
        text = " ".join(seg.text.strip() for seg in segments).strip()
        logger.info(
            f"[voice_transcribe] {os.path.basename(audio_path)} -> "
            f"'{text[:80]}' (lang={info.language} p={info.language_probability:.2f})"
        )
        return {"text": text, "language": info.language, "available": True, "error": None}
    except Exception as e:
        logger.error(f"[voice_transcribe] transcription failed: {e}")
        return {"text": "", "language": None, "available": True, "error": str(e)}
