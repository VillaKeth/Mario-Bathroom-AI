"""Test PANNs distress detection with real freesound.org vomit audio."""
import sys, os, glob
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'server'))
import numpy as np
from audio_distress import init_detector, detect_distress

def load_audio(filepath, target_sr=16000, max_seconds=10):
    """Load audio file and return float32 array at target sample rate."""
    if filepath.endswith('.mp3'):
        import subprocess, tempfile
        import imageio_ffmpeg
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        wav_path = filepath.replace('.mp3', '_tmp.wav')
        subprocess.run([ffmpeg, '-y', '-i', filepath, '-ar', str(target_sr), 
                       '-ac', '1', '-f', 'wav', wav_path],
                      capture_output=True, check=True)
        filepath = wav_path
        cleanup = True
    else:
        cleanup = False
    
    import wave
    with wave.open(filepath, 'rb') as wf:
        sr = wf.getframerate()
        ch = wf.getnchannels()
        frames = wf.readframes(wf.getnframes())
    
    if cleanup:
        os.remove(filepath)
    
    audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
    if ch > 1:
        audio = audio[::ch]
    
    if sr != target_sr:
        from scipy.signal import resample
        audio = resample(audio, int(len(audio) * target_sr / sr))
    
    max_samples = target_sr * max_seconds
    if len(audio) > max_samples:
        audio = audio[:max_samples]
    
    # Convert back to int16 bytes (detect_distress expects int16 PCM)
    audio_int16 = (audio * 32768.0).clip(-32768, 32767).astype(np.int16)
    return audio_int16

def main():
    print("Initializing PANNs detector...")
    init_detector(device="cpu")
    print("PANNs ready!\n")
    
    test_dir = os.path.dirname(__file__)
    audio_files = sorted(
        glob.glob(os.path.join(test_dir, '*.wav')) + 
        glob.glob(os.path.join(test_dir, '*.mp3'))
    )
    # Filter out any test script artifacts
    audio_files = [f for f in audio_files if not f.endswith('_tmp.wav')]
    
    print(f"Found {len(audio_files)} audio files\n")
    
    results = []
    for f in audio_files:
        name = os.path.basename(f)
        print(f"=== {name} ===")
        try:
            audio = load_audio(f)
            result = detect_distress(audio.tobytes(), sample_rate=16000)
            
            detected = result["is_distress"]
            combined = result["confidence"]
            speech = result.get("speech_score", 0)
            
            status = "✅ DETECTED" if detected else "❌ NOT detected"
            print(f"  Distress: {status}")
            print(f"  Combined score: {combined:.3f} (threshold: 0.35)")
            print(f"  Speech score:   {speech:.3f} (suppress if > 0.6)")
            
            if result.get("distress_classes"):
                print(f"  Triggered classes:")
                for cls, score in result["distress_classes"]:
                    print(f"    {cls}: {score:.3f}")
            
            print(f"  Top PANNs classes:")
            for cls, score in result.get("top_classes", []):
                marker = ' ***' if score > 0.1 else ''
                print(f"    {cls}: {score:.3f}{marker}")
            
            results.append((name, detected, combined, speech))
            print()
        except Exception as e:
            print(f"  ERROR: {e}\n")
            results.append((name, None, 0, 0))
    
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    detected_count = sum(1 for _, d, _, _ in results if d)
    total = len(results)
    print(f"Detected: {detected_count}/{total}")
    for name, detected, combined, speech in results:
        status = "PASS" if detected else "FAIL"
        print(f"  [{status}] {name}: combined={combined:.3f}, speech={speech:.3f}")

if __name__ == "__main__":
    main()
