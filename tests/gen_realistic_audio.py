"""
Generate realistic retching/gagging audio using multiple approaches:
1. TTS-generated vomit sounds (onomatopoeia)  
2. Layered audio with real-sounding frequency patterns
3. Test each against PANNs to find what triggers it
"""
import sys, os, wave, struct, time
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

OUT_DIR = os.path.dirname(__file__)

def save_wav(filename, audio_int16, sr=16000):
    path = os.path.join(OUT_DIR, filename)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(audio_int16.tobytes())
    return path

def generate_cough_pattern(sr=16000, duration=5.0):
    """Generate cough-like audio — sharp bursts with resonance."""
    t = np.linspace(0, duration, int(sr * duration))
    audio = np.zeros_like(t)
    
    # Cough bursts at irregular intervals
    cough_times = [0.3, 0.7, 1.5, 2.2, 2.5, 3.3, 4.0, 4.5]
    for ct in cough_times:
        # Sharp attack, exponential decay
        mask = (t >= ct) & (t < ct + 0.25)
        if mask.sum() == 0:
            continue
        local_t = t[mask] - ct
        # Vocal cord vibration (100-300Hz)
        vocal = np.sin(2 * np.pi * 200 * local_t) * np.exp(-15 * local_t)
        # Noise burst (throat)
        noise = np.random.randn(mask.sum()) * np.exp(-8 * local_t) * 0.5
        # Resonance (chest cavity ~500Hz)
        resonance = np.sin(2 * np.pi * 500 * local_t) * np.exp(-20 * local_t) * 0.3
        audio[mask] = vocal + noise + resonance
    
    audio = audio / max(np.max(np.abs(audio)), 0.001) * 0.8
    return (audio * 32767).astype(np.int16)

def generate_groan_wheeze(sr=16000, duration=5.0):
    """Generate groaning/wheezing — sustained low tones with modulation."""
    t = np.linspace(0, duration, int(sr * duration))
    
    # Groan: low fundamental with harmonics, slow amplitude modulation
    f0 = 120  # Low male groan
    groan = (np.sin(2 * np.pi * f0 * t) * 0.5 + 
             np.sin(2 * np.pi * f0 * 2 * t) * 0.3 +
             np.sin(2 * np.pi * f0 * 3 * t) * 0.1)
    # Amplitude envelope: slow rise, sustain, slow fall
    env = np.clip(t / 0.5, 0, 1) * np.clip((duration - t) / 0.5, 0, 1)
    # Vibrato
    vibrato = 1 + 0.1 * np.sin(2 * np.pi * 6 * t)
    groan = groan * env * vibrato
    
    # Wheeze: high-pitched narrow-band noise
    wheeze_freq = 800
    wheeze = np.sin(2 * np.pi * wheeze_freq * t + np.random.randn(len(t)) * 0.5) * 0.15
    wheeze *= env
    
    audio = groan + wheeze
    audio = audio / max(np.max(np.abs(audio)), 0.001) * 0.8
    return (audio * 32767).astype(np.int16)

def generate_gasp_pant(sr=16000, duration=5.0):
    """Generate gasping/panting — rhythmic breath-like bursts."""
    t = np.linspace(0, duration, int(sr * duration))
    audio = np.zeros_like(t)
    
    # Rapid breaths
    breath_rate = 2.5  # breaths per second (panicked)
    for i in range(int(duration * breath_rate)):
        bt = i / breath_rate
        # Inhale: filtered noise rising pitch
        inhale_mask = (t >= bt) & (t < bt + 0.15)
        if inhale_mask.sum() > 0:
            lt = t[inhale_mask] - bt
            noise = np.random.randn(inhale_mask.sum())
            # Simple low-pass via averaging
            env = np.sin(np.pi * lt / 0.15)
            audio[inhale_mask] += noise * env * 0.4
        
        # Exhale: lower, longer
        exhale_mask = (t >= bt + 0.15) & (t < bt + 0.35)
        if exhale_mask.sum() > 0:
            lt = t[exhale_mask] - (bt + 0.15)
            noise = np.random.randn(exhale_mask.sum())
            env = np.sin(np.pi * lt / 0.2) * 0.8
            # Add slight vocal quality
            vocal = np.sin(2 * np.pi * 150 * lt) * 0.2
            audio[exhale_mask] += (noise * 0.3 + vocal) * env
    
    audio = audio / max(np.max(np.abs(audio)), 0.001) * 0.7
    return (audio * 32767).astype(np.int16)

def generate_retch_realistic(sr=16000, duration=5.0):
    """Most realistic retching attempt — combines multiple patterns."""
    t = np.linspace(0, duration, int(sr * duration))
    audio = np.zeros_like(t)
    
    # Phase 1 (0-1.5s): Heavy breathing / gagging buildup
    mask1 = t < 1.5
    if mask1.sum() > 0:
        lt = t[mask1]
        audio[mask1] = (np.sin(2 * np.pi * 100 * lt) * 0.3 * 
                        (1 + 0.5 * np.sin(2 * np.pi * 4 * lt)))
    
    # Phase 2 (1.5-3s): Retching (irregular bursts + low groan)
    retch_times = [1.5, 1.9, 2.4, 2.7]
    for rt in retch_times:
        mask = (t >= rt) & (t < rt + 0.4)
        if mask.sum() > 0:
            lt = t[mask] - rt
            # Guttural sound
            guttural = np.sin(2 * np.pi * 80 * lt + 5 * np.sin(2 * np.pi * 12 * lt))
            # Strained vocal
            strain = np.sin(2 * np.pi * 250 * lt) * np.exp(-5 * lt) * 0.5
            # Noise component
            noise = np.random.randn(mask.sum()) * np.exp(-3 * lt) * 0.4
            audio[mask] = (guttural * 0.6 + strain + noise) * np.exp(-2 * lt)
    
    # Phase 3 (3-5s): Aftermath groaning + heavy breathing
    mask3 = t >= 3.0
    if mask3.sum() > 0:
        lt = t[mask3] - 3.0
        groan = np.sin(2 * np.pi * 130 * lt) * 0.3 * np.exp(-0.5 * lt)
        breath_noise = np.random.randn(mask3.sum()) * 0.15 * (1 + np.sin(2 * np.pi * 1.5 * lt))
        audio[mask3] = groan + breath_noise
    
    audio = audio / max(np.max(np.abs(audio)), 0.001) * 0.8
    return (audio * 32767).astype(np.int16)

# Generate all variants
print("Generating audio variants for PANNs testing...")
variants = {
    "test_cough.wav": generate_cough_pattern(),
    "test_groan.wav": generate_groan_wheeze(),
    "test_gasp.wav": generate_gasp_pant(),
    "test_retch_v2.wav": generate_retch_realistic(),
}

for name, audio in variants.items():
    path = save_wav(name, audio)
    print(f"  {name}: {os.path.getsize(path)} bytes")

# Now test all against PANNs
print("\nLoading PANNs model...")
from audio_distress import init_detector, is_available, detect_distress
init_detector(device="cpu")
print(f"PANNs available: {is_available()}\n")

if is_available():
    for name in variants:
        path = os.path.join(OUT_DIR, name)
        with wave.open(path, "rb") as wf:
            raw = wf.readframes(wf.getnframes())
        
        result = detect_distress(raw, sample_rate=16000)
        status = "✅ DETECTED" if result["is_distress"] else "❌ not detected"
        print(f"{name}: {status} (conf={result['confidence']:.3f})")
        if result.get("top_classes"):
            for cls_name, score in result["top_classes"][:5]:
                marker = " <<<" if score > 0.1 else ""
                print(f"    {cls_name}: {score:.4f}{marker}")
        if result.get("distress_classes"):
            print(f"  Triggered distress classes:")
            for cls_name, score in result["distress_classes"]:
                print(f"    {cls_name}: {score:.4f}")
        print()
