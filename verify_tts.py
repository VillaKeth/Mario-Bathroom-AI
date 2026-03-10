"""Automated TTS quality verification: generate audio then transcribe with Whisper to verify."""
import urllib.request, urllib.parse, tempfile, os, sys, time, re
import difflib

# Use the same Python env that has faster-whisper
try:
    from faster_whisper import WhisperModel
except ImportError:
    print("ERROR: faster-whisper not found. Install with: pip install faster-whisper")
    sys.exit(1)

def clean_for_compare(text):
    """Normalize text for comparison (lowercase, strip punctuation)."""
    t = text.lower().strip()
    t = re.sub(r'[^a-z0-9\s]', '', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t

def similarity(a, b):
    """Return similarity ratio between two strings (0-1)."""
    return difflib.SequenceMatcher(None, a, b).ratio()

# Expected clean text after our cleaning pipeline
test_cases = [
    ("It's-a me, Mario!", "It's a me, Mario!"),
    ("Let's-a go!", "Let's a go!"),
    ("What's-a going on?", "What's a going on?"),
    ("That's-a funny!", "That's a funny!"),
    ("Nice to meet-a you!", "Nice to meet a you!"),
    ("Take-a care!", "Take a care!"),
    ("This-a soap dispenser is very modern!", "This a soap dispenser is very modern!"),
    ("Not like-a my castle pipes!", "Not like a my castle pipes!"),
    ("Time flies-a when you're having fun!", "Time flies a when you're having fun!"),
    ("Good-a time to recharge!", "Good a time to recharge!"),
    ("The party is great - everyone is having fun!", "The party is great, everyone is having fun!"),
    ("Bowser is mean - but I still win!", "Bowzer is mean, but I still win!"),
    ("One coin - two coins - three coins!", "One coin, two coins, three coins!"),
    ("The mushroom kingdom -- what a place!", "The mushroom kingdom, what a place!"),
    ("Bathroom breaks --- very important!", "Bathroom breaks, very important!"),
    ("Ka-ching ka-ching! Mine cart madness!", "Mine cart madness!"),
    ("WOO-HA-HEEEEEEEE! I'm Mario!", "Ha He! I'm Mario!"),
    ("WAHOO! That was amazing!", "That was amazing!"),
    ("BOWSER is going DOWN!", "Bowzer is going Down!"),
    ("I found a MUSHROOM and a STAR!", "I found a Mushroom and a Star!"),
    ("MAMA MIA that's incredible!", "Mama Mia that's incredible!"),
    ("SUCTION TO THE BEAT! Plunge and boogie!", "Suction To The Beat! Plunge and boogie!"),
    ("The POWER of the FIRE FLOWER!", "The Power of the Fire Flower!"),
    ("Hmm, let me think!", "Let me think!"),
    ("Hmmm, I wonder what Luigi is doing...", "I wonder what Luigi is doing..."),
    ("Umm, I'm not sure about that.", "I'm not sure about that."),
    ("Uhh, maybe try again?", "Maybe try again?"),
    ("Ahh, that feels nice!", "That feels nice!"),
    ("Ohh, what a surprise!", "What a surprise!"),
    ("Brrrr, it's cold in here!", "It's cold in here!"),
    ("Shh, Bowser might hear us!", "Bowzer might hear us!"),
    ("Wahoo! Here we go!", "Here we go!"),
    ("Okie dokie!", "Okey dokey!"),
    ("I wonder if Chain Chomps count as pets? They're very bitey!", "I wonder if Chain Chomps count as pets? They're very biting!"),
    ("Pfft, that's nothing!", "That's nothing!"),
    ("Da da daa! Level complete!", "Da da da! Level complete!"),
    ("Boing boing boing! Jump jump jump!", "Jump jump jump!"),
    ("Whoosh! There goes the fireball!", "There goes the fireball!"),
    ("Splish splash, bathroom fun!", "Bathroom fun!"),
    ("Tick tock tick tock, hurry up!", "Hurry up!"),
    ("Boom! Another Goomba defeated!", "Another Goomba defeated!"),
    ("The mushroom kingdom.. da-da-daa!", "The mushroom kingdom.. da da da!"),
    ("Super Star Power!", "Super Star Power!"),
    ("I give it a 10/10!", "I give it a 10 out of 10!"),
    ("The score is 100 & counting!", "The score is 100 and counting!"),
    ("Email me at mario@mushroom.kingdom", "Email me at mario at mushroom.kingdom"),
    ("It's 50% off on mushrooms!", "It's 50% off on mushrooms!"),
    ("Afternoon break! Good time to recharge!", "Afternoon break! Good time to recharge!"),
    ("Hello there! How are you doing today?", "Hello there! How are you doing today?"),
    ("Line one. Line two. Line three.", "Line one. Line two. Line three."),
    ("YAAAAYYYY! I won!", "Yay! I won!"),
    ("Nooooooo! Bowser got me!", "No! Bowzer got me!"),
    ("Wahoooooo! Let's go!", "Let's go!"),
    ("BAAAAAALLS of fire!", "Balls of fire!"),
    ("Sooooo excited right now!", "So excited right now!"),
    ("Heeeeelp! Someone help!", "Help! Someone help!"),
    ("What?! You defeated Bowser?!?!", "What?! You defeated Bowzer?!"),
    ("Amazing... just... amazing...", "Amazing... just... amazing..."),
    ("Wait... really?!", "Wait... really?!"),
    ("Ha ha ha! That's hilarious!", "Ha ha ha! That's hilarious!"),
    ("Can you hear me?", "Can you hear me?"),
    ("The answer is: MUSHROOM!", "The answer is: Mushroom!"),
    ("'quoted speech' is fun!", "'quoted speech' is fun!"),
    ("Welcome to the most amazing bathroom party in the entire Mushroom Kingdom where everyone is having the time of their lives!", "Welcome to the most amazing bathroom party in the entire Mushroom Kingdom where everyone is having the time of their lives!"),
    ("I once traveled through eight worlds, defeated countless Goombas and Koopas, swam through underwater levels, and finally saved Princess Peach!", "I once traveled through eight worlds, defeated countless Goombas and Koopas, swam through underwater levels, and finally saved Princess Peach!"),
    ("The party is in full swing! What a night!", "The party is in full swing! What a night!"),
    ("Evening bathroom visits are the best! The lighting is so dramatic!", "Evening bathroom visits are the best! The lighting is so dramatic!"),
    ("Afternoon already! Time flies when you're having fun!", "Afternoon already! Time flies when you're having fun!"),
    ("I bet Toad would appreciate this tile pattern. Very mushroom-like!", "I bet Toad would appreciate this tile pattern. Very mushroom-like!"),
    ("This bathroom is cleaner than Bowser's castle!", "This bathroom is cleaner than Bowzer's castle!"),
    ("Did you know? In Super Mario 64, I can do over 20 different types of jumps!", "Did you know? In Super Mario 64, I can do over 20 different types of jumps!"),
    ("I wonder what Luigi is doing right now...", "I wonder what Luigi is doing right now..."),
    ("Mama mia, the acoustics in here are perfect for singing!", "Mama mia, the acoustics in here are perfect for singing!"),
]

print("Loading Whisper model (base)...")
model = WhisperModel("base", device="cpu", compute_type="int8")
print("Model loaded.\n")

results = []
for i, (original, expected_clean) in enumerate(test_cases, 1):
    # 1. Generate TTS audio
    url = f'http://localhost:8765/tts?text={urllib.parse.quote(original)}'
    try:
        t0 = time.time()
        resp = urllib.request.urlopen(url, timeout=60)
        wav_data = resp.read()
        gen_time = time.time() - t0
    except Exception as e:
        print(f'{i:2d}. ERROR generating: {e}')
        results.append((i, original, expected_clean, '', 0.0, 'GEN_ERROR'))
        continue

    # 2. Save to temp file
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
        f.write(wav_data)
        tmp_path = f.name

    # 3. Transcribe with Whisper
    try:
        segments, info = model.transcribe(tmp_path, language="en")
        transcript = ' '.join(s.text.strip() for s in segments).strip()
    except Exception as e:
        transcript = f'TRANSCRIBE_ERROR: {e}'
    finally:
        os.unlink(tmp_path)

    # 4. Compare
    clean_expected = clean_for_compare(expected_clean)
    clean_transcript = clean_for_compare(transcript)
    sim = similarity(clean_expected, clean_transcript)

    flag = ''
    if sim < 0.5:
        flag = 'BAD'
    elif sim < 0.75:
        flag = 'WEAK'
    elif sim < 0.9:
        flag = 'OK'
    else:
        flag = 'GOOD'

    results.append((i, original, expected_clean, transcript, sim, flag))
    
    status_icon = {'GOOD': '✓', 'OK': '~', 'WEAK': '⚠', 'BAD': '✗'}.get(flag, '?')
    if flag in ('BAD', 'WEAK'):
        print(f'{i:2d}. {status_icon} [{sim:.0%}] {flag:5s}')
        print(f'    Expected:    "{expected_clean[:60]}"')
        print(f'    Transcribed: "{transcript[:60]}"')
    else:
        print(f'{i:2d}. {status_icon} [{sim:.0%}] {flag:5s} | {expected_clean[:55]}')
    
    time.sleep(0.1)

# Summary
good = sum(1 for r in results if r[5] == 'GOOD')
ok = sum(1 for r in results if r[5] == 'OK')
weak = sum(1 for r in results if r[5] == 'WEAK')
bad = sum(1 for r in results if r[5] in ('BAD', 'GEN_ERROR'))
total = len(results)

print(f'\n{"="*60}')
print(f'RESULTS: {good} GOOD, {ok} OK, {weak} WEAK, {bad} BAD out of {total}')
print(f'{"="*60}')

if weak + bad > 0:
    print('\nProblematic phrases:')
    for r in results:
        if r[5] in ('BAD', 'WEAK', 'GEN_ERROR'):
            print(f'  #{r[0]}: [{r[4]:.0%}] "{r[2][:40]}" → "{r[3][:40]}"')
