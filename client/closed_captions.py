# client/closed_captions.py
"""Always-on subtitle bar at bottom of screen for Mario's speech."""
import pygame

DEBUG_CAPTIONS = False

class ClosedCaptions:
    def __init__(self, screen_width, screen_height):
        self._screen_w = screen_width
        self._screen_h = screen_height
        self._text = ""
        self._font = pygame.font.Font(None, 24)
        self._bg_color = (0, 0, 0, 180)  # semi-transparent black
        self._text_color = (255, 255, 255)
        self._padding = 10
        self._max_lines = 3
        if DEBUG_CAPTIONS:
            print("[DEBUG_CAPTIONS] ClosedCaptions: initialized")
    
    def set_text(self, text):
        if DEBUG_CAPTIONS:
            print(f"[DEBUG_CAPTIONS] set_text: {text[:50]}...")
        self._text = text
    
    def clear(self):
        self._text = ""
    
    def draw(self, surface):
        if not self._text:
            return
        
        # Word-wrap text
        words = self._text.split()
        lines = []
        current = ""
        max_w = self._screen_w - 2 * self._padding
        for word in words:
            test = f"{current} {word}".strip()
            if self._font.size(test)[0] <= max_w:
                current = test
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        
        # Limit to max lines
        lines = lines[-self._max_lines:]
        
        # Draw background
        line_h = self._font.get_linesize()
        total_h = len(lines) * line_h + 2 * self._padding
        bg_rect = pygame.Rect(0, self._screen_h - total_h, self._screen_w, total_h)
        bg_surface = pygame.Surface((bg_rect.w, bg_rect.h), pygame.SRCALPHA)
        bg_surface.fill(self._bg_color)
        surface.blit(bg_surface, bg_rect)
        
        # Draw text
        y = self._screen_h - total_h + self._padding
        for line in lines:
            text_surf = self._font.render(line, True, self._text_color)
            x = (self._screen_w - text_surf.get_width()) // 2
            surface.blit(text_surf, (x, y))
            y += line_h
