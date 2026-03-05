"""Generate 100 Mario sprite variant folders with different eye/style designs.

Run from client/ directory:
    python generate_variants.py

Output: client/assets/variants/001_name/ through 100_name/
Preview: Open client/assets/variants/index.html in a browser to browse all variants.
"""

import os
import sys
import time
import base64
from io import BytesIO
from PIL import Image

# Reuse the pipeline from generate_sprites
from generate_sprites import (
    PALETTE, SCALE, sprite_to_raw, add_outline, add_drop_shadow,
    SPRITE_IDLE, SPRITE_TALK, SPRITE_WALK1, SPRITE_WALK2,
    SPRITE_WAVE, SPRITE_JUMP, SPRITE_THINK, SPRITE_LAUGH,
    SPRITE_SURPRISE, SPRITE_SLEEP, SPRITE_DANCE,
)

VARIANTS_DIR = os.path.join(os.path.dirname(__file__), "assets", "variants")

# ==========================================
# SPRITE TEMPLATES (with placeholder eye rows)
# ==========================================

# Each sprite: (data, eye_row_start_index, eye_type)
# eye_type: "open" | "half" | "closed"
SPRITE_TEMPLATES = {
    "idle":     (SPRITE_IDLE,     6, "open"),
    "talk":     (SPRITE_TALK,     6, "open"),
    "walk1":    (SPRITE_WALK1,    6, "open"),
    "walk2":    (SPRITE_WALK2,    6, "open"),
    "wave":     (SPRITE_WAVE,     6, "open"),
    "jump":     (SPRITE_JUMP,     6, "open"),
    "think":    (SPRITE_THINK,    6, "half"),
    "laugh":    (SPRITE_LAUGH,    6, "closed"),
    "surprise": (SPRITE_SURPRISE, 6, "open"),
    "sleep":    (SPRITE_SLEEP,    9, "closed"),
    "dance":    (SPRITE_DANCE,    6, "open"),
}

# ==========================================
# EYE PATTERN HELPERS
# ==========================================

def make_eye_row(left5, right5):
    """Build a 16-char row: .b{left}s{right}n.."""
    return f".b{left5}s{right5}n.."


def derive_half(top, bot):
    """Half-closed: lids (dark skin) on top, pupils peeking below."""
    ht = top.replace('w', 'n').replace('k', 'n').replace('u', 'n').replace('i', 'n')
    return ht, bot


def derive_closed(top, bot):
    """Closed: dark skin lids on top, all skin below."""
    ct = top.replace('w', 'n').replace('k', 'n').replace('u', 'n').replace('i', 'n')
    cb = bot.replace('w', 's').replace('k', 's').replace('u', 's').replace('i', 's')
    return ct, cb


def apply_eyes(sprite_data, eye_idx, top5, bot5, eye_type):
    """Replace eye rows in a sprite copy with the given pattern."""
    result = list(sprite_data)

    if eye_type == "open":
        t, b = top5, bot5
    elif eye_type == "half":
        t, b = derive_half(top5, bot5)
    elif eye_type == "closed":
        t, b = derive_closed(top5, bot5)
    else:
        t, b = top5, bot5

    result[eye_idx] = make_eye_row(t, t)
    result[eye_idx + 1] = make_eye_row(b, b)
    return result


def generate_sprite_img(sprite_data):
    """Full pipeline: raw → outline → shadow → scale."""
    raw = sprite_to_raw(sprite_data)
    outlined = add_outline(raw)
    shadowed = add_drop_shadow(outlined)
    return shadowed.resize(
        (shadowed.width * SCALE, shadowed.height * SCALE),
        Image.NEAREST,
    )


# ==========================================
# DEFINE 100 EYE VARIANTS
# ==========================================
# Each: (name, top_5chars, bot_5chars)
# Both eyes use the same pattern (symmetric).

VARIANTS = []


def V(name, top, bot):
    """Register a variant. Validates 5-char patterns."""
    assert len(top) == 5, f"{name} top len={len(top)}: '{top}'"
    assert len(bot) == 5, f"{name} bot len={len(bot)}: '{bot}'"
    VARIANTS.append((name, top, bot))


# ===== 1-15: RECTANGULAR EYES, full pupil/position sweep =====
# Pupil width 1 (5 positions)
V("rect_pw1_left",     "wwwww", "kwwww")
V("rect_pw1_mleft",    "wwwww", "wkwww")
V("rect_pw1_center",   "wwwww", "wwkww")
V("rect_pw1_mright",   "wwwww", "wwwkw")
V("rect_pw1_right",    "wwwww", "wwwwk")
# Pupil width 2 (4 positions)
V("rect_pw2_left",     "wwwww", "kkwww")
V("rect_pw2_mleft",    "wwwww", "wkkww")
V("rect_pw2_center",   "wwwww", "wwkkw")
V("rect_pw2_right",    "wwwww", "wwwkk")
# Pupil width 3 (3 positions)
V("rect_pw3_left",     "wwwww", "kkkww")
V("rect_pw3_center",   "wwwww", "wkkkw")
V("rect_pw3_right",    "wwwww", "wwkkk")
# Pupil width 4-5
V("rect_pw4_left",     "wwwww", "kkkkw")
V("rect_pw4_right",    "wwwww", "wkkkk")
V("rect_pw5_full",     "wwwww", "kkkkk")

# ===== 16-21: ROUNDED EYES (skin corners) =====
V("round_pw1_left",    "swwws", "skwws")
V("round_pw1_center",  "swwws", "swkws")
V("round_pw1_right",   "swwws", "swwks")
V("round_pw2_left",    "swwws", "skkws")
V("round_pw2_right",   "swwws", "swkks")
V("round_pw3_full",    "swwws", "skkks")

# ===== 22-27: HEAVY EYELID (dark skin top row) =====
V("lid_pw1",           "nnnnn", "wwkww")
V("lid_pw2",           "nnnnn", "wkkww")
V("lid_pw3",           "nnnnn", "wkkkw")
V("lid_pw4",           "nnnnn", "kkkkw")
V("lid_round_pw1",     "snnns", "swkws")
V("lid_round_pw3",     "snnns", "skkks")

# ===== 28-30: DARK-CORNERED ROUNDED =====
V("dcorner_pw1",       "nwwwn", "nwkwn")
V("dcorner_pw2",       "nwwwn", "nwkkn")
V("dcorner_pw3",       "nwwwn", "nkkkn")

# ===== 31-36: TALL PUPILS (span both rows) =====
V("tall_pw1",          "wwkww", "wwkww")
V("tall_pw2",          "wkkww", "wkkww")
V("tall_pw3",          "wkkkw", "wkkkw")
V("tall_round_pw1",    "swkws", "swkws")
V("tall_round_pw2",    "swkks", "swkks")
V("tall_round_pw3",    "skkks", "skkks")

# ===== 37-39: LOOKING UP (pupil in top row only) =====
V("lookup_pw1",        "wwkww", "wwwww")
V("lookup_pw2",        "wkkww", "wwwww")
V("lookup_pw3",        "wkkkw", "wwwww")

# ===== 40-47: SHINE / HIGHLIGHT =====
V("shine_topright",    "wwwww", "wkwkw")
V("shine_topleft",     "wwwww", "kwkwk")
V("shine_corner_tr",   "wwwwk", "wkkkk")
V("shine_corner_tl",   "kwwww", "kkkkw")
V("shine_2dot",        "kwwwk", "kkwkk")
V("shine_center",      "wkkkw", "wkwkw")
V("shine_big_core",    "kwwwk", "kwwwk")
V("shine_inv",         "kkwkk", "kkkkk")

# ===== 48-55: BLUE IRIS =====
V("iris_ring",         "wuuuw", "ukuku")
V("iris_fill",         "uuuuu", "uukuu")
V("iris_in_white",     "wwwww", "wukuw")
V("iris_tall",         "wukuw", "wukuw")
V("iris_round",        "suwus", "sukus")
V("iris_lid",          "nnnnn", "wukuw")
V("iris_shine",        "wuuuw", "ukwku")
V("iris_deep",         "uuuuu", "uukuu")

# ===== 56-62: MINIMALIST =====
V("mini_dot",          "sssss", "sskss")
V("mini_tall_dot",     "sskss", "sskss")
V("mini_dash2",        "sssss", "skkss")
V("mini_dash3",        "sssss", "skkks")
V("mini_bar",          "sssss", "kkkkk")
V("mini_tall_bar",     "skkks", "skkks")
V("mini_block",        "kkkkk", "kkkkk")

# ===== 63-70: CHIBI / CUTE (dark eyes, small shine) =====
V("chibi_dot_br",      "kkkkk", "kkwkk")
V("chibi_dot_bl",      "kkkkk", "kwkkk")
V("chibi_2dot",        "kkkkk", "kwwkk")
V("chibi_top_dot",     "kkwkk", "kkkkk")
V("chibi_half_bw",     "wwkkk", "wwkkk")
V("chibi_half_wb",     "kkkww", "kkkww")
V("chibi_core",        "kwwwk", "kkkkk")
V("chibi_glow",        "kwwwk", "kwwwk")

# ===== 71-75: GRADIENT / COLORED =====
V("grad_blue_center",  "wwwww", "wiiiw")
V("grad_blue_tall",    "wiiiw", "wiiiw")
V("grad_blue_sides",   "wwwww", "iwwwi")
V("grad_blue_ring",    "iwiui", "iwkwi")
V("grad_dblue_core",   "wiiuw", "ikuki")

# ===== 76-85: UNIQUE / ARTISTIC =====
V("art_checker",       "wkwkw", "kwkwk")
V("art_diamond",       "wwkww", "wkwkw")
V("art_triangle",      "wwkww", "wkkkw")
V("art_invtri",        "wkkkw", "wwkww")
V("art_hourglass",     "kwwwk", "wkkkw")
V("art_bowtie",        "wkkkw", "kwwwk")
V("art_target",        "wkwkw", "kwwwk")
V("art_zigzag",        "kwkwk", "wkwkw")
V("art_frame",         "kwwwk", "kswsk")
V("art_cross",         "wwkww", "kkkkk")

# ===== 86-93: EXPRESSIONS =====
V("expr_sad",          "nwwwn", "nkkkn")
V("expr_angry",        "nnwnn", "wkkkw")
V("expr_bored",        "nnnnn", "nwkwn")
V("expr_happy_sq",     "swwws", "sssss")
V("expr_determined",   "nwwwn", "wkkkw")
V("expr_slit",         "nnnnn", "nkkkn")
V("expr_void",         "nnnnn", "nnnnn")
V("expr_laser",        "wwwww", "rkkkr")

# ===== 94-100: SPECIAL =====
V("spc_nopupil",       "wwwww", "wwwww")
V("spc_allskin",       "sssss", "sssss")
V("spc_thin_line",     "sssss", "skwks")
V("spc_double_dot",    "skwks", "skwks")
V("spc_pixel_pair",    "sksks", "sksks")
V("spc_bold_round",    "nwwwn", "nwkwn")
V("spc_anime_big",     "wwwww", "wkwkw")


# ==========================================
# GENERATION
# ==========================================

def generate_variant_folder(idx, name, top5, bot5):
    """Generate all 12 sprites for one variant and save to a folder."""
    folder_name = f"{idx:03d}_{name}"
    folder_path = os.path.join(VARIANTS_DIR, folder_name)
    os.makedirs(folder_path, exist_ok=True)

    for sprite_name, (sprite_data, eye_idx, eye_type) in SPRITE_TEMPLATES.items():
        modified = apply_eyes(sprite_data, eye_idx, top5, bot5, eye_type)
        img = generate_sprite_img(modified)
        img.save(os.path.join(folder_path, f"mario_{sprite_name}.png"))

    # Also generate talk2
    talk_data, talk_idx, _ = SPRITE_TEMPLATES["talk"]
    talk2_data = apply_eyes(talk_data, talk_idx, top5, bot5, "open")
    talk2_data[10] = "...snrrrrrnsss.."
    img = generate_sprite_img(talk2_data)
    img.save(os.path.join(folder_path, "mario_talk2.png"))


def img_to_base64(img_path):
    """Read a PNG and return a data URI for embedding in HTML."""
    with open(img_path, "rb") as f:
        data = base64.b64encode(f.read()).decode("ascii")
    return f"data:image/png;base64,{data}"


def generate_preview_html():
    """Create an HTML page to browse all variants."""
    html_parts = ["""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Mario Sprite Variants — Pick Your Favorite!</title>
<style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
        background: #1a1a2e;
        color: #eee;
        font-family: 'Segoe UI', Arial, sans-serif;
        padding: 20px;
    }
    h1 {
        text-align: center;
        color: #e94560;
        margin-bottom: 10px;
        font-size: 2.5em;
    }
    .subtitle {
        text-align: center;
        color: #888;
        margin-bottom: 30px;
        font-size: 1.1em;
    }
    .grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
        gap: 16px;
        max-width: 1800px;
        margin: 0 auto;
    }
    .card {
        background: #16213e;
        border: 2px solid #0f3460;
        border-radius: 12px;
        padding: 12px;
        text-align: center;
        transition: transform 0.2s, border-color 0.2s;
        cursor: pointer;
    }
    .card:hover {
        transform: scale(1.05);
        border-color: #e94560;
    }
    .card .num {
        font-size: 1.4em;
        font-weight: bold;
        color: #e94560;
    }
    .card .name {
        font-size: 0.8em;
        color: #aaa;
        margin-bottom: 8px;
        word-break: break-all;
    }
    .card .sprites {
        display: flex;
        justify-content: center;
        gap: 4px;
        align-items: flex-end;
    }
    .card .sprites img.main {
        width: 80px;
        height: auto;
        image-rendering: pixelated;
    }
    .card .sprites img.small {
        width: 40px;
        height: auto;
        image-rendering: pixelated;
        opacity: 0.8;
    }
    .category {
        grid-column: 1 / -1;
        background: #0f3460;
        color: #e94560;
        padding: 10px 20px;
        border-radius: 8px;
        font-size: 1.3em;
        font-weight: bold;
        margin-top: 10px;
    }
</style>
</head>
<body>
<h1>🍄 Mario Sprite Variants 🍄</h1>
<p class="subtitle">100 different eye styles — click a card to open the folder with all 12 sprites</p>
<div class="grid">
"""]

    categories = {
        1: "📐 Rectangular Eyes — Pupil Size & Position Sweep",
        16: "⭕ Rounded Eyes — Skin Corners",
        22: "😑 Heavy Eyelid — Dark Top Row",
        28: "🔲 Dark-Cornered Rounded",
        31: "📏 Tall Pupils — Spanning Both Rows",
        37: "👆 Looking Up — Pupils In Top Row",
        40: "✨ Shine / Highlight Effects",
        48: "💎 Blue Iris — Colored Ring",
        56: "➖ Minimalist — Dots & Lines",
        63: "🥺 Chibi / Cute — Big Dark Eyes",
        71: "🌈 Gradient / Colored",
        76: "🎨 Unique / Artistic Patterns",
        86: "😤 Expressions — Mood Variants",
        94: "🌟 Special / Experimental",
    }

    for i, (name, top5, bot5) in enumerate(VARIANTS, 1):
        folder_name = f"{i:03d}_{name}"
        folder_path = os.path.join(VARIANTS_DIR, folder_name)

        if i in categories:
            html_parts.append(f'<div class="category">{categories[i]}</div>\n')

        idle_path = os.path.join(folder_path, "mario_idle.png")
        talk_path = os.path.join(folder_path, "mario_talk.png")
        think_path = os.path.join(folder_path, "mario_think.png")
        laugh_path = os.path.join(folder_path, "mario_laugh.png")

        idle_src = img_to_base64(idle_path) if os.path.exists(idle_path) else ""
        talk_src = img_to_base64(talk_path) if os.path.exists(talk_path) else ""
        think_src = img_to_base64(think_path) if os.path.exists(think_path) else ""
        laugh_src = img_to_base64(laugh_path) if os.path.exists(laugh_path) else ""

        html_parts.append(f'''<div class="card" onclick="window.open('{folder_name}/', '_blank')">
    <div class="num">#{i}</div>
    <div class="name">{name}</div>
    <div class="sprites">
        <img class="small" src="{think_src}" title="think">
        <img class="main" src="{idle_src}" title="idle">
        <img class="small" src="{talk_src}" title="talk">
    </div>
</div>
''')

    html_parts.append("""</div>
</body>
</html>""")

    html_path = os.path.join(VARIANTS_DIR, "index.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write("".join(html_parts))
    print(f"\nPreview page: {html_path}")


# ==========================================
# MAIN
# ==========================================

def main():
    os.makedirs(VARIANTS_DIR, exist_ok=True)

    total = len(VARIANTS)
    print(f"Generating {total} variant folders ({total * 12} sprites)...")
    print(f"Output: {VARIANTS_DIR}\n")

    start = time.time()

    for i, (name, top5, bot5) in enumerate(VARIANTS, 1):
        generate_variant_folder(i, name, top5, bot5)
        pct = i * 100 // total
        elapsed = time.time() - start
        eta = (elapsed / i) * (total - i) if i > 0 else 0
        sys.stdout.write(f"\r  [{pct:3d}%] {i}/{total} — {name:<25s} (ETA: {eta:.0f}s)")
        sys.stdout.flush()

    elapsed = time.time() - start
    print(f"\n\nDone! Generated {total * 12} sprites in {elapsed:.1f}s")

    print("Building HTML preview...")
    generate_preview_html()
    print("All done! Open index.html in a browser to browse variants.")


if __name__ == "__main__":
    main()
