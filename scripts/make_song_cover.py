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


def _fallback_normalize(wav_bytes: bytes) -> bytes:
    """Peak-normalize to -3dB without server deps (numpy+soundfile only)."""
    import io
    import numpy as np
    import soundfile as sf
    data, rate = sf.read(io.BytesIO(wav_bytes))
    peak = float(abs(data).max() or 1.0)
    data = data * (10 ** (-3.0 / 20.0) / peak)
    buf = io.BytesIO()
    sf.write(buf, data, rate, format="WAV", subtype="PCM_16")
    return buf.getvalue()


def _load_voice_backend():
    """Prefer the server's tts module (exact party settings); fall back to
    local constants when its deps (edge_tts etc.) aren't in this env."""
    try:
        import tts
        return tts.RVC_MODEL_PATH, tts._normalize_audio
    except Exception as e:
        print(f"[note] server tts module unavailable here ({e}); using fallback paths")
        model = os.path.join(_ROOT, "mario_models_new", "MarioSwitch",
                             "SuperMario-NintendoSwitchEra.pth")
        return model, _fallback_normalize


def convert_to_character(vocals_path: str, out_wav: str, params: dict,
                         model_path: str = None) -> str:
    from rvc_python.infer import RVCInference
    default_model, normalize = _load_voice_backend()
    model_path = model_path or default_model
    print(f"[model] {model_path}")
    rvc = RVCInference()
    rvc.load_model(model_path)
    rvc.set_params(**params)
    tmp = out_wav + ".raw.wav"
    rvc.infer_file(vocals_path, tmp)
    with open(tmp, "rb") as f:
        raw = f.read()
    normalized = normalize(raw)
    with open(out_wav, "wb") as f:
        f.write(normalized)
    try:
        os.remove(tmp)
    except OSError:
        pass
    return out_wav


def build_argparser():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default=None, help="source audio (mp3/wav) — vocals get isolated with demucs")
    ap.add_argument("--vocals-in", dest="vocals_in", default=None,
                    help="already-isolated vocal wav (acapella) — skips demucs")
    ap.add_argument("--char", default="mario")
    ap.add_argument("--id", dest="song_id", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--f0-up-key", type=int, default=0)
    ap.add_argument("--index-rate", type=float, default=0.6)
    ap.add_argument("--protect", type=float, default=0.25)
    ap.add_argument("--workdir", default=os.path.join(_ROOT, "scripts", "_song_work"))
    ap.add_argument("--model", dest="model_path", default=None,
                    help="RVC .pth override (default: the server's model / MarioSwitch fallback)")
    return ap


def main(argv=None):
    ap = build_argparser()
    args = ap.parse_args(argv)
    if bool(args.inp) == bool(args.vocals_in):
        ap.error("give exactly one of --in (full mix) or --vocals-in (acapella)")

    songs_dir = os.path.join(_ROOT, "characters", args.char, "songs")
    os.makedirs(songs_dir, exist_ok=True)
    out_wav = os.path.join(songs_dir, f"{args.song_id}.wav")

    if args.vocals_in:
        print(f"[1/3] using provided acapella: {args.vocals_in} (demucs skipped)")
        vocals = args.vocals_in
    else:
        print(f"[1/3] isolating vocals from {args.inp}")
        vocals = isolate_vocals(args.inp, args.workdir)
    params = rvc_params(args.f0_up_key, args.index_rate, args.protect)
    print(f"[2/3] RVC -> {args.char} timbre  params={params}")
    convert_to_character(vocals, out_wav, params, model_path=args.model_path)
    print(f"[3/3] wrote {out_wav}")
    print(f"Now create characters/{args.char}/songs/{args.song_id}.json (see the design spec).")


if __name__ == "__main__":
    main()
