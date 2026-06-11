"""Render the same line from every saved fine-tune checkpoint, for A/B by epoch.

GPT-SoVITS saves a SoVITS (s2) weight every N epochs and a GPT (s1) weight every
N epochs. Fine-tunes can OVERFIT, so the last epoch isn't always best. This
renders one line through each (s2 x s1) checkpoint pair so you can listen and
pick the winner.

Run (GPT-SoVITS venv, after training, GPU free):
    gpt_sovits_env/Scripts/python.exe scripts/render_checkpoints.py jax "Your line here"

Outputs: model_comparison/<char>_ckpt_<s2tag>_<s1tag>.wav
"""
import os
import re
import sys

# GPT-SoVITS prints normalized text (which can contain non-cp1252 chars) to
# stdout during synthesis. Under a Windows console / redirect using cp1252 that
# raises UnicodeEncodeError mid-run and aborts the synth, leaving silent 0.5s
# wavs. Force UTF-8 so synthesis never dies on a print.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.join(BASE, "gpt_sovits_repo")
OUT = os.path.join(BASE, "model_comparison")


def find_ckpts(char):
    s2dir = os.path.join(REPO, "SoVITS_weights_v2")
    s1dir = os.path.join(REPO, "GPT_weights_v2")
    s2 = [os.path.join(s2dir, f) for f in os.listdir(s2dir)
          if char.lower() in f.lower() and f.endswith(".pth")] if os.path.isdir(s2dir) else []
    s1 = [os.path.join(s1dir, f) for f in os.listdir(s1dir)
          if char.lower() in f.lower() and f.endswith(".ckpt")] if os.path.isdir(s1dir) else []
    return sorted(s2), sorted(s1)


def _tag(path):
    m = re.search(r"e(\d+)", os.path.basename(path))
    return f"e{m.group(1)}" if m else os.path.splitext(os.path.basename(path))[0][-6:]


def main():
    char = sys.argv[1] if len(sys.argv) > 1 else "jax"
    line = sys.argv[2] if len(sys.argv) > 2 else (
        "Well well well, look who wandered into the digital circus. "
        "Try to keep up, newbie, things get weird around here.")
    os.makedirs(OUT, exist_ok=True)

    ref = os.path.join(BASE, "characters", char, "voice", "reference_audio.wav")
    rtxt_path = os.path.join(BASE, "characters", char, "voice", "reference_text.txt")
    ref_text = open(rtxt_path, encoding="utf-8").read().strip() if os.path.exists(rtxt_path) else ""

    s2s, s1s = find_ckpts(char)
    print(f"[ckpt] {char}: {len(s2s)} SoVITS x {len(s1s)} GPT checkpoints", flush=True)
    if not s2s or not s1s:
        sys.exit("[ckpt] no checkpoints found yet — train first")

    sys.path.insert(0, REPO)
    sys.path.insert(0, os.path.join(REPO, "GPT_SoVITS"))
    os.environ.setdefault("PYTHONPATH", os.pathsep.join([os.path.join(REPO, "GPT_SoVITS"), REPO]))
    os.chdir(REPO)
    from GPT_SoVITS.TTS_infer_pack.TTS import TTS, TTS_Config  # noqa: E402
    import soundfile as sf  # noqa: E402

    cfg = TTS_Config(os.path.join(REPO, "GPT_SoVITS/configs/tts_infer.yaml"))
    cfg.device = "cuda"
    tts = TTS(cfg)

    rendered = []
    for s2 in s2s:
        for s1 in s1s:
            tag = f"{_tag(s2)}_{_tag(s1)}"
            outp = os.path.join(OUT, f"{char}_ckpt_{tag}.wav")
            tts.init_t2s_weights(s1)
            tts.init_vits_weights(s2)
            gen = tts.run({
                "text": line, "text_lang": "en",
                "ref_audio_path": ref, "prompt_text": ref_text, "prompt_lang": "en",
                "top_k": 5, "top_p": 1, "temperature": 1,
                "text_split_method": "cut0", "speed_factor": 1.0,
                "return_fragment": False, "fragment_interval": 0.3,
            })
            for sr, audio in gen:
                sf.write(outp, audio, sr)
                rendered.append((tag, outp))
                print(f"[ckpt] rendered {tag} -> {outp}", flush=True)
                break
    print("\n[ckpt] DONE. Samples:", flush=True)
    for tag, p in rendered:
        print(f"  {tag}: {p}", flush=True)


if __name__ == "__main__":
    main()
