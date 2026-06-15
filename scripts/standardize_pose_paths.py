"""Standardize character sprite pose paths to the canonical March 7th model.

Many characters (the HSR/template cohort) were authored with an old set of
pose-path names (memorial/respectful, movement/action, reactions/shocked, ...)
that do NOT match the canonical generation-plan paths the drip + premium
importer write to. That mismatch caused the client to load stale sprites while
premium versions sat unused (the March 7th bug). This migrates every affected
character to the canonical paths: renames existing sprite files AND rewrites the
emotion/state map strings in character.yaml.

KEEP-CUSTOM characters (rudi, sonic) use intentional bespoke names and are
skipped. mario is skipped (separate asset source). march7th is already canonical.

Usage:
  venv/Scripts/python.exe scripts/standardize_pose_paths.py [--dry-run] [--only NAME]
"""
import argparse
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHARS_DIR = os.path.join(BASE, "characters")

SKIP = {"rudi", "sonic", "mario", "march7th"}

# old custom path -> canonical path (the March model)
RENAME = {
    "memorial/respectful": "memorial/moment_of_silence",
    "movement/action": "movement/dancing",
    "negative/startled": "negative/scared",
    "party/birthday": "birthday/birthday",
    "positive/charmed": "positive/love",
    "positive/confident": "positive/proud",
    "reactions/shocked": "thinking/shocked",
    "sleep/yawning": "sleep/sleepy",
    "speech/explaining": "speech/talking_excited",
    "thinking/focused": "thinking/determined",
    "thinking/pondering": "thinking/thinking",
    "thinking/scheming": "thinking/mischievous",
}


def migrate_char(name, dry):
    cdir = os.path.join(CHARS_DIR, name)
    ypath = os.path.join(cdir, "character.yaml")
    sdir = os.path.join(cdir, "sprites")
    if not os.path.isfile(ypath):
        return None
    text = open(ypath, encoding="utf-8").read()
    used = [old for old in RENAME if old in text]
    if not used:
        return None  # nothing to do (already canonical or different scheme)

    file_ops = []   # (src, dst)
    for old in used:
        new = RENAME[old]
        src = os.path.join(sdir, old + ".png")
        dst = os.path.join(sdir, new + ".png")
        if os.path.isfile(src):
            if os.path.isfile(dst):
                file_ops.append((src, None))  # canonical already exists -> drop the old dup
            else:
                file_ops.append((src, dst))

    # yaml string replacement (longest-first to avoid partial overlaps; none here overlap)
    new_text = text
    for old in sorted(used, key=len, reverse=True):
        new_text = new_text.replace(old, RENAME[old])

    if not dry:
        for src, dst in file_ops:
            if dst is None:
                os.remove(src)
            else:
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                os.rename(src, dst)
        open(ypath, "w", encoding="utf-8").write(new_text)

    return {"used": used, "file_ops": file_ops}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only", help="single character name")
    args = ap.parse_args()

    names = [args.only] if args.only else sorted(
        d for d in os.listdir(CHARS_DIR) if os.path.isdir(os.path.join(CHARS_DIR, d)))

    total_files = total_chars = 0
    for name in names:
        if name in SKIP:
            continue
        res = migrate_char(name, args.dry_run)
        if not res:
            continue
        total_chars += 1
        renamed = sum(1 for _, d in res["file_ops"] if d)
        dropped = sum(1 for _, d in res["file_ops"] if d is None)
        total_files += renamed
        tag = "WOULD" if args.dry_run else "DID"
        print(f"[{tag}] {name}: {len(res['used'])} map paths, "
              f"{renamed} files renamed, {dropped} dup dropped")

    print(f"\n{'DRY-RUN ' if args.dry_run else ''}TOTAL: {total_chars} characters, "
          f"{total_files} files renamed")


if __name__ == "__main__":
    main()
