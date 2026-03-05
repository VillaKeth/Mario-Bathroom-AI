"""Generate 100 edited iterations of Mario 3D assets into mario_3d_assets/.

Hero sources:
  - Mario_New_Super_Mario_Bros_U_Deluxe.webp (full body standing)
  - zap9gpu6vj9e1.png (thinking close-up)

Each iteration applies a unique visual edit to every source image found
in mario_assets/, producing mario_3d_assets/iter_NNN/ folders with an
index.html gallery for quick comparison.
"""

from __future__ import annotations

import math
import os
import random
import re
import sys
from datetime import UTC, datetime
from typing import Any, Callable

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps

ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
INPUT_DIR = os.path.join(ROOT_DIR, "mario_assets")
OUTPUT_DIR = os.path.join(ROOT_DIR, "mario_3d_assets")

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}

HERO_STANDING = "Mario_New_Super_Mario_Bros_U_Deluxe.webp"
HERO_THINKING = "zap9gpu6vj9e1.png"

MAX_DIM = 512


def load_rgba(path: str) -> Image.Image:
    img = Image.open(path)
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    w, h = img.size
    if w > MAX_DIM or h > MAX_DIM:
        ratio = min(MAX_DIM / w, MAX_DIM / h)
        img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
    return img


def arr(img: Image.Image) -> np.ndarray:
    return np.array(img, dtype=np.float64)


def from_arr(a: np.ndarray) -> Image.Image:
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGBA")


# ── 100 EFFECT FUNCTIONS ──


def fx_identity(img: Image.Image) -> Image.Image:
    return img.copy()


def fx_brightness_up(img: Image.Image) -> Image.Image:
    return ImageEnhance.Brightness(img).enhance(1.35)


def fx_brightness_down(img: Image.Image) -> Image.Image:
    return ImageEnhance.Brightness(img).enhance(0.65)


def fx_contrast_up(img: Image.Image) -> Image.Image:
    return ImageEnhance.Contrast(img).enhance(1.6)


def fx_contrast_down(img: Image.Image) -> Image.Image:
    return ImageEnhance.Contrast(img).enhance(0.5)


def fx_saturate_up(img: Image.Image) -> Image.Image:
    return ImageEnhance.Color(img).enhance(1.8)


def fx_desaturate(img: Image.Image) -> Image.Image:
    return ImageEnhance.Color(img).enhance(0.2)


def fx_sharpen(img: Image.Image) -> Image.Image:
    return ImageEnhance.Sharpness(img).enhance(3.0)


def fx_blur_soft(img: Image.Image) -> Image.Image:
    return img.filter(ImageFilter.GaussianBlur(2))


def fx_blur_heavy(img: Image.Image) -> Image.Image:
    return img.filter(ImageFilter.GaussianBlur(5))


def fx_edge_enhance(img: Image.Image) -> Image.Image:
    return img.filter(ImageFilter.EDGE_ENHANCE_MORE)


def fx_emboss(img: Image.Image) -> Image.Image:
    return img.filter(ImageFilter.EMBOSS)


def fx_contour(img: Image.Image) -> Image.Image:
    return img.filter(ImageFilter.CONTOUR)


def fx_find_edges(img: Image.Image) -> Image.Image:
    return img.filter(ImageFilter.FIND_EDGES)


def fx_invert(img: Image.Image) -> Image.Image:
    a = arr(img)
    a[:, :, :3] = 255 - a[:, :, :3]
    return from_arr(a)


def fx_flip_h(img: Image.Image) -> Image.Image:
    return ImageOps.mirror(img)


def fx_flip_v(img: Image.Image) -> Image.Image:
    return ImageOps.flip(img)


def fx_rotate_15(img: Image.Image) -> Image.Image:
    return img.rotate(15, expand=True, fillcolor=(0, 0, 0, 0))


def fx_rotate_neg15(img: Image.Image) -> Image.Image:
    return img.rotate(-15, expand=True, fillcolor=(0, 0, 0, 0))


def fx_rotate_45(img: Image.Image) -> Image.Image:
    return img.rotate(45, expand=True, fillcolor=(0, 0, 0, 0))


def fx_rotate_90(img: Image.Image) -> Image.Image:
    return img.rotate(90, expand=True, fillcolor=(0, 0, 0, 0))


def fx_pixelate_small(img: Image.Image) -> Image.Image:
    w, h = img.size
    s = img.resize((max(1, w // 4), max(1, h // 4)), Image.NEAREST)
    return s.resize((w, h), Image.NEAREST)


def fx_pixelate_heavy(img: Image.Image) -> Image.Image:
    w, h = img.size
    s = img.resize((max(1, w // 8), max(1, h // 8)), Image.NEAREST)
    return s.resize((w, h), Image.NEAREST)


def fx_posterize_4(img: Image.Image) -> Image.Image:
    a = arr(img)
    a[:, :, :3] = (a[:, :, :3] // 64) * 64
    return from_arr(a)


def fx_posterize_8(img: Image.Image) -> Image.Image:
    a = arr(img)
    a[:, :, :3] = (a[:, :, :3] // 32) * 32
    return from_arr(a)


def fx_sepia(img: Image.Image) -> Image.Image:
    a = arr(img)
    r, g, b = a[:, :, 0], a[:, :, 1], a[:, :, 2]
    tr = 0.393 * r + 0.769 * g + 0.189 * b
    tg = 0.349 * r + 0.686 * g + 0.168 * b
    tb = 0.272 * r + 0.534 * g + 0.131 * b
    a[:, :, 0] = np.clip(tr, 0, 255)
    a[:, :, 1] = np.clip(tg, 0, 255)
    a[:, :, 2] = np.clip(tb, 0, 255)
    return from_arr(a)


def fx_red_channel(img: Image.Image) -> Image.Image:
    a = arr(img)
    a[:, :, 1] = 0
    a[:, :, 2] = 0
    return from_arr(a)


def fx_green_channel(img: Image.Image) -> Image.Image:
    a = arr(img)
    a[:, :, 0] = 0
    a[:, :, 2] = 0
    return from_arr(a)


def fx_blue_channel(img: Image.Image) -> Image.Image:
    a = arr(img)
    a[:, :, 0] = 0
    a[:, :, 1] = 0
    return from_arr(a)


def fx_swap_rg(img: Image.Image) -> Image.Image:
    a = arr(img)
    a[:, :, 0], a[:, :, 1] = a[:, :, 1].copy(), a[:, :, 0].copy()
    return from_arr(a)


def fx_swap_rb(img: Image.Image) -> Image.Image:
    a = arr(img)
    a[:, :, 0], a[:, :, 2] = a[:, :, 2].copy(), a[:, :, 0].copy()
    return from_arr(a)


def fx_swap_gb(img: Image.Image) -> Image.Image:
    a = arr(img)
    a[:, :, 1], a[:, :, 2] = a[:, :, 2].copy(), a[:, :, 1].copy()
    return from_arr(a)


def fx_neon_pop(img: Image.Image) -> Image.Image:
    a = arr(img)
    rgb = a[:, :, :3]
    o = np.zeros_like(rgb)
    o[:, :, 0] = np.clip(rgb[:, :, 2] * 1.3 + rgb[:, :, 0] * 0.15, 0, 255)
    o[:, :, 1] = np.clip(rgb[:, :, 0] * 0.6 + rgb[:, :, 1] * 0.8, 0, 255)
    o[:, :, 2] = np.clip(rgb[:, :, 1] * 0.7 + rgb[:, :, 2] * 0.75, 0, 255)
    a[:, :, :3] = o
    return from_arr(a)


def fx_rgb_shift(img: Image.Image) -> Image.Image:
    a = arr(img)
    o = a.copy()
    o[:, :, 0] = np.roll(a[:, :, 0], 6, axis=1)
    o[:, :, 1] = np.roll(a[:, :, 1], -4, axis=0)
    o[:, :, 2] = np.roll(a[:, :, 2], 3, axis=1)
    return from_arr(o)


def fx_sine_wave(img: Image.Image) -> Image.Image:
    a = arr(img)
    h, w, c = a.shape
    o = np.zeros_like(a)
    for y in range(h):
        shift = int(10 * math.sin(y / 12.0))
        o[y] = np.roll(a[y], shift, axis=0)
    return from_arr(o)


def fx_scanlines(img: Image.Image) -> Image.Image:
    a = arr(img)
    a[::2, :, :3] *= 0.6
    return from_arr(a)


def fx_scanlines_thick(img: Image.Image) -> Image.Image:
    a = arr(img)
    h = a.shape[0]
    for y in range(0, h, 4):
        a[y:min(y + 2, h), :, :3] *= 0.4
    return from_arr(a)


def fx_vignette(img: Image.Image) -> Image.Image:
    a = arr(img)
    h, w = a.shape[:2]
    cy, cx = h / 2, w / 2
    Y, X = np.ogrid[:h, :w]
    dist = np.sqrt((X - cx) ** 2 + (Y - cy) ** 2) / max(cx, cy)
    mask = np.clip(1.0 - dist * 0.7, 0, 1)
    a[:, :, :3] *= mask[:, :, np.newaxis]
    return from_arr(a)


def fx_duotone_hot(img: Image.Image) -> Image.Image:
    a = arr(img)
    gray = np.mean(a[:, :, :3], axis=2) / 255.0
    cold = np.array([30, 12, 96])
    hot = np.array([255, 140, 36])
    mapped = cold + (hot - cold) * gray[:, :, np.newaxis]
    a[:, :, :3] = mapped
    return from_arr(a)


def fx_duotone_ice(img: Image.Image) -> Image.Image:
    a = arr(img)
    gray = np.mean(a[:, :, :3], axis=2) / 255.0
    cold = np.array([10, 20, 60])
    hot = np.array([180, 220, 255])
    mapped = cold + (hot - cold) * gray[:, :, np.newaxis]
    a[:, :, :3] = mapped
    return from_arr(a)


def fx_duotone_fire(img: Image.Image) -> Image.Image:
    a = arr(img)
    gray = np.mean(a[:, :, :3], axis=2) / 255.0
    cold = np.array([40, 0, 0])
    hot = np.array([255, 220, 50])
    mapped = cold + (hot - cold) * gray[:, :, np.newaxis]
    a[:, :, :3] = mapped
    return from_arr(a)


def fx_duotone_toxic(img: Image.Image) -> Image.Image:
    a = arr(img)
    gray = np.mean(a[:, :, :3], axis=2) / 255.0
    cold = np.array([10, 30, 10])
    hot = np.array([60, 255, 80])
    mapped = cold + (hot - cold) * gray[:, :, np.newaxis]
    a[:, :, :3] = mapped
    return from_arr(a)


def fx_duotone_purple(img: Image.Image) -> Image.Image:
    a = arr(img)
    gray = np.mean(a[:, :, :3], axis=2) / 255.0
    cold = np.array([20, 0, 40])
    hot = np.array([220, 120, 255])
    mapped = cold + (hot - cold) * gray[:, :, np.newaxis]
    a[:, :, :3] = mapped
    return from_arr(a)


def fx_gameboy(img: Image.Image) -> Image.Image:
    a = arr(img)
    gray = np.mean(a[:, :, :3], axis=2)
    pal = np.array([[15, 56, 15], [48, 98, 48], [139, 172, 15], [155, 188, 15]])
    idx = np.clip((gray / 64).astype(int), 0, 3)
    a[:, :, :3] = pal[idx]
    return from_arr(a)


def fx_thermal(img: Image.Image) -> Image.Image:
    a = arr(img)
    gray = np.mean(a[:, :, :3], axis=2) / 255.0
    r = np.clip(gray * 3 * 255, 0, 255)
    g = np.clip((gray - 0.33) * 3 * 255, 0, 255)
    b = np.clip((gray - 0.66) * 3 * 255, 0, 255)
    a[:, :, 0] = r
    a[:, :, 1] = g
    a[:, :, 2] = b
    return from_arr(a)


def fx_solarize(img: Image.Image) -> Image.Image:
    a = arr(img)
    mask = a[:, :, :3] > 128
    a[:, :, :3][mask] = 255 - a[:, :, :3][mask]
    return from_arr(a)


def fx_solarize_low(img: Image.Image) -> Image.Image:
    a = arr(img)
    mask = a[:, :, :3] < 128
    a[:, :, :3][mask] = 255 - a[:, :, :3][mask]
    return from_arr(a)


def fx_edge_glow(img: Image.Image) -> Image.Image:
    a = arr(img)
    rgb = a[:, :, :3]
    h, w, _ = rgb.shape
    edges = np.zeros((h, w))
    edges[:, 1:] = np.maximum(edges[:, 1:], np.max(np.abs(rgb[:, 1:] - rgb[:, :-1]), axis=2))
    edges[1:, :] = np.maximum(edges[1:, :], np.max(np.abs(rgb[1:, :] - rgb[:-1, :]), axis=2))
    mask = edges > 40
    a[mask, 0] = np.clip(a[mask, 0] + 140, 0, 255)
    a[mask, 1] = np.clip(a[mask, 1] + 140, 0, 255)
    a[mask, 2] = np.clip(a[mask, 2] + 50, 0, 255)
    return from_arr(a)


def fx_kaleido(img: Image.Image) -> Image.Image:
    a = arr(img)
    h, w = a.shape[:2]
    hh, hw = max(1, h // 2), max(1, w // 2)
    q = a[:hh, :hw]
    top = np.concatenate([q, np.flip(q, axis=1)], axis=1)
    full = np.concatenate([top, np.flip(top, axis=0)], axis=0)
    return Image.fromarray(np.clip(full, 0, 255).astype(np.uint8), "RGBA").resize((w, h), Image.LANCZOS)


def fx_glitch_block(img: Image.Image) -> Image.Image:
    a = arr(img)
    h, w = a.shape[:2]
    rng = random.Random(42)
    for _ in range(20):
        y1 = rng.randint(0, h - 10)
        bh = rng.randint(3, 15)
        shift = rng.randint(-30, 30)
        a[y1:y1 + bh] = np.roll(a[y1:y1 + bh], shift, axis=1)
    return from_arr(a)


def fx_glitch_color(img: Image.Image) -> Image.Image:
    a = arr(img)
    h, w = a.shape[:2]
    rng = random.Random(99)
    for _ in range(15):
        y1 = rng.randint(0, h - 8)
        bh = rng.randint(2, 10)
        ch = rng.randint(0, 2)
        a[y1:y1 + bh, :, ch] = np.roll(a[y1:y1 + bh, :, ch], rng.randint(-20, 20), axis=1)
    return from_arr(a)


def fx_noise_light(img: Image.Image) -> Image.Image:
    a = arr(img)
    rng = np.random.RandomState(12)
    noise = rng.normal(0, 15, a[:, :, :3].shape)
    a[:, :, :3] = np.clip(a[:, :, :3] + noise, 0, 255)
    return from_arr(a)


def fx_noise_heavy(img: Image.Image) -> Image.Image:
    a = arr(img)
    rng = np.random.RandomState(34)
    noise = rng.normal(0, 40, a[:, :, :3].shape)
    a[:, :, :3] = np.clip(a[:, :, :3] + noise, 0, 255)
    return from_arr(a)


def fx_tint_red(img: Image.Image) -> Image.Image:
    a = arr(img)
    a[:, :, 0] = np.clip(a[:, :, 0] + 60, 0, 255)
    return from_arr(a)


def fx_tint_blue(img: Image.Image) -> Image.Image:
    a = arr(img)
    a[:, :, 2] = np.clip(a[:, :, 2] + 60, 0, 255)
    return from_arr(a)


def fx_tint_green(img: Image.Image) -> Image.Image:
    a = arr(img)
    a[:, :, 1] = np.clip(a[:, :, 1] + 60, 0, 255)
    return from_arr(a)


def fx_tint_yellow(img: Image.Image) -> Image.Image:
    a = arr(img)
    a[:, :, 0] = np.clip(a[:, :, 0] + 50, 0, 255)
    a[:, :, 1] = np.clip(a[:, :, 1] + 50, 0, 255)
    return from_arr(a)


def fx_tint_pink(img: Image.Image) -> Image.Image:
    a = arr(img)
    a[:, :, 0] = np.clip(a[:, :, 0] + 50, 0, 255)
    a[:, :, 2] = np.clip(a[:, :, 2] + 30, 0, 255)
    return from_arr(a)


def fx_tint_cyan(img: Image.Image) -> Image.Image:
    a = arr(img)
    a[:, :, 1] = np.clip(a[:, :, 1] + 40, 0, 255)
    a[:, :, 2] = np.clip(a[:, :, 2] + 50, 0, 255)
    return from_arr(a)


def fx_warm(img: Image.Image) -> Image.Image:
    a = arr(img)
    a[:, :, 0] = np.clip(a[:, :, 0] + 20, 0, 255)
    a[:, :, 2] = np.clip(a[:, :, 2] - 20, 0, 255)
    return from_arr(a)


def fx_cool(img: Image.Image) -> Image.Image:
    a = arr(img)
    a[:, :, 0] = np.clip(a[:, :, 0] - 20, 0, 255)
    a[:, :, 2] = np.clip(a[:, :, 2] + 30, 0, 255)
    return from_arr(a)


def fx_high_contrast_bw(img: Image.Image) -> Image.Image:
    a = arr(img)
    gray = np.mean(a[:, :, :3], axis=2)
    bw = np.where(gray > 128, 255.0, 0.0)
    a[:, :, 0] = bw
    a[:, :, 1] = bw
    a[:, :, 2] = bw
    return from_arr(a)


def fx_halftone(img: Image.Image) -> Image.Image:
    a = arr(img)
    gray = np.mean(a[:, :, :3], axis=2)
    h, w = gray.shape
    for y in range(0, h, 4):
        for x in range(0, w, 4):
            block = gray[y:y + 4, x:x + 4]
            avg = np.mean(block) if block.size > 0 else 128
            a[y:y + 4, x:x + 4, :3] = avg
    return from_arr(a)


def fx_cross_process(img: Image.Image) -> Image.Image:
    a = arr(img)
    a[:, :, 0] = np.clip(a[:, :, 0] * 1.2 + 20, 0, 255)
    a[:, :, 1] = np.clip(a[:, :, 1] * 0.8, 0, 255)
    a[:, :, 2] = np.clip(a[:, :, 2] * 1.1 + 30, 0, 255)
    return from_arr(a)


def fx_vintage(img: Image.Image) -> Image.Image:
    a = arr(img)
    a[:, :, 0] = np.clip(a[:, :, 0] * 1.1 + 15, 0, 255)
    a[:, :, 1] = np.clip(a[:, :, 1] * 0.95 + 10, 0, 255)
    a[:, :, 2] = np.clip(a[:, :, 2] * 0.75, 0, 255)
    return from_arr(a)


def fx_lomo(img: Image.Image) -> Image.Image:
    result = ImageEnhance.Contrast(img).enhance(1.5)
    result = ImageEnhance.Color(result).enhance(1.4)
    a = arr(result)
    h, w = a.shape[:2]
    cy, cx = h / 2, w / 2
    Y, X = np.ogrid[:h, :w]
    dist = np.sqrt((X - cx) ** 2 + (Y - cy) ** 2) / max(cx, cy)
    mask = np.clip(1.0 - dist * 0.5, 0.3, 1)
    a[:, :, :3] *= mask[:, :, np.newaxis]
    return from_arr(a)


def fx_pop_art(img: Image.Image) -> Image.Image:
    a = arr(img)
    a[:, :, :3] = (a[:, :, :3] // 85) * 85
    a[:, :, 0] = np.clip(a[:, :, 0] * 1.3, 0, 255)
    a[:, :, 2] = np.clip(a[:, :, 2] * 1.2, 0, 255)
    return from_arr(a)


def fx_sketch(img: Image.Image) -> Image.Image:
    gray = img.convert("L")
    inv = ImageOps.invert(gray)
    blurred = inv.filter(ImageFilter.GaussianBlur(12))
    from PIL import ImageChops
    sketch = ImageChops.divide(gray, ImageOps.invert(blurred), scale=1, offset=0)
    result = Image.new("RGBA", img.size, (255, 255, 255, 255))
    result.paste(sketch.convert("RGB"), (0, 0))
    a = arr(img)
    result_arr = arr(result)
    result_arr[:, :, 3] = a[:, :, 3]
    return from_arr(result_arr)


def fx_oil_paint(img: Image.Image) -> Image.Image:
    w, h = img.size
    small = img.resize((max(1, w // 3), max(1, h // 3)), Image.LANCZOS)
    back = small.resize((w, h), Image.LANCZOS)
    result = ImageEnhance.Color(back).enhance(1.4)
    return ImageEnhance.Contrast(result).enhance(1.2)


def fx_underwater(img: Image.Image) -> Image.Image:
    a = arr(img)
    a[:, :, 0] = np.clip(a[:, :, 0] * 0.6, 0, 255)
    a[:, :, 1] = np.clip(a[:, :, 1] * 0.9 + 20, 0, 255)
    a[:, :, 2] = np.clip(a[:, :, 2] * 1.2 + 30, 0, 255)
    return from_arr(a)


def fx_sunset(img: Image.Image) -> Image.Image:
    a = arr(img)
    a[:, :, 0] = np.clip(a[:, :, 0] * 1.3 + 20, 0, 255)
    a[:, :, 1] = np.clip(a[:, :, 1] * 0.85 + 10, 0, 255)
    a[:, :, 2] = np.clip(a[:, :, 2] * 0.6, 0, 255)
    return from_arr(a)


def fx_midnight(img: Image.Image) -> Image.Image:
    a = arr(img)
    a[:, :, :3] *= 0.4
    a[:, :, 2] = np.clip(a[:, :, 2] + 30, 0, 255)
    return from_arr(a)


def fx_hdr(img: Image.Image) -> Image.Image:
    result = ImageEnhance.Contrast(img).enhance(1.8)
    result = ImageEnhance.Color(result).enhance(1.5)
    return ImageEnhance.Sharpness(result).enhance(2.0)


def fx_dreamy(img: Image.Image) -> Image.Image:
    blurred = img.filter(ImageFilter.GaussianBlur(4))
    a_orig = arr(img)
    a_blur = arr(blurred)
    blended = a_orig * 0.6 + a_blur * 0.4
    blended[:, :, 0] = np.clip(blended[:, :, 0] + 15, 0, 255)
    blended[:, :, 2] = np.clip(blended[:, :, 2] + 15, 0, 255)
    return from_arr(blended)


def fx_grain(img: Image.Image) -> Image.Image:
    a = arr(img)
    rng = np.random.RandomState(77)
    grain = rng.normal(0, 25, a[:, :, :3].shape)
    a[:, :, :3] = np.clip(a[:, :, :3] + grain, 0, 255)
    result = from_arr(a)
    return ImageEnhance.Color(result).enhance(0.7)


def fx_chrome(img: Image.Image) -> Image.Image:
    a = arr(img)
    gray = np.mean(a[:, :, :3], axis=2, keepdims=True)
    a[:, :, :3] = np.clip(gray * 1.2 + 10, 0, 255)
    return from_arr(a)


def fx_palette_fire(img: Image.Image) -> Image.Image:
    a = arr(img)
    gray = np.mean(a[:, :, :3], axis=2) / 255.0
    r = np.clip(gray * 2 * 255, 0, 255)
    g = np.clip((gray - 0.3) * 2 * 255, 0, 255)
    b = np.clip((gray - 0.7) * 5 * 255, 0, 255)
    a[:, :, 0] = r
    a[:, :, 1] = g
    a[:, :, 2] = b
    return from_arr(a)


def fx_palette_ocean(img: Image.Image) -> Image.Image:
    a = arr(img)
    gray = np.mean(a[:, :, :3], axis=2) / 255.0
    r = np.clip((gray - 0.6) * 4 * 255, 0, 255)
    g = np.clip(gray * 1.5 * 255, 0, 255)
    b = np.clip(gray * 2 * 255, 0, 255)
    a[:, :, 0] = r
    a[:, :, 1] = g
    a[:, :, 2] = b
    return from_arr(a)


def fx_palette_forest(img: Image.Image) -> Image.Image:
    a = arr(img)
    gray = np.mean(a[:, :, :3], axis=2) / 255.0
    r = np.clip(gray * 0.5 * 255, 0, 255)
    g = np.clip(gray * 1.8 * 255, 0, 255)
    b = np.clip(gray * 0.3 * 255, 0, 255)
    a[:, :, 0] = r
    a[:, :, 1] = g
    a[:, :, 2] = b
    return from_arr(a)


def fx_zoom_center(img: Image.Image) -> Image.Image:
    w, h = img.size
    crop_w, crop_h = int(w * 0.6), int(h * 0.6)
    left = (w - crop_w) // 2
    top = (h - crop_h) // 2
    cropped = img.crop((left, top, left + crop_w, top + crop_h))
    return cropped.resize((w, h), Image.LANCZOS)


def fx_zoom_face(img: Image.Image) -> Image.Image:
    w, h = img.size
    crop_h = int(h * 0.5)
    crop_w = int(w * 0.7)
    left = (w - crop_w) // 2
    cropped = img.crop((left, 0, left + crop_w, crop_h))
    return cropped.resize((w, h), Image.LANCZOS)


def fx_stretch_wide(img: Image.Image) -> Image.Image:
    w, h = img.size
    return img.resize((int(w * 1.5), h), Image.LANCZOS)


def fx_stretch_tall(img: Image.Image) -> Image.Image:
    w, h = img.size
    return img.resize((w, int(h * 1.4)), Image.LANCZOS)


def fx_squish(img: Image.Image) -> Image.Image:
    w, h = img.size
    return img.resize((int(w * 0.6), int(h * 1.3)), Image.LANCZOS)


def fx_border_frame(img: Image.Image) -> Image.Image:
    w, h = img.size
    border = 8
    result = Image.new("RGBA", (w + border * 2, h + border * 2), (40, 40, 40, 255))
    inner = Image.new("RGBA", (w + 4, h + 4), (255, 255, 255, 255))
    result.paste(inner, (border - 2, border - 2))
    result.paste(img, (border, border), img)
    return result


def fx_shadow_drop(img: Image.Image) -> Image.Image:
    w, h = img.size
    result = Image.new("RGBA", (w + 10, h + 10), (0, 0, 0, 0))
    shadow = Image.new("RGBA", (w, h), (0, 0, 0, 80))
    result.paste(shadow, (6, 6), shadow)
    result.paste(img, (0, 0), img)
    return result


def fx_glow_outer(img: Image.Image) -> Image.Image:
    w, h = img.size
    pad = 12
    result = Image.new("RGBA", (w + pad * 2, h + pad * 2), (0, 0, 0, 0))
    glow = img.copy().resize((w + pad, h + pad), Image.LANCZOS)
    glow = glow.filter(ImageFilter.GaussianBlur(6))
    ga = arr(glow)
    ga[:, :, :3] = np.clip(ga[:, :, :3] + 60, 0, 255)
    glow = from_arr(ga)
    result.paste(glow, (pad // 2, pad // 2), glow)
    result.paste(img, (pad, pad), img)
    return result


def fx_tile_2x2(img: Image.Image) -> Image.Image:
    w, h = img.size
    sw, sh = w // 2, h // 2
    small = img.resize((sw, sh), Image.LANCZOS)
    result = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    result.paste(small, (0, 0))
    result.paste(small, (sw, 0))
    result.paste(small, (0, sh))
    result.paste(small, (sw, sh))
    return result


def fx_tile_3x3(img: Image.Image) -> Image.Image:
    w, h = img.size
    sw, sh = w // 3, h // 3
    small = img.resize((sw, sh), Image.LANCZOS)
    result = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    for gy in range(3):
        for gx in range(3):
            result.paste(small, (gx * sw, gy * sh))
    return result


def fx_swirl(img: Image.Image) -> Image.Image:
    a = arr(img)
    h, w = a.shape[:2]
    cy, cx = h / 2, w / 2
    result = np.zeros_like(a)
    max_r = math.sqrt(cx ** 2 + cy ** 2)
    Y, X = np.mgrid[:h, :w]
    dx = X - cx
    dy = Y - cy
    r = np.sqrt(dx ** 2 + dy ** 2)
    angle = np.arctan2(dy, dx) + r / max_r * 2.0
    sx = np.clip((cx + r * np.cos(angle)).astype(int), 0, w - 1)
    sy = np.clip((cy + r * np.sin(angle)).astype(int), 0, h - 1)
    result = a[sy, sx]
    return from_arr(result)


def fx_wave_vertical(img: Image.Image) -> Image.Image:
    a = arr(img)
    h, w = a.shape[:2]
    o = np.zeros_like(a)
    for x in range(w):
        shift = int(8 * math.sin(x / 10.0))
        o[:, x] = np.roll(a[:, x], shift, axis=0)
    return from_arr(o)


def fx_rainbow_overlay(img: Image.Image) -> Image.Image:
    a = arr(img)
    h, w = a.shape[:2]
    for y in range(h):
        hue_shift = (y / h) * 360
        r_shift = int(60 * math.sin(math.radians(hue_shift)))
        g_shift = int(60 * math.sin(math.radians(hue_shift + 120)))
        b_shift = int(60 * math.sin(math.radians(hue_shift + 240)))
        a[y, :, 0] = np.clip(a[y, :, 0] + r_shift, 0, 255)
        a[y, :, 1] = np.clip(a[y, :, 1] + g_shift, 0, 255)
        a[y, :, 2] = np.clip(a[y, :, 2] + b_shift, 0, 255)
    return from_arr(a)


def fx_grid_overlay(img: Image.Image) -> Image.Image:
    result = img.copy()
    draw = ImageDraw.Draw(result)
    w, h = result.size
    for x in range(0, w, 16):
        draw.line([(x, 0), (x, h)], fill=(0, 0, 0, 100), width=1)
    for y in range(0, h, 16):
        draw.line([(0, y), (w, y)], fill=(0, 0, 0, 100), width=1)
    return result


def fx_dots_overlay(img: Image.Image) -> Image.Image:
    result = img.copy()
    draw = ImageDraw.Draw(result)
    w, h = result.size
    for y in range(4, h, 12):
        for x in range(4, w, 12):
            draw.ellipse([x - 2, y - 2, x + 2, y + 2], fill=(255, 255, 255, 60))
    return result


def fx_stripe_diagonal(img: Image.Image) -> Image.Image:
    a = arr(img)
    h, w = a.shape[:2]
    for y in range(h):
        for x in range(w):
            if (x + y) % 8 < 3:
                a[y, x, :3] = np.clip(a[y, x, :3] * 0.6, 0, 255)
    return from_arr(a)


def fx_color_burn(img: Image.Image) -> Image.Image:
    a = arr(img)
    a[:, :, :3] = np.clip(a[:, :, :3] ** 1.5 / 255 ** 0.5, 0, 255)
    return from_arr(a)


def fx_gamma_up(img: Image.Image) -> Image.Image:
    a = arr(img)
    a[:, :, :3] = np.clip(255 * (a[:, :, :3] / 255) ** 0.6, 0, 255)
    return from_arr(a)


def fx_gamma_down(img: Image.Image) -> Image.Image:
    a = arr(img)
    a[:, :, :3] = np.clip(255 * (a[:, :, :3] / 255) ** 1.6, 0, 255)
    return from_arr(a)


def fx_split_screen(img: Image.Image) -> Image.Image:
    w, h = img.size
    half = w // 2
    left = img.crop((0, 0, half, h))
    right = img.crop((half, 0, w, h))
    inv_right = fx_invert(right)
    result = Image.new("RGBA", (w, h))
    result.paste(left, (0, 0))
    result.paste(inv_right, (half, 0))
    return result


def fx_dither(img: Image.Image) -> Image.Image:
    gray = img.convert("L")
    dithered = gray.convert("1")
    result = Image.new("RGBA", img.size, (255, 255, 255, 255))
    result.paste(dithered.convert("RGB"), (0, 0))
    a = arr(img)
    result_arr = arr(result)
    result_arr[:, :, 3] = a[:, :, 3]
    return from_arr(result_arr)


def fx_color_quantize(img: Image.Image) -> Image.Image:
    rgb = img.convert("RGB")
    quantized = rgb.quantize(colors=8, method=Image.Quantize.MEDIANCUT)
    result = quantized.convert("RGBA")
    a = arr(img)
    result_arr = arr(result)
    result_arr[:, :, 3] = a[:, :, 3]
    return from_arr(result_arr)


def fx_mosaic(img: Image.Image) -> Image.Image:
    a = arr(img)
    h, w = a.shape[:2]
    block = 12
    for y in range(0, h, block):
        for x in range(0, w, block):
            region = a[y:y + block, x:x + block, :3]
            if region.size > 0:
                avg = np.mean(region, axis=(0, 1))
                a[y:y + block, x:x + block, :3] = avg
    return from_arr(a)


# ── MASTER EFFECT LIST ──
EFFECTS: list[tuple[str, Callable[[Image.Image], Image.Image]]] = [
    ("001_original", fx_identity),
    ("002_bright_up", fx_brightness_up),
    ("003_bright_down", fx_brightness_down),
    ("004_contrast_up", fx_contrast_up),
    ("005_contrast_down", fx_contrast_down),
    ("006_saturate", fx_saturate_up),
    ("007_desaturate", fx_desaturate),
    ("008_sharpen", fx_sharpen),
    ("009_blur_soft", fx_blur_soft),
    ("010_blur_heavy", fx_blur_heavy),
    ("011_edge_enhance", fx_edge_enhance),
    ("012_emboss", fx_emboss),
    ("013_contour", fx_contour),
    ("014_find_edges", fx_find_edges),
    ("015_invert", fx_invert),
    ("016_flip_h", fx_flip_h),
    ("017_flip_v", fx_flip_v),
    ("018_rotate_15", fx_rotate_15),
    ("019_rotate_neg15", fx_rotate_neg15),
    ("020_rotate_45", fx_rotate_45),
    ("021_rotate_90", fx_rotate_90),
    ("022_pixelate_sm", fx_pixelate_small),
    ("023_pixelate_hvy", fx_pixelate_heavy),
    ("024_posterize_4", fx_posterize_4),
    ("025_posterize_8", fx_posterize_8),
    ("026_sepia", fx_sepia),
    ("027_red_ch", fx_red_channel),
    ("028_green_ch", fx_green_channel),
    ("029_blue_ch", fx_blue_channel),
    ("030_swap_rg", fx_swap_rg),
    ("031_swap_rb", fx_swap_rb),
    ("032_swap_gb", fx_swap_gb),
    ("033_neon_pop", fx_neon_pop),
    ("034_rgb_shift", fx_rgb_shift),
    ("035_sine_wave", fx_sine_wave),
    ("036_scanlines", fx_scanlines),
    ("037_scanlines_thick", fx_scanlines_thick),
    ("038_vignette", fx_vignette),
    ("039_duotone_hot", fx_duotone_hot),
    ("040_duotone_ice", fx_duotone_ice),
    ("041_duotone_fire", fx_duotone_fire),
    ("042_duotone_toxic", fx_duotone_toxic),
    ("043_duotone_purple", fx_duotone_purple),
    ("044_gameboy", fx_gameboy),
    ("045_thermal", fx_thermal),
    ("046_solarize", fx_solarize),
    ("047_solarize_low", fx_solarize_low),
    ("048_edge_glow", fx_edge_glow),
    ("049_kaleido", fx_kaleido),
    ("050_glitch_block", fx_glitch_block),
    ("051_glitch_color", fx_glitch_color),
    ("052_noise_light", fx_noise_light),
    ("053_noise_heavy", fx_noise_heavy),
    ("054_tint_red", fx_tint_red),
    ("055_tint_blue", fx_tint_blue),
    ("056_tint_green", fx_tint_green),
    ("057_tint_yellow", fx_tint_yellow),
    ("058_tint_pink", fx_tint_pink),
    ("059_tint_cyan", fx_tint_cyan),
    ("060_warm", fx_warm),
    ("061_cool", fx_cool),
    ("062_hi_contrast_bw", fx_high_contrast_bw),
    ("063_halftone", fx_halftone),
    ("064_cross_process", fx_cross_process),
    ("065_vintage", fx_vintage),
    ("066_lomo", fx_lomo),
    ("067_pop_art", fx_pop_art),
    ("068_sketch", fx_sketch),
    ("069_oil_paint", fx_oil_paint),
    ("070_underwater", fx_underwater),
    ("071_sunset", fx_sunset),
    ("072_midnight", fx_midnight),
    ("073_hdr", fx_hdr),
    ("074_dreamy", fx_dreamy),
    ("075_grain", fx_grain),
    ("076_chrome", fx_chrome),
    ("077_palette_fire", fx_palette_fire),
    ("078_palette_ocean", fx_palette_ocean),
    ("079_palette_forest", fx_palette_forest),
    ("080_zoom_center", fx_zoom_center),
    ("081_zoom_face", fx_zoom_face),
    ("082_stretch_wide", fx_stretch_wide),
    ("083_stretch_tall", fx_stretch_tall),
    ("084_squish", fx_squish),
    ("085_border_frame", fx_border_frame),
    ("086_shadow_drop", fx_shadow_drop),
    ("087_glow_outer", fx_glow_outer),
    ("088_tile_2x2", fx_tile_2x2),
    ("089_tile_3x3", fx_tile_3x3),
    ("090_swirl", fx_swirl),
    ("091_wave_vert", fx_wave_vertical),
    ("092_rainbow", fx_rainbow_overlay),
    ("093_grid_overlay", fx_grid_overlay),
    ("094_dots_overlay", fx_dots_overlay),
    ("095_stripe_diag", fx_stripe_diagonal),
    ("096_color_burn", fx_color_burn),
    ("097_gamma_up", fx_gamma_up),
    ("098_gamma_down", fx_gamma_down),
    ("099_split_screen", fx_split_screen),
    ("100_dither", fx_dither),
]


def write_index(source_names: list[str]) -> None:
    effect_cards = []
    for i, (ename, _) in enumerate(EFFECTS):
        imgs_html = []
        for sname in source_names:
            slug = re.sub(r"[^a-z0-9]+", "_", os.path.splitext(sname)[0].lower()).strip("_")
            imgs_html.append(
                f'<img src="{ename}/{slug}.png" alt="{ename} {slug}" loading="lazy">'
            )
        effect_cards.append(f"""
<div class="card" id="fx{i+1}">
  <h2>{i+1}. {ename}</h2>
  <div class="row">{''.join(imgs_html)}</div>
</div>""")

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Mario 3D Asset Lab — 100 Iterations</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0; padding: 20px;
      background: #0c0e16; color: #e4e8f4;
      font-family: 'Segoe UI', Arial, sans-serif;
    }}
    h1 {{ color: #ff5252; margin: 0 0 4px 0; }}
    .subtitle {{ color: #9aa4c0; margin: 0 0 16px 0; font-size: 14px; }}
    .nav {{ margin: 0 0 12px 0; display: flex; flex-wrap: wrap; gap: 4px; }}
    .nav a {{
      display: inline-block; padding: 3px 7px; font-size: 11px;
      background: #1a1f2e; color: #7eb8ff; border-radius: 4px;
      text-decoration: none; border: 1px solid #2a3050;
    }}
    .nav a:hover {{ background: #2a3050; }}
    .card {{
      background: #141828; border: 1px solid #252d48;
      border-radius: 8px; padding: 10px; margin-bottom: 10px;
    }}
    .card h2 {{
      margin: 0 0 8px 0; font-size: 15px; color: #82c8ff;
    }}
    .row {{
      display: flex; gap: 8px; overflow-x: auto;
      align-items: flex-start; padding-bottom: 4px;
    }}
    img {{
      max-height: 160px; width: auto;
      border-radius: 4px; border: 1px solid #252d48;
      background: #08090f; image-rendering: auto;
    }}
  </style>
</head>
<body>
  <h1>Mario 3D Asset Lab — 100 Iterations</h1>
  <p class="subtitle">Hero: {HERO_STANDING} + {HERO_THINKING} | Sources: {len(source_names)} images | {len(EFFECTS)} effects</p>
  <div class="nav">
    {''.join(f'<a href="#fx{i+1}">{i+1}</a>' for i in range(len(EFFECTS)))}
  </div>
  {''.join(effect_cards)}
</body>
</html>"""
    with open(os.path.join(OUTPUT_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)


def generate_all() -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    source_files = []
    for name in [HERO_STANDING, HERO_THINKING]:
        path = os.path.join(INPUT_DIR, name)
        if os.path.exists(path):
            source_files.append(name)

    for name in sorted(os.listdir(INPUT_DIR)):
        if name in source_files:
            continue
        ext = os.path.splitext(name)[1].lower()
        if ext in IMAGE_EXTS and os.path.isfile(os.path.join(INPUT_DIR, name)):
            source_files.append(name)

    print(f"Found {len(source_files)} source images")

    sources: dict[str, Image.Image] = {}
    for name in source_files:
        try:
            sources[name] = load_rgba(os.path.join(INPUT_DIR, name))
            print(f"  Loaded: {name} ({sources[name].size[0]}x{sources[name].size[1]})")
        except Exception as e:
            print(f"  SKIP: {name} ({e})")

    source_names = list(sources.keys())

    for ei, (effect_name, effect_fn) in enumerate(EFFECTS):
        effect_dir = os.path.join(OUTPUT_DIR, effect_name)
        os.makedirs(effect_dir, exist_ok=True)

        for sname, simg in sources.items():
            slug = re.sub(r"[^a-z0-9]+", "_", os.path.splitext(sname)[0].lower()).strip("_")
            out_path = os.path.join(effect_dir, f"{slug}.png")
            try:
                result = effect_fn(simg)
                result.save(out_path)
            except Exception as e:
                print(f"  ERROR: {effect_name}/{slug}: {e}")
                simg.save(out_path)

        pct = (ei + 1) / len(EFFECTS) * 100
        print(f"[{ei+1:3d}/100] {effect_name} ({pct:.0f}%)")

    write_index(source_names)

    with open(os.path.join(OUTPUT_DIR, "manifest.txt"), "w", encoding="utf-8") as f:
        f.write(f"Mario 3D Asset Lab\nGenerated: {datetime.now(UTC).isoformat()}\n\n")
        f.write(f"Hero standing: {HERO_STANDING}\n")
        f.write(f"Hero thinking: {HERO_THINKING}\n")
        f.write(f"Total sources: {len(source_names)}\n")
        f.write(f"Total effects: {len(EFFECTS)}\n\n")
        for name, _ in EFFECTS:
            f.write(f"- {name}\n")

    print(f"\nDone: 100 effect folders with {len(source_names)} images each -> {OUTPUT_DIR}")
    print(f"Open {os.path.join(OUTPUT_DIR, 'index.html')} to browse.")


if __name__ == "__main__":
    generate_all()
