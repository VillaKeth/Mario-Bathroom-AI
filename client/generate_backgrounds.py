"""Generate background images for the Mario AI Pygame client."""
import requests
import os
import time
import random

BACKGROUNDS_DIR = os.path.join(os.path.dirname(__file__), "assets", "backgrounds")
os.makedirs(BACKGROUNDS_DIR, exist_ok=True)

BACKGROUNDS = [
    ("bathroom_luxury", "A luxurious modern bathroom interior with marble tiles, warm ambient lighting, vanity mirror with LED border, clean minimalist design, cinematic lighting, photorealistic, 8K"),
    ("space_station", "Interior of a futuristic space station observation deck, large windows showing Earth and stars, soft blue ambient lighting, sleek metallic surfaces, sci-fi atmosphere, photorealistic"),
    ("enchanted_forest", "Magical enchanted forest clearing at twilight, glowing mushrooms and fireflies, soft ethereal purple and teal lighting, mystical atmosphere, fantasy art style"),
    ("neon_city", "Cyberpunk neon-lit city alleyway at night, rain-soaked streets reflecting colorful neon signs, purple and pink ambient glow, atmospheric fog, blade runner style"),
    ("cozy_library", "A cozy warm library interior with floor-to-ceiling bookshelves, reading lamp glow, wooden furniture, fireplace, warm golden amber lighting, photorealistic"),
    ("japanese_garden", "Serene Japanese zen garden at sunset, cherry blossom trees, stone lantern, koi pond reflection, soft warm pink and orange sky, peaceful atmosphere"),
    ("underwater", "Deep underwater coral reef scene, bioluminescent sea creatures, light rays filtering through water surface, blue and teal ambient, ethereal underwater atmosphere"),
    ("retro_arcade", "Retro 80s arcade interior with rows of glowing arcade cabinets, neon tube lighting, checkered floor, synthwave aesthetic, warm nostalgia vaporwave colors"),
]


def generate_background(name, prompt):
    outpath = os.path.join(BACKGROUNDS_DIR, f"{name}.jpg")
    if os.path.exists(outpath) and os.path.getsize(outpath) > 5000:
        print(f"  SKIP {name} (exists)")
        return True

    encoded = requests.utils.quote(prompt)
    seed = random.randint(1, 999999)
    url = f"https://image.pollinations.ai/prompt/{encoded}?width=800&height=600&nologo=true&seed={seed}"

    for attempt in range(5):
        try:
            r = requests.get(url, timeout=120)
            if r.status_code == 200 and len(r.content) > 5000:
                with open(outpath, "wb") as f:
                    f.write(r.content)
                print(f"  OK {name} ({len(r.content) // 1024}KB)")
                return True
            else:
                print(f"  Retry {name} (HTTP {r.status_code}, {len(r.content)} bytes)")
                time.sleep(20 * (attempt + 1))
        except Exception as e:
            print(f"  Error {name}: {e}")
            time.sleep(20)

    print(f"  FAILED {name}")
    return False


if __name__ == "__main__":
    print(f"Generating {len(BACKGROUNDS)} backgrounds...")
    ok = 0
    for name, prompt in BACKGROUNDS:
        if generate_background(name, prompt):
            ok += 1
        time.sleep(15)
    print(f"\nDone: {ok}/{len(BACKGROUNDS)} backgrounds generated")
    print(f"Saved to: {BACKGROUNDS_DIR}")
