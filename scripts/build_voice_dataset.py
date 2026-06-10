"""Build a GPT-SoVITS fine-tuning dataset from raw character audio.

Slices long clips on silence into 3-10s segments, transcribes each locally with
faster-whisper, and writes the GPT-SoVITS .list manifest:
    <wav_path>|<speaker>|<lang>|<text>

Usage:
    venv/Scripts/python.exe scripts/build_voice_dataset.py jax

Reads:  characters/<char>/voice/dataset/raw/*.wav
Writes: characters/<char>/voice/dataset/segments/*.wav
        characters/<char>/voice/dataset/<char>.list
"""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "gpt_sovits_repo"))
sys.path.insert(0, os.path.join(BASE, "gpt_sovits_repo", "tools"))

import numpy as np
import soundfile as sf


def _load_audio_32k_mono(in_wav):
    """Decode any audio to mono float32 @ 32k via ffmpeg (avoids repo's gradio dep)."""
    import subprocess
    out = subprocess.run(
        ["ffmpeg", "-i", in_wav, "-ac", "1", "-ar", "32000", "-f", "f32le", "-"],
        capture_output=True)
    return np.frombuffer(out.stdout, dtype=np.float32).copy()


def slice_audio(in_wav, out_dir, speaker):
    """Silence-slice a wav into 3-10s segments using the repo's Slicer."""
    from slicer2 import Slicer
    os.makedirs(out_dir, exist_ok=True)
    audio = _load_audio_32k_mono(in_wav)  # mono float32 @ 32k
    slicer = Slicer(sr=32000, threshold=-34, min_length=4000, min_interval=300,
                    hop_size=10, max_sil_kept=500)
    seg_paths = []
    base = os.path.splitext(os.path.basename(in_wav))[0]
    idx = 0
    for chunk, start, end in slicer.slice(audio):
        m = np.abs(chunk).max()
        if m > 1:
            chunk /= m
        chunk = (chunk * 0.9 * 32767).astype(np.int16)
        dur = len(chunk) / 32000.0
        if dur < 2.0:   # too short to be useful
            continue
        # Hard-cap very long chunks at 10s (GPT-SoVITS zero-shot ref limit; also
        # keeps training segments tidy)
        max_len = int(10 * 32000)
        for off in range(0, len(chunk), max_len):
            piece = chunk[off:off + max_len]
            if len(piece) / 32000.0 < 2.0:
                continue
            p = os.path.join(out_dir, f"{base}_{idx:04d}.wav")
            sf.write(p, piece, 32000)
            seg_paths.append(p)
            idx += 1
    return seg_paths


def _median_f0(wav_path: str) -> tuple[float, float]:
    """Return (median F0 in Hz, voiced fraction) of a wav via parselmouth/Praat."""
    import parselmouth
    import numpy as np
    snd = parselmouth.Sound(wav_path)
    pitch = snd.to_pitch(time_step=0.02, pitch_floor=70, pitch_ceiling=450)
    f0 = pitch.selected_array["frequency"]
    voiced = f0[f0 > 0]
    if len(voiced) == 0:
        return 0.0, 0.0
    return float(np.median(voiced)), float(len(voiced) / len(f0))


def filter_by_pitch(seg_paths: list[str], f0_min: float, f0_max: float,
                    min_voiced: float = 0.25) -> list[str]:
    """Keep only segments whose median F0 falls in [f0_min, f0_max].

    Used to isolate a single speaker when sources mix voices of different sex
    (e.g. Reze [female] vs Denji/Beam [male]): female anime dub F0 typically
    sits 170-330 Hz, male 80-150 Hz. Low voiced-fraction segments (music/SFX/
    explosions) are dropped too.
    """
    kept = []
    for p in seg_paths:
        f0, vf = _median_f0(p)
        ok = f0_min <= f0 <= f0_max and vf >= min_voiced
        print(f"[dataset]   {os.path.basename(p)}: F0={f0:.0f}Hz voiced={vf:.0%} "
              f"{'KEEP' if ok else 'drop'}", flush=True)
        if ok:
            kept.append(p)
        else:
            os.remove(p)
    return kept


def main():
    char = sys.argv[1] if len(sys.argv) > 1 else "jax"
    ds = os.path.join(BASE, "characters", char, "voice", "dataset")
    raw_dir = os.path.join(ds, "raw")
    seg_dir = os.path.join(ds, "segments")
    list_path = os.path.join(ds, f"{char}.list")

    raws = [os.path.join(raw_dir, f) for f in sorted(os.listdir(raw_dir))
            if f.lower().endswith((".wav", ".mp3", ".flac", ".m4a", ".webm"))]
    print(f"[dataset] {char}: {len(raws)} raw file(s)", flush=True)

    all_segs = []
    for r in raws:
        segs = slice_audio(r, seg_dir, char)
        print(f"[dataset] sliced {os.path.basename(r)} -> {len(segs)} segments", flush=True)
        all_segs += segs

    # Optional single-speaker isolation: --f0 MIN MAX (Hz). E.g. female anime
    # dub voice vs male co-stars: --f0 170 330
    if "--f0" in sys.argv:
        i = sys.argv.index("--f0")
        f0_min, f0_max = float(sys.argv[i + 1]), float(sys.argv[i + 2])
        print(f"[dataset] pitch filter: keep {f0_min}-{f0_max} Hz", flush=True)
        all_segs = filter_by_pitch(all_segs, f0_min, f0_max)
        print(f"[dataset] {len(all_segs)} segments after pitch filter", flush=True)

    # Transcribe each segment locally
    from character_creator.voice_transcribe import transcribe_file
    lines = []
    total_dur = 0.0
    for i, p in enumerate(all_segs):
        try:
            import wave
            w = wave.open(p); total_dur += w.getnframes() / w.getframerate(); w.close()
        except Exception:
            pass
        tr = transcribe_file(p, model_size="base")
        text = (tr.get("text") or "").strip()
        if not text:
            continue
        lines.append(f"{os.path.abspath(p)}|{char}|en|{text}")
        if (i + 1) % 10 == 0:
            print(f"[dataset] transcribed {i+1}/{len(all_segs)}", flush=True)

    with open(list_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"[dataset] DONE: {len(lines)} usable segments, "
          f"{total_dur:.0f}s total audio -> {list_path}", flush=True)


if __name__ == "__main__":
    main()
