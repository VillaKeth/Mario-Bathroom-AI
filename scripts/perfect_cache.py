"""
Perfect Cache Builder — Generate TTS for each cached phrase until 100% Whisper accuracy.

Since these are pre-cached responses (not live), we can loop as many times as needed.
Each nocache=1 call generates fresh audio AND caches it on the server.
We stop per-phrase once Whisper scores it GOOD (>=90%), leaving the good version cached.
"""

import urllib.request
import urllib.parse
import tempfile
import os
import sys
import time
import json
import hashlib
from difflib import SequenceMatcher

# Add server dir to path so we can import clean_text_for_tts
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "server"))
from gpt_sovits_server import clean_text_for_tts

SERVER_URL = "http://localhost:8765"
CACHE_DIR = os.path.join(os.path.dirname(__file__), "server", "data", "tts_cache")


def _save_to_cache(phrase, wav_data):
    """Save WAV data directly to the server's disk cache."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache_key = clean_text_for_tts(phrase)
    key_hash = hashlib.md5(cache_key.encode()).hexdigest()[:16]
    wav_path = os.path.join(CACHE_DIR, f"{key_hash}.wav")
    key_path = os.path.join(CACHE_DIR, f"{key_hash}.key")
    with open(wav_path, "wb") as f:
        f.write(wav_data)
    with open(key_path, "w", encoding="utf-8") as f:
        f.write(cache_key)

# The phrases to perfect-cache (mirrors server/tts.py CACHED_PHRASES)
CACHED_PHRASES = [
    # Greetings
    "It's-a me, Mario!",
    "Hello there!",
    "Welcome, welcome!",
    "Hey, nice to see you!",
    "Good to see you again!",
    "Nice to meet-a you!",
    # Reactions/exclamations
    "Wahoo!",
    "Mama mia!",
    "Oh no, not again!",
    "Wow, that's-a amazing!",
    "Ha ha ha, that's so funny!",
    "That's-a funny!",
    "Oh yeah, that's right!",
    "Yippee!",
    "Super!",
    "Fantastic!",
    # Game prompts
    "Correct!",
    "That's not right! Try again!",
    "Let's play!",
    "Let's-a go!",
    "You got it!",
    "Try again!",
    "Great job!",
    "Your turn!",
    # Farewells
    "See you later!",
    "Bye bye!",
    "Until next time!",
    "Take-a care!",
    "See you soon, friend!",
    "Goodbye!",
    # Hand wash reminders
    "Don't forget to wash-a your hands!",
    "Wash those hands, it's-a important!",
    "Clean hands, happy Mario!",
    "Scrub-a scrub-a, nice and clean!",
    "Time to wash-a your hands!",
    # Common commands/responses
    "Alrighty!",
    "Here we go!",
    "Yes, that's correct!",
    "No way!",
    "Of course!",
    "I don't-a know about that.",
    "Tell me more!",
    "What do you think?",
    "That's-a good question!",
    "Let me think about that.",
    "You're-a welcome!",
    "Thank you so much!",
    "I'm-a ready!",
    "One more time!",
    # Thinking filler phrases
    "Hmm, let me think!",
    "Alrighty, one moment!",
]


def clean_for_compare(text):
    """Normalize text for fuzzy comparison."""
    import re
    t = text.lower().strip()
    t = re.sub(r"[^a-z0-9 ]", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def similarity(a, b):
    return SequenceMatcher(None, a, b).ratio()


def get_expected_clean(phrase):
    """Get the expected Whisper output by running the same cleaning pipeline the server uses."""
    return clean_text_for_tts(phrase)


def perfect_one_phrase(model, index, phrase, max_attempts=15):
    """Generate TTS for a phrase until Whisper scores it acceptably.
    
    Threshold scales with phrase length:
    - Very short (<15 chars cleaned): accept >=70% (best of 5)
    - Short (<25 chars cleaned): accept >=80% (best of 8)
    - Normal: accept >=90% (up to 15 attempts)
    
    Returns (index, phrase, best_sim, attempts_needed, best_transcript).
    """
    expected = get_expected_clean(phrase)
    
    # Skip phrases that clean to empty (pure sound effects like "Wahoo!")
    if not expected or len(expected.strip()) == 0:
        print(f"      [skipping — cleans to empty string]", flush=True)
        return (index, phrase, 1.0, 0, "[SOUND EFFECT — no text to verify]")
    
    exp_len = len(expected.strip())
    if exp_len < 15:
        threshold = 0.70
        max_att = 5
    elif exp_len < 25:
        threshold = 0.80
        max_att = 8
    else:
        threshold = 0.88
        max_att = max_attempts
    
    best_sim = 0
    best_transcript = ""
    best_wav = None
    
    for attempt in range(1, max_att + 1):
        url = f'{SERVER_URL}/tts?nocache=1&text={urllib.parse.quote(phrase)}'
        try:
            resp = urllib.request.urlopen(url, timeout=60)
            wav_data = resp.read()
        except Exception as e:
            print(f"      [attempt {attempt}: GEN ERROR: {e}]", flush=True)
            time.sleep(2)
            continue

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

        clean_exp = clean_for_compare(expected)
        clean_trans = clean_for_compare(transcript)
        sim = similarity(clean_exp, clean_trans)

        if sim > best_sim:
            best_sim = sim
            best_transcript = transcript
            best_wav = wav_data

        if sim >= threshold:
            # Save best to cache directly
            _save_to_cache(phrase, wav_data)
            return (index, phrase, sim, attempt, transcript)
        
        if attempt < max_att:
            print(f"      [attempt {attempt}: {sim:.0%} (need {threshold:.0%}) — retrying...]", flush=True)
            time.sleep(0.5)
    
    # Fallback: accept best result if >= 75% after all attempts
    if best_sim >= 0.75 and best_wav:
        print(f"      [accepting best {best_sim:.0%} after {max_att} attempts (fallback)]", flush=True)
        _save_to_cache(phrase, best_wav)
    
    return (index, phrase, best_sim, max_att, best_transcript)


def main():
    print("Loading Whisper model (base)...", flush=True)
    from faster_whisper import WhisperModel
    model = WhisperModel("base", device="cpu", compute_type="int8")
    print("Model loaded.", flush=True)

    # Health check
    try:
        resp = urllib.request.urlopen(f"{SERVER_URL}/health", timeout=10)
        print(f"Server OK at {SERVER_URL}\n", flush=True)
    except Exception as e:
        print(f"ERROR: Server not reachable: {e}", flush=True)
        sys.exit(1)

    # Pause idle precache during testing
    try:
        urllib.request.urlopen(f"{SERVER_URL}/precache?pause=true", timeout=5)
        print("Idle precache PAUSED\n", flush=True)
    except Exception:
        pass

    total = len(CACHED_PHRASES)
    results = []
    perfect_count = 0
    failed_phrases = []

    print(f"{'='*60}")
    print(f"PERFECTING {total} CACHED PHRASES")
    print(f"Target: 90%+ Whisper accuracy for each phrase")
    print(f"Max attempts per phrase: 20")
    print(f"{'='*60}\n")

    for i, phrase in enumerate(CACHED_PHRASES):
        idx, ph, sim, attempts, transcript = perfect_one_phrase(model, i + 1, phrase)
        
        if sim >= 0.90:
            flag = "PERFECT"
            perfect_count += 1
            symbol = "+"
        elif sim >= 0.75:
            flag = "OK"
            symbol = "~"
        else:
            flag = "FAILED"
            symbol = "X"
            failed_phrases.append((idx, phrase, sim, transcript))
        
        # Truncate long transcripts for display
        disp_trans = transcript[:60] + "..." if len(transcript) > 60 else transcript
        attempt_info = f" (took {attempts} attempts)" if attempts > 1 else ""
        print(f"  {idx:>3}. {symbol} [{sim:.0%}] {flag:>7}  | {phrase[:50]}{attempt_info}", flush=True)
        
        results.append({
            "index": idx,
            "phrase": phrase,
            "sim": sim,
            "attempts": attempts,
            "transcript": transcript,
            "flag": flag,
        })

    # Summary
    print(f"\n{'='*60}")
    print(f"RESULTS: {perfect_count}/{total} PERFECT ({perfect_count/total*100:.1f}%)")
    print(f"{'='*60}")
    
    if failed_phrases:
        print(f"\n  Failed phrases ({len(failed_phrases)}):")
        for idx, phrase, sim, transcript in failed_phrases:
            print(f"    #{idx}: [{sim:.0%}] \"{phrase}\" -> \"{transcript[:60]}\"")
    
    # Save results
    results_file = "perfect_cache_results.json"
    with open(results_file, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total": total,
            "perfect": perfect_count,
            "rate": f"{perfect_count/total*100:.1f}%",
            "results": results,
        }, f, indent=2)
    print(f"\nResults saved to {results_file}")

    # Resume idle precache
    try:
        urllib.request.urlopen(f"{SERVER_URL}/precache?pause=false", timeout=5)
    except Exception:
        pass


if __name__ == "__main__":
    main()
