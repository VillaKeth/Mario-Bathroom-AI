"""Diagnostic: Show exact PANNs scores for distress classes on real vomit audio."""
import sys, os, wave, glob
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'server'))
import numpy as np
from audio_distress import init_detector, _DISTRESS_CLASSES

init_detector(device="cpu")
from audio_distress import _model, _labels

test_dir = os.path.dirname(__file__)
wav_files = sorted(glob.glob(os.path.join(test_dir, '*.wav')))

for f in wav_files:
    name = os.path.basename(f)
    print(f"\n{'='*60}")
    print(f"FILE: {name}")
    print(f"{'='*60}")
    
    try:
        wf = wave.open(f, 'rb')
        sr, ch = wf.getframerate(), wf.getnchannels()
        frames = wf.readframes(wf.getnframes())
        wf.close()
        
        audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
        if ch > 1:
            audio = audio[::ch]
        
        import librosa
        audio = librosa.resample(audio, orig_sr=sr, target_sr=32000)
        audio = audio[:32000 * 10]
        
        out, _ = _model.inference(audio[None, :])
        probs = out[0]
        
        print("\nDISTRESS CLASSES:")
        total_distress = 0
        triggered = 0
        for idx, (cname, thresh) in sorted(_DISTRESS_CLASSES.items()):
            score = float(probs[idx])
            flag = ' <<< TRIGGERED' if score >= thresh else ''
            if score >= thresh:
                total_distress += score
                triggered += 1
            print(f"  [{idx:3d}] {cname:25s}: {score:.4f}  (threshold: {thresh}){flag}")
        
        speech_max = max(float(probs[i]) for i in [0, 1, 2, 3, 4])
        print(f"\n  Combined distress: {total_distress:.4f} (need >= 0.35)")
        print(f"  Classes triggered: {triggered} (need >= 2)")
        print(f"  Speech score: {speech_max:.4f} (suppress if > 0.6)")
        
        print("\nTOP 15 CLASSES:")
        top15 = np.argsort(probs)[-15:][::-1]
        for i in top15:
            print(f"  [{i:3d}] {_labels[i]:35s}: {probs[i]:.4f}")
    except Exception as e:
        print(f"  ERROR: {e}")
