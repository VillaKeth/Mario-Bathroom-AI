"""Move flat (root-level) sprite files into canonical subfolders.

Some characters (goku, power, voice-test bots) had sprites generated with the
old flat layout: characters/<c>/sprites/angry.png instead of
characters/<c>/sprites/negative/angry.png. Their character.yaml maps reference
the subfolder paths, so the client never found them. Map each flat file
(<pose_name>.png) to its canonical sprite_path via the generation plan and move
it; drop flat files whose canonical target already exists.

Usage: venv/Scripts/python.exe scripts/fix_flat_sprites.py [--dry-run]
"""
import argparse
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
from character_creator import sprite_generator as sg  # noqa: E402

CHARS = os.path.join(BASE, "characters")


def plan_map():
    m = {i["pose_name"]: i["sprite_path"] for i in sg._generation_pose_plan()}
    m.setdefault("state_idle", "neutral/idle")  # dup of emotion 'neutral'
    return m


def fix(name, m, dry):
    sd = os.path.join(CHARS, name, "sprites")
    roots = [f for f in os.listdir(sd)
             if f.endswith(".png") and os.path.isfile(os.path.join(sd, f))]
    moved = dropped = unknown = 0
    for f in roots:
        pose = f[:-4]
        target = m.get(pose)
        if not target:
            unknown += 1
            print(f"  ? {name}: no plan path for flat '{f}' (left in place)")
            continue
        src = os.path.join(sd, f)
        dst = os.path.join(sd, target + ".png")
        if os.path.isfile(dst):
            if not dry:
                os.remove(src)
            dropped += 1
        else:
            if not dry:
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                os.rename(src, dst)
            moved += 1
    return moved, dropped, unknown


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    m = plan_map()
    flat = []
    for c in sorted(os.listdir(CHARS)):
        sd = os.path.join(CHARS, c, "sprites")
        if os.path.isdir(sd) and any(
                f.endswith(".png") and os.path.isfile(os.path.join(sd, f))
                for f in os.listdir(sd)):
            flat.append(c)
    tag = "WOULD" if args.dry_run else "DID"
    for c in flat:
        mo, dr, un = fix(c, m, args.dry_run)
        print(f"[{tag}] {c}: {mo} moved, {dr} dup dropped, {un} unknown")
    print(f"\n{'DRY-RUN ' if args.dry_run else ''}chars: {len(flat)}")


if __name__ == "__main__":
    main()
