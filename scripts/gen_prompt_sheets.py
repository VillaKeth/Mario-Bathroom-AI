"""Generate per-character sprite_prompts.txt — paste-ready image-gen prompts.

For every real character, emit one block per pose with the EXACT filename the
sprite must be saved as (the character's own map path), so that an AI (or a
person) generating the art drops each file where the client + character-aware
importer expect it. Pose direction comes from the canonical pose prompts keyed
by the emotion/state, so it works for canonical AND custom path names alike.

Usage:
  venv/Scripts/python.exe scripts/gen_prompt_sheets.py [--only NAME] [--force]
Only writes a sheet if one is missing, unless --force.
"""
import argparse
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
import yaml  # noqa: E402
from character_creator import sprite_generator as sg  # noqa: E402

CHARS_DIR = os.path.join(BASE, "characters")
# scaffolds / non-characters to skip
SKIP = {"mario", "test_bot", "test_voice_bot", "trainable_voice_bot",
        "voicetraintest", "voicetrain", "pomni"}


def _dir_for_emotion(emotion):
    """Canonical pose direction for an emotion/state key."""
    p = sg.POSE_PROMPTS.get(emotion) or sg.STATE_PROMPTS.get(emotion)
    if p:
        return p.replace("{char}", "").strip().lstrip(", ").strip()
    return f"{emotion} expression with matching body pose"


def build_sheet(name):
    cdir = os.path.join(CHARS_DIR, name)
    ypath = os.path.join(cdir, "character.yaml")
    y = yaml.safe_load(open(ypath, encoding="utf-8")) or {}
    vis = y.get("visuals", {}) or {}
    ident = y.get("identity", {}) or {}
    disp = ident.get("display_name") or ident.get("name") or name

    master = (vis.get("visual_description") or vis.get("drip_description")
              or ident.get("description")
              or f"[DESCRIBE {disp}'s appearance here — keep it identical in every block]")

    # (path, direction) deduped by path, ordered: emotions then states
    seen = {}
    for emotion, path in (vis.get("emotion_sprite_map") or {}).items():
        if path and path not in seen:
            seen[path] = _dir_for_emotion(emotion)
    for state, val in (vis.get("state_sprite_map") or {}).items():
        for path in (val if isinstance(val, list) else [val]):
            if path and path not in seen:
                seen[path] = _dir_for_emotion(state)

    lines = []
    lines.append(f"{disp} — SPRITE IMAGE PROMPTS (for GPT-4o / image gen)")
    lines.append("=" * 70)
    lines.append("HOW TO USE: copy one block, paste into the image GPT, generate.")
    lines.append("Save each result at the EXACT path shown, then run:")
    lines.append(f"    venv/Scripts/python.exe scripts/import_sprites.py {name}")
    lines.append("(drop files in characters/{}/_incoming/ named like the path with".format(name))
    lines.append(" slashes as underscores, e.g. positive_happy.png; the importer routes them).")
    lines.append("Keep the MASTER DESCRIPTION identical every time; only 'Pose:' changes.")
    lines.append("=" * 70)
    lines.append("")
    lines.append("MASTER DESCRIPTION (paste into every block):")
    lines.append(master)
    lines.append("")
    lines.append("=" * 70)
    for i, (path, direction) in enumerate(sorted(seen.items()), 1):
        fn = path.replace("/", "_")
        lines.append("")
        lines.append(f"[{i:02d}] save as: sprites/{path}.png   (file: {fn}.png)")
        lines.append("-" * 70)
        lines.append(f"{{MASTER DESCRIPTION}}  Pose: {direction}.")
    lines.append("")
    return "\n".join(lines), len(seen)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    names = [args.only] if args.only else sorted(
        d for d in os.listdir(CHARS_DIR) if os.path.isdir(os.path.join(CHARS_DIR, d)))
    wrote = skipped = 0
    for name in names:
        if name in SKIP:
            continue
        ypath = os.path.join(CHARS_DIR, name, "character.yaml")
        if not os.path.isfile(ypath):
            continue
        out = os.path.join(CHARS_DIR, name, "sprite_prompts.txt")
        if os.path.isfile(out) and not args.force:
            skipped += 1
            continue
        sheet, n = build_sheet(name)
        open(out, "w", encoding="utf-8").write(sheet)
        wrote += 1
        print(f"[wrote] {name}: {n} pose blocks")
    print(f"\nwrote {wrote} sheets, skipped {skipped} (already had one; use --force to overwrite)")


if __name__ == "__main__":
    main()
