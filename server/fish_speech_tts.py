"""Fish Speech v0.1.0+ TTS engine wrapper.

Provides character voice synthesis via Fish Speech's voice-cloning model.
Gracefully degrades if fish-speech is not installed — is_available()
returns False and synthesize() returns None.

Usage:
    tts = FishSpeechTTS(reference_audio="voice/reference_audio.wav")
    if tts.is_available():
        audio_bytes = await tts.synthesize("Let's-a go!")
"""

import logging
import os
import asyncio
import tempfile

logger = logging.getLogger(__name__)

# Try importing fish_speech — package may not be installed
_fish_speech_available = False
_fish_speech_version = "unknown"
try:
    import fish_speech  # noqa: F401
    _fish_speech_available = True
    _fish_speech_version = getattr(fish_speech, "__version__", "unknown")
    logger.debug(f"[fish_speech_tts] fish-speech package found (v{_fish_speech_version})")
except ImportError:
    logger.debug("[fish_speech_tts] fish-speech package not installed — engine will be unavailable")


class FishSpeechTTS:
    """Fish Speech v0.1.0+ voice-cloning TTS wrapper.

    Uses a reference audio clip to clone voice characteristics.
    Falls back gracefully if fish-speech is not installed or model fails to load.
    Supports both old API (fish_speech.models.TTSModel) and new API
    (fish_speech.inference_engine / fish_speech.inference).
    """

    engine_name = "fish_speech"

    def __init__(self, reference_audio: str, device: str = "cuda"):
        self._reference_audio = reference_audio
        self._device = device
        self._engine = None
        self._available = False
        self._api_version = None

        if not _fish_speech_available:
            logger.debug("[fish_speech_tts] __init__: skipping — package not installed")
            return

        if not os.path.isfile(reference_audio):
            logger.debug(f"[fish_speech_tts] __init__: reference audio not found: {reference_audio}")
            return

        try:
            self._load_engine()
        except Exception as e:
            logger.debug(f"[fish_speech_tts] __init__: engine load failed: {e}")
            self._engine = None
            self._available = False

    def _load_engine(self):
        """Load Fish Speech engine, trying v0.1.0+ API first, then legacy."""
        logger.debug(f"[fish_speech_tts] Loading engine on device={self._device}, ref={self._reference_audio}")

        # Try v0.1.0+ API first: fish_speech.inference_engine
        try:
            from fish_speech.inference_engine import TTSInferenceEngine  # type: ignore
            self._engine = TTSInferenceEngine(
                reference_audio=self._reference_audio,
                device=self._device,
            )
            self._available = True
            self._api_version = "v0.1.0_inference_engine"
            logger.debug("[fish_speech_tts] Loaded via inference_engine API (v0.1.0+)")
            return
        except (ImportError, AttributeError, TypeError):
            logger.debug("[fish_speech_tts] inference_engine API not available, trying alternatives...")

        # Try alternative v0.1.0 API: fish_speech.inference
        try:
            from fish_speech.inference import TTSInference  # type: ignore
            self._engine = TTSInference(
                reference_audio=self._reference_audio,
                device=self._device,
            )
            self._available = True
            self._api_version = "v0.1.0_inference"
            logger.debug("[fish_speech_tts] Loaded via inference API (v0.1.0)")
            return
        except (ImportError, AttributeError, TypeError):
            logger.debug("[fish_speech_tts] inference API not available, trying legacy...")

        # Try legacy API: fish_speech.models.TTSModel
        try:
            from fish_speech.models import TTSModel  # type: ignore
            self._engine = TTSModel.from_pretrained(
                "fishaudio/fish-speech-1.5",
                device=self._device,
            )
            self._engine.set_reference_audio(self._reference_audio)
            self._available = True
            self._api_version = "legacy"
            logger.debug("[fish_speech_tts] Loaded via legacy TTSModel API")
            return
        except (ImportError, AttributeError, TypeError) as e:
            logger.debug(f"[fish_speech_tts] Legacy API not compatible: {e}")

        logger.warning("[fish_speech_tts] No compatible Fish Speech API found")
        self._available = False

    def is_available(self) -> bool:
        """True if Fish Speech engine loaded successfully and is ready for synthesis."""
        return self._available

    async def synthesize(self, text: str, rate: str = None, pitch: str = None,
                         output_path: str = None, **kwargs) -> bytes | None:
        """Synthesize text to WAV audio bytes using Fish Speech voice cloning.

        Args:
            text: Text to synthesize.
            rate: Speech rate (not all Fish Speech versions support this).
            pitch: Pitch adjustment (not all Fish Speech versions support this).
            output_path: Optional path to save WAV file to.

        Returns:
            WAV audio bytes, or None if synthesis fails or engine unavailable.
        """
        if not self._available or self._engine is None:
            logger.debug("[fish_speech_tts] synthesize: engine unavailable, returning None")
            return None

        logger.debug(f"[fish_speech_tts] synthesize: text='{text[:60]}{'...' if len(text) > 60 else ''}' api={self._api_version}")
        try:
            loop = asyncio.get_running_loop()
            audio_bytes = await loop.run_in_executor(
                None, lambda: self._synthesize_sync(text, rate, pitch, output_path)
            )
            return audio_bytes
        except Exception as e:
            logger.debug(f"[fish_speech_tts] synthesize failed: {e}")
            return None

    def _synthesize_sync(self, text: str, rate: str = None, pitch: str = None,
                         output_path: str = None) -> bytes | None:
        """Synchronous synthesis — called from executor."""
        try:
            if self._api_version in ("v0.1.0_inference_engine", "v0.1.0_inference"):
                # v0.1.0 API: synthesize returns file path or bytes
                if output_path:
                    result = self._engine.synthesize(text=text, output_path=output_path)
                    with open(output_path, "rb") as f:
                        return f.read()
                else:
                    tmp_path = tempfile.mktemp(suffix=".wav")
                    try:
                        result = self._engine.synthesize(text=text, output_path=tmp_path)
                        if isinstance(result, bytes):
                            return result
                        if os.path.isfile(tmp_path):
                            with open(tmp_path, "rb") as f:
                                return f.read()
                        return result
                    finally:
                        if os.path.isfile(tmp_path):
                            os.unlink(tmp_path)
            else:
                # Legacy API
                result = self._engine.synthesize(text)
                if output_path:
                    with open(output_path, "wb") as f:
                        f.write(result)
                return result
        except Exception as e:
            logger.debug(f"[fish_speech_tts] _synthesize_sync error: {e}")
            return None

    def synthesize_sync(self, text: str, rate: str = None, pitch: str = None,
                        nocache: bool = False, **kwargs) -> bytes | None:
        """Synchronous interface matching TTSRouter engine contract.

        Returns WAV bytes or None.
        """
        if not self._available:
            return None
        return self._synthesize_sync(text, rate, pitch)
