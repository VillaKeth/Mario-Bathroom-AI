"""Batch generate sprites for all HSR characters sequentially.

Usage:
    python batch_generate_hsr.py              # Generate all HSR chars
    python batch_generate_hsr.py --start kafka  # Start from kafka onwards
    python batch_generate_hsr.py --only stelle march7th  # Only specific chars
    python batch_generate_hsr.py --status       # Show generation status
"""
import subprocess
import sys
import os
import time
import argparse
from datetime import datetime

HSR_CHARACTERS = [
    "stelle", "march7th", "danheng", "himeko", "welt", "kafka", "silverwolf",
    "seele", "blade_hsr", "jingyuan", "bronya_hsr", "clara", "fuxuan",
    "jingliu", "topaz_hsr", "ruanmei", "drratio", "blackswan", "sparkle_hsr",
    "acheron", "aventurine", "robin_hsr", "firefly", "sunday", "theherta",
    "luocha", "argenti", "huohuo", "gallagher", "boothill", "yunli",
    "feixiao", "lingsha", "jiaoqiu",
]

EXPECTED_SPRITES_PER_CHAR = 40  # approx based on shared pose template


def get_sprite_count(char_id):
    """Count existing valid sprites (>1KB) for a character."""
    sprite_dir = os.path.join("characters", char_id, "sprites")
    if not os.path.exists(sprite_dir):
        return 0
    count = 0
    for root, _, files in os.walk(sprite_dir):
        for f in files:
            if f.endswith(".png"):
                path = os.path.join(root, f)
                if os.path.getsize(path) > 1000:
                    count += 1
    return count


def show_status():
    """Show generation status for all HSR characters."""
    total_done = 0
    total_expected = 0
    print(f"\n{'Character':<16} {'Sprites':<10} {'Status'}")
    print("-" * 45)
    for char_id in HSR_CHARACTERS:
        count = get_sprite_count(char_id)
        total_done += count
        total_expected += EXPECTED_SPRITES_PER_CHAR
        if count == 0:
            status = "⬜ Not started"
        elif count >= EXPECTED_SPRITES_PER_CHAR - 2:
            status = "✅ Complete"
        else:
            status = f"🔄 In progress"
        print(f"  {char_id:<14} {count:>3}/{EXPECTED_SPRITES_PER_CHAR:<6} {status}")
    print("-" * 45)
    print(f"  Total: {total_done}/{total_expected}")
    print()


def generate_character(char_id, char_index, total):
    """Generate all sprites for one character."""
    print(f"\n{'='*60}")
    print(f"  [{char_index}/{total}] Starting: {char_id}")
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    existing = get_sprite_count(char_id)
    if existing >= EXPECTED_SPRITES_PER_CHAR - 2:
        print(f"  Already has {existing} sprites, skipping!")
        return True

    cmd = [
        sys.executable, "client/generate_character_poses.py",
        "--character", char_id,
        "--pollinations"
    ]

    start = time.time()
    result = subprocess.run(cmd, capture_output=False)
    elapsed = time.time() - start

    final_count = get_sprite_count(char_id)
    print(f"\n  {char_id} finished in {elapsed/60:.1f} minutes")
    print(f"  Sprites: {existing} -> {final_count}")

    if result.returncode != 0:
        print(f"  ⚠️  Process exited with code {result.returncode}")
        return False

    return True


def git_commit_progress(chars_done):
    """Commit progress after each character batch."""
    try:
        subprocess.run(["git", "add", "characters/", "client/generate_character_poses.py"],
                       capture_output=True, timeout=30)
        msg = f"feat: generate HSR sprites ({', '.join(chars_done[-3:])})"
        subprocess.run(["git", "commit", "-m", msg,
                        "-m", f"Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"],
                       capture_output=True, timeout=30)
        print(f"  📦 Committed progress for {len(chars_done)} characters")
    except Exception as e:
        print(f"  ⚠️  Commit failed: {e}")


def main():
    parser = argparse.ArgumentParser(description="Batch HSR sprite generation")
    parser.add_argument("--start", help="Start from this character (skip earlier ones)")
    parser.add_argument("--only", nargs="+", help="Only generate these characters")
    parser.add_argument("--status", action="store_true", help="Show generation status")
    parser.add_argument("--commit-every", type=int, default=3,
                        help="Commit after every N characters (default: 3)")
    args = parser.parse_args()

    if args.status:
        show_status()
        return

    chars = list(HSR_CHARACTERS)
    if args.only:
        chars = [c for c in args.only if c in HSR_CHARACTERS]
        if not chars:
            print("No valid characters specified!")
            return
    elif args.start:
        if args.start in chars:
            idx = chars.index(args.start)
            chars = chars[idx:]
        else:
            print(f"Character '{args.start}' not found!")
            return

    print(f"\n🎮 HSR Batch Generator")
    print(f"   Characters to process: {len(chars)}")
    print(f"   Commit every: {args.commit_every} characters")
    print(f"   Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   Queue: {', '.join(chars)}")

    chars_done = []
    chars_failed = []

    for i, char_id in enumerate(chars, 1):
        success = generate_character(char_id, i, len(chars))
        if success:
            chars_done.append(char_id)
        else:
            chars_failed.append(char_id)

        if len(chars_done) % args.commit_every == 0 and chars_done:
            git_commit_progress(chars_done)

        # Brief pause between characters to help with rate limiting
        if i < len(chars):
            print(f"\n  ⏳ Waiting 30s before next character...")
            time.sleep(30)

    # Final commit if needed
    if chars_done and len(chars_done) % args.commit_every != 0:
        git_commit_progress(chars_done)

    print(f"\n{'='*60}")
    print(f"  BATCH COMPLETE")
    print(f"  Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Done: {len(chars_done)}  Failed: {len(chars_failed)}")
    if chars_failed:
        print(f"  Failed: {', '.join(chars_failed)}")
    print(f"{'='*60}")

    show_status()


if __name__ == "__main__":
    main()
