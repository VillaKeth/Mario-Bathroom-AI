"""
Use Edge TTS to generate human-like gagging/retching vocalizations.
PANNs is trained on real AudioSet audio, so synthetic sine waves won't work.
TTS-generated vocalizations should be closer to real human sounds.
"""
import sys, os, asyncio, wave
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

OUT_DIR = os.path.dirname(__file__)

async def generate_tts_gagging():
    import edge_tts
    
    # Various onomatopoeia that TTS will vocalize
    phrases = [
        ("tts_retch1.mp3", "Bleeeargh! Huuurgh! *cough cough* Blaaaargh!"),
        ("tts_retch2.mp3", "Uuuugh... Huuuurgh... Bleargh! Oh god... Huuurgh!"),
        ("tts_retch3.mp3", "Ugh ugh ugh... BLEARGH! *gasp* *cough cough cough* Huuurgh!"),
        ("tts_groan1.mp3", "Uuuuuuugh... Ohhhhh... Uuuuuugh... Mmmmnngh..."),
        ("tts_cough1.mp3", "Ahem! Hck! Hck! *cough* *cough* Hcccck! Hck!"),
    ]
    
    voice = "en-US-GuyNeural"  # Male voice, more natural
    
    for filename, text in phrases:
        path = os.path.join(OUT_DIR, filename)
        communicate = edge_tts.Communicate(text, voice, rate="-20%")
        await communicate.save(path)
        size = os.path.getsize(path)
        print(f"Generated: {filename} ({size} bytes) - \"{text[:50]}...\"")
    
    return [p[0] for p in phrases]

# Generate the TTS audio
print("Generating TTS-vocalized gagging audio...")
filenames = asyncio.run(generate_tts_gagging())

# Convert MP3 to WAV PCM for PANNs testing
print("\nConverting to WAV and testing with PANNs...")

try:
    import subprocess
    import numpy as np
    
    from audio_distress import init_detector, is_available, detect_distress
    init_detector(device="cpu")
    print(f"PANNs available: {is_available()}\n")
    
    if not is_available():
        print("PANNs not available, skipping detection tests")
        sys.exit(1)
    
    for mp3_name in filenames:
        mp3_path = os.path.join(OUT_DIR, mp3_name)
        wav_name = mp3_name.replace(".mp3", ".wav")
        wav_path = os.path.join(OUT_DIR, wav_name)
        
        # Convert MP3 to 16kHz mono WAV using ffmpeg
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", mp3_path, "-ar", "16000", "-ac", "1", "-f", "wav", wav_path],
            capture_output=True, text=True
        )
        
        if result.returncode != 0:
            # Try with python's pydub if ffmpeg not available
            try:
                from pydub import AudioSegment
                audio = AudioSegment.from_mp3(mp3_path)
                audio = audio.set_frame_rate(16000).set_channels(1).set_sample_width(2)
                audio.export(wav_path, format="wav")
            except Exception as e:
                print(f"  {mp3_name}: Cannot convert - {e}")
                continue
        
        # Read raw PCM from WAV
        with wave.open(wav_path, "rb") as wf:
            raw = wf.readframes(wf.getnframes())
            sr = wf.getframerate()
        
        # Test with PANNs
        result = detect_distress(raw, sample_rate=sr)
        status = "✅ DETECTED" if result["is_distress"] else "❌ not detected"
        print(f"{wav_name}: {status} (conf={result['confidence']:.3f})")
        
        if result.get("top_classes"):
            for cls_name, score in result["top_classes"][:8]:
                marker = " <<<"  if score > 0.1 else ""
                print(f"    {cls_name}: {score:.4f}{marker}")
        if result.get("distress_classes"):
            print(f"  Distress classes:")
            for cls_name, score in result["distress_classes"]:
                print(f"    {cls_name}: {score:.4f}")
        print()

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
