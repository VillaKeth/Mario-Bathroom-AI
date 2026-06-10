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
