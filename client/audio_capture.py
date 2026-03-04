"""Audio capture from microphone using sounddevice."""

import logging
import threading
import queue
import numpy as np
import sounddevice as sd

DEBUG_AUDIO = True
logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000  # 16kHz for Whisper compatibility
CHANNELS = 1
BLOCK_SIZE = 4096  # Samples per callback (~256ms at 16kHz)
DTYPE = np.int16


class AudioCapture:
    """Captures audio from the microphone in a background thread."""

    def __init__(self, sample_rate=SAMPLE_RATE, channels=CHANNELS, block_size=BLOCK_SIZE):
        self.sample_rate = sample_rate
        self.channels = channels
        self.block_size = block_size
        self.audio_queue = queue.Queue()
        self._stream = None
        self._running = False

    def _audio_callback(self, indata, frames, time_info, status):
        """Called by sounddevice for each audio block."""
        if status and DEBUG_AUDIO:
            logger.warning(f"[DEBUG_AUDIO] audio_callback: status={status}")
        # Convert float32 to int16 bytes
        audio_int16 = (indata[:, 0] * 32767).astype(np.int16)
        self.audio_queue.put(audio_int16.tobytes())

    def start(self):
        """Start capturing audio."""
        if DEBUG_AUDIO:
            logger.info("[DEBUG_AUDIO] AudioCapture.start: opening mic stream")

        try:
            self._running = True

            # Find an input device if default isn't set
            device = None
            try:
                sd.query_devices(sd.default.device[0], 'input')
            except Exception:
                # No default input — find one, preferring WDM-KS/WASAPI over ASIO
                for i, d in enumerate(sd.query_devices()):
                    if d["max_input_channels"] > 0 and "ASIO" not in d["name"]:
                        device = i
                        logger.info(f"[DEBUG_AUDIO] Trying input device {i}: {d['name']}")
                        break

            if device is None and sd.default.device[0] == -1:
                logger.warning("[DEBUG_AUDIO] No input devices available")
                self._running = False
                return False

            self._stream = sd.InputStream(
                device=device,
                samplerate=self.sample_rate,
                channels=self.channels,
                blocksize=self.block_size,
                dtype="float32",
                callback=self._audio_callback,
            )
            self._stream.start()
            if DEBUG_AUDIO:
                logger.info("[DEBUG_AUDIO] AudioCapture.start: mic stream active")
            return True
        except Exception as e:
            logger.warning(f"[DEBUG_AUDIO] AudioCapture.start: no mic available: {e}")
            self._running = False
            return False

    def stop(self):
        """Stop capturing audio."""
        if DEBUG_AUDIO:
            logger.info("[DEBUG_AUDIO] AudioCapture.stop: closing mic stream")
        self._running = False
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    def get_audio(self, timeout=0.1) -> bytes:
        """Get next audio chunk from the queue.
        
        Returns None if no audio available within timeout.
        """
        try:
            return self.audio_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def drain(self) -> bytes:
        """Drain all available audio from the queue into a single buffer."""
        chunks = []
        while not self.audio_queue.empty():
            try:
                chunks.append(self.audio_queue.get_nowait())
            except queue.Empty:
                break
        return b"".join(chunks) if chunks else None


def list_devices():
    """List available audio devices."""
    devices = sd.query_devices()
    print("Available audio devices:")
    for i, dev in enumerate(devices):
        marker = ""
        if dev["max_input_channels"] > 0:
            marker += " [INPUT]"
        if dev["max_output_channels"] > 0:
            marker += " [OUTPUT]"
        print(f"  {i}: {dev['name']}{marker}")
    return devices
