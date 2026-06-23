"""Render A/B samples: OLD Mario model vs every NEW mario2 epoch combo.

Renders a fixed set of test lines (countdown numbers, the -a flourish,
interjections, general) through:
  - OLD: mario_models_new/GPT_SoVITS_Mario/ (Mario-e20.ckpt + Mario_e15_s255.pth)
  - NEW: every (s2 x s1) checkpoint pair for exp 'mario2' saved during training
         (gpt_sovits_repo/SoVITS_weights_v2 + GPT_weights_v2)

So in the morning you can listen and (a) hear old-vs-new and (b) pick the best
new epoch combo — same flow as the Pomni e8_e4 pick.

Run (GPT-SoVITS venv, after training, GPU free):
    gpt_sovits_env/Scripts/python.exe scripts/render_mario_ab.py

Outputs: model_comparison/mario_ab/<model>__<line>.wav  + INDEX.txt
"""
import os
import re
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.join(BASE, "gpt_sovits_repo")
OUT = os.path.join(BASE, "model_comparison", "mario_ab")

TEST_LINES = {
    "countdown10": "Ten! Nine! Eight! Seven! Six! Five! Four! Three! Two! One!",
    "countdown_shot": "Three! Two! One! Take a shot!",
    "itsame": "It's-a me, Mario! Let's-a go, my friend!",
    "interjections": "Hmm, well, oh boy! So, you know, let me think.",
    "general": "Welcome to the party! Wash your hands and have a great time!",
}


def _tag(path):
    m = re.search(r"e(\d+)", os.path.basename(path))
    return f"e{m.group(1)}" if m else os.path.splitext(os.path.basename(path))[0][-6:]


def _find(folder, ext, needle):
    d = os.path.join(REPO, folder)
    if not os.path.isdir(d):
        return []
    return sorted(os.path.join(d, f) for f in os.listdir(d)
                  if f.endswith(ext) and needle.lower() in f.lower())


def main():
    os.makedirs(OUT, exist_ok=True)

    # NEW mario2 checkpoint combos (saved during training)
    s2s = _find("SoVITS_weights_v2", ".pth", "mario2")
    s1s = _find("GPT_weights_v2", ".ckpt", "mario2")
    new_ref = os.path.join(BASE, "characters", "mario2", "voice", "reference_audio.wav")
    new_reftxt_p = os.path.join(BASE, "characters", "mario2", "voice", "reference_text.txt")
    new_reftxt = open(new_reftxt_p, encoding="utf-8").read().strip() if os.path.exists(new_reftxt_p) else ""

    # OLD model
    old_dir = os.path.join(BASE, "mario_models_new", "GPT_SoVITS_Mario")
    old_s2 = os.path.join(old_dir, "Mario_e15_s255.pth")
    old_s1 = os.path.join(old_dir, "Mario-e20.ckpt")
    old_ref = os.path.join(old_dir, "mario_ref.wav")
    old_reftxt_p = os.path.join(BASE, "characters", "mario", "voice", "reference_text.txt")
    # Match the server's old-Mario prompt exactly (gpt_sovits_server DEFAULT_PROMPT_TEXT)
    # so the A/B reflects how old Mario actually sounds live.
    old_reftxt = open(old_reftxt_p, encoding="utf-8").read().strip() if os.path.exists(old_reftxt_p) else "It's a me Mario"

    # model list: (label, s1_ckpt, s2_pth, ref_wav, ref_text)
    models = []
    if os.path.exists(old_s1) and os.path.exists(old_s2):
        models.append(("OLD", old_s1, old_s2, old_ref, old_reftxt))
    for s2 in s2s:
        for s1 in s1s:
            models.append((f"NEW_{_tag(s2)}_{_tag(s1)}", s1, s2, new_ref, new_reftxt))

    print(f"[ab] {len(s2s)} new SoVITS x {len(s1s)} new GPT combos + "
          f"{'OLD' if models and models[0][0]=='OLD' else 'no old'}", flush=True)
    if not s2s or not s1s:
        print("[ab] WARNING: no mario2 checkpoints found — train first", flush=True)
    if not models:
        sys.exit("[ab] nothing to render")

    sys.path.insert(0, REPO)
    sys.path.insert(0, os.path.join(REPO, "GPT_SoVITS"))
    os.environ.setdefault("PYTHONPATH", os.pathsep.join([os.path.join(REPO, "GPT_SoVITS"), REPO]))
    os.chdir(REPO)
    from GPT_SoVITS.TTS_infer_pack.TTS import TTS, TTS_Config  # noqa: E402
    import soundfile as sf  # noqa: E402

    cfg = TTS_Config(os.path.join(REPO, "GPT_SoVITS/configs/tts_infer.yaml"))
    cfg.device = "cuda"
    tts = TTS(cfg)

    index = []
    for label, s1, s2, ref, reftxt in models:
        if not (os.path.exists(s1) and os.path.exists(s2) and os.path.exists(ref)):
            print(f"[ab] skip {label}: missing weights/ref", flush=True)
            continue
        tts.init_t2s_weights(s1)
        tts.init_vits_weights(s2)
        for slug, line in TEST_LINES.items():
            outp = os.path.join(OUT, f"{label}__{slug}.wav")
            try:
                gen = tts.run({
                    "text": line, "text_lang": "en",
                    "ref_audio_path": ref, "prompt_text": reftxt, "prompt_lang": "en",
                    "top_k": 5, "top_p": 1, "temperature": 1,
                    "text_split_method": "cut0", "speed_factor": 1.0,
                    "return_fragment": False, "fragment_interval": 0.3,
                })
                for sr, audio in gen:
                    sf.write(outp, audio, sr)
                    index.append(f"{label}__{slug}.wav  <-  \"{line}\"")
                    print(f"[ab] {label} / {slug}", flush=True)
                    break
            except Exception as e:
                print(f"[ab] ERROR {label}/{slug}: {e}", flush=True)

    with open(os.path.join(OUT, "INDEX.txt"), "w", encoding="utf-8") as f:
        f.write("Mario voice A/B — OLD vs NEW (mario2, trained on the Evolution compilation)\n")
        f.write("=" * 70 + "\n\n")
        f.write("Compare OLD__<line> vs NEW_<s2>_<s1>__<line>. Pick the best NEW combo.\n")
        f.write("Key line to judge the numbers fix: *countdown10* and *countdown_shot*.\n\n")
        f.write("\n".join(sorted(index)) + "\n")
    print(f"\n[ab] DONE -> {OUT}\n[ab] {len(index)} clips. See INDEX.txt", flush=True)


if __name__ == "__main__":
    main()
