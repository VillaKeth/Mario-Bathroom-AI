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
    
    captions = ClosedCaptions(800, 600)
    
    # Test set_text
    captions.set_text("Hello, World!")
    assert captions._text == "Hello, World!"
    assert captions._dirty is True
    
    # Test clear
    captions.clear()
    assert captions._text == ""
    assert captions._dirty is True

def test_word_wrapping():
    """Test word wrapping produces correct lines."""
    from client.closed_captions import ClosedCaptions
    
    captions = ClosedCaptions(800, 600)
    
    # Very long text that should wrap
    long_text = "This is a very long sentence that should definitely wrap across multiple lines when displayed at the bottom of the screen"
    
    # Call _wrap_text directly
    lines = captions._wrap_text(long_text)
    
    # Should produce multiple lines
    assert len(lines) > 1
    
    # Each line should fit within max width
    max_w = captions._screen_w - 2 * captions._padding
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
    
    # Call _wrap_text directly
    lines = captions._wrap_text(many_words)
    
    # Should not exceed max_lines
    assert len(lines) <= captions._max_lines
