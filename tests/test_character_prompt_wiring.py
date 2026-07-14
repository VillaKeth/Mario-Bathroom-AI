"""The authored per-character system_prompt.md must actually reach the LLM.

Regression: the authored prompt was loaded into mario_prompt.MARIO_SYSTEM_PROMPT
at runtime, but `_BASE_PROMPT_RULES` was derived from it ONCE at import (before any
character loaded) and `_character_system_prompt()` built a generic identity from
config fields — so the rich per-character persona never propagated. Fixed by a
`set_character_prompt()` setter + using the authored prompt as the system-prompt base.
"""
import pytest
from server import mario_prompt


@pytest.fixture(autouse=True)
def _restore():
    saved = (
        mario_prompt._CHARACTER_NAME, mario_prompt._CHARACTER_DISPLAY_NAME,
        mario_prompt._CHARACTER_DESCRIPTION, mario_prompt._CHARACTER_TAGLINE,
        mario_prompt._CHARACTER_PROMPT, mario_prompt.MARIO_SYSTEM_PROMPT,
    )
    yield
    (
        mario_prompt._CHARACTER_NAME, mario_prompt._CHARACTER_DISPLAY_NAME,
        mario_prompt._CHARACTER_DESCRIPTION, mario_prompt._CHARACTER_TAGLINE,
        mario_prompt._CHARACTER_PROMPT, mario_prompt.MARIO_SYSTEM_PROMPT,
    ) = saved


def test_authored_prompt_reaches_system_prompt():
    mario_prompt.set_character("rudi", "Rudi AI")
    mario_prompt.set_character_prompt(
        'You ARE Rudi, a chronically-online gremlin. UNIQUE_PERSONA_MARKER_XYZ. '
        'End every response with JSON: {"emotion": "happy", "energy": 0.5}')
    sp = mario_prompt._character_system_prompt()
    assert "UNIQUE_PERSONA_MARKER_XYZ" in sp, "authored persona must reach the system prompt"


def test_setter_syncs_mario_system_prompt():
    # Group/TADC mode still reads MARIO_SYSTEM_PROMPT, so the setter keeps it in sync.
    mario_prompt.set_character_prompt('AUTHORED_BASE_ABC {"emotion": "x"}')
    assert "AUTHORED_BASE_ABC" in mario_prompt.MARIO_SYSTEM_PROMPT


def test_emotion_json_present_even_if_authored_lacks_it():
    # Emotion/energy JSON is infra the server parses off every reply — guarantee it.
    mario_prompt.set_character("rudi", "Rudi AI")
    mario_prompt.set_character_prompt("You ARE Rudi. No json ending here.")
    sp = mario_prompt._character_system_prompt()
    assert '"emotion"' in sp, "emotion-JSON instruction must always be present"


def test_fallback_generic_identity_when_no_authored_prompt():
    mario_prompt.set_character("gizmo", "Gizmo")
    mario_prompt.set_character_prompt("")  # none loaded
    sp = mario_prompt._character_system_prompt()
    assert "You are Gizmo" in sp, "generic identity is the fallback with no authored prompt"
    assert '"emotion"' in sp
