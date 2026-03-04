"""Audio playback for Mario's voice responses."""

import io
import wave
import logging
import threading
import queue
import numpy as np
import sounddevice as sd

DEBUG_PLAYBACK = True
logger = logging.getLogger(__name__)


class AudioPlayback:
    """Plays audio (WAV bytes) through the speakers."""

    def __init__(self):
        self._play_queue = queue.Queue()
        self._playing = False
        self._thread = None

    def start(self):
        """Start the playback worker thread."""
        if DEBUG_PLAYBACK:
            logger.info("[DEBUG_PLAYBACK] AudioPlayback.start: starting worker")
        self._playing = True
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop playback."""
        if DEBUG_PLAYBACK:
            logger.info("[DEBUG_PLAYBACK] AudioPlayback.stop: stopping worker")
        self._playing = False
        if self._thread:
            self._thread.join(timeout=2.0)

    def play(self, wav_bytes: bytes):
        """Queue WAV audio bytes for playback."""
        if wav_bytes and len(wav_bytes) > 0:
            self._play_queue.put(wav_bytes)

    @property
    def is_playing(self) -> bool:
        return not self._play_queue.empty()

    def _worker(self):
        """Background thread that plays queued audio."""
        while self._playing:
            try:
                wav_bytes = self._play_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            try:
                self._play_wav(wav_bytes)
            except Exception as e:
                logger.error(f"[DEBUG_PLAYBACK] _worker: playback error: {e}")

    def _play_wav(self, wav_bytes: bytes):
        """Play a WAV byte buffer."""
        if DEBUG_PLAYBACK:
            logger.info(f"[DEBUG_PLAYBACK] _play_wav: playing {len(wav_bytes)} bytes")

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

            sd.play(audio, samplerate=sample_rate)
            sd.wait()

            if DEBUG_PLAYBACK:
                logger.info("[DEBUG_PLAYBACK] _play_wav: done")

        except Exception as e:
            logger.error(f"[DEBUG_PLAYBACK] _play_wav: error: {e}")
