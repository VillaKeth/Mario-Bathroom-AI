#!/usr/bin/env python3
"""Generate AI sprites for Sonic using Pollinations.ai free image API."""

import os
import sys
import time
import requests
import urllib.parse

CHARACTER_DIR = os.path.join("characters", "sonic", "sprites")

# Sonic's appearance for consistent generation
SONIC_APPEARANCE = (
    "Sonic the Hedgehog, iconic SEGA video game character, "
    "blue anthropomorphic hedgehog with spiky blue quills, "
    "bright green eyes, tan muzzle and belly, "
    "red running shoes with white stripes and gold buckles, "
    "white gloves, confident smirk, "
    "anime art style, full body view, pure white background, "
    "high quality digital illustration, clean lines"
)

# All 38 unique sprites needed from character.yaml
POSES = {
    "greeting/peace_out": "waving goodbye with two fingers peace sign, turning away coolly, looking back with a wink",
    "greeting/wave": "waving hello energetically with one hand raised high, big friendly grin",
    "memorial/respectful": "standing solemnly with head slightly bowed, hand over heart, respectful expression",
    "movement/running": "running at super speed, legs blurred with motion lines, determined expression, leaning forward",
    "movement/speed_entry": "bursting onto scene in a blue blur, dramatic speed entrance with wind effects, excited face",
    "negative/bummed": "looking down sadly, shoulders slumped, frowning, disappointed expression",
    "negative/fired_up": "angry and furious, fists clenched, teeth gritted, fiery aura around him",
    "negative/flustered": "blushing deeply, scratching back of head nervously, embarrassed smile, sweat drop",
    "negative/grossed_out": "recoiling in disgust, tongue sticking out, squinting eyes, hands up defensively",
    "negative/impatient": "tapping foot rapidly, arms crossed, annoyed expression, looking at wrist impatiently",
    "negative/startled": "jumping back in shock, eyes wide, quills standing on end, surprised and scared",
    "negative/uneasy": "looking around nervously, shifting weight, uncertain expression, slight frown",
    "neutral/idle": "standing casually with arms at sides, relaxed confident posture, slight smirk, classic Sonic pose",
    "party/birthday": "wearing a small party hat, holding a birthday cake, big celebration smile, confetti around",
    "party/celebrate": "jumping in the air with fist pumped, huge excited grin, celebration pose, sparkles and confetti",
    "positive/charmed": "hand on chin, flirty confident expression, one eyebrow raised, charming smirk",
    "positive/confident": "standing tall with arms crossed, proud smirk, chin up, heroic confident pose",
    "positive/cracking_up": "laughing hysterically, holding stomach, eyes squeezed shut, mouth wide open laughing",
    "positive/hyped": "super excited, both fists pumped, jumping with energy, electric blue aura, huge grin",
    "positive/thumbs_up": "giving a big thumbs up with classic wink, confident grin, signature Sonic pose",
    "reactions/cringe": "cringing hard, one eye closed, teeth showing, uncomfortable grimace, leaning away",
    "reactions/double_take": "doing a dramatic double take, head whipping back, eyes popping wide, shocked expression",
    "reactions/impressed": "nodding approvingly, slight smile, one eyebrow raised, arms crossed, impressed look",
    "reactions/jaw_drop": "jaw dropped in total shock, eyes huge and round, hands on cheeks, stunned expression",
    "reactions/mind_blown": "hands on head, eyes spiraling, mind completely blown, explosive effect around head",
    "reactions/sassy": "hand on hip, looking smug and sassy, one finger wagging, playful smirk",
    "sleep/dozing": "curled up sleeping peacefully, quills relaxed, small Z's floating above, gentle breathing",
    "sleep/impatient": "yawning dramatically while tapping foot, bored and sleepy, half-lidded eyes",
    "speech/explaining": "one hand gesturing while explaining something, thoughtful expression, slight lean forward",
    "speech/listening": "head tilted slightly, ear perked up, attentive listening expression, nodding",
    "speech/talking": "mouth open mid-sentence, one hand gesturing, animated talking expression",
    "thinking/focused": "intense concentration, eyes narrowed, hand on chin, determined focused expression",
    "thinking/head_scratch": "scratching head with one hand, confused expression, question mark floating above",
    "thinking/intrigued": "leaning forward with interest, eyes wide with curiosity, slight smile, fascinated look",
    "thinking/lightbulb": "sudden idea, finger pointing up, eyes bright, lightbulb appearing above head, excited smile",
    "thinking/pondering": "chin resting on fist, looking up thoughtfully, contemplative expression",
    "thinking/smirk": "sly mischievous smirk, half-lidded eyes, one eyebrow raised, planning something",
    "toast/raising_glass": "holding up a glass for a toast, warm smile, celebratory expression",
}

DELAY_SECONDS = 120
SKIP_THRESHOLD = 25000  # Skip files > 25KB (already generated)
INITIAL_COOLDOWN = 300  # 5 min initial cooldown


def generate_sprite(pose_name: str, pose_desc: str, force: bool = False) -> bool:
    """Generate a single sprite. Returns True on success."""
    rel_path = os.path.join(CHARACTER_DIR, f"{pose_name}.png")
    os.makedirs(os.path.dirname(rel_path), exist_ok=True)

    if not force and os.path.exists(rel_path):
        size = os.path.getsize(rel_path)
        if size > SKIP_THRESHOLD:
            print(f"  SKIP {pose_name} (already {size:,} bytes)")
            return True

    prompt = f"{SONIC_APPEARANCE}, {pose_desc}"
    encoded = urllib.parse.quote(prompt)
    url = f"https://image.pollinations.ai/prompt/{encoded}?width=512&height=512&nologo=true"

    for attempt in range(3):
        try:
            resp = requests.get(url, timeout=120, headers={"User-Agent": "SonicSpriteGen/1.0"})
            if resp.status_code == 200 and len(resp.content) > 5000:
                with open(rel_path, "wb") as f:
                    f.write(resp.content)
                print(f"  OK: {pose_name} ({len(resp.content):,} bytes)")
                return True
            elif resp.status_code == 402:
                wait = 90 * (attempt + 1)
                print(f"  Rate limited (attempt {attempt+1}/3), waiting {wait}s...")
                time.sleep(wait)
                continue
            else:
                print(f"  FAIL: {pose_name} (status={resp.status_code}, size={len(resp.content)})")
                return False
        except Exception as e:
            print(f"  ERROR: {pose_name} ({e})")
            return False
    print(f"  FAIL: {pose_name} (max retries exceeded)")
    return False


def main():
    force = "--force" in sys.argv
    sorted_poses = sorted(POSES.items())
    total = len(sorted_poses)
    success = 0
    fail = 0

    print(f"=== Sonic Sprite Generator ===")
    print(f"Total poses: {total}")
    print(f"Force regenerate: {force}")
    print(f"Delay between requests: {DELAY_SECONDS}s")
    print(f"Initial cooldown: {INITIAL_COOLDOWN}s...")
    time.sleep(INITIAL_COOLDOWN)
    print(f"Starting generation...")
    print()

    for i, (pose_name, pose_desc) in enumerate(sorted_poses, 1):
        # Check if already exists (skip without delay)
        rel_path = os.path.join(CHARACTER_DIR, f"{pose_name}.png")
        already_exists = (
            not force
            and os.path.exists(rel_path)
            and os.path.getsize(rel_path) > SKIP_THRESHOLD
        )

        print(f"[{i}/{total}] {'SKIP' if already_exists else 'Generating'} {pose_name}...")
        if already_exists:
            size = os.path.getsize(rel_path)
            print(f"  SKIP {pose_name} (already {size:,} bytes)")
            success += 1
            continue

        ok = generate_sprite(pose_name, pose_desc, force)
        if ok:
            success += 1
        else:
            fail += 1

        if i < total:
            print(f"  Waiting {DELAY_SECONDS}s before next...")
            time.sleep(DELAY_SECONDS)

    print(f"\n=== DONE ===")
    print(f"Success: {success}/{total}")
    print(f"Failed: {fail}/{total}")


if __name__ == "__main__":
    main()
