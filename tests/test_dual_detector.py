"""Test the dual spectral+PANNs detector against real vomit audio files."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'server'))

import numpy as np
import librosa

from audio_distress import init_detector, detect_distress

print("Loading PANNs model...")
init_detector("cpu")

test_dir = os.path.dirname(__file__)
audio_files = sorted([f for f in os.listdir(test_dir) if f.endswith(('.wav', '.mp3'))])

print(f"\n=== TESTING {len(audio_files)} REAL VOMIT AUDIO FILES ===\n")

detected = 0
total = 0

for fname in audio_files:
    fpath = os.path.join(test_dir, fname)
    try:
        y, sr = librosa.load(fpath, sr=16000, duration=10)
        # Convert to int16 bytes (what detect_distress expects)
        audio_int16 = (y * 32768).clip(-32768, 32767).astype(np.int16)
        audio_bytes = audio_int16.tobytes()

        result = detect_distress(audio_bytes, sample_rate=16000)

        total += 1
        status = "✅ DETECTED" if result["is_distress"] else "❌ MISSED"
        if result["is_distress"]:
            detected += 1

        spectral = result.get("spectral", {})
        spectral_score = spectral.get("spectral_score", 0)
        spectral_reason = spectral.get("reason", "")
        
        short = fname[:50]
        print(f"  {status} {short}")
        print(f"           PANNs combined={result['confidence']:.2f}, spectral={spectral_score:.2f}")
        if spectral.get("features"):
            f = spectral["features"]
            print(f"           flat={f['spectral_flatness']:.3f} burst={f['burst_ratio']:.1f} "
                  f"bursts={f['burst_count']} bw={f['spectral_bandwidth']:.0f} "
                  f"rms={f['rms_mean']:.4f}")
        if result["details"]:
            print(f"           → {result['details']}")
        print()

    except Exception as e:
        print(f"  ⚠️  {fname}: ERROR - {e}\n")

print(f"=== RESULT: {detected}/{total} detected ===")
if detected == total:
    print("🎉 PERFECT — All vomit audio detected!")
elif detected >= total * 0.75:
    print("✅ GOOD — Most detected, may need threshold tuning")
else:
    print("⚠️  NEEDS WORK — Too many misses")
