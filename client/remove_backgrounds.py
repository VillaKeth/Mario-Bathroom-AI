"""Remove gray studio backgrounds from AI-generated Mario poses.

Uses rembg (U²-Net) for AI-powered background removal, producing
transparent PNGs suitable for Pygame overlay.

Output: mario_3d_assets/ai_poses_transparent/
"""

import os
import sys
from pathlib import Path
from PIL import Image
from rembg import remove

DEBUG_REMBG = True

# Paths
SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
INPUT_DIR = PROJECT_DIR / "mario_3d_assets" / "ai_poses"
OUTPUT_DIR = PROJECT_DIR / "mario_3d_assets" / "ai_poses_transparent"

CATEGORIES = [
    "neutral", "greeting", "speech", "positive", "negative",
    "thinking", "sleep", "movement", "action", "powerup",
]


def remove_background(input_path: Path, output_path: Path) -> bool:
    """Remove background from a single image using rembg."""
    try:
        with open(input_path, "rb") as f:
            input_data = f.read()

        output_data = remove(input_data)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(output_data)

        # Verify output
        img = Image.open(output_path)
        if img.mode != "RGBA":
            img = img.convert("RGBA")
            img.save(output_path)

        if DEBUG_REMBG:
            print(f"  ✓ {input_path.name} → {img.size[0]}x{img.size[1]} RGBA")
        return True

    except Exception as e:
        print(f"  ✗ {input_path.name} FAILED: {e}")
        return False


def process_all():
    """Process all AI poses, removing backgrounds."""
    print(f"Input:  {INPUT_DIR}")
    print(f"Output: {OUTPUT_DIR}")
    print()

    total = 0
    success = 0
    skipped = 0

    for category in CATEGORIES:
        cat_input = INPUT_DIR / category
        cat_output = OUTPUT_DIR / category

        if not cat_input.exists():
            print(f"⚠ Category not found: {category}")
            continue

        pngs = sorted(cat_input.glob("*.png"))
        if not pngs:
            continue

        print(f"{'='*50}")
        print(f"📁 {category.upper()} ({len(pngs)} images)")
        print(f"{'='*50}")

        for png in pngs:
            total += 1
            out_path = cat_output / png.name

            # Skip if already processed
            if out_path.exists() and out_path.stat().st_size > 1000:
                if DEBUG_REMBG:
                    print(f"  ⏭ {png.name} (already done)")
                skipped += 1
                success += 1
                continue

            if remove_background(png, out_path):
                success += 1

    print(f"\n{'='*50}")
    print(f"DONE: {success}/{total} successful ({skipped} skipped)")
    print(f"Output: {OUTPUT_DIR}")


if __name__ == "__main__":
    process_all()
