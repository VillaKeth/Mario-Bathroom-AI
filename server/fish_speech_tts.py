"""Fish Speech v2.2+ TTS engine wrapper.

Provides Mario voice synthesis via Fish Speech's voice-cloning model.
Gracefully degrades if fish-speech is not installed — is_available()
returns False and synthesize() returns None.

Usage:
    tts = FishSpeechTTS(reference_audio="mario_ref_audio/mario_reference_sentences.wav")
    if tts.is_available():
        audio_bytes = await tts.synthesize("Let's-a go!")
"""

import logging
import os
import asyncio

logger = logging.getLogger(__name__)

# Try importing fish_speech — package may not be installed
_fish_speech_available = False
try:
    import fish_speech  # noqa: F401
    _fish_speech_available = True
    logger.debug("[fish_speech_tts] fish-speech package found")
except ImportError:
    logger.debug("[fish_speech_tts] fish-speech package not installed — engine will be unavailable")


class FishSpeechTTS:
    """Fish Speech v2.2+ voice-cloning TTS wrapper.

    Uses a reference audio clip to clone Mario's voice characteristics.
    Falls back gracefully if fish-speech is not installed or model fails to load.
    """

    engine_name = "fish_speech"

    def __init__(self, reference_audio: str, device: str = "cuda"):
        self._reference_audio = reference_audio
        self._device = device
        self._model = None
        self._available = False

        if not _fish_speech_available:
            logger.debug("[fish_speech_tts] __init__: skipping model load — package not installed")
            return

        if not os.path.isfile(reference_audio):
            logger.debug(f"[fish_speech_tts] __init__: reference audio not found: {reference_audio}")
            return

        try:
            self._load_model()
        except Exception as e:
            logger.debug(f"[fish_speech_tts] __init__: model load failed: {e}")
            self._model = None
            self._available = False

    def _load_model(self):
        """Load Fish Speech model with the reference audio for voice cloning."""
        logger.debug(f"[fish_speech_tts] Loading model on device={self._device}, ref={self._reference_audio}")
        try:
            # Fish Speech API — actual import path may vary by version
            from fish_speech.models import TTSModel  # type: ignore

            self._model = TTSModel.from_pretrained(
                "fishaudio/fish-speech-1.5",
                device=self._device,
            )
            self._model.set_reference_audio(self._reference_audio)
            self._available = True
            logger.debug("[fish_speech_tts] Model loaded successfully")
        except (ImportError, AttributeError) as e:
            logger.debug(f"[fish_speech_tts] Fish Speech API not compatible: {e}")
            self._available = False
        except Exception as e:
            logger.debug(f"[fish_speech_tts] Model load error: {e}")
            self._available = False

    def is_available(self) -> bool:
        """True if Fish Speech model loaded successfully and is ready for synthesis."""
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
        if not self._available or self._model is None:
            logger.debug("[fish_speech_tts] synthesize: engine unavailable, returning None")
            return None

        logger.debug(f"[fish_speech_tts] synthesize: text='{text[:60]}...'")
        try:
            loop = asyncio.get_event_loop()
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
            result = self._model.synthesize(text)
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
