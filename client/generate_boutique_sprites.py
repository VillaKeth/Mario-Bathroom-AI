"""Generate 10 hand-crafted Mario sprite iteration folders in assets_boutique.

Each iteration rebuilds the full sprite set with deliberate facial + costume details:
- plumber cap silhouette
- overalls + buttons
- mustache definition
- large blue eyes
"""

import os
from datetime import datetime, UTC
from typing import Any

from PIL import Image

from generate_sprites import (
    PALETTE,
    add_drop_shadow,
    add_outline,
    SPRITE_DANCE,
    SPRITE_IDLE,
    SPRITE_JUMP,
    SPRITE_LAUGH,
    SPRITE_SLEEP,
    SPRITE_SURPRISE,
    SPRITE_TALK,
    SPRITE_THINK,
    SPRITE_WALK1,
    SPRITE_WALK2,
    SPRITE_WAVE,
)

ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
OUTPUT_DIR = os.path.join(ROOT_DIR, "assets_boutique")

# sprite_name -> (data, eye_row_start_index, eye_type)
# eye_type: open | half | closed
SPRITE_TEMPLATES = {
    "idle": (SPRITE_IDLE, 6, "open"),
    "talk": (SPRITE_TALK, 6, "open"),
    "walk1": (SPRITE_WALK1, 6, "open"),
    "walk2": (SPRITE_WALK2, 6, "open"),
    "wave": (SPRITE_WAVE, 6, "open"),
    "jump": (SPRITE_JUMP, 6, "open"),
    "think": (SPRITE_THINK, 6, "half"),
    "laugh": (SPRITE_LAUGH, 6, "closed"),
    "surprise": (SPRITE_SURPRISE, 6, "open"),
    "sleep": (SPRITE_SLEEP, 9, "closed"),
    "dance": (SPRITE_DANCE, 6, "open"),
}

STYLE_BASE: dict[str, Any] = {
    "id": "base",
    "note": "Base style",
    "scale": 12,
    "palette_overrides": {},
    "hat_top": "....rrrrr.......",
    "hat_brim": "...rrrrrrrrr....",
    "hat_shadow": "...drrrrrrrrr...",
    "hat_side": "..drrrrrrrrrrd..",
    "nose_row": "..ssssnssnsss...",
    "mustache_row": "..ssbbbbbbbss...",
    "mouth_neutral": "...ssssssssss...",
    "mouth_talk": "...ssnrrrnsss...",
    "mouth_talk2": "...snrrrrrnsss..",
    "mouth_laugh": "...snrrrrrnsn...",
    "mouth_surprise": "...sssnrnsssn...",
    "shirt_row": "....rrrrrrrr....",
    "bib_row": "..rrrruuuurrrr..",
    "buttons_row": "..rrrruuyuurrrr.",
    "eye_open_top": "wuuuw",
    "eye_open_bottom": "ukuku",
    "eye_half_top": "nuuun",
    "eye_half_bottom": "ukuku",
    "eye_closed_top": "nnnnn",
    "eye_closed_bottom": "sssss",
}


def build_style(style_id: str, note: str, overrides: dict[str, Any]) -> dict[str, Any]:
    style = dict(STYLE_BASE)
    style["palette_overrides"] = dict(STYLE_BASE["palette_overrides"])
    style.update(overrides)
    style["id"] = style_id
    style["note"] = note
    return style


STYLES = [
    build_style(
        "01_classic_cobalt",
        "Balanced classic Mario proportions with rounded cobalt eyes.",
        {},
    ),
    build_style(
        "02_heroic_round",
        "Wider hat brim, fuller mustache, rounded blue irises.",
        {
            "hat_top": "...rrrrrrr......",
            "hat_brim": "..rrrrrrrrrrr...",
            "hat_shadow": "..ddrrrrrrrrr...",
            "hat_side": ".ddrrrrrrrrrrdd.",
            "nose_row": "..sssnnssnnss...",
            "mustache_row": "..sbbbbbbbbbbs..",
            "mouth_neutral": "...ssnssssnss...",
            "mouth_talk": "...ssnrrrnnss...",
            "mouth_talk2": "...snrrrrrnnss..",
            "mouth_laugh": "...snrrrrrrns...",
            "mouth_surprise": "...sssnrrnsss...",
            "shirt_row": "...rrrrrrrrrr...",
            "bib_row": "..rrruuuuuurrr..",
            "buttons_row": "..rrruuyyuuurrr.",
            "eye_open_top": "suuus",
            "eye_open_bottom": "sukus",
            "eye_half_top": "nnnnn",
            "eye_half_bottom": "sukus",
            "palette_overrides": {
                "r": (232, 24, 8, 255),
                "d": (172, 8, 8, 255),
                "u": (24, 112, 248, 255),
                "i": (16, 74, 206, 255),
            },
        },
    ),
    build_style(
        "03_arcade_bold",
        "Arcade-forward contrast with punchy blues and deeper facial lines.",
        {
            "hat_top": ".....rrrrr......",
            "hat_brim": "...rrrrrrrrrr...",
            "hat_shadow": "...ddrrrrrrrr...",
            "hat_side": "..drrrrrrrrrr...",
            "nose_row": "..ssssnnsnnss...",
            "mustache_row": "..ssbbbbbbbbb...",
            "mouth_neutral": "...ssnnnnnnss...",
            "mouth_talk": "...ssnrrrrnss...",
            "mouth_talk2": "...snrrrrrrnss..",
            "mouth_laugh": "...snrrrrrrrs...",
            "mouth_surprise": "...sssnrrnsss...",
            "shirt_row": "...drrrrrrrrd...",
            "buttons_row": "..rrrruuyyuurrr.",
            "eye_open_top": "uuuuu",
            "eye_open_bottom": "uukuu",
            "eye_half_top": "iuuui",
            "eye_half_bottom": "uukuu",
            "palette_overrides": {
                "r": (246, 20, 12, 255),
                "d": (188, 8, 8, 255),
                "u": (52, 130, 255, 255),
                "i": (12, 84, 232, 255),
                "y": (255, 230, 64, 255),
            },
        },
    ),
    build_style(
        "04_soft_chibi",
        "Softer roundness, warm skin, and sparkly blue pupils.",
        {
            "hat_top": "....rrrrrr......",
            "hat_shadow": "...drrrrrrrrd...",
            "nose_row": "..ssssnssnnss...",
            "mouth_neutral": "...ssssnnssss...",
            "mouth_talk": "...ssnrrnrrss...",
            "mouth_talk2": "...snrrrrrrsss..",
            "mouth_laugh": "...ssrrrrrrss...",
            "mouth_surprise": "...sssnrrnsss...",
            "shirt_row": "....rrdrrdrr....",
            "bib_row": "..rrruuuyuuurr..",
            "buttons_row": "..rrruuuyyuurrr.",
            "eye_open_top": "wuuuw",
            "eye_open_bottom": "ukwku",
            "eye_half_top": "nuuun",
            "eye_half_bottom": "ukwku",
            "palette_overrides": {
                "r": (238, 56, 56, 255),
                "d": (194, 36, 36, 255),
                "s": (255, 194, 132, 255),
                "n": (234, 154, 98, 255),
                "u": (40, 130, 255, 255),
                "i": (24, 92, 220, 255),
            },
        },
    ),
    build_style(
        "05_poster_hero",
        "Stronger silhouette with a dramatic cap and bold facial contrast.",
        {
            "hat_top": "..rrrrrrr.......",
            "hat_brim": "..rrrrrrrrrr....",
            "hat_shadow": "..drrrrrrrrrr...",
            "hat_side": ".drrrrrrrrrrrrd.",
            "nose_row": "..sssnsssnsss...",
            "mustache_row": "..ssbbbbbbbbbss.",
            "mouth_neutral": "...sssnnnnsss...",
            "mouth_talk": "...ssnrrrrnss...",
            "mouth_talk2": "...snrrrrrrsss..",
            "mouth_laugh": "...snrrrrrrns...",
            "mouth_surprise": "...sssnrrnsss...",
            "shirt_row": "...rrrrrrrrrr...",
            "bib_row": "..rrruuuuuurrr..",
            "buttons_row": "..rrruuuyyuurrr.",
            "eye_open_top": "iuuui",
            "eye_open_bottom": "ikuki",
            "eye_half_top": "niiin",
            "eye_half_bottom": "ikuki",
            "palette_overrides": {
                "r": (216, 0, 0, 255),
                "d": (148, 0, 0, 255),
                "u": (8, 96, 255, 255),
                "i": (0, 60, 214, 255),
                "b": (142, 78, 0, 255),
                "g": (82, 46, 0, 255),
            },
        },
    ),
    build_style(
        "06_friendly_smile",
        "Warm, approachable expression with bright hat and soft shading.",
        {
            "hat_top": "...rrrrrrrr.....",
            "hat_brim": "...rrrrrrrrrr...",
            "hat_shadow": "...drrrrrrrrdd..",
            "mustache_row": "..sbbbbbbbbbbs..",
            "mouth_neutral": "...ssnnnnnnss...",
            "mouth_talk": "...ssnrrrnnss...",
            "mouth_talk2": "...snrrrrrrnss..",
            "mouth_laugh": "...snnrrrrnns...",
            "mouth_surprise": "...sssnnnnsss...",
            "shirt_row": "....rrrrddrr....",
            "bib_row": "..rrrruuiuurrr..",
            "buttons_row": "..rrrruuyyurrrr.",
            "eye_open_bottom": "ukkku",
            "eye_half_bottom": "ukkku",
            "palette_overrides": {
                "r": (236, 34, 18, 255),
                "d": (178, 18, 10, 255),
                "s": (255, 188, 120, 255),
                "u": (20, 118, 255, 255),
                "i": (8, 76, 210, 255),
            },
        },
    ),
    build_style(
        "07_cinematic_shade",
        "Darker movie-like shading with intense sapphire eyes.",
        {
            "hat_brim": "..rrrrrrrrrr....",
            "hat_shadow": "..ddrrrrrrrrd...",
            "hat_side": ".ddrrrrrrrrrrdd.",
            "nose_row": "..sssnnssnnss...",
            "mustache_row": "...sbbbbbbbbs...",
            "mouth_neutral": "...ssnnssnnss...",
            "mouth_talk": "...ssnrrrrnss...",
            "mouth_laugh": "...snnrrrrnns...",
            "shirt_row": "...drrrrrrrrd...",
            "bib_row": "..rrrruuiuurrr..",
            "buttons_row": "..rrruuuyyuurrr.",
            "eye_open_top": "wiiiw",
            "eye_open_bottom": "ikiki",
            "eye_half_top": "niiin",
            "eye_half_bottom": "ikiki",
            "palette_overrides": {
                "r": (196, 0, 0, 255),
                "d": (130, 0, 0, 255),
                "b": (120, 64, 0, 255),
                "g": (70, 38, 0, 255),
                "u": (0, 92, 220, 255),
                "i": (0, 56, 172, 255),
                "s": (242, 168, 96, 255),
                "n": (206, 132, 76, 255),
            },
        },
    ),
    build_style(
        "08_neon_party",
        "Party-ready high-saturation palette with luminous eyes.",
        {
            "hat_top": "...rrrrrrr......",
            "hat_brim": "...rrrrrrrrrr...",
            "hat_shadow": "..drrrrrrrrrrd..",
            "hat_side": ".drrrrrrrrrrrrd.",
            "nose_row": "..ssssnnsnnss...",
            "mustache_row": "..ssbbbbbbbbb...",
            "mouth_neutral": "...ssnssssnss...",
            "mouth_talk": "...ssnrrnrrss...",
            "mouth_talk2": "...snrrnrrnsss..",
            "mouth_laugh": "...ssrrrrrrss...",
            "mouth_surprise": "...sssnrrnsss...",
            "bib_row": "..rrruuuyuuurr..",
            "buttons_row": "..rrruuuyyuurrr.",
            "eye_open_bottom": "uwkuw",
            "eye_half_bottom": "uwkuw",
            "palette_overrides": {
                "r": (255, 44, 64, 255),
                "d": (214, 16, 40, 255),
                "u": (0, 164, 255, 255),
                "i": (0, 110, 224, 255),
                "y": (255, 240, 68, 255),
            },
        },
    ),
    build_style(
        "09_retro_clean",
        "NES-clean proportions with restrained linework and crisp eyes.",
        {
            "hat_top": ".....rrrrr......",
            "hat_brim": "....rrrrrrrr....",
            "eye_open_top": "suuus",
            "eye_open_bottom": "sukus",
            "eye_half_bottom": "sukus",
            "palette_overrides": {
                "r": (220, 12, 12, 255),
                "d": (164, 0, 0, 255),
                "u": (20, 100, 246, 255),
                "i": (0, 64, 198, 255),
            },
        },
    ),
    build_style(
        "10_boutique_prime",
        "Final polished pass with clean hat structure and premium eye detail.",
        {
            "hat_top": "...rrrrrrrr.....",
            "hat_brim": "..rrrrrrrrrrr...",
            "hat_shadow": "..ddrrrrrrrrr...",
            "hat_side": ".ddrrrrrrrrrrdd.",
            "nose_row": "..ssssnnssnss...",
            "mustache_row": "..sbbbbbbbbbbs..",
            "mouth_neutral": "...ssnnnnnnss...",
            "mouth_talk": "...ssnrrrrnss...",
            "mouth_talk2": "...snrrrrrrnss..",
            "mouth_laugh": "...snrrrrrrns...",
            "mouth_surprise": "...sssnrrnsss...",
            "shirt_row": "...rrrrrrrrrr...",
            "bib_row": "..rrruuuuuurrr..",
            "buttons_row": "..rrruuyyuuurrr.",
            "eye_open_top": "wuuuw",
            "eye_open_bottom": "ukwku",
            "eye_half_bottom": "ukwku",
            "palette_overrides": {
                "r": (232, 18, 8, 255),
                "d": (174, 8, 8, 255),
                "u": (16, 112, 252, 255),
                "i": (0, 72, 210, 255),
                "s": (254, 186, 118, 255),
                "n": (226, 146, 88, 255),
            },
        },
    ),
]


def ensure_row(label: str, row: str) -> None:
    if len(row) != 16:
        raise ValueError(f"{label} must be 16 chars, got {len(row)}: {row}")


def ensure_eye(label: str, eye: str) -> None:
    if len(eye) != 5:
        raise ValueError(f"{label} must be 5 chars, got {len(eye)}: {eye}")


def validate_style(style: dict[str, Any]) -> None:
    row_fields = [
        "hat_top",
        "hat_brim",
        "hat_shadow",
        "hat_side",
        "nose_row",
        "mustache_row",
        "mouth_neutral",
        "mouth_talk",
        "mouth_talk2",
        "mouth_laugh",
        "mouth_surprise",
        "shirt_row",
        "bib_row",
        "buttons_row",
    ]
    for field in row_fields:
        ensure_row(f"{style['id']}.{field}", style[field])

    eye_fields = [
        "eye_open_top",
        "eye_open_bottom",
        "eye_half_top",
        "eye_half_bottom",
        "eye_closed_top",
        "eye_closed_bottom",
    ]
    for field in eye_fields:
        ensure_eye(f"{style['id']}.{field}", style[field])


def make_eye_row(left_eye: str, right_eye: str) -> str:
    row = f".b{left_eye}s{right_eye}n.."
    ensure_row("eye_row", row)
    return row


def palette_for_style(style: dict[str, Any]) -> dict[str, Any]:
    palette = dict(PALETTE)
    for color_key, color_value in style["palette_overrides"].items():
        palette[color_key] = color_value
    return palette


def sprite_to_raw_with_palette(sprite_data: list[str], palette: dict[str, Any]) -> Image.Image:
    height = len(sprite_data)
    width = max(len(row) for row in sprite_data)
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    pixels = img.load()

    for y, row in enumerate(sprite_data):
        for x, char in enumerate(row):
            color = palette[char]
            if color:
                pixels[x, y] = color
    return img


def generate_sprite_image(sprite_data: list[str], palette: dict[str, Any], scale: int) -> Image.Image:
    raw = sprite_to_raw_with_palette(sprite_data, palette)
    outlined = add_outline(raw)
    shadowed = add_drop_shadow(outlined)
    return shadowed.resize((shadowed.width * scale, shadowed.height * scale), Image.NEAREST)


def apply_style(
    sprite_name: str,
    sprite_data: list[str],
    eye_index: int,
    eye_type: str,
    style: dict[str, Any],
) -> list[str]:
    rows = list(sprite_data)

    head_start = eye_index - 6
    if head_start >= 0 and (head_start + 3) < len(rows):
        rows[head_start] = style["hat_top"]
        rows[head_start + 1] = style["hat_brim"]
        rows[head_start + 2] = style["hat_shadow"]
        rows[head_start + 3] = style["hat_side"]

    if eye_type == "open":
        rows[eye_index] = make_eye_row(style["eye_open_top"], style["eye_open_top"])
        rows[eye_index + 1] = make_eye_row(style["eye_open_bottom"], style["eye_open_bottom"])
    elif eye_type == "half":
        rows[eye_index] = make_eye_row(style["eye_half_top"], style["eye_half_top"])
        rows[eye_index + 1] = make_eye_row(style["eye_half_bottom"], style["eye_half_bottom"])
    else:
        rows[eye_index] = make_eye_row(style["eye_closed_top"], style["eye_closed_top"])
        rows[eye_index + 1] = make_eye_row(style["eye_closed_bottom"], style["eye_closed_bottom"])

    if (eye_index + 2) < len(rows):
        rows[eye_index + 2] = style["nose_row"]
    if (eye_index + 3) < len(rows):
        rows[eye_index + 3] = style["mustache_row"]

    if (eye_index + 4) < len(rows):
        mouth_row = style["mouth_neutral"]
        if sprite_name == "talk":
            mouth_row = style["mouth_talk"]
        elif sprite_name == "laugh":
            mouth_row = style["mouth_laugh"]
        elif sprite_name == "surprise":
            mouth_row = style["mouth_surprise"]
        rows[eye_index + 4] = mouth_row

    if (eye_index + 5) < len(rows):
        rows[eye_index + 5] = style["shirt_row"]
    if (eye_index + 6) < len(rows):
        rows[eye_index + 6] = style["bib_row"]
    if (eye_index + 9) < len(rows):
        rows[eye_index + 9] = style["buttons_row"]

    for index, row in enumerate(rows):
        ensure_row(f"{style['id']}.{sprite_name}[{index}]", row)

    return rows


def write_iteration_notes(
    folder_path: str,
    style: dict[str, Any],
    iteration_number: int,
) -> None:
    notes_path = os.path.join(folder_path, "style_notes.txt")
    text = (
        f"Iteration {iteration_number:02d} - {style['id']}\n"
        f"{style['note']}\n\n"
        "Hand-crafted details included in every sprite:\n"
        "- Plumber hat rows rebuilt\n"
        "- Overalls and button rows rebuilt\n"
        "- Mustache row rebuilt\n"
        "- Large blue eye rows rebuilt\n"
    )
    with open(notes_path, "w", encoding="utf-8") as file:
        file.write(text)


def write_index(records: list[dict[str, str]]) -> None:
    cards = []
    for record in records:
        cards.append(
            f"""
<div class="card">
  <h2>{record['title']}</h2>
  <p>{record['note']}</p>
  <div class="previews">
    <img src="{record['folder']}/mario_idle.png" alt="{record['title']} idle">
    <img src="{record['folder']}/mario_talk.png" alt="{record['title']} talk">
    <img src="{record['folder']}/mario_surprise.png" alt="{record['title']} surprise">
  </div>
</div>
"""
        )

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Mario Boutique Iterations</title>
  <style>
    body {{
      margin: 0;
      font-family: Arial, sans-serif;
      background: #12131a;
      color: #e9ecf6;
      padding: 24px;
    }}
    h1 {{
      margin: 0 0 8px 0;
      color: #ff5a5a;
    }}
    .subtitle {{
      margin: 0 0 20px 0;
      color: #aeb7d0;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
      gap: 16px;
    }}
    .card {{
      background: #1b1f2e;
      border: 1px solid #2d3550;
      border-radius: 10px;
      padding: 14px;
    }}
    .card h2 {{
      margin: 0 0 8px 0;
      font-size: 18px;
      color: #8fd1ff;
    }}
    .card p {{
      margin: 0 0 10px 0;
      color: #c7cee3;
      min-height: 42px;
    }}
    .previews {{
      display: flex;
      gap: 8px;
      align-items: flex-end;
      flex-wrap: wrap;
    }}
    img {{
      image-rendering: pixelated;
      max-width: 96px;
      height: auto;
      background: #0b0e18;
      border-radius: 6px;
      padding: 2px;
      border: 1px solid #2d3550;
    }}
  </style>
</head>
<body>
  <h1>Mario Boutique Iterations</h1>
  <p class="subtitle">10 careful full-set reconstructions (hat, overalls, mustache, big blue eyes).</p>
  <div class="grid">
    {''.join(cards)}
  </div>
</body>
</html>
"""
    index_path = os.path.join(OUTPUT_DIR, "index.html")
    with open(index_path, "w", encoding="utf-8") as file:
        file.write(html)


def write_manifest(records: list[dict[str, str]]) -> None:
    manifest_path = os.path.join(OUTPUT_DIR, "manifest.txt")
    lines = [
        "Mario Boutique Iterations",
        f"Generated: {datetime.now(UTC).isoformat()}",
        "",
    ]
    for record in records:
        lines.append(f"{record['title']} -> {record['folder']}")
        lines.append(f"  {record['note']}")
    lines.append("")
    with open(manifest_path, "w", encoding="utf-8") as file:
        file.write("\n".join(lines))


def generate_all() -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    records: list[dict[str, str]] = []

    for iteration_number, style in enumerate(STYLES, start=1):
        validate_style(style)
        palette = palette_for_style(style)

        folder_name = f"iteration_{iteration_number:02d}_{style['id']}"
        folder_path = os.path.join(OUTPUT_DIR, folder_name)
        os.makedirs(folder_path, exist_ok=True)

        for sprite_name, (sprite_data, eye_index, eye_type) in SPRITE_TEMPLATES.items():
            styled = apply_style(sprite_name, sprite_data, eye_index, eye_type, style)
            image = generate_sprite_image(styled, palette, style["scale"])
            image.save(os.path.join(folder_path, f"mario_{sprite_name}.png"))

        talk_eye_index = SPRITE_TEMPLATES["talk"][1]
        styled_talk = apply_style("talk", SPRITE_TEMPLATES["talk"][0], talk_eye_index, "open", style)
        styled_talk[talk_eye_index + 4] = style["mouth_talk2"]
        image_talk2 = generate_sprite_image(styled_talk, palette, style["scale"])
        image_talk2.save(os.path.join(folder_path, "mario_talk2.png"))

        write_iteration_notes(folder_path, style, iteration_number)
        records.append(
            {
                "title": f"#{iteration_number:02d} {style['id']}",
                "folder": folder_name,
                "note": style["note"],
            }
        )
        print(f"Created {folder_name}")

    write_manifest(records)
    write_index(records)
    print(f"\nDone: {len(STYLES)} iteration folders written to {OUTPUT_DIR}")


if __name__ == "__main__":
    generate_all()
