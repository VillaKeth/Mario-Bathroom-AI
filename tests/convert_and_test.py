"""Convert the downloaded MP3 to WAV using imageio-ffmpeg, then test PANNs."""
import sys, os, subprocess, wave
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

OUT_DIR = os.path.dirname(__file__)

# Find ffmpeg from imageio-ffmpeg
import imageio_ffmpeg
ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
print(f"ffmpeg: {ffmpeg_path}")

# Convert all MP3s in tests/ to WAV
mp3_files = [f for f in os.listdir(OUT_DIR) if f.endswith(".mp3") and os.path.getsize(os.path.join(OUT_DIR, f)) > 1000]
print(f"Found {len(mp3_files)} MP3 files to convert")

from audio_distress import init_detector, is_available, detect_distress
init_detector(device="cpu")
print(f"PANNs available: {is_available()}\n")

for mp3_name in sorted(mp3_files):
    mp3_path = os.path.join(OUT_DIR, mp3_name)
    wav_name = mp3_name.replace(".mp3", ".wav")
    wav_path = os.path.join(OUT_DIR, wav_name)
    
    # Convert to 16kHz mono WAV
    result = subprocess.run(
        [ffmpeg_path, "-y", "-i", mp3_path, "-ar", "16000", "-ac", "1", "-f", "wav", wav_path],
        capture_output=True, text=True
    )
    
    if result.returncode != 0:
        print(f"❌ {mp3_name}: ffmpeg failed - {result.stderr[:200]}")
        continue
    
    # Read raw PCM
    with wave.open(wav_path, "rb") as wf:
        raw = wf.readframes(wf.getnframes())
        sr = wf.getframerate()
        dur = wf.getnframes() / sr
    
    print(f"Testing: {mp3_name} ({dur:.1f}s)")
    
    if is_available():
        res = detect_distress(raw, sample_rate=sr)
        status = "✅ DETECTED" if res["is_distress"] else "❌ not detected"
        print(f"  Result: {status} (conf={res['confidence']:.3f})")
        if res.get("top_classes"):
            for cls_name, score in res["top_classes"][:8]:
                marker = " <<<" if score > 0.1 else ""
                print(f"    {cls_name}: {score:.4f}{marker}")
        if res.get("distress_classes"):
            print(f"  Distress classes:")
            for cls_name, score in res["distress_classes"]:
                print(f"    {cls_name}: {score:.4f}")
    print()
