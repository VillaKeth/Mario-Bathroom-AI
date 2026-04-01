"""Generate Nintendo-style sound effect WAV files for assets/sfx/.

Creates 6 WAV files matching DEFAULT_EVENT_MAP in server/sound_events.py:
  coin.wav    - Two-note coin collect (greeting event)
  powerup.wav - Ascending power-up (game_start event)
  fireball.wav - Quick descending fireball (roast event)
  pipe.wav    - Descending pipe warp (vomit event)
  star.wav    - Star jingle (farewell event)
  1up.wav     - 1-UP ascending arpeggio (birthday event)

All files: 16-bit mono WAV, 44100 Hz, <2 seconds.
"""
import numpy as np
import wave
import os

SAMPLE_RATE = 44100
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "sfx")


def generate_tone(freq, duration, wave_type="square", volume=0.3):
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False)
    if wave_type == "square":
        signal = volume * np.sign(np.sin(2 * np.pi * freq * t))
    elif wave_type == "sine":
        signal = volume * np.sin(2 * np.pi * freq * t)
    elif wave_type == "triangle":
        signal = volume * (2 * np.abs(2 * (t * freq - np.floor(t * freq + 0.5))) - 1)
    else:
        signal = volume * np.sin(2 * np.pi * freq * t)
    return signal


def apply_envelope(signal, attack=0.01, decay=0.05):
    n = len(signal)
    env = np.ones(n)
    attack_samples = min(int(attack * SAMPLE_RATE), n)
    decay_samples = min(int(decay * SAMPLE_RATE), n)
    if attack_samples > 0:
        env[:attack_samples] = np.linspace(0, 1, attack_samples)
    if decay_samples > 0:
        env[-decay_samples:] = np.linspace(1, 0, decay_samples)
    return signal * env


def save_wav(filename, signal):
    filepath = os.path.join(OUTPUT_DIR, filename)
    signal = np.clip(signal, -1.0, 1.0)
    data = (signal * 32767).astype(np.int16)
    with wave.open(filepath, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(data.tobytes())
    print(f"  Created: {filename} ({len(data) / SAMPLE_RATE:.2f}s, {os.path.getsize(filepath)} bytes)")


def generate_coin():
    """Two-note coin sound (B5 -> E6)."""
    note1 = apply_envelope(generate_tone(988, 0.08, "square", 0.25), decay=0.02)
    gap = np.zeros(int(SAMPLE_RATE * 0.02))
    note2 = apply_envelope(generate_tone(1319, 0.15, "square", 0.25), decay=0.08)
    return np.concatenate([note1, gap, note2])


def generate_powerup():
    """Ascending power-up glide (10 notes)."""
    segments = []
    for f in [262, 330, 392, 523, 659, 784, 1047, 1319, 1568, 2093]:
        seg = apply_envelope(generate_tone(f, 0.06, "square", 0.2), decay=0.02)
        segments.append(seg)
    return np.concatenate(segments)


def generate_fireball():
    """Fast descending fireball sweep."""
    t = np.linspace(0, 0.3, int(SAMPLE_RATE * 0.3), endpoint=False)
    freq = 800 * np.exp(-5 * t)
    phase = np.cumsum(2 * np.pi * freq / SAMPLE_RATE)
    signal = 0.25 * np.sin(phase)
    return apply_envelope(signal, decay=0.1)


def generate_pipe():
    """Descending pipe warp sound (5 steps)."""
    segments = []
    for f in [600, 500, 400, 300, 200]:
        seg = apply_envelope(generate_tone(f, 0.1, "square", 0.2), decay=0.03)
        segments.append(seg)
    return np.concatenate(segments)


def generate_star():
    """Star/invincibility jingle (10 notes)."""
    segments = []
    for f in [784, 988, 1175, 1319, 1175, 988, 784, 988, 1175, 1319]:
        seg = apply_envelope(generate_tone(f, 0.08, "square", 0.2), decay=0.02)
        segments.append(seg)
    return np.concatenate(segments)


def generate_1up():
    """1-UP ascending arpeggio (E4->G4->C5->E5->G5->C6)."""
    segments = []
    for f in [330, 392, 523, 659, 784, 1047]:
        seg = apply_envelope(generate_tone(f, 0.1, "sine", 0.3), decay=0.04)
        segments.append(seg)
    return np.concatenate(segments)


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"Generating Mario SFX WAV files in {OUTPUT_DIR}...")
    save_wav("coin.wav", generate_coin())
    save_wav("powerup.wav", generate_powerup())
    save_wav("fireball.wav", generate_fireball())
    save_wav("pipe.wav", generate_pipe())
    save_wav("star.wav", generate_star())
    save_wav("1up.wav", generate_1up())
    print(f"\nDone! 6 files created.")


if __name__ == "__main__":
    main()
