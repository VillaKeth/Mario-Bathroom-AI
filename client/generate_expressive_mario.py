#!/usr/bin/env python3
"""
generate_expressive_mario.py
============================
Takes the Mario_New_Super_Mario_Bros_U_Deluxe.webp image and
actually EDITS it to create different poses, expressions, and actions.

This is NOT just color filters — it crops, moves, overlays, and composites
to create genuinely different visual states for Mario.

Output: mario_3d_assets/expressive/
"""

import os
import sys
import math
import random
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance, ImageOps, ImageFont
import numpy as np

random.seed(42)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIR = PROJECT_ROOT / "mario_assets"
OUTPUT_DIR = PROJECT_ROOT / "mario_3d_assets" / "expressive"

PRIMARY_BASE = SOURCE_DIR / "Mario_New_Super_Mario_Bros_U_Deluxe.webp"
THINKING_REF = SOURCE_DIR / "zap9gpu6vj9e1.png"

TARGET_W, TARGET_H = 400, 500


def remove_background_smart(img, tolerance=30):
    """Remove background by sampling corners."""
    arr = np.array(img)
    h, w = arr.shape[:2]
    corners = [arr[0, 0, :3], arr[0, w-1, :3], arr[h-1, 0, :3], arr[h-1, w-1, :3]]
    bg_color = np.mean(corners, axis=0).astype(np.uint8)
    diff = np.abs(arr[:, :, :3].astype(int) - bg_color.astype(int))
    mask = np.all(diff < tolerance, axis=2)
    arr[mask, 3] = 0
    return Image.fromarray(arr)


def crop_to_content(img, padding=5):
    """Crop to non-transparent content."""
    bbox = img.getbbox()
    if bbox is None:
        return img
    x0, y0, x1, y1 = bbox
    x0 = max(0, x0 - padding)
    y0 = max(0, y0 - padding)
    x1 = min(img.width, x1 + padding)
    y1 = min(img.height, y1 + padding)
    return img.crop((x0, y0, x1, y1))


def fit_to_canvas(img, w=TARGET_W, h=TARGET_H, y_offset=0):
    """Fit image to canvas, centered, with optional vertical offset."""
    iw, ih = img.size
    scale = min(w / iw, h / ih) * 0.9  # 90% to leave room
    new_w = int(iw * scale)
    new_h = int(ih * scale)
    resized = img.resize((new_w, new_h), Image.LANCZOS)
    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ox = (w - new_w) // 2
    oy = (h - new_h) // 2 + y_offset
    canvas.paste(resized, (ox, oy), resized)
    return canvas


def prepare_base(img_path):
    """Load and prepare the base Mario image."""
    img = Image.open(img_path).convert("RGBA")
    cleaned = remove_background_smart(img)
    cropped = crop_to_content(cleaned)
    return cropped


def get_face_region(img):
    """Estimate face region coordinates. Returns (x, y, w, h) of face area."""
    iw, ih = img.size
    # Mario's face is roughly in the upper-center portion
    fx = int(iw * 0.25)
    fy = int(ih * 0.18)
    fw = int(iw * 0.50)
    fh = int(ih * 0.22)
    return (fx, fy, fw, fh)


def get_eye_region(img):
    """Estimate eye region within the image."""
    iw, ih = img.size
    ex = int(iw * 0.30)
    ey = int(ih * 0.26)
    ew = int(iw * 0.40)
    eh = int(ih * 0.08)
    return (ex, ey, ew, eh)


def get_mouth_region(img):
    """Estimate mouth region."""
    iw, ih = img.size
    mx = int(iw * 0.35)
    my = int(ih * 0.35)
    mw = int(iw * 0.30)
    mh = int(ih * 0.06)
    return (mx, my, mw, mh)


def draw_text_overlay(draw, text, x, y, size=20, color=(255, 255, 255)):
    """Draw text at position with outline for readability."""
    try:
        font = ImageFont.truetype("arial.ttf", size)
    except (OSError, IOError):
        font = ImageFont.load_default()
    # Outline
    for dx in [-2, -1, 0, 1, 2]:
        for dy in [-2, -1, 0, 1, 2]:
            draw.text((x + dx, y + dy), text, fill=(0, 0, 0), font=font)
    draw.text((x, y), text, fill=color, font=font)


def draw_thought_bubble(draw, x, y, w, h, text=""):
    """Draw a thought cloud bubble."""
    # Main bubble (ellipse)
    draw.ellipse([x, y, x + w, y + h], fill=(255, 255, 255, 220), outline=(100, 100, 100, 200), width=2)
    # Trail dots leading to head
    for i, (r, ox, oy) in enumerate([(6, 15, h + 10), (4, 10, h + 20), (3, 8, h + 28)]):
        draw.ellipse([x + ox - r, y + oy - r, x + ox + r, y + oy + r],
                     fill=(255, 255, 255, 200), outline=(100, 100, 100, 180))
    if text:
        try:
            font = ImageFont.truetype("arial.ttf", 14)
        except (OSError, IOError):
            font = ImageFont.load_default()
        draw.text((x + 10, y + h // 3), text, fill=(50, 50, 50), font=font)


def draw_speech_bubble(draw, x, y, w, h, text="", shout=False):
    """Draw a speech bubble with tail."""
    if shout:
        # Spiky bubble for shouting
        points = []
        cx, cy = x + w // 2, y + h // 2
        num_spikes = 16
        for i in range(num_spikes * 2):
            angle = (i / (num_spikes * 2)) * 2 * math.pi
            r = (w // 2 + 8) if i % 2 == 0 else (w // 2 - 5)
            px = cx + int(r * math.cos(angle))
            py = cy + int(r * 0.6 * math.sin(angle))
            points.append((px, py))
        draw.polygon(points, fill=(255, 255, 255, 230), outline=(200, 50, 50, 255))
    else:
        draw.rounded_rectangle([x, y, x + w, y + h], radius=15,
                               fill=(255, 255, 255, 220), outline=(80, 80, 80, 200), width=2)
    # Tail pointing down
    tail_x = x + w // 3
    draw.polygon([(tail_x, y + h - 2), (tail_x + 15, y + h - 2), (tail_x - 5, y + h + 20)],
                 fill=(255, 255, 255, 220))
    if text:
        try:
            font = ImageFont.truetype("arial.ttf", 13)
        except (OSError, IOError):
            font = ImageFont.load_default()
        draw.text((x + 12, y + h // 3), text, fill=(30, 30, 30), font=font)


def draw_zzz(draw, x, y, count=3):
    """Draw floating Zzz for sleep."""
    for i in range(count):
        size = 18 + i * 6
        px = x + i * 25
        py = y - i * 30
        try:
            font = ImageFont.truetype("arial.ttf", size)
        except (OSError, IOError):
            font = ImageFont.load_default()
        draw.text((px + 1, py + 1), "Z", fill=(0, 0, 80, 150), font=font)
        draw.text((px, py), "Z", fill=(100, 100, 255, 220), font=font)


def draw_music_notes(draw, x, y, count=4):
    """Draw floating music notes."""
    notes = ["♪", "♫", "♩", "♬"]
    colors = [(255, 100, 100), (100, 255, 100), (100, 100, 255), (255, 255, 100)]
    for i in range(count):
        px = x + i * 30 + random.randint(-5, 5)
        py = y - i * 20 + random.randint(-10, 10)
        try:
            font = ImageFont.truetype("arial.ttf", 20)
        except (OSError, IOError):
            font = ImageFont.load_default()
        draw.text((px, py), notes[i % len(notes)], fill=colors[i % len(colors)], font=font)


def draw_hearts(draw, x, y, count=3):
    """Draw floating hearts."""
    for i in range(count):
        px = x + i * 25 + random.randint(-5, 5)
        py = y - i * 25 + random.randint(-10, 5)
        size = 12 + random.randint(0, 6)
        # Simple heart shape with two circles and a triangle
        draw.ellipse([px, py, px + size, py + size], fill=(255, 50, 80, 200))
        draw.ellipse([px + size - 2, py, px + size * 2 - 2, py + size], fill=(255, 50, 80, 200))
        draw.polygon([(px, py + size // 2), (px + size, py + size + size // 2), (px + size * 2 - 2, py + size // 2)],
                     fill=(255, 50, 80, 200))


def draw_sweat_drops(draw, x, y, count=3):
    """Draw sweat/stress drops."""
    for i in range(count):
        px = x + i * 15 + random.randint(-3, 3)
        py = y + i * 8 + random.randint(-2, 2)
        # Teardrop shape
        draw.ellipse([px, py + 4, px + 8, py + 12], fill=(100, 180, 255, 200))
        draw.polygon([(px + 4, py), (px, py + 6), (px + 8, py + 6)], fill=(100, 180, 255, 200))


def draw_anger_veins(draw, x, y, count=2):
    """Draw anger vein marks (cross pattern)."""
    for i in range(count):
        px = x + i * 35
        py = y + (i * 10)
        s = 14
        draw.line([(px, py), (px + s, py + s)], fill=(220, 40, 40, 230), width=3)
        draw.line([(px + s, py), (px, py + s)], fill=(220, 40, 40, 230), width=3)
        draw.line([(px + s // 2, py), (px + s // 2, py + s)], fill=(220, 40, 40, 230), width=3)
        draw.line([(px, py + s // 2), (px + s, py + s // 2)], fill=(220, 40, 40, 230), width=3)


def draw_stars(draw, x, y, count=5):
    """Draw sparkle stars."""
    for i in range(count):
        px = x + random.randint(-40, 60)
        py = y + random.randint(-40, 20)
        size = random.randint(4, 10)
        color = random.choice([(255, 255, 100), (255, 200, 50), (255, 255, 200)])
        # 4-point star
        draw.polygon([(px, py - size), (px + 3, py - 3), (px + size, py), (px + 3, py + 3),
                       (px, py + size), (px - 3, py + 3), (px - size, py), (px - 3, py - 3)],
                     fill=(*color, 220))


def draw_exclamation(draw, x, y, color=(255, 50, 50)):
    """Draw a big exclamation mark."""
    try:
        font = ImageFont.truetype("arial.ttf", 40)
    except (OSError, IOError):
        font = ImageFont.load_default()
    draw.text((x + 2, y + 2), "!", fill=(0, 0, 0, 180), font=font)
    draw.text((x, y), "!", fill=(*color, 255), font=font)


def draw_question_mark(draw, x, y, color=(100, 100, 255)):
    """Draw a big question mark."""
    try:
        font = ImageFont.truetype("arial.ttf", 36)
    except (OSError, IOError):
        font = ImageFont.load_default()
    draw.text((x + 2, y + 2), "?", fill=(0, 0, 0, 180), font=font)
    draw.text((x, y), "?", fill=(*color, 255), font=font)


def draw_motion_lines(draw, x, y, direction="right", count=6):
    """Draw speed/motion lines."""
    for i in range(count):
        ly = y + i * 12
        length = random.randint(20, 50)
        if direction == "right":
            draw.line([(x - length, ly), (x, ly)], fill=(200, 200, 200, 150), width=2)
        elif direction == "left":
            draw.line([(x, ly), (x + length, ly)], fill=(200, 200, 200, 150), width=2)
        elif direction == "up":
            lx = x + i * 12
            draw.line([(lx, y + length), (lx, y)], fill=(200, 200, 200, 150), width=2)


def draw_tears(draw, x, y, side="both"):
    """Draw tears streaming down."""
    for i in range(4):
        dy = i * 8
        if side in ("left", "both"):
            draw.ellipse([x - 4, y + dy, x + 4, y + dy + 6], fill=(80, 150, 255, 180))
        if side in ("right", "both"):
            draw.ellipse([x + 30 - 4, y + dy, x + 30 + 4, y + dy + 6], fill=(80, 150, 255, 180))


def draw_blush(draw, x, y, w=25, h=12):
    """Draw blush marks on cheeks."""
    # Left cheek
    draw.ellipse([x, y, x + w, y + h], fill=(255, 120, 120, 100))
    # Right cheek
    draw.ellipse([x + w + 15, y, x + w * 2 + 15, y + h], fill=(255, 120, 120, 100))


def tint_region(img, region, color, intensity=0.3):
    """Apply a color tint to a region of the image."""
    arr = np.array(img).astype(float)
    x, y, w, h = region
    for c in range(3):
        arr[y:y+h, x:x+w, c] = arr[y:y+h, x:x+w, c] * (1 - intensity) + color[c] * intensity
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def close_eyes(img, eye_region):
    """Close eyes by drawing horizontal lines over them."""
    result = img.copy()
    draw = ImageDraw.Draw(result)
    ex, ey, ew, eh = eye_region
    cy = ey + eh // 2
    # Left eye — horizontal line
    draw.line([(ex + 2, cy), (ex + ew // 2 - 5, cy)], fill=(30, 30, 30, 200), width=3)
    # Right eye
    draw.line([(ex + ew // 2 + 5, cy), (ex + ew - 2, cy)], fill=(30, 30, 30, 200), width=3)
    return result


def wide_eyes(img, eye_region):
    """Make eyes wider (surprise) by adding white highlight."""
    result = img.copy()
    draw = ImageDraw.Draw(result)
    ex, ey, ew, eh = eye_region
    # Add white circles around eyes
    r = eh
    cx1, cx2 = ex + ew // 4, ex + 3 * ew // 4
    cy = ey + eh // 2
    draw.ellipse([cx1 - r, cy - r, cx1 + r, cy + r], outline=(255, 255, 255, 180), width=2)
    draw.ellipse([cx2 - r, cy - r, cx2 + r, cy + r], outline=(255, 255, 255, 180), width=2)
    return result


def add_open_mouth(img, mouth_region):
    """Draw an open mouth (talking/laughing)."""
    result = img.copy()
    draw = ImageDraw.Draw(result)
    mx, my, mw, mh = mouth_region
    cx = mx + mw // 2
    cy = my + mh // 2
    # Open oval mouth
    draw.ellipse([cx - mw // 3, cy - mh, cx + mw // 3, cy + mh],
                 fill=(60, 20, 20, 200), outline=(30, 30, 30, 220), width=2)
    return result


def add_frown(img, mouth_region):
    """Add a frown line to the mouth area."""
    result = img.copy()
    draw = ImageDraw.Draw(result)
    mx, my, mw, mh = mouth_region
    # Curved frown
    cx = mx + mw // 2
    cy = my + mh
    draw.arc([cx - 12, cy - 6, cx + 12, cy + 6], start=180, end=360,
             fill=(30, 30, 30, 200), width=3)
    return result


def squash_stretch(img, sx=1.0, sy=1.0):
    """Squash and stretch the image."""
    w, h = img.size
    new_w = int(w * sx)
    new_h = int(h * sy)
    stretched = img.resize((new_w, new_h), Image.LANCZOS)
    return stretched


# ===================================================================
# Expressive poses — each takes base mario (cropped) and returns RGBA
# ===================================================================

def pose_idle(mario):
    """Standing idle — clean, neutral."""
    return fit_to_canvas(mario)


def pose_idle_blink(mario):
    """Idle with eyes closed (blink frame)."""
    fitted = fit_to_canvas(mario)
    eyes = get_eye_region(fitted)
    result = close_eyes(fitted, eyes)
    return result


def pose_talking_1(mario):
    """Talking — open mouth, speech bubble."""
    fitted = fit_to_canvas(mario)
    mouth = get_mouth_region(fitted)
    result = add_open_mouth(fitted, mouth)
    draw = ImageDraw.Draw(result)
    draw_speech_bubble(draw, 220, 30, 160, 60, "Let's-a go!")
    return result


def pose_talking_2(mario):
    """Talking excitedly — open mouth, shout bubble."""
    fitted = fit_to_canvas(mario)
    mouth = get_mouth_region(fitted)
    result = add_open_mouth(fitted, mouth)
    draw = ImageDraw.Draw(result)
    draw_speech_bubble(draw, 210, 20, 170, 70, "Wahoo!", shout=True)
    return result


def pose_talking_3(mario):
    """Talking — mouth open, no bubble (for TTS overlay)."""
    fitted = fit_to_canvas(mario)
    mouth = get_mouth_region(fitted)
    return add_open_mouth(fitted, mouth)


def pose_thinking(mario):
    """Thinking — thought bubble, eyes looking up."""
    fitted = fit_to_canvas(mario)
    draw = ImageDraw.Draw(fitted)
    draw_thought_bubble(draw, 240, 20, 140, 70, "Hmm...")
    draw_question_mark(draw, 260, 30, color=(150, 150, 200))
    return fitted


def pose_thinking_deep(mario):
    """Deep thinking — slightly tilted, multiple question marks."""
    tilted = mario.rotate(-5, expand=True, resample=Image.BICUBIC)
    fitted = fit_to_canvas(tilted)
    draw = ImageDraw.Draw(fitted)
    draw_thought_bubble(draw, 230, 10, 150, 80)
    draw_question_mark(draw, 250, 25, color=(100, 100, 200))
    draw_question_mark(draw, 290, 40, color=(130, 130, 220))
    return fitted


def pose_thinking_chin(mario_base, thinking_ref_path):
    """Thinking with hand on chin — uses the thinking reference image."""
    try:
        ref = Image.open(thinking_ref_path).convert("RGBA")
        ref = remove_background_smart(ref)
        ref = crop_to_content(ref)
        fitted = fit_to_canvas(ref)
        draw = ImageDraw.Draw(fitted)
        draw_thought_bubble(draw, 230, 15, 150, 75, "Mama mia...")
        return fitted
    except Exception:
        return pose_thinking(mario_base)


def pose_happy(mario):
    """Happy — bright, sparkles, slight bounce up."""
    fitted = fit_to_canvas(mario, y_offset=-10)
    # Brighten
    rgb = fitted.convert("RGB")
    rgb = ImageEnhance.Brightness(rgb).enhance(1.15)
    result = rgb.convert("RGBA")
    result.putalpha(fitted.split()[3])
    draw = ImageDraw.Draw(result)
    draw_stars(draw, 280, 60, count=5)
    draw_blush(draw, 155, 210)
    return result


def pose_very_happy(mario):
    """Very happy — big sparkles, blush, stars everywhere."""
    squished = squash_stretch(mario, 1.05, 0.95)
    fitted = fit_to_canvas(squished, y_offset=-5)
    rgb = fitted.convert("RGB")
    rgb = ImageEnhance.Brightness(rgb).enhance(1.2)
    rgb = ImageEnhance.Color(rgb).enhance(1.3)
    result = rgb.convert("RGBA")
    result.putalpha(fitted.split()[3])
    draw = ImageDraw.Draw(result)
    draw_stars(draw, 60, 50, count=4)
    draw_stars(draw, 280, 40, count=4)
    draw_blush(draw, 155, 210)
    eyes = get_eye_region(result)
    result = close_eyes(result, eyes)  # Happy squint
    return result


def pose_sad(mario):
    """Sad — muted colors, tears, frown."""
    fitted = fit_to_canvas(mario, y_offset=5)
    # Desaturate slightly
    rgb = fitted.convert("RGB")
    rgb = ImageEnhance.Color(rgb).enhance(0.6)
    rgb = ImageEnhance.Brightness(rgb).enhance(0.85)
    result = rgb.convert("RGBA")
    result.putalpha(fitted.split()[3])
    mouth = get_mouth_region(result)
    result = add_frown(result, mouth)
    draw = ImageDraw.Draw(result)
    draw_tears(draw, 165, 195)
    return result


def pose_crying(mario):
    """Crying — tears streaming, very desaturated."""
    fitted = fit_to_canvas(mario, y_offset=8)
    rgb = fitted.convert("RGB")
    rgb = ImageEnhance.Color(rgb).enhance(0.4)
    rgb = ImageEnhance.Brightness(rgb).enhance(0.8)
    result = rgb.convert("RGBA")
    result.putalpha(fitted.split()[3])
    mouth = get_mouth_region(result)
    result = add_open_mouth(result, mouth)
    result = add_frown(result, mouth)
    draw = ImageDraw.Draw(result)
    draw_tears(draw, 160, 190, "both")
    draw_tears(draw, 163, 205, "both")
    return result


def pose_surprised(mario):
    """Surprised — wide eyes, exclamation, slight jump."""
    fitted = fit_to_canvas(mario, y_offset=-15)
    eyes = get_eye_region(fitted)
    result = wide_eyes(fitted, eyes)
    mouth = get_mouth_region(result)
    result = add_open_mouth(result, mouth)
    draw = ImageDraw.Draw(result)
    draw_exclamation(draw, 280, 30)
    return result


def pose_shocked(mario):
    """Shocked — extreme surprise, shaking effect."""
    fitted = fit_to_canvas(mario, y_offset=-20)
    # Slight shake effect by compositing offset copies
    arr = np.array(fitted).astype(float)
    shifted = np.roll(arr, 3, axis=1)
    blended = np.clip(arr * 0.7 + shifted * 0.3, 0, 255).astype(np.uint8)
    result = Image.fromarray(blended)
    eyes = get_eye_region(result)
    result = wide_eyes(result, eyes)
    draw = ImageDraw.Draw(result)
    draw_exclamation(draw, 270, 20, color=(255, 50, 50))
    draw_exclamation(draw, 300, 40, color=(255, 100, 50))
    draw_sweat_drops(draw, 300, 120, count=4)
    return result


def pose_angry(mario):
    """Angry — red tint on face, anger veins, furrowed expression."""
    fitted = fit_to_canvas(mario)
    face = get_face_region(fitted)
    result = tint_region(fitted, face, (255, 0, 0), 0.2)
    draw = ImageDraw.Draw(result)
    draw_anger_veins(draw, 280, 60, count=2)
    # Add slightly darker/red vignette
    arr = np.array(result).astype(float)
    arr[:, :, 0] = np.clip(arr[:, :, 0] * 1.1, 0, 255)
    arr[:, :, 1] *= 0.95
    arr[:, :, 2] *= 0.9
    return Image.fromarray(arr.astype(np.uint8))


def pose_furious(mario):
    """Furious — strong red, lots of anger veins, shaking."""
    fitted = fit_to_canvas(mario)
    face = get_face_region(fitted)
    result = tint_region(fitted, face, (255, 30, 0), 0.35)
    # Shake
    arr = np.array(result)
    shifted = np.roll(arr, 4, axis=1)
    blended = np.clip(np.array(result).astype(float) * 0.6 + shifted.astype(float) * 0.4, 0, 255)
    result = Image.fromarray(blended.astype(np.uint8))
    draw = ImageDraw.Draw(result)
    draw_anger_veins(draw, 270, 50, count=3)
    draw_anger_veins(draw, 90, 70, count=2)
    return result


def pose_sleepy(mario):
    """Sleepy — droopy, dim, small Zzz."""
    fitted = fit_to_canvas(mario, y_offset=10)
    rgb = fitted.convert("RGB")
    rgb = ImageEnhance.Brightness(rgb).enhance(0.8)
    result = rgb.convert("RGBA")
    result.putalpha(fitted.split()[3])
    eyes = get_eye_region(result)
    result = close_eyes(result, eyes)
    draw = ImageDraw.Draw(result)
    draw_zzz(draw, 270, 70, count=2)
    return result


def pose_sleeping(mario):
    """Fully asleep — tilted, Zzz, very dim."""
    tilted = mario.rotate(8, expand=True, resample=Image.BICUBIC)
    fitted = fit_to_canvas(tilted, y_offset=15)
    rgb = fitted.convert("RGB")
    rgb = ImageEnhance.Brightness(rgb).enhance(0.65)
    result = rgb.convert("RGBA")
    result.putalpha(fitted.split()[3])
    eyes = get_eye_region(result)
    result = close_eyes(result, eyes)
    draw = ImageDraw.Draw(result)
    draw_zzz(draw, 260, 50, count=3)
    return result


def pose_excited(mario):
    """Excited — jumping up, sparkles, bright."""
    fitted = fit_to_canvas(mario, y_offset=-25)
    rgb = fitted.convert("RGB")
    rgb = ImageEnhance.Brightness(rgb).enhance(1.2)
    rgb = ImageEnhance.Color(rgb).enhance(1.4)
    result = rgb.convert("RGBA")
    result.putalpha(fitted.split()[3])
    draw = ImageDraw.Draw(result)
    draw_stars(draw, 80, 30, count=6)
    draw_stars(draw, 280, 50, count=5)
    draw_exclamation(draw, 310, 20, color=(255, 200, 50))
    # Drop shadow below feet
    draw.ellipse([130, 460, 270, 475], fill=(0, 0, 0, 60))
    return result


def pose_laughing(mario):
    """Laughing — eyes squinted, mouth open, tilted back."""
    tilted = mario.rotate(-3, expand=True, resample=Image.BICUBIC)
    fitted = fit_to_canvas(tilted)
    eyes = get_eye_region(fitted)
    result = close_eyes(fitted, eyes)
    mouth = get_mouth_region(result)
    result = add_open_mouth(result, mouth)
    draw = ImageDraw.Draw(result)
    draw_text_overlay(draw, "Ha ha!", 260, 60, size=22, color=(255, 200, 50))
    draw_blush(draw, 155, 210)
    return result


def pose_laughing_hard(mario):
    """Laughing hard — squished, tears of joy."""
    squished = squash_stretch(mario, 1.1, 0.9)
    fitted = fit_to_canvas(squished, y_offset=5)
    eyes = get_eye_region(fitted)
    result = close_eyes(fitted, eyes)
    mouth = get_mouth_region(result)
    result = add_open_mouth(result, mouth)
    draw = ImageDraw.Draw(result)
    draw_tears(draw, 165, 195, "both")
    draw_text_overlay(draw, "WAHAHA!", 230, 40, size=24, color=(255, 220, 50))
    return result


def pose_waving(mario):
    """Waving — greeting pose (slight tilt)."""
    tilted = mario.rotate(-5, expand=True, resample=Image.BICUBIC)
    fitted = fit_to_canvas(tilted, y_offset=-5)
    draw = ImageDraw.Draw(fitted)
    # Wave lines near hand area
    draw.arc([280, 80, 330, 140], start=0, end=180, fill=(255, 255, 100, 180), width=3)
    draw.arc([290, 70, 340, 130], start=0, end=180, fill=(255, 255, 100, 140), width=2)
    draw_text_overlay(draw, "Ciao!", 290, 50, size=20, color=(255, 255, 200))
    return fitted


def pose_waving_hello(mario):
    """Waving hello with speech bubble."""
    tilted = mario.rotate(-5, expand=True, resample=Image.BICUBIC)
    fitted = fit_to_canvas(tilted, y_offset=-5)
    draw = ImageDraw.Draw(fitted)
    draw_speech_bubble(draw, 230, 20, 150, 55, "It's-a me!")
    draw.arc([280, 90, 330, 150], start=0, end=180, fill=(255, 255, 100, 180), width=3)
    return fitted


def pose_jumping(mario):
    """Jumping — raised high, shadow below."""
    fitted = fit_to_canvas(mario, y_offset=-40)
    draw = ImageDraw.Draw(fitted)
    # Drop shadow
    draw.ellipse([120, 470, 280, 490], fill=(0, 0, 0, 80))
    draw_motion_lines(draw, 140, 380, direction="up", count=5)
    draw_text_overlay(draw, "Yahoo!", 260, 30, size=24, color=(255, 220, 50))
    return fitted


def pose_jumping_high(mario):
    """High jump — very high up, big shadow, stars."""
    small = squash_stretch(mario, 0.9, 1.1)
    fitted = fit_to_canvas(small, y_offset=-60)
    draw = ImageDraw.Draw(fitted)
    draw.ellipse([140, 475, 260, 488], fill=(0, 0, 0, 50))
    draw_motion_lines(draw, 150, 350, direction="up", count=8)
    draw_stars(draw, 100, 20, count=4)
    return fitted


def pose_dancing(mario):
    """Dancing — tilted, music notes."""
    tilted = mario.rotate(10, expand=True, resample=Image.BICUBIC)
    fitted = fit_to_canvas(tilted)
    draw = ImageDraw.Draw(fitted)
    draw_music_notes(draw, 270, 40, count=4)
    draw_stars(draw, 80, 60, count=3)
    return fitted


def pose_dancing_2(mario):
    """Dancing other direction — mirror + tilt."""
    mirrored = ImageOps.mirror(mario)
    tilted = mirrored.rotate(-10, expand=True, resample=Image.BICUBIC)
    fitted = fit_to_canvas(tilted)
    draw = ImageDraw.Draw(fitted)
    draw_music_notes(draw, 50, 50, count=4)
    draw_stars(draw, 290, 70, count=3)
    return fitted


def pose_confused(mario):
    """Confused — question marks, slight head tilt."""
    tilted = mario.rotate(7, expand=True, resample=Image.BICUBIC)
    fitted = fit_to_canvas(tilted)
    draw = ImageDraw.Draw(fitted)
    draw_question_mark(draw, 280, 30, color=(150, 150, 255))
    draw_question_mark(draw, 310, 55, color=(130, 130, 230))
    draw_sweat_drops(draw, 290, 100, count=2)
    return fitted


def pose_embarrassed(mario):
    """Embarrassed — blushing hard, sweat, looking away."""
    mirrored = ImageOps.mirror(mario)
    fitted = fit_to_canvas(mirrored)
    face = get_face_region(fitted)
    result = tint_region(fitted, face, (255, 100, 100), 0.25)
    draw = ImageDraw.Draw(result)
    draw_blush(draw, 145, 205, w=30, h=15)
    draw_sweat_drops(draw, 100, 130, count=3)
    return result


def pose_nervous(mario):
    """Nervous — sweat drops, slight shake."""
    fitted = fit_to_canvas(mario)
    arr = np.array(fitted)
    shifted = np.roll(arr, 2, axis=1)
    blended = np.clip(arr.astype(float) * 0.8 + shifted.astype(float) * 0.2, 0, 255)
    result = Image.fromarray(blended.astype(np.uint8))
    draw = ImageDraw.Draw(result)
    draw_sweat_drops(draw, 280, 100, count=4)
    draw_sweat_drops(draw, 100, 120, count=2)
    return result


def pose_scared(mario):
    """Scared — shaking, wide eyes, sweat, blue tint."""
    fitted = fit_to_canvas(mario, y_offset=5)
    # Blue/cold tint
    arr = np.array(fitted).astype(float)
    arr[:, :, 0] *= 0.85
    arr[:, :, 2] = np.clip(arr[:, :, 2] * 1.15, 0, 255)
    result = Image.fromarray(arr.astype(np.uint8))
    # Shake
    arr2 = np.array(result)
    shifted = np.roll(arr2, 3, axis=1)
    blended = np.clip(arr2.astype(float) * 0.7 + shifted.astype(float) * 0.3, 0, 255)
    result = Image.fromarray(blended.astype(np.uint8))
    eyes = get_eye_region(result)
    result = wide_eyes(result, eyes)
    draw = ImageDraw.Draw(result)
    draw_sweat_drops(draw, 280, 90, count=5)
    draw_exclamation(draw, 300, 30, color=(100, 100, 255))
    return result


def pose_love(mario):
    """In love — hearts, blush, dreamy."""
    fitted = fit_to_canvas(mario)
    rgb = fitted.convert("RGB")
    rgb = ImageEnhance.Color(rgb).enhance(1.2)
    result = rgb.convert("RGBA")
    result.putalpha(fitted.split()[3])
    draw = ImageDraw.Draw(result)
    draw_hearts(draw, 270, 30, count=4)
    draw_hearts(draw, 80, 50, count=3)
    draw_blush(draw, 155, 210, w=28, h=14)
    eyes = get_eye_region(result)
    result = close_eyes(result, eyes)  # Dreamy closed eyes
    return result


def pose_mischievous(mario):
    """Mischievous — sly grin, one eye narrowed."""
    fitted = fit_to_canvas(mario)
    draw = ImageDraw.Draw(fitted)
    # Narrow one eye
    eyes = get_eye_region(fitted)
    ex, ey, ew, eh = eyes
    cy = ey + eh // 2
    draw.line([(ex + 2, cy), (ex + ew // 2 - 5, cy)], fill=(30, 30, 30, 160), width=2)
    draw_text_overlay(draw, "Heh heh...", 240, 60, size=18, color=(255, 200, 100))
    return fitted


def pose_determined(mario):
    """Determined — bold, sharp, slight lean forward."""
    fitted = fit_to_canvas(mario, y_offset=-5)
    rgb = fitted.convert("RGB")
    rgb = ImageEnhance.Contrast(rgb).enhance(1.3)
    rgb = ImageEnhance.Color(rgb).enhance(1.2)
    result = rgb.convert("RGBA")
    result.putalpha(fitted.split()[3])
    draw = ImageDraw.Draw(result)
    draw_text_overlay(draw, "Let's-a go!", 230, 40, size=22, color=(255, 50, 50))
    # Intensity lines
    for i in range(4):
        x = 280 + i * 8
        draw.line([(x, 80 + i * 5), (x, 120 + i * 3)], fill=(255, 200, 50, 180), width=2)
    return result


def pose_proud(mario):
    """Proud — puffed up, sparkles, chin up."""
    stretched = squash_stretch(mario, 1.05, 1.0)
    fitted = fit_to_canvas(stretched, y_offset=-10)
    rgb = fitted.convert("RGB")
    rgb = ImageEnhance.Brightness(rgb).enhance(1.1)
    result = rgb.convert("RGBA")
    result.putalpha(fitted.split()[3])
    draw = ImageDraw.Draw(result)
    draw_stars(draw, 280, 40, count=4)
    draw_stars(draw, 70, 50, count=3)
    # Crown-like sparkle above head
    draw_stars(draw, 170, 15, count=3)
    return result


def pose_tired(mario):
    """Tired — droopy, dark circles, dull."""
    fitted = fit_to_canvas(mario, y_offset=10)
    rgb = fitted.convert("RGB")
    rgb = ImageEnhance.Brightness(rgb).enhance(0.75)
    rgb = ImageEnhance.Color(rgb).enhance(0.5)
    result = rgb.convert("RGBA")
    result.putalpha(fitted.split()[3])
    eyes = get_eye_region(result)
    # Dark circles under eyes
    draw = ImageDraw.Draw(result)
    ex, ey, ew, eh = eyes
    draw.ellipse([ex + 3, ey + eh + 2, ex + ew // 2 - 5, ey + eh + 8],
                 fill=(80, 60, 100, 80))
    draw.ellipse([ex + ew // 2 + 5, ey + eh + 2, ex + ew - 3, ey + eh + 8],
                 fill=(80, 60, 100, 80))
    draw_sweat_drops(draw, 280, 120, count=2)
    return result


def pose_eating(mario):
    """Eating a mushroom — nom nom."""
    fitted = fit_to_canvas(mario)
    mouth = get_mouth_region(fitted)
    result = add_open_mouth(fitted, mouth)
    draw = ImageDraw.Draw(result)
    # Draw a small mushroom near mouth
    mx = 260
    my = 200
    # Mushroom cap
    draw.ellipse([mx - 12, my - 10, mx + 12, my + 2], fill=(255, 50, 50, 220))
    draw.ellipse([mx - 4, my - 8, mx + 0, my - 2], fill=(255, 255, 255, 200))
    draw.ellipse([mx + 2, my - 6, mx + 8, my], fill=(255, 255, 255, 200))
    # Stem
    draw.rectangle([mx - 5, my + 2, mx + 5, my + 12], fill=(255, 240, 200, 220))
    draw_text_overlay(draw, "Nom nom!", 270, 160, size=16, color=(255, 200, 100))
    return result


def pose_star_power(mario):
    """Star power — rainbow glow, flashing, invincible!"""
    fitted = fit_to_canvas(mario, y_offset=-10)
    arr = np.array(fitted).astype(float)
    h, w = arr.shape[:2]
    for y in range(h):
        phase = (y / h) * 2 * math.pi * 3
        arr[y, :, 0] = np.clip(arr[y, :, 0] + 30 * math.sin(phase), 0, 255)
        arr[y, :, 1] = np.clip(arr[y, :, 1] + 30 * math.sin(phase + 2.1), 0, 255)
        arr[y, :, 2] = np.clip(arr[y, :, 2] + 30 * math.sin(phase + 4.2), 0, 255)
    result = Image.fromarray(arr.astype(np.uint8))
    # Add glow
    glow = result.filter(ImageFilter.GaussianBlur(8))
    glow_arr = np.array(glow).astype(float)
    arr2 = np.array(result).astype(float)
    blended = np.clip(arr2 * 0.7 + glow_arr * 0.4, 0, 255)
    blended[:, :, 3] = arr[:, :, 3]
    result = Image.fromarray(blended.astype(np.uint8))
    draw = ImageDraw.Draw(result)
    draw_stars(draw, 60, 30, count=8)
    draw_stars(draw, 280, 40, count=8)
    draw_stars(draw, 170, 10, count=5)
    return result


def pose_fire_flower(mario):
    """Fire flower power — white/red palette, fireballs."""
    fitted = fit_to_canvas(mario)
    arr = np.array(fitted).astype(float)
    # Shift to white/red fire mario colors
    red_mask = (arr[:, :, 0] > 150) & (arr[:, :, 1] < 100) & (arr[:, :, 2] < 100) & (arr[:, :, 3] > 128)
    arr[red_mask, :3] = [255, 255, 255]
    result = Image.fromarray(arr.astype(np.uint8))
    draw = ImageDraw.Draw(result)
    # Fireballs
    for i in range(3):
        fx = 280 + i * 20
        fy = 200 - i * 40
        draw.ellipse([fx - 8, fy - 8, fx + 8, fy + 8], fill=(255, 150, 30, 220))
        draw.ellipse([fx - 5, fy - 5, fx + 5, fy + 5], fill=(255, 255, 100, 240))
    return result


def pose_mega_mushroom(mario):
    """Mega mushroom — giant Mario!"""
    big = squash_stretch(mario, 1.3, 1.25)
    fitted = fit_to_canvas(big, y_offset=10)
    draw = ImageDraw.Draw(fitted)
    draw_text_overlay(draw, "MEGA!", 250, 20, size=30, color=(255, 50, 50))
    # Ground shake lines
    for i in range(6):
        lx = 80 + i * 50
        draw.line([(lx, 485), (lx, 495)], fill=(150, 150, 150, 150), width=2)
    return fitted


def pose_mini_mushroom(mario):
    """Mini mushroom — tiny Mario!"""
    small = squash_stretch(mario, 0.5, 0.5)
    fitted = fit_to_canvas(small, y_offset=80)
    draw = ImageDraw.Draw(fitted)
    draw_text_overlay(draw, "So tiny!", 250, 100, size=14, color=(200, 200, 255))
    return fitted


def pose_greeting(mario):
    """Greeting — welcoming pose with warm text."""
    tilted = mario.rotate(-3, expand=True, resample=Image.BICUBIC)
    fitted = fit_to_canvas(tilted, y_offset=-5)
    draw = ImageDraw.Draw(fitted)
    draw_speech_bubble(draw, 220, 15, 165, 65, "Welcome!")
    draw_stars(draw, 80, 40, count=3)
    return fitted


def pose_farewell(mario):
    """Farewell — waving goodbye."""
    tilted = mario.rotate(-8, expand=True, resample=Image.BICUBIC)
    fitted = fit_to_canvas(tilted, y_offset=-5)
    draw = ImageDraw.Draw(fitted)
    draw_speech_bubble(draw, 220, 20, 160, 55, "See ya!")
    draw.arc([290, 85, 340, 145], start=0, end=180, fill=(255, 255, 100, 180), width=3)
    draw.arc([300, 75, 350, 135], start=0, end=180, fill=(255, 255, 100, 120), width=2)
    return fitted


def pose_listening(mario):
    """Listening — attentive, slight lean, ear indicator."""
    tilted = mario.rotate(3, expand=True, resample=Image.BICUBIC)
    fitted = fit_to_canvas(tilted)
    draw = ImageDraw.Draw(fitted)
    # Sound wave indicators near ear
    for i in range(3):
        r = 15 + i * 12
        draw.arc([90 - r, 150 - r // 2, 90 + r, 150 + r // 2], start=120, end=240,
                 fill=(100, 200, 255, 180 - i * 50), width=2)
    draw_text_overlay(draw, "...", 270, 80, size=24, color=(200, 200, 200))
    return fitted


def pose_singing(mario):
    """Singing — open mouth, music notes everywhere."""
    fitted = fit_to_canvas(mario)
    mouth = get_mouth_region(fitted)
    result = add_open_mouth(fitted, mouth)
    draw = ImageDraw.Draw(result)
    draw_music_notes(draw, 260, 30, count=4)
    draw_music_notes(draw, 70, 50, count=3)
    draw_blush(draw, 155, 210)
    return result


def pose_victorious(mario):
    """Victory — fist pump pose, stars, bright."""
    fitted = fit_to_canvas(mario, y_offset=-15)
    rgb = fitted.convert("RGB")
    rgb = ImageEnhance.Brightness(rgb).enhance(1.25)
    rgb = ImageEnhance.Color(rgb).enhance(1.4)
    result = rgb.convert("RGBA")
    result.putalpha(fitted.split()[3])
    draw = ImageDraw.Draw(result)
    draw_stars(draw, 250, 10, count=8)
    draw_stars(draw, 80, 20, count=6)
    draw_text_overlay(draw, "WAHOO!", 230, 25, size=28, color=(255, 215, 0))
    return result


def pose_processing(mario):
    """Processing/loading — thinking with gear indicator."""
    fitted = fit_to_canvas(mario)
    draw = ImageDraw.Draw(fitted)
    # Loading dots
    for i in range(3):
        cx = 270 + i * 20
        cy = 80
        draw.ellipse([cx - 5, cy - 5, cx + 5, cy + 5], fill=(200, 200, 200, 200))
    draw_thought_bubble(draw, 240, 15, 130, 50)
    # Gear icon (simplified)
    gx, gy = 290, 32
    for angle in range(0, 360, 45):
        rad = math.radians(angle)
        x1 = gx + int(12 * math.cos(rad))
        y1 = gy + int(12 * math.sin(rad))
        draw.rectangle([x1 - 3, y1 - 3, x1 + 3, y1 + 3], fill=(150, 150, 150, 200))
    draw.ellipse([gx - 8, gy - 8, gx + 8, gy + 8], fill=(100, 100, 100, 200))
    draw.ellipse([gx - 4, gy - 4, gx + 4, gy + 4], fill=(180, 180, 180, 200))
    return fitted


# Master list of all expressive poses
ALL_POSES = [
    ("idle", pose_idle, "Standing neutral — default state"),
    ("idle_blink", pose_idle_blink, "Idle with eyes closed — blink frame"),
    ("talking_1", pose_talking_1, "Talking with 'Let's-a go!' speech bubble"),
    ("talking_2", pose_talking_2, "Shouting 'Wahoo!' — excited speech"),
    ("talking_3", pose_talking_3, "Mouth open — for TTS audio overlay"),
    ("thinking", pose_thinking, "Thinking with thought bubble and question mark"),
    ("thinking_deep", pose_thinking_deep, "Deep thinking — tilted, multiple ?'s"),
    ("thinking_chin", None, "Thinking with hand on chin (uses reference image)"),
    ("happy", pose_happy, "Happy — bright, sparkles, blushing"),
    ("very_happy", pose_very_happy, "Very happy — squished, squinting, stars"),
    ("sad", pose_sad, "Sad — muted colors, tears, frown"),
    ("crying", pose_crying, "Crying — streaming tears, desaturated"),
    ("surprised", pose_surprised, "Surprised — wide eyes, exclamation, slight jump"),
    ("shocked", pose_shocked, "Shocked — extreme surprise, shaking"),
    ("angry", pose_angry, "Angry — red face tint, anger veins"),
    ("furious", pose_furious, "Furious — deep red, lots of anger veins, shaking"),
    ("sleepy", pose_sleepy, "Sleepy — droopy eyes, dim, small Zzz"),
    ("sleeping", pose_sleeping, "Fully asleep — tilted, Zzz, very dim"),
    ("excited", pose_excited, "Excited — jumping up, sparkles, bright"),
    ("laughing", pose_laughing, "Laughing — eyes squinted, mouth open"),
    ("laughing_hard", pose_laughing_hard, "Laughing hard — tears of joy, squished"),
    ("waving", pose_waving, "Waving — greeting with wave arcs"),
    ("waving_hello", pose_waving_hello, "Waving hello with 'It's-a me!' bubble"),
    ("jumping", pose_jumping, "Jumping — raised up with shadow below"),
    ("jumping_high", pose_jumping_high, "High jump — way up, motion lines"),
    ("dancing", pose_dancing, "Dancing — tilted right, music notes"),
    ("dancing_2", pose_dancing_2, "Dancing — tilted left, mirrored"),
    ("confused", pose_confused, "Confused — question marks, head tilt"),
    ("embarrassed", pose_embarrassed, "Embarrassed — blushing, looking away"),
    ("nervous", pose_nervous, "Nervous — shaking, sweat drops"),
    ("scared", pose_scared, "Scared — blue tint, wide eyes, sweat"),
    ("love", pose_love, "In love — hearts, blush, dreamy eyes"),
    ("mischievous", pose_mischievous, "Mischievous — sly wink, 'Heh heh'"),
    ("determined", pose_determined, "Determined — bold, sharp, 'Let's-a go!'"),
    ("proud", pose_proud, "Proud — puffed up, sparkles above head"),
    ("tired", pose_tired, "Tired — dim, dark circles, droopy"),
    ("eating", pose_eating, "Eating a mushroom — nom nom!"),
    ("star_power", pose_star_power, "Star power — rainbow glow, invincible!"),
    ("fire_flower", pose_fire_flower, "Fire flower — white/red, fireballs"),
    ("mega_mushroom", pose_mega_mushroom, "Mega mushroom — giant Mario!"),
    ("mini_mushroom", pose_mini_mushroom, "Mini mushroom — tiny Mario!"),
    ("greeting", pose_greeting, "Greeting — welcoming with 'Welcome!'"),
    ("farewell", pose_farewell, "Farewell — waving goodbye"),
    ("listening", pose_listening, "Listening — attentive, sound waves"),
    ("singing", pose_singing, "Singing — open mouth, music everywhere"),
    ("victorious", pose_victorious, "Victory — fist pump, 'WAHOO!'"),
    ("processing", pose_processing, "Processing — thinking with gear icon"),
]


def generate_gallery(output_dir, poses_info):
    """Generate HTML gallery for expressive poses."""
    html = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Mario Expressive Poses Gallery</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { background: #1a1a2e; color: #eee; font-family: 'Segoe UI', Arial, sans-serif; padding: 20px; }
  h1 { text-align: center; color: #e63946; font-size: 2.5em; margin-bottom: 10px;
       text-shadow: 2px 2px 4px rgba(0,0,0,0.5); }
  .subtitle { text-align: center; color: #a8dadc; margin-bottom: 30px; font-size: 1.1em; }
  .stats { text-align: center; color: #a8dadc; margin: 15px 0; font-size: 1.1em; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
           gap: 20px; margin: 20px auto; max-width: 1400px; }
  .card { background: #16213e; border-radius: 12px; overflow: hidden; transition: transform 0.2s;
           box-shadow: 0 4px 8px rgba(0,0,0,0.3); }
  .card:hover { transform: scale(1.05); box-shadow: 0 8px 16px rgba(0,0,0,0.5); }
  .card img { width: 100%; height: 300px; object-fit: contain; background: #0f3460; padding: 10px; }
  .card .label { padding: 10px 12px; background: #1a1a2e; }
  .card .label .name { font-size: 1em; color: #e63946; font-weight: bold; }
  .card .label .desc { font-size: 0.8em; color: #a8dadc; margin-top: 4px; }
  .category { margin: 40px 0 20px; padding: 10px 20px; background: #16213e;
              border-radius: 8px; border-left: 4px solid #e63946; }
  .category h2 { color: #f1faee; font-size: 1.3em; }
</style>
</head>
<body>
<h1>🎭 Mario Expressive Poses</h1>
<p class="subtitle">Photoshopped emotions, actions, and power-ups — not just filters!</p>
"""
    html += f'<p class="stats">🎨 {len(poses_info)} unique expressive poses from NSMBU Deluxe Mario</p>\n'

    # Categorize
    categories = {
        "💬 Speech & Communication": ["talking_1", "talking_2", "talking_3", "greeting", "waving", "waving_hello", "farewell", "listening", "singing"],
        "😊 Positive Emotions": ["idle", "idle_blink", "happy", "very_happy", "excited", "laughing", "laughing_hard", "love", "proud", "victorious"],
        "😢 Negative Emotions": ["sad", "crying", "angry", "furious", "scared", "nervous", "embarrassed", "tired"],
        "🤔 Thinking & Processing": ["thinking", "thinking_deep", "thinking_chin", "confused", "mischievous", "determined", "processing"],
        "💤 Sleep & Rest": ["sleepy", "sleeping"],
        "🏃 Movement & Action": ["jumping", "jumping_high", "dancing", "dancing_2", "eating"],
        "⭐ Power-Ups": ["star_power", "fire_flower", "mega_mushroom", "mini_mushroom"],
    }

    for cat_name, pose_names in categories.items():
        html += f'<div class="category"><h2>{cat_name}</h2></div>\n'
        html += '<div class="grid">\n'
        for name, desc in poses_info:
            if name in pose_names:
                html += f'  <div class="card">\n'
                html += f'    <img src="{name}.png" alt="{name}" loading="lazy">\n'
                html += f'    <div class="label">\n'
                html += f'      <div class="name">{name}</div>\n'
                html += f'      <div class="desc">{desc}</div>\n'
                html += f'    </div>\n'
                html += f'  </div>\n'
        html += '</div>\n'

    html += "\n</body>\n</html>"

    (output_dir / "index.html").write_text(html, encoding="utf-8")
    print(f"  Gallery: {output_dir / 'index.html'}")


def main():
    print("=" * 60)
    print("  MARIO EXPRESSIVE POSES GENERATOR")
    print("  Photoshopping real emotions & actions!")
    print("=" * 60)

    # Load base Mario
    print(f"\nLoading base: {PRIMARY_BASE.name}...")
    mario_base = prepare_base(PRIMARY_BASE)
    print(f"  Base prepared: {mario_base.size}")

    # Create output dir
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Generate each pose
    poses_info = []
    success = 0
    for name, func, desc in ALL_POSES:
        print(f"  Generating: {name}...", end=" ")
        try:
            if name == "thinking_chin":
                result = pose_thinking_chin(mario_base, THINKING_REF)
            else:
                result = func(mario_base)

            out_path = OUTPUT_DIR / f"{name}.png"
            result.save(str(out_path), "PNG")
            poses_info.append((name, desc))
            success += 1
            print("OK")
        except Exception as e:
            print(f"FAIL: {e}")

    # Generate gallery
    print(f"\nGenerating gallery...")
    generate_gallery(OUTPUT_DIR, poses_info)

    # Manifest
    manifest_path = OUTPUT_DIR / "manifest.txt"
    with open(manifest_path, "w", encoding="utf-8") as f:
        f.write("Mario Expressive Poses\n")
        f.write("=" * 40 + "\n\n")
        f.write(f"Base image: {PRIMARY_BASE.name}\n")
        f.write(f"Thinking ref: {THINKING_REF.name}\n")
        f.write(f"Total poses: {success}\n\n")
        for name, desc in poses_info:
            f.write(f"  {name}: {desc}\n")

    print(f"\n{'=' * 60}")
    print(f"  DONE! {success}/{len(ALL_POSES)} expressive poses generated")
    print(f"  Output: {OUTPUT_DIR}")
    print(f"  Open index.html to browse!")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
