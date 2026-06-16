"""Audio playback for Mario's voice responses."""

import io
import wave
import logging
import threading
import queue
import numpy as np
import sounddevice as sd
import pygame

DEBUG_PLAYBACK = True
DEBUG_AUDIO = True
logger = logging.getLogger(__name__)


class AudioPlayback:
    """Plays audio (WAV bytes) through the speakers."""

    def __init__(self):
        self._play_queue = queue.Queue()
        self._playing = False
        self._thread = None
        self._actively_playing = False
        self._lock = threading.Lock()
        self._gain = 1.0  # Volume multiplier (0.0 - 2.0)

    def start(self):
        """Start the playback worker thread."""
        if DEBUG_PLAYBACK:
            logger.info("[DEBUG_PLAYBACK] AudioPlayback.start: starting worker")
        self._playing = True
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop playback and drain queue."""
        if DEBUG_PLAYBACK:
            logger.info("[DEBUG_PLAYBACK] AudioPlayback.stop: stopping worker")
        with self._lock:
            self._playing = False
        # Drain any queued audio to prevent stale playback on restart
        while not self._play_queue.empty():
            try:
                self._play_queue.get_nowait()
            except queue.Empty:
                break
        # Stop any currently playing audio
        try:
            sd.stop()
        except Exception:
            pass
        if self._thread:
            self._thread.join(timeout=2.0)

    def play(self, wav_bytes: bytes, on_start=None):
        """Queue WAV audio bytes for playback. on_start (optional) is called the
        moment this clip actually begins playing — used to sync the countdown
        visual to the spoken number instead of to message arrival."""
        if not wav_bytes or len(wav_bytes) < 44:
            if DEBUG_PLAYBACK:
                logger.warning(f"[DEBUG_PLAYBACK] play: invalid audio ({len(wav_bytes) if wav_bytes else 0} bytes), skipping")
            return
        self._play_queue.put((wav_bytes, on_start))

    def clear(self):
        """Interrupt current playback and drain the queue (for self-interruption).
        
        Unlike stop(), this keeps the worker thread alive for future playback.
        """
        if DEBUG_PLAYBACK:
            logger.info("[DEBUG_PLAYBACK] clear: interrupting playback and draining queue")
        # Drain queued audio
        while not self._play_queue.empty():
            try:
                self._play_queue.get_nowait()
            except queue.Empty:
                break
        # Stop currently playing audio
        try:
            sd.stop()
        except Exception:
            pass

    def set_volume(self, gain: float):
        """Set the volume/gain multiplier (clamped to 0.0-2.0)."""
        self._gain = max(0.0, min(2.0, gain))
        if DEBUG_AUDIO:
            logger.info(f"[DEBUG_AUDIO] set_volume: gain set to {self._gain:.2f}")

    def get_volume(self) -> float:
        """Get the current volume/gain multiplier."""
        return self._gain

    @property
    def is_playing(self) -> bool:
        with self._lock:
            return self._actively_playing or not self._play_queue.empty()

    # ── Memorial music (MP3 via pygame.mixer.music) ──────────────
    def play_memorial_music(self, path: str, loops: int = 0):
        """Play an MP3 file using pygame.mixer.music.
        
        Args:
            path: Path to the MP3 file.
            loops: Number of extra repeats (0=play once, 1=play twice, etc.)
        """
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            pygame.mixer.music.load(path)
            pygame.mixer.music.set_volume(0.5)
            pygame.mixer.music.play(loops=loops)  # Use the parameter
            if DEBUG_PLAYBACK:
                logger.info(f"[DEBUG_PLAYBACK] Memorial music started: {path} (loops={loops})")
        except Exception as e:
            logger.error(f"[DEBUG_PLAYBACK] Memorial music error: {e}")

    def stop_memorial_music(self, fadeout_ms: int = 3000):
        """Fade out and stop memorial music."""
        try:
            if pygame.mixer.music.get_busy():
                pygame.mixer.music.fadeout(fadeout_ms)
                if DEBUG_PLAYBACK:
                    logger.info(f"[DEBUG_PLAYBACK] Memorial music fading out ({fadeout_ms}ms)")
        except Exception as e:
            logger.error(f"[DEBUG_PLAYBACK] Memorial music stop error: {e}")

    @property
    def is_music_playing(self) -> bool:
        """Check if memorial music is currently playing."""
        try:
            return pygame.mixer.music.get_busy()
        except Exception:
            return False

    def _worker(self):
        """Background thread that plays queued audio."""
        while self._playing:
            try:
                item = self._play_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            # Items are (wav_bytes, on_start); tolerate a bare buffer too.
            if isinstance(item, tuple):
                wav_bytes, on_start = item
            else:
                wav_bytes, on_start = item, None
            try:
                if on_start:
                    try:
                        on_start()
                    except Exception as cb_e:
                        logger.error(f"[DEBUG_PLAYBACK] on_start callback error: {cb_e}")
                self._play_wav(wav_bytes)
            except Exception as e:
                logger.error(f"[DEBUG_PLAYBACK] _worker: playback error: {e}")

    def _play_wav(self, wav_bytes: bytes):
        """Play a WAV byte buffer."""
        if DEBUG_PLAYBACK:
            logger.info(f"[DEBUG_PLAYBACK] _play_wav: playing {len(wav_bytes)} bytes")

        with self._lock:
            self._actively_playing = True

        wav_buffer = io.BytesIO(wav_bytes)
        try:
            with wave.open(wav_buffer, "rb") as wf:
                sample_rate = wf.getframerate()
                channels = wf.getnchannels()
                sample_width = wf.getsampwidth()
                frames = wf.readframes(wf.getnframes())

            if sample_width == 2:
                audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32767.0
            elif sample_width == 4:
                audio = np.frombuffer(frames, dtype=np.int32).astype(np.float32) / 2147483647.0
            else:
                logger.error(f"[DEBUG_PLAYBACK] unsupported sample width: {sample_width}")
                return

            if channels > 1:
                audio = audio.reshape(-1, channels)
            else:
                audio = audio.reshape(-1, 1)

            # Apply gain/volume multiplier
            if self._gain != 1.0:
                if DEBUG_AUDIO:
                    logger.info(f"[DEBUG_AUDIO] _play_wav: applying gain {self._gain:.2f}")
                audio = audio * self._gain
                audio = np.clip(audio, -1.0, 1.0)

            sd.play(audio, samplerate=sample_rate)
            sd.wait()

            if DEBUG_PLAYBACK:
                logger.info("[DEBUG_PLAYBACK] _play_wav: done")

        except Exception as e:
            logger.error(f"[DEBUG_PLAYBACK] _play_wav: error: {e}")
        finally:
            with self._lock:
                self._actively_playing = False
