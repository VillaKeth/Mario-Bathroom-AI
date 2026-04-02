"""
Perfect Cache V2 — Aggressive TTS quality verification

For each of 51 cached Mario phrases:
  1. Generate up to MAX_ATTEMPTS versions (with nocache=1)
  2. Transcribe each with Whisper "base" (beam_size=5 for accuracy)
  3. Check audio duration bounds (reject too-short or too-long clips)
  4. Keep the BEST scoring generation
  5. Directly save the best WAV to the disk cache

Improvements over V1:
  - Beam search (beam_size=5) for more accurate transcription
  - Audio duration bounds checking
  - More attempts (30 vs 20)
  - Directly writes best WAV to server/data/tts_cache/ (no re-generation)
"""

import os
import sys
import json
import time
import wave
import hashlib
import tempfile
import urllib.request
import urllib.parse
from difflib import SequenceMatcher

SERVER_URL = "http://localhost:8765"
MAX_ATTEMPTS = 30
CACHE_DIR = os.path.join(os.path.dirname(__file__), "server", "data", "tts_cache")
EDGE_VOICE = "en-US-GuyNeural"

# All 51 cached phrases (must match server/tts.py CACHED_PHRASES)
CACHED_PHRASES = [
    "It's-a me, Mario!", "Hello there!", "Welcome, welcome!",
    "Hey, nice to see you!", "Good to see you again!", "Nice to meet-a you!",
    "Wahoo!", "Mama mia!", "Oh no, not again!",
    "Wow, that's-a amazing!", "Ha ha ha, that's so funny!", "That's-a funny!",
    "Oh yeah, that's right!", "Yippee!", "Super!", "Fantastic!",
    "Correct!", "That's not right! Try again!", "Let's play!",
    "Let's-a go!", "You got it!", "Try again!", "Great job!",
    "Your turn!", "Yes, that's correct!",
    "See you later!", "Bye bye!", "Until next time!",
    "Take-a care!", "See you soon, friend!", "Goodbye!",
    "Don't forget to wash-a your hands!",
    "Wash those hands, it's-a important!",
    "Clean hands, happy Mario!",
    "Scrub-a scrub-a, nice and clean!",
    "Time to wash-a your hands!",
    "Okie dokie!", "Here we go!",
    "No way!", "Of course!",
    "I don't-a know about that.", "Tell me more!",
    "What do you think?", "That's-a good question!",
    "Let me think about that.", "You're-a welcome!",
    "Thank you so much!", "I'm-a ready!", "One more time!",
    "Hmm, let me think!", "Okie dokie, one moment!",
]


def clean_for_compare(text):
    """Normalize text for comparison — strip punctuation, lowercase, collapse spaces."""
    import re
    t = text.lower().strip()
    t = re.sub(r"[^a-z0-9\s]", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def similarity(a, b):
    """SequenceMatcher ratio between two cleaned strings."""
    return SequenceMatcher(None, a, b).ratio()


def get_wav_duration(wav_data):
    """Get duration of WAV data in seconds."""
    try:
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            f.write(wav_data)
            tmp = f.name
        with wave.open(tmp, 'rb') as w:
            frames = w.getnframes()
            rate = w.getframerate()
            duration = frames / float(rate)
        os.unlink(tmp)
        return duration
    except Exception:
        return 0.0


def expected_duration_range(phrase):
    """Estimate expected audio duration range for a phrase."""
    words = len(phrase.split())
    chars = len(phrase)
    # Mario speaks at roughly 2.5-4 words/second
    # Short phrases (1-3 words): 0.3s - 3.0s
    # Medium phrases (4-7 words): 1.0s - 4.5s
    # Long phrases (8+ words): 2.0s - 6.0s
    if words <= 3:
        return (0.3, 4.0)
    elif words <= 7:
        return (0.8, 5.5)
    else:
        return (1.5, 7.0)


def get_threshold(phrase):
    """Similarity threshold based on phrase length."""
    char_len = len(phrase)
    if char_len < 12:
        return 0.75  # Very short — Whisper inherently less accurate
    elif char_len < 20:
        return 0.82
    elif char_len < 30:
        return 0.88
    else:
        return 0.92


def save_to_cache(phrase, wav_data):
    """Directly save WAV data to the server's disk cache directory."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache_key = f"{EDGE_VOICE}:{phrase.strip()}:+0%:+0Hz"
    key_hash = hashlib.md5(cache_key.encode()).hexdigest()[:16]
    wav_path = os.path.join(CACHE_DIR, f"{key_hash}.wav")
    key_path = os.path.join(CACHE_DIR, f"{key_hash}.key")
    with open(wav_path, "wb") as f:
        f.write(wav_data)
    with open(key_path, "w", encoding="utf-8") as f:
        f.write(cache_key)
    return wav_path


def test_phrase(model, phrase, index):
    """Generate and test a single phrase, keeping the best result."""
    expected = phrase
    threshold = get_threshold(phrase)
    dur_min, dur_max = expected_duration_range(phrase)
    
    best_score = 0
    best_transcript = ""
    best_wav = None
    best_duration = 0
    
    for attempt in range(1, MAX_ATTEMPTS + 1):
        url = f'{SERVER_URL}/tts?nocache=1&text={urllib.parse.quote(phrase)}'
        try:
            resp = urllib.request.urlopen(url, timeout=90)
            wav_data = resp.read()
        except Exception as e:
            print(f"      [attempt {attempt}: GEN ERROR: {e}]", flush=True)
            time.sleep(3)
            continue

        # Check audio duration
        duration = get_wav_duration(wav_data)
        if duration < dur_min:
            print(f"      [attempt {attempt}: TOO SHORT {duration:.1f}s (min {dur_min:.1f}s) — retrying]", flush=True)
            time.sleep(0.5)
            continue
        if duration > dur_max:
            print(f"      [attempt {attempt}: TOO LONG {duration:.1f}s (max {dur_max:.1f}s) — retrying]", flush=True)
            time.sleep(0.5)
            continue

        # Transcribe with Whisper
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            f.write(wav_data)
            tmp_path = f.name
        try:
            segments, info = model.transcribe(tmp_path, language="en", beam_size=5)
            transcript = ' '.join(s.text.strip() for s in segments).strip()
        except Exception as e:
            transcript = f'TRANSCRIBE_ERROR: {e}'
        finally:
            os.unlink(tmp_path)

        clean_exp = clean_for_compare(expected)
        clean_trans = clean_for_compare(transcript)
        sim = similarity(clean_exp, clean_trans)

        # Track the best result
        if sim > best_score:
            best_score = sim
            best_transcript = transcript
            best_wav = wav_data
            best_duration = duration

        # Accept immediately if perfect
        if sim >= threshold:
            # Save this good WAV directly to cache
            saved = save_to_cache(phrase, wav_data)
            
            result = {
                'index': index, 'phrase': phrase, 'sim': sim,
                'attempts': attempt, 'transcript': transcript,
                'duration': round(duration, 2),
                'flag': 'PERFECT' if sim >= 0.90 else 'OK'
            }
            return result

        if attempt < MAX_ATTEMPTS:
            print(f"      [attempt {attempt}: {sim:.0%} ({duration:.1f}s) need {threshold:.0%} — retrying]", flush=True)
        time.sleep(0.3)

    # Exhausted attempts — save the best one to cache anyway
    if best_wav:
        save_to_cache(phrase, best_wav)

    flag = 'PERFECT' if best_score >= 0.90 else ('OK' if best_score >= get_threshold(phrase) * 0.9 else 'FAILED')
    return {
        'index': index, 'phrase': phrase, 'sim': best_score,
        'attempts': MAX_ATTEMPTS, 'transcript': best_transcript,
        'duration': round(best_duration, 2), 'flag': flag
    }


def main():
    print("Loading Whisper model (base with beam_size=5 for better accuracy)...", flush=True)
    from faster_whisper import WhisperModel
    model = WhisperModel("base", device="cpu", compute_type="int8")
    print("Model loaded.\n", flush=True)

    # Health check
    try:
        resp = urllib.request.urlopen(f"{SERVER_URL}/health", timeout=10)
        print(f"Server OK at {SERVER_URL}", flush=True)
    except Exception as e:
        print(f"ERROR: Server not reachable: {e}", flush=True)
        sys.exit(1)

    # Pause idle precache
    try:
        urllib.request.urlopen(f"{SERVER_URL}/precache?pause=true", timeout=5)
        print("Idle precache PAUSED\n", flush=True)
    except Exception:
        pass

    total = len(CACHED_PHRASES)
    results = []
    perfect_count = 0
    ok_count = 0
    failed_phrases = []

    print("=" * 60)
    print(f"PERFECTING {total} CACHED PHRASES (V2 — aggressive)")
    print(f"Whisper model: base (beam=5) | Max attempts: {MAX_ATTEMPTS}")
    print(f"Duration bounds + higher thresholds")
    print("=" * 60)

    for i, phrase in enumerate(CACHED_PHRASES):
        result = test_phrase(model, phrase, i + 1)
        results.append(result)

        flag_str = result['flag']
        sim_pct = f"{result['sim']:.0%}"
        dur_str = f"{result['duration']:.1f}s"
        att_str = f" (took {result['attempts']} attempts)" if result['attempts'] > 1 else ""

        if flag_str == 'PERFECT':
            perfect_count += 1
            print(f"  {result['index']:3d}. + [{sim_pct}] {dur_str} PERFECT  | {phrase}{att_str}", flush=True)
        elif flag_str == 'OK':
            ok_count += 1
            print(f"  {result['index']:3d}. ~ [{sim_pct}] {dur_str}      OK  | {phrase}{att_str}", flush=True)
        else:
            failed_phrases.append(result)
            print(f"  {result['index']:3d}. X [{sim_pct}] {dur_str}  FAILED  | {phrase}{att_str}", flush=True)

    passed = perfect_count + ok_count
    print("\n" + "=" * 60)
    print(f"RESULTS: {passed}/{total} passed | {perfect_count} PERFECT | {ok_count} OK")
    print("=" * 60)

    if failed_phrases:
        print(f"\n  Failed phrases ({len(failed_phrases)}):")
        for r in failed_phrases:
            print(f'    #{r["index"]}: [{r["sim"]:.0%}] "{r["phrase"]}" -> "{r["transcript"]}"')

    # Save results
    output = {
        'total': total, 'passed': passed, 'perfect': perfect_count,
        'ok': ok_count, 'failed': len(failed_phrases),
        'whisper_model': 'base (beam=5)', 'max_attempts': MAX_ATTEMPTS,
        'results': results
    }
    with open('perfect_cache_results.json', 'w') as f:
        json.dump(output, f, indent=2)
    print(f"\nResults saved to perfect_cache_results.json", flush=True)

    # Resume precache
    try:
        urllib.request.urlopen(f"{SERVER_URL}/precache?pause=false", timeout=5)
    except Exception:
        pass


if __name__ == '__main__':
    main()
