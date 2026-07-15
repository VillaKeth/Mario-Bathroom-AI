"""Offline: turn a source recording into a character-voice singing cover.

Pipeline:  source -> demucs (isolate vocals) -> rvc_python (character timbre)
           -> peak-normalize -3dB -> characters/<char>/songs/<id>.wav

Melody is preserved (f0_up_key defaults to 0); the speech path's +12 semitone
shift would wreck a sung melody. Re-run with different --f0-up-key / --index-rate
/ --protect until it sings right. Rendered wav is LOCAL ONLY (copyright).

Example (run from repo root, RVC env has torch + rvc_python + demucs):
  gpt_sovits_env\\Scripts\\python scripts/make_song_cover.py \\
      --in "My Way.mp3" --char mario --id my_way --title "My Way"
"""
import os
import sys
import argparse
import subprocess

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "server"))


def demucs_stem_path(outdir: str, input_path: str) -> str:
    """Where demucs (default htdemucs model) writes the isolated vocal stem."""
    track = os.path.splitext(os.path.basename(input_path))[0]
    return os.path.join(outdir, "htdemucs", track, "vocals.wav")


def rvc_params(f0_up_key, index_rate, protect) -> dict:
    """RVC params tuned for SINGING (melody-preserving), unlike the speech path."""
    return {
        "f0method": "rmvpe",
        "f0up_key": int(f0_up_key),
        "index_rate": float(index_rate),
        "protect": float(protect),
    }


def isolate_vocals(input_path: str, outdir: str, python_exe: str = sys.executable) -> str:
    os.makedirs(outdir, exist_ok=True)
    subprocess.run(
        [python_exe, "-m", "demucs", "--two-stems=vocals", "-o", outdir, input_path],
        check=True,
    )
    stem = demucs_stem_path(outdir, input_path)
    if not os.path.isfile(stem):
        raise FileNotFoundError(f"demucs did not produce {stem}")
    return stem


def convert_to_character(vocals_path: str, out_wav: str, params: dict) -> str:
    from rvc_python.infer import RVCInference
    import tts
    rvc = RVCInference()
    rvc.load_model(tts.RVC_MODEL_PATH)
    rvc.set_params(**params)
    tmp = out_wav + ".raw.wav"
    rvc.infer_file(vocals_path, tmp)
    with open(tmp, "rb") as f:
        raw = f.read()
    normalized = tts._normalize_audio(raw)
    with open(out_wav, "wb") as f:
        f.write(normalized)
    try:
        os.remove(tmp)
    except OSError:
        pass
    return out_wav


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True, help="source audio (mp3/wav)")
    ap.add_argument("--char", default="mario")
    ap.add_argument("--id", dest="song_id", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--f0-up-key", type=int, default=0)
    ap.add_argument("--index-rate", type=float, default=0.6)
    ap.add_argument("--protect", type=float, default=0.25)
    ap.add_argument("--workdir", default=os.path.join(_ROOT, "scripts", "_song_work"))
    args = ap.parse_args(argv)

    songs_dir = os.path.join(_ROOT, "characters", args.char, "songs")
    os.makedirs(songs_dir, exist_ok=True)
    out_wav = os.path.join(songs_dir, f"{args.song_id}.wav")

    print(f"[1/3] isolating vocals from {args.inp}")
    vocals = isolate_vocals(args.inp, args.workdir)
    params = rvc_params(args.f0_up_key, args.index_rate, args.protect)
    print(f"[2/3] RVC -> {args.char} timbre  params={params}")
    convert_to_character(vocals, out_wav, params)
    print(f"[3/3] wrote {out_wav}")
    print(f"Now create characters/{args.char}/songs/{args.song_id}.json (see the design spec).")


if __name__ == "__main__":
    main()
