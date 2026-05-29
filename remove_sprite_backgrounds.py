#!/usr/bin/env python3
"""Remove white backgrounds from all character sprites, making them transparent PNGs."""

import os
import sys
from PIL import Image
import numpy as np

CHARACTERS_DIR = "characters"
THRESHOLD = 230  # Pixels with R,G,B all > this are considered "white"
EDGE_FEATHER = 2  # Pixels of edge feathering for smooth borders


def remove_white_bg(img_path: str) -> tuple[bool, int]:
    """Remove white background from a sprite. Returns (changed, transparent_pixels)."""
    img = Image.open(img_path).convert("RGBA")
    data = np.array(img)

    # Find pixels where R, G, B are all above threshold (white/near-white)
    r, g, b, a = data[:, :, 0], data[:, :, 1], data[:, :, 2], data[:, :, 3]
    white_mask = (r > THRESHOLD) & (g > THRESHOLD) & (b > THRESHOLD)

    if not white_mask.any():
        return False, 0

    # Set white pixels to fully transparent
    data[white_mask, 3] = 0

    # Save as proper RGBA PNG
    result = Image.fromarray(data)
    result.save(img_path, "PNG")

    transparent_count = int(white_mask.sum())
    return True, transparent_count


def process_character(char_name: str) -> tuple[int, int]:
    """Process all sprites for a character. Returns (processed, changed)."""
    sprites_dir = os.path.join(CHARACTERS_DIR, char_name, "sprites")
    if not os.path.isdir(sprites_dir):
        print(f"  No sprites dir for {char_name}")
        return 0, 0

    processed = 0
    changed = 0

    for root, dirs, files in os.walk(sprites_dir):
        for f in sorted(files):
            if not f.lower().endswith(".png"):
                continue
            fpath = os.path.join(root, f)
            rel = os.path.relpath(fpath, sprites_dir)
            try:
                was_changed, trans_px = remove_white_bg(fpath)
                processed += 1
                if was_changed:
                    changed += 1
                    pct = trans_px / (512 * 512) * 100  # rough percentage
                    print(f"    ✓ {rel} — {trans_px:,} px transparent ({pct:.0f}%)")
            except Exception as e:
                print(f"    ✗ {rel} — ERROR: {e}")

    return processed, changed


def main():
    chars = sys.argv[1:] if len(sys.argv) > 1 else None

    if chars is None:
        # Process all characters
        chars = [d for d in os.listdir(CHARACTERS_DIR)
                 if os.path.isdir(os.path.join(CHARACTERS_DIR, d, "sprites"))]

    total_processed = 0
    total_changed = 0

    for char in sorted(chars):
        print(f"\n=== {char} ===")
        processed, changed = process_character(char)
        total_processed += processed
        total_changed += changed
        print(f"  {changed}/{processed} sprites updated")

    print(f"\n=== DONE: {total_changed}/{total_processed} sprites had backgrounds removed ===")


if __name__ == "__main__":
    main()
