"""Generate AI sprites for Reze (Chainsaw Man) using Pollinations.ai free image API.

Run: python gen_reze_sprites.py
Skips poses that already exist and are > 25KB.
Use --force to regenerate all.
"""
import os, sys, time, requests, urllib.parse

SPRITES_DIR = os.path.join("characters", "reze", "sprites")

REZE_BASE = (
    "Reze from Chainsaw Man anime, short dark hair, dark red eyes, "
    "choker necklace with grenade pin at neck, fair skin, "
    "wearing a dark café apron over casual clothes, "
    "young woman, slender build, gentle yet dangerous expression, "
    "full body view, pure white background, clean anime art style, "
    "cel-shaded illustration, high quality, no text, no watermark, "
    "consistent character design, one character only"
)

WIDTH, HEIGHT = 768, 1024

POSES = {
    # Positive emotions
    "positive/happy":    "genuinely happy smile, eyes bright, arms slightly open, warm welcoming expression",
    "positive/excited":  "excited expression, hands up in the air, jumping slightly, big grin",
    "positive/laughing": "laughing with hand over mouth, eyes crinkled, head tilted back slightly",
    "positive/love":     "loving expression, hands clasped to cheek, starry-eyed, soft blush",
    "positive/proud":    "proud stance, hands on hips, chin up, confident smile",
    # Negative emotions
    "negative/sad":         "sad expression, eyes downcast, shoulders slumped, slight pout, tears threatening",
    "negative/angry":       "angry glare, furrowed brows, fists clenched, sharp dangerous look",
    "negative/annoyed":     "annoyed expression, arms crossed, eyes half-closed, slight frown",
    "negative/nervous":     "nervous fidgeting, hands clasped, biting lip, anxious wide eyes",
    "negative/scared":      "frightened expression, hands up defensively, eyes wide, stepping back",
    "negative/embarrassed": "blushing furiously, hands over cheeks, looking away, flustered expression",
    "negative/disgusted":   "disgusted face, tongue slightly out, hand raised in refusal, leaning back",
    "negative/grossed_out": "grossed out expression, both hands up, leaning far back, grimacing",
    # Thinking emotions
    "thinking/confused":    "head tilted, eyebrow raised quizzically, finger on chin, puzzled look",
    "thinking/thinking":    "finger to lips, eyes looking up, thoughtful pensive expression",
    "thinking/curious":     "curious leaning forward slightly, eyes wide and interested, hands behind back",
    "thinking/determined":  "determined focused glare, jaw set, fists at sides, intense eyes",
    "thinking/mischievous": "mischievous smirk, one eyebrow up, side-eye glance, plotting expression",
    "thinking/shocked":     "shocked expression, mouth open, eyes wide, hands to face",
    "thinking/idea":        "lightbulb moment, finger raised, eyes lit up, excited realization",
    "thinking/surprised":   "pleasantly surprised, eyebrows raised, small gasp, hand over mouth",
    # Reactions
    "reactions/mind_blown": "mind blown gesture, hands at temples, jaw dropped, eyes wide",
    "reactions/sassy":      "sassy pose, one hand on hip, finger wagging, knowing smirk",
    "reactions/cringe":     "cringing expression, eyes squeezed shut, teeth gritted, shoulders raised",
    "reactions/impressed":  "impressed expression, eyebrows raised, small nod, arms crossed approvingly",
    # Memorial
    "memorial/moment_of_silence": "solemn expression, eyes closed, hands clasped at chest, head slightly bowed, respectful pose",
    # Party
    "party/celebrate": "celebrating with arms raised, confetti implied by pose, huge grin, eyes sparkling",
    # Sleep
    "sleep/yawning":  "yawning with hand covering mouth, eyes half-closed, sleepy expression",
    "sleep/sleepy":   "drowsy expression, eyes drooping, swaying slightly, exhausted look",
    "sleep/sleeping": "eyes closed peacefully, hands together beside cheek, sleeping pose, zzz",
    # Neutral
    "neutral/idle": "neutral relaxed standing pose, slight soft smile, at ease, natural stance",
    # Toast
    "toast/raising_glass": "raising an imaginary glass in a toast gesture, warm smile, celebratory",
    # Birthday
    "birthday/birthday": "holding imaginary birthday cake pose, party hat, delighted expression",
    # Speech
    "speech/talking":         "talking expressively, one hand gesturing, mouth slightly open, engaged",
    "speech/talking_excited": "talking excitedly, both hands gesturing, leaning forward, animated face",
    "speech/listening":       "listening attentively, head tilted, eyes focused, patient expression",
    # Greeting
    "greeting/wave":    "enthusiastic waving hello, one arm raised high, bright friendly smile",
    "greeting/farewell": "waving goodbye, gentle smile, slight turn as if leaving, warm farewell",
    # Movement
    "movement/dancing":  "dancing pose, one leg lifted, arms gracefully out, joyful movement",
    "movement/entering": "walking forward with confidence, one foot stepping ahead, slight smile",
}


def generate_sprite(pose_key: str, pose_desc: str) -> bool:
    prompt = f"{REZE_BASE}, {pose_desc}"
    encoded = urllib.parse.quote(prompt)
    url = f"https://image.pollinations.ai/prompt/{encoded}?width={WIDTH}&height={HEIGHT}&nologo=true"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    filepath = os.path.join(SPRITES_DIR, pose_key.replace("/", os.sep) + ".png")
    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    for attempt in range(8):
        try:
            r = requests.get(url, timeout=120, headers=headers)
            if r.status_code == 402:
                print(f"  Rate limited (402), waiting 90s...")
                time.sleep(90)
                continue
            if r.status_code != 200:
                print(f"  HTTP {r.status_code}, waiting 20s...")
                time.sleep(20)
                continue

            data = r.content
            is_png = data[:4] == b'\x89PNG'
            is_jpg = data[:3] == b'\xff\xd8\xff'
            if not (is_png or is_jpg):
                print(f"  Not a valid image ({len(data)} bytes), waiting 20s...")
                time.sleep(20)
                continue

            if len(data) < 5000:
                print(f"  Too small ({len(data)} bytes), waiting 20s...")
                time.sleep(20)
                continue

            with open(filepath, "wb") as f:
                f.write(data)
            print(f"  OK: {pose_key} ({len(data):,} bytes)")
            return True

        except Exception as e:
            print(f"  Error: {e}, retrying...")
            time.sleep(20)

    print(f"  FAILED after 8 attempts: {pose_key}")
    return False


def main():
    os.makedirs(SPRITES_DIR, exist_ok=True)
    total = len(POSES)
    success = 0
    failed = []

    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    only = args[0] if args else None
    force = "--force" in sys.argv

    for i, (pose_key, pose_desc) in enumerate(POSES.items()):
        if only and pose_key != only:
            continue
        filepath = os.path.join(SPRITES_DIR, pose_key.replace("/", os.sep) + ".png")
        if os.path.exists(filepath) and os.path.getsize(filepath) > 25000 and not force:
            print(f"[{i+1}/{total}] SKIP {pose_key} ({os.path.getsize(filepath):,} bytes)")
            success += 1
            continue

        print(f"[{i+1}/{total}] Generating {pose_key}...")
        if generate_sprite(pose_key, pose_desc):
            success += 1
        else:
            failed.append(pose_key)

        # Pollinations free tier: ~90s cooldown between successful generations
        if i < total - 1:
            print(f"  Waiting 90s before next...")
            time.sleep(90)

    print(f"\nDone! {success}/{total} generated successfully")
    if failed:
        print(f"Failed: {', '.join(failed)}")


if __name__ == "__main__":
    main()
