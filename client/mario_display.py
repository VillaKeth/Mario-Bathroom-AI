"""Mario sprite display with background scene, transitions, typewriter bubbles,
keyboard input, party effects, and emotion-mapped reaction sprites."""

import os
import logging
import math
import random
import string
import time
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
    "loving": "positive/love",
    "proud": "positive/proud",
    "embarrassed": "negative/embarrassed",
    "disgusted": "negative/disgusted",
    "determined": "thinking/determined",
    "bored": "sleep/yawning",
    "worried": "negative/nervous",
    "curious": "thinking/curious",
    "thinking": "thinking/thinking",
    "shocked": "thinking/shocked",
    "idea": "thinking/idea",
    "frustrated": "negative/annoyed",
    "neutral": "neutral/idle",
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
        self._initialized = False
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
        self._subtitle_set_frame = 0
        self.connected = False
        self._reconnect_info = None
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

        # Pose hint (server-driven sprite override)
        self._pose_hint = None
        self._pose_hint_timer = 0

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
        self.on_volume_change = None   # callback(delta: float)

        # Party mode
        self.party_mode = False
        self._party_timer = 0
        self._disco_colors = [
            (255, 0, 0), (0, 255, 0), (0, 100, 255),
            (255, 255, 0), (255, 0, 255), (0, 255, 255),
        ]
        self._disco_index = 0

        # Thinking animation (shown while waiting for LLM response)
        self._thinking = False
        self._thinking_dots = 0

        # Response timing display
        self._last_response_time = 0
        self._visitor_count = 0
        self._speaking = False

        # Fullscreen toggle
        self._fullscreen = False

        # --- Enhanced animation system (time-based, frame-independent) ---
        # Sprite crossfade
        self._crossfade_start = 0.0
        self._crossfade_from_surface = None
        self._crossfade_duration = 0.3  # 300ms crossfade
        self._last_sprite_key = None

        # Talking word-bounce
        self._talk_bounce_start = 0.0
        self._talk_last_char_count = 0

        # Entrance/Exit time-based
        self._enter_exit_start = 0.0

        # Emotion flash + edge glow
        self._emotion_flash_start = 0.0
        self._emotion_flash_color = (255, 255, 255)
        self._emotion_flash_type = ""
        self._edge_glow_start = 0.0
        self._edge_glow_color = (255, 255, 255)

        # Volume overlay
        self._volume_level = 1.0
        self._volume_show_frame = -999  # frame when volume was last shown
        self._volume_display_duration = 60  # ~2 seconds at 30fps

        # Leaderboard overlay
        self._leaderboard_visible = False
        self._leaderboard_show_frame = 0  # frame when leaderboard was shown
        self._leaderboard_auto_hide_frames = 450  # ~15 seconds at 30fps
        self._leaderboard_data = {}
        self._leaderboard_ticker_index = 0
        self._leaderboard_ticker_frame = 0
        self._leaderboard_ticker_interval = 150  # ~5 seconds at 30fps

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
        self._initialized = True
        pygame.display.set_caption("Mario AI \U0001f344")
        self._screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        self._clock = pygame.time.Clock()
        self._font = pygame.font.Font(None, 28)
        self._font_small = pygame.font.Font(None, 22)
        self._font_title = pygame.font.Font(None, 48)
        self._font_input = pygame.font.Font(None, 32)
        self._running = True

        self._load_sprites()
        self._bg_surface = None  # cached static background

        if DEBUG_DISPLAY:
            logger.info("[DEBUG_DISPLAY] MarioDisplay.init: END")

    def update(self) -> bool:
        """Update the display. Returns False if window was closed."""
        if not self._running:
            return False

        try:
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
                    elif event.key == pygame.K_F6:
                        self._leaderboard_visible = not self._leaderboard_visible
                        if self._leaderboard_visible:
                            self._leaderboard_show_frame = self._frame
                    elif event.key == pygame.K_F11:
                        self._fullscreen = not self._fullscreen
                        if self._fullscreen:
                            self._screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
                        else:
                            self._screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
                    elif not self.keyboard_mode and event.key in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
                        if self.on_volume_change:
                            self.on_volume_change(0.1)
                    elif not self.keyboard_mode and event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                        if self.on_volume_change:
                            self.on_volume_change(-0.1)
                    elif self.keyboard_mode:
                        self._handle_keyboard_input(event)

            self._frame += 1
            self._update_typewriter()
            self._update_transition()
            self._draw()
            self._clock.tick(30)
            return True
        except pygame.error as e:
            logger.error(f"[DEBUG_DISPLAY] Pygame error in update(): {e}")
            self._running = False
            return False

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
        self._talk_last_char_count = 0

    def set_subtitle(self, text: str):
        """Set subtitle text (what the user said). Auto-clears after 5 seconds."""
        self.subtitle_text = text
        self._subtitle_set_frame = self._frame

    def set_state(self, state: str):
        """Set Mario's animation state."""
        self.state = state

    def set_emotion(self, emotion: str):
        """Set Mario's emotional state, spawning particles and triggering flash."""
        if emotion and emotion not in EMOTION_SPRITE_MAP:
            if DEBUG_DISPLAY:
                logger.info(f"[DEBUG_DISPLAY] set_emotion: unknown emotion '{emotion}', using 'happy'")
            emotion = "happy"
        prev = self._emotion
        self._emotion = emotion
        self._emotion_timer = 0
        if emotion != prev:
            self._particles = []  # Clear old particles on emotion change
            self._spawn_emotion_particles(emotion)
            self._trigger_emotion_flash(emotion)

    def set_pose_hint(self, pose_hint: str):
        """Set an explicit pose hint from the server (highest priority for sprite selection)."""
        if pose_hint and pose_hint in self._sprites:
            self._pose_hint = pose_hint
            self._pose_hint_timer = 0
            if DEBUG_DISPLAY:
                logger.info(f"[DEBUG_DISPLAY] set_pose_hint: {pose_hint}")
        elif pose_hint:
            if DEBUG_DISPLAY:
                logger.info(f"[DEBUG_DISPLAY] set_pose_hint: {pose_hint} not found in loaded sprites")

    def set_thinking(self, thinking: bool):
        """Show/hide thinking animation (while waiting for server response)."""
        self._thinking = thinking
        self._thinking_dots = 0

    def show_volume(self, level: float):
        """Show a brief volume indicator overlay (~2 seconds)."""
        self._volume_level = level
        self._volume_show_frame = self._frame
        if DEBUG_DISPLAY:
            logger.info(f"[DEBUG_DISPLAY] show_volume: {level:.1f} ({int(level * 100)}%)")

    def start_transition(self, transition_type: str):
        """Start a walk-in or walk-out transition. Type: 'enter' or 'exit'."""
        self._transition_active = True
        self._transition_type = transition_type
        self._transition_progress = 0.0
        self._enter_exit_start = time.time()
        if transition_type == "enter":
            self.state = STATE_ENTERING
        elif transition_type == "exit":
            self.state = STATE_EXITING

    def _update_typewriter(self):
        """Advance typewriter text effect."""
        if self._typewriter_text and self._typewriter_pos < len(self._typewriter_text):
            self._typewriter_pos = min(
                self._typewriter_pos + self._typewriter_speed,
                len(self._typewriter_text)
            )
            self.current_text = self._typewriter_text[:int(self._typewriter_pos)]

    def _update_transition(self):
        """Update walk-in/walk-out animation progress (time-based)."""
        if not self._transition_active:
            return
        now = time.time()
        elapsed = now - self._enter_exit_start
        if self._transition_type == "enter":
            self._transition_progress = min(elapsed / 1.5, 1.0)
        elif self._transition_type == "exit":
            self._transition_progress = min(elapsed / 1.5, 1.0)

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
            "loving": {"color": (255, 100, 150), "count": 12, "shape": "star", "spread": 75},
            "love": {"color": (255, 80, 130), "count": 12, "shape": "star", "spread": 75},
            "proud": {"color": (255, 200, 0), "count": 10, "shape": "star", "spread": 65},
            "frustrated": {"color": (255, 60, 30), "count": 10, "shape": "circle", "spread": 55},
            "embarrassed": {"color": (255, 150, 180), "count": 6, "shape": "circle", "spread": 45},
            "worried": {"color": (180, 180, 255), "count": 5, "shape": "circle", "spread": 35},
            "bored": {"color": (150, 150, 150), "count": 4, "shape": "circle", "spread": 30},
            "determined": {"color": (255, 165, 0), "count": 8, "shape": "star", "spread": 60},
            "sad": {"color": (100, 150, 255), "count": 6, "shape": "circle", "spread": 45},
            "angry": {"color": (255, 30, 30), "count": 12, "shape": "circle", "spread": 70},
            "nervous": {"color": (200, 200, 255), "count": 5, "shape": "circle", "spread": 40},
            "scared": {"color": (180, 180, 255), "count": 8, "shape": "circle", "spread": 60},
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

        if len(self._particles) > 200:
            self._particles = self._particles[-200:]

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
        if len(self._particles) > 200:
            self._particles = self._particles[-200:]

    def spawn_keyword_particles(self, effect_type: str):
        """Spawn themed particles based on keyword detection from server."""
        cx = WINDOW_WIDTH // 2
        cy = WINDOW_HEIGHT // 2

        effects = {
            "fire": {"color": (255, 100, 0), "count": 15, "shape": "circle", "vy": (-4, -1), "spread": 60},
            "stars": {"color": (255, 215, 0), "count": 12, "shape": "star", "vy": (-3, -0.5), "spread": 80},
            "hearts": {"color": (255, 80, 130), "count": 10, "shape": "star", "vy": (-2, -0.5), "spread": 70},
            "confetti": {"color": None, "count": 20, "shape": "rect", "vy": (1, 3), "spread": 150},
            "rain": {"color": (100, 150, 255), "count": 15, "shape": "circle", "vy": (2, 4), "spread": 120},
            "sparkle": {"color": (255, 255, 200), "count": 8, "shape": "star", "vy": (-2, 0), "spread": 50},
            "mushroom": {"color": (255, 50, 50), "count": 8, "shape": "circle", "vy": (-3, -1), "spread": 40},
            "coins": {"color": (255, 215, 0), "count": 10, "shape": "circle", "vy": (-3, -1), "spread": 60},
        }

        cfg = effects.get(effect_type, effects["sparkle"])
        for _ in range(cfg["count"]):
            color = cfg["color"] or random.choice(self._disco_colors)
            vy_min, vy_max = cfg["vy"]
            p = Particle(
                x=cx + random.randint(-cfg["spread"], cfg["spread"]),
                y=cy + random.randint(-30, 30) if vy_min < 0 else random.randint(-50, 0),
                color=color,
                vx=random.uniform(-1.5, 1.5),
                vy=random.uniform(vy_min, vy_max),
                life=random.randint(40, 100),
                size=random.randint(3, 7),
                shape=cfg["shape"],
            )
            if effect_type in ("confetti", "rain"):
                p.gravity = 0.05
            self._particles.append(p)

        if len(self._particles) > 200:
            self._particles = self._particles[-200:]

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
        """Get sprite key for AI-generated poses (category/name format).

        Priority: pose_hint (server) > state transitions > talking/dancing > emotion > idle
        """
        # Pose hint from server is highest priority (expires after ~120 frames / ~2s)
        if self._pose_hint and self._pose_hint_timer < 120:
            self._pose_hint_timer += 1
            if self._pose_hint in self._sprites:
                return self._pose_hint

        # Clear expired pose hint
        if self._pose_hint_timer >= 120:
            self._pose_hint = None

        # Transitions use appropriate poses (walk/run for enter, wave for exit)
        if self._transition_active:
            if self._transition_type == "enter":
                cycle = int(time.time() * 5) % 2
                if cycle == 0:
                    return "movement/running"
                walk_key = "movement/walking"
                return walk_key if walk_key in self._sprites else "movement/running"
            elif self._transition_type == "exit":
                elapsed = time.time() - self._enter_exit_start
                if elapsed < 0.5:
                    return "greeting/wave_high"
                return "greeting/farewell"

        # State-based selection
        if self.state == STATE_TALKING:
            sprites = STATE_SPRITE_MAP[STATE_TALKING]
            cycle = int(time.time() / 0.3) % len(sprites)
            return sprites[cycle]
        elif self.state == STATE_DANCING:
            sprites = STATE_SPRITE_MAP[STATE_DANCING]
            return sprites[0] if (self._frame // 8) % 2 == 0 else sprites[1]
        elif self.state in (STATE_GREETING, STATE_THINKING, STATE_SLEEPING, STATE_ENTERING, STATE_EXITING):
            return STATE_SPRITE_MAP.get(self.state, "neutral/idle")
        elif self.state in (STATE_LISTENING, STATE_IDLE):
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
        """Draw the bathroom background scene (cached for performance)."""
        if self._bg_surface is None:
            self._bg_surface = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT))
            tile_color1 = (40, 50, 70)
            tile_color2 = (35, 45, 65)
            grout_color = (30, 35, 50)
            tile_size = 40

            for row in range(WINDOW_HEIGHT // tile_size + 1):
                for col in range(WINDOW_WIDTH // tile_size + 1):
                    x = col * tile_size
                    y = row * tile_size
                    color = tile_color1 if (row + col) % 2 == 0 else tile_color2
                    pygame.draw.rect(self._bg_surface, color, (x, y, tile_size, tile_size))
                    pygame.draw.rect(self._bg_surface, grout_color, (x, y, tile_size, tile_size), 1)

            floor_y = WINDOW_HEIGHT - 80
            floor_color1 = (60, 50, 40)
            floor_color2 = (50, 40, 30)
            for col in range(WINDOW_WIDTH // tile_size + 1):
                x = col * tile_size
                color = floor_color1 if col % 2 == 0 else floor_color2
                pygame.draw.rect(self._bg_surface, color, (x, floor_y, tile_size, 80))
                pygame.draw.rect(self._bg_surface, (40, 30, 20), (x, floor_y, tile_size, 80), 1)

            mirror_x, mirror_y = 30, 80
            mirror_w, mirror_h = 120, 160
            pygame.draw.rect(self._bg_surface, (80, 80, 90), (mirror_x - 4, mirror_y - 4, mirror_w + 8, mirror_h + 8))
            pygame.draw.rect(self._bg_surface, (140, 160, 180), (mirror_x, mirror_y, mirror_w, mirror_h))
            pygame.draw.line(self._bg_surface, (180, 200, 220), (mirror_x + 10, mirror_y + 10), (mirror_x + 10, mirror_y + 50), 2)
            pygame.draw.line(self._bg_surface, (180, 200, 220), (mirror_x + 15, mirror_y + 10), (mirror_x + 15, mirror_y + 30), 1)

            sink_y = mirror_y + mirror_h + 10
            pygame.draw.ellipse(self._bg_surface, (180, 180, 190), (mirror_x + 10, sink_y, 100, 30))
            pygame.draw.ellipse(self._bg_surface, (160, 160, 170), (mirror_x + 20, sink_y + 5, 80, 20))
            pygame.draw.rect(self._bg_surface, (150, 150, 160), (mirror_x + 55, sink_y - 15, 10, 18))
            pygame.draw.rect(self._bg_surface, (170, 170, 180), (mirror_x + 50, sink_y - 15, 20, 5))

            toilet_x = WINDOW_WIDTH - 140
            toilet_y = floor_y - 80
            pygame.draw.rect(self._bg_surface, (200, 200, 210), (toilet_x + 15, toilet_y - 50, 60, 55), border_radius=5)
            pygame.draw.rect(self._bg_surface, (180, 180, 190), (toilet_x + 15, toilet_y - 50, 60, 55), 2, border_radius=5)
            pygame.draw.rect(self._bg_surface, (170, 170, 180), (toilet_x + 60, toilet_y - 35, 15, 5))
            pygame.draw.ellipse(self._bg_surface, (210, 210, 220), (toilet_x, toilet_y, 90, 85))
            pygame.draw.ellipse(self._bg_surface, (190, 190, 200), (toilet_x, toilet_y, 90, 85), 2)
            pygame.draw.ellipse(self._bg_surface, (220, 220, 230), (toilet_x + 10, toilet_y + 5, 70, 50))

            tp_x = toilet_x - 30
            tp_y = toilet_y + 10
            pygame.draw.rect(self._bg_surface, (80, 80, 90), (tp_x + 5, tp_y - 15, 5, 20))
            pygame.draw.circle(self._bg_surface, (240, 235, 225), (tp_x + 7, tp_y + 8), 12)
            pygame.draw.circle(self._bg_surface, (180, 175, 165), (tp_x + 7, tp_y + 8), 5)

        # Blit cached background
        self._screen.blit(self._bg_surface, (0, 0))

        # Party mode: disco lighting overlay (dynamic, not cached)
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

        # Draw connection status + visitor count
        status_color = (0, 255, 0) if self.connected else (255, 0, 0)
        status_text = "\u25cf Connected" if self.connected else "\u25cf Disconnected"
        # Show reconnection attempt info when disconnected
        reconnect_info = self._reconnect_info
        if not self.connected and reconnect_info and reconnect_info.get("attempting"):
            attempt = reconnect_info.get("attempt", 0)
            max_att = reconnect_info.get("max_attempts", 0)
            status_text = f"\u25cf Reconnecting... ({attempt}/{max_att})"
            pulse = abs(math.sin(self._frame * 0.08))
            status_color = (255, int(165 * pulse), 0)
        status_surf = self._font_small.render(status_text, True, status_color)
        self._screen.blit(status_surf, (WINDOW_WIDTH - 150, 15))

        # Draw visitor count
        if self._visitor_count > 0:
            vc_text = f"\U0001f464 {self._visitor_count} visitor{'s' if self._visitor_count != 1 else ''}"
            vc_surf = self._font_small.render(vc_text, True, (180, 180, 220))
            self._screen.blit(vc_surf, (WINDOW_WIDTH - 150, 35))

        # Speaking indicator (pulsing dot)
        if self._speaking:
            pulse = abs(math.sin(self._frame * 0.1)) * 255
            speak_color = (int(pulse), 200, int(pulse))
            speak_surf = self._font_small.render("\U0001f50a Speaking", True, speak_color)
            self._screen.blit(speak_surf, (WINDOW_WIDTH - 150, 55))
        elif self._last_response_time > 0:
            rt_color = (100, 255, 100) if self._last_response_time < 5 else (255, 200, 100)
            rt_surf = self._font_small.render(f"\u23f1 {self._last_response_time:.1f}s", True, rt_color)
            self._screen.blit(rt_surf, (WINDOW_WIDTH - 150, 55))

        # Draw emotion indicator
        emo_surf = self._font_small.render(f"Mood: {self._emotion}", True, (200, 200, 100))
        emo_bg = pygame.Surface((emo_surf.get_width() + 10, emo_surf.get_height() + 6), pygame.SRCALPHA)
        emo_bg.fill((0, 0, 0, 140))
        self._screen.blit(emo_bg, (5, 12))
        self._screen.blit(emo_surf, (10, 15))

        # Draw Mario sprite
        self._draw_mario()

        # Emotion flash overlay (on Mario area)
        self._draw_emotion_flash()

        # Draw particles on top of Mario
        self._draw_particles()

        # Draw speech bubble with typewriter (auto-clear after 8 seconds / 480 frames)
        if self.current_text:
            if self._frame - self._text_display_time > 480:
                self.current_text = ""
            else:
                self._draw_speech_bubble(self.current_text)
        elif self._thinking:
            # Animated thinking dots
            self._thinking_dots = (self._thinking_dots + 1) % 90
            dots = "." * ((self._thinking_dots // 15) % 4)
            self._draw_speech_bubble(f"Hmm{dots}")

        # Draw subtitle (auto-clear after 5 seconds / 300 frames)
        if self.subtitle_text:
            if self._frame - self._subtitle_set_frame > 300:
                self.subtitle_text = ""
            else:
                self._draw_subtitle(self.subtitle_text)

        # Draw keyboard input area
        if self.keyboard_mode:
            self._draw_keyboard_input()

        # Draw state / mode indicators
        conn_color = (50, 200, 50) if self.connected else (200, 50, 50)
        conn_text = "● Connected" if self.connected else "● Disconnected"
        indicators = [conn_text, f"[{self.state.upper()}]"]
        if self.keyboard_mode:
            indicators.append("[TAB: Keyboard Mode]")
        if self.party_mode:
            indicators.append("[F5: Party Mode]")
        ind_text = " ".join(indicators)
        ind_surf = self._font_small.render(ind_text, True, conn_color)
        ind_bg = pygame.Surface((ind_surf.get_width() + 10, ind_surf.get_height() + 6), pygame.SRCALPHA)
        ind_bg.fill((0, 0, 0, 140))
        self._screen.blit(ind_bg, (5, WINDOW_HEIGHT - 33))
        self._screen.blit(ind_surf, (10, WINDOW_HEIGHT - 30))

        # Hint for keyboard/party toggle
        hint = "TAB: type | F5: party | +/-: vol | ESC: quit"
        hint_surf = self._font_small.render(hint, True, (100, 100, 120))
        self._screen.blit(hint_surf, (WINDOW_WIDTH - hint_surf.get_width() - 10, WINDOW_HEIGHT - 20))

        # Volume overlay (fades out after ~2 seconds)
        self._draw_volume_overlay()

        # Leaderboard overlay (F6 toggle)
        self._draw_leaderboard()

        # Screen edge glow for emotion changes
        self._draw_edge_glow()

        pygame.display.flip()

    def _draw_mario(self):
        """Draw the Mario sprite with crossfade transitions, breathing,
        talking bounce, entrance/exit spring, excitement shake, and emotion flash."""
        now = time.time()

        # --- Get target sprite ---
        sprite_key = self._get_current_sprite()
        sprite = self._sprites.get(sprite_key)
        if not sprite:
            sprite = self._sprites.get("neutral/idle") or self._sprites.get("idle")
        if not sprite:
            return

        # --- Sprite crossfade detection ---
        if sprite_key != self._last_sprite_key and self._last_sprite_key is not None:
            old_spr = self._sprites.get(self._last_sprite_key)
            if old_spr:
                self._crossfade_from_surface = old_spr
                self._crossfade_start = now
        self._last_sprite_key = sprite_key

        crossfade_progress = 1.0
        if self._crossfade_from_surface is not None:
            elapsed_cf = now - self._crossfade_start
            if elapsed_cf < self._crossfade_duration:
                crossfade_progress = elapsed_cf / self._crossfade_duration
            else:
                self._crossfade_from_surface = None

        # --- Animation offsets ---
        offset_x = 0
        offset_y = 0
        scale = 1.0
        rotation = 0.0
        alpha = 255

        # 1. Idle breathing animation (sine wave, ~3s period)
        if self.state == STATE_IDLE and not self._transition_active:
            breath = math.sin(2.0 * math.pi * now / 3.0)
            offset_y += int(breath * 3)                        # ±3px vertical bob
            scale *= 1.0 + 0.01 * (1.0 + breath)              # 1.0 → 1.02

        # 2. Talking bounce
        if self.state == STATE_TALKING:
            offset_y += int(math.sin(self._frame * 0.3) * 6)  # general talking bob
            # Word-based micro-bounce on word boundaries
            char_count = int(self._typewriter_pos)
            if char_count > self._talk_last_char_count and self._typewriter_text:
                new_text = self._typewriter_text[self._talk_last_char_count:char_count]
                if ' ' in new_text or any(c in '.,!?;:' for c in new_text):
                    self._talk_bounce_start = now
            self._talk_last_char_count = char_count
            bounce_elapsed = now - self._talk_bounce_start
            if 0 < bounce_elapsed < 0.2:
                t = bounce_elapsed / 0.2
                offset_y -= int(5 * math.sin(t * math.pi))    # 5px up then down
        else:
            self._talk_last_char_count = 0

        # Preserved state bounces
        if self.state == STATE_THINKING:
            offset_y += int(math.sin(self._frame * 0.15) * 5)
        elif self.state == STATE_DANCING:
            offset_y += int(math.sin(self._frame * 0.4) * 8)

        # 5. Excitement shake (excited emotion)
        if self._emotion == "excited" and not self._transition_active:
            scale *= 1.0 + math.sin(self._frame * 0.2) * 0.03  # scale pulse
            offset_x += random.randint(-3, 3)                   # rapid position jitter
            offset_y += random.randint(-3, 3)
            rotation = random.uniform(-5, 5)                    # ±5° rotation wobble
            if self._frame % 5 == 0:                            # faster particles
                self._spawn_emotion_particles("excited")
        elif self._emotion == "sleepy":
            offset_y += int(math.sin(self._frame * 0.02) * 2)
        elif self._emotion == "surprised":
            offset_y -= 10

        # 4. Entrance/Exit time-based transitions with spring
        if self._transition_active:
            elapsed = now - self._enter_exit_start
            if self._transition_type == "enter":
                duration = 1.5
                if elapsed >= duration:
                    self._transition_active = False
                    self.state = STATE_IDLE
                else:
                    t = min(elapsed / duration, 1.0)
                    spring_val = self._spring_ease_out(t)
                    start_x = -200 - sprite.get_width() // 2
                    offset_x = int(start_x * (1.0 - spring_val))
            elif self._transition_type == "exit":
                wave_dur = 0.5
                slide_dur = 1.0
                total = wave_dur + slide_dur
                if elapsed >= total:
                    self._transition_active = False
                    self.state = STATE_IDLE
                elif elapsed >= wave_dur:
                    slide_t = (elapsed - wave_dur) / slide_dur
                    eased = self._ease_in_out(slide_t)
                    offset_x = int(WINDOW_WIDTH * eased)
                    alpha = max(0, int(255 * (1.0 - slide_t)))

        # Gentle sway for idle
        if self.state == STATE_IDLE and not self._transition_active:
            sway = int(math.sin(self._frame * 0.03) * 3)
            offset_x += sway

        # --- Render sprite with transforms ---
        def apply_transforms(spr, scl, rot):
            if scl != 1.0:
                w = max(1, int(spr.get_width() * scl))
                h = max(1, int(spr.get_height() * scl))
                spr = pygame.transform.smoothscale(spr, (w, h))
            if abs(rot) > 0.1:
                spr = pygame.transform.rotate(spr, rot)
            return spr

        display_sprite = apply_transforms(sprite, scale, rotation)
        cx = WINDOW_WIDTH // 2 - display_sprite.get_width() // 2 + offset_x
        cy = WINDOW_HEIGHT // 2 - display_sprite.get_height() // 2 + 40 + offset_y

        # --- Draw with crossfade and/or alpha ---
        if self._crossfade_from_surface is not None and crossfade_progress < 1.0:
            # Old sprite fading out
            old_spr = apply_transforms(self._crossfade_from_surface, scale, rotation)
            old_copy = old_spr.copy()
            old_copy.set_alpha(int(255 * (1.0 - crossfade_progress)))
            ocx = WINDOW_WIDTH // 2 - old_copy.get_width() // 2 + offset_x
            ocy = WINDOW_HEIGHT // 2 - old_copy.get_height() // 2 + 40 + offset_y
            self._screen.blit(old_copy, (ocx, ocy))
            # New sprite fading in
            new_copy = display_sprite.copy()
            new_copy.set_alpha(int(255 * crossfade_progress))
            self._screen.blit(new_copy, (cx, cy))
        elif alpha < 255:
            faded = display_sprite.copy()
            faded.set_alpha(alpha)
            self._screen.blit(faded, (cx, cy))
        else:
            self._screen.blit(display_sprite, (cx, cy))

    @staticmethod
    def _ease_in_out(t: float) -> float:
        """Smooth ease-in-out interpolation."""
        return t * t * (3 - 2 * t)

    @staticmethod
    def _spring_ease_out(t: float) -> float:
        """Ease-out with elastic spring overshoot (~20px at display scale)."""
        if t <= 0:
            return 0.0
        if t >= 1:
            return 1.0
        c4 = (2 * math.pi) / 3
        return math.pow(2, -10 * t) * math.sin((t * 10 - 0.75) * c4) + 1

    def _trigger_emotion_flash(self, emotion: str):
        """Set up emotion flash effect (color tint + edge glow)."""
        now = time.time()
        self._emotion_flash_start = now
        self._edge_glow_start = now

        flash_map = {
            "happy": ((255, 215, 0), "golden"),
            "excited": ((255, 255, 0), "rainbow"),
            "surprised": ((255, 255, 255), "white"),
            "shocked": ((255, 255, 255), "white"),
            "angry": ((255, 50, 30), "red"),
            "frustrated": ((255, 80, 40), "red"),
            "sad": ((80, 130, 255), "blue"),
            "nervous": ((100, 150, 255), "blue"),
            "love": ((255, 100, 150), "golden"),
            "loving": ((255, 100, 150), "golden"),
            "proud": ((255, 200, 0), "golden"),
            "laughing": ((255, 255, 100), "golden"),
            "mischievous": ((0, 255, 100), "golden"),
        }

        color, flash_type = flash_map.get(emotion, ((200, 200, 200), "white"))
        self._emotion_flash_color = color
        self._emotion_flash_type = flash_type
        self._edge_glow_color = color

    def _draw_emotion_flash(self):
        """Draw brief color tint flash overlay on Mario when emotion changes."""
        now = time.time()
        elapsed = now - self._emotion_flash_start
        if elapsed > 0.2:
            return

        intensity = 1.0 - (elapsed / 0.2)

        if self._emotion_flash_type == "rainbow":
            colors = self._disco_colors
            idx = int(elapsed * 30) % len(colors)
            r, g, b = colors[idx]
        else:
            r, g, b = self._emotion_flash_color

        flash_alpha = int(60 * intensity)
        flash_w = AI_POSE_DISPLAY_SIZE[0] + 40
        flash_h = AI_POSE_DISPLAY_SIZE[1] + 40
        flash_x = WINDOW_WIDTH // 2 - flash_w // 2
        flash_y = WINDOW_HEIGHT // 2 - flash_h // 2 + 40

        flash_surf = pygame.Surface((flash_w, flash_h), pygame.SRCALPHA)
        flash_surf.fill((r, g, b, flash_alpha))
        self._screen.blit(flash_surf, (flash_x, flash_y))

    def _draw_edge_glow(self):
        """Draw screen edge glow matching emotion color for 500ms."""
        now = time.time()
        elapsed = now - self._edge_glow_start
        if elapsed > 0.5:
            return

        intensity = 1.0 - (elapsed / 0.5)
        r, g, b = self._edge_glow_color
        glow_alpha = int(40 * intensity)
        glow_w = 40

        top = pygame.Surface((WINDOW_WIDTH, glow_w), pygame.SRCALPHA)
        top.fill((r, g, b, glow_alpha))
        self._screen.blit(top, (0, 0))

        bottom = pygame.Surface((WINDOW_WIDTH, glow_w), pygame.SRCALPHA)
        bottom.fill((r, g, b, glow_alpha))
        self._screen.blit(bottom, (0, WINDOW_HEIGHT - glow_w))

        left = pygame.Surface((glow_w, WINDOW_HEIGHT), pygame.SRCALPHA)
        left.fill((r, g, b, glow_alpha))
        self._screen.blit(left, (0, 0))

        right = pygame.Surface((glow_w, WINDOW_HEIGHT), pygame.SRCALPHA)
        right.fill((r, g, b, glow_alpha))
        self._screen.blit(right, (WINDOW_WIDTH - glow_w, 0))

    def _draw_speech_bubble(self, text: str):
        """Draw Mario's speech bubble with style variations."""
        style = self._detect_bubble_style(self._typewriter_text)
        max_width = 350
        words = text.split()
        lines = []
        current_line = ""

        for word in words:
            # Break long words that exceed max_width on their own
            if self._font.size(word)[0] > max_width:
                if current_line:
                    lines.append(current_line)
                    current_line = ""
                # Split by character
                for char in word:
                    test = current_line + char
                    if self._font.size(test)[0] > max_width:
                        lines.append(current_line)
                        current_line = char
                    else:
                        current_line = test
                continue
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

    def _draw_volume_overlay(self):
        """Draw a volume indicator that fades out after ~2 seconds."""
        frames_since = self._frame - self._volume_show_frame
        if frames_since >= self._volume_display_duration:
            return

        # Fade out over the last 20 frames
        fade_start = self._volume_display_duration - 20
        if frames_since > fade_start:
            alpha = int(255 * (1.0 - (frames_since - fade_start) / 20.0))
        else:
            alpha = 255

        pct = int(self._volume_level * 100)
        # Pick icon based on level
        if self._volume_level <= 0.01:
            icon = "\U0001f507"  # muted
        elif self._volume_level < 0.5:
            icon = "\U0001f509"  # low
        elif self._volume_level <= 1.0:
            icon = "\U0001f50a"  # normal
        else:
            icon = "\U0001f50a"  # loud (boosted)

        label = f"{icon} Volume: {pct}%"
        label_surf = self._font.render(label, True, (255, 255, 255))

        # Draw filled volume bar
        bar_w = 160
        bar_h = 12
        bar_x = 15
        bar_y = 55

        # Background panel
        panel_w = max(label_surf.get_width() + 20, bar_w + 30)
        panel_h = label_surf.get_height() + bar_h + 20
        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel.fill((0, 0, 0, min(180, alpha)))

        # Label on panel
        label_alpha_surf = pygame.Surface(label_surf.get_size(), pygame.SRCALPHA)
        label_alpha_surf.blit(label_surf, (0, 0))
        label_alpha_surf.set_alpha(alpha)
        panel.blit(label_alpha_surf, (10, 5))

        # Bar background
        pygame.draw.rect(panel, (60, 60, 60, alpha), (10, label_surf.get_height() + 10, bar_w, bar_h), border_radius=4)

        # Bar fill (green->yellow->red as volume increases)
        fill_w = int(bar_w * min(self._volume_level / 2.0, 1.0))
        if self._volume_level <= 1.0:
            bar_color = (80, 220, 80, alpha)
        elif self._volume_level <= 1.5:
            bar_color = (220, 220, 50, alpha)
        else:
            bar_color = (220, 80, 80, alpha)
        if fill_w > 0:
            pygame.draw.rect(panel, bar_color, (10, label_surf.get_height() + 10, fill_w, bar_h), border_radius=4)

        self._screen.blit(panel, (10, 45))

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

    def update_leaderboard(self, data: dict):
        """Update leaderboard data from server."""
        self._leaderboard_data = data
        if DEBUG_DISPLAY:
            logger.info(f"[DEBUG_DISPLAY] Leaderboard data updated")

    def _draw_leaderboard(self):
        """Draw the party leaderboard overlay on the right side of the screen."""
        if not self._leaderboard_visible:
            return

        # Auto-hide after 15 seconds if not interacted with
        if self._frame - self._leaderboard_show_frame > self._leaderboard_auto_hide_frames:
            self._leaderboard_visible = False
            return

        screen_w = self._screen.get_width()
        screen_h = self._screen.get_height()
        panel_w = int(screen_w * 0.4)
        panel_x = screen_w - panel_w

        # Semi-transparent dark background
        overlay = pygame.Surface((panel_w, screen_h), pygame.SRCALPHA)
        overlay.fill((10, 10, 30, 200))
        self._screen.blit(overlay, (panel_x, 0))

        # Gold border on left edge
        pygame.draw.line(self._screen, (255, 215, 0), (panel_x, 0), (panel_x, screen_h), 2)

        data = self._leaderboard_data
        y = 15
        cx = panel_x + panel_w // 2

        # Title
        title_text = "PARTY LEADERBOARD"
        title_surf = self._font_title.render(title_text, True, (255, 215, 0))
        self._screen.blit(title_surf, (cx - title_surf.get_width() // 2, y))
        y += 45

        # Trophy decorations
        trophy_left = self._font.render("\u2b50", True, (255, 215, 0))
        trophy_right = self._font.render("\u2b50", True, (255, 215, 0))
        self._screen.blit(trophy_left, (panel_x + 15, 18))
        self._screen.blit(trophy_right, (panel_x + panel_w - 35, 18))

        # Divider line
        pygame.draw.line(self._screen, (255, 215, 0), (panel_x + 15, y), (panel_x + panel_w - 15, y), 1)
        y += 12

        # Category entries
        categories = []

        # Most visits
        mv = data.get("most_visits", {})
        if mv.get("name"):
            categories.append(("Most Visits", f"{mv['name']} ({mv.get('count', 0)})", (255, 215, 0)))

        # Longest stay
        ls = data.get("longest_stay", {})
        if ls.get("name"):
            minutes = ls.get("minutes", 0)
            categories.append(("Longest Stay", f"{ls['name']} ({minutes:.0f}m)", (100, 200, 255)))

        # Game champion
        gc = data.get("game_champion", {})
        if gc.get("name"):
            categories.append(("Game Champion", f"{gc['name']} ({gc.get('score', 0)})", (255, 100, 100)))

        # Most chatty
        chatty = data.get("most_chatty")
        if chatty:
            categories.append(("Most Chatty", chatty, (100, 255, 200)))

        # Total visitors
        total = data.get("unique_visitors", 0)
        categories.append(("Total Visitors", str(total), (200, 200, 255)))

        # Party duration
        pd = data.get("party_duration", {})
        if pd:
            h = pd.get("hours", 0)
            m = pd.get("minutes", 0)
            categories.append(("Party Duration", f"{h}h {m}m", (255, 180, 100)))

        # Funniest moment
        fm = data.get("funniest_moment", {})
        if fm and fm.get("name"):
            categories.append(("Funniest Moment", fm["name"], (255, 255, 100)))

        # Most dramatic
        md = data.get("most_dramatic", {})
        if md and md.get("name"):
            categories.append(("Most Dramatic", f"{md['name']} ({md.get('count', 0)})", (255, 100, 255)))

        # Draw category entries
        icons = {
            "Most Visits": "\u265a",
            "Longest Stay": "\u23f1",
            "Game Champion": "\u2605",
            "Most Chatty": "\u266a",
            "Total Visitors": "\u2606",
            "Party Duration": "\u25cb",
            "Funniest Moment": "\u263a",
            "Most Dramatic": "\u2727",
        }
        for label, value, color in categories:
            if y > screen_h - 80:
                break
            icon = icons.get(label, "\u2022")
            label_surf = self._font_small.render(f"{icon} {label}:", True, (180, 180, 200))
            value_surf = self._font.render(value, True, color)
            self._screen.blit(label_surf, (panel_x + 20, y))
            y += 20
            self._screen.blit(value_surf, (panel_x + 30, y))
            y += 30

        # Top visitors list
        visitors = data.get("visitors", [])
        if visitors and y < screen_h - 100:
            y += 5
            pygame.draw.line(self._screen, (100, 100, 140), (panel_x + 15, y), (panel_x + panel_w - 15, y), 1)
            y += 8
            rank_header = self._font_small.render("Top Visitors", True, (255, 215, 0))
            self._screen.blit(rank_header, (cx - rank_header.get_width() // 2, y))
            y += 22
            for i, visitor in enumerate(visitors[:5]):
                if y > screen_h - 60:
                    break
                name = visitor.get("name", "???")
                count = visitor.get("visit_count", 0)
                rank_colors = [(255, 215, 0), (200, 200, 210), (205, 127, 50),
                               (180, 180, 200), (160, 160, 180)]
                rc = rank_colors[i] if i < len(rank_colors) else (150, 150, 170)
                entry_surf = self._font_small.render(f"#{i+1}  {name} — {count} visits", True, rc)
                self._screen.blit(entry_surf, (panel_x + 25, y))
                y += 20

        # Scrolling ticker at bottom
        ticker_stats = data.get("ticker_stats", [])
        if ticker_stats:
            self._leaderboard_ticker_frame += 1
            if self._leaderboard_ticker_frame >= self._leaderboard_ticker_interval:
                self._leaderboard_ticker_frame = 0
                self._leaderboard_ticker_index = (self._leaderboard_ticker_index + 1) % len(ticker_stats)
            ticker_y = screen_h - 35
            pygame.draw.rect(self._screen, (20, 20, 50), (panel_x, ticker_y - 5, panel_w, 30))
            pygame.draw.line(self._screen, (255, 215, 0), (panel_x, ticker_y - 5), (panel_x + panel_w, ticker_y - 5), 1)
            idx = self._leaderboard_ticker_index % len(ticker_stats)
            ticker_text = ticker_stats[idx]
            # Pulsing alpha effect
            pulse = abs(math.sin(self._frame * 0.05))
            g_val = int(200 + 55 * pulse)
            ticker_surf = self._font_small.render(f"\u2726 {ticker_text}", True, (g_val, g_val, 100))
            self._screen.blit(ticker_surf, (panel_x + 15, ticker_y))

    def quit(self):
        """Clean up Pygame."""
        self._running = False
        if getattr(self, '_initialized', False):
            try:
                pygame.quit()
            except Exception:
                pass
            self._initialized = False
