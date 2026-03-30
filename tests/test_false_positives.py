"""Test that the detector doesn't false-positive on normal speech/silence."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'server'))

import numpy as np
from audio_distress import init_detector, detect_distress

print("Loading PANNs model...")
init_detector("cpu")

print("\n=== FALSE POSITIVE TESTS ===\n")

results = []

# Test 1: Pure silence
print("1. Pure silence (2 seconds):")
silence = np.zeros(32000, dtype=np.int16)
r = detect_distress(silence.tobytes(), 16000)
status = "❌ FALSE POS" if r["is_distress"] else "✅ CORRECT (no detect)"
print(f"   {status} - confidence={r['confidence']:.2f}")
results.append(not r["is_distress"])

# Test 2: White noise (ambient)
print("\n2. White noise (ambient sound):")
noise = (np.random.randn(32000) * 1000).astype(np.int16)
r = detect_distress(noise.tobytes(), 16000)
status = "❌ FALSE POS" if r["is_distress"] else "✅ CORRECT (no detect)"
print(f"   {status} - confidence={r['confidence']:.2f}, spectral={r.get('spectral', {}).get('spectral_score', 0):.2f}")
results.append(not r["is_distress"])

# Test 3: Sine wave (pure tone, like a beep)
print("\n3. Sine wave (pure tone):")
t = np.linspace(0, 2, 32000)
sine = (np.sin(2 * np.pi * 440 * t) * 10000).astype(np.int16)
r = detect_distress(sine.tobytes(), 16000)
status = "❌ FALSE POS" if r["is_distress"] else "✅ CORRECT (no detect)"
print(f"   {status} - confidence={r['confidence']:.2f}")
results.append(not r["is_distress"])

# Test 4: Sustained noise (like hand dryer - low burst ratio)
print("\n4. Sustained noise (hand dryer simulation):")
sustained = (np.random.randn(32000) * 5000).astype(np.int16)
r = detect_distress(sustained.tobytes(), 16000)
status = "❌ FALSE POS" if r["is_distress"] else "✅ CORRECT (no detect)"
spectral = r.get('spectral', {})
print(f"   {status} - confidence={r['confidence']:.2f}, spectral={spectral.get('spectral_score', 0):.2f}")
if spectral.get("features"):
    f = spectral["features"]
    print(f"   burst_ratio={f['burst_ratio']:.1f}, bursts={f['burst_count']}, flat={f['spectral_flatness']:.3f}")
results.append(not r["is_distress"])

# Test 5: Speech-like signal (vowel sounds)
print("\n5. Speech-like signal (vowel formants):")
t = np.linspace(0, 2, 32000)
# Simulate vowel: F0=120Hz + formants at 500Hz, 1500Hz
speech = (np.sin(2*np.pi*120*t) * 3000 + np.sin(2*np.pi*500*t) * 2000 +
          np.sin(2*np.pi*1500*t) * 1000).astype(np.int16)
r = detect_distress(speech.tobytes(), 16000)
status = "❌ FALSE POS" if r["is_distress"] else "✅ CORRECT (no detect)"
print(f"   {status} - confidence={r['confidence']:.2f}, speech_score={r.get('speech_score', 0):.2f}")
results.append(not r["is_distress"])

passed = sum(results)
total = len(results)
print(f"\n=== FALSE POSITIVE RESULTS: {passed}/{total} passed ===")
if passed == total:
    print("🎉 PERFECT — No false positives!")
else:
    print("⚠️  Some false positives detected — needs tuning")
