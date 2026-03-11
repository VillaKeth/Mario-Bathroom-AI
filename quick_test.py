import sys; sys.path.insert(0, 'server')
from gpt_sovits_server import clean_text_for_tts
sys.path.insert(0, '.')
from ralph_tts_loop import TEST_PHRASES

mismatches = 0
for i, (raw, expected) in enumerate(TEST_PHRASES):
    actual = clean_text_for_tts(raw)
    if actual != expected:
        mismatches += 1
        print(f"#{i}: MISMATCH")
        print(f"  raw:      {raw!r}")
        print(f"  expected: {expected!r}")
        print(f"  actual:   {actual!r}")
        print()

print(f"\n--- {mismatches} mismatches out of {len(TEST_PHRASES)} phrases ---")
