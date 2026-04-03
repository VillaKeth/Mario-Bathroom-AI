"""
Regenerate ALL Mario poses except memorial/honor.
Uses SubNP free API with improved prompts for better quality.
Runs background removal with rembg after generation.
"""
import requests
import json
import time
import os
import sys
from io import BytesIO
from PIL import Image

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
RAW_DIR = os.path.join(PROJECT_ROOT, "mario_3d_assets", "ai_poses")
TRANSPARENT_DIR = os.path.join(PROJECT_ROOT, "mario_3d_assets", "ai_poses_transparent")

API_URL = "https://subnp.com/api/free/generate"
MODEL = "magic"

STYLE_SUFFIX = (
    ", 3D rendered Nintendo figurine style, clean gray studio background, "
    "full body shot, highly detailed, Nintendo official art quality, soft studio lighting, "
    "vivid colors, sharp details, professional render"
)

SKIP_POSES = {("memorial", "honor")}

# ── Original 74 poses ──
ORIGINAL_POSES = {
    "neutral": [
        ("idle", "Super Mario standing in a neutral relaxed pose, arms at sides, friendly calm expression, wearing red cap with M logo, blue overalls, white gloves, brown shoes"),
        ("idle_blink", "Super Mario standing with eyes gently closed mid-blink, peaceful relaxed expression, arms at sides"),
        ("idle_wink", "Super Mario standing and winking his right eye playfully, slight smile, fun expression"),
        ("looking_left", "Super Mario standing and looking to his left with eyes shifted sideways, curious expression"),
        ("looking_right", "Super Mario standing and looking to his right with eyes shifted sideways, curious expression"),
        ("looking_up", "Super Mario standing and looking upward at the sky, wondering amazed expression"),
    ],
    "greeting": [
        ("wave_high", "Super Mario waving his right hand high above his head enthusiastically, big welcoming smile, classic greeting pose"),
        ("wave_casual", "Super Mario waving his right hand at shoulder height, friendly casual wave, warm smile"),
        ("wave_both", "Super Mario waving both hands above his head excitedly, huge joyful smile, very welcoming"),
        ("welcome_arms", "Super Mario with both arms open wide in a welcoming gesture, inviting warm expression"),
        ("farewell", "Super Mario waving goodbye with one hand raised high, slightly bittersweet but warm smile"),
        ("tip_hat", "Super Mario tipping his red cap politely with one hand, gentleman gesture, slight charming bow"),
        ("hello_sparkle", "Super Mario in a cheerful hello pose, one hand waving, sparkles and stars around him, bright joyful face"),
    ],
    "speech": [
        ("talking", "Super Mario talking with mouth open mid-speech, one hand gesturing forward, animated lively expression"),
        ("talking_excited", "Super Mario talking very excitedly with both hands gesturing wildly, wide open mouth, enthusiastic"),
        ("shouting", "Super Mario shouting loudly with hands cupped around his mouth like a megaphone, very wide open mouth"),
        ("singing", "Super Mario singing with eyes closed blissfully, mouth open in song, one hand up, musical notes around"),
        ("whistling", "Super Mario whistling a cheerful tune with puckered lips, hands behind back, casual relaxed pose"),
        ("listening", "Super Mario leaning forward with one hand cupped behind his ear, listening attentively, curious face"),
        ("shushing", "Super Mario with finger to his lips making a quiet shush gesture, sneaky conspiratorial look"),
        ("whispering", "Super Mario leaning sideways with hand cupped near mouth whispering a secret, mischievous expression"),
    ],
    "positive": [
        ("happy", "Super Mario with a huge bright beaming smile, rosy cheeks, very happy expression, hands on hips proudly"),
        ("very_happy", "Super Mario extremely happy, jumping slightly with pure joy, eyes squinted from smiling, fists pumped"),
        ("excited_jump", "Super Mario jumping high with one fist raised triumphantly in the air, classic Mario jump pose, ecstatic face"),
        ("laughing", "Super Mario laughing heartily with mouth wide open, eyes squinted shut, holding his belly, genuine laughter"),
        ("love", "Super Mario with heart-shaped eyes, dreamy loving expression, floating red hearts around him, love-struck"),
        ("proud", "Super Mario standing proudly with chest puffed out, one fist on hip, confident heroic determined look"),
        ("victorious", "Super Mario in victory pose with both arms raised high making V signs, huge triumphant smile, sparkles"),
        ("thumbs_up", "Super Mario giving a big thumbs up with right hand extended forward, encouraging supportive smile"),
        ("peace_sign", "Super Mario making a peace sign with two fingers, playful wink, fun cool casual pose"),
    ],
    "negative": [
        ("sad", "Super Mario looking sad and dejected, drooping posture, downcast eyes, frown, slightly slumped shoulders"),
        ("crying", "Super Mario crying with tears streaming down his face, eyes squeezed shut, very sad, wiping tears"),
        ("angry", "Super Mario looking very angry with deeply furrowed brows, gritted teeth, fists clenched, red-faced"),
        ("furious", "Super Mario absolutely furious, face bright red with rage, steam from ears, fists raised, shaking with anger"),
        ("annoyed", "Super Mario looking annoyed and unimpressed, arms crossed, half-lidded eyes, slight unamused frown"),
        ("disappointed", "Super Mario looking disappointed, shoulders slumped, looking down sadly, hand on forehead"),
        ("scared", "Super Mario looking terrified, very wide frightened eyes, mouth agape, trembling, backing away in fear"),
        ("nervous", "Super Mario looking nervous and anxious, visible sweat drops, biting lip, fidgeting hands worried"),
        ("embarrassed", "Super Mario looking embarrassed, blushing bright red cheeks, hand behind head sheepishly, awkward smile"),
        ("disgusted", "Super Mario looking disgusted, nose wrinkled, tongue slightly out, leaning back in revulsion"),
    ],
    "thinking": [
        ("thinking", "Super Mario in a classic thinking pose, hand on chin, looking upward thoughtfully, pondering expression"),
        ("confused", "Super Mario looking confused with head tilted, question marks floating around his head, scratching head"),
        ("curious", "Super Mario looking very curious, leaning forward eagerly, wide interested eyes, one eyebrow raised"),
        ("surprised", "Super Mario with a shocked surprised expression, eyes extremely wide, mouth in perfect O shape, hands up"),
        ("shocked", "Super Mario absolutely jaw-dropped shocked, stepping backward, hands on cheeks Home Alone style"),
        ("mischievous", "Super Mario with a sly mischievous grin, one eye winking, rubbing hands together deviously, scheming"),
        ("determined", "Super Mario looking fiercely determined, strong heroic stance, fists ready, laser focus eyes"),
        ("suspicious", "Super Mario looking very suspicious, squinting one eye, glancing sideways, hand on chin doubtfully"),
        ("dizzy", "Super Mario looking dizzy with spiral swirly eyes, stumbling off balance, stars circling above head"),
        ("idea", "Super Mario with a bright lightbulb moment, finger pointing up, eyes wide with realization, exclamation mark"),
    ],
    "sleep": [
        ("sleeping", "Super Mario peacefully sleeping standing up, eyes closed, slight snoring, Z letters floating, peaceful"),
        ("sleepy", "Super Mario looking very sleepy and drowsy, heavy drooping eyelids, big yawn starting, rubbing eye"),
        ("yawning", "Super Mario in a big wide yawn, mouth stretched wide open, eyes squeezed shut, stretching arms up"),
    ],
    "movement": [
        ("running", "Super Mario running forward at full speed, dynamic running pose, legs mid-stride, arms pumping, wind effect"),
        ("jumping", "Super Mario in his iconic high jump pose, one fist raised up, legs tucked, classic Mario jump"),
        ("crouching", "Super Mario crouching down low, one knee on ground, ready to spring up, focused expression"),
        ("sliding", "Super Mario sliding on his knees with arms outstretched, dynamic slide tackle pose, dust trail"),
        ("dancing_1", "Super Mario dancing happily, one leg up, arms swinging, big smile, classic dance move"),
        ("dancing_2", "Super Mario doing a fun dance with disco finger pointing up, other hand on hip, groovy expression"),
        ("tiptoeing", "Super Mario tiptoeing carefully and quietly, one foot forward gently, finger to lips, sneaky"),
        ("flexing", "Super Mario flexing both biceps proudly, strong man pose, confident big grin, showing off muscles"),
        ("pointing", "Super Mario pointing dramatically forward with one finger extended, bold confident expression, decisive"),
    ],
    "action": [
        ("eating_mushroom", "Super Mario eating a big red Super Mushroom with white spots, big satisfied bite, happy expression"),
        ("facepalm", "Super Mario doing a classic facepalm, hand over face, exasperated disappointed expression"),
        ("shrug", "Super Mario shrugging with both palms up, confused unsure expression, head tilted, oh well gesture"),
        ("salute", "Super Mario giving a crisp military salute, standing tall at attention, respectful serious expression"),
        ("dabbing", "Super Mario dabbing with one arm extended forward, other arm bent covering face, trendy fun pose"),
    ],
    "powerup": [
        ("fire_mario", "Fire Mario in white and red outfit, throwing a fireball from his hand, dynamic action pose, flames"),
        ("star_power", "Super Mario glowing with rainbow Star Power invincibility, sparkles and light radiating, triumphant"),
        ("mega_mario", "Mega Mario grown very large, towering powerful pose, looking down with enormous presence"),
        ("mini_mario", "Mini Mario shrunk very tiny, cute small proportions, looking up with big adorable eyes"),
        ("gold_mario", "Gold Mario covered entirely in gleaming gold, shining metallic surface, powerful stance, coin sparkles"),
        ("ice_mario", "Ice Mario in light blue and white outfit, creating ice crystal from hand, cool frosty aura"),
        ("metal_mario", "Metal Mario with silver metallic reflective body, heavy powerful stance, shining chrome effect"),
    ],
}

# ── Expanded 48 poses ──
EXPANDED_POSES = {
    "party": [
        ("cheers", "Super Mario holding up a drink glass for a toast, big celebratory smile, party streamers around, festive atmosphere"),
        ("party_hat", "Super Mario wearing a colorful party hat, celebrating with arms up, joyful excited expression, confetti falling"),
        ("confetti", "Super Mario throwing handfuls of confetti high in the air, ecstatic expression, colorful paper pieces everywhere"),
        ("cake", "Super Mario proudly presenting a large decorated birthday cake with candles, big warm smile, both hands holding cake"),
        ("balloon", "Super Mario holding a bunch of colorful party balloons in one hand, happy cheerful expression, floating balloons"),
        ("gift", "Super Mario presenting a beautifully wrapped gift box with a bow, generous warm smile, offering it forward"),
        ("countdown", "Super Mario counting down excitedly with fingers raised showing numbers, wide eager eyes, anticipation"),
        ("celebrate", "Super Mario celebrating wildly with arms up, jumping with pure joy, party poppers going off, maximum excitement"),
        ("cheering", "Super Mario cheering loudly with both fists pumped in the air, wide open mouth yelling with joy, supportive"),
        ("group_photo", "Super Mario posing for a group photo with a big smile, one arm around an invisible friend, camera-ready pose"),
    ],
    "memorial": [
        ("candle", "Super Mario solemnly holding a lit memorial candle with both hands, gentle warm candlelight on face, respectful quiet moment"),
        ("moment_of_silence", "Super Mario with head bowed respectfully, eyes closed, hands folded in front, solemn moment of silence pose"),
        ("tribute", "Super Mario placing a hand over his heart in tribute, eyes closed, deeply respectful, somber dignified pose"),
        ("remembering", "Super Mario looking up at the sky with a gentle bittersweet smile, remembering someone special, hand on heart"),
    ],
    "toast": [
        ("raising_glass", "Super Mario raising a glass high in the air for a toast, big proud warm smile, arm fully extended up"),
        ("clinking_glasses", "Super Mario reaching forward to clink glasses in a cheers motion, happy warm expression, celebrating"),
        ("shot_ready", "Super Mario holding a small shot glass ready to drink, big excited grin, anticipation, one eyebrow up"),
        ("drinking", "Super Mario taking a drink from a glass, head tilted back slightly, satisfied happy expression"),
        ("after_shot", "Super Mario reacting to a shot of strong drink, eyes wide, shaking head slightly, fun surprised reaction"),
    ],
    "bathroom": [
        ("washing_hands", "Super Mario washing his hands at a sink with lots of soap bubbles, responsible clean expression"),
        ("mirror_check", "Super Mario checking himself in a mirror, adjusting his cap, satisfied with his appearance, wink"),
        ("air_freshener", "Super Mario spraying air freshener with a relieved expression, holding nose with other hand, funny"),
        ("grossed_out", "Super Mario holding his nose shut, extremely grossed out expression, waving hand to clear the air"),
        ("knock_knock", "Super Mario knocking on a bathroom door, polite but urgent expression, one hand knocking, other hand patient"),
        ("reading", "Super Mario sitting and reading a newspaper or book, relaxed comfortable expression, casual"),
        ("thumbs_up_flush", "Super Mario giving a proud thumbs up after flushing, satisfied accomplished expression, job well done"),
        ("waiting", "Super Mario waiting outside a bathroom door impatiently, arms crossed, tapping foot, checking watch"),
    ],
    "reactions": [
        ("jaw_drop", "Super Mario with his jaw literally dropped to the ground in shock, eyes as wide as saucers, hands on cheeks"),
        ("mind_blown", "Super Mario with an exploding mind blown expression, hands on sides of head, eyes popping, sparkle effects"),
        ("slow_clap", "Super Mario doing a sarcastic slow clap, unimpressed half-lidded eyes, slight smirk, deliberate clapping"),
        ("mic_drop", "Super Mario dropping an invisible microphone, cool confident walk-away pose, sunglasses on, boss move"),
        ("eye_roll", "Super Mario rolling his eyes dramatically, head tilted back slightly, exasperated unamused expression"),
        ("double_take", "Super Mario doing a comical double take, head whipping back around, eyes bugged out, what-did-I-just-see"),
        ("sassy", "Super Mario with one hand on hip, other hand up in a sassy talk-to-the-hand gesture, knowing smirk"),
        ("impressed", "Super Mario looking genuinely impressed, nodding approvingly, eyebrows raised, respectful impressed face"),
        ("rofl", "Super Mario rolling on the floor laughing hysterically, tears of joy, holding stomach, can't stop laughing"),
        ("cringe", "Super Mario cringing hard, teeth gritted, eyes squinting, pulling back, uncomfortable expression"),
    ],
    "birthday": [
        ("birthday_boy", "Super Mario wearing a birthday crown and party outfit, pointing to himself proudly, it's-a my birthday expression"),
        ("blowing_candles", "Super Mario leaning forward to blow out birthday candles on a cake, cheeks puffed, making a wish"),
        ("opening_gift", "Super Mario excitedly tearing open a wrapped present, surprised delighted face, wrapping paper flying"),
        ("birthday_toast", "Super Mario raising a glass for a birthday toast, wearing a birthday hat, warm celebratory smile"),
        ("party_dance", "Super Mario dancing at a birthday party, fun silly dance moves, party hat on, streamers everywhere"),
    ],
    "gaming": [
        ("coin_collect", "Super Mario jumping up to grab a floating gold coin, classic coin collection pose, sparkle effects"),
        ("power_star", "Super Mario reaching up to grab a Power Star, starlight glowing on his face, wonder and awe"),
        ("game_over", "Super Mario in a dramatic game over pose, falling backward, x eyes, tongue out, comical defeat"),
        ("level_up", "Super Mario celebrating a level up with rainbow effects, growing bigger with power, triumphant face"),
        ("warp_pipe", "Super Mario emerging from a green warp pipe, arms first, surprised expression, classic pipe entrance"),
    ],
}


def generate_subnp(prompt, retries=5):
    """Generate image using SubNP free API with retry logic."""
    full_prompt = prompt + STYLE_SUFFIX
    for attempt in range(retries):
        try:
            print(f"    Attempt {attempt + 1}/{retries}...")
            resp = requests.post(
                API_URL,
                json={"prompt": full_prompt, "model": MODEL},
                timeout=180, stream=True,
                headers={"Connection": "keep-alive"},
            )
            if resp.status_code != 200:
                print(f"    HTTP {resp.status_code}")
                continue

            img_url = None
            for line in resp.iter_lines(decode_unicode=True):
                if not line or not line.startswith("data:"):
                    continue
                try:
                    data = json.loads(line[5:].strip())
                except json.JSONDecodeError:
                    continue
                if data.get("status") == "error":
                    break
                img_url = data.get("image_url") or data.get("url") or data.get("imageUrl")
                if img_url:
                    break

            if img_url:
                img_resp = requests.get(img_url, timeout=60)
                if img_resp.status_code == 200 and len(img_resp.content) > 1000:
                    return img_resp.content
        except Exception as e:
            print(f"    Error: {e}")
        time.sleep(3)
    return None


def remove_background(input_path, output_path):
    """Remove background using rembg."""
    try:
        from rembg import remove
        with open(input_path, "rb") as f:
            result = remove(f.read())
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(result)
        return True
    except Exception as e:
        print(f"    BG removal error: {e}")
        return False


def main():
    # Merge all poses
    all_poses = {}
    for cat, poses in ORIGINAL_POSES.items():
        all_poses[cat] = poses
    for cat, poses in EXPANDED_POSES.items():
        if cat in all_poses:
            all_poses[cat].extend(poses)
        else:
            all_poses[cat] = poses

    # Count total (minus skipped)
    total = sum(
        1 for cat, poses in all_poses.items()
        for pid, _ in poses
        if (cat, pid) not in SKIP_POSES
    )
    print(f"=== Regenerating {total} poses (skipping {len(SKIP_POSES)}) ===\n")

    done = 0
    failed = []
    for cat, poses in sorted(all_poses.items()):
        cat_raw = os.path.join(RAW_DIR, cat)
        cat_trans = os.path.join(TRANSPARENT_DIR, cat)
        os.makedirs(cat_raw, exist_ok=True)
        os.makedirs(cat_trans, exist_ok=True)

        for pose_id, prompt in poses:
            if (cat, pose_id) in SKIP_POSES:
                print(f"  SKIP: {cat}/{pose_id}")
                continue

            done += 1
            raw_path = os.path.join(cat_raw, f"{pose_id}.png")
            trans_path = os.path.join(cat_trans, f"{pose_id}.png")

            print(f"[{done}/{total}] {cat}/{pose_id}")

            img_data = generate_subnp(prompt)
            if not img_data:
                print(f"  FAILED: {cat}/{pose_id}")
                failed.append(f"{cat}/{pose_id}")
                continue

            # Save raw
            with open(raw_path, "wb") as f:
                f.write(img_data)
            print(f"  Saved raw: {raw_path}")

            # Remove background
            if remove_background(raw_path, trans_path):
                print(f"  Saved transparent: {trans_path}")
            else:
                print(f"  BG removal failed, copying raw")
                with open(trans_path, "wb") as f:
                    f.write(img_data)

            time.sleep(5)  # Rate limit

    print(f"\n=== DONE: {done - len(failed)}/{total} succeeded, {len(failed)} failed ===")
    if failed:
        print("Failed poses:")
        for f in failed:
            print(f"  - {f}")


if __name__ == "__main__":
    main()
