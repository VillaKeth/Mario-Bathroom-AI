"""Mario sprite display using Pygame with pixel art sprites, particles, and emotions."""

import os
import logging
import math
import random
import pygame

DEBUG_DISPLAY = True
logger = logging.getLogger(__name__)

WINDOW_WIDTH = 800
WINDOW_HEIGHT = 600
BG_COLOR = (20, 20, 40)
TEXT_COLOR = (255, 255, 255)

# Mario states
STATE_IDLE = "idle"
STATE_TALKING = "talking"
STATE_LISTENING = "listening"
STATE_GREETING = "greeting"
STATE_THINKING = "thinking"

SPRITE_DIR = os.path.join(os.path.dirname(__file__), "assets", "mario")


class Particle:
    """Simple particle for visual effects."""
    def __init__(self, x, y, color, vx=0, vy=-2, life=60, size=4, shape="circle"):
        self.x = x
        self.y = y
        self.color = color
        self.vx = vx
        self.vy = vy
        self.life = life
        self.max_life = life
        self.size = size
        self.shape = shape

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.life -= 1
        return self.life > 0

    def draw(self, screen):
        alpha = self.life / self.max_life
        r, g, b = self.color
        color = (int(r * alpha), int(g * alpha), int(b * alpha))
        s = max(1, int(self.size * alpha))
        if self.shape == "circle":
            pygame.draw.circle(screen, color, (int(self.x), int(self.y)), s)
        elif self.shape == "star":
            points = [
                (self.x, self.y - s * 2),
                (self.x + s, self.y),
                (self.x, self.y + s * 2),
                (self.x - s, self.y),
            ]
            pygame.draw.polygon(screen, color, [(int(px), int(py)) for px, py in points])


class MarioDisplay:
    """Pygame-based Mario sprite display with pixel art sprites and speech bubbles."""

    def __init__(self):
        self._screen = None
        self._clock = None
        self._running = False
        self._font = None
        self._font_small = None
        self._font_title = None

        # Sprite system
        self._sprites = {}
        self._walk_frame = 0
        self._talk_frame = 0

        # State
        self.state = STATE_IDLE
        self.current_text = ""
        self.subtitle_text = ""
        self.connected = False
        self._frame = 0
        self._text_display_time = 0

        # Emotion system
        self._emotion = "happy"
        self._particles = []
        self._emotion_timer = 0

    def _load_sprites(self):
        """Load all Mario pixel art sprite PNGs."""
        sprite_names = ["idle", "talk", "talk2", "walk1", "walk2", "wave", "jump", "think"]
        for name in sprite_names:
            path = os.path.join(SPRITE_DIR, f"mario_{name}.png")
            if os.path.exists(path):
                img = pygame.image.load(path).convert_alpha()
                self._sprites[name] = img
                if DEBUG_DISPLAY:
                    logger.info(f"[DEBUG_DISPLAY] Loaded sprite: {name} ({img.get_width()}x{img.get_height()})")
            else:
                logger.warning(f"[DEBUG_DISPLAY] Sprite not found: {path}")

        if not self._sprites:
            logger.error("[DEBUG_DISPLAY] No sprites loaded! Run generate_sprites.py first.")

    def init(self):
        """Initialize Pygame display."""
        if DEBUG_DISPLAY:
            logger.info("[DEBUG_DISPLAY] MarioDisplay.init: START")

        pygame.init()
        pygame.display.set_caption("Mario AI \U0001f344")
        self._screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        self._clock = pygame.time.Clock()
        self._font = pygame.font.Font(None, 28)
        self._font_small = pygame.font.Font(None, 22)
        self._font_title = pygame.font.Font(None, 48)
        self._running = True

        self._load_sprites()

        if DEBUG_DISPLAY:
            logger.info("[DEBUG_DISPLAY] MarioDisplay.init: END")

    def update(self) -> bool:
        """Update the display. Returns False if window was closed."""
        if not self._running:
            return False

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self._running = False
                return False
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self._running = False
                return False

        self._frame += 1
        self._draw()
        self._clock.tick(30)
        return True

    def set_mario_text(self, text: str):
        """Set what Mario is saying (shown in speech bubble)."""
        self.current_text = text
        self.state = STATE_TALKING
        self._text_display_time = self._frame

    def set_subtitle(self, text: str):
        """Set subtitle text (what the user said)."""
        self.subtitle_text = text

    def set_state(self, state: str):
        """Set Mario's animation state."""
        self.state = state

    def set_emotion(self, emotion: str):
        """Set Mario's emotional state, spawning particles."""
        prev = self._emotion
        self._emotion = emotion
        self._emotion_timer = 0
        if emotion != prev:
            self._spawn_emotion_particles(emotion)

    def _spawn_emotion_particles(self, emotion: str):
        """Spawn particles based on emotion change."""
        cx = WINDOW_WIDTH // 2
        cy = WINDOW_HEIGHT // 2 + 20

        particle_configs = {
            "excited": {"color": (255, 215, 0), "count": 15, "shape": "star", "spread": 80},
            "happy": {"color": (255, 255, 0), "count": 8, "shape": "circle", "spread": 60},
            "surprised": {"color": (255, 100, 255), "count": 12, "shape": "circle", "spread": 100},
            "confused": {"color": (150, 150, 255), "count": 6, "shape": "circle", "spread": 40},
            "annoyed": {"color": (255, 100, 50), "count": 8, "shape": "circle", "spread": 50},
            "sleepy": {"color": (100, 100, 200), "count": 3, "shape": "circle", "spread": 30},
            "mischievous": {"color": (0, 255, 100), "count": 10, "shape": "star", "spread": 70},
        }

        cfg = particle_configs.get(emotion, {"color": (200, 200, 200), "count": 5, "shape": "circle", "spread": 50})
        for _ in range(cfg["count"]):
            self._particles.append(Particle(
                x=cx + random.randint(-cfg["spread"], cfg["spread"]),
                y=cy + random.randint(-40, 20),
                color=cfg["color"],
                vx=random.uniform(-1.5, 1.5),
                vy=random.uniform(-3, -0.5),
                life=random.randint(30, 80),
                size=random.randint(3, 7),
                shape=cfg["shape"],
            ))

    def _update_particles(self):
        """Update and remove dead particles."""
        self._particles = [p for p in self._particles if p.update()]

    def _draw_particles(self):
        """Draw all active particles."""
        for p in self._particles:
            p.draw(self._screen)

    def _get_current_sprite(self) -> str:
        """Get the sprite name for the current state."""
        if self.state == STATE_TALKING:
            # Alternate between talk and talk2 for mouth animation
            self._talk_frame += 1
            return "talk" if (self._talk_frame // 6) % 2 == 0 else "talk2"
        elif self.state == STATE_GREETING:
            return "wave"
        elif self.state == STATE_THINKING:
            return "think"
        elif self.state == STATE_LISTENING:
            return "idle"
        else:
            # Idle — subtle breathing via walk frames occasionally
            return "idle"

    def _draw(self):
        """Draw the full frame."""
        self._screen.fill(BG_COLOR)
        self._update_particles()
        self._emotion_timer += 1

        # Draw title
        title = self._font_title.render("It's-a Me, Mario!", True, (255, 215, 0))
        self._screen.blit(title, (WINDOW_WIDTH // 2 - title.get_width() // 2, 20))

        # Draw connection status
        status_color = (0, 255, 0) if self.connected else (255, 0, 0)
        status_text = "\u25cf Connected" if self.connected else "\u25cf Disconnected"
        status_surf = self._font_small.render(status_text, True, status_color)
        self._screen.blit(status_surf, (WINDOW_WIDTH - 150, 15))

        # Draw emotion indicator
        emo_surf = self._font_small.render(f"Mood: {self._emotion}", True, (200, 200, 100))
        self._screen.blit(emo_surf, (10, 15))

        # Draw Mario sprite
        self._draw_mario()

        # Draw particles on top of Mario
        self._draw_particles()

        # Draw speech bubble
        if self.current_text:
            self._draw_speech_bubble(self.current_text)

        # Draw subtitle
        if self.subtitle_text:
            self._draw_subtitle(self.subtitle_text)

        # Draw state indicator
        state_surf = self._font_small.render(f"[{self.state.upper()}]", True, (150, 150, 150))
        self._screen.blit(state_surf, (10, WINDOW_HEIGHT - 30))

        pygame.display.flip()

    def _draw_mario(self):
        """Draw the Mario sprite with bounce animation."""
        sprite_name = self._get_current_sprite()
        sprite = self._sprites.get(sprite_name)

        if not sprite:
            sprite = self._sprites.get("idle")
        if not sprite:
            return

        # Calculate bounce animation based on state and emotion
        bounce = 0
        if self.state == STATE_TALKING:
            bounce = int(math.sin(self._frame * 0.3) * 6)
        elif self.state == STATE_IDLE:
            bounce = int(math.sin(self._frame * 0.05) * 3)
        elif self.state == STATE_THINKING:
            bounce = int(math.sin(self._frame * 0.15) * 5)

        if self._emotion == "excited":
            bounce += int(math.sin(self._frame * 0.5) * 6)
        elif self._emotion == "sleepy":
            bounce += int(math.sin(self._frame * 0.02) * 2)
        elif self._emotion == "surprised":
            bounce -= 10

        # Center the sprite
        cx = WINDOW_WIDTH // 2 - sprite.get_width() // 2
        cy = WINDOW_HEIGHT // 2 - sprite.get_height() // 2 + 40 + bounce

        self._screen.blit(sprite, (cx, cy))

    def _draw_speech_bubble(self, text: str):
        """Draw Mario's speech bubble."""
        max_width = 350
        words = text.split()
        lines = []
        current_line = ""

        for word in words:
            test = current_line + " " + word if current_line else word
            if self._font.size(test)[0] > max_width:
                if current_line:
                    lines.append(current_line)
                current_line = word
            else:
                current_line = test
        if current_line:
            lines.append(current_line)

        if not lines:
            return

        line_height = 28
        bubble_w = max_width + 40
        bubble_h = len(lines) * line_height + 30
        bubble_x = WINDOW_WIDTH // 2 - bubble_w // 2
        bubble_y = 80

        # Bubble background
        pygame.draw.rect(self._screen, (255, 255, 255), (bubble_x, bubble_y, bubble_w, bubble_h), border_radius=15)
        pygame.draw.rect(self._screen, (0, 0, 0), (bubble_x, bubble_y, bubble_w, bubble_h), 2, border_radius=15)

        # Bubble pointer
        pointer_x = WINDOW_WIDTH // 2
        pointer_y = bubble_y + bubble_h
        pygame.draw.polygon(self._screen, (255, 255, 255), [
            (pointer_x - 10, pointer_y),
            (pointer_x + 10, pointer_y),
            (pointer_x, pointer_y + 20),
        ])
        pygame.draw.lines(self._screen, (0, 0, 0), False, [
            (pointer_x - 10, pointer_y),
            (pointer_x, pointer_y + 20),
            (pointer_x + 10, pointer_y),
        ], 2)

        # Text
        for i, line in enumerate(lines):
            text_surf = self._font.render(line, True, (0, 0, 0))
            self._screen.blit(text_surf, (bubble_x + 20, bubble_y + 15 + i * line_height))

    def _draw_subtitle(self, text: str):
        """Draw subtitle text at the bottom (what the user said)."""
        subtitle_surf = self._font_small.render(f'You: "{text}"', True, (200, 200, 200))
        x = WINDOW_WIDTH // 2 - subtitle_surf.get_width() // 2
        self._screen.blit(subtitle_surf, (x, WINDOW_HEIGHT - 60))

    def quit(self):
        """Clean up Pygame."""
        self._running = False
        pygame.quit()
