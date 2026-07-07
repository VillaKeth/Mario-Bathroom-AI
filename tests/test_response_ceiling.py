import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))
from safety_filter import filter_response


def test_long_response_no_longer_cut_at_500():
    # 60 sentences x ~25 chars = ~1500 chars — was amputated at 500 before.
    text = " ".join(f"This is sentence number {i}." for i in range(60))
    out = filter_response(text, cap=True)
    assert len(out) > 1000, f"still amputated: {len(out)} chars"


def test_ceiling_cuts_at_sentence_boundary():
    text = " ".join(f"This is sentence number {i}." for i in range(300))  # ~8000 chars
    out = filter_response(text, cap=True, cap_chars=4000)
    assert len(out) <= 4000
    assert out.endswith((".", "!", "?")), f"bad tail: ...{out[-20:]!r}"


def test_custom_low_ceiling_respected():
    text = " ".join(f"Sentence number {i} here." for i in range(40))
    out = filter_response(text, cap=True, cap_chars=300)
    assert len(out) <= 300


def test_cap_false_never_cuts():
    text = " ".join(f"This is sentence number {i}." for i in range(300))
    out = filter_response(text, cap=False)
    assert len(out) > 6000


def test_short_response_unchanged():
    text = "Wahoo, what a great party!"
    assert filter_response(text, cap=True) == text
