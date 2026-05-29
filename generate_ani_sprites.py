"""Generate Ani sprites via Pollinations.ai image API."""
import os, time, sys, requests

SPRITES_DIR = os.path.join(os.path.dirname(__file__), "characters", "ani", "sprites")

# Ani's consistent appearance description - matches reference image exactly
ANI_BASE = (
    "anime character sprite, blonde girl with twintails held by black ribbons, "
    "bright blue eyes, gothic lolita navy blue off-shoulder dress, "
    "black corset with lacing, black lace choker necklace, "
    "black fingerless gloves with arm wraps, asymmetric pleated skirt, "
    "one leg fishnet stockings one leg sheer, black platform boots, "
    "full body view, pure white background, clean game sprite style, "
    "consistent character design, high quality anime illustration, "
    "no text, no watermark, no extra characters"
)

# Pose descriptions for each sprite
POSES = {
    "birthday/birthday": "holding a birthday cake with candles, party hat, happy celebration pose",
    "greeting/farewell": "waving goodbye with a gentle smile, one hand raised",
    "greeting/wave": "enthusiastic waving hello, both arms up, warm welcoming smile",
    "memorial/moment_of_silence": "eyes closed, hands clasped together, solemn respectful pose, head slightly bowed",
    "movement/dancing": "dynamic dancing pose, one leg lifted, arms gracefully extended, joyful expression",
    "movement/entering": "walking forward pose, one foot stepping ahead, confident stride, slight smile",
    "negative/angry": "angry expression, furrowed brows, clenched fists, aggressive stance",
    "negative/annoyed": "annoyed eye roll, arms crossed, slightly turned away, irritated expression",
    "negative/disgusted": "disgusted face, tongue out slightly, one hand up in rejection",
    "negative/embarrassed": "blushing face, hands covering cheeks, looking away shyly",
    "negative/grossed_out": "grossed out expression, hands up defensively, leaning back",
    "negative/nervous": "nervous fidgeting, hands together, biting lip, worried eyes",
    "negative/sad": "sad expression, looking down, slumped shoulders, tear in eye",
    "negative/scared": "scared pose, hands near face, wide eyes, stepping back",
    "neutral/idle": "standing relaxed, slight smile, hands at sides, calm neutral pose",
    "neutral/thinking": "hand on chin, thoughtful expression, slight head tilt, gazing to the side",
    "party/celebrate": "celebration pose, confetti, arms raised triumphantly, huge smile",
    "positive/excited": "jumping excitedly, fists pumped, sparkling eyes, huge grin",
    "positive/happy": "genuinely happy smile, hands clasped together, bright expression",
    "positive/laughing": "laughing heartily, one hand near mouth, eyes squeezed shut from laughing",
    "positive/love": "heart eyes, hands forming heart shape, blushing with love expression",
    "positive/proud": "proud confident stance, hands on hips, chin up, satisfied smirk",
    "reactions/cringe": "cringe expression, one eye squinting, looking away uncomfortable",
    "reactions/impressed": "impressed expression, mouth slightly open, eyebrows raised, clapping",
    "reactions/mind_blown": "mind blown pose, hands on head, shocked wide eyes, explosive background effect",
    "reactions/sassy": "sassy pose, one hand on hip, finger wagging, confident smirk",
    "sleep/sleeping": "sleeping peacefully, eyes closed, head tilted to side, zzz effect",
    "sleep/sleepy": "drowsy expression, half-closed eyes, yawning slightly, rubbing eyes",
    "sleep/yawning": "big yawn, mouth wide open, stretching arms up",
    "speech/listening": "attentive listening pose, hand near ear, curious engaged expression",
    "speech/talking": "talking animated, one hand gesturing, mouth open speaking",
    "speech/talking_excited": "excited talking, both hands gesturing wildly, enthusiastic expression",
    "thinking/confused": "confused expression, question mark above head, head tilted, scratching head",
    "thinking/curious": "curious lean forward, finger on lip, wide interested eyes",
    "thinking/determined": "determined expression, fist clenched, intense focused eyes",
    "thinking/idea": "lightbulb moment, finger pointing up, eyes bright, excited eureka expression",
    "thinking/mischievous": "mischievous smirk, hands behind back, sly knowing expression",
    "thinking/shocked": "shocked face, hands on cheeks, mouth wide open, extreme surprise",
    "thinking/surprised": "surprised expression, eyebrows up, hands slightly raised, oh expression",
    "thinking/thinking": "deep in thought, finger on chin, looking up contemplatively",
    "toast/raising_glass": "raising a glass for a toast, one hand holding glass up, warm smile",
}

WIDTH = 512
HEIGHT = 512

def generate_sprite(pose_key: str, pose_desc: str) -> bool:
    prompt = f"{ANI_BASE}, {pose_desc}"
    url = f"https://image.pollinations.ai/prompt/{requests.utils.quote(prompt)}?width={WIDTH}&height={HEIGHT}&nologo=true"
    
    filepath = os.path.join(SPRITES_DIR, pose_key.replace("/", os.sep) + ".png")
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    for attempt in range(8):  # up to 8 attempts
        try:
            r = requests.get(url, timeout=120, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code == 402:
                wait = 25 + attempt * 10  # progressive backoff
                print(f"  Rate limited, waiting {wait}s (attempt {attempt+1}/8)...")
                time.sleep(wait)
                continue
            if r.status_code != 200:
                print(f"  HTTP {r.status_code}, waiting 20s...")
                time.sleep(20)
                continue
            
            with open(filepath, "wb") as f:
                f.write(r.content)
            
            size = len(r.content)
            if size < 5000:
                print(f"  Too small ({size}b), retrying...")
                time.sleep(20)
                continue
            print(f"  OK: {pose_key} ({size:,} bytes)")
            return True
        except Exception as e:
            print(f"  Error: {e}, retrying...")
            time.sleep(20)
    
    print(f"  FAILED after 8 attempts: {pose_key}")
    return False

def main():
    total = len(POSES)
    success = 0
    failed = []
    
    # Check if specific pose requested (skip flags like --force)
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    only = args[0] if args else None
    force = "--force" in sys.argv
    
    for i, (pose_key, pose_desc) in enumerate(POSES.items()):
        if only and pose_key != only:
            continue
        # Skip already-generated sprites unless forcing
        filepath = os.path.join(SPRITES_DIR, pose_key.replace("/", os.sep) + ".png")
        if os.path.exists(filepath) and os.path.getsize(filepath) > 25000 and not force:
            print(f"[{i+1}/{total}] SKIP {pose_key} (already {os.path.getsize(filepath):,} bytes)")
            success += 1
            continue
        
        print(f"[{i+1}/{total}] Generating {pose_key}...")
        if generate_sprite(pose_key, pose_desc):
            success += 1
        else:
            failed.append(pose_key)
        
        # Wait between successful generations to avoid rate limiting
        # Pollinations needs ~90s cooldown between generations
        if i < total - 1:
            print(f"  Waiting 90s before next...")
            time.sleep(90)
    
    print(f"\nDone! {success}/{total} generated successfully")
    if failed:
        print(f"Failed: {', '.join(failed)}")

if __name__ == "__main__":
    main()
