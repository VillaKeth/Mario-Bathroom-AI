"""Try to download real retching/gagging audio from free sources."""
import requests
import os

OUT_DIR = os.path.join(os.path.dirname(__file__))
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# Free sound effect sources (public domain / CC0)
urls = [
    # Freesound preview URLs (low quality but real)
    ("freesound_vomit1.mp3", "https://freesound.org/data/previews/519/519157_9497060-lq.mp3"),
    ("freesound_cough1.mp3", "https://freesound.org/data/previews/370/370754_6687700-lq.mp3"),
    ("freesound_gag1.mp3", "https://freesound.org/data/previews/456/456965_9497060-lq.mp3"),
    # Pixabay audio (CC0)
    ("pixabay_cough1.mp3", "https://cdn.pixabay.com/download/audio/2021/08/04/audio_0625c1539c.mp3"),
    ("pixabay_cough2.mp3", "https://cdn.pixabay.com/download/audio/2022/03/15/audio_4bf62e4e0e.mp3"),
]

downloaded = []
for filename, url in urls:
    path = os.path.join(OUT_DIR, filename)
    try:
        r = requests.get(url, timeout=15, headers=headers)
        if r.status_code == 200 and len(r.content) > 1000:
            with open(path, "wb") as f:
                f.write(r.content)
            print(f"  ✅ {filename}: {len(r.content)} bytes")
            downloaded.append(filename)
        else:
            print(f"  ❌ {filename}: status={r.status_code}, size={len(r.content)}")
    except Exception as e:
        print(f"  ❌ {filename}: {e}")

if not downloaded:
    print("\nNo audio downloaded. The user will need to provide real retching audio.")
    print("Recommended: Record yourself fake-gagging into a mic, or download from:")
    print("  - freesound.org (search 'vomiting' or 'gagging')")
    print("  - zapsplat.com (search 'retching')")
    print("  - soundsnap.com (search 'throwing up')")
else:
    print(f"\nDownloaded {len(downloaded)} files. Testing against PANNs...")
    
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))
    from audio_distress import init_detector, is_available, detect_distress
    
    init_detector(device="cpu")
    if not is_available():
        print("PANNs not available")
        sys.exit(1)
    
    from pydub import AudioSegment
    
    for filename in downloaded:
        path = os.path.join(OUT_DIR, filename)
        try:
            audio = AudioSegment.from_mp3(path)
            audio = audio.set_frame_rate(16000).set_channels(1).set_sample_width(2)
            raw_pcm = audio.raw_data
            
            result = detect_distress(raw_pcm, sample_rate=16000)
            status = "✅ DETECTED" if result["is_distress"] else "❌ not detected"
            print(f"\n{filename}: {status} (conf={result['confidence']:.3f})")
            if result.get("top_classes"):
                for cls_name, score in result["top_classes"][:8]:
                    print(f"    {cls_name}: {score:.4f}")
            if result.get("distress_classes"):
                for cls_name, score in result["distress_classes"]:
                    print(f"    [DISTRESS] {cls_name}: {score:.4f}")
        except Exception as e:
            print(f"\n{filename}: ERROR - {e}")
