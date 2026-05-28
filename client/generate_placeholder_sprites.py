"""Generate placeholder character sprites using Pillow.

Creates simple avatar-style sprites with the character's theme colors
when AI image generation APIs are unavailable. Each sprite shows a
stylized face with expression indicators and category-based coloring.
"""

import os
import sys
import math
import json
from PIL import Image, ImageDraw, ImageFont

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# Emotion-to-expression mapping: (mouth_type, eye_type, extras)
# mouth: smile, neutral, frown, open, grin, pout, gasp
# eyes: normal, happy, sad, wide, closed, wink, angry
EXPRESSIONS = {
    # Neutral
    "idle":         ("smile",   "normal",  None),
    "thinking":     ("neutral", "normal",  "thought_bubble"),
    # Positive
    "happy":        ("grin",    "happy",   None),
    "excited":      ("open",    "wide",    "sparkles"),
    "laughing":     ("open",    "happy",   None),
    "love":         ("smile",   "happy",   "hearts"),
    "proud":        ("smile",   "normal",  "star"),
    # Negative
    "sad":          ("frown",   "sad",     "tear"),
    "angry":        ("frown",   "angry",   None),
    "annoyed":      ("pout",    "angry",   None),
    "nervous":      ("neutral", "wide",    "sweat"),
    "scared":       ("gasp",    "wide",    "sweat"),
    "embarrassed":  ("neutral", "closed",  "blush"),
    "disgusted":    ("pout",    "normal",  None),
    "grossed_out":  ("gasp",    "wide",    None),
    # Thinking
    "confused":     ("neutral", "normal",  "question"),
    "curious":      ("smile",   "wide",    None),
    "determined":   ("neutral", "angry",   None),
    "mischievous":  ("grin",    "wink",    None),
    "shocked":      ("gasp",    "wide",    "exclaim"),
    "idea":         ("open",    "wide",    "lightbulb"),
    "surprised":    ("gasp",    "wide",    None),
    # Speech
    "talking":      ("open",    "normal",  None),
    "talking_excited": ("open", "happy",   None),
    "listening":    ("smile",   "normal",  None),
    # Greeting
    "wave":         ("grin",    "happy",   "wave_hand"),
    "farewell":     ("smile",   "sad",     "wave_hand"),
    # Reactions
    "mind_blown":   ("gasp",    "wide",    "explosion"),
    "sassy":        ("grin",    "wink",    None),
    "cringe":       ("pout",    "closed",  None),
    "impressed":    ("smile",   "wide",    "sparkles"),
    # Sleep
    "yawning":      ("open",    "closed",  None),
    "sleepy":       ("neutral", "closed",  "zzz"),
    "sleeping":     ("neutral", "closed",  "zzz"),
    # Movement
    "dancing":      ("grin",    "happy",   "music"),
    "entering":     ("grin",    "happy",   "wave_hand"),
    # Party
    "celebrate":    ("grin",    "happy",   "confetti"),
    "party_dance":  ("open",    "happy",   "music"),
}

# Category color tints (R, G, B base hue)
CATEGORY_COLORS = {
    "neutral":  (180, 160, 220),  # Soft lavender
    "positive": (255, 107, 157),  # Ani pink
    "negative": (120, 140, 200),  # Muted blue
    "thinking": (192, 132, 252),  # Ani purple
    "speech":   (220, 180, 240),  # Light purple
    "greeting": (252, 211, 77),   # Ani gold
    "reactions":(230, 150, 200),  # Rose
    "sleep":    (140, 160, 200),  # Dusky blue
    "movement": (200, 230, 180),  # Soft green
    "party":    (255, 200, 100),  # Warm gold
}


def draw_face(draw, cx, cy, radius, mouth_type, eye_type, extras, color):
    """Draw a stylized face with expression."""
    r, g, b = color

    # Head circle with gradient effect
    for i in range(radius, 0, -1):
        factor = 0.6 + 0.4 * (i / radius)
        c = (int(r * factor), int(g * factor), int(b * factor), 255)
        draw.ellipse([cx - i, cy - i, cx + i, cy + i], fill=c)

    # Inner highlight
    hr = int(radius * 0.85)
    highlight = (min(r + 40, 255), min(g + 40, 255), min(b + 40, 255), 200)
    draw.ellipse([cx - hr, cy - hr - 5, cx + hr, cy + hr - 5], fill=highlight)

    eye_y = cy - int(radius * 0.15)
    eye_x_off = int(radius * 0.25)
    eye_r = int(radius * 0.1)

    # Eyes
    for ex in [cx - eye_x_off, cx + eye_x_off]:
        if eye_type == "happy":
            # Upside-down arcs (happy squint)
            draw.arc([ex - eye_r, eye_y - eye_r, ex + eye_r, eye_y + eye_r],
                     200, 340, fill=(60, 60, 80), width=3)
        elif eye_type == "sad":
            draw.arc([ex - eye_r, eye_y - eye_r, ex + eye_r, eye_y + eye_r],
                     20, 160, fill=(60, 60, 80), width=3)
        elif eye_type == "wide":
            draw.ellipse([ex - eye_r, eye_y - eye_r - 2, ex + eye_r, eye_y + eye_r + 2],
                         fill=(60, 60, 80))
            draw.ellipse([ex - 3, eye_y - 3, ex + 3, eye_y + 3], fill=(255, 255, 255))
        elif eye_type == "closed":
            draw.line([ex - eye_r, eye_y, ex + eye_r, eye_y], fill=(60, 60, 80), width=3)
        elif eye_type == "angry":
            draw.ellipse([ex - eye_r + 1, eye_y - eye_r + 1, ex + eye_r - 1, eye_y + eye_r - 1],
                         fill=(60, 60, 80))
            # Angry brow
            if ex < cx:
                draw.line([ex - eye_r - 2, eye_y - eye_r - 4, ex + eye_r + 2, eye_y - eye_r],
                          fill=(60, 60, 80), width=3)
            else:
                draw.line([ex - eye_r - 2, eye_y - eye_r, ex + eye_r + 2, eye_y - eye_r - 4],
                          fill=(60, 60, 80), width=3)
        elif eye_type == "wink":
            if ex < cx:
                draw.ellipse([ex - eye_r, eye_y - eye_r, ex + eye_r, eye_y + eye_r],
                             fill=(60, 60, 80))
            else:
                draw.arc([ex - eye_r, eye_y - eye_r, ex + eye_r, eye_y + eye_r],
                         200, 340, fill=(60, 60, 80), width=3)
        else:  # normal
            draw.ellipse([ex - eye_r, eye_y - eye_r, ex + eye_r, eye_y + eye_r],
                         fill=(60, 60, 80))

    # Mouth
    mouth_y = cy + int(radius * 0.25)
    mouth_w = int(radius * 0.3)
    if mouth_type == "smile":
        draw.arc([cx - mouth_w, mouth_y - mouth_w // 2, cx + mouth_w, mouth_y + mouth_w // 2],
                 0, 180, fill=(60, 60, 80), width=3)
    elif mouth_type == "grin":
        draw.arc([cx - mouth_w, mouth_y - mouth_w // 2, cx + mouth_w, mouth_y + mouth_w // 2],
                 0, 180, fill=(60, 60, 80), width=3)
        draw.arc([cx - mouth_w + 2, mouth_y - mouth_w // 2 + 2,
                  cx + mouth_w - 2, mouth_y + mouth_w // 2 - 2],
                 0, 180, fill=(60, 60, 80), width=2)
    elif mouth_type == "frown":
        draw.arc([cx - mouth_w, mouth_y, cx + mouth_w, mouth_y + mouth_w],
                 180, 360, fill=(60, 60, 80), width=3)
    elif mouth_type == "open":
        draw.ellipse([cx - mouth_w // 2, mouth_y - 5, cx + mouth_w // 2, mouth_y + mouth_w // 2],
                     fill=(80, 50, 60))
    elif mouth_type == "gasp":
        draw.ellipse([cx - mouth_w // 3, mouth_y - 3, cx + mouth_w // 3, mouth_y + mouth_w // 3],
                     fill=(80, 50, 60))
    elif mouth_type == "pout":
        draw.arc([cx - mouth_w // 2, mouth_y, cx + mouth_w // 2, mouth_y + mouth_w // 2],
                 180, 360, fill=(60, 60, 80), width=3)
    else:  # neutral
        draw.line([cx - mouth_w // 2, mouth_y, cx + mouth_w // 2, mouth_y],
                  fill=(60, 60, 80), width=2)

    # Extras
    if extras == "hearts":
        for hx, hy in [(cx + radius - 15, cy - radius + 15), (cx - radius + 25, cy - radius + 10)]:
            draw.text((hx, hy), "♥", fill=(255, 80, 120))
    elif extras == "sparkles":
        for sx, sy in [(cx + radius - 10, cy - radius + 10), (cx - radius + 15, cy - radius + 20)]:
            draw.text((sx, sy), "✦", fill=(252, 211, 77))
    elif extras == "tear":
        tx = cx + eye_x_off + 3
        ty = eye_y + eye_r + 5
        draw.ellipse([tx - 3, ty, tx + 3, ty + 8], fill=(100, 150, 255, 200))
    elif extras == "sweat":
        sx = cx + eye_x_off + eye_r + 5
        sy = eye_y - 5
        draw.ellipse([sx - 2, sy, sx + 2, sy + 6], fill=(100, 150, 255, 200))
    elif extras == "blush":
        for bx in [cx - eye_x_off, cx + eye_x_off]:
            by = eye_y + eye_r + 10
            draw.ellipse([bx - 12, by - 4, bx + 12, by + 4], fill=(255, 120, 150, 100))
    elif extras == "zzz":
        draw.text((cx + radius - 20, cy - radius), "Z", fill=(100, 100, 200))
        draw.text((cx + radius - 5, cy - radius - 15), "z", fill=(120, 120, 210))
    elif extras == "music":
        draw.text((cx + radius - 15, cy - radius + 5), "♪", fill=(200, 100, 200))
    elif extras == "question":
        draw.text((cx + radius - 20, cy - radius), "?", fill=(180, 140, 220))
    elif extras == "exclaim":
        draw.text((cx + radius - 20, cy - radius), "!", fill=(255, 100, 100))
    elif extras == "lightbulb":
        draw.text((cx + radius - 20, cy - radius), "💡", fill=(252, 211, 77))
    elif extras == "thought_bubble":
        for i, (dx, dy, dr) in enumerate([(radius - 5, -radius + 10, 6), (radius + 5, -radius - 5, 4)]):
            draw.ellipse([cx + dx - dr, cy + dy - dr, cx + dx + dr, cy + dy + dr],
                         fill=(230, 230, 240, 180))
    elif extras == "wave_hand":
        hx = cx + radius + 10
        hy = cy - 20
        draw.ellipse([hx - 10, hy - 12, hx + 10, hy + 12],
                     fill=(min(r + 30, 255), min(g + 30, 255), min(b + 20, 255)))
    elif extras == "star":
        draw.text((cx + radius - 15, cy - radius + 5), "★", fill=(252, 211, 77))
    elif extras == "confetti":
        import random
        rng = random.Random(42)
        for _ in range(6):
            px = cx + rng.randint(-radius, radius)
            py = cy + rng.randint(-radius, -radius // 2)
            pc = rng.choice([(255, 107, 157), (192, 132, 252), (252, 211, 77), (100, 200, 255)])
            draw.rectangle([px - 3, py - 3, px + 3, py + 3], fill=pc)
    elif extras == "explosion":
        for angle in range(0, 360, 45):
            rad = math.radians(angle)
            x1 = cx + int(radius * 0.8 * math.cos(rad))
            y1 = cy + int(radius * 0.8 * math.sin(rad))
            x2 = cx + int(radius * 1.1 * math.cos(rad))
            y2 = cy + int(radius * 1.1 * math.sin(rad))
            draw.line([x1, y1, x2, y2], fill=(252, 211, 77), width=2)


def generate_placeholder_sprite(pose_name, category, size=512):
    """Generate a single placeholder sprite."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img, "RGBA")

    color = CATEGORY_COLORS.get(category, (180, 160, 220))
    cx, cy = size // 2, size // 2
    radius = int(size * 0.35)

    expr = EXPRESSIONS.get(pose_name, ("smile", "normal", None))
    mouth_type, eye_type, extras = expr

    draw_face(draw, cx, cy, radius, mouth_type, eye_type, extras, color)

    # Label at bottom
    try:
        font = ImageFont.truetype("arial.ttf", 16)
    except OSError:
        font = ImageFont.load_default()
    label = pose_name.replace("_", " ").title()
    bbox = draw.textbbox((0, 0), label, font=font)
    tw = bbox[2] - bbox[0]
    draw.text((cx - tw // 2, size - 40), label, fill=(80, 80, 100, 200), font=font)

    return img


def generate_character_placeholders(character_name):
    """Generate all placeholder sprites for a character."""
    # Load character poses from generate_character_poses.py
    sys.path.insert(0, os.path.join(PROJECT_ROOT, "client"))
    from generate_character_poses import CHARACTER_POSES

    if character_name not in CHARACTER_POSES:
        print(f"Unknown character: {character_name}")
        print(f"Available: {list(CHARACTER_POSES.keys())}")
        return

    poses = CHARACTER_POSES[character_name]
    sprite_dir = os.path.join(PROJECT_ROOT, "characters", character_name, "sprites")
    total = 0
    skipped = 0

    for category, pose_list in poses.items():
        cat_dir = os.path.join(sprite_dir, category)
        os.makedirs(cat_dir, exist_ok=True)

        print(f"\n  {category.upper()} ({len(pose_list)} poses)")
        for pose_id, _ in pose_list:
            out_path = os.path.join(cat_dir, f"{pose_id}.png")

            if os.path.exists(out_path) and os.path.getsize(out_path) > 1000:
                print(f"    {pose_id} — SKIPPED (exists)")
                skipped += 1
                continue

            img = generate_placeholder_sprite(pose_id, category)
            img.save(out_path, "PNG")
            print(f"    {pose_id} — OK ✓")
            total += 1

    print(f"\n{'=' * 50}")
    print(f"  {character_name.upper()} PLACEHOLDERS COMPLETE")
    print(f"  Generated: {total}  Skipped: {skipped}")
    print(f"  Sprites: {sprite_dir}")
    print(f"{'=' * 50}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate placeholder character sprites")
    parser.add_argument("--character", "-c", required=True, help="Character name")
    parser.add_argument("--force", action="store_true", help="Overwrite existing sprites")
    args = parser.parse_args()

    if args.force:
        # Remove existing sprites to regenerate
        sprite_dir = os.path.join(PROJECT_ROOT, "characters", args.character, "sprites")
        if os.path.exists(sprite_dir):
            import shutil
            shutil.rmtree(sprite_dir)
            print(f"Removed existing sprites: {sprite_dir}")

    generate_character_placeholders(args.character)
