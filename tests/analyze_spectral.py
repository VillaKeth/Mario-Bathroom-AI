"""Analyze spectral features of vomit audio files to build detector thresholds."""
import librosa
import numpy as np
import os

test_dir = os.path.join(os.path.dirname(__file__))
audio_files = [f for f in os.listdir(test_dir) if f.endswith(('.wav', '.mp3'))]

print("=== SPECTRAL ANALYSIS OF VOMIT AUDIO ===\n")
print(f"{'File':42s} {'centroid':>8s} {'flat':>7s} {'bw':>7s} {'zcr':>7s} {'rms':>7s} {'evar':>9s} {'emax':>7s}")
print("-" * 100)

all_features = []

for fname in sorted(audio_files):
    fpath = os.path.join(test_dir, fname)
    try:
        y, sr = librosa.load(fpath, sr=16000, duration=10)
        spectral_centroid = np.mean(librosa.feature.spectral_centroid(y=y, sr=sr))
        spectral_flatness = np.mean(librosa.feature.spectral_flatness(y=y))
        spectral_bandwidth = np.mean(librosa.feature.spectral_bandwidth(y=y, sr=sr))
        zcr = np.mean(librosa.feature.zero_crossing_rate(y))
        rms = np.mean(librosa.feature.rms(y=y))
        rms_frames = librosa.feature.rms(y=y)[0]
        energy_var = np.var(rms_frames)
        energy_max = np.max(rms_frames)

        features = {
            'file': fname, 'centroid': spectral_centroid, 'flatness': spectral_flatness,
            'bandwidth': spectral_bandwidth, 'zcr': zcr, 'rms': rms,
            'energy_var': energy_var, 'energy_max': energy_max
        }
        all_features.append(features)

        short = fname[:40]
        print(f"{short:42s} {spectral_centroid:8.0f} {spectral_flatness:7.4f} {spectral_bandwidth:7.0f} {zcr:7.4f} {rms:7.4f} {energy_var:9.6f} {energy_max:7.4f}")
    except Exception as e:
        print(f"{fname}: ERROR - {e}")

# Now compare with speech-like audio - generate a simple speech reference
print("\n=== REFERENCE: Typical speech features ===")
# Generate simple sine wave (approximates voiced speech fundamental)
t = np.linspace(0, 3, 16000 * 3)
speech_like = 0.1 * np.sin(2 * np.pi * 200 * t) * (1 + 0.3 * np.sin(2 * np.pi * 3 * t))
speech_like = speech_like.astype(np.float32)

sc = np.mean(librosa.feature.spectral_centroid(y=speech_like, sr=16000))
sf = np.mean(librosa.feature.spectral_flatness(y=speech_like))
sb = np.mean(librosa.feature.spectral_bandwidth(y=speech_like, sr=16000))
zc = np.mean(librosa.feature.zero_crossing_rate(speech_like))
rm = np.mean(librosa.feature.rms(y=speech_like))
rf = librosa.feature.rms(y=speech_like)[0]
ev = np.var(rf)
em = np.max(rf)
print(f"{'Synthetic speech ref':42s} {sc:8.0f} {sf:7.4f} {sb:7.0f} {zc:7.4f} {rm:7.4f} {ev:9.6f} {em:7.4f}")

if all_features:
    print("\n=== SUMMARY RANGES (vomit audio) ===")
    for key in ['centroid', 'flatness', 'bandwidth', 'zcr', 'rms', 'energy_var', 'energy_max']:
        vals = [f[key] for f in all_features]
        print(f"  {key:15s}: min={min(vals):.4f}  max={max(vals):.4f}  mean={np.mean(vals):.4f}")
