"""Mario sprite display with background scene, transitions, typewriter bubbles,
keyboard input, party effects, and emotion-mapped reaction sprites."""

import os
import logging
import math
import random
import string
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
STATE_ENTERING = "entering"
STATE_EXITING = "exiting"
STATE_SLEEPING = "sleeping"
STATE_DANCING = "dancing"

SPRITE_DIR = os.path.join(os.path.dirname(__file__), "assets", "mario")

# AI-generated 3D poses directory (transparent PNGs)
AI_POSES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                            "mario_3d_assets", "ai_poses_transparent")

# Map emotions to AI pose paths (category/filename without .png)
EMOTION_SPRITE_MAP = {
    "happy": "positive/happy",
    "excited": "positive/excited_jump",
    "surprised": "thinking/surprised",
    "confused": "thinking/confused",
    "annoyed": "negative/annoyed",
    "sleepy": "sleep/sleepy",
    "mischievous": "thinking/mischievous",
    "laughing": "positive/laughing",
    "sad": "negative/sad",
    "angry": "negative/angry",
    "nervous": "negative/nervous",
    "scared": "negative/scared",
    "love": "positive/love",
    "proud": "positive/proud",
    "embarrassed": "negative/embarrassed",
    "disgusted": "negative/disgusted",
    "determined": "thinking/determined",
}

# Map states to AI pose paths
STATE_SPRITE_MAP = {
    STATE_IDLE: "neutral/idle",
    STATE_TALKING: ["speech/talking", "speech/talking_excited"],
    STATE_LISTENING: "speech/listening",
    STATE_GREETING: "greeting/wave_high",
    STATE_THINKING: "thinking/thinking",
    STATE_SLEEPING: "sleep/sleeping",
    STATE_DANCING: ["movement/dancing_1", "movement/dancing_2"],
    STATE_ENTERING: "movement/running",
    STATE_EXITING: "greeting/farewell",
}

# Target display size for AI poses (scaled from 1024x1024)
AI_POSE_DISPLAY_SIZE = (250, 250)

# Speech bubble style based on text content
BUBBLE_STYLE_NORMAL = "normal"
BUBBLE_STYLE_SHOUT = "shout"
BUBBLE_STYLE_QUESTION = "question"
BUBBLE_STYLE_WHISPER = "whisper"


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
        self.gravity = 0.0

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.vy += self.gravity
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
            cx, cy = int(self.x), int(self.y)
            points = []
            for i in range(8):
                angle = i * math.pi / 4
                r2 = s * 2 if i % 2 == 0 else s
                points.append((cx + int(r2 * math.cos(angle)), cy + int(r2 * math.sin(angle))))
            if len(points) >= 3:
                pygame.draw.polygon(screen, color, points)
        elif self.shape == "rect":
            pygame.draw.rect(screen, color, (int(self.x), int(self.y), s * 2, s))


class MarioDisplay:
    """Pygame-based Mario display with background, transitions, typewriter,
    keyboard input, and party effects."""

    def __init__(self):
        self._screen = None
        self._clock = None
        self._running = False
        self._font = None
        self._font_small = None
        self._font_title = None
        self._font_input = None

        # Sprite system
        self._sprites = {}
        self._walk_frame = 0
        self._talk_frame = 0
        self._using_ai_poses = False  # set after loading

        # State
        self.state = STATE_IDLE
        self.current_text = ""
        self.subtitle_text = ""
        self.connected = False
        self._frame = 0
        self._text_display_time = 0

        # Typewriter effect
        self._typewriter_text = ""
        self._typewriter_pos = 0
        self._typewriter_speed = 2  # chars per frame

        # Emotion system
        self._emotion = "happy"
        self._particles = []
        self._emotion_timer = 0

        # Transition system
        self._transition_active = False
        self._transition_type = None  # "enter" or "exit"
        self._transition_progress = 0.0
        self._transition_speed = 0.03

        # Keyboard input mode
        self.keyboard_mode = False
        self._keyboard_text = ""
        self._keyboard_cursor_visible = True
        self._keyboard_cursor_timer = 0
        self.on_keyboard_submit = None  # callback(text)

        # Party mode
        self.party_mode = False
        self._party_timer = 0
        self._disco_colors = [
            (255, 0, 0), (0, 255, 0), (0, 100, 255),
            (255, 255, 0), (255, 0, 255), (0, 255, 255),
        ]
        self._disco_index = 0

    def _load_sprites(self):
        """Load Mario sprites — prefer AI-generated transparent poses, fallback to pixel art."""
        # Try loading AI-generated poses first
        if os.path.isdir(AI_POSES_DIR):
            self._load_ai_poses()
            if self._sprites:
                self._using_ai_poses = True
                if DEBUG_DISPLAY:
                    logger.info(f"[DEBUG_DISPLAY] Using AI-generated poses ({len(self._sprites)} loaded)")
                return

        # Fallback to old pixel art sprites
        if DEBUG_DISPLAY:
            logger.info("[DEBUG_DISPLAY] AI poses not found, falling back to pixel art sprites")
        sprite_names = [
            "idle", "talk", "talk2", "walk1", "walk2", "wave",
            "jump", "think", "laugh", "surprise", "sleep", "dance",
        ]
        for name in sprite_names:
            path = os.path.join(SPRITE_DIR, f"mario_{name}.png")
            if os.path.exists(path):
                img = pygame.image.load(path).convert_alpha()
                self._sprites[name] = img

        if not self._sprites:
            logger.error("[DEBUG_DISPLAY] No sprites loaded! Run generate_sprites.py first.")

    def _load_ai_poses(self):
        """Load all AI-generated transparent poses from category subdirectories."""
        categories = [
            "neutral", "greeting", "speech", "positive", "negative",
            "thinking", "sleep", "movement", "action", "powerup",
        ]
        for category in categories:
            cat_dir = os.path.join(AI_POSES_DIR, category)
            if not os.path.isdir(cat_dir):
                continue
            for filename in os.listdir(cat_dir):
                if not filename.endswith(".png"):
                    continue
                pose_name = filename[:-4]  # strip .png
                sprite_key = f"{category}/{pose_name}"
                path = os.path.join(cat_dir, filename)
                try:
                    img = pygame.image.load(path).convert_alpha()
                    # Scale down from 1024x1024 to display size
                    img = pygame.transform.smoothscale(img, AI_POSE_DISPLAY_SIZE)
                    self._sprites[sprite_key] = img
                    if DEBUG_DISPLAY:
                        logger.info(f"[DEBUG_DISPLAY] Loaded AI pose: {sprite_key}")
                except Exception as e:
                    logger.warning(f"[DEBUG_DISPLAY] Failed to load {path}: {e}")

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
        self._font_input = pygame.font.Font(None, 32)
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
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if self.keyboard_mode:
                        self.keyboard_mode = False
                        self._keyboard_text = ""
                    else:
                        self._running = False
                        return False
                elif event.key == pygame.K_TAB:
                    self.keyboard_mode = not self.keyboard_mode
                    self._keyboard_text = ""
                elif event.key == pygame.K_F5:
                    self.party_mode = not self.party_mode
                elif self.keyboard_mode:
                    self._handle_keyboard_input(event)

        self._frame += 1
        self._update_typewriter()
        self._update_transition()
        self._draw()
        self._clock.tick(30)
        return True

    def _handle_keyboard_input(self, event):
        """Handle keyboard input when in keyboard mode."""
        if event.key == pygame.K_RETURN:
            if self._keyboard_text.strip() and self.on_keyboard_submit:
                self.on_keyboard_submit(self._keyboard_text.strip())
                self.subtitle_text = self._keyboard_text.strip()
                self._keyboard_text = ""
        elif event.key == pygame.K_BACKSPACE:
            self._keyboard_text = self._keyboard_text[:-1]
        else:
            if event.unicode and len(self._keyboard_text) < 200:
                self._keyboard_text += event.unicode

    def set_mario_text(self, text: str):
        """Set what Mario is saying (shown in speech bubble with typewriter effect)."""
        self._typewriter_text = text
        self._typewriter_pos = 0
        self.current_text = ""
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

    def start_transition(self, transition_type: str):
        """Start a walk-in or walk-out transition. Type: 'enter' or 'exit'."""
        self._transition_active = True
        self._transition_type = transition_type
        self._transition_progress = 0.0

    def _update_typewriter(self):
        """Advance typewriter text effect."""
        if self._typewriter_text and self._typewriter_pos < len(self._typewriter_text):
            self._typewriter_pos = min(
                self._typewriter_pos + self._typewriter_speed,
                len(self._typewriter_text)
            )
            self.current_text = self._typewriter_text[:int(self._typewriter_pos)]

    def _update_transition(self):
        """Update walk-in/walk-out animation."""
        if not self._transition_active:
            return
        self._transition_progress += self._transition_speed
        if self._transition_progress >= 1.0:
            self._transition_active = False
            self._transition_progress = 1.0
            if self._transition_type == "exit":
                self.state = STATE_IDLE

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
            "laughing": {"color": (255, 255, 100), "count": 10, "shape": "star", "spread": 70},
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

    def _spawn_confetti(self, count=20):
        """Spawn confetti particles for party mode."""
        for _ in range(count):
            color = random.choice(self._disco_colors)
            self._particles.append(Particle(
                x=random.randint(0, WINDOW_WIDTH),
                y=random.randint(-50, 0),
                color=color,
                vx=random.uniform(-1, 1),
                vy=random.uniform(1, 3),
                life=random.randint(60, 150),
                size=random.randint(3, 6),
                shape="rect",
            ))
            self._particles[-1].gravity = 0.05

    def _update_particles(self):
        """Update and remove dead particles."""
        self._particles = [p for p in self._particles if p.update()]

    def _draw_particles(self):
        """Draw all active particles."""
        for p in self._particles:
            p.draw(self._screen)

    def _get_current_sprite(self) -> str:
        """Get the sprite key, considering state and emotion. Works with both AI poses and pixel art."""
        if self._using_ai_poses:
            return self._get_ai_sprite_key()
        else:
            return self._get_legacy_sprite_key()

    def _get_ai_sprite_key(self) -> str:
        """Get sprite key for AI-generated poses (category/name format)."""
        # Transitions use running sprite
        if self._transition_active:
            return "movement/running"

        # State-based selection
        state_mapping = STATE_SPRITE_MAP.get(self.state)

        if self.state == STATE_TALKING:
            sprites = STATE_SPRITE_MAP[STATE_TALKING]
            self._talk_frame += 1
            return sprites[0] if (self._talk_frame // 6) % 2 == 0 else sprites[1]
        elif self.state == STATE_DANCING:
            sprites = STATE_SPRITE_MAP[STATE_DANCING]
            return sprites[0] if (self._frame // 8) % 2 == 0 else sprites[1]
        elif self.state in (STATE_GREETING, STATE_THINKING, STATE_SLEEPING, STATE_ENTERING, STATE_EXITING):
            return STATE_SPRITE_MAP.get(self.state, "neutral/idle")
        elif self.state in (STATE_LISTENING, STATE_IDLE):
            # Use emotion-based sprite
            emo_sprite = EMOTION_SPRITE_MAP.get(self._emotion)
            if emo_sprite and emo_sprite in self._sprites:
                if self.state == STATE_IDLE and self._emotion == "happy":
                    return "neutral/idle"
                return emo_sprite
            return STATE_SPRITE_MAP.get(self.state, "neutral/idle")
        else:
            return "neutral/idle"

    def _get_legacy_sprite_key(self) -> str:
        """Get sprite key for old pixel art sprites (flat name format)."""
        # Transitions use walk sprites
        if self._transition_active:
            return "walk1" if (self._frame // 6) % 2 == 0 else "walk2"

        if self.state == STATE_TALKING:
            self._talk_frame += 1
            return "talk" if (self._talk_frame // 6) % 2 == 0 else "talk2"
        elif self.state == STATE_GREETING:
            return "wave"
        elif self.state == STATE_THINKING:
            return "think"
        elif self.state == STATE_SLEEPING:
            return "sleep"
        elif self.state == STATE_DANCING:
            return "dance"
        elif self.state == STATE_LISTENING:
            # Use emotion sprite if available
            emo_sprite = EMOTION_SPRITE_MAP.get(self._emotion)
            if emo_sprite and emo_sprite in self._sprites:
                return emo_sprite
            return "idle"
        else:
            # Idle — use emotion-based sprite
            emo_sprite = EMOTION_SPRITE_MAP.get(self._emotion)
            if emo_sprite and emo_sprite in self._sprites and self._emotion != "happy":
                return emo_sprite
            return "idle"

    def _detect_bubble_style(self, text: str) -> str:
        """Detect speech bubble style from text content."""
        if text.endswith("?"):
            return BUBBLE_STYLE_QUESTION
        elif text.endswith("!") or text.isupper():
            return BUBBLE_STYLE_SHOUT
        elif text.startswith("(") or text.startswith("*"):
            return BUBBLE_STYLE_WHISPER
        return BUBBLE_STYLE_NORMAL

    # ==========================================
    # BACKGROUND SCENE
    # ==========================================

    def _draw_background(self):
        """Draw the bathroom background scene."""
        # Tile pattern on walls
        tile_color1 = (40, 50, 70)
        tile_color2 = (35, 45, 65)
        grout_color = (30, 35, 50)
        tile_size = 40

        # Draw tiled wall
        for row in range(WINDOW_HEIGHT // tile_size + 1):
            for col in range(WINDOW_WIDTH // tile_size + 1):
                x = col * tile_size
                y = row * tile_size
                color = tile_color1 if (row + col) % 2 == 0 else tile_color2
                pygame.draw.rect(self._screen, color, (x, y, tile_size, tile_size))
                pygame.draw.rect(self._screen, grout_color, (x, y, tile_size, tile_size), 1)

        # Floor (darker tiles at bottom)
        floor_y = WINDOW_HEIGHT - 80
        floor_color1 = (60, 50, 40)
        floor_color2 = (50, 40, 30)
        for col in range(WINDOW_WIDTH // tile_size + 1):
            x = col * tile_size
            color = floor_color1 if col % 2 == 0 else floor_color2
            pygame.draw.rect(self._screen, color, (x, floor_y, tile_size, 80))
            pygame.draw.rect(self._screen, (40, 30, 20), (x, floor_y, tile_size, 80), 1)

        # Mirror on left wall
        mirror_x, mirror_y = 30, 80
        mirror_w, mirror_h = 120, 160
        pygame.draw.rect(self._screen, (80, 80, 90), (mirror_x - 4, mirror_y - 4, mirror_w + 8, mirror_h + 8))
        pygame.draw.rect(self._screen, (140, 160, 180), (mirror_x, mirror_y, mirror_w, mirror_h))
        # Mirror shine
        pygame.draw.line(self._screen, (180, 200, 220), (mirror_x + 10, mirror_y + 10), (mirror_x + 10, mirror_y + 50), 2)
        pygame.draw.line(self._screen, (180, 200, 220), (mirror_x + 15, mirror_y + 10), (mirror_x + 15, mirror_y + 30), 1)

        # Sink below mirror
        sink_y = mirror_y + mirror_h + 10
        pygame.draw.ellipse(self._screen, (180, 180, 190), (mirror_x + 10, sink_y, 100, 30))
        pygame.draw.ellipse(self._screen, (160, 160, 170), (mirror_x + 20, sink_y + 5, 80, 20))
        # Faucet
        pygame.draw.rect(self._screen, (150, 150, 160), (mirror_x + 55, sink_y - 15, 10, 18))
        pygame.draw.rect(self._screen, (170, 170, 180), (mirror_x + 50, sink_y - 15, 20, 5))

        # Toilet on right side
        toilet_x = WINDOW_WIDTH - 140
        toilet_y = floor_y - 80
        # Tank
        pygame.draw.rect(self._screen, (200, 200, 210), (toilet_x + 15, toilet_y - 50, 60, 55), border_radius=5)
        pygame.draw.rect(self._screen, (180, 180, 190), (toilet_x + 15, toilet_y - 50, 60, 55), 2, border_radius=5)
        # Handle
        pygame.draw.rect(self._screen, (170, 170, 180), (toilet_x + 60, toilet_y - 35, 15, 5))
        # Bowl
        pygame.draw.ellipse(self._screen, (210, 210, 220), (toilet_x, toilet_y, 90, 85))
        pygame.draw.ellipse(self._screen, (190, 190, 200), (toilet_x, toilet_y, 90, 85), 2)
        # Seat
        pygame.draw.ellipse(self._screen, (220, 220, 230), (toilet_x + 10, toilet_y + 5, 70, 50))

        # Toilet paper roll
        tp_x = toilet_x - 30
        tp_y = toilet_y + 10
        pygame.draw.rect(self._screen, (80, 80, 90), (tp_x + 5, tp_y - 15, 5, 20))
        pygame.draw.circle(self._screen, (240, 235, 225), (tp_x + 7, tp_y + 8), 12)
        pygame.draw.circle(self._screen, (180, 175, 165), (tp_x + 7, tp_y + 8), 5)

        # Party mode: disco lighting overlay
        if self.party_mode:
            self._party_timer += 1
            if self._party_timer % 15 == 0:
                self._disco_index = (self._disco_index + 1) % len(self._disco_colors)
            if self._party_timer % 10 == 0:
                self._spawn_confetti(5)

            disco_surf = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
            color = self._disco_colors[self._disco_index]
            disco_surf.fill((*color, 25))
            self._screen.blit(disco_surf, (0, 0))

            # Disco ball at top
            ball_x = WINDOW_WIDTH // 2
            ball_y = 25
            pygame.draw.circle(self._screen, (200, 200, 200), (ball_x, ball_y), 15)
            # Light beams
            for i in range(6):
                angle = (self._frame * 3 + i * 60) * math.pi / 180
                end_x = ball_x + int(math.cos(angle) * 200)
                end_y = ball_y + int(math.sin(angle) * 200)
                beam_color = self._disco_colors[(self._disco_index + i) % len(self._disco_colors)]
                pygame.draw.line(self._screen, (*beam_color,), (ball_x, ball_y), (end_x, max(ball_y, end_y)), 1)

    # ==========================================
    # MAIN DRAW
    # ==========================================

    def _draw(self):
        """Draw the full frame."""
        # Background scene instead of flat fill
        self._draw_background()
        self._update_particles()
        self._emotion_timer += 1

        # Draw title
        title = self._font_title.render("It's-a Me, Mario!", True, (255, 215, 0))
        title_bg = pygame.Surface((title.get_width() + 20, title.get_height() + 10), pygame.SRCALPHA)
        title_bg.fill((0, 0, 0, 140))
        self._screen.blit(title_bg, (WINDOW_WIDTH // 2 - title.get_width() // 2 - 10, 15))
        self._screen.blit(title, (WINDOW_WIDTH // 2 - title.get_width() // 2, 20))

        # Draw connection status
        status_color = (0, 255, 0) if self.connected else (255, 0, 0)
        status_text = "\u25cf Connected" if self.connected else "\u25cf Disconnected"
        status_surf = self._font_small.render(status_text, True, status_color)
        self._screen.blit(status_surf, (WINDOW_WIDTH - 150, 15))

        # Draw emotion indicator
        emo_surf = self._font_small.render(f"Mood: {self._emotion}", True, (200, 200, 100))
        emo_bg = pygame.Surface((emo_surf.get_width() + 10, emo_surf.get_height() + 6), pygame.SRCALPHA)
        emo_bg.fill((0, 0, 0, 140))
        self._screen.blit(emo_bg, (5, 12))
        self._screen.blit(emo_surf, (10, 15))

        # Draw Mario sprite
        self._draw_mario()

        # Draw particles on top of Mario
        self._draw_particles()

        # Draw speech bubble with typewriter
        if self.current_text:
            self._draw_speech_bubble(self.current_text)

        # Draw subtitle
        if self.subtitle_text:
            self._draw_subtitle(self.subtitle_text)

        # Draw keyboard input area
        if self.keyboard_mode:
            self._draw_keyboard_input()

        # Draw state / mode indicators
        indicators = [f"[{self.state.upper()}]"]
        if self.keyboard_mode:
            indicators.append("[TAB: Keyboard Mode]")
        if self.party_mode:
            indicators.append("[F5: Party Mode]")
        ind_text = " ".join(indicators)
        ind_surf = self._font_small.render(ind_text, True, (150, 150, 150))
        ind_bg = pygame.Surface((ind_surf.get_width() + 10, ind_surf.get_height() + 6), pygame.SRCALPHA)
        ind_bg.fill((0, 0, 0, 140))
        self._screen.blit(ind_bg, (5, WINDOW_HEIGHT - 33))
        self._screen.blit(ind_surf, (10, WINDOW_HEIGHT - 30))

        # Hint for keyboard/party toggle
        hint = "TAB: type | F5: party | ESC: quit"
        hint_surf = self._font_small.render(hint, True, (100, 100, 120))
        self._screen.blit(hint_surf, (WINDOW_WIDTH - hint_surf.get_width() - 10, WINDOW_HEIGHT - 20))

        pygame.display.flip()

    def _draw_mario(self):
        """Draw the Mario sprite with bounce and transition animations."""
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
        elif self.state == STATE_DANCING:
            bounce = int(math.sin(self._frame * 0.4) * 8)

        if self._emotion == "excited":
            bounce += int(math.sin(self._frame * 0.5) * 6)
        elif self._emotion == "sleepy":
            bounce += int(math.sin(self._frame * 0.02) * 2)
        elif self._emotion == "surprised":
            bounce -= 10

        # Transition offset (walk in from left, walk out to right)
        offset_x = 0
        if self._transition_active:
            if self._transition_type == "enter":
                # Walk in from left edge to center
                start_x = -sprite.get_width()
                end_x = 0
                t = self._ease_in_out(self._transition_progress)
                offset_x = int(start_x + (end_x - start_x) * t)
            elif self._transition_type == "exit":
                # Walk out to right edge
                start_x = 0
                end_x = WINDOW_WIDTH
                t = self._ease_in_out(self._transition_progress)
                offset_x = int(start_x + (end_x - start_x) * t)

        # Center the sprite
        cx = WINDOW_WIDTH // 2 - sprite.get_width() // 2 + offset_x
        cy = WINDOW_HEIGHT // 2 - sprite.get_height() // 2 + 40 + bounce

        self._screen.blit(sprite, (cx, cy))

    @staticmethod
    def _ease_in_out(t: float) -> float:
        """Smooth ease-in-out interpolation."""
        return t * t * (3 - 2 * t)

    def _draw_speech_bubble(self, text: str):
        """Draw Mario's speech bubble with style variations."""
        style = self._detect_bubble_style(self._typewriter_text)
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
        bubble_y = 70

        # Style-dependent colors
        if style == BUBBLE_STYLE_SHOUT:
            bg_color = (255, 255, 200)
            border_color = (200, 0, 0)
            text_color = (180, 0, 0)
            border_width = 3
        elif style == BUBBLE_STYLE_QUESTION:
            bg_color = (220, 230, 255)
            border_color = (0, 0, 180)
            text_color = (0, 0, 120)
            border_width = 2
        elif style == BUBBLE_STYLE_WHISPER:
            bg_color = (230, 230, 230)
            border_color = (150, 150, 150)
            text_color = (100, 100, 100)
            border_width = 1
        else:
            bg_color = (255, 255, 255)
            border_color = (0, 0, 0)
            text_color = (0, 0, 0)
            border_width = 2

        # Spiky bubble for shouts
        if style == BUBBLE_STYLE_SHOUT:
            # Draw spiky/jagged bubble
            points = []
            cx_b = bubble_x + bubble_w // 2
            cy_b = bubble_y + bubble_h // 2
            num_spikes = 16
            for i in range(num_spikes * 2):
                angle = i * math.pi / num_spikes
                if i % 2 == 0:
                    rx = bubble_w // 2 + 15
                    ry = bubble_h // 2 + 15
                else:
                    rx = bubble_w // 2 - 5
                    ry = bubble_h // 2 - 5
                points.append((
                    int(cx_b + rx * math.cos(angle)),
                    int(cy_b + ry * math.sin(angle))
                ))
            pygame.draw.polygon(self._screen, bg_color, points)
            pygame.draw.polygon(self._screen, border_color, points, border_width)
        else:
            # Rounded rectangle bubble
            pygame.draw.rect(self._screen, bg_color,
                             (bubble_x, bubble_y, bubble_w, bubble_h), border_radius=15)
            pygame.draw.rect(self._screen, border_color,
                             (bubble_x, bubble_y, bubble_w, bubble_h), border_width, border_radius=15)

        # Bubble pointer
        pointer_x = WINDOW_WIDTH // 2
        pointer_y = bubble_y + bubble_h
        if style == BUBBLE_STYLE_WHISPER:
            # Dots for whisper
            for i in range(3):
                pygame.draw.circle(self._screen, border_color,
                                   (pointer_x, pointer_y + 8 + i * 10), 4 - i)
        else:
            pygame.draw.polygon(self._screen, bg_color, [
                (pointer_x - 10, pointer_y),
                (pointer_x + 10, pointer_y),
                (pointer_x, pointer_y + 20),
            ])
            pygame.draw.lines(self._screen, border_color, False, [
                (pointer_x - 10, pointer_y),
                (pointer_x, pointer_y + 20),
                (pointer_x + 10, pointer_y),
            ], border_width)

        # Typewriter cursor
        showing_cursor = (self._typewriter_pos < len(self._typewriter_text)
                          and (self._frame // 8) % 2 == 0)

        # Text
        for i, line in enumerate(lines):
            text_surf = self._font.render(line, True, text_color)
            self._screen.blit(text_surf, (bubble_x + 20, bubble_y + 15 + i * line_height))

        # Blinking cursor at end of typewriter text
        if showing_cursor and lines:
            last_line = lines[-1]
            cursor_x = bubble_x + 20 + self._font.size(last_line)[0] + 2
            cursor_y = bubble_y + 15 + (len(lines) - 1) * line_height
            pygame.draw.rect(self._screen, text_color, (cursor_x, cursor_y, 2, 22))

    def _draw_subtitle(self, text: str):
        """Draw subtitle text at the bottom (what the user said)."""
        subtitle_surf = self._font_small.render(f'You: "{text}"', True, (200, 200, 200))
        # Semi-transparent background
        bg = pygame.Surface((subtitle_surf.get_width() + 20, subtitle_surf.get_height() + 10), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 140))
        x = WINDOW_WIDTH // 2 - subtitle_surf.get_width() // 2
        y = WINDOW_HEIGHT - 65
        self._screen.blit(bg, (x - 10, y - 5))
        self._screen.blit(subtitle_surf, (x, y))

    def _draw_keyboard_input(self):
        """Draw the keyboard text input area."""
        input_y = WINDOW_HEIGHT - 110
        input_w = 500
        input_h = 40
        input_x = WINDOW_WIDTH // 2 - input_w // 2

        # Background
        pygame.draw.rect(self._screen, (30, 30, 50),
                         (input_x, input_y, input_w, input_h), border_radius=8)
        pygame.draw.rect(self._screen, (100, 200, 255),
                         (input_x, input_y, input_w, input_h), 2, border_radius=8)

        # Prompt
        prompt = "> "
        display_text = prompt + self._keyboard_text
        text_surf = self._font_input.render(display_text, True, (220, 220, 255))

        # Clip to input box
        clip_rect = pygame.Rect(input_x + 10, input_y + 5, input_w - 20, input_h - 10)
        self._screen.set_clip(clip_rect)
        # Scroll text if too long
        text_w = text_surf.get_width()
        if text_w > input_w - 20:
            self._screen.blit(text_surf, (input_x + 10 - (text_w - input_w + 20), input_y + 8))
        else:
            self._screen.blit(text_surf, (input_x + 10, input_y + 8))
        self._screen.set_clip(None)

        # Blinking cursor
        self._keyboard_cursor_timer += 1
        if (self._keyboard_cursor_timer // 15) % 2 == 0:
            cursor_x = min(input_x + 10 + text_surf.get_width(), input_x + input_w - 15)
            pygame.draw.rect(self._screen, (100, 200, 255),
                             (cursor_x, input_y + 8, 2, input_h - 16))

        # Label
        label = self._font_small.render("Type a message (Enter to send, ESC to close)", True, (120, 120, 160))
        self._screen.blit(label, (input_x, input_y - 18))

    def quit(self):
        """Clean up Pygame."""
        self._running = False
        pygame.quit()
