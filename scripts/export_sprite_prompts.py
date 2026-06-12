"""Export ready-to-paste image-generation prompts for every sprite pose.

For each character, writes characters/<char>/sprite_prompts.txt containing the
FULL prompt for each of the 39 poses — exactly what the wizard sends to the
image backend (visual_description + pose + art-style suffix + framing). Paste
any line into a free image generator (Gemini, Bing, Leonardo, etc.) by hand.

Usage:
    venv/Scripts/python.exe scripts/export_sprite_prompts.py            # all chars
    venv/Scripts/python.exe scripts/export_sprite_prompts.py reze jax   # specific
"""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

import yaml  # noqa: E402
from character_creator import sprite_generator as sg  # noqa: E402


def export_char(char: str) -> str | None:
    ypath = os.path.join(BASE, "characters", char, "character.yaml")
    if not os.path.exists(ypath):
        print(f"[prompts] {char}: no character.yaml — skip")
        return None
    y = yaml.safe_load(open(ypath, encoding="utf-8"))
    visuals = y.get("visuals", {}) or {}
    desc = visuals.get("visual_description", "")
    if not desc:
        ident = y.get("identity", {}) or {}
        desc = f"{ident.get('display_name', char)}, {ident.get('description', '')}"
    art = visuals.get("art_style", "3d_figurine")
    style = sg.ART_STYLE_SUFFIXES.get(art, sg.ART_STYLE_SUFFIXES["3d_figurine"])

    lines = [
        f"# Sprite prompts for {char}",
        f"# art_style: {art}",
        "# Paste any prompt below into a free image generator. Generate on a plain",
        "# white or transparent background; the app removes the background itself.",
        "# Save each result as characters/%s/sprites/<path>.png" % char,
        "",
        "## CHARACTER DESCRIPTION (reused in every prompt)",
        desc,
        "",
        "## PER-POSE PROMPTS",
        "",
    ]
    plan = sg._generation_pose_plan()
    for info in plan:
        full = info["prompt"].replace("{char}", desc) + style + sg.FRAMING_SUFFIX
        lines.append(f"### {info['sprite_path']}")
        lines.append(full)
        lines.append("")

    out = os.path.join(BASE, "characters", char, "sprite_prompts.txt")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"[prompts] {char}: {len(plan)} prompts -> {out}")
    return out


def main():
    chars = sys.argv[1:]
    if not chars:
        cdir = os.path.join(BASE, "characters")
        chars = [d for d in sorted(os.listdir(cdir))
                 if not d.startswith("_")
                 and os.path.isfile(os.path.join(cdir, d, "character.yaml"))]
    for c in chars:
        export_char(c)


if __name__ == "__main__":
    main()
