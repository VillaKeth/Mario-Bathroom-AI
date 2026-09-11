"""Report which .ckpt/.pth tts._resolve_sovits_models would load for a character.

    venv/Scripts/python.exe scripts/which_sovits.py [folder ...]

No args = every character folder that has a character.yaml. The lookup key is
identity.name from character.yaml (NOT the folder name, NOT config.json).
"""
import os, sys, yaml

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.join(BASE, "mario_models_new")
CHARS = os.path.join(BASE, "characters")


def resolve(char_name):
    """Mirror of tts._resolve_sovits_models -> (ckpt, pth, dir, is_finetune)."""
    cands = [f"GPT_SoVITS_{char_name.capitalize()}"]
    for d in sorted(os.listdir(ROOT)):
        if d.lower().startswith(f"gpt_sovits_{char_name.lower()}") and d not in cands:
            cands.append(d)
    for n in cands:
        p = os.path.join(ROOT, n)
        if not os.path.isdir(p):
            continue
        files = os.listdir(p)
        ck = [f for f in files if f.endswith(".ckpt")]
        pt = [f for f in files if f.endswith(".pth")]
        if ck and pt:
            return ck[0], pt[0], n, True, len(ck), len(pt)
    return "s1bert25hz-...ckpt", "s2G2333k.pth", "(v2 base)", False, 1, 1


folders = sys.argv[1:] or sorted(
    d for d in os.listdir(CHARS)
    if os.path.isfile(os.path.join(CHARS, d, "character.yaml")))

for f in folders:
    y = os.path.join(CHARS, f, "character.yaml")
    if not os.path.isfile(y):
        print(f"{f}: no character.yaml")
        continue
    name = yaml.safe_load(open(y, encoding="utf-8"))["identity"]["name"]
    ck, pt, d, ft, nck, npt = resolve(name.lower())
    if not ft:
        continue  # only report characters that actually have a fine-tune
    extra = ""
    if nck > 1 or npt > 1:
        extra = f"   <-- {nck} ckpt / {npt} pth present, picks [0] alphabetically"
    print(f"{f:14} identity={name!r:16} -> {d}")
    print(f"{'':14}   ckpt={ck}")
    print(f"{'':14}   pth ={pt}{extra}")
