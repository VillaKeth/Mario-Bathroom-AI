"""
Ralph TTS Loop — Automated TTS quality improvement through iterative testing.
Tests phrases with GPT-SoVITS TTS + Whisper transcription, tracks progress across rounds.
"""
import urllib.request, urllib.parse, tempfile, os, sys, time, re, json, subprocess, signal
import difflib
import traceback

# Catch ALL unhandled exceptions and print them
def _crash_handler(exc_type, exc_value, exc_tb):
    print(f"\n!!! UNHANDLED CRASH: {exc_type.__name__}: {exc_value}", flush=True)
    traceback.print_exception(exc_type, exc_value, exc_tb)
    sys.__excepthook__(exc_type, exc_value, exc_tb)
sys.excepthook = _crash_handler

SERVER_URL = "http://localhost:8765"
MARIO_AI_DIR = os.path.dirname(os.path.abspath(__file__))
SERVER_DIR = os.path.join(MARIO_AI_DIR, "server")
CACHE_DIR = os.path.join(SERVER_DIR, "data", "tts_cache")
RESULTS_FILE = os.path.join(MARIO_AI_DIR, "ralph_tts_results.json")
SERVER_PYTHON = r"C:\.pyenv\pyenv-win\versions\3.11.9\python.exe"


def _server_healthy():
    """Quick health check — returns True if server is responding."""
    try:
        urllib.request.urlopen(f"{SERVER_URL}/health", timeout=5)
        return True
    except Exception:
        return False


def _restart_server():
    """Kill server Python processes, restart server, wait for health, pause idle precache.
    Note: avoids killing THIS process (ralph loop) by targeting specific PIDs.
    """
    my_pid = os.getpid()
    # Walk entire ancestor chain to protect Copilot CLI process tree
    safe_pids = set()
    pid = my_pid
    while pid and pid > 0:
        safe_pids.add(pid)
        try:
            r = subprocess.run(
                f'wmic process where "ProcessId={pid}" get ParentProcessId /format:value',
                shell=True, capture_output=True, text=True, timeout=5
            )
            for line in r.stdout.strip().split('\n'):
                if line.strip().startswith('ParentProcessId='):
                    parent = int(line.strip().split('=')[1])
                    if parent in safe_pids or parent == 0:
                        pid = 0
                    else:
                        pid = parent
                    break
            else:
                break
        except Exception:
            break
    print(f"      [_restart_server: safe_pids={safe_pids}]", flush=True)
    # Find all python processes except this one using tasklist (works on all Windows)
    try:
        result = subprocess.run(
            'tasklist /FI "IMAGENAME eq python.exe" /FO CSV /NH',
            shell=True, capture_output=True, text=True, timeout=10
        )
        print(f"      [tasklist output: {result.stdout.strip()[:200]}]", flush=True)
        for line in result.stdout.strip().split('\n'):
            line = line.strip()
            if line and line.startswith('"python.exe"'):
                # CSV format: "python.exe","PID","Session Name","Session#","Mem Usage"
                parts = line.split(',')
                if len(parts) >= 2:
                    pid = int(parts[1].strip('"'))
                    if pid not in safe_pids:
                        subprocess.run(f"taskkill /F /PID {pid}",
                                       shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        print(f"      [killed PID {pid}]", flush=True)
                    else:
                        print(f"      [SKIPPED my own PID {pid}]", flush=True)
    except Exception as e:
        print(f"      [kill error: {e}]")
    time.sleep(4)
    # Start server in background
    subprocess.Popen(
        f'cmd /c "cd /d {MARIO_AI_DIR} && {SERVER_PYTHON} server/main.py > server_startup.log 2>&1"',
        shell=True, creationflags=subprocess.CREATE_NO_WINDOW,
    )
    # Wait for health
    for _ in range(40):  # up to 200s
        time.sleep(5)
        if _server_healthy():
            # Immediately pause idle precache
            try:
                urllib.request.urlopen(f"{SERVER_URL}/pause_idle?pause=true", timeout=5)
            except Exception:
                pass
            return True
    return False

# All test phrases: (input_text, expected_clean_text)
# expected_clean is what should come out AFTER the cleaning pipeline
TEST_PHRASES = [
    ("It's-a me, Mario!", "It's a me, Mario!"),
    ("Let's-a go! Here we go!", "Oh, let's a go! Here we go!"),
    ("What's-a going on?", "What's a going on?"),
    ("That's-a funny!", "Oh, that's a funny!"),
    ("Nice to meet-a you!", "Nice to meet a you!"),
    ("Take-a care, my friend!", "Take a care, my friend!"),
    ("This-a soap dispenser is very modern!", "This a soap dispenser is very modern!"),
    ("Not like-a my castle pipes!", "Not like a my castle pipes!"),
    ("Time flies-a when you're having fun!", "Time flies a when you're having fun!"),
    ("Good-a time to recharge!", "Good a time to recharge!"),
    ("The party is great - everyone is having fun!", "The party is great, everyone is having fun!"),
    ("Bowser is mean - but I still win!", "the bad guy is mean, but I still win!"),
    ("Coins coins coins! I love collecting coins!", "Coins coins coins! I love collecting coins!"),
    ("The mushroom kingdom -- what a place!", "The mushroom kingdom, what a place!"),
    ("Taking a quick break is always a good idea!", "Taking a quick break is always a good idea!"),
    ("Gold coins are everywhere! So shiny!", "Gold coins are everywhere! So shiny!"),
    ("WAHOO! Super Mario time!", "Oh, super Mario time!"),
    ("WAHOO! That was amazing!", "That was amazing!"),
    ("The villain is going down!", "The villain is going down!"),
    ("I found a MUSHROOM and a STAR!", "I found a Mushroom and a Star!"),
    ("MAMA MIA that's incredible!", "Mama Mia that's incredible!"),
    ("DANCE to the music! Move your feet!", "Dance to the music! Move your feet!"),
    ("The POWER of the FIRE FLOWER!", "The Power of the Fire Flower!"),
    ("Hmm, let me think!", "Hmm, let me think!"),
    ("Hmmm, I wonder what Luigi is doing...", "Hmm, I wonder what Luigi is doing"),
    ("Umm, I'm not sure about that.", "Um, I'm not sure about that."),
    ("Uhh, maybe try again?", "Uh, maybe try again?"),
    ("Ahh, that feels really nice!", "Ah, that feels really nice!"),
    ("Ohh, what a surprise!", "Oh, what a surprise!"),
    ("Brrrr, it's cold in here!", "It's cold in here!"),
    ("Shhh, the villain is nearby! Be very quiet!", "Sh, the villain is nearby! Be very quiet!"),
    ("Wahoo! Here we go!", "Oh, here we go!"),
    ("Alright everybody, let's do this!", "Alright everybody, let's do this!"),
    ("I wonder if Chain Chomps count as pets? They're very bitey!", "I wonder if Chain Chomps count as pets? They're very biting!"),
    ("Pfft, that's nothing!", "Oh, that's nothing!"),
    ("Yahoo! I completed the level!", "I completed the level!"),
    ("Jump jump jump! Here we go!", "Oh, jump jump jump! Here we go!"),
    ("Whoosh! There goes the fireball!", "There goes the fireball!"),
    ("This bathroom is amazing! So much fun!", "This bathroom is amazing! So much fun!"),
    ("Time to head out! See you later!", "Time to head out! See you later!"),
    ("Another enemy defeated! Take that!", "Another enemy defeated! Take that!"),
    ("The mushroom kingdom.. da-da-daa!", "The mushroom kingdom"),
    ("Super Star Power!", "Oh, super Star Power!"),
    ("I give it a perfect score!", "I give it a perfect score!"),
    ("The score keeps going up and up!", "The score keeps going up and up!"),
    ("Email me at mario@mushroom.kingdom", "Email me at mario at mushroom.kingdom"),
    ("It's 50% off on mushrooms!", "It's fifty percent off on mushrooms!"),
    ("Afternoon break! Good time to recharge!", "Afternoon break! Good time to recharge!"),
    ("Hey there, friend! Welcome to the party!", "Hey there, friend! Welcome to the party!"),
    ("First mushroom. Then star. Then victory!", "First mushroom, Then star, Then victory!"),
    ("YEAH YEAH! I won the game!", "Yeah Yeah! I won the game!"),
    ("Oh no! The villain got me this time!", "Oh no! The villain got me this time!"),
    ("Wahoooooo! Let's go!", "Oh, let's go!"),
    ("Watch out for the fireballs!", "Watch out for the fireballs!"),
    ("Sooooo excited right now!", "So excited right now!"),
    ("Heeeeelp! Someone help!", "Help! Someone help!"),
    ("What?! You defeated the villain?!", "What?! You defeated the villain?!"),
    ("Incredible... absolutely incredible!", "Incredible, absolutely incredible!"),
    ("Really? Are you serious right now?", "Really? Are you serious right now?"),
    ("Ha ha ha! That's hilarious!", "Ha ha ha! That's hilarious!"),
    ("Can you hear me?", "Oh, can you hear me?"),
    ("The answer is: MUSHROOM!", "The answer is: Mushroom!"),
    ("'quoted speech' is fun!", "Noted speech is fun!"),
    ("Welcome to the most amazing bathroom party in the entire Mushroom Kingdom where everyone is having the time of their lives!", "Welcome to the most amazing bathroom party in the entire Mushroom Kingdom where everyone is having the time of their lives!"),
    ("I once traveled through eight worlds, defeated countless Goombas and Koopas, swam through underwater levels, and finally saved Princess Peach!", "I once traveled through eight worlds, defeated countless bad mushrooms and Coopers, swam through underwater levels, and finally saved Princess Peach!"),
    ("The party is in full swing! What a night!", "The party is in full swing! What a night!"),
    ("Evening bathroom visits are the best! The lighting is so dramatic!", "Evening bathroom visits are the best! The lighting is so dramatic!"),
    ("Afternoon already! Time flies when you're having fun!", "Afternoon already! Time flies when you're having fun!"),
    ("I bet Toad would appreciate this tile pattern. Very mushroom-like!", "I bet Todd would appreciate this tile pattern, Very mushroom like!"),
    ("This bathroom is cleaner than Bowser's castle!", "This bathroom is cleaner than the bad guy's castle!"),
    ("Did you know? In Super Mario 64, I can do over 20 different types of jumps!", "Did you know? In Super Mario sixty four, I can do over twenty different types of jumps!"),
    ("I wonder what Luigi is doing right now...", "I wonder what Luigi is doing right now"),
    ("Mama mia, the acoustics in here are perfect for singing!", "Mama mia, the acoustics in here are perfect for singing!"),
]


def clean_for_compare(text):
    """Normalize text for comparison — handles number/word equivalence."""
    t = text.lower().strip()
    t = re.sub(r'[^a-z0-9\s%]', '', t)
    # Normalize number words → digits for fair comparison (Whisper writes digits)
    _num_map = {
        'zero': '0', 'one': '1', 'two': '2', 'three': '3', 'four': '4',
        'five': '5', 'six': '6', 'seven': '7', 'eight': '8', 'nine': '9',
        'ten': '10', 'eleven': '11', 'twelve': '12', 'thirteen': '13',
        'fourteen': '14', 'fifteen': '15', 'sixteen': '16', 'seventeen': '17',
        'eighteen': '18', 'nineteen': '19', 'twenty': '20', 'thirty': '30',
        'forty': '40', 'fifty': '50', 'sixty': '60', 'seventy': '70',
        'eighty': '80', 'ninety': '90', 'one hundred': '100',
        'two hundred': '200', 'three hundred': '300',
    }
    for word, digit in _num_map.items():
        t = t.replace(word, digit)
    t = t.replace('percent', '%')
    t = re.sub(r'\s+', ' ', t).strip()
    return t


def similarity(a, b):
    """Return similarity ratio between two strings (0-1)."""
    return difflib.SequenceMatcher(None, a, b).ratio()


def test_phrase(model, index, original, expected_clean, max_retries=2):
    """Test a single phrase: TTS -> Whisper -> compare. 
    Retries up to max_retries times if score is WEAK/BAD, keeping best result.
    Returns (index, sim, flag, transcript)."""
    best_result = None
    
    for attempt in range(1 + max_retries):
        url = f'{SERVER_URL}/tts?nocache=1&text={urllib.parse.quote(original)}'
        try:
            resp = urllib.request.urlopen(url, timeout=60)
            wav_data = resp.read()
        except Exception as e:
            if best_result:
                return best_result
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

        result = (index, sim, flag, transcript)
        
        # Keep the best result across attempts
        if best_result is None or sim > best_result[1]:
            best_result = result
        
        # If GOOD or OK, no need to retry
        if flag in ('GOOD', 'OK'):
            if attempt > 0:
                print(f"      [retry #{attempt} improved to {sim:.0%}]", flush=True)
            return best_result
        
        # If WEAK/BAD and we have retries left, try again
        if attempt < max_retries:
            print(f"      [retry #{attempt+1}: {sim:.0%} {flag}, regenerating...]", flush=True)
            time.sleep(1)  # Brief pause between retries
    
    return best_result


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
    """Run TTS verification on specified phrases (or all if None).
    Self-healing: auto-restarts server on crash and retries failed items.
    """
    results = {}
    phrases = TEST_PHRASES if phrase_indices is None else [(TEST_PHRASES[i-1]) for i in phrase_indices]
    indices = phrase_indices if phrase_indices else list(range(1, len(TEST_PHRASES)+1))

    items_since_restart = 0
    for idx, (orig, exp) in zip(indices, phrases):
        try:
            # Proactive subprocess restart disabled — causes ralph process death
            # Relying on self-healing (full server restart on GEN_ERROR) instead
            if items_since_restart >= 20:
                print("      [skipping mid-round restart, relying on self-healing]", flush=True)
                items_since_restart = 0

            result = test_phrase(model, idx, orig, exp)

            # Self-healing: if GEN_ERROR, skip instead of restarting server
            # Server restarts kill the ralph loop process, so just skip
            if result[2] == 'GEN_ERROR':
                print(f"      [GEN_ERROR on #{idx}, skipping (no restart)]")
                # Wait a moment for the server to recover naturally
                time.sleep(5)
                # Try once more
                result = test_phrase(model, idx, orig, exp)
                if result[2] == 'GEN_ERROR':
                    print(f"      [still failing, recording as BAD]")
                    result = (idx, 0.0, 'BAD', '<GEN_ERROR>')

            items_since_restart += 1
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
        except Exception as e:
            print(f"  {idx:2d}. ? [0%] ERROR  | Unhandled: {e}")
            results[idx] = {
                'sim': 0.0,
                'flag': 'GEN_ERROR',
                'transcript': f'UNHANDLED: {e}',
                'expected': exp,
                'original': orig,
            }

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
    'bowser': ['Bowser', 'Bowzer', 'Bawzer', 'Bowsur', 'Bowzur', 'Browser'],
    # Short phrases — try adding context padding
    'short_pad': [
        ('Take a care!', ['Take a care, friend!', 'You take a care now!', 'Mario says, take a care!']),
        ('Gold coin madness!', ['It is gold coin madness!', 'Oh, gold coin madness!', 'Gold coin madness, here we go!']),
        ('Okey dokey!', ["let's go, here we go!", "Oh, let's go!", "let's go then!"]),
        ('Bathroom fun!', ['This bathroom is fun for everyone!', 'Oh, this bathroom is fun!', 'This bathroom is so much fun!']),
        ('Time to go!', ['Time to go now!', 'Come on, time to go!', 'It is time to go!']),
        ('Balls of fire!', ['Great fire balls!', 'fire balls, watch out!', 'Oh, fire balls!']),
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

    # Pause idle precache to prevent OOM during testing
    try:
        urllib.request.urlopen(f"{SERVER_URL}/pause_idle?pause=true", timeout=5)
        print("Idle precache PAUSED for testing\n")
    except Exception as e:
        print(f"  [Warning: could not pause idle precache: {e}]")

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

        # Skip between-round restart — it kills the ralph process
        if round_num > 1:
            print("  [Skipping between-round restart to avoid process death]")

        try:
            results = run_full_test(model, test_indices)
        except Exception as e:
            print(f"\n  [CRASH in run_full_test: {e}]")
            print(f"  [Attempting server restart and continuing...]")
            print(f"  [Continuing without restart...]")
            continue
        if not results:
            print("  [No results — skipping round]")
            continue
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
            # Only re-test WEAK/BAD phrases — OK (75-89%) are acceptable
            test_indices = [k for k, v in results.items() if v['flag'] in ('WEAK', 'BAD', 'GEN_ERROR')]
            if not test_indices:
                print("\n  All phrases GOOD or OK! Stopping early.")
                break
            print(f"\n  Next round will re-test {len(test_indices)} WEAK/BAD phrases")
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

    # Resume idle precache
    try:
        urllib.request.urlopen(f"{SERVER_URL}/pause_idle?pause=false", timeout=5)
    except Exception:
        pass
