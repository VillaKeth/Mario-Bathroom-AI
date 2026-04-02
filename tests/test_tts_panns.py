"""Convert TTS MP3s to WAV and test against PANNs."""
import sys, os, wave, io, struct
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

OUT_DIR = os.path.dirname(__file__)

# Use pydub or raw approach to convert MP3 to 16kHz mono WAV
def mp3_to_pcm(mp3_path):
    """Convert MP3 to raw 16kHz mono int16 PCM bytes."""
    try:
        from pydub import AudioSegment
        audio = AudioSegment.from_mp3(mp3_path)
        audio = audio.set_frame_rate(16000).set_channels(1).set_sample_width(2)
        return audio.raw_data
    except Exception:
        pass
    
    # Fallback: try librosa
    try:
        import librosa
        import numpy as np
        y, sr = librosa.load(mp3_path, sr=16000, mono=True)
        return (y * 32767).astype(np.int16).tobytes()
    except Exception:
        pass
    
    # Fallback: try soundfile
    try:
        import soundfile as sf
        import numpy as np
        data, sr = sf.read(mp3_path)
        if len(data.shape) > 1:
            data = data.mean(axis=1)
        # Resample if needed
        if sr != 16000:
            import scipy.signal
            data = scipy.signal.resample(data, int(len(data) * 16000 / sr))
        return (data * 32767).astype(np.int16).tobytes()
    except Exception:
        pass
    
    raise RuntimeError("No MP3 decoder available (tried pydub, librosa, soundfile)")

print("Loading PANNs model...")
from audio_distress import init_detector, is_available, detect_distress
init_detector(device="cpu")
print(f"PANNs available: {is_available()}\n")

mp3_files = [f for f in os.listdir(OUT_DIR) if f.startswith("tts_") and f.endswith(".mp3")]
mp3_files.sort()

for mp3_name in mp3_files:
    mp3_path = os.path.join(OUT_DIR, mp3_name)
    print(f"Testing: {mp3_name} ({os.path.getsize(mp3_path)} bytes)")
    
    try:
        raw_pcm = mp3_to_pcm(mp3_path)
        print(f"  Converted: {len(raw_pcm)} bytes ({len(raw_pcm)/2/16000:.1f}s)")
        
        result = detect_distress(raw_pcm, sample_rate=16000)
        status = "✅ DETECTED" if result["is_distress"] else "❌ not detected"
        print(f"  Result: {status} (conf={result['confidence']:.3f})")
        
        if result.get("top_classes"):
            for cls_name, score in result["top_classes"][:8]:
                marker = " <<<"  if score > 0.1 else ""
                print(f"    {cls_name}: {score:.4f}{marker}")
        if result.get("distress_classes"):
            print(f"  Distress classes triggered:")
            for cls_name, score in result["distress_classes"]:
                print(f"    {cls_name}: {score:.4f}")
    except Exception as e:
        print(f"  ERROR: {e}")
    print()
