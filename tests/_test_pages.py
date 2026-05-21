"""Test the page-based speech bubble system with a long message."""
import pygame
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'client'))
from mario_display import MarioDisplay

pygame.init()
display = MarioDisplay()
display.init()
display.connected = True

# Set a very long text to test pagination
long_text = (
    "Wahoo! Let me tell you about my greatest adventure! "
    "I traveled through the Mushroom Kingdom, fought Bowser in his castle, "
    "saved Princess Peach, collected all the Power Stars, jumped through paintings "
    "into magical worlds, swam with dolphins in Jolly Roger Bay, climbed the tallest "
    "mountains, defeated King Bob-omb, raced Koopa the Quick, and finally threw "
    "Bowser into the bombs three times! It was absolutely magnificent and I would "
    "do it all over again! Every single star was worth the effort!"
)

display.set_mario_text(long_text)
display.sync_typewriter_to_audio(15.0)  # Simulate 15 second audio

# Run for 500 frames (about 17 seconds at 30fps)
clock = pygame.time.Clock()
for frame in range(500):
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()

    display._frame = frame
    display._update_typewriter()
    display.current_text = display._typewriter_text[:int(display._typewriter_pos)]
    display._draw()
    clock.tick(30)

    # Print page info at key moments
    if frame in (1, 30, 150, 300, 450):
        pages = len(display._text_pages)
        print(f"Frame {frame}: pages={pages}, current_page={display._current_page}, "
              f"pos={int(display._typewriter_pos)}/{len(long_text)}")
        if frame == 1 and pages > 0:
            for i, page in enumerate(display._text_pages):
                print(f"  Page {i}: {len(page)} lines, chars {display._text_page_char_ranges[i]}")

    # Take screenshot at key moments
    if frame in (60, 200, 499):
        pygame.image.save(display._screen, f'_page_test_{frame}.png')

pygame.quit()
print("Done!")
