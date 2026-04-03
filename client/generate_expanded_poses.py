"""
Mario Expanded Pose Generator
Generates new pose categories using SubNP free API or DALL-E.
Automatically removes backgrounds with rembg.

Usage:
    python generate_expanded_poses.py                    # Generate all new categories
    python generate_expanded_poses.py --category party   # Generate only 'party' category
    python generate_expanded_poses.py --dalle             # Use DALL-E instead of SubNP
    python generate_expanded_poses.py --gallery-only      # Just build HTML gallery
    python generate_expanded_poses.py --remove-bg-only    # Just remove backgrounds from ai_poses/
    python generate_expanded_poses.py --list              # List all expanded pose categories
"""
import requests
import json
import time
import os
import sys
import argparse
from io import BytesIO
from PIL import Image

DEBUG_GEN = True

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
RAW_DIR = os.path.join(PROJECT_ROOT, "mario_3d_assets", "ai_poses")
TRANSPARENT_DIR = os.path.join(PROJECT_ROOT, "mario_3d_assets", "ai_poses_transparent")

API_URL = "https://subnp.com/api/free/generate"
MODEL = "magic"

# Same style suffix as original generator for visual consistency
STYLE_SUFFIX = (
    ", 3D rendered figurine style, clean gray studio background, "
    "full body shot, highly detailed, Nintendo official art quality, soft studio lighting"
)

# ---------------------------------------------------------------------------
# Expanded pose definitions — NEW categories only (original 74 untouched)
# Each entry: (pose_id, prompt_text)
# ---------------------------------------------------------------------------
EXPANDED_POSES = {
    "party": [
        ("cheers", "Super Mario holding up a drink glass for a toast, big celebratory smile, party streamers around, festive atmosphere"),
        ("party_hat", "Super Mario wearing a colorful party hat, celebrating with arms up, joyful excited expression, confetti falling"),
        ("confetti", "Super Mario throwing handfuls of confetti high in the air, ecstatic expression, colorful paper pieces everywhere"),
        ("cake", "Super Mario proudly presenting a large decorated birthday cake with candles, big warm smile, both hands holding cake"),
        ("balloon", "Super Mario holding a bunch of colorful party balloons in one hand, happy cheerful expression, floating balloons"),
        ("gift", "Super Mario presenting a beautifully wrapped gift box with a bow, generous warm smile, offering it forward"),
        ("countdown", "Super Mario counting down excitedly with fingers raised showing numbers, wide eager eyes, anticipation"),
        ("celebrate", "Super Mario in wild celebration, arms raised high, streamers and confetti everywhere, pure joy expression"),
        ("group_photo", "Super Mario posing for a group photo, one arm extended around imaginary friend, big camera-ready smile, peace sign"),
        ("cheering", "Super Mario cheering enthusiastically, clapping hands together above head, huge encouraging smile, supportive"),
    ],
    "memorial": [
        ("moment_of_silence", "Super Mario with head bowed respectfully, red cap removed and held over his heart, solemn peaceful expression, eyes closed"),
        ("candle", "Super Mario holding a single lit candle gently with both hands, soft somber expression, warm candlelight glow on face"),
        ("honor", "Super Mario in a formal respectful pose, standing straight, one hand over his heart, dignified serious expression"),
        ("remembering", "Super Mario looking upward at the sky with a nostalgic peaceful expression, soft smile, hands clasped together"),
        ("tribute", "Super Mario raising a glass solemnly in a dignified tribute, respectful expression, slight bow of head"),
    ],
    "toast": [
        ("raising_glass", "Super Mario raising a glass high triumphantly above his head, big proud smile, celebratory toast gesture"),
        ("clinking_glasses", "Super Mario extending a glass forward toward the viewer as if clinking glasses, warm friendly smile, cheers gesture"),
        ("drinking", "Super Mario drinking from a glass with eyes closed, enjoying the moment, satisfied happy expression"),
        ("shot_ready", "Super Mario holding up a small shot glass eagerly, excited wide eyes, ready to drink, enthusiastic expression"),
        ("after_shot", "Super Mario making a funny face after taking a shot, eyes squinted, lips puckered, shaking his head comically"),
    ],
    "bathroom": [
        ("grossed_out", "Super Mario pinching his nose with one hand in disgust, leaning away, extremely disgusted revolted expression"),
        ("air_freshener", "Super Mario spraying an air freshener can with one hand, relieved happy expression, fresh sparkles in the air"),
        ("waiting", "Super Mario waiting impatiently, one foot tapping, checking an imaginary watch on his wrist, annoyed expression"),
        ("knock_knock", "Super Mario knocking on an imaginary door with one fist raised, curious puzzled expression, leaning forward"),
        ("thumbs_up_flush", "Super Mario giving a big thumbs up with a satisfied grin, other hand on hip, mission accomplished pose"),
        ("washing_hands", "Super Mario washing his hands at a sink, scrubbing responsibly, proud hygienic expression, soap bubbles"),
        ("mirror_check", "Super Mario checking himself in a mirror, adjusting his red cap, confident self-assured smile, preening"),
        ("reading", "Super Mario sitting casually and reading a newspaper, relaxed content expression, legs crossed, comfortable"),
    ],
    "reactions": [
        ("mind_blown", "Super Mario with an amazed shocked expression, hands on sides of head, cartoon explosion effect around head, eyes wide"),
        ("slow_clap", "Super Mario slow clapping sarcastically, unimpressed half-lidded eyes, slight smirk, condescending attitude"),
        ("eye_roll", "Super Mario rolling his eyes dramatically upward, exasperated expression, arms crossed, totally unamused"),
        ("double_take", "Super Mario doing a cartoon double take, head whipping back, extremely surprised, body leaning backward"),
        ("jaw_drop", "Super Mario with jaw dropped comically low, eyes popping wide, hands on cheeks, utterly astonished"),
        ("mic_drop", "Super Mario dropping an imaginary microphone from one hand, confident smirk, walking away coolly, victorious"),
        ("cringe", "Super Mario cringing hard, teeth gritted, one eye closed, head turned slightly away, uncomfortable expression"),
        ("impressed", "Super Mario nodding approvingly, arms crossed, confident smirk, raised eyebrow, genuinely impressed expression"),
        ("sassy", "Super Mario with one hand on hip, sassy confident pose, head tilted, playful smirk, finger wagging"),
        ("rofl", "Super Mario rolling on the floor laughing uncontrollably, tears of joy streaming, holding his belly, hilarious"),
    ],
    "birthday": [
        ("birthday_boy", "Super Mario wearing a golden birthday crown on his head, proud triumphant pose, arms on hips, birthday royalty"),
        ("blowing_candles", "Super Mario leaning forward blowing out candles on a birthday cake, cheeks puffed, determined expression"),
        ("opening_gift", "Super Mario excitedly tearing open a wrapped present, wide joyful eyes, paper flying everywhere, pure excitement"),
        ("party_dance", "Super Mario doing a silly exaggerated birthday dance, arms flailing joyfully, goofy happy expression, party moves"),
        ("birthday_toast", "Super Mario raising a glass for a birthday toast, warm genuine smile, celebratory sparkling aura"),
    ],
    "gaming": [
        ("game_over", "Super Mario in a dramatic Game Over pose, fallen on knees, head tilted down, defeated dramatic expression, game over text"),
        ("level_up", "Super Mario leveling up with sparkles and upward triumphant pose, glowing aura, fist raised, ascending powerfully"),
        ("coin_collect", "Super Mario catching a golden coin mid-air, one hand reaching up, excited gleeful expression, coin sparkle"),
        ("warp_pipe", "Super Mario emerging from a green warp pipe, upper body visible, surprised curious expression, classic Nintendo pipe"),
        ("power_star", "Super Mario reaching upward for a glowing power star floating above, stretching high, awestruck amazed expression"),
    ],
}

# Category display icons for gallery
CATEGORY_ICONS = {
    "party": "🎉",
    "memorial": "🕯️",
    "toast": "🥂",
    "bathroom": "🚻",
    "reactions": "😲",
    "birthday": "🎂",
    "gaming": "🎮",
}


def generate_subnp(prompt, retries=5):
    """Generate an image using SubNP free API (no key needed) with retry logic."""
    full_prompt = prompt + STYLE_SUFFIX

    for attempt in range(retries):
        try:
            if DEBUG_GEN:
                print(f"    [DEBUG_GEN] SubNP attempt {attempt + 1}/{retries}")

            resp = requests.post(
                API_URL,
                json={"prompt": full_prompt, "model": MODEL},
                timeout=180,
                stream=True,
                headers={"Connection": "keep-alive"},
            )

            if resp.status_code != 200:
                if DEBUG_GEN:
                    print(f"    [DEBUG_GEN] HTTP {resp.status_code}")
                continue

            img_url = None
            for line in resp.iter_lines(decode_unicode=True):
                if not line or not line.startswith("data:"):
                    continue
                try:
                    data = json.loads(line[5:].strip())
                except json.JSONDecodeError:
                    continue
                status = data.get("status", "")

                if DEBUG_GEN:
                    print(f"    [DEBUG_GEN] SSE: {status} - {data.get('message', '')}")

                if status == "error":
                    break

                img_url = data.get("image_url") or data.get("url") or data.get("imageUrl")
                if img_url:
                    break

            if img_url:
                img_resp = requests.get(img_url, timeout=60)
                if img_resp.status_code == 200 and len(img_resp.content) > 1000:
                    return img_resp.content
                else:
                    if DEBUG_GEN:
                        print(f"    [DEBUG_GEN] Download failed: {img_resp.status_code}")

        except requests.exceptions.ConnectionError as e:
            if DEBUG_GEN:
                print(f"    [DEBUG_GEN] Connection dropped: {e}")
        except requests.exceptions.Timeout as e:
            if DEBUG_GEN:
                print(f"    [DEBUG_GEN] Timeout: {e}")
        except Exception as e:
            if DEBUG_GEN:
                print(f"    [DEBUG_GEN] Error: {type(e).__name__}: {e}")

        if attempt < retries - 1:
            wait = 10 * (attempt + 1)
            if DEBUG_GEN:
                print(f"    [DEBUG_GEN] Retrying in {wait}s...")
            time.sleep(wait)

    return None


def generate_dalle(prompt):
    """Generate an image using OpenAI DALL-E API. Requires OPENAI_API_KEY env var."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY environment variable is not set. "
            "Set it before using --dalle flag."
        )

    full_prompt = prompt + STYLE_SUFFIX

    try:
        if DEBUG_GEN:
            print("    [DEBUG_GEN] DALL-E request...")

        resp = requests.post(
            "https://api.openai.com/v1/images/generations",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "dall-e-3",
                "prompt": full_prompt,
                "n": 1,
                "size": "1024x1024",
                "quality": "standard",
            },
            timeout=120,
        )

        if resp.status_code != 200:
            if DEBUG_GEN:
                print(f"    [DEBUG_GEN] DALL-E HTTP {resp.status_code}: {resp.text[:200]}")
            return None

        data = resp.json()
        img_url = data["data"][0]["url"]
        img_resp = requests.get(img_url, timeout=60)
        if img_resp.status_code == 200 and len(img_resp.content) > 1000:
            return img_resp.content
        else:
            if DEBUG_GEN:
                print(f"    [DEBUG_GEN] DALL-E image download failed")
            return None

    except Exception as e:
        if DEBUG_GEN:
            print(f"    [DEBUG_GEN] DALL-E error: {type(e).__name__}: {e}")
        return None


def remove_background(input_path, output_path):
    """Remove background from an image using rembg and save as transparent PNG."""
    try:
        from rembg import remove as rembg_remove
    except ImportError:
        print("    [ERROR] rembg not installed. Run: pip install rembg")
        return False

    try:
        with open(input_path, "rb") as f:
            input_data = f.read()

        output_data = rembg_remove(input_data)

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(output_data)

        if DEBUG_GEN:
            in_kb = len(input_data) / 1024
            out_kb = len(output_data) / 1024
            print(f"    [DEBUG_GEN] BG removed: {in_kb:.0f}KB → {out_kb:.0f}KB")
        return True

    except Exception as e:
        print(f"    [ERROR] Background removal failed for {input_path}: {e}")
        return False


def generate_category(category, poses, use_dalle=False):
    """Generate all poses for a single category.

    Returns (generated, skipped, failed) counts.
    """
    raw_cat_dir = os.path.join(RAW_DIR, category)
    transparent_cat_dir = os.path.join(TRANSPARENT_DIR, category)
    os.makedirs(raw_cat_dir, exist_ok=True)
    os.makedirs(transparent_cat_dir, exist_ok=True)

    generated = 0
    skipped = 0
    failed = 0

    for i, (pose_id, prompt) in enumerate(poses):
        raw_path = os.path.join(raw_cat_dir, f"{pose_id}.png")
        transparent_path = os.path.join(transparent_cat_dir, f"{pose_id}.png")

        # Skip if transparent version already exists
        if os.path.exists(transparent_path) and os.path.getsize(transparent_path) > 1000:
            print(f"  [{i+1}/{len(poses)}] {category}/{pose_id} — SKIPPED (exists)")
            skipped += 1
            continue

        # If raw exists but no transparent, just do background removal
        if os.path.exists(raw_path) and os.path.getsize(raw_path) > 1000:
            print(f"  [{i+1}/{len(poses)}] {category}/{pose_id} — Removing background...")
            if remove_background(raw_path, transparent_path):
                print(f"  [{i+1}/{len(poses)}] {category}/{pose_id} — BG removed OK")
                generated += 1
            else:
                print(f"  [{i+1}/{len(poses)}] {category}/{pose_id} — BG removal FAILED")
                failed += 1
            continue

        # Generate image
        print(f"  [{i+1}/{len(poses)}] {category}/{pose_id} — Generating...")
        start = time.time()

        if use_dalle:
            img_data = generate_dalle(prompt)
        else:
            img_data = generate_subnp(prompt)

        elapsed = time.time() - start

        if img_data:
            # Save raw image
            with open(raw_path, "wb") as f:
                f.write(img_data)
            size_kb = len(img_data) / 1024
            print(f"  [{i+1}/{len(poses)}] {category}/{pose_id} — Downloaded ({size_kb:.0f}KB, {elapsed:.1f}s)")

            # Remove background
            print(f"  [{i+1}/{len(poses)}] {category}/{pose_id} — Removing background...")
            if remove_background(raw_path, transparent_path):
                print(f"  [{i+1}/{len(poses)}] {category}/{pose_id} — OK ✓")
                generated += 1
            else:
                print(f"  [{i+1}/{len(poses)}] {category}/{pose_id} — BG removal FAILED (raw saved)")
                failed += 1
        else:
            print(f"  [{i+1}/{len(poses)}] {category}/{pose_id} — GENERATION FAILED after {elapsed:.1f}s")
            failed += 1

        # Rate limiting between API requests
        time.sleep(5)

    return generated, skipped, failed


def remove_backgrounds_only():
    """Process all raw images in ai_poses/ that don't have transparent versions yet."""
    print(f"\n{'='*60}")
    print(f"  BACKGROUND REMOVAL — Processing ai_poses/ → ai_poses_transparent/")
    print(f"{'='*60}\n")

    total_processed = 0
    total_skipped = 0
    total_failed = 0

    for category in sorted(os.listdir(RAW_DIR)):
        raw_cat_dir = os.path.join(RAW_DIR, category)
        if not os.path.isdir(raw_cat_dir):
            continue

        transparent_cat_dir = os.path.join(TRANSPARENT_DIR, category)
        os.makedirs(transparent_cat_dir, exist_ok=True)

        print(f"\n--- {category.upper()} ---")

        for filename in sorted(os.listdir(raw_cat_dir)):
            if not filename.endswith(".png"):
                continue

            raw_path = os.path.join(raw_cat_dir, filename)
            transparent_path = os.path.join(transparent_cat_dir, filename)

            if os.path.exists(transparent_path) and os.path.getsize(transparent_path) > 1000:
                print(f"  {category}/{filename} — SKIPPED (exists)")
                total_skipped += 1
                continue

            print(f"  {category}/{filename} — Removing background...")
            if remove_background(raw_path, transparent_path):
                print(f"  {category}/{filename} — OK ✓")
                total_processed += 1
            else:
                print(f"  {category}/{filename} — FAILED")
                total_failed += 1

    print(f"\n{'='*60}")
    print(f"  DONE! Processed: {total_processed}, Skipped: {total_skipped}, Failed: {total_failed}")
    print(f"{'='*60}\n")


def generate_gallery():
    """Generate an HTML gallery of ALL poses (original + expanded)."""
    # Gather all categories from the transparent directory
    all_categories = {}

    # Original categories from generate_ai_poses.py
    from generate_ai_poses import POSE_CATEGORIES as ORIGINAL_POSES
    for cat, poses in ORIGINAL_POSES.items():
        all_categories[cat] = [(pid, prompt) for pid, prompt in poses]

    # Expanded categories
    for cat, poses in EXPANDED_POSES.items():
        all_categories[cat] = poses

    original_icons = {
        "neutral": "😐", "greeting": "👋", "speech": "💬",
        "positive": "😄", "negative": "😢", "thinking": "🤔",
        "sleep": "💤", "movement": "🏃", "action": "⚡", "powerup": "⭐",
    }
    all_icons = {**original_icons, **CATEGORY_ICONS}

    html = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Mario AI Poses — Full Gallery (Original + Expanded)</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { background: #1a1a2e; color: #e0e0e0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 20px; }
h1 { color: #e63946; text-align: center; margin-bottom: 5px; font-size: 2em; }
.subtitle { text-align: center; color: #888; margin-bottom: 10px; }
.tabs { display: flex; justify-content: center; gap: 8px; flex-wrap: wrap; margin-bottom: 20px; }
.tab { padding: 6px 14px; border-radius: 20px; border: 1px solid #444; cursor: pointer;
       color: #ccc; font-size: 13px; transition: all 0.2s; }
.tab:hover { border-color: #e63946; color: #fff; }
.tab.active { background: #e63946; border-color: #e63946; color: #fff; }
.tab.new { border-color: #f4a261; }
.tab.new::after { content: " ✨"; }
h2 { color: #f4a261; padding: 15px 0 10px; border-bottom: 2px solid #e63946; margin-top: 30px; }
h2 .new-badge { background: #e63946; color: white; font-size: 11px; padding: 2px 8px;
                border-radius: 10px; margin-left: 10px; vertical-align: middle; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 15px; margin-top: 15px; }
.card { background: #16213e; border-radius: 10px; overflow: hidden; border: 1px solid #333;
        transition: transform 0.2s; cursor: pointer; }
.card:hover { transform: scale(1.02); border-color: #e63946; }
.card img { width: 100%; height: 280px; object-fit: contain; background: #0a0a1a; }
.card .info { padding: 10px; }
.card .info h3 { color: #f4a261; font-size: 14px; }
.card .info p { color: #888; font-size: 11px; margin-top: 3px; }
.card .info .cat-tag { display: inline-block; background: #333; color: #aaa; padding: 1px 6px;
                       border-radius: 8px; font-size: 10px; margin-top: 4px; }
.modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%;
         background: rgba(0,0,0,0.9); z-index: 1000; justify-content: center; align-items: center; }
.modal.active { display: flex; }
.modal img { max-width: 90%; max-height: 90%; object-fit: contain; }
.modal .close { position: absolute; top: 20px; right: 30px; color: white; font-size: 40px; cursor: pointer; }
.stats { text-align: center; background: #16213e; padding: 15px; border-radius: 10px; margin-bottom: 20px; }
.stats span { margin: 0 15px; }
.missing { opacity: 0.3; border: 1px dashed #555; }
.missing .info h3::after { content: " (not generated)"; color: #666; font-size: 11px; }
</style>
</head>
<body>
<h1>🍄 Mario AI Poses — Full Gallery</h1>
<p class="subtitle">Original 74 poses + Expanded categories</p>
"""

    expanded_cats = set(EXPANDED_POSES.keys())
    total_count = 0
    total_existing = 0

    # Build category sections
    sections_html = ""
    for category, poses in all_categories.items():
        cat_dir_transparent = os.path.join(TRANSPARENT_DIR, category)
        cat_dir_raw = os.path.join(RAW_DIR, category)
        icon = all_icons.get(category, "🎮")
        is_new = category in expanded_cats

        existing = []
        missing = []
        for pid, prompt in poses:
            t_path = os.path.join(cat_dir_transparent, f"{pid}.png")
            r_path = os.path.join(cat_dir_raw, f"{pid}.png")
            if os.path.exists(t_path):
                existing.append((pid, prompt, f"../ai_poses_transparent/{category}/{pid}.png"))
            elif os.path.exists(r_path):
                existing.append((pid, prompt, f"../ai_poses/{category}/{pid}.png"))
            else:
                missing.append((pid, prompt))

        badge = '<span class="new-badge">NEW</span>' if is_new else ""
        sections_html += f'\n<h2 id="cat-{category}">{icon} {category.title()} ({len(existing)}/{len(poses)}) {badge}</h2>\n<div class="grid">\n'

        for pid, prompt, rel_path in existing:
            sections_html += f'''<div class="card" onclick="showModal('{rel_path}')">
<img src="{rel_path}" alt="{pid}" loading="lazy">
<div class="info"><h3>{pid}</h3><p>{prompt[:80]}...</p><span class="cat-tag">{category}</span></div>
</div>\n'''
            total_existing += 1

        for pid, prompt in missing:
            sections_html += f'''<div class="card missing">
<div style="width:100%;height:280px;background:#0a0a1a;display:flex;align-items:center;justify-content:center;color:#444;font-size:48px;">?</div>
<div class="info"><h3>{pid}</h3><p>{prompt[:80]}...</p><span class="cat-tag">{category}</span></div>
</div>\n'''

        total_count += len(poses)
        sections_html += "</div>\n"

    # Stats bar
    html += f'<div class="stats"><strong>Total defined:</strong> <span>{total_count}</span> | '
    html += f'<strong>Generated:</strong> <span>{total_existing}</span> | '
    html += f'<strong>Missing:</strong> <span>{total_count - total_existing}</span></div>\n'

    # Tab navigation
    html += '<div class="tabs">\n'
    for category in all_categories:
        icon = all_icons.get(category, "🎮")
        is_new = "new" if category in expanded_cats else ""
        html += f'<a class="tab {is_new}" href="#cat-{category}">{icon} {category.title()}</a>\n'
    html += '</div>\n'

    html += sections_html

    html += """
<div class="modal" id="modal" onclick="this.classList.remove('active')">
<span class="close">&times;</span>
<img id="modalImg" src="">
</div>

<script>
function showModal(src) {
    document.getElementById('modalImg').src = src;
    document.getElementById('modal').classList.add('active');
}
document.addEventListener('keydown', e => {
    if (e.key === 'Escape') document.getElementById('modal').classList.remove('active');
});
</script>
</body>
</html>"""

    gallery_path = os.path.join(RAW_DIR, "expanded_gallery.html")
    with open(gallery_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Gallery saved to {gallery_path}")


def list_categories():
    """Print all expanded pose categories and counts."""
    total = 0
    print(f"\n{'='*60}")
    print(f"  EXPANDED POSE CATEGORIES")
    print(f"{'='*60}")
    for cat, poses in EXPANDED_POSES.items():
        icon = CATEGORY_ICONS.get(cat, "🎮")
        transparent_cat_dir = os.path.join(TRANSPARENT_DIR, cat)
        existing = 0
        if os.path.isdir(transparent_cat_dir):
            existing = len([f for f in os.listdir(transparent_cat_dir) if f.endswith(".png")])
        print(f"  {icon} {cat:<12} — {len(poses):>2} poses ({existing} generated)")
        total += len(poses)
    print(f"{'='*60}")
    print(f"  Total new poses: {total}")
    print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Mario Expanded Pose Generator — adds new pose categories"
    )
    parser.add_argument(
        "--category",
        help="Generate only this category (e.g. party, memorial, toast)",
        choices=list(EXPANDED_POSES.keys()),
    )
    parser.add_argument(
        "--dalle",
        action="store_true",
        help="Use OpenAI DALL-E instead of SubNP (requires OPENAI_API_KEY env var)",
    )
    parser.add_argument(
        "--gallery-only",
        action="store_true",
        help="Only build the HTML gallery, don't generate images",
    )
    parser.add_argument(
        "--remove-bg-only",
        action="store_true",
        help="Only remove backgrounds from existing raw images in ai_poses/",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all expanded categories and exit",
    )
    args = parser.parse_args()

    if args.list:
        list_categories()
        return

    if args.gallery_only:
        generate_gallery()
        return

    if args.remove_bg_only:
        remove_backgrounds_only()
        return

    # Determine which categories to generate
    if args.category:
        categories = {args.category: EXPANDED_POSES[args.category]}
    else:
        categories = EXPANDED_POSES

    total_poses = sum(len(p) for p in categories.values())

    print(f"\n{'='*60}")
    print(f"  MARIO EXPANDED POSE GENERATOR")
    print(f"  Engine: {'DALL-E' if args.dalle else 'SubNP (free)'}")
    print(f"  Categories: {len(categories)}")
    print(f"  Total poses: {total_poses}")
    print(f"  Raw output:  {RAW_DIR}")
    print(f"  Transparent: {TRANSPARENT_DIR}")
    print(f"{'='*60}\n")

    grand_generated = 0
    grand_skipped = 0
    grand_failed = 0

    for cat, poses in categories.items():
        icon = CATEGORY_ICONS.get(cat, "🎮")
        print(f"\n--- {icon} {cat.upper()} ({len(poses)} poses) ---")

        gen, skip, fail = generate_category(cat, poses, use_dalle=args.dalle)
        grand_generated += gen
        grand_skipped += skip
        grand_failed += fail

    print(f"\n{'='*60}")
    print(f"  DONE!")
    print(f"  Generated:  {grand_generated}")
    print(f"  Skipped:    {grand_skipped}")
    print(f"  Failed:     {grand_failed}")
    print(f"{'='*60}\n")

    # Auto-build gallery after generation
    print("Building gallery...")
    generate_gallery()


if __name__ == "__main__":
    main()
