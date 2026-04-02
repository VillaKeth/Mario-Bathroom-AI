"""Verify TTS output matches intended text by running through Whisper STT."""
import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

print("Loading STT (Whisper)...")
import stt
stt.init_model(model_size="base", device="auto")

print("Loading TTS...")
import tts
tts.init_tts()

test_phrases = [
    "Hey friend, you're in the right room for this.",
    "Bowser? Where? Don't scare Mario like that!",
    "Why did Mario go to the doctor? Because he had too many extra lives!",
    "Cold water in the sink, towels are right there.",
    "If anyone asks, you were in here fixing your hair. Our secret.",
]

print(f"\n{'='*70}")
print("TTS -> STT VERIFICATION")
print(f"{'='*70}\n")

passed = 0
total = len(test_phrases)

for phrase in test_phrases:
    print(f"Original: \"{phrase}\"")
    
    t0 = time.time()
    audio_data = tts.synthesize(phrase)
    tts_time = time.time() - t0
    
    if not audio_data:
        print(f"  ❌ TTS failed to generate audio\n")
        continue
    
    print(f"  TTS: {len(audio_data)} bytes in {tts_time:.1f}s")
    
    t0 = time.time()
    transcript = stt.transcribe(audio_data)
    stt_time = time.time() - t0
    
    print(f"  STT heard: \"{transcript}\"")
    print(f"  STT time: {stt_time:.1f}s")
    
    # Fuzzy comparison: check word overlap
    import re
    orig_words = set(re.findall(r'\w+', phrase.lower()))
    heard_words = set(re.findall(r'\w+', (transcript or "").lower()))
    
    if not heard_words:
        print(f"  ❌ STT returned empty transcript\n")
        continue
    
    overlap = orig_words & heard_words
    precision = len(overlap) / max(len(heard_words), 1)
    recall = len(overlap) / max(len(orig_words), 1)
    
    ok = recall >= 0.5
    status = "✅" if ok else "❌"
    if ok:
        passed += 1
    
    print(f"  {status} Match: {recall:.0%} recall ({len(overlap)}/{len(orig_words)} words)")
    if orig_words - heard_words:
        print(f"  Missing: {orig_words - heard_words}")
    if heard_words - orig_words:
        print(f"  Extra: {heard_words - orig_words}")
    print()

print(f"{'='*70}")
print(f"RESULT: {passed}/{total} phrases verified ({passed/total*100:.0f}%)")
print(f"{'='*70}")
