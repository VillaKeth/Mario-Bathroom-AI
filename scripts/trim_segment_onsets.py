"""Trim the lead-in before speech starts in each dataset segment.

Menu/UI voice-line rips often have leading dead air and/or a short non-speech
transient (a "water droplet" / select SFX) before the line. That junk teaches a
fine-tune to emit a click/pause before every utterance. This finds the real
speech onset by energy (first point with SUSTAINED energy, so a brief click is
skipped, not latched onto) and trims everything before it, in place.

Run (after build_voice_dataset.py, before fine_tune_voice.py):
    venv/Scripts/python.exe scripts/trim_segment_onsets.py march7th [--pad 0.05] [--thresh 0.02]

Operates on every wav referenced by characters/<char>/voice/dataset/<char>.list.
"""
import os
import sys

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import soundfile as sf


def speech_onset(audio: np.ndarray, sr: int, thresh: float, sustain_s: float = 0.08) -> float | None:
    """First time (s) where RMS stays above `thresh` for `sustain_s` — i.e. real
    speech, not a one-off transient (droplet/click)."""
    frame = max(1, int(0.02 * sr))
    need = max(1, int(sustain_s / 0.02))  # consecutive frames required
    run = 0
    n_frames = (len(audio) - frame) // frame
    peak = float(np.sqrt(np.mean(audio ** 2))) or 1.0
    t = thresh * max(1.0, peak / 0.1)  # scale a little with overall loudness
    for i in range(n_frames):
        seg = audio[i * frame:(i + 1) * frame]
        rms = float(np.sqrt(np.mean(seg ** 2)))
        if rms > thresh:
            run += 1
            if run >= need:
                onset_frame = i - need + 1
                return max(0.0, onset_frame * 0.02)
        else:
            run = 0
    return None


def trim_wav(wav_path: str, start: float):
    audio, sr = sf.read(wav_path)
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    cut = int(start * sr)
    sf.write(wav_path, audio[cut:].astype(np.float32), sr)


def main():
    char = sys.argv[1] if len(sys.argv) > 1 else "jax"
    pad = float(sys.argv[sys.argv.index("--pad") + 1]) if "--pad" in sys.argv else 0.05
    thresh = float(sys.argv[sys.argv.index("--thresh") + 1]) if "--thresh" in sys.argv else 0.02

    list_path = os.path.join(BASE, "characters", char, "voice", "dataset", f"{char}.list")
    if not os.path.exists(list_path):
        raise SystemExit(f"[trim] dataset list missing: {list_path}")

    wavs = [ln.strip().split("|", 1)[0] for ln in open(list_path, encoding="utf-8") if ln.strip()]
    print(f"[trim] {char}: {len(wavs)} segments, thresh={thresh} pad={pad}s", flush=True)

    trimmed = 0
    for p in wavs:
        if not os.path.exists(p):
            continue
        audio, sr = sf.read(p)
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        audio = audio.astype(np.float64)
        onset = speech_onset(audio, sr, thresh)
        if onset is None:
            print(f"[trim]   {os.path.basename(p)}: no sustained speech — skip", flush=True)
            continue
        cut = max(0.0, onset - pad)
        if cut < 0.05:
            print(f"[trim]   {os.path.basename(p)}: onset {onset:.2f}s — keep", flush=True)
            continue
        try:
            trim_wav(p, cut)
            trimmed += 1
            print(f"[trim]   {os.path.basename(p)}: cut {cut:.2f}s lead-in", flush=True)
        except Exception as e:
            print(f"[trim]   {os.path.basename(p)}: failed ({e})", flush=True)

    print(f"[trim] DONE: trimmed {trimmed}/{len(wavs)} segments", flush=True)


if __name__ == "__main__":
    main()
