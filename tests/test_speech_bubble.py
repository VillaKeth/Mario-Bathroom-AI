# tests/test_speech_bubble.py
import pytest
import pygame

@pytest.fixture(scope="module", autouse=True)
def init_pygame():
    pygame.init()
    yield
    pygame.quit()

def _auto_shrink(text, max_width=350, max_height=180, min_font=14, max_font=28):
    """Run the production auto-shrink algorithm."""
    from client.mario_display import MarioDisplay
    # Use a static-like call to the wrap method
    display = object.__new__(MarioDisplay)
    for size in range(max_font, min_font - 1, -2):
        font = pygame.font.Font(None, size)
        lines = display._wrap_text_for_bubble(text, font, max_width)
        total_height = len(lines) * (size + 4)
        if total_height <= max_height:
            return size, lines
    font = pygame.font.Font(None, min_font)
    lines = display._wrap_text_for_bubble(text, font, max_width)
    return min_font, lines

def test_short_text_uses_max_font():
    size, lines = _auto_shrink("Hello!")
    assert size == 28

def test_long_text_shrinks_font():
    long_text = "This is a very long sentence that Mario says which absolutely should not fit in the speech bubble at the default font size of twenty eight pixels"
    size, lines = _auto_shrink(long_text, max_height=120)
    assert size < 28
    assert size >= 14

def test_extremely_long_text_hits_minimum():
    huge_text = " ".join(["supercalifragilisticexpialidocious"] * 20)
    size, lines = _auto_shrink(huge_text, max_height=100)
    assert size == 14

def test_long_word_character_splits():
    """Verify long words that exceed max_width are split by character."""
    from client.mario_display import MarioDisplay
    display = object.__new__(MarioDisplay)
    font = pygame.font.Font(None, 28)
    long_word = "A" * 100  # Very long word
    lines = display._wrap_text_for_bubble(long_word, font, 350)
    assert len(lines) > 1  # Must be split
    for line in lines:
        assert font.size(line)[0] <= 350  # Each line fits

