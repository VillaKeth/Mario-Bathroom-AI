"""
Ralph TTS Loop — Automated TTS quality improvement through iterative testing.
Tests phrases with GPT-SoVITS TTS + Whisper transcription, tracks progress across rounds.
"""
import urllib.request, urllib.parse, tempfile, os, sys, time, re, json, subprocess, signal
import difflib

SERVER_URL = "http://localhost:8765"
MARIO_AI_DIR = os.path.dirname(os.path.abspath(__file__))
SERVER_DIR = os.path.join(MARIO_AI_DIR, "server")
CACHE_DIR = os.path.join(SERVER_DIR, "data", "tts_cache")
RESULTS_FILE = os.path.join(MARIO_AI_DIR, "ralph_tts_results.json")

# All test phrases: (input_text, expected_clean_text)
# expected_clean is what should come out AFTER the cleaning pipeline
TEST_PHRASES = [
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
    ("Ka-ching ka-ching! Mine cart madness!", "Well, minecart madness!"),
    ("WOO-HA-HEEEEEEEE! I'm Mario!", "Hah hey! I'm Mario!"),
    ("WAHOO! That was amazing!", "That was amazing!"),
    ("BOWSER is going DOWN!", "Bowzer is going Down!"),
    ("I found a MUSHROOM and a STAR!", "I found a Mushroom and a Star!"),
    ("MAMA MIA that's incredible!", "Mama Mia that's incredible!"),
    ("SUCTION TO THE BEAT! Plunge and boogie!", "Suction To The Beat! Plunge and boogie!"),
    ("The POWER of the FIRE FLOWER!", "The Power of the Fire Flower!"),
    ("Hmm, let me think!", "Hmm, let me think!"),
    ("Hmmm, I wonder what Luigi is doing...", "Hmm, I wonder what Luigi is doing"),
    ("Umm, I'm not sure about that.", "Um, I'm not sure about that."),
    ("Uhh, maybe try again?", "Uh, maybe try again?"),
    ("Ahh, that feels nice!", "Ah, that feels nice!"),
    ("Ohh, what a surprise!", "Oh, what a surprise!"),
    ("Brrrr, it's cold in here!", "It's cold in here!"),
    ("Shh, Bowser might hear us!", "Bowzer might hear us!"),
    ("Wahoo! Here we go!", "Here we go!"),
    ("Okie dokie!", "Well, okey dokey!"),
    ("I wonder if Chain Chomps count as pets? They're very bitey!", "I wonder if Chain Chomps count as pets? They're very biting!"),
    ("Pfft, that's nothing!", "Well, that's nothing!"),
    ("Da da daa! Level complete!", "Well, level complete!"),
    ("Boing boing boing! Jump jump jump!", "Jump jump jump!"),
    ("Whoosh! There goes the fireball!", "There goes the fireball!"),
    ("Splish splash, bathroom fun!", "Well, bathroom fun!"),
    ("Tick tock tick tock, hurry up!", "Well, hurry up!"),
    ("Boom! Another Goomba defeated!", "Another Gumba defeated!"),
    ("The mushroom kingdom.. da-da-daa!", "The mushroom kingdom"),
    ("Super Star Power!", "Super Star Power!"),
    ("I give it a 10/10!", "I give it a ten out of ten!"),
    ("The score is 100 & counting!", "The score is one hundred and counting!"),
    ("Email me at mario@mushroom.kingdom", "Email me at mario at mushroom.kingdom"),
    ("It's 50% off on mushrooms!", "It's fifty percent off on mushrooms!"),
    ("Afternoon break! Good time to recharge!", "Afternoon break! Good time to recharge!"),
    ("Hello there! How are you doing today?", "Hello there! How are you doing today?"),
    ("Line one. Line two. Line three.", "Line one, Line two, Line three."),
    ("YAAAAYYYY! I won!", "Yay! I won!"),
    ("Nooooooo! Bowser got me!", "No! Bowzer got me!"),
    ("Wahoooooo! Let's go!", "Well, let's go!"),
    ("BAAAAAALLS of fire!", "Balls of fire!"),
    ("Sooooo excited right now!", "So excited right now!"),
    ("Heeeeelp! Someone help!", "Help! Someone help!"),
    ("What?! You defeated Bowser?!?!", "What?! You defeated Bowzer?!"),
    ("Amazing... just... amazing...", "Amazing, just, amazing"),
    ("Wait... really?!", "Well, wait, really?!"),
    ("Ha ha ha! That's hilarious!", "Ha ha hah! That's hilarious!"),
    ("Can you hear me?", "Can you hear me?"),
    ("The answer is: MUSHROOM!", "The answer is: Mushroom!"),
    ("'quoted speech' is fun!", "Quoted speech is fun!"),
    ("Welcome to the most amazing bathroom party in the entire Mushroom Kingdom where everyone is having the time of their lives!", "Welcome to the most amazing bathroom party in the entire Mushroom Kingdom where everyone is having the time of their lives!"),
    ("I once traveled through eight worlds, defeated countless Goombas and Koopas, swam through underwater levels, and finally saved Princess Peach!", "I once traveled through eight worlds, defeated countless Gumbas and Koopas, swam through underwater levels, and finally saved Princess Peach!"),
    ("The party is in full swing! What a night!", "The party is in full swing! What a night!"),
    ("Evening bathroom visits are the best! The lighting is so dramatic!", "Evening bathroom visits are the best! The lighting is so dramatic!"),
    ("Afternoon already! Time flies when you're having fun!", "Afternoon already! Time flies when you're having fun!"),
    ("I bet Toad would appreciate this tile pattern. Very mushroom-like!", "I bet Toad would appreciate this tile pattern, Very mushroom like!"),
    ("This bathroom is cleaner than Bowser's castle!", "This bathroom is cleaner than Bowzer's castle!"),
    ("Did you know? In Super Mario 64, I can do over 20 different types of jumps!", "Did you know? In Super Mario sixty four, I can do over twenty different types of jumps!"),
    ("I wonder what Luigi is doing right now...", "I wonder what Luigi is doing right now"),
    ("Mama mia, the acoustics in here are perfect for singing!", "Mama mia, the acoustics in here are perfect for singing!"),
]


def clean_for_compare(text):
    """Normalize text for comparison."""
    t = text.lower().strip()
    t = re.sub(r'[^a-z0-9\s]', '', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t


def similarity(a, b):
    """Return similarity ratio between two strings (0-1)."""
    return difflib.SequenceMatcher(None, a, b).ratio()


def test_phrase(model, index, original, expected_clean):
    """Test a single phrase: TTS -> Whisper -> compare. Returns (index, sim, flag, transcript)."""
    url = f'{SERVER_URL}/tts?nocache=1&text={urllib.parse.quote(original)}'
    try:
        resp = urllib.request.urlopen(url, timeout=60)
        wav_data = resp.read()
    except Exception as e:
        return (index, 0.0, 'GEN_ERROR', str(e))

    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
        f.write(wav_data)
        tmp_path = f.name

    try:
        segments, info = model.transcribe(tmp_path, language="en")
        transcript = ' '.join(s.text.strip() for s in segments).strip()
    except Exception as e:
        transcript = f'TRANSCRIBE_ERROR: {e}'
    finally:
        os.unlink(tmp_path)

    clean_exp = clean_for_compare(expected_clean)
    clean_trans = clean_for_compare(transcript)
    sim = similarity(clean_exp, clean_trans)

    if sim >= 0.9:
        flag = 'GOOD'
    elif sim >= 0.75:
        flag = 'OK'
    elif sim >= 0.5:
        flag = 'WEAK'
    else:
        flag = 'BAD'

    return (index, sim, flag, transcript)


def test_raw_phrase(model, raw_text):
    """Test a raw text string directly (bypasses cleaning — text is already clean)."""
    url = f'{SERVER_URL}/tts?nocache=1&text={urllib.parse.quote(raw_text)}'
    try:
        resp = urllib.request.urlopen(url, timeout=60)
        wav_data = resp.read()
    except Exception as e:
        return (0.0, 'GEN_ERROR', str(e))

    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
        f.write(wav_data)
        tmp_path = f.name

    try:
        segments, info = model.transcribe(tmp_path, language="en")
        transcript = ' '.join(s.text.strip() for s in segments).strip()
    except Exception as e:
        transcript = f'TRANSCRIBE_ERROR: {e}'
    finally:
        os.unlink(tmp_path)

    clean_raw = clean_for_compare(raw_text)
    clean_trans = clean_for_compare(transcript)
    sim = similarity(clean_raw, clean_trans)

    if sim >= 0.9:
        flag = 'GOOD'
    elif sim >= 0.75:
        flag = 'OK'
    elif sim >= 0.5:
        flag = 'WEAK'
    else:
        flag = 'BAD'

    return (sim, flag, transcript)


def wait_for_server(timeout=30):
    """Wait for server to be responsive."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            resp = urllib.request.urlopen(f'{SERVER_URL}/health', timeout=5)
            if resp.status == 200:
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


def clear_tts_cache():
    """Clear the TTS cache directory."""
    if os.path.exists(CACHE_DIR):
        count = 0
        for f in os.listdir(CACHE_DIR):
            fp = os.path.join(CACHE_DIR, f)
            if os.path.isfile(fp):
                os.unlink(fp)
                count += 1
        return count
    return 0


def run_full_test(model, phrase_indices=None):
    """Run TTS verification on specified phrases (or all if None)."""
    results = {}
    phrases = TEST_PHRASES if phrase_indices is None else [(TEST_PHRASES[i-1]) for i in phrase_indices]
    indices = phrase_indices if phrase_indices else list(range(1, len(TEST_PHRASES)+1))

    for idx, (orig, exp) in zip(indices, phrases):
        result = test_phrase(model, idx, orig, exp)
        results[idx] = {
            'sim': result[1],
            'flag': result[2],
            'transcript': result[3],
            'expected': exp,
            'original': orig,
        }
        icon = {'GOOD': '+', 'OK': '~', 'WEAK': '!', 'BAD': 'X'}.get(result[2], '?')
        if result[2] in ('BAD', 'WEAK'):
            print(f'  {idx:2d}. {icon} [{result[1]:.0%}] {result[2]:5s} "{exp[:45]}" -> "{result[3][:45]}"')
        else:
            print(f'  {idx:2d}. {icon} [{result[1]:.0%}] {result[2]:5s} | {exp[:55]}')
        time.sleep(0.05)

    return results


def summarize_results(results):
    """Print summary of test results."""
    good = sum(1 for r in results.values() if r['flag'] == 'GOOD')
    ok = sum(1 for r in results.values() if r['flag'] == 'OK')
    weak = sum(1 for r in results.values() if r['flag'] == 'WEAK')
    bad = sum(1 for r in results.values() if r['flag'] in ('BAD', 'GEN_ERROR'))
    total = len(results)
    print(f'\n  Score: {good} GOOD, {ok} OK, {weak} WEAK, {bad} BAD / {total} total')
    print(f'  Quality: {(good+ok)/total*100:.1f}% acceptable (GOOD+OK)')
    return good, ok, weak, bad


def load_history():
    """Load previous test results."""
    if os.path.exists(RESULTS_FILE):
        with open(RESULTS_FILE, 'r') as f:
            return json.load(f)
    return {'rounds': [], 'best_scores': {}}


def save_history(history):
    """Save test results."""
    with open(RESULTS_FILE, 'w') as f:
        json.dump(history, f, indent=2)


# Alternative text transformations to try for problem phrases
ALTERNATIVES = {
    # Bowser alternatives — different phonetic spellings to test
    'bowser': ['Bowser', 'Bowzer', 'Bawzer', 'Bowsur'],
    # Short phrases — try adding context padding
    'short_pad': [
        ('Take a care!', ['Take a care, friend!', 'You take a care now!', 'Mario says, take a care!']),
        ('Mine cart madness!', ['It is mine cart madness!', 'Oh, mine cart madness!', 'Mine cart madness, here we go!']),
        ('Okey dokey!', ['Okey dokey, lets go!', 'Oh, okey dokey!', 'Okey dokey then!']),
        ('Bathroom fun!', ['Bathroom fun for everyone!', 'Oh, bathroom fun!', 'It is bathroom fun time!']),
        ('Hurry up!', ['Hurry up now!', 'Come on, hurry up!', 'Hurry up, lets go!']),
        ('Balls of fire!', ['Great balls of fire!', 'Balls of fire, watch out!', 'Oh, balls of fire!']),
    ],
}


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Ralph TTS Loop — automated quality improvement')
    parser.add_argument('--rounds', type=int, default=10, help='Number of full test rounds')
    parser.add_argument('--problems-only', action='store_true', help='Only test previously problematic phrases')
    parser.add_argument('--try-alternatives', action='store_true', help='Test alternative texts for problem phrases')
    parser.add_argument('--indices', type=str, help='Comma-separated phrase indices to test (e.g., "6,31,33,39")')
    parser.add_argument('--raw', type=str, help='Test a raw text string directly')
    args = parser.parse_args()

    # Load Whisper
    print("Loading Whisper model (base)...")
    from faster_whisper import WhisperModel
    model = WhisperModel("base", device="cpu", compute_type="int8")
    print("Model loaded.\n")

    # Check server
    if not wait_for_server(5):
        print("ERROR: Server not responding at", SERVER_URL)
        sys.exit(1)
    print(f"Server OK at {SERVER_URL}\n")

    history = load_history()

    if args.raw:
        # Test a single raw text string
        print(f"Testing raw text: \"{args.raw}\"")
        sim, flag, transcript = test_raw_phrase(model, args.raw)
        print(f"  Result: [{sim:.0%}] {flag}")
        print(f"  Transcript: \"{transcript}\"")
        sys.exit(0)

    if args.try_alternatives:
        # Test alternative Bowzer spellings
        print("=" * 60)
        print("TESTING ALTERNATIVE BOWSER SPELLINGS")
        print("=" * 60)
        bowzer_phrases = [
            "{name} is mean, but I still win!",
            "{name} might hear us!",
            "No! {name} got me!",
            "What? You defeated {name}?!",
            "This bathroom is cleaner than {name}'s castle!",
        ]
        for alt in ALTERNATIVES['bowser']:
            print(f"\n--- Testing: '{alt}' ---")
            total_sim = 0
            for phrase_template in bowzer_phrases:
                raw = phrase_template.format(name=alt)
                sim, flag, transcript = test_raw_phrase(model, raw)
                total_sim += sim
                icon = {'GOOD': '+', 'OK': '~', 'WEAK': '!', 'BAD': 'X'}.get(flag, '?')
                print(f"  {icon} [{sim:.0%}] \"{raw[:40]}\" -> \"{transcript[:40]}\"")
            avg = total_sim / len(bowzer_phrases)
            print(f"  Average: {avg:.0%}")

        # Test short phrase alternatives
        print("\n" + "=" * 60)
        print("TESTING SHORT PHRASE ALTERNATIVES")
        print("=" * 60)
        for original, alternatives in ALTERNATIVES['short_pad']:
            print(f"\n--- Original: '{original}' ---")
            for alt in alternatives:
                sim, flag, transcript = test_raw_phrase(model, alt)
                icon = {'GOOD': '+', 'OK': '~', 'WEAK': '!', 'BAD': 'X'}.get(flag, '?')
                print(f"  {icon} [{sim:.0%}] \"{alt}\" -> \"{transcript[:50]}\"")

        sys.exit(0)

    # Determine which phrases to test
    if args.indices:
        test_indices = [int(x.strip()) for x in args.indices.split(',')]
    elif args.problems_only:
        # Test phrases that scored < 90% in previous rounds
        if history['rounds']:
            last = history['rounds'][-1]
            test_indices = [int(k) for k, v in last['results'].items() if v['sim'] < 0.9]
        else:
            test_indices = None  # Full test if no history
    else:
        test_indices = None  # Full test

    for round_num in range(1, args.rounds + 1):
        round_id = len(history['rounds']) + 1
        print(f"{'='*60}")
        print(f"ROUND {round_id} (loop {round_num}/{args.rounds})")
        print(f"{'='*60}")

        results = run_full_test(model, test_indices)
        good, ok, weak, bad = summarize_results(results)

        # Save round
        round_data = {
            'round': round_id,
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'tested': len(results),
            'good': good, 'ok': ok, 'weak': weak, 'bad': bad,
            'results': {str(k): v for k, v in results.items()},
        }
        history['rounds'].append(round_data)

        # Update best scores
        for k, v in results.items():
            k_str = str(k)
            if k_str not in history['best_scores'] or v['sim'] > history['best_scores'][k_str]['sim']:
                history['best_scores'][k_str] = {'sim': v['sim'], 'flag': v['flag'], 'round': round_id}

        save_history(history)

        # Show problem phrases for next iteration
        problems = {k: v for k, v in results.items() if v['flag'] in ('BAD', 'WEAK')}
        if problems:
            print(f"\n  Problem phrases ({len(problems)}):")
            for k in sorted(problems.keys()):
                v = problems[k]
                print(f"    #{k}: [{v['sim']:.0%}] \"{v['expected'][:40]}\" -> \"{v['transcript'][:40]}\"")

        # If doing multiple rounds, update test_indices to only problem phrases
        if args.rounds > 1 and round_num < args.rounds:
            test_indices = [k for k, v in results.items() if v['sim'] < 0.9]
            if not test_indices:
                print("\n  All phrases GOOD or OK! Stopping early.")
                break
            print(f"\n  Next round will test {len(test_indices)} phrases with sim < 90%")
            time.sleep(1)

    # Final summary
    print(f"\n{'='*60}")
    print("FINAL SUMMARY")
    print(f"{'='*60}")
    if history['rounds']:
        last = history['rounds'][-1]
        print(f"  Rounds completed: {len(history['rounds'])}")
        print(f"  Latest: {last['good']} GOOD, {last['ok']} OK, {last['weak']} WEAK, {last['bad']} BAD")

    # Show improvement trajectory if multiple rounds
    if len(history['rounds']) > 1:
        print("\n  Progress:")
        for r in history['rounds']:
            pct = (r['good'] + r['ok']) / r['tested'] * 100 if r['tested'] > 0 else 0
            print(f"    Round {r['round']}: {pct:.0f}% acceptable ({r['good']}G+{r['ok']}O / {r['tested']})")
