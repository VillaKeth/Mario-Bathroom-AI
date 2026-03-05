#!/usr/bin/env python3
"""
generate_3d_mario_assets.py
===========================
Takes images from mario_assets/, processes them to isolate Mario,
and generates 100 styled iterations in mario_3d_assets/.

Primary base: Mario_New_Super_Mario_Bros_U_Deluxe.webp
Thinking pose: zap9gpu6vj9e1.png

Each iteration applies a unique combination of visual effects.
"""

import os
import sys
import math
import random
import colorsys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance, ImageOps, ImageFont

random.seed(42)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIR = PROJECT_ROOT / "mario_assets"
OUTPUT_DIR = PROJECT_ROOT / "mario_3d_assets"

# Key reference images
PRIMARY_BASE = "Mario_New_Super_Mario_Bros_U_Deluxe.webp"
THINKING_POSE = "zap9gpu6vj9e1.png"

# All supported image extensions
IMG_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}

# Target size for consistent outputs
TARGET_SIZE = (400, 500)


def load_source_images():
    """Load all image files from mario_assets/."""
    images = {}
    for f in sorted(SOURCE_DIR.iterdir()):
        if f.suffix.lower() in IMG_EXTENSIONS and f.is_file():
            try:
                img = Image.open(f).convert("RGBA")
                images[f.name] = img
                print(f"  Loaded: {f.name} ({img.size[0]}x{img.size[1]})")
            except Exception as e:
                print(f"  SKIP: {f.name} — {e}")
    return images


def remove_background(img, threshold=240):
    """Remove near-white backgrounds by making them transparent."""
    import numpy as np
    arr = np.array(img)
    # White/near-white pixels → transparent
    mask = (arr[:, :, 0] > threshold) & (arr[:, :, 1] > threshold) & (arr[:, :, 2] > threshold)
    arr[mask, 3] = 0
    return Image.fromarray(arr)


def remove_background_smart(img, tolerance=30):
    """Remove background by sampling corners and removing similar colors."""
    import numpy as np
    arr = np.array(img)
    h, w = arr.shape[:2]
    
    # Sample corners for background color
    corners = [
        arr[0, 0, :3], arr[0, w-1, :3],
        arr[h-1, 0, :3], arr[h-1, w-1, :3],
    ]
    bg_color = np.mean(corners, axis=0).astype(np.uint8)
    
    # Remove pixels similar to background
    diff = np.abs(arr[:, :, :3].astype(int) - bg_color.astype(int))
    mask = np.all(diff < tolerance, axis=2)
    arr[mask, 3] = 0
    return Image.fromarray(arr)


def crop_to_content(img, padding=10):
    """Crop image to non-transparent content with padding."""
    bbox = img.getbbox()
    if bbox is None:
        return img
    x0, y0, x1, y1 = bbox
    x0 = max(0, x0 - padding)
    y0 = max(0, y0 - padding)
    x1 = min(img.width, x1 + padding)
    y1 = min(img.height, y1 + padding)
    return img.crop((x0, y0, x1, y1))


def fit_to_target(img, target_size=TARGET_SIZE):
    """Resize image to fit within target while maintaining aspect ratio."""
    tw, th = target_size
    iw, ih = img.size
    scale = min(tw / iw, th / ih)
    new_w = int(iw * scale)
    new_h = int(ih * scale)
    resized = img.resize((new_w, new_h), Image.LANCZOS)
    
    # Center on transparent canvas
    canvas = Image.new("RGBA", target_size, (0, 0, 0, 0))
    offset_x = (tw - new_w) // 2
    offset_y = (th - new_h) // 2
    canvas.paste(resized, (offset_x, offset_y), resized)
    return canvas


def prepare_mario(img):
    """Full pipeline: remove bg → crop → fit to target size."""
    cleaned = remove_background_smart(img)
    cropped = crop_to_content(cleaned)
    fitted = fit_to_target(cropped)
    return fitted


# ============================================================
# 100 Effect Functions — each takes an RGBA image, returns RGBA
# ============================================================

def fx_original(img):
    """No changes — clean Mario."""
    return img.copy()

def fx_vibrant(img):
    """Boost saturation and contrast."""
    rgb = img.convert("RGB")
    rgb = ImageEnhance.Color(rgb).enhance(1.8)
    rgb = ImageEnhance.Contrast(rgb).enhance(1.3)
    result = rgb.convert("RGBA")
    result.putalpha(img.split()[3])
    return result

def fx_pastel(img):
    """Soft pastel look."""
    import numpy as np
    arr = np.array(img).astype(float)
    arr[:, :, :3] = arr[:, :, :3] * 0.6 + 255 * 0.4
    return Image.fromarray(arr.astype(np.uint8))

def fx_neon_glow(img):
    """Bright neon glow effect."""
    import numpy as np
    arr = np.array(img).astype(float)
    # Boost brightness and add glow
    arr[:, :, :3] = np.clip(arr[:, :, :3] * 1.5, 0, 255)
    result = Image.fromarray(arr.astype(np.uint8))
    glow = result.filter(ImageFilter.GaussianBlur(8))
    glow_arr = np.array(glow).astype(float)
    arr2 = np.array(result).astype(float)
    blended = np.clip(arr2 * 0.7 + glow_arr * 0.5, 0, 255)
    blended[:, :, 3] = arr[:, :, 3]
    return Image.fromarray(blended.astype(np.uint8))

def fx_retro_crt(img):
    """CRT scanline effect."""
    import numpy as np
    arr = np.array(img).copy()
    for y in range(0, arr.shape[0], 3):
        arr[y, :, :3] = (arr[y, :, :3].astype(float) * 0.6).astype(np.uint8)
    return Image.fromarray(arr)

def fx_sepia(img):
    """Warm sepia tone."""
    import numpy as np
    arr = np.array(img).astype(float)
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    new_r = np.clip(r * 0.393 + g * 0.769 + b * 0.189, 0, 255)
    new_g = np.clip(r * 0.349 + g * 0.686 + b * 0.168, 0, 255)
    new_b = np.clip(r * 0.272 + g * 0.534 + b * 0.131, 0, 255)
    arr[:, :, 0] = new_r
    arr[:, :, 1] = new_g
    arr[:, :, 2] = new_b
    return Image.fromarray(arr.astype(np.uint8))

def fx_ice_blue(img):
    """Cold ice-blue tint."""
    import numpy as np
    arr = np.array(img).astype(float)
    arr[:, :, 0] *= 0.7  # less red
    arr[:, :, 1] *= 0.85  # slightly less green
    arr[:, :, 2] = np.clip(arr[:, :, 2] * 1.4, 0, 255)  # more blue
    return Image.fromarray(arr.astype(np.uint8))

def fx_fire_red(img):
    """Hot fire-red tint."""
    import numpy as np
    arr = np.array(img).astype(float)
    arr[:, :, 0] = np.clip(arr[:, :, 0] * 1.5, 0, 255)
    arr[:, :, 1] *= 0.6
    arr[:, :, 2] *= 0.5
    return Image.fromarray(arr.astype(np.uint8))

def fx_golden(img):
    """Golden/warm sunshine look."""
    import numpy as np
    arr = np.array(img).astype(float)
    arr[:, :, 0] = np.clip(arr[:, :, 0] * 1.3, 0, 255)
    arr[:, :, 1] = np.clip(arr[:, :, 1] * 1.1, 0, 255)
    arr[:, :, 2] *= 0.5
    return Image.fromarray(arr.astype(np.uint8))

def fx_purple_haze(img):
    """Purple psychedelic tint."""
    import numpy as np
    arr = np.array(img).astype(float)
    arr[:, :, 0] = np.clip(arr[:, :, 0] * 1.2, 0, 255)
    arr[:, :, 1] *= 0.5
    arr[:, :, 2] = np.clip(arr[:, :, 2] * 1.4, 0, 255)
    return Image.fromarray(arr.astype(np.uint8))

def fx_matrix_green(img):
    """Matrix-style green tint."""
    import numpy as np
    arr = np.array(img).astype(float)
    arr[:, :, 0] *= 0.3
    arr[:, :, 1] = np.clip(arr[:, :, 1] * 1.5, 0, 255)
    arr[:, :, 2] *= 0.3
    return Image.fromarray(arr.astype(np.uint8))

def fx_high_contrast(img):
    """Extreme contrast."""
    rgb = img.convert("RGB")
    rgb = ImageEnhance.Contrast(rgb).enhance(2.5)
    result = rgb.convert("RGBA")
    result.putalpha(img.split()[3])
    return result

def fx_low_contrast(img):
    """Dreamy low contrast."""
    rgb = img.convert("RGB")
    rgb = ImageEnhance.Contrast(rgb).enhance(0.5)
    rgb = ImageEnhance.Brightness(rgb).enhance(1.2)
    result = rgb.convert("RGBA")
    result.putalpha(img.split()[3])
    return result

def fx_sharpen(img):
    """Extra sharp."""
    rgb = img.convert("RGB")
    rgb = ImageEnhance.Sharpness(rgb).enhance(3.0)
    result = rgb.convert("RGBA")
    result.putalpha(img.split()[3])
    return result

def fx_soft_blur(img):
    """Soft dreamy blur."""
    alpha = img.split()[3]
    blurred = img.filter(ImageFilter.GaussianBlur(2))
    blurred.putalpha(alpha)
    return blurred

def fx_emboss(img):
    """Embossed/relief effect."""
    alpha = img.split()[3]
    emb = img.convert("RGB").filter(ImageFilter.EMBOSS)
    result = emb.convert("RGBA")
    result.putalpha(alpha)
    return result

def fx_edge_detect(img):
    """Edge-only silhouette."""
    alpha = img.split()[3]
    edges = img.convert("RGB").filter(ImageFilter.FIND_EDGES)
    result = edges.convert("RGBA")
    result.putalpha(alpha)
    return result

def fx_posterize_4(img):
    """4-level posterization."""
    alpha = img.split()[3]
    post = ImageOps.posterize(img.convert("RGB"), 2)
    result = post.convert("RGBA")
    result.putalpha(alpha)
    return result

def fx_posterize_8(img):
    """8-level posterization."""
    alpha = img.split()[3]
    post = ImageOps.posterize(img.convert("RGB"), 3)
    result = post.convert("RGBA")
    result.putalpha(alpha)
    return result

def fx_invert(img):
    """Inverted colors."""
    import numpy as np
    arr = np.array(img).copy()
    arr[:, :, :3] = 255 - arr[:, :, :3]
    return Image.fromarray(arr)

def fx_mirror_h(img):
    """Horizontal mirror (facing other way)."""
    return ImageOps.mirror(img)

def fx_flip_v(img):
    """Vertical flip (upside down Mario)."""
    return ImageOps.flip(img)

def fx_rotate_15(img):
    """Slight 15° tilt."""
    alpha = img.split()[3]
    rotated = img.rotate(15, expand=True, resample=Image.BICUBIC)
    return fit_to_target(rotated)

def fx_rotate_neg15(img):
    """Slight -15° tilt."""
    rotated = img.rotate(-15, expand=True, resample=Image.BICUBIC)
    return fit_to_target(rotated)

def fx_rotate_45(img):
    """45° dynamic tilt."""
    rotated = img.rotate(45, expand=True, resample=Image.BICUBIC)
    return fit_to_target(rotated)

def fx_pixel_8(img):
    """8-pixel pixelation."""
    w, h = img.size
    small = img.resize((w // 8, h // 8), Image.NEAREST)
    return small.resize((w, h), Image.NEAREST)

def fx_pixel_4(img):
    """4-pixel pixelation."""
    w, h = img.size
    small = img.resize((w // 4, h // 4), Image.NEAREST)
    return small.resize((w, h), Image.NEAREST)

def fx_pixel_16(img):
    """Heavy 16-pixel pixelation."""
    w, h = img.size
    small = img.resize((w // 16, h // 16), Image.NEAREST)
    return small.resize((w, h), Image.NEAREST)

def fx_vignette(img):
    """Dark vignette around edges."""
    import numpy as np
    arr = np.array(img).astype(float)
    h, w = arr.shape[:2]
    cy, cx = h / 2, w / 2
    Y, X = np.ogrid[:h, :w]
    dist = np.sqrt((X - cx) ** 2 + (Y - cy) ** 2)
    max_dist = np.sqrt(cx ** 2 + cy ** 2)
    vign = 1.0 - (dist / max_dist) ** 1.5
    vign = np.clip(vign, 0.3, 1.0)
    for c in range(3):
        arr[:, :, c] *= vign
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))

def fx_spotlight(img):
    """Center spotlight effect."""
    import numpy as np
    arr = np.array(img).astype(float)
    h, w = arr.shape[:2]
    cy, cx = h / 2, w / 2
    Y, X = np.ogrid[:h, :w]
    dist = np.sqrt((X - cx) ** 2 + (Y - cy) ** 2)
    max_dist = np.sqrt(cx ** 2 + cy ** 2) * 0.6
    spot = np.clip(1.0 - dist / max_dist, 0, 1.0) ** 0.5
    spot = spot * 0.8 + 0.2
    for c in range(3):
        arr[:, :, c] *= spot
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))

def fx_rainbow_shift(img):
    """Hue rotation across the image horizontally."""
    import numpy as np
    arr = np.array(img)
    alpha_ch = Image.fromarray(arr[:, :, 3])
    hsv_arr = np.array(img.convert("RGB").convert("HSV"))
    w = hsv_arr.shape[1]
    for x in range(w):
        shift = int((x / w) * 128)
        hsv_arr[:, x, 0] = (hsv_arr[:, x, 0].astype(int) + shift) % 256
    result = Image.fromarray(hsv_arr, "HSV").convert("RGBA")
    result.putalpha(alpha_ch)
    return result

def fx_hue_shift_60(img):
    """Shift hue by 60 degrees."""
    import numpy as np
    arr = np.array(img)
    alpha_ch = Image.fromarray(arr[:, :, 3])
    hsv_arr = np.array(img.convert("RGB").convert("HSV"))
    hsv_arr[:, :, 0] = (hsv_arr[:, :, 0].astype(int) + 42) % 256
    result = Image.fromarray(hsv_arr, "HSV").convert("RGBA")
    result.putalpha(alpha_ch)
    return result

def fx_hue_shift_120(img):
    """Shift hue by 120 degrees."""
    import numpy as np
    arr = np.array(img)
    alpha_ch = Image.fromarray(arr[:, :, 3])
    hsv_arr = np.array(img.convert("RGB").convert("HSV"))
    hsv_arr[:, :, 0] = (hsv_arr[:, :, 0].astype(int) + 85) % 256
    result = Image.fromarray(hsv_arr, "HSV").convert("RGBA")
    result.putalpha(alpha_ch)
    return result

def fx_hue_shift_180(img):
    """Shift hue by 180 degrees — complementary colors."""
    import numpy as np
    arr = np.array(img)
    alpha_ch = Image.fromarray(arr[:, :, 3])
    hsv_arr = np.array(img.convert("RGB").convert("HSV"))
    hsv_arr[:, :, 0] = (hsv_arr[:, :, 0].astype(int) + 128) % 256
    result = Image.fromarray(hsv_arr, "HSV").convert("RGBA")
    result.putalpha(alpha_ch)
    return result

def fx_grayscale(img):
    """Full grayscale."""
    import numpy as np
    arr = np.array(img)
    gray = img.convert("L").convert("RGBA")
    gray_arr = np.array(gray)
    gray_arr[:, :, 3] = arr[:, :, 3]
    return Image.fromarray(gray_arr)

def fx_duotone_red_blue(img):
    """Red-blue duotone."""
    import numpy as np
    arr = np.array(img)
    gray = np.mean(arr[:, :, :3], axis=2)
    result = np.zeros_like(arr)
    result[:, :, 0] = np.clip(gray * 1.5, 0, 255)  # red
    result[:, :, 2] = np.clip((255 - gray) * 1.2, 0, 255)  # blue
    result[:, :, 3] = arr[:, :, 3]
    return Image.fromarray(result.astype(np.uint8))

def fx_duotone_orange_teal(img):
    """Orange-teal duotone."""
    import numpy as np
    arr = np.array(img)
    gray = np.mean(arr[:, :, :3], axis=2)
    result = np.zeros_like(arr)
    result[:, :, 0] = np.clip(gray * 1.4, 0, 255)
    result[:, :, 1] = np.clip(gray * 0.7, 0, 255)
    result[:, :, 2] = np.clip((255 - gray) * 1.0, 0, 255)
    result[:, :, 3] = arr[:, :, 3]
    return Image.fromarray(result.astype(np.uint8))

def fx_thermal(img):
    """Thermal/heat map look."""
    import numpy as np
    arr = np.array(img)
    gray = np.mean(arr[:, :, :3], axis=2)
    result = np.zeros_like(arr)
    # Low=blue, mid=green/yellow, high=red
    result[:, :, 0] = np.clip(gray * 2 - 128, 0, 255)
    result[:, :, 1] = np.clip(255 - np.abs(gray - 128) * 2, 0, 255)
    result[:, :, 2] = np.clip(255 - gray * 2, 0, 255)
    result[:, :, 3] = arr[:, :, 3]
    return Image.fromarray(result.astype(np.uint8))

def fx_xray(img):
    """X-ray negative with blue tint."""
    import numpy as np
    arr = np.array(img).copy()
    arr[:, :, :3] = 255 - arr[:, :, :3]
    arr[:, :, 0] = (arr[:, :, 0].astype(float) * 0.5).astype(np.uint8)
    arr[:, :, 1] = (arr[:, :, 1].astype(float) * 0.7).astype(np.uint8)
    return Image.fromarray(arr)

def fx_oil_paint(img):
    """Simulate oil painting via heavy median filter."""
    alpha = img.split()[3]
    oil = img.convert("RGB").filter(ImageFilter.MedianFilter(7))
    oil = ImageEnhance.Color(oil).enhance(1.5)
    result = oil.convert("RGBA")
    result.putalpha(alpha)
    return result

def fx_watercolor(img):
    """Watercolor — blur + posterize + boost color."""
    alpha = img.split()[3]
    wc = img.convert("RGB").filter(ImageFilter.GaussianBlur(3))
    wc = ImageOps.posterize(wc, 4)
    wc = ImageEnhance.Color(wc).enhance(1.3)
    result = wc.convert("RGBA")
    result.putalpha(alpha)
    return result

def fx_comic_book(img):
    """Bold comic book style — high contrast + edges."""
    import numpy as np
    alpha = img.split()[3]
    rgb = img.convert("RGB")
    rgb = ImageEnhance.Contrast(rgb).enhance(2.0)
    rgb = ImageOps.posterize(rgb, 3)
    edges = rgb.filter(ImageFilter.FIND_EDGES)
    edges = ImageOps.invert(edges)
    arr_rgb = np.array(rgb).astype(float)
    arr_edge = np.array(edges).astype(float) / 255.0
    combined = (arr_rgb * arr_edge).astype(np.uint8)
    result = Image.fromarray(combined).convert("RGBA")
    result.putalpha(alpha)
    return result

def fx_pop_art(img):
    """Pop art — posterize + vibrant + dots pattern hint."""
    alpha = img.split()[3]
    rgb = img.convert("RGB")
    rgb = ImageOps.posterize(rgb, 2)
    rgb = ImageEnhance.Color(rgb).enhance(2.5)
    result = rgb.convert("RGBA")
    result.putalpha(alpha)
    return result

def fx_sketch(img):
    """Pencil sketch effect."""
    import numpy as np
    alpha_ch = img.split()[3]
    gray = img.convert("L")
    inv = ImageOps.invert(gray)
    blur = inv.filter(ImageFilter.GaussianBlur(21))
    arr_g = np.array(gray).astype(float)
    arr_b = np.array(blur).astype(float)
    sketch = np.clip(arr_g / (256 - arr_b + 1) * 256, 0, 255).astype(np.uint8)
    result = Image.fromarray(sketch).convert("RGBA")
    result.putalpha(alpha_ch)
    return result

def fx_halftone(img):
    """Simulated halftone dot pattern."""
    import numpy as np
    arr = np.array(img).copy()
    h, w = arr.shape[:2]
    dot_size = 4
    for y in range(0, h, dot_size):
        for x in range(0, w, dot_size):
            block = arr[y:y+dot_size, x:x+dot_size, :3]
            if block.size > 0:
                avg = block.mean(axis=(0, 1)).astype(np.uint8)
                arr[y:y+dot_size, x:x+dot_size, :3] = avg
    return Image.fromarray(arr)

def fx_noise_grain(img):
    """Film grain noise overlay."""
    import numpy as np
    arr = np.array(img).astype(float)
    noise = np.random.normal(0, 15, arr[:, :, :3].shape)
    arr[:, :, :3] = np.clip(arr[:, :, :3] + noise, 0, 255)
    return Image.fromarray(arr.astype(np.uint8))

def fx_glitch_h(img):
    """Horizontal glitch — shift random rows."""
    import numpy as np
    arr = np.array(img).copy()
    h = arr.shape[0]
    for _ in range(15):
        y = random.randint(0, h - 10)
        band = random.randint(2, 8)
        end = min(y + band, h)
        shift = random.randint(-30, 30)
        arr[y:end] = np.roll(arr[y:end], shift, axis=1)
    return Image.fromarray(arr)

def fx_glitch_rgb(img):
    """RGB channel split glitch."""
    import numpy as np
    arr = np.array(img).copy()
    result = np.zeros_like(arr)
    result[:, :, 0] = np.roll(arr[:, :, 0], 5, axis=1)  # red right
    result[:, :, 1] = arr[:, :, 1]  # green stays
    result[:, :, 2] = np.roll(arr[:, :, 2], -5, axis=1)  # blue left
    result[:, :, 3] = arr[:, :, 3]
    return Image.fromarray(result)

def fx_wave_sine(img):
    """Sine wave distortion."""
    import numpy as np
    arr = np.array(img)
    h, w = arr.shape[:2]
    result = np.zeros_like(arr)
    for y in range(h):
        shift = int(10 * math.sin(2 * math.pi * y / 60))
        result[y] = np.roll(arr[y], shift, axis=0)
    return Image.fromarray(result)

def fx_wave_vertical(img):
    """Vertical wave distortion."""
    import numpy as np
    arr = np.array(img)
    h, w = arr.shape[:2]
    result = np.zeros_like(arr)
    for x in range(w):
        shift = int(8 * math.sin(2 * math.pi * x / 50))
        result[:, x] = np.roll(arr[:, x], shift, axis=0)
    return Image.fromarray(result)

def fx_swirl(img):
    """Simple swirl distortion from center."""
    import numpy as np
    arr = np.array(img)
    h, w = arr.shape[:2]
    cy, cx = h / 2, w / 2
    result = np.zeros_like(arr)
    for y in range(h):
        for x in range(w):
            dx, dy = x - cx, y - cy
            dist = math.sqrt(dx * dx + dy * dy)
            angle = dist / 50.0
            cos_a, sin_a = math.cos(angle), math.sin(angle)
            src_x = int(cx + dx * cos_a - dy * sin_a)
            src_y = int(cy + dx * sin_a + dy * cos_a)
            if 0 <= src_x < w and 0 <= src_y < h:
                result[y, x] = arr[src_y, src_x]
    return Image.fromarray(result)

def fx_zoom_burst(img):
    """Radial zoom blur from center."""
    import numpy as np
    arr = np.array(img).astype(float)
    blur1 = np.array(img.resize((int(img.width * 0.95), int(img.height * 0.95)), Image.LANCZOS).resize(img.size, Image.LANCZOS)).astype(float)
    blended = np.clip(arr * 0.6 + blur1 * 0.4, 0, 255)
    blended[:, :, 3] = arr[:, :, 3]
    return Image.fromarray(blended.astype(np.uint8))

def fx_double_exposure(img):
    """Double exposure with offset self."""
    import numpy as np
    arr = np.array(img).astype(float)
    shifted = np.roll(arr, 20, axis=1)
    shifted = np.roll(shifted, 15, axis=0)
    blended = np.clip(arr * 0.6 + shifted * 0.5, 0, 255)
    blended[:, :, 3] = np.maximum(arr[:, :, 3], shifted[:, :, 3].astype(float))
    return Image.fromarray(blended.astype(np.uint8))

def fx_shadow_long(img):
    """Long dramatic shadow behind Mario."""
    import numpy as np
    arr = np.array(img)
    alpha = arr[:, :, 3]
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    # Create shadow from alpha channel
    shadow_layer = Image.new("RGBA", img.size, (30, 30, 30, 100))
    shadow_mask = Image.fromarray(alpha).filter(ImageFilter.GaussianBlur(5))
    shadow_offset = Image.new("RGBA", img.size, (0, 0, 0, 0))
    shadow_offset.paste(shadow_layer, (8, 12), shadow_mask)
    # Composite
    result = Image.alpha_composite(shadow_offset, img)
    return result

def fx_outline_black(img):
    """Thick black outline around Mario."""
    import numpy as np
    arr = np.array(img)
    alpha = arr[:, :, 3]
    # Dilate alpha to find outline area
    alpha_img = Image.fromarray(alpha)
    dilated = alpha_img.filter(ImageFilter.MaxFilter(7))
    dilated_arr = np.array(dilated)
    outline_mask = (dilated_arr > 128) & (alpha < 128)
    result = arr.copy()
    result[outline_mask, :3] = 0
    result[outline_mask, 3] = 255
    return Image.fromarray(result)

def fx_outline_white(img):
    """White outline around Mario."""
    import numpy as np
    arr = np.array(img)
    alpha = arr[:, :, 3]
    alpha_img = Image.fromarray(alpha)
    dilated = alpha_img.filter(ImageFilter.MaxFilter(7))
    dilated_arr = np.array(dilated)
    outline_mask = (dilated_arr > 128) & (alpha < 128)
    result = arr.copy()
    result[outline_mask, :3] = 255
    result[outline_mask, 3] = 255
    return Image.fromarray(result)

def fx_outline_gold(img):
    """Gold outline around Mario."""
    import numpy as np
    arr = np.array(img)
    alpha = arr[:, :, 3]
    alpha_img = Image.fromarray(alpha)
    dilated = alpha_img.filter(ImageFilter.MaxFilter(9))
    dilated_arr = np.array(dilated)
    outline_mask = (dilated_arr > 128) & (alpha < 128)
    result = arr.copy()
    result[outline_mask, 0] = 255
    result[outline_mask, 1] = 215
    result[outline_mask, 2] = 0
    result[outline_mask, 3] = 255
    return Image.fromarray(result)

def fx_scale_up_120(img):
    """120% scale."""
    w, h = img.size
    scaled = img.resize((int(w * 1.2), int(h * 1.2)), Image.LANCZOS)
    return fit_to_target(scaled)

def fx_scale_down_80(img):
    """80% scale — smaller Mario."""
    w, h = img.size
    scaled = img.resize((int(w * 0.8), int(h * 0.8)), Image.LANCZOS)
    return fit_to_target(scaled)

def fx_squish_wide(img):
    """Wide squished Mario."""
    w, h = img.size
    squished = img.resize((int(w * 1.4), int(h * 0.75)), Image.LANCZOS)
    return fit_to_target(squished)

def fx_stretch_tall(img):
    """Tall stretched Mario."""
    w, h = img.size
    stretched = img.resize((int(w * 0.75), int(h * 1.3)), Image.LANCZOS)
    return fit_to_target(stretched)

def fx_bg_red(img):
    """Red background."""
    bg = Image.new("RGBA", img.size, (220, 40, 40, 255))
    bg.paste(img, (0, 0), img)
    return bg

def fx_bg_blue(img):
    """Blue sky background."""
    bg = Image.new("RGBA", img.size, (100, 160, 255, 255))
    bg.paste(img, (0, 0), img)
    return bg

def fx_bg_green(img):
    """Green pipe background."""
    bg = Image.new("RGBA", img.size, (50, 180, 50, 255))
    bg.paste(img, (0, 0), img)
    return bg

def fx_bg_yellow(img):
    """Star power yellow background."""
    bg = Image.new("RGBA", img.size, (255, 220, 50, 255))
    bg.paste(img, (0, 0), img)
    return bg

def fx_bg_gradient_sunset(img):
    """Gradient sunset background."""
    import numpy as np
    w, h = img.size
    bg_arr = np.zeros((h, w, 4), dtype=np.uint8)
    for y in range(h):
        t = y / h
        bg_arr[y, :, 0] = int(255 * (1 - t * 0.3))
        bg_arr[y, :, 1] = int(100 + 100 * t)
        bg_arr[y, :, 2] = int(50 + 200 * t)
        bg_arr[y, :, 3] = 255
    bg = Image.fromarray(bg_arr)
    bg.paste(img, (0, 0), img)
    return bg

def fx_bg_gradient_night(img):
    """Gradient night sky background."""
    import numpy as np
    w, h = img.size
    bg_arr = np.zeros((h, w, 4), dtype=np.uint8)
    for y in range(h):
        t = y / h
        bg_arr[y, :, 0] = int(10 + 20 * t)
        bg_arr[y, :, 1] = int(10 + 30 * t)
        bg_arr[y, :, 2] = int(40 + 60 * t)
        bg_arr[y, :, 3] = 255
    bg = Image.fromarray(bg_arr)
    bg.paste(img, (0, 0), img)
    return bg

def fx_bg_checkerboard(img):
    """Checkerboard pattern background."""
    import numpy as np
    w, h = img.size
    bg_arr = np.zeros((h, w, 4), dtype=np.uint8)
    sq = 20
    for y in range(h):
        for x in range(w):
            if ((x // sq) + (y // sq)) % 2 == 0:
                bg_arr[y, x] = [200, 200, 200, 255]
            else:
                bg_arr[y, x] = [240, 240, 240, 255]
    bg = Image.fromarray(bg_arr)
    bg.paste(img, (0, 0), img)
    return bg

def fx_channel_red_only(img):
    """Red channel only."""
    import numpy as np
    arr = np.array(img).copy()
    arr[:, :, 1] = 0
    arr[:, :, 2] = 0
    return Image.fromarray(arr)

def fx_channel_green_only(img):
    """Green channel only."""
    import numpy as np
    arr = np.array(img).copy()
    arr[:, :, 0] = 0
    arr[:, :, 2] = 0
    return Image.fromarray(arr)

def fx_channel_blue_only(img):
    """Blue channel only."""
    import numpy as np
    arr = np.array(img).copy()
    arr[:, :, 0] = 0
    arr[:, :, 1] = 0
    return Image.fromarray(arr)

def fx_brightness_up(img):
    """Bright — +40%."""
    rgb = img.convert("RGB")
    rgb = ImageEnhance.Brightness(rgb).enhance(1.4)
    result = rgb.convert("RGBA")
    result.putalpha(img.split()[3])
    return result

def fx_brightness_down(img):
    """Dark — -30%."""
    rgb = img.convert("RGB")
    rgb = ImageEnhance.Brightness(rgb).enhance(0.7)
    result = rgb.convert("RGBA")
    result.putalpha(img.split()[3])
    return result

def fx_solarize(img):
    """Solarize effect."""
    alpha = img.split()[3]
    sol = ImageOps.solarize(img.convert("RGB"), threshold=128)
    result = sol.convert("RGBA")
    result.putalpha(alpha)
    return result

def fx_quantize_16(img):
    """Reduce to 16 colors."""
    alpha = img.split()[3]
    q = img.convert("RGB").quantize(colors=16, method=Image.Quantize.MEDIANCUT)
    result = q.convert("RGBA")
    result.putalpha(alpha)
    return result

def fx_quantize_8(img):
    """Reduce to 8 colors — NES style."""
    alpha = img.split()[3]
    q = img.convert("RGB").quantize(colors=8, method=Image.Quantize.MEDIANCUT)
    result = q.convert("RGBA")
    result.putalpha(alpha)
    return result

def fx_gameboy(img):
    """GameBoy 4-shade green palette."""
    import numpy as np
    arr = np.array(img)
    gray = np.mean(arr[:, :, :3], axis=2)
    # 4 shades of green
    shades = [(15, 56, 15), (48, 98, 48), (139, 172, 15), (155, 188, 15)]
    result = np.zeros_like(arr)
    for i, (lo, hi) in enumerate([(0, 64), (64, 128), (128, 192), (192, 256)]):
        mask = (gray >= lo) & (gray < hi)
        result[mask, :3] = shades[i]
    result[:, :, 3] = arr[:, :, 3]
    return Image.fromarray(result)

def fx_super_saiyan(img):
    """Golden glow — Super Saiyan Mario!"""
    import numpy as np
    arr = np.array(img).astype(float)
    # Yellow-gold shift
    arr[:, :, 0] = np.clip(arr[:, :, 0] * 1.3, 0, 255)
    arr[:, :, 1] = np.clip(arr[:, :, 1] * 1.2, 0, 255)
    arr[:, :, 2] *= 0.4
    # Add glow
    result = Image.fromarray(arr.astype(np.uint8))
    glow = result.filter(ImageFilter.GaussianBlur(10))
    glow_arr = np.array(glow).astype(float)
    arr2 = np.array(result).astype(float)
    blended = np.clip(arr2 * 0.7 + glow_arr * 0.4, 0, 255)
    blended[:, :, 3] = np.array(img)[:, :, 3].astype(float)
    return Image.fromarray(blended.astype(np.uint8))

def fx_star_power(img):
    """Star power — flashing rainbow tint with glow."""
    import numpy as np
    arr = np.array(img).astype(float)
    h, w = arr.shape[:2]
    for y in range(h):
        phase = (y / h) * 2 * math.pi
        arr[y, :, 0] = np.clip(arr[y, :, 0] + 40 * math.sin(phase), 0, 255)
        arr[y, :, 1] = np.clip(arr[y, :, 1] + 40 * math.sin(phase + 2.1), 0, 255)
        arr[y, :, 2] = np.clip(arr[y, :, 2] + 40 * math.sin(phase + 4.2), 0, 255)
    result = Image.fromarray(arr.astype(np.uint8))
    glow = result.filter(ImageFilter.GaussianBlur(6))
    glow_arr = np.array(glow).astype(float)
    arr2 = np.array(result).astype(float)
    blended = np.clip(arr2 * 0.7 + glow_arr * 0.4, 0, 255)
    blended[:, :, 3] = np.array(img)[:, :, 3].astype(float)
    return Image.fromarray(blended.astype(np.uint8))

def fx_fire_mario(img):
    """Fire Mario — white hat, red overalls tint."""
    import numpy as np
    arr = np.array(img).astype(float)
    # Shift reds toward white, blues toward red
    red_mask = (arr[:, :, 0] > 150) & (arr[:, :, 1] < 100) & (arr[:, :, 2] < 100) & (arr[:, :, 3] > 128)
    blue_mask = (arr[:, :, 2] > 100) & (arr[:, :, 0] < 100) & (arr[:, :, 3] > 128)
    arr[red_mask, :3] = [255, 255, 255]  # red → white
    arr[blue_mask, 0] = 220  # blue → reddish
    arr[blue_mask, 1] = 50
    arr[blue_mask, 2] = 50
    return Image.fromarray(arr.astype(np.uint8))

def fx_ice_mario(img):
    """Ice Mario — cyan/white palette."""
    import numpy as np
    arr = np.array(img).astype(float)
    # Cool everything down
    arr[:, :, 0] = np.clip(arr[:, :, 0] * 0.6, 0, 255)
    arr[:, :, 1] = np.clip(arr[:, :, 1] * 0.9 + 30, 0, 255)
    arr[:, :, 2] = np.clip(arr[:, :, 2] * 1.3 + 40, 0, 255)
    return Image.fromarray(arr.astype(np.uint8))

def fx_shadow_mario(img):
    """Shadow/dark Mario — very dark with glowing eyes hint."""
    import numpy as np
    arr = np.array(img).astype(float)
    arr[:, :, :3] *= 0.25
    return Image.fromarray(arr.astype(np.uint8))

def fx_ghost_mario(img):
    """Ghost Mario — semi-transparent, blue-white tint."""
    import numpy as np
    arr = np.array(img).astype(float)
    arr[:, :, :3] = arr[:, :, :3] * 0.4 + 180
    arr[:, :, 3] = arr[:, :, 3] * 0.5
    return Image.fromarray(arr.astype(np.uint8))

def fx_metal_mario(img):
    """Metal Mario — silver/steel look."""
    import numpy as np
    arr = np.array(img).astype(float)
    gray = np.mean(arr[:, :, :3], axis=2, keepdims=True)
    metallic = gray * 0.7 + arr[:, :, :3] * 0.3
    metallic = np.clip(metallic * 1.2, 0, 255)
    arr[:, :, :3] = metallic
    return Image.fromarray(arr.astype(np.uint8))

def fx_8bit_nes(img):
    """NES-style with limited palette and heavy pixelation."""
    w, h = img.size
    alpha = img.split()[3]
    small = img.resize((w // 10, h // 10), Image.NEAREST)
    small = ImageOps.posterize(small.convert("RGB"), 2)
    big = small.resize((w, h), Image.NEAREST).convert("RGBA")
    big.putalpha(alpha)
    return big

def fx_snes_16bit(img):
    """SNES 16-bit style — moderate pixelation, more colors."""
    w, h = img.size
    alpha = img.split()[3]
    small = img.resize((w // 6, h // 6), Image.NEAREST)
    small = ImageOps.posterize(small.convert("RGB"), 4)
    big = small.resize((w, h), Image.NEAREST).convert("RGBA")
    big.putalpha(alpha)
    return big

def fx_n64_low_poly(img):
    """N64 style — blocky with slight blur and limited colors."""
    w, h = img.size
    alpha = img.split()[3]
    small = img.resize((w // 4, h // 4), Image.BILINEAR)
    small = ImageOps.posterize(small.convert("RGB"), 5)
    big = small.resize((w, h), Image.BILINEAR).convert("RGBA")
    big.putalpha(alpha)
    return big

def fx_chromatic_aberration(img):
    """Strong chromatic aberration — RGB offset."""
    import numpy as np
    arr = np.array(img).copy()
    result = np.zeros_like(arr)
    result[:, :, 0] = np.roll(arr[:, :, 0], 8, axis=1)
    result[:, :, 1] = arr[:, :, 1]
    result[:, :, 2] = np.roll(arr[:, :, 2], -8, axis=1)
    result[:, :, 3] = arr[:, :, 3]
    return Image.fromarray(result)

def fx_tilt_shift(img):
    """Tilt-shift miniature effect — sharp center, blurry top/bottom."""
    import numpy as np
    alpha = img.split()[3]
    blurred = img.filter(ImageFilter.GaussianBlur(6))
    arr_sharp = np.array(img).astype(float)
    arr_blur = np.array(blurred).astype(float)
    h = arr_sharp.shape[0]
    mask = np.zeros((h, 1, 1))
    center = h // 2
    band = h // 4
    for y in range(h):
        dist = abs(y - center)
        if dist < band:
            mask[y] = 1.0
        else:
            mask[y] = max(0, 1.0 - (dist - band) / (h / 4))
    result = arr_sharp * mask + arr_blur * (1 - mask)
    result = np.clip(result, 0, 255).astype(np.uint8)
    result_img = Image.fromarray(result)
    result_img.putalpha(alpha)
    return result_img

def fx_cross_process(img):
    """Cross-processed film look."""
    import numpy as np
    arr = np.array(img).astype(float)
    # Boost greens, shift blues toward cyan, warm reds
    arr[:, :, 0] = np.clip(arr[:, :, 0] * 1.1 + 10, 0, 255)
    arr[:, :, 1] = np.clip(arr[:, :, 1] * 1.3, 0, 255)
    arr[:, :, 2] = np.clip(arr[:, :, 2] * 0.8 + 20, 0, 255)
    return Image.fromarray(arr.astype(np.uint8))

def fx_vintage_film(img):
    """Vintage film — yellow tint, low contrast, grain."""
    import numpy as np
    arr = np.array(img).astype(float)
    # Low contrast
    arr[:, :, :3] = arr[:, :, :3] * 0.7 + 40
    # Yellow tint
    arr[:, :, 0] = np.clip(arr[:, :, 0] + 15, 0, 255)
    arr[:, :, 1] = np.clip(arr[:, :, 1] + 10, 0, 255)
    arr[:, :, 2] = np.clip(arr[:, :, 2] - 20, 0, 255)
    # Grain
    noise = np.random.normal(0, 8, arr[:, :, :3].shape)
    arr[:, :, :3] = np.clip(arr[:, :, :3] + noise, 0, 255)
    return Image.fromarray(arr.astype(np.uint8))

def fx_contour(img):
    """Contour lines effect."""
    alpha = img.split()[3]
    contour = img.convert("RGB").filter(ImageFilter.CONTOUR)
    result = contour.convert("RGBA")
    result.putalpha(alpha)
    return result

def fx_detail_enhance(img):
    """Enhanced detail."""
    alpha = img.split()[3]
    detail = img.convert("RGB").filter(ImageFilter.DETAIL)
    detail = ImageEnhance.Sharpness(detail).enhance(2.0)
    result = detail.convert("RGBA")
    result.putalpha(alpha)
    return result

def fx_smooth(img):
    """Heavy smooth."""
    alpha = img.split()[3]
    smooth = img.convert("RGB").filter(ImageFilter.SMOOTH_MORE)
    result = smooth.convert("RGBA")
    result.putalpha(alpha)
    return result

def fx_wario_colors(img):
    """Wario palette swap — yellow hat, purple overalls."""
    import numpy as np
    arr = np.array(img).astype(float)
    # Shift reds to yellow, blues to purple
    red_mask = (arr[:, :, 0] > 150) & (arr[:, :, 1] < 120) & (arr[:, :, 2] < 120) & (arr[:, :, 3] > 128)
    blue_mask = (arr[:, :, 2] > 100) & (arr[:, :, 0] < 120) & (arr[:, :, 3] > 128)
    arr[red_mask, 0] = 255
    arr[red_mask, 1] = 220
    arr[red_mask, 2] = 0
    arr[blue_mask, 0] = 120
    arr[blue_mask, 1] = 0
    arr[blue_mask, 2] = 180
    return Image.fromarray(arr.astype(np.uint8))

def fx_luigi_colors(img):
    """Luigi palette swap — green hat, dark blue overalls."""
    import numpy as np
    arr = np.array(img).astype(float)
    red_mask = (arr[:, :, 0] > 150) & (arr[:, :, 1] < 120) & (arr[:, :, 2] < 120) & (arr[:, :, 3] > 128)
    arr[red_mask, 0] = 30
    arr[red_mask, 1] = 200
    arr[red_mask, 2] = 30
    return Image.fromarray(arr.astype(np.uint8))

def fx_waluigi_colors(img):
    """Waluigi palette — purple hat, black overalls."""
    import numpy as np
    arr = np.array(img).astype(float)
    red_mask = (arr[:, :, 0] > 150) & (arr[:, :, 1] < 120) & (arr[:, :, 2] < 120) & (arr[:, :, 3] > 128)
    blue_mask = (arr[:, :, 2] > 100) & (arr[:, :, 0] < 120) & (arr[:, :, 3] > 128)
    arr[red_mask, 0] = 130
    arr[red_mask, 1] = 0
    arr[red_mask, 2] = 200
    arr[blue_mask, :3] = [30, 30, 30]
    return Image.fromarray(arr.astype(np.uint8))

def fx_tiny_planet(img):
    """Tiny/chibi scale with big head feel."""
    import numpy as np
    w, h = img.size
    top_half = img.crop((0, 0, w, h // 2))
    bot_half = img.crop((0, h // 2, w, h))
    top_scaled = top_half.resize((int(w * 1.3), int(h * 0.55)), Image.LANCZOS)
    bot_scaled = bot_half.resize((int(w * 0.8), int(h * 0.35)), Image.LANCZOS)
    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    tx = (w - top_scaled.width) // 2
    bx = (w - bot_scaled.width) // 2
    canvas.paste(top_scaled, (tx, 0), top_scaled)
    canvas.paste(bot_scaled, (bx, int(h * 0.55)), bot_scaled)
    return canvas


# Master list of all 100 effects
ALL_EFFECTS = [
    ("001_original", fx_original),
    ("002_vibrant", fx_vibrant),
    ("003_pastel", fx_pastel),
    ("004_neon_glow", fx_neon_glow),
    ("005_retro_crt", fx_retro_crt),
    ("006_sepia", fx_sepia),
    ("007_ice_blue", fx_ice_blue),
    ("008_fire_red", fx_fire_red),
    ("009_golden", fx_golden),
    ("010_purple_haze", fx_purple_haze),
    ("011_matrix_green", fx_matrix_green),
    ("012_high_contrast", fx_high_contrast),
    ("013_low_contrast", fx_low_contrast),
    ("014_sharpen", fx_sharpen),
    ("015_soft_blur", fx_soft_blur),
    ("016_emboss", fx_emboss),
    ("017_edge_detect", fx_edge_detect),
    ("018_posterize_4", fx_posterize_4),
    ("019_posterize_8", fx_posterize_8),
    ("020_invert", fx_invert),
    ("021_mirror_h", fx_mirror_h),
    ("022_flip_v", fx_flip_v),
    ("023_rotate_15", fx_rotate_15),
    ("024_rotate_neg15", fx_rotate_neg15),
    ("025_rotate_45", fx_rotate_45),
    ("026_pixel_8", fx_pixel_8),
    ("027_pixel_4", fx_pixel_4),
    ("028_pixel_16", fx_pixel_16),
    ("029_vignette", fx_vignette),
    ("030_spotlight", fx_spotlight),
    ("031_rainbow_shift", fx_rainbow_shift),
    ("032_hue_shift_60", fx_hue_shift_60),
    ("033_hue_shift_120", fx_hue_shift_120),
    ("034_hue_shift_180", fx_hue_shift_180),
    ("035_grayscale", fx_grayscale),
    ("036_duotone_red_blue", fx_duotone_red_blue),
    ("037_duotone_orange_teal", fx_duotone_orange_teal),
    ("038_thermal", fx_thermal),
    ("039_xray", fx_xray),
    ("040_oil_paint", fx_oil_paint),
    ("041_watercolor", fx_watercolor),
    ("042_comic_book", fx_comic_book),
    ("043_pop_art", fx_pop_art),
    ("044_sketch", fx_sketch),
    ("045_halftone", fx_halftone),
    ("046_noise_grain", fx_noise_grain),
    ("047_glitch_h", fx_glitch_h),
    ("048_glitch_rgb", fx_glitch_rgb),
    ("049_wave_sine", fx_wave_sine),
    ("050_wave_vertical", fx_wave_vertical),
    ("051_swirl", fx_swirl),
    ("052_zoom_burst", fx_zoom_burst),
    ("053_double_exposure", fx_double_exposure),
    ("054_shadow_long", fx_shadow_long),
    ("055_outline_black", fx_outline_black),
    ("056_outline_white", fx_outline_white),
    ("057_outline_gold", fx_outline_gold),
    ("058_scale_up_120", fx_scale_up_120),
    ("059_scale_down_80", fx_scale_down_80),
    ("060_squish_wide", fx_squish_wide),
    ("061_stretch_tall", fx_stretch_tall),
    ("062_bg_red", fx_bg_red),
    ("063_bg_blue", fx_bg_blue),
    ("064_bg_green", fx_bg_green),
    ("065_bg_yellow", fx_bg_yellow),
    ("066_bg_gradient_sunset", fx_bg_gradient_sunset),
    ("067_bg_gradient_night", fx_bg_gradient_night),
    ("068_bg_checkerboard", fx_bg_checkerboard),
    ("069_channel_red_only", fx_channel_red_only),
    ("070_channel_green_only", fx_channel_green_only),
    ("071_channel_blue_only", fx_channel_blue_only),
    ("072_brightness_up", fx_brightness_up),
    ("073_brightness_down", fx_brightness_down),
    ("074_solarize", fx_solarize),
    ("075_quantize_16", fx_quantize_16),
    ("076_quantize_8", fx_quantize_8),
    ("077_gameboy", fx_gameboy),
    ("078_super_saiyan", fx_super_saiyan),
    ("079_star_power", fx_star_power),
    ("080_fire_mario", fx_fire_mario),
    ("081_ice_mario", fx_ice_mario),
    ("082_shadow_mario", fx_shadow_mario),
    ("083_ghost_mario", fx_ghost_mario),
    ("084_metal_mario", fx_metal_mario),
    ("085_8bit_nes", fx_8bit_nes),
    ("086_snes_16bit", fx_snes_16bit),
    ("087_n64_low_poly", fx_n64_low_poly),
    ("088_chromatic_aberration", fx_chromatic_aberration),
    ("089_tilt_shift", fx_tilt_shift),
    ("090_cross_process", fx_cross_process),
    ("091_vintage_film", fx_vintage_film),
    ("092_contour", fx_contour),
    ("093_detail_enhance", fx_detail_enhance),
    ("094_smooth", fx_smooth),
    ("095_wario_colors", fx_wario_colors),
    ("096_luigi_colors", fx_luigi_colors),
    ("097_waluigi_colors", fx_waluigi_colors),
    ("098_tiny_planet", fx_tiny_planet),
    ("099_comic_neon", lambda img: fx_neon_glow(fx_comic_book(img))),
    ("100_star_sketch", lambda img: fx_star_power(fx_sketch(img))),
]


def generate_index_html(output_dir, source_names, effects):
    """Generate an HTML gallery for browsing all iterations."""
    html_parts = ["""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Mario 3D Assets — 100 Iterations Gallery</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { background: #1a1a2e; color: #eee; font-family: 'Segoe UI', Arial, sans-serif; padding: 20px; }
  h1 { text-align: center; color: #e63946; font-size: 2.5em; margin-bottom: 10px;
       text-shadow: 2px 2px 4px rgba(0,0,0,0.5); }
  h2 { color: #f1faee; margin: 30px 0 15px; border-bottom: 2px solid #457b9d; padding-bottom: 8px; }
  .subtitle { text-align: center; color: #a8dadc; margin-bottom: 30px; font-size: 1.1em; }
  .controls { text-align: center; margin: 20px 0; }
  .controls select { padding: 8px 16px; font-size: 1em; border-radius: 8px; border: none;
                      background: #457b9d; color: white; cursor: pointer; margin: 0 5px; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
           gap: 15px; margin: 20px 0; }
  .card { background: #16213e; border-radius: 12px; overflow: hidden; transition: transform 0.2s;
           box-shadow: 0 4px 8px rgba(0,0,0,0.3); }
  .card:hover { transform: scale(1.05); box-shadow: 0 8px 16px rgba(0,0,0,0.5); }
  .card img { width: 100%; height: 260px; object-fit: contain; background: #0f3460;
              padding: 10px; image-rendering: auto; }
  .card .label { padding: 10px; text-align: center; font-size: 0.85em; color: #a8dadc;
                  background: #1a1a2e; }
  .source-section { margin: 30px 0; padding: 20px; background: #16213e; border-radius: 12px; }
  .stats { text-align: center; color: #a8dadc; margin: 15px 0; font-size: 1.1em; }
  .filter-row { display: flex; justify-content: center; gap: 10px; flex-wrap: wrap; margin: 15px 0; }
  .filter-btn { padding: 6px 14px; border: 1px solid #457b9d; border-radius: 20px;
                 background: transparent; color: #a8dadc; cursor: pointer; font-size: 0.85em; }
  .filter-btn.active { background: #457b9d; color: white; }
  .filter-btn:hover { background: #457b9d; color: white; }
</style>
</head>
<body>
<h1>🍄 Mario 3D Assets — 100 Iterations</h1>
<p class="subtitle">Each source image × 100 unique visual effects</p>
"""]

    total_images = len(source_names) * len(effects)
    html_parts.append(f'<p class="stats">📊 {len(source_names)} source images × {len(effects)} effects = {total_images} total outputs</p>\n')

    # Source filter
    html_parts.append('<div class="controls">\n')
    html_parts.append('  <select id="sourceFilter" onchange="filterBySource()">\n')
    html_parts.append('    <option value="all">All Sources</option>\n')
    for sn in source_names:
        safe = sn.replace("'", "\\'")
        html_parts.append(f'    <option value="{safe}">{sn}</option>\n')
    html_parts.append('  </select>\n')
    html_parts.append('</div>\n')

    for sn in source_names:
        safe_id = sn.replace(".", "_").replace(" ", "_").replace("-", "_")
        html_parts.append(f'<div class="source-section" data-source="{sn}" id="section_{safe_id}">\n')
        html_parts.append(f'  <h2>📸 {sn}</h2>\n')
        html_parts.append(f'  <div class="grid">\n')
        for ename, _ in effects:
            fname = f"{sn}/{ename}.png"
            html_parts.append(f'    <div class="card">\n')
            html_parts.append(f'      <img src="{fname}" alt="{ename}" loading="lazy">\n')
            html_parts.append(f'      <div class="label">{ename}</div>\n')
            html_parts.append(f'    </div>\n')
        html_parts.append(f'  </div>\n')
        html_parts.append(f'</div>\n')

    html_parts.append("""
<script>
function filterBySource() {
  const val = document.getElementById('sourceFilter').value;
  document.querySelectorAll('.source-section').forEach(s => {
    s.style.display = (val === 'all' || s.dataset.source === val) ? 'block' : 'none';
  });
}
</script>
</body>
</html>""")

    html_path = output_dir / "index.html"
    html_path.write_text("".join(html_parts), encoding="utf-8")
    print(f"\n✅ Gallery: {html_path}")


def main():
    print("=" * 60)
    print("  MARIO 3D ASSETS — 100 ITERATION GENERATOR")
    print("=" * 60)

    # Load source images
    print(f"\n📂 Loading from {SOURCE_DIR}...")
    all_images = load_source_images()

    if not all_images:
        print("❌ No images found in mario_assets/!")
        sys.exit(1)

    print(f"\n📦 Loaded {len(all_images)} source images")

    # Prepare output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Process each source image
    processed_sources = []
    for name, src_img in all_images.items():
        print(f"\n{'─' * 50}")
        print(f"🖼️  Processing: {name}")

        # Prepare (remove background, crop, fit)
        mario = prepare_mario(src_img)

        # Create folder for this source
        src_folder = OUTPUT_DIR / name
        src_folder.mkdir(parents=True, exist_ok=True)

        # Apply all 100 effects
        success_count = 0
        for ename, efunc in ALL_EFFECTS:
            try:
                result = efunc(mario)
                out_path = src_folder / f"{ename}.png"
                result.save(str(out_path), "PNG")
                success_count += 1
            except Exception as e:
                print(f"  ⚠️  {ename}: {e}")

        print(f"  ✅ {success_count}/{len(ALL_EFFECTS)} effects applied")
        processed_sources.append(name)

    # Generate HTML gallery
    print("\n🌐 Generating index.html gallery...")
    generate_index_html(OUTPUT_DIR, processed_sources, ALL_EFFECTS)

    # Generate manifest
    manifest_path = OUTPUT_DIR / "manifest.txt"
    with open(manifest_path, "w") as f:
        f.write(f"Mario 3D Assets — 100 Iterations\n")
        f.write(f"{'=' * 40}\n\n")
        f.write(f"Sources: {len(processed_sources)}\n")
        f.write(f"Effects per source: {len(ALL_EFFECTS)}\n")
        f.write(f"Total outputs: {len(processed_sources) * len(ALL_EFFECTS)}\n\n")
        f.write(f"Source images:\n")
        for s in processed_sources:
            f.write(f"  - {s}\n")
        f.write(f"\nEffects:\n")
        for ename, efunc in ALL_EFFECTS:
            doc = efunc.__doc__ or "No description"
            f.write(f"  {ename}: {doc.strip()}\n")
    print(f"📋 Manifest: {manifest_path}")

    total = len(processed_sources) * len(ALL_EFFECTS)
    print(f"\n{'=' * 60}")
    print(f"  🎉 DONE! Generated {total} images across {len(processed_sources)} sources")
    print(f"  📂 Output: {OUTPUT_DIR}")
    print(f"  🌐 Open index.html to browse all iterations")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
