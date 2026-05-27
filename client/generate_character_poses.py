"""
Universal Character Pose Generator
Generates sprite poses for any character using SubNP free API or DALL-E.
Automatically removes backgrounds with rembg.

Usage:
    python generate_character_poses.py --character rudi
    python generate_character_poses.py --character sonic --category party
    python generate_character_poses.py --character rudi --dalle
    python generate_character_poses.py --character sonic --list
"""
import requests
import json
import time
import os
import sys
import argparse
from io import BytesIO

DEBUG_GEN = True

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))

API_URL = "https://subnp.com/api/free/generate"
MODEL = "magic"

# Character-specific style suffixes
CHARACTER_STYLES = {
    "rudi": (
        "A sleek humanoid AI character named Rudi with a dark hoodie, "
        "neon cyan glowing circuit-pattern accents, confident smirk, "
        "modern tech-punk aesthetic, slightly robotic features with human expression"
    ),
    "sonic": (
        "Sonic the Hedgehog, classic blue anthropomorphic hedgehog character "
        "with red sneakers, white gloves, green eyes, spiky blue quills"
    ),
}

RENDER_SUFFIX = (
    ", 3D rendered figurine style, clean gray studio background, "
    "full body shot, highly detailed, high quality, soft studio lighting"
)

# Pose definitions per character
CHARACTER_POSES = {
    "rudi": {
        "neutral": [
            ("idle", "{char} standing relaxed with arms crossed, slight smirk, casual confident stance"),
            ("thinking", "{char} with hand on chin, one eyebrow raised, thoughtful expression"),
        ],
        "positive": [
            ("smirk", "{char} with a knowing smirk, arms crossed, head slightly tilted, confident"),
            ("hyped", "{char} pumping fist in the air, excited grin, energetic pose"),
            ("cracking_up", "{char} laughing hard, head thrown back, genuine amusement"),
            ("charmed", "{char} with a warm genuine smile, hand over heart, pleasantly surprised"),
            ("confident", "{char} standing tall, hands on hips, chin up, supremely confident"),
        ],
        "negative": [
            ("unimpressed", "{char} with arms crossed, one eyebrow raised, clearly unimpressed look"),
            ("disappointed", "{char} pinching bridge of nose, eyes closed, disappointed expression"),
            ("facepalm", "{char} doing a full facepalm, other hand on hip, exasperated"),
            ("grossed_out", "{char} leaning away with disgusted face, hand up in stop gesture"),
            ("fired_up", "{char} with intense angry expression, fists clenched, leaning forward"),
            ("uneasy", "{char} looking nervously to the side, hands fidgeting, uncertain expression"),
            ("startled", "{char} jumping back with wide eyes, arms up in surprise, startled"),
            ("flustered", "{char} scratching back of head sheepishly, embarrassed half-smile"),
        ],
        "thinking": [
            ("pondering", "{char} looking upward thoughtfully, finger tapping chin"),
            ("questioning", "{char} with head tilted, confused expression, one eyebrow raised high"),
            ("scheming", "{char} with a mischievous grin, fingers steepled, plotting look"),
            ("focused", "{char} with intense focused eyes, determined expression, leaning forward"),
            ("intrigued", "{char} leaning forward with curiosity, eyes bright, interested expression"),
            ("lightbulb", "{char} with index finger raised, bright idea moment, excited eyes"),
        ],
        "speech": [
            ("talking", "{char} gesturing with one hand while speaking, animated expression"),
            ("explaining", "{char} with both hands open, explaining something passionately"),
            ("listening", "{char} with head slightly tilted, attentive listening pose, slight nod"),
        ],
        "greeting": [
            ("casual_wave", "{char} giving a casual two-finger wave, cool relaxed smile"),
            ("peace_out", "{char} throwing up a peace sign, walking away with a smirk"),
        ],
        "reactions": [
            ("double_take", "{char} doing a dramatic double take, head whipping back, surprised"),
            ("jaw_drop", "{char} with mouth wide open in shock, eyes huge, absolutely stunned"),
            ("mind_blown", "{char} with hands on sides of head, explosion effect, amazed"),
            ("sassy", "{char} with hand on hip, head tilted, finger wagging, sassy attitude"),
            ("cringe", "{char} cringing hard, one eye closed, teeth gritted, looking away"),
            ("impressed", "{char} nodding approvingly, arms crossed, raised eyebrow, genuine respect"),
        ],
        "sleep": [
            ("bored_yawn", "{char} mid-yawn, hand covering mouth, half-closed eyes, bored"),
            ("powered_down", "{char} slumped against wall, eyes closed, hoodie pulled up, sleeping"),
        ],
        "movement": [
            ("vibing", "{char} doing a casual dance move, bobbing head to music, relaxed groove"),
            ("arriving", "{char} walking in confidently, one hand in pocket, cool entrance"),
        ],
        "party": [
            ("celebrate", "{char} raising both arms in celebration, huge grin, confetti around"),
            ("birthday", "{char} holding a birthday cake with candles, warm smile"),
        ],
        "toast": [
            ("raising_glass", "{char} raising a glass high, confident smile, toasting"),
        ],
        "memorial": [
            ("respectful", "{char} with head bowed, one hand over heart, solemn respectful pose"),
        ],
    },
    "sonic": {
        "neutral": [
            ("idle", "{char} standing in classic pose, arms crossed, confident smirk, foot tapping"),
            ("thinking", "{char} with hand on chin, looking to the side, thoughtful"),
        ],
        "positive": [
            ("thumbs_up", "{char} giving a big thumbs up, wide grin, classic heroic pose"),
            ("hyped", "{char} in dynamic running pose, fist pumped, excited grin"),
            ("cracking_up", "{char} laughing, holding his belly, genuine amusement"),
            ("charmed", "{char} with a cocky but warm smile, hand behind head, chill pose"),
            ("confident", "{char} standing heroically, hands on hips, wind blowing quills"),
        ],
        "negative": [
            ("impatient", "{char} tapping foot impatiently, arms crossed, annoyed expression"),
            ("bummed", "{char} looking down sadly, ears drooped, disappointed"),
            ("grossed_out", "{char} holding nose in disgust, leaning away, revolted face"),
            ("fired_up", "{char} in battle stance, intense angry eyes, fists clenched"),
            ("uneasy", "{char} looking nervously to the side, uncertain stance"),
            ("startled", "{char} jumping back with wide eyes, spines raised, surprised"),
            ("flustered", "{char} scratching head sheepishly, embarrassed grin"),
        ],
        "thinking": [
            ("pondering", "{char} looking up thoughtfully, finger on chin"),
            ("head_scratch", "{char} scratching head confused, puzzled expression"),
            ("smirk", "{char} with a mischievous knowing smirk, plan forming"),
            ("focused", "{char} crouched in ready stance, determined eyes"),
            ("intrigued", "{char} leaning forward curiously, eyebrow raised"),
            ("lightbulb", "{char} snapping fingers with bright idea, excited eyes"),
        ],
        "speech": [
            ("talking", "{char} gesturing enthusiastically while talking, animated"),
            ("explaining", "{char} pointing at something while explaining, energetic"),
            ("listening", "{char} standing with arms crossed, listening attentively, slight nod"),
        ],
        "greeting": [
            ("wave", "{char} waving hello energetically, big smile, welcoming pose"),
            ("peace_out", "{char} giving peace sign, running away, looking back with grin"),
        ],
        "reactions": [
            ("double_take", "{char} doing a cartoon double take, body whipping around"),
            ("jaw_drop", "{char} jaw dropped, eyes popping, absolutely stunned"),
            ("mind_blown", "{char} hands on head, amazed shocked expression, spines standing up"),
            ("sassy", "{char} wagging finger confidently, cocky grin, attitude pose"),
            ("cringe", "{char} cringing, one eye closed, looking away uncomfortable"),
            ("impressed", "{char} giving slow nod of approval, arms crossed, respect"),
        ],
        "sleep": [
            ("dozing", "{char} curled up sleeping, peaceful expression, tail wrapped around"),
            ("impatient", "{char} yawning dramatically, checking imaginary watch"),
        ],
        "movement": [
            ("running", "{char} in full speed running pose, motion blur, dynamic"),
            ("speed_entry", "{char} sliding to a stop, dust cloud, dramatic entrance"),
        ],
        "party": [
            ("celebrate", "{char} jumping high with joy, fist pumped, confetti, celebration"),
            ("birthday", "{char} wearing a party hat, holding cake, excited expression"),
        ],
        "toast": [
            ("raising_glass", "{char} raising a glass, grinning, celebratory pose"),
        ],
        "memorial": [
            ("respectful", "{char} standing solemnly, head bowed, respectful, hand over heart"),
        ],
    },
}


def generate_subnp(prompt, retries=5):
    """Generate an image using SubNP free API with retry logic."""
    for attempt in range(retries):
        try:
            if DEBUG_GEN:
                print(f"    [DEBUG_GEN] SubNP attempt {attempt + 1}/{retries}")

            resp = requests.post(
                API_URL,
                json={"prompt": prompt, "model": MODEL},
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
        except requests.exceptions.ConnectionError:
            pass
        except requests.exceptions.Timeout:
            pass
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
    """Generate an image using OpenAI DALL-E API."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable not set")

    try:
        resp = requests.post(
            "https://api.openai.com/v1/images/generations",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": "dall-e-3", "prompt": prompt, "n": 1, "size": "1024x1024", "quality": "standard"},
            timeout=120,
        )
        if resp.status_code == 200:
            img_url = resp.json()["data"][0]["url"]
            img_resp = requests.get(img_url, timeout=60)
            if img_resp.status_code == 200:
                return img_resp.content
        else:
            print(f"    [ERROR] DALL-E API: {resp.status_code} {resp.text[:200]}")
    except Exception as e:
        print(f"    [ERROR] DALL-E error: {e}")
    return None


def remove_background(input_path, output_path):
    """Remove background from image using rembg."""
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
        return True
    except Exception as e:
        print(f"    [ERROR] Background removal failed: {e}")
        return False


def generate_character(character_name, category_filter=None, use_dalle=False):
    """Generate all poses for a character."""
    if character_name not in CHARACTER_POSES:
        print(f"Error: Unknown character '{character_name}'. Available: {list(CHARACTER_POSES.keys())}")
        return

    char_style = CHARACTER_STYLES.get(character_name, character_name)
    poses = CHARACTER_POSES[character_name]
    char_dir = os.path.join(PROJECT_ROOT, "characters", character_name, "sprites")
    raw_dir = os.path.join(PROJECT_ROOT, "characters", character_name, "_raw_sprites")

    total_gen = 0
    total_skip = 0
    total_fail = 0

    categories = [category_filter] if category_filter else list(poses.keys())

    for category in categories:
        if category not in poses:
            print(f"Unknown category: {category}")
            continue

        print(f"\n{'='*50}")
        print(f"  {character_name.upper()} — {category.upper()}")
        print(f"{'='*50}")

        cat_poses = poses[category]
        cat_dir = os.path.join(char_dir, category)
        raw_cat_dir = os.path.join(raw_dir, category)
        os.makedirs(cat_dir, exist_ok=True)
        os.makedirs(raw_cat_dir, exist_ok=True)

        for i, (pose_id, prompt_template) in enumerate(cat_poses):
            out_path = os.path.join(cat_dir, f"{pose_id}.png")
            raw_path = os.path.join(raw_cat_dir, f"{pose_id}.png")

            if os.path.exists(out_path) and os.path.getsize(out_path) > 1000:
                print(f"  [{i+1}/{len(cat_poses)}] {category}/{pose_id} — SKIPPED (exists)")
                total_skip += 1
                continue

            if os.path.exists(raw_path) and os.path.getsize(raw_path) > 1000:
                print(f"  [{i+1}/{len(cat_poses)}] {category}/{pose_id} — Removing BG...")
                if remove_background(raw_path, out_path):
                    total_gen += 1
                else:
                    total_fail += 1
                continue

            # Build full prompt
            full_prompt = prompt_template.format(char=char_style) + RENDER_SUFFIX
            print(f"  [{i+1}/{len(cat_poses)}] {category}/{pose_id} — Generating...")
            start = time.time()

            if use_dalle:
                img_data = generate_dalle(full_prompt)
            else:
                img_data = generate_subnp(full_prompt)

            elapsed = time.time() - start

            if img_data:
                with open(raw_path, "wb") as f:
                    f.write(img_data)
                print(f"  [{i+1}/{len(cat_poses)}] {category}/{pose_id} — Downloaded ({len(img_data)/1024:.0f}KB, {elapsed:.1f}s)")
                print(f"  [{i+1}/{len(cat_poses)}] {category}/{pose_id} — Removing BG...")
                if remove_background(raw_path, out_path):
                    print(f"  [{i+1}/{len(cat_poses)}] {category}/{pose_id} — OK ✓")
                    total_gen += 1
                else:
                    total_fail += 1
            else:
                print(f"  [{i+1}/{len(cat_poses)}] {category}/{pose_id} — FAILED ({elapsed:.1f}s)")
                total_fail += 1

            time.sleep(5)

    print(f"\n{'='*50}")
    print(f"  {character_name.upper()} COMPLETE")
    print(f"  Generated: {total_gen}  Skipped: {total_skip}  Failed: {total_fail}")
    print(f"  Sprites saved to: {char_dir}")
    print(f"{'='*50}")


def list_poses(character_name):
    """List all pose categories and counts for a character."""
    if character_name not in CHARACTER_POSES:
        print(f"Unknown character: {character_name}")
        return
    poses = CHARACTER_POSES[character_name]
    total = 0
    for cat, items in poses.items():
        print(f"  {cat}: {len(items)} poses")
        total += len(items)
    print(f"  TOTAL: {total} poses")


def main():
    parser = argparse.ArgumentParser(description="Generate character sprite poses")
    parser.add_argument("--character", "-c", required=True, help="Character name (rudi, sonic)")
    parser.add_argument("--category", help="Generate only this category")
    parser.add_argument("--dalle", action="store_true", help="Use DALL-E instead of SubNP")
    parser.add_argument("--list", action="store_true", help="List pose categories")
    args = parser.parse_args()

    if args.list:
        list_poses(args.character)
        return

    generate_character(args.character, args.category, args.dalle)


if __name__ == "__main__":
    main()
