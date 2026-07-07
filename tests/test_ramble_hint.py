import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))
import mario_prompt


def test_chance_one_always_fires():
    for _ in range(5):
        assert mario_prompt.maybe_ramble_hint(1.0) == mario_prompt.RAMBLE_HINT


def test_chance_zero_never_fires():
    for _ in range(50):
        assert mario_prompt.maybe_ramble_hint(0.0) == ""


def test_invalid_chance_is_safe():
    assert mario_prompt.maybe_ramble_hint(None) == ""
    assert mario_prompt.maybe_ramble_hint("nope") == ""


def test_hint_is_tts_safe_and_character_agnostic():
    assert "..." not in mario_prompt.RAMBLE_HINT
    assert "Mario" not in mario_prompt.RAMBLE_HINT


def test_base_prompt_no_longer_bans_rambling():
    # The old prompt said "NEVER: ... Ramble. ..." — that contradicts ramble mode.
    never_line = [l for l in mario_prompt.MARIO_SYSTEM_PROMPT.splitlines()
                  if l.startswith("NEVER:")][0]
    assert "Ramble" not in never_line
    assert "2-3 sentences max" not in mario_prompt.MARIO_SYSTEM_PROMPT


def test_character_prompt_grants_long_permission():
    prompt = mario_prompt._character_system_prompt()
    assert "screen handles long replies" in prompt
