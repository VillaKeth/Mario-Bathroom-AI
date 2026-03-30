"""Generate synthetic retching/gagging audio for PANNs distress detection testing."""
import numpy as np
import wave
import os

sr = 16000
duration = 4.0
t = np.linspace(0, duration, int(sr * duration))

# Layer 1: Low groan (100-250Hz with vibrato)
groan = 0.4 * np.sin(2 * np.pi * 150 * t + 3 * np.sin(2 * np.pi * 5 * t))

# Layer 2: Irregular retching bursts (short loud bursts)
retch = np.zeros_like(t)
burst_times = [0.5, 1.2, 2.0, 2.8, 3.5]
for bt in burst_times:
    mask = (t >= bt) & (t < bt + 0.3)
    retch[mask] = 0.6 * np.random.randn(mask.sum()) * np.exp(-10 * (t[mask] - bt))

# Layer 3: Gargling/gurgling (amplitude-modulated noise)
gargle_env = (0.5 + 0.5 * np.sin(2 * np.pi * 8 * t)) * (0.5 + 0.5 * np.sin(2 * np.pi * 3 * t))
gargle = 0.3 * np.random.randn(len(t)) * gargle_env

# Layer 4: Stomach rumble (very low freq)
rumble = 0.2 * np.sin(2 * np.pi * 40 * t + 2 * np.sin(2 * np.pi * 2 * t))

combined = groan + retch + gargle + rumble
combined = combined / np.max(np.abs(combined)) * 0.8
audio_int16 = (combined * 32767).astype(np.int16)

out_path = os.path.join(os.path.dirname(__file__), "test_retch_audio.wav")
with wave.open(out_path, "wb") as wf:
    wf.setnchannels(1)
    wf.setsampwidth(2)
    wf.setframerate(sr)
    wf.writeframes(audio_int16.tobytes())

raw_path = os.path.join(os.path.dirname(__file__), "test_retch_raw.pcm")
with open(raw_path, "wb") as f:
    f.write(audio_int16.tobytes())

print(f"Generated: {out_path} ({os.path.getsize(out_path)} bytes)")
print(f"Generated: {raw_path} ({os.path.getsize(raw_path)} bytes)")
print(f"Duration: {duration}s, SR: {sr}Hz, Samples: {len(audio_int16)}")
