"""Render the SAME phrases through two or more GPT (s1) checkpoints so you can
pick the better epoch by ear.

render_voice_tune.py sweeps sampling knobs for ONE checkpoint pair; this is the
other axis — sampling held fixed, the checkpoint varied. Its output names carry
the checkpoint stem, so runs never overwrite each other.

The reference prompt text is read from character.yaml (voice.prompt_text), with
voice/reference_text.txt as a fallback. Passing an empty prompt_text degrades
GPT-SoVITS noticeably, so a missing one is reported rather than silently used.

Run (GPT-SoVITS venv, GPU free):
    gpt_sovits_env/Scripts/python.exe scripts/ab_checkpoints.py charlie_kirk \
        charlie_kirk_e8_s1056.pth charlie_kirk-e12.ckpt charlie_kirk-e24.ckpt

Outputs: model_comparison/<char>_ab/<ckpt_stem>__<NN>_<slug>.wav
"""
import os
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.join(BASE, "gpt_sovits_repo")

# Fixed, deliberately calm sampling — the point is to compare CHECKPOINTS, so
# every other variable is pinned. Matches the middle of render_voice_tune's grid.
TEMPERATURE = 0.70
TOP_K = 8
TOP_P = 1

# Numbers and countdowns are a known weak spot for these fine-tunes (a training
# set of interview speech rarely contains them), so they get their own probes.
PHRASES = [
    "Hey there, welcome to the party. Glad you could make it.",
    "That is a phenomenal question, and I want to answer it carefully.",
    "Let me count us down. Five, four, three, two, one.",
    "There are twenty seven people here tonight and I have met maybe nine of them.",
    "I have to be honest with you, that is completely wrong and here is why.",
    "Take a deep breath. You are going to be just fine, I promise.",
]


def slug(text, width=28):
    keep = []
    for ch in text.lower():
        if ch.isalnum():
            keep.append(ch)
        elif keep and keep[-1] != "_":
            keep.append("_")
    return "".join(keep).strip("_")[:width]


def prompt_text_for(char):
    yml = os.path.join(BASE, "characters", char, "character.yaml")
    if os.path.exists(yml):
        try:
            import yaml as _yaml
            with open(yml, encoding="utf-8") as f:
                voice = (_yaml.safe_load(f) or {}).get("voice") or {}
            if voice.get("prompt_text"):
                return voice["prompt_text"]
        except Exception as e:
            print(f"[ab] could not read {yml}: {e}", flush=True)
    rtxt = os.path.join(BASE, "characters", char, "voice", "reference_text.txt")
    if os.path.exists(rtxt):
        with open(rtxt, encoding="utf-8") as f:
            return f.read().strip()
    return ""


def main():
    if len(sys.argv) < 4:
        raise SystemExit(
            "usage: ab_checkpoints.py <char> <s2_pth> <s1_ckpt> [<s1_ckpt> ...]")
    char = sys.argv[1]
    s2 = os.path.join(REPO, "SoVITS_weights_v2", sys.argv[2])
    ckpts = sys.argv[3:]

    if not os.path.isfile(s2):
        raise SystemExit(f"[ab] missing s2 weights: {s2}")
    resolved = []
    for c in ckpts:
        p = c if os.path.isfile(c) else os.path.join(REPO, "GPT_weights_v2", c)
        if not os.path.isfile(p):
            raise SystemExit(f"[ab] missing s1 checkpoint: {p}")
        resolved.append(p)

    ref = os.path.join(BASE, "characters", char, "voice", "reference_audio.wav")
    if not os.path.isfile(ref):
        raise SystemExit(f"[ab] missing reference audio: {ref}")
    ref_text = prompt_text_for(char)
    if not ref_text:
        print("[ab] WARNING: no voice.prompt_text and no reference_text.txt — "
              "synthesis quality will be understated for every checkpoint",
              flush=True)

    out_dir = os.path.join(BASE, "model_comparison", f"{char}_ab")
    os.makedirs(out_dir, exist_ok=True)

    print(f"[ab] {char} | s2={os.path.basename(s2)} | "
          f"{len(resolved)} checkpoint(s) x {len(PHRASES)} phrase(s) | "
          f"temp={TEMPERATURE} top_k={TOP_K}", flush=True)

    sys.path.insert(0, REPO)
    sys.path.insert(0, os.path.join(REPO, "GPT_SoVITS"))
    os.environ.setdefault(
        "PYTHONPATH", os.pathsep.join([os.path.join(REPO, "GPT_SoVITS"), REPO]))
    os.chdir(REPO)
    from GPT_SoVITS.TTS_infer_pack.TTS import TTS, TTS_Config  # noqa: E402
    import soundfile as sf  # noqa: E402

    cfg = TTS_Config(os.path.join(REPO, "GPT_SoVITS/configs/tts_infer.yaml"))
    cfg.device = "cuda"
    tts = TTS(cfg)
    tts.init_vits_weights(s2)

    written = []
    for ck in resolved:
        stem = os.path.splitext(os.path.basename(ck))[0]
        tts.init_t2s_weights(ck)
        print(f"[ab] --- {stem} ---", flush=True)
        for i, phrase in enumerate(PHRASES):
            outp = os.path.join(out_dir, f"{stem}__{i:02d}_{slug(phrase)}.wav")
            gen = tts.run({
                "text": phrase, "text_lang": "en",
                "ref_audio_path": ref, "prompt_text": ref_text, "prompt_lang": "en",
                "top_k": TOP_K, "top_p": TOP_P, "temperature": TEMPERATURE,
                "text_split_method": "cut0", "speed_factor": 1.0,
                "return_fragment": False, "fragment_interval": 0.3,
            })
            for sr, audio in gen:
                sf.write(outp, audio, sr)
                print(f"[ab]   {i:02d} {len(audio)/sr:5.1f}s  "
                      f"{os.path.basename(outp)}", flush=True)
                written.append(outp)
                break

    print(f"[ab] DONE -> {out_dir} ({len(written)} files)", flush=True)


if __name__ == "__main__":
    main()
