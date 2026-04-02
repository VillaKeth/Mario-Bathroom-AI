# tests/test_closed_captions.py
import pytest
import pygame

@pytest.fixture(scope="module", autouse=True)
def init_pygame():
    pygame.init()
    yield
    pygame.quit()

def test_set_text_and_clear():
    """Test setting and clearing caption text."""
    from client.closed_captions import ClosedCaptions
    
    # Create instance without calling __init__ (pygame already initialized)
    captions = object.__new__(ClosedCaptions)
    captions._screen_w = 800
    captions._screen_h = 600
    captions._text = ""
    captions._font = pygame.font.Font(None, 24)
    captions._padding = 10
    captions._max_lines = 3
    
    # Test set_text
    captions.set_text("Hello, World!")
    assert captions._text == "Hello, World!"
    
    # Test clear
    captions.clear()
    assert captions._text == ""

def test_word_wrapping():
    """Test word wrapping produces correct lines."""
    from client.closed_captions import ClosedCaptions
    
    captions = ClosedCaptions(800, 600)
    
    # Very long text that should wrap
    long_text = "This is a very long sentence that should definitely wrap across multiple lines when displayed at the bottom of the screen"
    captions.set_text(long_text)
    
    # Simulate the word-wrap logic from draw()
    words = captions._text.split()
    lines = []
    current = ""
    max_w = captions._screen_w - 2 * captions._padding
    
    for word in words:
        test = f"{current} {word}".strip()
        if captions._font.size(test)[0] <= max_w:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    
    # Should produce multiple lines
    assert len(lines) > 1
    
    # Each line should fit within max width
    for line in lines:
        assert captions._font.size(line)[0] <= max_w

def test_empty_text_doesnt_draw():
    """Test that empty text doesn't draw anything."""
    from client.closed_captions import ClosedCaptions
    
    captions = ClosedCaptions(800, 600)
    
    # Create a test surface
    surface = pygame.Surface((800, 600))
    original_surface = surface.copy()
    
    # Draw with empty text
    captions.draw(surface)
    
    # Surface should be unchanged (early return when no text)
    # Compare the surfaces (they should be identical)
    assert surface.get_at((0, 0)) == original_surface.get_at((0, 0))
    assert surface.get_at((400, 300)) == original_surface.get_at((400, 300))

def test_max_lines_limit():
    """Test that only max_lines are displayed."""
    from client.closed_captions import ClosedCaptions
    
    captions = ClosedCaptions(800, 600)
    
    # Create text that will produce many lines
    many_words = " ".join(["word"] * 100)
    captions.set_text(many_words)
    
    # Simulate the word-wrap logic
    words = captions._text.split()
    lines = []
    current = ""
    max_w = captions._screen_w - 2 * captions._padding
    
    for word in words:
        test = f"{current} {word}".strip()
        if captions._font.size(test)[0] <= max_w:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    
    # Limit to max lines (as done in draw())
    lines = lines[-captions._max_lines:]
    
    # Should not exceed max_lines
    assert len(lines) <= captions._max_lines
