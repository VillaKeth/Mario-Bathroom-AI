"""Character isolation: a non-Mario character must NEVER invoke Mario's world.

Regression guard for a live-caught leak — running as Rudi, the LLM greeting
hallucinated "party in the bathroom with a Mario AI bot". The whole app is themed
"Mario AI", so the model free-associates a bathroom party bot into Mario. The fix
is a hard negative constraint (`mario_prompt.non_mario_guard()`) injected at the
`llm.generate_response` chokepoint that every guest-facing path shares.
"""
import pytest
from server import mario_prompt


@pytest.fixture(autouse=True)
def _restore_character():
    """Character identity lives in module globals — save/restore around each test
    so we never bleed a non-Mario character into the rest of the suite."""
    saved = (
        mario_prompt._CHARACTER_NAME,
        mario_prompt._CHARACTER_DISPLAY_NAME,
        mario_prompt._CHARACTER_DESCRIPTION,
        mario_prompt._CHARACTER_TAGLINE,
    )
    yield
    (
        mario_prompt._CHARACTER_NAME,
        mario_prompt._CHARACTER_DISPLAY_NAME,
        mario_prompt._CHARACTER_DESCRIPTION,
        mario_prompt._CHARACTER_TAGLINE,
    ) = saved


def test_guard_empty_for_mario():
    mario_prompt.set_character("mario", "Mario")
    assert mario_prompt.non_mario_guard() == ""


def test_guard_empty_for_mario_capitalized():
    # _is_mario() is case-insensitive; the guard must not self-negate Mario.
    mario_prompt.set_character("Mario", "Mario")
    assert mario_prompt.non_mario_guard() == ""


def test_guard_present_and_names_character_for_rudi():
    mario_prompt.set_character("rudi", "Rudi AI", "A witty gremlin", "Truth hurts")
    g = mario_prompt.non_mario_guard()
    assert g, "expected a non-empty guard for a non-Mario character"
    assert "not mario" in g.lower(), "guard must explicitly forbid being Mario"
    assert "Rudi AI" in g, "guard must name the actual character"


def test_guard_forbids_nintendo_cast_for_rudi():
    mario_prompt.set_character("rudi", "Rudi AI")
    g = mario_prompt.non_mario_guard().lower()
    for name in ("luigi", "bowser", "peach", "nintendo"):
        assert name in g, f"guard should forbid '{name}'"
