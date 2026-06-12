"""Import hand-made / premium sprites (e.g. ChatGPT-generated) for a character.

Workflow for replacing drip sprites with better manual ones:
  1. Generate an image for a pose (e.g. positive/happy).
  2. Save it into  characters/<char>/_incoming/  named after the pose with the
     slash as a dash or underscore, e.g.:
        positive-happy.png   or   positive_happy.png   or   happy.png
  3. Run:  venv/Scripts/python.exe scripts/import_sprites.py reze
  4. Each image is background-removed (rembg, transparent), installed to
     characters/<char>/sprites/<pose>.png, marked done in the flux drip state
     so the drip never overwrites your premium version, and the source moved to
     _incoming/done/.

Filename → pose matching is fuzzy: it matches the trailing segment of any of
the 39 canonical pose paths, so "happy.png" -> positive/happy, "wave.png" ->
greeting/wave, "talking_excited.png" -> speech/talking_excited.
"""
import json
import os
import shutil
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
from character_creator import sprite_generator as sg  # noqa: E402

STATE_PATH = os.path.join(BASE, ".secrets", "flux_drip_state.json")


def _pose_index():
    """Map every matchable key -> canonical pose path."""
    idx = {}
    for info in sg._generation_pose_plan():
        p = info["sprite_path"]              # e.g. speech/talking_excited
        idx[p.replace("/", "_")] = p         # speech_talking_excited
        idx[p.replace("/", "-")] = p
        idx[p.split("/")[-1]] = p            # talking_excited
    return idx


def _autocrop(png_path, pad_frac=0.04):
    """Crop a transparent-background PNG to the character's bounding box (+ small
    margin) so the figure fills the sprite instead of floating tiny in a huge
    landscape canvas. Keeps it RGBA."""
    from PIL import Image
    im = Image.open(png_path).convert("RGBA")
    bbox = im.split()[3].getbbox()  # alpha bounding box
    if not bbox:
        return
    w, h = im.size
    pad = int(max(w, h) * pad_frac)
    l, t, r, b = bbox
    l = max(0, l - pad); t = max(0, t - pad)
    r = min(w, r + pad); b = min(h, b + pad)
    im.crop((l, t, r, b)).save(png_path)


def _mark_done(char, pose):
    try:
        state = json.load(open(STATE_PATH, encoding="utf-8"))
    except Exception:
        state = {"done": []}
    key = f"{char}/{pose}"
    if key not in state.setdefault("done", []):
        state["done"].append(key)
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    json.dump(state, open(STATE_PATH, "w", encoding="utf-8"), indent=1)


def main():
    char = sys.argv[1] if len(sys.argv) > 1 else "reze"
    inbox = os.path.join(BASE, "characters", char, "_incoming")
    if not os.path.isdir(inbox):
        os.makedirs(inbox, exist_ok=True)
        print(f"[import] created {inbox} — drop pose-named images there and re-run")
        return
    done_dir = os.path.join(inbox, "done")
    os.makedirs(done_dir, exist_ok=True)
    idx = _pose_index()

    imported = 0
    for fn in sorted(os.listdir(inbox)):
        src = os.path.join(inbox, fn)
        if not os.path.isfile(src) or not fn.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
            continue
        stem = os.path.splitext(fn)[0].lower().strip()
        pose = idx.get(stem)
        if not pose:
            print(f"[import] {fn}: no matching pose (use names like positive_happy.png) — skipped")
            continue
        out = os.path.join(BASE, "characters", char, "sprites", f"{pose}.png")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(src, "rb") as f:
            sg._try_remove_background(f.read(), out)  # transparent cutout
        _autocrop(out)  # trim huge transparent margins so the figure fills the sprite
        _mark_done(char, pose)
        shutil.move(src, os.path.join(done_dir, fn))
        imported += 1
        print(f"[import] {fn} -> sprites/{pose}.png (bg removed, drip-protected)")

    print(f"[import] DONE: {imported} sprite(s) imported for {char}")


if __name__ == "__main__":
    main()
