"""Generate wacky edited Mario sprite-sheet remixes from mario_assets."""

from __future__ import annotations

import os
import re
from datetime import UTC, datetime
from typing import Callable

import numpy as np
from PIL import Image


ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
INPUT_DIR = os.path.join(ROOT_DIR, "mario_assets")
OUTPUT_DIR = os.path.join(ROOT_DIR, "assets_wacky_lab")

SOURCE_IMAGES = [
    "mario.png",
    "dcpb2k5-fccc921c-3d4e-47dc-845b-1361bb1c5fab.png",
    "t4p5ims9enlc1.png",
]


def ensure_rgba(image: Image.Image) -> Image.Image:
    if image.mode == "RGBA":
        return image
    return image.convert("RGBA")


def to_array(image: Image.Image) -> np.ndarray:
    return np.array(ensure_rgba(image), dtype=np.uint8)


def from_array(arr: np.ndarray) -> Image.Image:
    return Image.fromarray(arr.astype(np.uint8), "RGBA")


def effect_neon_pop(image: Image.Image) -> Image.Image:
    arr = to_array(image).astype(np.int16)
    rgb = arr[:, :, :3]
    out = np.zeros_like(rgb)
    out[:, :, 0] = np.clip((rgb[:, :, 2] * 1.25) + (rgb[:, :, 0] * 0.15), 0, 255)
    out[:, :, 1] = np.clip((rgb[:, :, 0] * 0.65) + (rgb[:, :, 1] * 0.80), 0, 255)
    out[:, :, 2] = np.clip((rgb[:, :, 1] * 0.70) + (rgb[:, :, 2] * 0.75), 0, 255)
    arr[:, :, :3] = out
    return from_array(arr)


def effect_rgb_ghost(image: Image.Image) -> Image.Image:
    arr = to_array(image)
    out = arr.copy()
    out[:, :, 0] = np.roll(arr[:, :, 0], 5, axis=1)
    out[:, :, 1] = np.roll(arr[:, :, 1], -3, axis=0)
    out[:, :, 2] = np.roll(arr[:, :, 2], 2, axis=1)
    return from_array(out)


def effect_sine_wave(image: Image.Image) -> Image.Image:
    arr = to_array(image)
    h, w, c = arr.shape
    out = np.zeros_like(arr)
    for y in range(h):
        shift = int(8 * np.sin(y / 11.0))
        out[y, :, :] = np.roll(arr[y, :, :], shift, axis=0)
    return from_array(out.reshape(h, w, c))


def effect_pixel_crunch(image: Image.Image) -> Image.Image:
    base = ensure_rgba(image)
    w, h = base.size
    down = base.resize((max(1, w // 5), max(1, h // 5)), Image.NEAREST)
    up = down.resize((w, h), Image.NEAREST)
    arr = to_array(up)
    arr[:, :, :3] = (arr[:, :, :3] // 32) * 32
    return from_array(arr)


def effect_hot_duotone(image: Image.Image) -> Image.Image:
    arr = to_array(image)
    gray = np.mean(arr[:, :, :3], axis=2, keepdims=True) / 255.0
    cold = np.array([30, 12, 96], dtype=np.float32)
    hot = np.array([255, 140, 36], dtype=np.float32)
    mapped = cold + (hot - cold) * gray
    out = arr.copy().astype(np.float32)
    out[:, :, :3] = mapped
    return from_array(out)


def effect_inverted_scanline(image: Image.Image) -> Image.Image:
    arr = to_array(image).astype(np.int16)
    out = arr.copy()
    out[:, :, :3] = 255 - out[:, :, :3]
    out[::2, :, :3] = np.clip(out[::2, :, :3] * 0.72, 0, 255)
    return from_array(out)


def effect_kaleido_mirror(image: Image.Image) -> Image.Image:
    arr = to_array(image)
    h, w, _ = arr.shape
    half_h = max(1, h // 2)
    half_w = max(1, w // 2)
    quad = arr[:half_h, :half_w, :]
    top = np.concatenate([quad, np.flip(quad, axis=1)], axis=1)
    bottom = np.flip(top, axis=0)
    merged = np.concatenate([top, bottom], axis=0)
    out = Image.fromarray(merged.astype(np.uint8), "RGBA").resize((w, h), Image.NEAREST)
    return ensure_rgba(out)


def effect_solar_flare(image: Image.Image) -> Image.Image:
    arr = to_array(image).astype(np.int16)
    rgb = arr[:, :, :3]
    high = rgb > 140
    rgb[high] = 255 - rgb[high]
    rgb = np.clip((rgb * 1.15) + 18, 0, 255)
    arr[:, :, :3] = rgb
    return from_array(arr)


def effect_edge_glow(image: Image.Image) -> Image.Image:
    arr = to_array(image)
    rgb = arr[:, :, :3].astype(np.int16)
    h, w, _ = rgb.shape
    edges = np.zeros((h, w), dtype=np.int16)
    edges[:, 1:] = np.maximum(edges[:, 1:], np.max(np.abs(rgb[:, 1:, :] - rgb[:, :-1, :]), axis=2))
    edges[1:, :] = np.maximum(edges[1:, :], np.max(np.abs(rgb[1:, :, :] - rgb[:-1, :, :]), axis=2))
    mask = edges > 45
    out = arr.copy().astype(np.int16)
    out[mask, 0] = np.clip(out[mask, 0] + 130, 0, 255)
    out[mask, 1] = np.clip(out[mask, 1] + 130, 0, 255)
    out[mask, 2] = np.clip(out[mask, 2] + 40, 0, 255)
    return from_array(out)


def effect_gameboy_mutation(image: Image.Image) -> Image.Image:
    arr = to_array(image)
    gray = np.mean(arr[:, :, :3], axis=2)
    palette = np.array(
        [
            [15, 56, 15],
            [48, 98, 48],
            [139, 172, 15],
            [155, 188, 15],
        ],
        dtype=np.uint8,
    )
    idx = np.clip((gray // 64).astype(np.int16), 0, 3)
    mapped = palette[idx]
    out = arr.copy()
    out[:, :, :3] = mapped
    return from_array(out)


EFFECTS: list[tuple[str, Callable[[Image.Image], Image.Image]]] = [
    ("neon_pop", effect_neon_pop),
    ("rgb_ghost", effect_rgb_ghost),
    ("sine_wave", effect_sine_wave),
    ("pixel_crunch", effect_pixel_crunch),
    ("hot_duotone", effect_hot_duotone),
    ("inverted_scanline", effect_inverted_scanline),
    ("kaleido_mirror", effect_kaleido_mirror),
    ("solar_flare", effect_solar_flare),
    ("edge_glow", effect_edge_glow),
    ("gameboy_mutation", effect_gameboy_mutation),
]


def slugify(name: str) -> str:
    base = os.path.splitext(name)[0].lower()
    return re.sub(r"[^a-z0-9]+", "_", base).strip("_")


def write_index(records: list[dict[str, str]]) -> None:
    cards = []
    for rec in records:
        cards.append(
            f"""
<div class="card">
  <h2>{rec['title']}</h2>
  <div class="row">
    <img src="{rec['folder']}/original.png" alt="{rec['title']} original">
    <img src="{rec['folder']}/neon_pop.png" alt="{rec['title']} neon pop">
    <img src="{rec['folder']}/rgb_ghost.png" alt="{rec['title']} rgb ghost">
    <img src="{rec['folder']}/kaleido_mirror.png" alt="{rec['title']} kaleido">
  </div>
</div>
"""
        )

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Wacky Mario Remix Lab</title>
  <style>
    body {{
      margin: 0;
      padding: 24px;
      background: #10121a;
      color: #e9edf9;
      font-family: Arial, sans-serif;
    }}
    h1 {{
      margin: 0 0 8px 0;
      color: #ff6f6f;
    }}
    .subtitle {{
      margin: 0 0 16px 0;
      color: #b8c2dd;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(420px, 1fr));
      gap: 14px;
    }}
    .card {{
      background: #1a2030;
      border: 1px solid #2c3653;
      border-radius: 10px;
      padding: 12px;
    }}
    .card h2 {{
      margin: 0 0 10px 0;
      color: #91d5ff;
      font-size: 18px;
    }}
    .row {{
      display: flex;
      gap: 8px;
      align-items: flex-start;
      overflow-x: auto;
    }}
    img {{
      max-width: 180px;
      height: auto;
      border-radius: 6px;
      border: 1px solid #2c3653;
      background: #070910;
      padding: 2px;
      image-rendering: pixelated;
    }}
  </style>
</head>
<body>
  <h1>Wacky Mario Remix Lab</h1>
  <p class="subtitle">Remixed from local mario_assets using 10 transformation effects per source.</p>
  <div class="grid">{''.join(cards)}</div>
</body>
</html>
"""
    with open(os.path.join(OUTPUT_DIR, "index.html"), "w", encoding="utf-8") as file:
        file.write(html)


def write_manifest(records: list[dict[str, str]]) -> None:
    lines = [
        "Wacky Mario Remix Lab",
        f"Generated: {datetime.now(UTC).isoformat()}",
        "",
    ]
    for rec in records:
        lines.append(f"{rec['title']} -> {rec['folder']}")
    lines.append("")
    lines.append("Effects:")
    for effect_name, _ in EFFECTS:
        lines.append(f"- {effect_name}")
    lines.append("")
    with open(os.path.join(OUTPUT_DIR, "manifest.txt"), "w", encoding="utf-8") as file:
        file.write("\n".join(lines))


def generate_all() -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    records: list[dict[str, str]] = []

    for image_name in SOURCE_IMAGES:
        source_path = os.path.join(INPUT_DIR, image_name)
        if not os.path.exists(source_path):
            print(f"Skipping missing source: {source_path}")
            continue

        source_slug = slugify(image_name)
        folder_name = f"source_{source_slug}"
        folder_path = os.path.join(OUTPUT_DIR, folder_name)
        os.makedirs(folder_path, exist_ok=True)

        base_image = ensure_rgba(Image.open(source_path))
        base_image.save(os.path.join(folder_path, "original.png"))

        for effect_name, effect_fn in EFFECTS:
            remixed = effect_fn(base_image)
            remixed.save(os.path.join(folder_path, f"{effect_name}.png"))

        records.append({"title": image_name, "folder": folder_name})
        print(f"Created remixes for {image_name}")

    write_manifest(records)
    write_index(records)
    print(f"\nDone: {len(records)} source sets written to {OUTPUT_DIR}")


if __name__ == "__main__":
    generate_all()
