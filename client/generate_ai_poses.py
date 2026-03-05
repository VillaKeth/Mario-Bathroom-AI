"""
Mario AI Pose Generator — Using SubNP Free API (magic model)
Generates high-quality 3D Mario poses via free AI image generation.
No API key required.
"""
import requests
import json
import time
import os
import sys

DEBUG_GEN = True

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'mario_3d_assets', 'ai_poses')
os.makedirs(OUTPUT_DIR, exist_ok=True)

API_URL = 'https://subnp.com/api/free/generate'
MODEL = 'magic'

# Style suffix appended to every prompt for consistency
STYLE_SUFFIX = ", 3D rendered figurine style, clean gray studio background, full body shot, highly detailed, Nintendo official art quality, soft studio lighting"

POSE_CATEGORIES = {
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
        ("determined", "Super Mario with intense determined expression, fist raised powerfully, focused fierce eyes, hero stance"),
        ("idea", "Super Mario having a eureka moment, finger pointing up excitedly, light bulb above head, bright realization"),
        ("dizzy", "Super Mario looking dizzy and disoriented, spiral swirl eyes, wobbling stance, stars circling his head"),
        ("suspicious", "Super Mario looking suspicious, squinting eyes narrowly, leaning to peek, detective-like investigating pose"),
    ],
    "sleep": [
        ("sleepy", "Super Mario looking very sleepy and drowsy, heavy half-closed drooping eyes, big yawn, slouching, small Zzz"),
        ("sleeping", "Super Mario fast asleep standing up, eyes fully closed peacefully, head tilted to side, big Zzz letters floating"),
        ("yawning", "Super Mario mid-yawn with mouth stretched very wide open, one hand covering mouth, eyes squeezed, stretching"),
    ],
    "movement": [
        ("jumping", "Super Mario in his iconic mid-air jump pose, one fist raised high, knees bent, classic Nintendo jump, shadow below"),
        ("running", "Super Mario running fast forward dynamically, arms pumping, determined face, motion speed lines"),
        ("dancing_1", "Super Mario dancing happily, one arm up one arm down, disco dance pose, joyful expression, music notes"),
        ("dancing_2", "Super Mario doing a fun spin dance move, arms spread out, happy energetic party dance"),
        ("pointing", "Super Mario pointing forward directly at the viewer confidently, arm fully extended, bold dynamic pose"),
        ("flexing", "Super Mario flexing both arms showing muscles, strong bodybuilder pose, proud powerful expression"),
        ("crouching", "Super Mario crouching down low, body compressed ready to spring, coiled athletic pose"),
        ("sliding", "Super Mario doing a cool ground slide, one leg extended forward, dynamic action pose, dust trail"),
        ("tiptoeing", "Super Mario tiptoeing carefully and quietly, exaggerated sneaky walk, hands up for balance, hushed"),
    ],
    "action": [
        ("eating_mushroom", "Super Mario eating a red Super Mushroom power-up, holding mushroom near his open mouth, delighted sparkles"),
        ("salute", "Super Mario doing a crisp military salute with hand at his cap brim, standing straight and respectful"),
        ("shrug", "Super Mario doing an exaggerated shrug, both palms up, shoulders raised high, confused innocent expression"),
        ("facepalm", "Super Mario doing a dramatic facepalm, hand covering face in total disbelief, comedic disappointment"),
        ("dabbing", "Super Mario doing the classic dab dance move, one arm extended the other bent covering face"),
    ],
    "powerup": [
        ("star_power", "Super Mario glowing with golden Star Power invincibility, rainbow shimmering aura, flashing colors, powerful"),
        ("fire_mario", "Fire Mario with white cap and red overalls, throwing an orange fireball from his hand, flames around"),
        ("ice_mario", "Ice Mario with light blue and white frozen color scheme, holding a glowing ice ball, frost crystals"),
        ("mega_mario", "Giant Mega Mario after eating Mega Mushroom, oversized and towering, powerful dominant pose"),
        ("mini_mario", "Tiny Mini Mario after eating Mini Mushroom, very small and adorable, cute tiny squeaky pose"),
        ("metal_mario", "Metal Mario with entire body in shiny metallic silver chrome, reflective surface, heavy powerful"),
        ("gold_mario", "Gold Mario with entire body in brilliant golden shine, luxurious golden glow, coins scattered around"),
    ],
}


def generate_image(prompt, retries=5):
    """Generate an image using SubNP free API with retry logic."""
    full_prompt = prompt + STYLE_SUFFIX
    
    for attempt in range(retries):
        try:
            if DEBUG_GEN:
                print(f"    [DEBUG_GEN] Attempt {attempt + 1}/{retries}")
            
            resp = requests.post(
                API_URL,
                json={'prompt': full_prompt, 'model': MODEL},
                timeout=180,
                stream=True,
                headers={'Connection': 'keep-alive'}
            )
            
            if resp.status_code != 200:
                if DEBUG_GEN:
                    print(f"    [DEBUG_GEN] HTTP {resp.status_code}")
                continue
            
            img_url = None
            for line in resp.iter_lines(decode_unicode=True):
                if not line or not line.startswith('data:'):
                    continue
                try:
                    data = json.loads(line[5:].strip())
                except json.JSONDecodeError:
                    continue
                status = data.get('status', '')
                
                if DEBUG_GEN:
                    print(f"    [DEBUG_GEN] SSE: {status} - {data.get('message', '')}")
                
                if status == 'error':
                    break
                
                img_url = data.get('image_url') or data.get('url') or data.get('imageUrl')
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


def generate_all_poses():
    """Generate all Mario poses."""
    total = sum(len(poses) for poses in POSE_CATEGORIES.values())
    completed = 0
    failed = 0
    skipped = 0
    
    print(f"\n{'='*60}")
    print(f"  MARIO AI POSE GENERATOR — SubNP Magic Model")
    print(f"  Total poses to generate: {total}")
    print(f"  Output: {OUTPUT_DIR}")
    print(f"{'='*60}\n")
    
    for category, poses in POSE_CATEGORIES.items():
        cat_dir = os.path.join(OUTPUT_DIR, category)
        os.makedirs(cat_dir, exist_ok=True)
        
        print(f"\n--- {category.upper()} ({len(poses)} poses) ---")
        
        for pose_id, prompt in poses:
            filepath = os.path.join(cat_dir, f"{pose_id}.png")
            
            # Skip if already exists
            if os.path.exists(filepath) and os.path.getsize(filepath) > 1000:
                print(f"  [{completed + 1}/{total}] {pose_id} — SKIPPED (exists)")
                skipped += 1
                completed += 1
                continue
            
            print(f"  [{completed + 1}/{total}] {pose_id} — Generating...")
            start = time.time()
            
            img_data = generate_image(prompt)
            elapsed = time.time() - start
            
            if img_data:
                with open(filepath, 'wb') as f:
                    f.write(img_data)
                size_kb = len(img_data) / 1024
                print(f"  [{completed + 1}/{total}] {pose_id} — OK ({size_kb:.0f}KB, {elapsed:.1f}s)")
            else:
                print(f"  [{completed + 1}/{total}] {pose_id} — FAILED after {elapsed:.1f}s")
                failed += 1
            
            completed += 1
            
            # Rate limiting: wait between requests (longer to avoid drops)
            time.sleep(5)
    
    print(f"\n{'='*60}")
    print(f"  DONE!")
    print(f"  Generated: {completed - failed - skipped}/{total}")
    print(f"  Skipped:   {skipped}")
    print(f"  Failed:    {failed}")
    print(f"{'='*60}\n")
    
    return completed, failed, skipped


def generate_gallery():
    """Generate an HTML gallery of all generated poses."""
    html = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Mario AI Poses — AI Generated</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { background: #1a1a2e; color: #e0e0e0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 20px; }
h1 { color: #e63946; text-align: center; margin-bottom: 5px; font-size: 2em; }
.subtitle { text-align: center; color: #888; margin-bottom: 30px; }
h2 { color: #f4a261; padding: 15px 0 10px; border-bottom: 2px solid #e63946; margin-top: 30px; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 15px; margin-top: 15px; }
.card { background: #16213e; border-radius: 10px; overflow: hidden; border: 1px solid #333; transition: transform 0.2s; cursor: pointer; }
.card:hover { transform: scale(1.02); border-color: #e63946; }
.card img { width: 100%; height: 280px; object-fit: contain; background: #0a0a1a; }
.card .info { padding: 10px; }
.card .info h3 { color: #f4a261; font-size: 14px; }
.card .info p { color: #888; font-size: 11px; margin-top: 3px; }
.modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.9); z-index: 1000; justify-content: center; align-items: center; }
.modal.active { display: flex; }
.modal img { max-width: 90%; max-height: 90%; object-fit: contain; }
.modal .close { position: absolute; top: 20px; right: 30px; color: white; font-size: 40px; cursor: pointer; }
.stats { text-align: center; background: #16213e; padding: 15px; border-radius: 10px; margin-bottom: 20px; }
.stats span { margin: 0 15px; }
</style>
</head>
<body>
<h1>🍄 Mario AI Poses — AI Generated</h1>
<p class="subtitle">Generated with SubNP Magic Model — free AI image generation</p>
"""
    
    total_count = 0
    category_icons = {
        'neutral': '😐', 'greeting': '👋', 'speech': '💬',
        'positive': '😄', 'negative': '😢', 'thinking': '🤔',
        'sleep': '💤', 'movement': '🏃', 'action': '⚡', 'powerup': '⭐',
    }
    
    for category, poses in POSE_CATEGORIES.items():
        cat_dir = os.path.join(OUTPUT_DIR, category)
        icon = category_icons.get(category, '🎮')
        existing = [p for p in poses if os.path.exists(os.path.join(cat_dir, f"{p[0]}.png"))]
        
        html += f'\n<h2>{icon} {category.title()} ({len(existing)}/{len(poses)})</h2>\n<div class="grid">\n'
        
        for pose_id, prompt in poses:
            filepath = os.path.join(cat_dir, f"{pose_id}.png")
            if os.path.exists(filepath):
                rel_path = f"{category}/{pose_id}.png"
                html += f'''<div class="card" onclick="showModal('{rel_path}')">
<img src="{rel_path}" alt="{pose_id}" loading="lazy">
<div class="info"><h3>{pose_id}</h3><p>{prompt[:80]}...</p></div>
</div>\n'''
                total_count += 1
        
        html += '</div>\n'
    
    html += f"""
<div class="stats"><strong>Total images:</strong> <span>{total_count}</span></div>

<div class="modal" id="modal" onclick="this.classList.remove('active')">
<span class="close">&times;</span>
<img id="modalImg" src="">
</div>

<script>
function showModal(src) {{
    document.getElementById('modalImg').src = src;
    document.getElementById('modal').classList.add('active');
}}
document.addEventListener('keydown', e => {{
    if (e.key === 'Escape') document.getElementById('modal').classList.remove('active');
}});
</script>
</body>
</html>"""
    
    gallery_path = os.path.join(OUTPUT_DIR, 'index.html')
    with open(gallery_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"Gallery saved to {gallery_path}")


if __name__ == '__main__':
    # Check for --gallery-only flag
    if '--gallery-only' in sys.argv:
        generate_gallery()
    else:
        generate_all_poses()
        generate_gallery()
