"""Create a curated Mario reference audio optimized for XTTS v2 voice cloning.

Selects the most iconic Charles Martinet Mario clips, trims silence,
normalizes volume, and optionally pitch-shifts for a more cartoony sound.
"""
import os
import wave
import numpy as np
import soundfile as sf

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

# Best clips for Mario voice character (clear, enthusiastic, iconic)
CURATED_CLIPS = [
    "mario_clip_2.wav",   # "Hello everybody, it's a me, Mario!" — THE classic
    "mario_clip_xd.wav",  # Long enthusiastic speech — lots of energy and character
    "mario_clip_56.wav",  # Longer clear sentence — good variety
]

def trim_silence(audio, sr, threshold_db=-35):
    """Trim leading/trailing silence."""
    threshold = 10 ** (threshold_db / 20.0)
    abs_audio = np.abs(audio)
    mask = abs_audio > threshold
    if not np.any(mask):
        return audio
    start = np.argmax(mask)
    end = len(mask) - np.argmax(mask[::-1])
    pad = int(sr * 0.05)  # 50ms padding
    start = max(0, start - pad)
    end = min(len(audio), end + pad)
    return audio[start:end]


def normalize(audio, target_db=-3):
    """Normalize audio to target dB level."""
    peak = np.max(np.abs(audio))
    if peak < 1e-6:
        return audio
    target_peak = 10 ** (target_db / 20.0)
    return audio * (target_peak / peak)


def main():
    clips = []
    total_duration = 0

    for clip_name in CURATED_CLIPS:
        path = os.path.join(DATA_DIR, clip_name)
        if not os.path.exists(path):
            print(f"  MISSING: {clip_name}")
            continue

        audio, sr = sf.read(path, dtype="float32")
        if audio.ndim > 1:
            audio = audio[:, 0]

        audio = trim_silence(audio, sr)
        audio = normalize(audio)

        duration = len(audio) / sr
        total_duration += duration
        clips.append((audio, sr))
        print(f"  {clip_name}: {duration:.1f}s (trimmed, normalized)")

    if not clips:
        print("ERROR: No clips found!")
        return

    # All clips should be same sample rate (22050)
    target_sr = clips[0][1]
    all_audio = np.concatenate([c[0] for c in clips])

    # Save curated reference
    out_path = os.path.join(DATA_DIR, "mario_reference_curated.wav")
    sf.write(out_path, all_audio, target_sr)
    size = os.path.getsize(out_path)
    print(f"\nCurated reference: {out_path}")
    print(f"  Duration: {total_duration:.1f}s")
    print(f"  Sample rate: {target_sr} Hz")
    print(f"  Size: {size} bytes")


if __name__ == "__main__":
    main()
