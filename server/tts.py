"""Text-to-speech using Edge TTS with Mario-like voice."""

import io
import wave
import logging
import asyncio
import tempfile
import os
import numpy as np
from scipy import signal as scipy_signal

DEBUG_TTS = True
logger = logging.getLogger(__name__)

# Edge TTS voice — use a lively male voice, then pitch-shift for Mario
EDGE_VOICE = "en-US-GuyNeural"  # Energetic male voice
PITCH_SHIFT_SEMITONES = 3  # Shift pitch up to sound more Mario-like
RATE = "+15%"  # Slightly faster for Mario's energy
PITCH_OFFSET = "+3Hz"  # Additional pitch adjustment in Edge TTS


def init_tts():
    """Initialize TTS — verify edge-tts is available."""
    if DEBUG_TTS:
        logger.info("[DEBUG_TTS] init_tts: START")
    try:
        import edge_tts
        logger.info(f"[DEBUG_TTS] init_tts: edge-tts loaded, voice={EDGE_VOICE}")
    except ImportError:
        logger.error("[DEBUG_TTS] init_tts: edge-tts not installed! pip install edge-tts")
    if DEBUG_TTS:
        logger.info("[DEBUG_TTS] init_tts: END")


def pitch_shift(audio_data: np.ndarray, sample_rate: int, semitones: float) -> np.ndarray:
    """Shift pitch of audio by resampling."""
    if semitones == 0:
        return audio_data
    factor = 2 ** (semitones / 12.0)
    new_length = int(len(audio_data) / factor)
    shifted = scipy_signal.resample(audio_data, new_length)
    return shifted.astype(np.int16)


def synthesize(text: str, rate: str = None, pitch: str = None) -> bytes:
    """Convert text to Mario-voiced speech audio.
    
    Args:
        text: Text to speak as Mario
        rate: Override speech rate (e.g. "+15%", "-10%")
        pitch: Override pitch offset (e.g. "+3Hz", "-2Hz")
        
    Returns:
        WAV audio bytes (or MP3 converted to WAV)
    """
    if DEBUG_TTS:
        logger.info(f"[DEBUG_TTS] synthesize: START text='{text[:50]}...' rate={rate} pitch={pitch}")

    try:
        # Run async edge-tts in sync context
        loop = None
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            pass

        if loop and loop.is_running():
            # We're in an async context — use a new thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(_synthesize_sync, text, rate, pitch)
                audio_bytes = future.result(timeout=30)
        else:
            audio_bytes = asyncio.run(_synthesize_async(text, rate, pitch))

        if DEBUG_TTS:
            logger.info(f"[DEBUG_TTS] synthesize: END, audio_size={len(audio_bytes) if audio_bytes else 0}")
        return audio_bytes or b""

    except Exception as e:
        logger.error(f"[DEBUG_TTS] synthesize: error: {e}")
        return b""


def _synthesize_sync(text: str, rate: str = None, pitch: str = None) -> bytes:
    """Sync wrapper for edge-tts."""
    return asyncio.run(_synthesize_async(text, rate, pitch))


async def _synthesize_async(text: str, rate: str = None, pitch: str = None) -> bytes:
    """Generate speech using edge-tts."""
    import edge_tts

    communicate = edge_tts.Communicate(
        text,
        voice=EDGE_VOICE,
        rate=rate or RATE,
        pitch=pitch or PITCH_OFFSET,
    )

    # Write to temp file, then read back
    tmp_path = os.path.join(tempfile.gettempdir(), "mario_tts_output.mp3")
    await communicate.save(tmp_path)

    # Read MP3 and convert to WAV using soundfile if available
    try:
        import soundfile as sf
        audio_data, sample_rate = sf.read(tmp_path)

        # Convert to int16
        if audio_data.dtype != np.int16:
            audio_data = (audio_data * 32767).astype(np.int16)

        # Make mono if stereo
        if len(audio_data.shape) > 1:
            audio_data = audio_data[:, 0]

        # Pitch shift for Mario effect
        if PITCH_SHIFT_SEMITONES != 0:
            audio_data = pitch_shift(audio_data, sample_rate, PITCH_SHIFT_SEMITONES)

        # Pack into WAV
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(audio_data.tobytes())

        wav_buffer.seek(0)
        return wav_buffer.read()

    except Exception as e:
        logger.warning(f"[DEBUG_TTS] Couldn't convert MP3 to WAV: {e}. Returning raw MP3.")
        with open(tmp_path, "rb") as f:
            return f.read()
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
