# tests/test_speech_bubble.py
import pytest

def _measure_text_fits(text, max_width, max_height, min_font=14, max_font=28):
    """Simulate the auto-shrink algorithm. Returns (font_size, lines)."""
    import pygame
    pygame.font.init()
    for size in range(max_font, min_font - 1, -2):
        font = pygame.font.Font(None, size)
        words = text.split()
        lines = []
        current_line = ""
        for word in words:
            test_line = f"{current_line} {word}".strip()
            if font.size(test_line)[0] <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
        if current_line:
            lines.append(current_line)
        total_height = len(lines) * (size + 4)
        if total_height <= max_height:
            return size, lines
    return min_font, lines

def test_short_text_uses_max_font():
    size, lines = _measure_text_fits("Hello!", 350, 200)
    assert size == 28

def test_long_text_shrinks_font():
    long_text = "This is a very long sentence that Mario says which absolutely should not fit in the speech bubble at the default font size of twenty eight pixels"
    size, lines = _measure_text_fits(long_text, 350, 120)
    assert size < 28
    assert size >= 14

def test_extremely_long_text_hits_minimum():
    huge_text = " ".join(["supercalifragilisticexpialidocious"] * 20)
    size, lines = _measure_text_fits(huge_text, 350, 100)
    assert size == 14
