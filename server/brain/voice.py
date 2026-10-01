"""The fly's voice: Edge speech ring-modulated by a ~200 Hz wingbeat, and a
procedural takeoff buzz. Pure numpy.

Bypasses tts.synthesize and the TTS router on purpose (spec 5.4): the global
tts_mode would clone another character's voice, and the router's last resort
is Mario clips. If Edge is unavailable, the fly buzzes instead of speaking.
"""
import io
import wave
from collections import OrderedDict

import numpy as np

SR_DEFAULT = 24000


def read_wav(b):
    with wave.open(io.BytesIO(b), "rb") as w:
        sr, ch, sw, n = w.getframerate(), w.getnchannels(), w.getsampwidth(), w.getnframes()
        raw = w.readframes(n)
    if sw != 2:
        raise ValueError(f"expected 16-bit WAV, got {8 * sw}-bit")
    x = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    if ch > 1:
        x = x.reshape(-1, ch).mean(axis=1)
    return x, sr


def write_wav(x, sr, peak_db=-3.0):
    x = np.asarray(x, dtype=np.float32)
    peak = float(np.max(np.abs(x))) if len(x) else 0.0
    if peak > 0:
        x = x * (10 ** (peak_db / 20.0) / peak)
    pcm = np.clip(x * 32767.0, -32768, 32767).astype("<i2")
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(int(sr))
        w.writeframes(pcm.tobytes())
    return out.getvalue()


def _wing(phase):
    """A wingbeat is not a sine: fundamental plus two harmonics."""
    return 0.6 * np.sin(phase) + 0.3 * np.sin(2 * phase) + 0.1 * np.sin(3 * phase)


def ring_mod(wav_bytes, carrier_hz=200.0, mix=0.55, bed=0.06):
    x, sr = read_wav(wav_bytes)
    if len(x) == 0:
        return wav_bytes
    t = np.arange(len(x), dtype=np.float32) / sr
    y = (1.0 - mix) * x + mix * x * np.sin(2 * np.pi * carrier_hz * t)
    win = max(1, int(0.01 * sr))
    env = np.convolve(np.abs(x), np.ones(win, np.float32) / win, mode="same")
    if env.max() > 0:
        env = env / env.max()
    y = y + bed * env * _wing(2 * np.pi * carrier_hz * t)  # buzz only while speaking
    return write_wav(y, sr)


def takeoff_buzz(duration_s=0.5, sample_rate=SR_DEFAULT, f0=180.0, f1=230.0, level=1.0):
    n = max(1, int(duration_s * sample_rate))
    t = np.arange(n, dtype=np.float32) / sample_rate
    freq = f0 + (f1 - f0) * (t / max(duration_s, 1e-6))
    phase = 2 * np.pi * np.cumsum(freq) / sample_rate
    env = np.clip(np.minimum(t / 0.03, (duration_s - t) / 0.12), 0.0, 1.0)
    y = _wing(phase) * env * (1.0 + 0.3 * np.sin(2 * np.pi * 12.0 * t))
    level = max(0.0, min(1.0, float(level)))
    return write_wav(y, sample_rate, peak_db=-3.0 - 18.0 * (1.0 - level))


class FlyVoice:
    def __init__(self, edge_fn, carrier_hz=200.0, mix=0.55, bed=0.06, cache_size=64):
        self.edge_fn = edge_fn
        self.carrier_hz, self.mix, self.bed = float(carrier_hz), float(mix), float(bed)
        self._cache = OrderedDict()
        self._cache_size = int(cache_size)

    def _dry(self, text):
        if text in self._cache:
            self._cache.move_to_end(text)
            return self._cache[text]
        try:
            wav = self.edge_fn(text) or b""
        except Exception:
            wav = b""
        if wav:
            self._cache[text] = wav
            while len(self._cache) > self._cache_size:
                self._cache.popitem(last=False)
        return wav

    def speak(self, text):
        text = (text or "").strip()
        if not text:
            return b""
        dry = self._dry(text)
        if dry:
            try:
                return ring_mod(dry, self.carrier_hz, self.mix, self.bed)
            except Exception:
                pass  # not a 16-bit WAV (e.g. Edge's raw mp3 fallback): buzz instead
        return takeoff_buzz(duration_s=min(1.5, 0.25 + 0.12 * len(text.split())),
                            f0=self.carrier_hz - 10.0, f1=self.carrier_hz + 10.0, level=0.6)

    def buzz(self, intensity=1.0):
        """ESCAPE: the 0.5 s takeoff buzz (spec 4.4); intensity sets loudness."""
        i = max(0.0, min(1.0, float(intensity)))
        return takeoff_buzz(duration_s=0.5, level=0.5 + 0.5 * i)
