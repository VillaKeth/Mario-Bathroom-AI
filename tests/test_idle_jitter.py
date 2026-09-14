"""Standing still should look calm, not nervous.

The "excitement shake" applies per-frame RANDOM offsets — position on both axes
plus rotation — rather than a smooth curve:

    offset_x += random.randint(-3, 3)
    offset_y += random.randint(-3, 3)
    rotation  = random.uniform(-5, 5)

It was gated on `self._emotion == "excited"` alone, with no check on what the
character is actually doing. Emotion persists after a reply ends, so an excited
answer left the character vibrating indefinitely while standing idle.

Shake belongs to active moments (talking, dancing, arriving). Idle already has its
own smooth breathing bob and sway, which is what standing still should look like.
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (ROOT, os.path.join(ROOT, "client")):
    if p not in sys.path:
        sys.path.insert(0, p)


@pytest.fixture(scope="module")
def md():
    import client.mario_display as md
    return md


def test_excited_and_idle_does_not_shake(md):
    """THE BUG: a leftover excited emotion vibrated the character while standing."""
    assert md.should_shake_excited("excited", md.STATE_IDLE, False) is False


def test_excited_while_talking_still_shakes(md):
    """The effect is wanted where it was meant to apply."""
    assert md.should_shake_excited("excited", md.STATE_TALKING, False) is True


def test_excited_while_dancing_still_shakes(md):
    assert md.should_shake_excited("excited", md.STATE_DANCING, False) is True


def test_calm_emotion_never_shakes(md):
    assert md.should_shake_excited("neutral", md.STATE_TALKING, False) is False


def test_sleeping_never_shakes_even_if_excited(md):
    assert md.should_shake_excited("excited", md.STATE_SLEEPING, False) is False


def test_listening_never_shakes(md):
    """Listening is a standing-still pose — same reason as idle."""
    assert md.should_shake_excited("excited", md.STATE_LISTENING, False) is False


def test_no_shake_during_a_sprite_transition(md):
    """Preserves the existing `not self._transition_active` guard."""
    assert md.should_shake_excited("excited", md.STATE_TALKING, True) is False
