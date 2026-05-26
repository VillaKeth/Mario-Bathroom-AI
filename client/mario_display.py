"""Mario sprite display with background scene, transitions, typewriter bubbles,
keyboard input, party effects, and emotion-mapped reaction sprites."""

import os
import logging
import math
import random
import re
import string
import time
import pygame
from closed_captions import ClosedCaptions

DEBUG_DISPLAY = True
logger = logging.getLogger(__name__)

WINDOW_WIDTH = 800
WINDOW_HEIGHT = 600
BG_COLOR = (20, 20, 40)
TEXT_COLOR = (255, 255, 255)

# Regex to strip emoji/symbol characters that Pygame fonts can't render
_EMOJI_RE = re.compile(
    "["
    "\U0001F600-\U0001F64F"  # emoticons
    "\U0001F300-\U0001F5FF"  # symbols & pictographs
    "\U0001F680-\U0001F6FF"  # transport & map
    "\U0001F1E0-\U0001F1FF"  # flags
    "\U00002702-\U000027B0"  # dingbats
    "\U0001F900-\U0001F9FF"  # supplemental symbols
    "\U0001FA00-\U0001FA6F"  # chess symbols
    "\U0001FA70-\U0001FAFF"  # symbols extended-A
    "\U00002600-\U000026FF"  # misc symbols
    "\U0000FE00-\U0000FE0F"  # variation selectors
    "\U0000200D"             # zero-width joiner
    "\U00002B50"             # star
    "\U0001F4A0-\U0001F4FF"  # misc symbols
    "]+",
    flags=re.UNICODE
)

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
# Values can be a single string or a list for random selection.
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
    "memorial": "memorial/moment_of_silence",
    "toast": "toast/raising_glass",
    "party": "party/celebrate",
    "grossed_out": "bathroom/grossed_out",
    "mind_blown": "reactions/mind_blown",
    "sassy": "reactions/sassy",
    "cringe": "reactions/cringe",
    "impressed": "reactions/impressed",
    "celebratory": "party/cheers",
    "solemn": "memorial/moment_of_silence",
    "birthday": "birthday/birthday_boy",
}

# Map states to AI pose paths (string or list for cycling/random)
STATE_SPRITE_MAP = {
    STATE_IDLE: "neutral/idle",
    STATE_TALKING: ["speech/talking", "speech/talking_excited"],
    STATE_LISTENING: "speech/listening",
    STATE_GREETING: "greeting/wave_high",
    STATE_THINKING: "thinking/thinking",
    STATE_SLEEPING: "sleep/sleeping",
    STATE_DANCING: ["movement/dancing_1", "movement/dancing_2", "party/celebrate", "birthday/party_dance"],
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

# Emotion badge visuals — emoji + color per mood
EMOTION_EMOJI = {
    "happy": "☺", "excited": "★", "surprised": "!", "confused": "?",
    "annoyed": "×", "sleepy": "~", "mischievous": "♦", "laughing": "♪",
    "sad": "♡", "angry": "!", "loving": "♥", "love": "♥",
    "proud": "★", "frustrated": "×", "embarrassed": "~", "worried": "~",
    "bored": "—", "determined": "!", "nervous": "~", "scared": "!",
    "disgusted": "×", "curious": "?", "thinking": "?", "shocked": "!",
    "idea": "★", "neutral": "—", "memorial": "♥", "toast": "★",
    "party": "♪", "grossed_out": "×", "mind_blown": "!", "sassy": "♦",
    "cringe": "~", "impressed": "★", "celebratory": "♪", "solemn": "♥",
    "birthday": "★",
}

EMOTION_BADGE_COLORS = {
    "happy": (255, 220, 50), "excited": (255, 160, 0), "surprised": (200, 100, 255),
    "confused": (130, 130, 255), "annoyed": (255, 120, 50), "sleepy": (100, 100, 200),
    "mischievous": (50, 200, 100), "laughing": (255, 230, 50), "sad": (100, 150, 255),
    "angry": (255, 50, 50), "loving": (255, 100, 150), "love": (255, 80, 130),
    "proud": (255, 200, 0), "frustrated": (255, 80, 30), "embarrassed": (255, 170, 200),
    "worried": (180, 180, 255), "bored": (160, 160, 160), "determined": (255, 165, 0),
    "nervous": (200, 200, 255), "scared": (180, 180, 255),
    "disgusted": (150, 200, 50), "curious": (100, 200, 255), "thinking": (150, 150, 220),
    "shocked": (255, 80, 200), "idea": (255, 240, 100), "neutral": (180, 180, 180),
    "memorial": (200, 170, 255), "toast": (255, 200, 100), "party": (255, 100, 200),
    "grossed_out": (150, 180, 50), "mind_blown": (200, 50, 255), "sassy": (255, 100, 180),
    "cringe": (220, 180, 200), "impressed": (100, 220, 200), "celebratory": (255, 200, 50),
    "solemn": (140, 140, 200), "birthday": (255, 180, 50),
}

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
        self._chat_title_font = None
        self._chat_msg_font = None

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
        self._typewriter_speed = 2  # chars per frame (default, overridden by audio sync)
        self._typewriter_audio_synced = False  # True when speed is calculated from audio duration

        # Page-based text display (auto-advances with speech)
        self._text_pages = []  # list of lists of lines per page
        self._text_page_char_ranges = []  # (start_char, end_char) for each page
        self._current_page = 0
        self._page_transition_alpha = 255  # for fade transitions
        self._page_transition_frame = 0

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
        self._thinking_start = 0
        self._THINKING_TIMEOUT = 60.0  # auto-cancel after 60s

        # Response timing display
        self._last_response_time = 0
        self._visitor_count = 0
        self._speaking = False

        # Emotion badge pop animation
        self._emotion_badge_scale = 1.0
        self._emotion_badge_pop_time = 0.0

        # Mood meter (rolling sentiment bar)
        self._mood_score = 0.0  # -1.0 to +1.0
        self._mood_display = 0.0  # Smoothly animated toward _mood_score
        self._mood_label = ""  # e.g. "Vibing", "Neutral", "Grumpy"

        # Fullscreen toggle with proportional scaling
        self._fullscreen = False
        self._windowed_scaled = False  # True when window is resized/maximized
        self._display_scale = 1.0  # scale factor for fullscreen proportional scaling
        self._native_width = WINDOW_WIDTH
        self._native_height = WINDOW_HEIGHT
        self._fs_scale = 1.0
        self._render_w = WINDOW_WIDTH
        self._render_h = WINDOW_HEIGHT

        # Chat history sidebar (F3 toggle)
        self._chat_history = []  # List of {"role": "mario"|"user", "text": str}
        self._show_chat_history = False
        self._MAX_CHAT_HISTORY = 20

        # Panic mode (Konami-like sequence: Up Up Down Down Left Right)
        self._panic_mode = False
        self._panic_sequence_buffer = []  # last arrow key presses
        self._PANIC_SEQUENCE = [pygame.K_UP, pygame.K_UP, pygame.K_DOWN, pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT]

        # Help overlay
        self._show_help = False

        # Connection status overlay for error recovery
        self._connection_status = None
        self._camera_status = None  # None=no camera, "connected", "reconnecting"

        # Party info banner
        self._party_start_time = time.time()
        self._party_name = "Jacob's Birthday Party"
        self._guest_count = 0
        self._banner_bottom = 48  # updated by _draw_party_banner each frame

        # --- Enhanced animation system (time-based, frame-independent) ---
        # Sprite crossfade
        self._crossfade_start = 0.0
        self._crossfade_from_surface = None
        self._crossfade_duration = 0.5  # 500ms crossfade for smooth transitions
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

        # Health overlay (F4 toggle)
        self._health_visible = False
        self._health_data = {}

        # Memorial overlay
        self._memorial_active = False
        self._memorial_phase = "silence"
        self._memorial_name = ""
        self._memorial_text = ""
        self._memorial_start = 0.0
        self._memorial_duration = 15
        self._memorial_particles = []  # Floating golden light particles
        self._memorial_photo = None
        self._event_image = None  # Event-specific image (loaded dynamically)
        self._event_image_path = None  # Track loaded path to avoid reloading
        
        # Closed captions (initialized after pygame.init() in init() method)
        self.captions = None

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
            # Expanded categories
            "party", "memorial", "toast", "bathroom", "reactions",
            "birthday", "gaming",
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

    def _load_backgrounds(self):
        """Load all background images from client/assets/backgrounds/."""
        backgrounds_dir = os.path.join(os.path.dirname(__file__), "assets", "backgrounds")
        if not os.path.isdir(backgrounds_dir):
            if DEBUG_DISPLAY:
                logger.info("[DEBUG_DISPLAY] No backgrounds directory found")
            return
        
        supported_formats = ('.png', '.jpg', '.jpeg')
        for filename in os.listdir(backgrounds_dir):
            if filename.lower().endswith(supported_formats):
                path = os.path.join(backgrounds_dir, filename)
                try:
                    img = pygame.image.load(path).convert()
                    # Scale to window size
                    img = pygame.transform.scale(img, (WINDOW_WIDTH, WINDOW_HEIGHT))
                    self._backgrounds.append({
                        'name': filename,
                        'image': img
                    })
                    if DEBUG_DISPLAY:
                        logger.info(f"[DEBUG_DISPLAY] Loaded background: {filename}")
                except Exception as e:
                    logger.warning(f"[DEBUG_DISPLAY] Failed to load background {filename}: {e}")
        
        if DEBUG_DISPLAY:
            logger.info(f"[DEBUG_DISPLAY] Loaded {len(self._backgrounds)} background images")

    def init(self):
        """Initialize Pygame display."""
        if DEBUG_DISPLAY:
            logger.info("[DEBUG_DISPLAY] MarioDisplay.init: START")

        pygame.init()
        self._initialized = True
        pygame.display.set_caption("Mario AI \U0001f344")
        self._screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.RESIZABLE)

        # Auto-move window to Desktop 2 if available (keeps Desktop 1 clear for user)
        try:
            import pyvda
            desktops = pyvda.get_virtual_desktops()
            if len(desktops) >= 2:
                import ctypes, ctypes.wintypes
                # Find our window by title
                hwnd = ctypes.windll.user32.FindWindowW(None, "Mario AI \U0001f344")
                if not hwnd:
                    # Fallback: use pygame's wm_info
                    hwnd = pygame.display.get_wm_info().get("window", 0)
                if hwnd:
                    app_view = pyvda.AppView(hwnd=hwnd)
                    app_view.move(desktops[1])  # Desktop 2 (0-indexed)
                    logger.info("[DEBUG_DISPLAY] Moved window to Desktop 2")
        except Exception as e:
            logger.debug(f"[DEBUG_DISPLAY] Could not move to Desktop 2: {e}")
        # Render buffer: all drawing happens at 800x600, then scaled to screen
        self._render_buffer = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT))
        self._clock = pygame.time.Clock()
        self._font = pygame.font.Font(None, 28)
        self._font_small = pygame.font.Font(None, 22)
        self._font_title = pygame.font.Font(None, 48)
        self._font_input = pygame.font.Font(None, 32)
        self._chat_title_font = pygame.font.SysFont("arial", 16, bold=True)
        self._chat_msg_font = pygame.font.SysFont("arial", 13)
        # Pre-cache bubble fonts — prefer a friendly font that fits Mario's personality
        bubble_font_path = None
        for font_name in ["segoeui", "calibri", "arial", "comicsansms"]:
            match = pygame.font.match_font(font_name)
            if match:
                bubble_font_path = match
                break
        self._bubble_fonts = {
            size: pygame.font.Font(bubble_font_path, size)
            for size in range(14, 30, 2)  # 14, 16, 18, 20, 22, 24, 26, 28
        }
        self._running = True

        # ── Memorial photo loading (requires pygame to be initialized) ──
        try:
            photo_path = os.path.join(os.path.dirname(__file__), "assets", "images", "lisa_webb.jpg")
            if os.path.exists(photo_path):
                raw = pygame.image.load(photo_path)
                scale = 300 / raw.get_height()
                new_w = int(raw.get_width() * scale)
                self._memorial_photo = pygame.transform.smoothscale(raw, (new_w, 300))
                if DEBUG_DISPLAY:
                    logger.info(f"[DEBUG_DISPLAY] Memorial photo loaded: {new_w}x300")
        except Exception as e:
            logger.warning(f"[DEBUG_DISPLAY] Failed to load memorial photo: {e}")

        self._load_sprites()
        self._bg_surface = None  # cached static background
        
        # Background system
        self._backgrounds = []  # loaded background images
        self._current_bg_index = -1  # -1 = use drawn background, 0+ = use image
        self._load_backgrounds()
        self._bg_auto_cycle = False
        self._bg_last_cycle_time = time.time()
        
        # Initialize closed captions
        self.captions = ClosedCaptions(WINDOW_WIDTH, WINDOW_HEIGHT)

        if DEBUG_DISPLAY:
            logger.info("[DEBUG_DISPLAY] MarioDisplay.init: END")

    def load_event_image(self, image_file):
        """Load an event-specific image for display during shot events."""
        try:
            if image_file == self._event_image_path and self._event_image:
                return  # Already loaded
            # Resolve relative paths — try from client dir first, then project root
            if not os.path.isabs(image_file):
                client_dir = os.path.dirname(__file__)
                project_root = os.path.dirname(client_dir)
                candidate = os.path.join(client_dir, image_file)
                if not os.path.exists(candidate):
                    candidate = os.path.join(project_root, image_file)
                image_file = candidate
            if os.path.exists(image_file):
                raw = pygame.image.load(image_file).convert_alpha()
                scale = 300 / raw.get_height()
                new_w = int(raw.get_width() * scale)
                self._event_image = pygame.transform.smoothscale(raw, (new_w, 300))
                self._event_image_path = image_file
                if DEBUG_DISPLAY:
                    logger.info(f"[DEBUG_DISPLAY] Event image loaded: {image_file} ({new_w}x300)")
            else:
                logger.warning(f"[DEBUG_DISPLAY] Event image not found: {image_file}")
        except Exception as e:
            logger.warning(f"[DEBUG_DISPLAY] Failed to load event image: {e}")

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
                    elif event.key == pygame.K_F1:
                        self._show_help = not self._show_help
                    elif event.key == pygame.K_F3:
                        self._show_chat_history = not self._show_chat_history
                    elif event.key == pygame.K_F4:
                        self._health_visible = not self._health_visible
                    elif event.key == pygame.K_F5:
                        self.party_mode = not self.party_mode
                    elif event.key == pygame.K_F6:
                        self._leaderboard_visible = not self._leaderboard_visible
                        if self._leaderboard_visible:
                            self._leaderboard_show_frame = self._frame
                    elif event.key == pygame.K_F7:
                        self.next_background()
                    elif event.key == pygame.K_F8:
                        self._bg_auto_cycle = not self._bg_auto_cycle
                        logger.info(f"[DISPLAY] Background auto-cycle: {'ON' if self._bg_auto_cycle else 'OFF'}")
                    elif event.key == pygame.K_F11:
                        self._toggle_fullscreen()
                    elif event.key == pygame.K_F12:
                        self._toggle_panic_mode()
                    elif event.key in (pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT):
                        # Konami-like sequence to toggle panic mode
                        self._panic_sequence_buffer.append(event.key)
                        self._panic_sequence_buffer = self._panic_sequence_buffer[-6:]
                        if self._panic_sequence_buffer == self._PANIC_SEQUENCE:
                            self._panic_sequence_buffer.clear()
                            self._toggle_panic_mode()
                    elif event.key == pygame.K_l and (pygame.key.get_mods() & pygame.KMOD_CTRL) and (pygame.key.get_mods() & pygame.KMOD_SHIFT):
                        # Ctrl+Shift+L: Skip memorial event
                        if self._memorial_active:
                            # Call the skip callback if it exists
                            try:
                                if hasattr(self, '_on_memorial_skip') and self._on_memorial_skip:
                                    self._on_memorial_skip()
                                # Clear memorial overlay
                                self._memorial_active = False
                                self.clear_memorial_overlay()
                            except Exception as e:
                                logger.error(f"Memorial skip error: {e}")
                    elif not self.keyboard_mode and event.key in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
                        if self.on_volume_change:
                            self.on_volume_change(0.1)
                    elif not self.keyboard_mode and event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                        if self.on_volume_change:
                            self.on_volume_change(-0.1)
                    elif not self.keyboard_mode and event.key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5, pygame.K_6, pygame.K_7, pygame.K_8, pygame.K_9, pygame.K_0):
                        game_prompts = {
                            pygame.K_1: "Let's play Trivia!",
                            pygame.K_2: "Let's play Rock Paper Scissors!",
                            pygame.K_3: "Truth or Dare!",
                            pygame.K_4: "Let's play Simon Says!",
                            pygame.K_5: "Let's play 20 Questions!",
                            pygame.K_6: "Tell me a joke!",
                            pygame.K_7: "Sing me a song!",
                            pygame.K_8: "Let's dance!",
                            pygame.K_9: "Would you rather!",
                            pygame.K_0: "Give me a fortune!",
                        }
                        prompt = game_prompts[event.key]
                        if self.on_keyboard_submit:
                            self.add_chat_message("user", prompt)
                            self.on_keyboard_submit(prompt)
                            self.set_subtitle(f"🎮 {prompt}")
                    elif self.keyboard_mode:
                        self._handle_keyboard_input(event)
                if event.type == pygame.VIDEORESIZE and not self._fullscreen:
                    self._handle_window_resize(event.w, event.h)

            self._frame += 1
            # Auto-cancel thinking state after timeout (prevents stuck indicator)
            if self._thinking and self._thinking_start > 0:
                if time.time() - self._thinking_start > self._THINKING_TIMEOUT:
                    logger.warning("[DISPLAY] Thinking timeout — auto-cancelling after 60s")
                    self._thinking = False
                    self._thinking_start = 0
            # Auto-cycle backgrounds every 5 minutes
            if self._bg_auto_cycle and self._backgrounds and time.time() - self._bg_last_cycle_time > 300:
                self.next_background()
                self._bg_last_cycle_time = time.time()
            self._update_typewriter()
            self._update_transition()
            self._draw()
            self._clock.tick(30)
            self._consecutive_errors = 0  # Reset error counter on success
            return True
        except pygame.error as e:
            logger.error(f"[DEBUG_DISPLAY] Pygame error in update(): {e}")
            # Try to recover instead of immediately dying
            self._consecutive_errors = getattr(self, '_consecutive_errors', 0) + 1
            if self._consecutive_errors > 10:
                logger.error("[DEBUG_DISPLAY] Too many consecutive errors, shutting down")
                self._running = False
                return False
            return True  # Try to continue

    def _handle_keyboard_input(self, event):
        """Handle keyboard input when in keyboard mode."""
        if event.key == pygame.K_RETURN:
            if self._keyboard_text.strip() and self.on_keyboard_submit:
                self.add_chat_message("user", self._keyboard_text.strip())
                self.on_keyboard_submit(self._keyboard_text.strip())
                self.subtitle_text = self._keyboard_text.strip()
                self._keyboard_text = ""
        elif event.key == pygame.K_BACKSPACE:
            if pygame.key.get_mods() & pygame.KMOD_CTRL:
                # Ctrl+Backspace: delete last word
                stripped = self._keyboard_text.rstrip()
                last_space = stripped.rfind(" ")
                self._keyboard_text = stripped[:last_space + 1] if last_space >= 0 else ""
            else:
                self._keyboard_text = self._keyboard_text[:-1]
        elif event.key == pygame.K_a and (pygame.key.get_mods() & pygame.KMOD_CTRL):
            pass  # Ctrl+A select all — no-op in single-line input
        elif event.key == pygame.K_v and (pygame.key.get_mods() & pygame.KMOD_CTRL):
            try:
                import subprocess
                clip = subprocess.run(["powershell", "-c", "Get-Clipboard"], capture_output=True, text=True, timeout=2)
                if clip.returncode == 0 and clip.stdout.strip():
                    paste = clip.stdout.strip()[:200 - len(self._keyboard_text)]
                    self._keyboard_text += paste
            except Exception:
                pass
        elif event.key == pygame.K_u and (pygame.key.get_mods() & pygame.KMOD_CTRL):
            self._keyboard_text = ""  # Ctrl+U: clear line
        else:
            if event.unicode and len(self._keyboard_text) < 200:
                self._keyboard_text += event.unicode

    def set_mario_text(self, text: str):
        """Set what Mario is saying (shown in speech bubble with typewriter effect)."""
        if text is None:
            text = ""
        # Strip emojis that Pygame fonts can't render (appear as missing glyphs)
        text = _EMOJI_RE.sub("", text).strip()
        self._typewriter_text = text
        self._typewriter_pos = 0
        self._typewriter_audio_synced = False
        self.current_text = ""
        self.state = STATE_TALKING
        self._text_display_time = self._frame
        self._talk_last_char_count = 0
        # Reset page state (pages will be calculated on first draw)
        self._text_pages = []
        self._text_page_char_ranges = []
        self._current_page = 0
        self._page_transition_alpha = 255
        self._page_transition_frame = 0
        if text:
            self.add_chat_message("mario", text)

    def sync_typewriter_to_audio(self, duration_seconds: float):
        """Adjust typewriter speed so text finishes slightly before audio ends.
        
        Called when audio arrives (after text). Calculates the exact
        chars-per-frame needed for text to complete in sync with audio.
        """
        if not self._typewriter_text:
            return
        remaining = len(self._typewriter_text) - self._typewriter_pos
        if remaining <= 0:
            return
        # Text should finish 0.3s before audio ends (feels natural)
        target_duration = max(0.5, duration_seconds - 0.3)
        # Calculate frames remaining in audio (at 30 FPS)
        frames_available = max(1, int(target_duration * 30))
        # Speed = chars per frame to finish text when audio ends
        speed = remaining / frames_available
        # Clamp: min 0.15 (still visible), max 8 (still readable)
        self._typewriter_speed = max(0.15, min(8.0, speed))
        self._typewriter_audio_synced = True

    def add_chat_message(self, role, text):
        """Add a message to chat history. role is 'mario' or 'user'."""
        if not isinstance(text, str):
            text = str(text) if text is not None else ""
        if not isinstance(role, str):
            role = str(role) if role is not None else "unknown"
        self._chat_history.append({"role": role, "text": text, "time": time.time()})
        if len(self._chat_history) > self._MAX_CHAT_HISTORY:
            self._chat_history.pop(0)

    def set_subtitle(self, text: str):
        """Set subtitle text (what the user said). Auto-clears after 5 seconds."""
        self.subtitle_text = text
        self._subtitle_set_frame = self._frame

    def update_health(self, data: dict):
        """Update cached health data for the overlay."""
        self._health_data = data

    def set_connection_status(self, connected: bool, attempt: int = 0, max_attempts: int = 20):
        """Update connection status display."""
        if connected:
            self._connection_status = None
        else:
            if attempt >= max_attempts:
                self._connection_status = "Cannot reach server - restart Mario AI"
            elif attempt > 0:
                self._connection_status = f"Reconnecting... (attempt {attempt}/{max_attempts})"
            else:
                self._connection_status = "Connecting..."

    def set_guest_count(self, count):
        """Update the party guest count shown in the banner."""
        self._guest_count = count

    def set_camera_status(self, status: str):
        """Update camera status: connected, reconnecting, disconnected, or None."""
        self._camera_status = status

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
            logger.info(f"[EMOTION_CHANGE] {prev} → {emotion}")
            self._particles = []  # Clear old particles on emotion change
            self._spawn_emotion_particles(emotion)
            self._trigger_emotion_flash(emotion)
            self._emotion_badge_pop_time = time.time()

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
        if thinking:
            self._thinking_start = time.time()
        else:
            self._thinking_start = 0

    def _draw_thinking_indicator(self):
        """Draw bouncing dots indicator (like iMessage typing) while waiting for response."""
        self._thinking_dots = (self._thinking_dots + 1) % 60

        # Pill-shaped container positioned below the banner
        pill_w, pill_h = 90, 36
        pill_x = WINDOW_WIDTH // 2 - pill_w // 2
        pill_y = getattr(self, '_banner_bottom', 48) + 14

        # Drop shadow
        shadow = pygame.Surface((pill_w + 4, pill_h + 4), pygame.SRCALPHA)
        pygame.draw.rect(shadow, (0, 0, 0, 50),
                         (0, 0, pill_w + 4, pill_h + 4), border_radius=pill_h // 2)
        self._screen.blit(shadow, (pill_x + 2, pill_y + 2))

        # Pill background (dark, glassy)
        pygame.draw.rect(self._screen, (45, 45, 65),
                         (pill_x, pill_y, pill_w, pill_h), border_radius=pill_h // 2)
        # Inner highlight
        highlight = pygame.Surface((pill_w - 8, 2), pygame.SRCALPHA)
        highlight.fill((255, 255, 255, 40))
        self._screen.blit(highlight, (pill_x + 4, pill_y + 3))
        # Border
        pygame.draw.rect(self._screen, (80, 80, 110),
                         (pill_x, pill_y, pill_w, pill_h), 2, border_radius=pill_h // 2)

        # Three bouncing dots with staggered timing
        for i in range(3):
            phase = (self._thinking_dots + i * 12) % 60
            bounce = math.sin(phase * math.pi / 30) * 7 if phase < 30 else 0
            dot_x = pill_x + 24 + i * 18
            dot_y = pill_y + pill_h // 2 - int(bounce)
            brightness = 160 + int(95 * max(0, bounce / 7))
            color = (brightness, brightness, min(255, brightness + 30))
            pygame.draw.circle(self._screen, color, (dot_x, dot_y), 5)

    def set_countdown(self, countdown_text: str):
        """Show countdown overlay with large centered text."""
        if not hasattr(self, '_countdown_text'):
            self._countdown_text = None
        self._countdown_text = countdown_text
        if DEBUG_DISPLAY:
            logger.info(f"[DEBUG_DISPLAY] set_countdown: {countdown_text}")

    def clear_countdown(self):
        """Clear countdown overlay."""
        if hasattr(self, '_countdown_text'):
            self._countdown_text = None

    def clear_memorial_overlay(self):
        """Clear memorial overlay."""
        self._memorial_active = False
        if hasattr(self, '_countdown_text'):
            self._countdown_text = None

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

    def _get_typewriter_speed(self, text_length: int) -> float:
        """Adaptive speed: short text = slower (savor), long text = faster (don't bore).
        Used as fallback when audio sync is not available."""
        if text_length < 20:
            return 1
        elif text_length < 60:
            return 2
        elif text_length < 120:
            return 3
        else:
            return 4

    def _update_typewriter(self):
        """Advance typewriter text effect."""
        if self._typewriter_text and self._typewriter_pos < len(self._typewriter_text):
            if self._typewriter_audio_synced:
                speed = self._typewriter_speed
            else:
                speed = self._get_typewriter_speed(len(self._typewriter_text))
            self._typewriter_pos = min(
                self._typewriter_pos + speed,
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

    def _resolve_sprite_value(self, value):
        """Resolve a sprite map value that may be a string or list.

        For lists, picks a random loaded sprite. Falls back to first entry if none loaded.
        For strings, returns as-is.
        """
        if isinstance(value, list):
            # Prefer sprites that are actually loaded
            loaded = [s for s in value if s in self._sprites]
            if loaded:
                return random.choice(loaded)
            return value[0]
        return value

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
            # Cycle through all available dance sprites
            cycle = (self._frame // 8) % len(sprites)
            return sprites[cycle]
        elif self.state in (STATE_GREETING, STATE_THINKING, STATE_SLEEPING, STATE_ENTERING, STATE_EXITING):
            val = STATE_SPRITE_MAP.get(self.state, "neutral/idle")
            return self._resolve_sprite_value(val)
        elif self.state in (STATE_LISTENING, STATE_IDLE):
            emo_val = EMOTION_SPRITE_MAP.get(self._emotion)
            emo_sprite = self._resolve_sprite_value(emo_val) if emo_val else None
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
            emo_val = EMOTION_SPRITE_MAP.get(self._emotion)
            emo_sprite = self._resolve_sprite_value(emo_val) if emo_val else None
            if emo_sprite and emo_sprite in self._sprites:
                return emo_sprite
            return "idle"
        else:
            # Idle — use emotion-based sprite
            emo_val = EMOTION_SPRITE_MAP.get(self._emotion)
            emo_sprite = self._resolve_sprite_value(emo_val) if emo_val else None
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
            
            # Use image background if available and selected
            if (self._current_bg_index >= 0 and 
                self._current_bg_index < len(self._backgrounds)):
                bg_img = self._backgrounds[self._current_bg_index]['image']
                self._bg_surface.blit(bg_img, (0, 0))
            else:
                # Draw the original bathroom scene
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
    # FULLSCREEN, PANIC, RECONNECT
    # ==========================================

    def _toggle_fullscreen(self):
        """Toggle between fullscreen and windowed mode with native resolution scaling."""
        try:
            self._fullscreen = not self._fullscreen
            if self._fullscreen:
                # Get desktop resolution BEFORE switching to fullscreen
                # pygame.display.get_desktop_sizes() returns [(w,h)] for each display
                try:
                    desktop_sizes = pygame.display.get_desktop_sizes()
                    desk_w, desk_h = desktop_sizes[0]
                except (AttributeError, IndexError):
                    # Fallback for older pygame: use display.Info() before set_mode
                    info = pygame.display.Info()
                    desk_w, desk_h = info.current_w, info.current_h
                # Ensure render buffer exists before switching
                if not hasattr(self, '_render_buffer') or self._render_buffer is None:
                    self._render_buffer = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT))
                self._screen = pygame.display.set_mode(
                    (desk_w, desk_h), pygame.FULLSCREEN
                )
                scale = min(desk_w / WINDOW_WIDTH, desk_h / WINDOW_HEIGHT)
                self._render_w = int(WINDOW_WIDTH * scale)
                self._render_h = int(WINDOW_HEIGHT * scale)
                self._fs_scale = scale
                self._display_scale = scale
                self._native_width = desk_w
                self._native_height = desk_h
                if DEBUG_DISPLAY:
                    logger.info(f"[DEBUG_DISPLAY] Fullscreen ON: {desk_w}x{desk_h}, scale={scale:.2f}")
            else:
                self._screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.RESIZABLE)
                self._render_buffer = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT))
                self._render_w = WINDOW_WIDTH
                self._render_h = WINDOW_HEIGHT
                self._fs_scale = 1.0
                self._display_scale = 1.0
                self._native_width = WINDOW_WIDTH
                self._native_height = WINDOW_HEIGHT
                self._windowed_scaled = False
                if DEBUG_DISPLAY:
                    logger.info("[DEBUG_DISPLAY] Fullscreen OFF: windowed 800x600")
        except Exception as e:
            logger.error(f"[DEBUG_DISPLAY] Fullscreen toggle failed: {e}")
            # Revert to safe windowed mode
            try:
                self._fullscreen = False
                self._windowed_scaled = False
                self._screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.RESIZABLE)
                self._render_buffer = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT))
                self._render_w = WINDOW_WIDTH
                self._render_h = WINDOW_HEIGHT
                self._fs_scale = 1.0
                self._display_scale = 1.0
            except Exception:
                pass
        # Invalidate cached background so it redraws at new size
        self._bg_surface = None

    def _handle_window_resize(self, new_w: int, new_h: int):
        """Handle window resize/maximize — scale render buffer to fit."""
        try:
            # Clamp minimum size
            new_w = max(new_w, 400)
            new_h = max(new_h, 300)
            self._screen = pygame.display.set_mode((new_w, new_h), pygame.RESIZABLE)
            if not hasattr(self, '_render_buffer') or self._render_buffer is None:
                self._render_buffer = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT))
            scale = min(new_w / WINDOW_WIDTH, new_h / WINDOW_HEIGHT)
            self._render_w = int(WINDOW_WIDTH * scale)
            self._render_h = int(WINDOW_HEIGHT * scale)
            self._display_scale = scale
            self._native_width = new_w
            self._native_height = new_h
            self._windowed_scaled = (new_w != WINDOW_WIDTH or new_h != WINDOW_HEIGHT)
            self._bg_surface = None  # Invalidate background cache
            if DEBUG_DISPLAY:
                logger.info(f"[DEBUG_DISPLAY] Window resized: {new_w}x{new_h}, scale={scale:.2f}")
        except Exception as e:
            logger.error(f"[DEBUG_DISPLAY] Window resize failed: {e}")

    def _draw_help_overlay(self):
        """Draw keyboard shortcuts help overlay (F1 toggle)."""
        w = self._screen.get_width()
        h = self._screen.get_height()

        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 200))
        self._screen.blit(overlay, (0, 0))

        shortcuts = [
            ("TAB", "Toggle keyboard input mode"),
            ("1-0", "Quick-trigger game phrases"),
            ("F1", "Toggle this help overlay"),
            ("F3", "Toggle chat history sidebar"),
            ("F4", "Toggle server health panel"),
            ("F5", "Toggle party mode effects"),
            ("F6", "Toggle leaderboard"),
            ("F7", "Cycle background image"),
            ("F8", "Toggle background auto-cycle"),
            ("F11", "Toggle fullscreen"),
            ("F12", "Toggle panic mode"),
            ("ESC", "Exit keyboard / close window"),
            ("Ctrl+V", "Paste from clipboard"),
            ("Ctrl+Bksp", "Delete last word"),
            ("Ctrl+U", "Clear input line"),
            ("Ctrl+Shift+L", "Skip memorial event"),
        ]

        title_font = pygame.font.Font(None, 48)
        key_font = pygame.font.Font(None, 28)
        desc_font = pygame.font.Font(None, 26)

        title = title_font.render("Keyboard Shortcuts", True, (255, 215, 0))
        self._screen.blit(title, (w // 2 - title.get_width() // 2, 60))

        start_y = 120
        col_w = 380
        mid_x = w // 2

        for i, (key, desc) in enumerate(shortcuts):
            col = i // 8
            row = i % 8
            x_base = mid_x - col_w + col * col_w
            y = start_y + row * 36

            key_surf = key_font.render(key, True, (100, 255, 100))
            desc_surf = desc_font.render(desc, True, (200, 200, 220))

            # Key badge
            badge_w = key_surf.get_width() + 16
            badge_h = 28
            badge_x = x_base
            badge_y = y
            pygame.draw.rect(self._screen, (40, 40, 60),
                             (badge_x, badge_y, badge_w, badge_h), border_radius=6)
            pygame.draw.rect(self._screen, (80, 80, 100),
                             (badge_x, badge_y, badge_w, badge_h), 1, border_radius=6)
            self._screen.blit(key_surf, (badge_x + 8, badge_y + 4))
            self._screen.blit(desc_surf, (badge_x + badge_w + 10, badge_y + 4))

        hint_font = pygame.font.Font(None, 22)
        hint = hint_font.render("Press F1 to close", True, (120, 120, 150))
        self._screen.blit(hint, (w // 2 - hint.get_width() // 2, h - 40))

    def _toggle_panic_mode(self):
        """Toggle panic mode — mute audio and show 'Technical Difficulties' screen."""
        self._panic_mode = not self._panic_mode
        try:
            if self._panic_mode:
                pygame.mixer.pause()
                if DEBUG_DISPLAY:
                    logger.info("[DEBUG_DISPLAY] PANIC MODE ON — audio paused, showing technical difficulties")
            else:
                pygame.mixer.unpause()
                if DEBUG_DISPLAY:
                    logger.info("[DEBUG_DISPLAY] PANIC MODE OFF — audio resumed")
        except Exception as e:
            logger.warning(f"[DEBUG_DISPLAY] Mixer pause/unpause error (no mixer?): {e}")

    def next_background(self):
        """Cycle to the next background (drawn -> bg1 -> bg2 -> ... -> drawn)."""
        if not self._backgrounds:
            if DEBUG_DISPLAY:
                logger.info("[DEBUG_DISPLAY] No background images available")
            return
        
        self._current_bg_index = (self._current_bg_index + 1) % (len(self._backgrounds) + 1)
        # -1=drawn, 0=first bg, 1=second bg, etc.
        if self._current_bg_index == len(self._backgrounds):
            self._current_bg_index = -1  # back to drawn background
        
        # Invalidate cached background so it redraws
        self._bg_surface = None
        
        if self._current_bg_index == -1:
            bg_name = "drawn bathroom"
        else:
            bg_name = self._backgrounds[self._current_bg_index]['name']
        
        if DEBUG_DISPLAY:
            logger.info(f"[DEBUG_DISPLAY] Switched to background: {bg_name}")

    def _draw_panic_overlay(self):
        """Draw 'Technical Difficulties' full-screen overlay when panic mode is active."""
        w = self._screen.get_width()
        h = self._screen.get_height()

        # Dark background
        overlay = pygame.Surface((w, h))
        overlay.fill((15, 15, 35))
        self._screen.blit(overlay, (0, 0))

        # Sleeping Mario sprite (if available)
        sleep_sprite = self._sprites.get("sleep/sleeping") or self._sprites.get("sleep/sleepy") or self._sprites.get("sleep")
        if sleep_sprite:
            sx = w // 2 - sleep_sprite.get_width() // 2
            sy = h // 2 - sleep_sprite.get_height() // 2 - 40
            # Gentle breathing bob
            bob = int(math.sin(time.time() * 1.5) * 4)
            self._screen.blit(sleep_sprite, (sx, sy + bob))

        # "Technical Difficulties" text
        big_font = pygame.font.Font(None, 52)
        sub_font = pygame.font.Font(None, 32)

        # Pulsing alpha for friendliness
        pulse = 0.7 + 0.3 * abs(math.sin(time.time() * 1.2))
        text_color = (int(255 * pulse), int(215 * pulse), int(0 * pulse + 80))

        line1 = big_font.render("Technical Difficulties", True, text_color)
        line2 = sub_font.render("Be Right Back!", True, (180, 180, 220))

        self._screen.blit(line1, (w // 2 - line1.get_width() // 2, h // 2 + 80))
        self._screen.blit(line2, (w // 2 - line2.get_width() // 2, h // 2 + 130))

        # Floating ZZZ animation
        zzz_font = pygame.font.Font(None, 36)
        for i in range(3):
            t = time.time() + i * 0.5
            zx = w // 2 + 80 + int(math.sin(t * 0.8) * 20) + i * 25
            zy = h // 2 - 60 - i * 30 + int(math.sin(t * 1.2) * 8)
            z_alpha = max(80, int(200 - i * 50))
            z_surf = zzz_font.render("Z", True, (100, 100, 200))
            z_surf.set_alpha(z_alpha)
            self._screen.blit(z_surf, (zx, zy))



    def draw_countdown_overlay(self, text: str):
        """Draw large centered countdown number with black outline."""
        if not text:
            return
            
        try:
            # Try to get Impact font, fallback to default
            try:
                countdown_font = pygame.font.SysFont("Impact", 180)
            except Exception:
                countdown_font = pygame.font.Font(None, 180)
                
            # Render the text with black outline
            # First render black outline (multiple times for thickness)
            outline_color = (0, 0, 0)
            text_color = (255, 255, 255)
            
            # Create surfaces for outline (render text slightly offset in all directions)
            outline_surfaces = []
            for dx in [-3, -2, -1, 0, 1, 2, 3]:
                for dy in [-3, -2, -1, 0, 1, 2, 3]:
                    if dx != 0 or dy != 0:  # Skip center (0,0)
                        surf = countdown_font.render(text, True, outline_color)
                        outline_surfaces.append((surf, dx, dy))
            
            # Render main text
            text_surf = countdown_font.render(text, True, text_color)
            
            # Calculate center position
            w = self._screen.get_width()
            h = self._screen.get_height()
            center_x = w // 2 - text_surf.get_width() // 2
            center_y = h // 2 - text_surf.get_height() // 2
            
            # Draw outline first
            for surf, dx, dy in outline_surfaces:
                self._screen.blit(surf, (center_x + dx, center_y + dy))
                
            # Draw main text on top
            self._screen.blit(text_surf, (center_x, center_y))
            
        except Exception as e:
            logger.error(f"Error drawing countdown overlay: {e}")

    def _draw_reconnect_overlay(self):
        """Draw reconnection UI when WebSocket is disconnected."""
        w = self._screen.get_width()
        h = self._screen.get_height()

        # Semi-transparent overlay
        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        overlay.fill((10, 10, 30, 180))
        self._screen.blit(overlay, (0, 0))

        # Idle animation of Mario (if available)
        idle_sprite = self._sprites.get("neutral/idle") or self._sprites.get("idle")
        if idle_sprite:
            bob = int(math.sin(time.time() * 2.0) * 6)
            sx = w // 2 - idle_sprite.get_width() // 2
            sy = h // 2 - idle_sprite.get_height() // 2 - 50 + bob
            self._screen.blit(idle_sprite, (sx, sy))

        # Friendly message
        big_font = pygame.font.Font(None, 40)
        sub_font = pygame.font.Font(None, 28)

        msg = big_font.render("Mario is taking a bathroom break...", True, (255, 215, 0))
        msg2 = sub_font.render("be right back!", True, (180, 220, 255))
        self._screen.blit(msg, (w // 2 - msg.get_width() // 2, h // 2 + 60))
        self._screen.blit(msg2, (w // 2 - msg2.get_width() // 2, h // 2 + 100))

        # Reconnection status from ws_client
        reconnect_info = self._reconnect_info
        if reconnect_info and reconnect_info.get("attempting"):
            attempt = reconnect_info.get("attempt", 0)
            max_att = reconnect_info.get("max_attempts", 20)
            delay = reconnect_info.get("delay", 0)
            started = reconnect_info.get("started", 0)

            # Countdown timer
            if started > 0 and delay > 0:
                elapsed = time.time() - started
                remaining = max(0, delay - elapsed)
                countdown_text = f"Reconnecting in {remaining:.0f}s..."
            else:
                countdown_text = "Reconnecting..."

            attempt_text = f"Attempt {attempt} / {max_att}"

            # Pulsing dots animation
            dots = "." * ((int(time.time() * 2) % 3) + 1)

            ct_surf = sub_font.render(f"{countdown_text}{dots}", True, (255, 180, 80))
            at_surf = self._font_small.render(attempt_text, True, (150, 150, 180))
            self._screen.blit(ct_surf, (w // 2 - ct_surf.get_width() // 2, h // 2 + 140))
            self._screen.blit(at_surf, (w // 2 - at_surf.get_width() // 2, h // 2 + 170))

            # Progress bar
            bar_w = 300
            bar_h = 8
            bar_x = w // 2 - bar_w // 2
            bar_y = h // 2 + 195
            pygame.draw.rect(self._screen, (40, 40, 60), (bar_x, bar_y, bar_w, bar_h), border_radius=4)
            if started > 0 and delay > 0:
                fill = min(1.0, (time.time() - started) / delay)
                fill_w = int(bar_w * fill)
                if fill_w > 0:
                    pygame.draw.rect(self._screen, (100, 200, 255), (bar_x, bar_y, fill_w, bar_h), border_radius=4)

    # ==========================================
    # MAIN DRAW
    # ==========================================

    def _draw(self):
        """Draw the full frame. Uses render buffer for fullscreen/resized scaling."""
        # Panic mode: draw directly to real screen (full-res friendly text)
        if self._panic_mode:
            self._draw_panic_overlay()
            pygame.display.flip()
            return

        # When scaled (fullscreen or resized window), redirect drawing to 800x600 render buffer
        needs_scaling = self._fullscreen or self._windowed_scaled
        real_screen = self._screen
        if needs_scaling:
            self._screen = self._render_buffer

        # Background scene instead of flat fill
        self._draw_background()

        # Two-strip header (title bar + info strip — all HUD in one place)
        self._draw_party_banner(self._screen)

        self._update_particles()
        self._emotion_timer += 1

        # Draw Mario sprite
        self._draw_mario()

        # Emotion flash overlay (on Mario area)
        self._draw_emotion_flash()

        # Floating emotion badge near Mario
        self._draw_emotion_badge()
        self._draw_mood_bar()

        # Draw particles on top of Mario
        self._draw_particles()

        # Draw speech bubble with typewriter (keep visible while speaking, then auto-clear after 8s)
        if self.current_text:
            if self._speaking:
                # Reset timer while still speaking so bubble stays visible
                self._text_display_time = self._frame
            if self._frame - self._text_display_time > 480:
                self.current_text = ""
            else:
                self._draw_speech_bubble(self.current_text)
        elif self._thinking:
            self._draw_thinking_indicator()

        # Draw subtitle (auto-clear after 5 seconds / 300 frames)
        if self.subtitle_text:
            if self._frame - self._subtitle_set_frame > 300:
                self.subtitle_text = ""
            else:
                self._draw_subtitle(self.subtitle_text)

        # Draw keyboard input area
        if self.keyboard_mode:
            self._draw_keyboard_input()

        # Minimal bottom bar — connection dot + compact hints
        bottom_bar = pygame.Surface((WINDOW_WIDTH, 22), pygame.SRCALPHA)
        bottom_bar.fill((0, 0, 0, 100))
        self._screen.blit(bottom_bar, (0, WINDOW_HEIGHT - 22))

        # Connection dot (left)
        conn_color = (50, 200, 50) if self.connected else (200, 50, 50)
        pygame.draw.circle(self._screen, conn_color, (10, WINDOW_HEIGHT - 11), 4)

        # Active mode indicators (compact, left side)
        mode_parts = []
        if self.keyboard_mode:
            mode_parts.append("⌨ Typing")
        if self.party_mode:
            mode_parts.append("🎉 Party")
        if mode_parts:
            mode_text = " | ".join(mode_parts)
            mode_surf = self._font_small.render(mode_text, True, (180, 180, 200))
            self._screen.blit(mode_surf, (22, WINDOW_HEIGHT - 18))

        # Compact hint (right side, dimmed)
        hint = "F1:help | TAB:type | 1-0:games | F3:chat | F4:health | F6:board | F11:full | F12:panic"
        hint_surf = self._font_small.render(hint, True, (70, 70, 90))
        self._screen.blit(hint_surf, (WINDOW_WIDTH - hint_surf.get_width() - 8, WINDOW_HEIGHT - 18))

        # Volume overlay (fades out after ~2 seconds)
        self._draw_volume_overlay()

        # Leaderboard overlay (F6 toggle)
        self._draw_leaderboard()

        # Health overlay (F4 toggle)
        self._draw_health_overlay()

        # Screen edge glow for emotion changes
        self._draw_edge_glow()

        # Connection status overlay (below party banner)
        if self._connection_status:
            try:
                status_font = self._font_small or pygame.font.SysFont("arial", 14)
                status_surface = status_font.render(self._connection_status, True, (255, 80, 80))
                self._screen.blit(status_surface, (10, getattr(self, '_banner_bottom', 48) + 4))
            except Exception:
                pass

        # Camera status indicator (top-right corner, below banner)
        if self._camera_status and self._camera_status != "connected":
            try:
                cam_font = self._font_small or pygame.font.SysFont("arial", 14)
                if self._camera_status == "reconnecting":
                    cam_text = "📷 Camera reconnecting..."
                    cam_color = (255, 200, 50)
                else:
                    cam_text = "📷 No camera"
                    cam_color = (255, 80, 80)
                cam_surface = cam_font.render(cam_text, True, cam_color)
                cam_x = self._screen.get_width() - cam_surface.get_width() - 10
                self._screen.blit(cam_surface, (cam_x, getattr(self, '_banner_bottom', 48) + 4))
            except Exception:
                pass

        # Reconnect overlay (drawn on top of everything when disconnected)
        if not self.connected and self._reconnect_info:
            self._draw_reconnect_overlay()

        # Chat history sidebar (F3 toggle)
        self._draw_chat_history(self._screen)

        # Memorial overlay (drawn on top of everything)
        if self._memorial_active:
            self._draw_memorial(self._screen)
        
        # Countdown overlay (drawn on top of memorial)
        if hasattr(self, '_countdown_text') and self._countdown_text:
            self.draw_countdown_overlay(self._countdown_text)
        
        # Closed captions (drawn last, on top of everything except fullscreen scaling)
        if self.captions:
            self.captions.draw(self._screen)

        # Help overlay (F1 toggle — on top of everything)
        if self._show_help:
            self._draw_help_overlay()

        # Scale render buffer to real screen, centered with aspect ratio
        if needs_scaling:
            self._screen = real_screen
            scaled = pygame.transform.smoothscale(self._render_buffer,
                                                  (self._render_w, self._render_h))
            x_off = (self._native_width - self._render_w) // 2
            y_off = (self._native_height - self._render_h) // 2
            if x_off > 0 or y_off > 0:
                self._screen.fill(BG_COLOR)
                # Draw extended floor strip into letterbox bars so they blend
                floor_h = int(self._render_h * 0.12)
                floor_y = y_off + self._render_h - floor_h
                pygame.draw.rect(self._screen, (60, 40, 25),
                                 (0, floor_y, self._native_width, floor_h))
            self._screen.blit(scaled, (x_off, y_off))

        pygame.display.flip()

    def _draw_party_banner(self, surface):
        """Draw two-strip header: title bar (Y=0-28) + info strip (Y=28-48).
        
        Exposes self._banner_bottom so other elements can position below it.
        """
        try:
            w = surface.get_width()
            font = self._font_small or pygame.font.SysFont("arial", 14)

            # === ZONE 1: Title Bar (Y=0-28) ===
            title_h = 28
            title_bar = pygame.Surface((w, title_h), pygame.SRCALPHA)
            title_bar.fill((20, 10, 40, 230))
            surface.blit(title_bar, (0, 0))

            # Centered title
            title_surf = self._font_title.render("It's-a Me, Mario!", True, (255, 215, 0))
            title_x = w // 2 - title_surf.get_width() // 2
            title_y = (title_h - title_surf.get_height()) // 2
            surface.blit(title_surf, (title_x, title_y))

            # Gold accent line at bottom of title bar
            accent = pygame.Surface((w, 1), pygame.SRCALPHA)
            accent.fill((255, 215, 0, 64))
            surface.blit(accent, (0, title_h - 1))

            # === ZONE 2: Info Strip (Y=28-48) ===
            info_h = 20
            info_y = title_h
            info_bar = pygame.Surface((w, info_h), pygame.SRCALPHA)
            info_bar.fill((10, 5, 30, 200))
            surface.blit(info_bar, (0, info_y))
            self._banner_bottom = info_y + info_h  # expose for speech bubble

            sep_color = (255, 255, 255, 40)
            text_y = info_y + (info_h - font.get_height()) // 2

            # --- Left side: party name | mood ---
            name_surf = font.render(self._party_name, True, (255, 215, 0))
            x = 10
            surface.blit(name_surf, (x, text_y))
            x += name_surf.get_width() + 6
            left_max = x  # track how far left items go

            sep_surf = font.render("|", True, sep_color)

            # Mood is now shown via the floating emotion badge — not in the strip

            # --- Right side (drawn right-to-left) ---
            rx = w - 10

            # Connection status
            if self.connected:
                conn_text = "●"
                conn_color = (0, 255, 0)
            else:
                reconnect_info = self._reconnect_info
                if reconnect_info and reconnect_info.get("attempting"):
                    attempt = reconnect_info.get("attempt", 0)
                    max_att = reconnect_info.get("max_attempts", 0)
                    conn_text = f"Reconn ({attempt}/{max_att})"
                    pulse = abs(math.sin(self._frame * 0.08))
                    conn_color = (255, int(165 * pulse), 0)
                else:
                    conn_text = "● Disconnected"
                    conn_color = (255, 0, 0)
            conn_surf = font.render(conn_text, True, conn_color)
            rx -= conn_surf.get_width()
            surface.blit(conn_surf, (rx, text_y))

            rx -= 6
            surface.blit(sep_surf, (rx - sep_surf.get_width(), text_y))
            rx -= sep_surf.get_width() + 6

            # Duration
            elapsed = time.time() - self._party_start_time
            hours = int(elapsed // 3600)
            mins = int((elapsed % 3600) // 60)
            dur_text = f"{hours}h {mins}m" if hours > 0 else f"{mins}m"
            dur_surf = font.render(dur_text, True, (180, 180, 255))
            if rx - dur_surf.get_width() > left_max + 20:
                rx -= dur_surf.get_width()
                surface.blit(dur_surf, (rx, text_y))

                # Guest/visitor count
                count = self._guest_count if self._guest_count > 0 else self._visitor_count
                if count > 0:
                    rx -= 6
                    surface.blit(sep_surf, (rx - sep_surf.get_width(), text_y))
                    rx -= sep_surf.get_width() + 6
                    count_surf = font.render(f"👥{count}", True, (100, 255, 100))
                    if rx - count_surf.get_width() > left_max + 20:
                        rx -= count_surf.get_width()
                        surface.blit(count_surf, (rx, text_y))

            # Game indicator (show when active game is running)
            if self._health_data and self._health_data.get("active_games", 0) > 0:
                rx -= 6
                surface.blit(sep_surf, (rx - sep_surf.get_width(), text_y))
                rx -= sep_surf.get_width() + 6
                pulse = abs(math.sin(self._frame * 0.1))
                game_color = (int(255 * (0.6 + 0.4 * pulse)), 255, 100)
                game_surf = font.render("GAME", True, game_color)
                if rx - game_surf.get_width() > left_max + 20:
                    rx -= game_surf.get_width()
                    surface.blit(game_surf, (rx, text_y))

            # Speaking indicator (only if room)
            if self._speaking and rx > left_max + 80:
                pulse = abs(math.sin(self._frame * 0.1)) * 255
                speak_surf = font.render("🔊", True, (int(pulse), 200, int(pulse)))
                rx -= 6
                surface.blit(sep_surf, (rx - sep_surf.get_width(), text_y))
                rx -= sep_surf.get_width() + 6 + speak_surf.get_width()
                surface.blit(speak_surf, (rx, text_y))

        except Exception:
            pass  # Never crash the display for a banner

    def _draw_chat_history(self, surface):
        """Draw scrollable chat log on right side."""
        if not self._show_chat_history or not self._chat_history or not self._font_small:
            return
        panel_w = 280
        panel_x = surface.get_width() - panel_w - 10
        panel_y = getattr(self, '_banner_bottom', 48) + 4
        panel_h = surface.get_height() - 120
        # Semi-transparent background
        try:
            overlay = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 180))
            surface.blit(overlay, (panel_x, panel_y))
        except Exception:
            return
        # Title
        title_font = self._chat_title_font or pygame.font.SysFont("arial", 16, bold=True)
        title = title_font.render("Chat History (F3)", True, (255, 215, 0))
        surface.blit(title, (panel_x + 10, panel_y + 5))
        # Messages (newest at bottom)
        msg_font = self._chat_msg_font or pygame.font.SysFont("arial", 13)
        y_offset = panel_y + 30
        from datetime import datetime as _dt
        for msg in self._chat_history[-12:]:  # Show last 12
            color = (144, 238, 144) if msg["role"] == "mario" else (173, 216, 230)
            prefix = "M:" if msg["role"] == "mario" else "U:"
            ts = msg.get("time")
            ts_str = _dt.fromtimestamp(ts).strftime("%H:%M") if ts else ""
            text = f"{ts_str} {prefix} {msg['text'][:40]}{'...' if len(msg['text']) > 40 else ''}"
            rendered = msg_font.render(text, True, color)
            surface.blit(rendered, (panel_x + 10, y_offset))
            y_offset += 22

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

    def _draw_emotion_badge(self):
        """Draw a floating emotion badge in the top-left corner showing current mood."""
        if not self._emotion:
            return

        now = time.time()
        symbol = EMOTION_EMOJI.get(self._emotion, "—")
        color = EMOTION_BADGE_COLORS.get(self._emotion, (180, 180, 180))
        label_text = self._emotion.capitalize()

        # Position: top-left corner below the banner
        banner_bot = getattr(self, '_banner_bottom', 48)
        badge_x = 12
        badge_y = banner_bot + 8

        # Gentle float animation
        float_offset = math.sin(now * 2.0) * 4
        badge_y += int(float_offset)

        # Pop animation on emotion change (scale 1.4 → 1.0 over 0.3s)
        pop_elapsed = now - self._emotion_badge_pop_time
        if pop_elapsed < 0.3:
            scale = 1.0 + 0.4 * (1.0 - pop_elapsed / 0.3)
        else:
            scale = 1.0

        # Render text to measure size
        font = self._bubble_fonts.get(16, self._font_small)
        sym_font = self._bubble_fonts.get(18, self._font)
        sym_surf = sym_font.render(symbol, True, (50, 50, 50))
        label_surf = font.render(f" {label_text}", True, (40, 40, 40))

        badge_w = sym_surf.get_width() + label_surf.get_width() + 18
        badge_h = max(sym_surf.get_height(), label_surf.get_height()) + 12

        # Apply pop scale
        if scale != 1.0:
            scaled_w = int(badge_w * scale)
            scaled_h = int(badge_h * scale)
            badge_x -= (scaled_w - badge_w) // 2
            badge_y -= (scaled_h - badge_h) // 2
            badge_w = scaled_w
            badge_h = scaled_h

        # Shadow
        shadow = pygame.Surface((badge_w + 4, badge_h + 4), pygame.SRCALPHA)
        pygame.draw.rect(shadow, (0, 0, 0, 45),
                         (0, 0, badge_w + 4, badge_h + 4), border_radius=badge_h // 2)
        self._screen.blit(shadow, (badge_x + 2, badge_y + 2))

        # Background pill with emotion color
        bg_r, bg_g, bg_b = color
        pygame.draw.rect(self._screen, (bg_r, bg_g, bg_b),
                         (badge_x, badge_y, badge_w, badge_h), border_radius=badge_h // 2)
        # Highlight strip at top
        hl = pygame.Surface((badge_w - 10, 2), pygame.SRCALPHA)
        hl.fill((255, 255, 255, 70))
        self._screen.blit(hl, (badge_x + 5, badge_y + 3))
        # Border
        br = (min(255, bg_r + 40), min(255, bg_g + 40), min(255, bg_b + 40))
        pygame.draw.rect(self._screen, br,
                         (badge_x, badge_y, badge_w, badge_h), 2, border_radius=badge_h // 2)

        # Symbol + label (re-render at scaled size if popping)
        if scale != 1.0:
            s_font = self._bubble_fonts.get(min(28, int(18 * scale)), sym_font)
            l_font = self._bubble_fonts.get(min(28, int(16 * scale)), font)
            sym_surf = s_font.render(symbol, True, (50, 50, 50))
            label_surf = l_font.render(f" {label_text}", True, (40, 40, 40))

        content_w = sym_surf.get_width() + label_surf.get_width()
        cx = badge_x + (badge_w - content_w) // 2
        cy_sym = badge_y + (badge_h - sym_surf.get_height()) // 2
        cy_lbl = badge_y + (badge_h - label_surf.get_height()) // 2
        self._screen.blit(sym_surf, (cx, cy_sym))
        self._screen.blit(label_surf, (cx + sym_surf.get_width(), cy_lbl))

    def set_mood_score(self, score: float):
        """Set the rolling mood score (-1.0 to +1.0)."""
        self._mood_score = max(-1.0, min(1.0, score))

    def _draw_mood_bar(self):
        """Draw a horizontal mood meter below the emotion badge."""
        # Smoothly animate toward target
        diff = self._mood_score - self._mood_display
        self._mood_display += diff * 0.08  # Ease toward target

        banner_bot = getattr(self, '_banner_bottom', 48)
        bar_x = 12
        bar_y = banner_bot + 44  # Below emotion badge
        bar_w = 110
        bar_h = 10

        # Determine mood label
        val = self._mood_display
        if val > 0.5:
            label = "Vibing!"
        elif val > 0.2:
            label = "Happy"
        elif val > -0.2:
            label = "Neutral"
        elif val > -0.5:
            label = "Meh"
        else:
            label = "Grumpy"

        # Shadow
        shadow = pygame.Surface((bar_w + 4, bar_h + 4), pygame.SRCALPHA)
        pygame.draw.rect(shadow, (0, 0, 0, 40),
                         (0, 0, bar_w + 4, bar_h + 4), border_radius=bar_h // 2)
        self._screen.blit(shadow, (bar_x + 1, bar_y + 1))

        # Background (dark pill)
        pygame.draw.rect(self._screen, (40, 40, 55),
                         (bar_x, bar_y, bar_w, bar_h), border_radius=bar_h // 2)

        # Fill: map -1..+1 to 0..bar_w, color from red→yellow→green
        fill_frac = (self._mood_display + 1.0) / 2.0  # 0.0 to 1.0
        fill_w = max(4, int(bar_w * fill_frac))

        # Color gradient: red(0) → yellow(0.5) → green(1.0)
        if fill_frac < 0.5:
            t = fill_frac * 2.0
            r = int(220 * (1 - t) + 240 * t)
            g = int(60 * (1 - t) + 200 * t)
            b = int(60 * (1 - t) + 50 * t)
        else:
            t = (fill_frac - 0.5) * 2.0
            r = int(240 * (1 - t) + 80 * t)
            g = int(200 * (1 - t) + 220 * t)
            b = int(50 * (1 - t) + 80 * t)

        # Draw fill with clipping to rounded rect
        fill_surf = pygame.Surface((bar_w, bar_h), pygame.SRCALPHA)
        pygame.draw.rect(fill_surf, (r, g, b), (0, 0, fill_w, bar_h), border_radius=bar_h // 2)
        self._screen.blit(fill_surf, (bar_x, bar_y))

        # Border
        pygame.draw.rect(self._screen, (80, 80, 100),
                         (bar_x, bar_y, bar_w, bar_h), 1, border_radius=bar_h // 2)

        # Label to the right of bar
        font = self._bubble_fonts.get(12, self._font_small)
        lbl_surf = font.render(label, True, (200, 200, 220))
        self._screen.blit(lbl_surf, (bar_x + bar_w + 6, bar_y - 1))

    def _wrap_text_for_bubble(self, text: str, font, max_width: int) -> list[str]:
        """Wrap text to fit within max_width using given font."""
        words = text.split()
        lines = []
        current_line = ""
        for word in words:
            if font.size(word)[0] > max_width:
                if current_line:
                    lines.append(current_line)
                    current_line = ""
                for char in word:
                    test = current_line + char
                    if font.size(test)[0] > max_width:
                        lines.append(current_line)
                        current_line = char
                    else:
                        current_line = test
                continue
            test = current_line + " " + word if current_line else word
            if font.size(test)[0] > max_width:
                if current_line:
                    lines.append(current_line)
                current_line = word
            else:
                current_line = test
        if current_line:
            lines.append(current_line)
        return lines

    def _build_text_pages(self, all_lines: list[str], max_lines_per_page: int,
                          full_text: str, font, max_width: int):
        """Split wrapped lines into pages.
        
        Pages are simply chunks of max_lines_per_page from the full-text wrap.
        The typewriter determines which page to show based on visible line count.
        """
        self._text_pages = []
        self._text_page_char_ranges = []  # Not used — kept for compatibility

        # Split lines into page-sized chunks
        for i in range(0, len(all_lines), max_lines_per_page):
            page_lines = all_lines[i:i + max_lines_per_page]
            self._text_pages.append(page_lines)
            self._text_page_char_ranges.append((i, i + len(page_lines)))  # line ranges, not char ranges

    def _draw_speech_bubble(self, text: str):
        """Draw Mario's speech bubble with page-based auto-advance.

        Pages auto-advance in sync with Mario's speech — no manual scrolling.
        Each page of text appears cleanly, typewriter reveals it, then when
        the typewriter reaches the end of the page it transitions to the next.
        """
        style = self._detect_bubble_style(self._typewriter_text)

        # Layout constants — shout style needs extra padding due to spiky shape
        if style == BUBBLE_STYLE_SHOUT:
            PAD_X = 35
            PAD_Y = 20
        else:
            PAD_X = 20
            PAD_Y = 15
        max_text_width = 380  # consistent text width for all styles
        bubble_w = max_text_width + PAD_X * 2  # shout gets wider to accommodate extra padding
        banner_bot = getattr(self, '_banner_bottom', 48)
        available_h = int(WINDOW_HEIGHT * 0.38) - banner_bot
        max_bubble_height = max(available_h, 120)
        min_font_size = 14
        max_font_size = 28

        layout_text = self._typewriter_text or text

        # Auto-shrink: find largest font where at least some text fits nicely
        best_font = None
        best_size = min_font_size
        best_line_height = 18
        layout_lines = []

        for size in range(max_font_size, min_font_size - 1, -2):
            font = self._bubble_fonts[size]
            line_h = font.get_linesize()
            lines = self._wrap_text_for_bubble(layout_text, font, max_text_width)
            total_h = len(lines) * line_h + PAD_Y * 2
            if total_h <= max_bubble_height:
                # All text fits on one page — use this font
                best_font = font
                best_size = size
                best_line_height = line_h
                layout_lines = lines
                break
            # If text is too long, use smallest readable font but paginate
            layout_lines = lines
            best_line_height = line_h

        if best_font is None:
            best_font = self._bubble_fonts[min_font_size]
            best_line_height = best_font.get_linesize()
            layout_lines = self._wrap_text_for_bubble(layout_text, best_font, max_text_width)

        if not layout_lines:
            return

        # Calculate max lines per page
        max_lines = max((max_bubble_height - PAD_Y * 2) // best_line_height, 2)

        # Build pages if not already built for this text
        if not self._text_pages or self._text_pages[0] is None:
            self._build_text_pages(layout_lines, max_lines, layout_text, best_font, max_text_width)

        # Determine current page by wrapping the VISIBLE text and counting lines
        # This ensures page transitions happen at natural word boundaries
        visible_text_so_far = text  # text param = typewriter portion
        visible_wrapped = self._wrap_text_for_bubble(visible_text_so_far, best_font, max_text_width)
        num_visible_lines = len(visible_wrapped)
        target_page = max(0, (num_visible_lines - 1) // max_lines) if num_visible_lines > 0 else 0

        # Handle page transitions
        if target_page != self._current_page:
            self._current_page = target_page
            self._page_transition_frame = self._frame
            self._page_transition_alpha = 0  # fade in

        # Fade-in effect for page transitions (10 frames = ~0.33s at 30fps)
        frames_since_transition = self._frame - self._page_transition_frame
        if frames_since_transition < 10:
            self._page_transition_alpha = min(255, int(255 * frames_since_transition / 10))
        else:
            self._page_transition_alpha = 255

        # Get current page lines from the visible wrapped text
        page_idx = min(self._current_page, len(self._text_pages) - 1)
        page_start_line = page_idx * max_lines
        page_end_line = page_start_line + max_lines
        # Show lines from the visible wrapped text that belong to current page
        visible_lines = visible_wrapped[page_start_line:page_end_line]

        # Bubble dimensions (stable — sized for max page content)
        display_lines = min(max_lines, max(len(p) for p in self._text_pages) if self._text_pages else len(visible_lines))
        bubble_h = display_lines * best_line_height + PAD_Y * 2 + 4  # +4 for descender buffer
        bubble_x = WINDOW_WIDTH // 2 - bubble_w // 2
        bubble_y = banner_bot + 6

        # Style-dependent colors (warm, polished palette)
        if style == BUBBLE_STYLE_SHOUT:
            bg_color = (255, 245, 215)
            border_color = (200, 60, 60)
            text_color = (160, 30, 30)
            border_width = 3
            shadow_alpha = 80
        elif style == BUBBLE_STYLE_QUESTION:
            bg_color = (230, 238, 255)
            border_color = (80, 120, 200)
            text_color = (30, 50, 130)
            border_width = 2
            shadow_alpha = 60
        elif style == BUBBLE_STYLE_WHISPER:
            bg_color = (235, 235, 240)
            border_color = (170, 170, 180)
            text_color = (100, 100, 110)
            border_width = 1
            shadow_alpha = 40
        else:
            bg_color = (255, 252, 245)
            border_color = (70, 70, 80)
            text_color = (30, 30, 35)
            border_width = 2
            shadow_alpha = 60

        # Drop shadow (matches bubble shape)
        if style == BUBBLE_STYLE_SHOUT:
            # Spiky shadow matching the shout polygon
            shadow_surf = pygame.Surface((bubble_w + 36, bubble_h + 36), pygame.SRCALPHA)
            cx_s = (bubble_w + 36) // 2
            cy_s = (bubble_h + 36) // 2
            shadow_pts = []
            num_spikes = 16
            for i in range(num_spikes * 2):
                angle = i * math.pi / num_spikes
                if i % 2 == 0:
                    rx = bubble_w // 2 + 15
                    ry = bubble_h // 2 + 15
                else:
                    rx = bubble_w // 2 + 5
                    ry = bubble_h // 2 + 5
                shadow_pts.append((
                    int(cx_s + rx * math.cos(angle)),
                    int(cy_s + ry * math.sin(angle))
                ))
            pygame.draw.polygon(shadow_surf, (0, 0, 0, shadow_alpha), shadow_pts)
            self._screen.blit(shadow_surf, (bubble_x - 15 + 3, bubble_y - 15 + 4))
        else:
            shadow_surf = pygame.Surface((bubble_w + 6, bubble_h + 6), pygame.SRCALPHA)
            pygame.draw.rect(shadow_surf, (0, 0, 0, shadow_alpha),
                             (0, 0, bubble_w + 6, bubble_h + 6), border_radius=16)
            self._screen.blit(shadow_surf, (bubble_x + 2, bubble_y + 3))

        # Spiky bubble for shouts (inner dips pushed outward to prevent text overlap)
        if style == BUBBLE_STYLE_SHOUT:
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
                    # Inner dips stay outside the text area (+5px margin)
                    rx = bubble_w // 2 + 5
                    ry = bubble_h // 2 + 5
                points.append((
                    int(cx_b + rx * math.cos(angle)),
                    int(cy_b + ry * math.sin(angle))
                ))
            pygame.draw.polygon(self._screen, bg_color, points)
            pygame.draw.polygon(self._screen, border_color, points, border_width)
        else:
            # Main bubble with rounded corners
            pygame.draw.rect(self._screen, bg_color,
                             (bubble_x, bubble_y, bubble_w, bubble_h), border_radius=16)
            # Inner highlight (top edge glow for depth)
            highlight = pygame.Surface((bubble_w - 8, 3), pygame.SRCALPHA)
            highlight.fill((255, 255, 255, 90))
            self._screen.blit(highlight, (bubble_x + 4, bubble_y + 3))
            # Border
            pygame.draw.rect(self._screen, border_color,
                             (bubble_x, bubble_y, bubble_w, bubble_h), border_width, border_radius=16)

        # Bubble pointer (tail)
        pointer_x = WINDOW_WIDTH // 2
        pointer_y = bubble_y + bubble_h
        if style == BUBBLE_STYLE_WHISPER:
            for i in range(3):
                pygame.draw.circle(self._screen, border_color,
                                   (pointer_x, pointer_y + 8 + i * 10), 4 - i)
        else:
            shadow_pts = [
                (pointer_x - 8, pointer_y + 2),
                (pointer_x + 12, pointer_y + 2),
                (pointer_x + 2, pointer_y + 22),
            ]
            pygame.draw.polygon(self._screen, (0, 0, 0, 30) if hasattr(pygame, 'SRCALPHA') else (40, 40, 40), shadow_pts)
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

        # Page indicator (small dots) — only show if multiple pages
        if len(self._text_pages) > 1:
            dot_y = bubble_y + bubble_h - 8
            dot_start_x = bubble_x + bubble_w - 12 - (len(self._text_pages) * 8)
            for i in range(len(self._text_pages)):
                dot_color = border_color if i == page_idx else (*border_color[:3], 80) if len(border_color) == 3 else border_color
                dot_x = dot_start_x + i * 8
                if i == page_idx:
                    pygame.draw.circle(self._screen, border_color, (dot_x, dot_y), 3)
                else:
                    pygame.draw.circle(self._screen, (*bg_color[:3],), (dot_x, dot_y), 3)
                    pygame.draw.circle(self._screen, border_color, (dot_x, dot_y), 3, 1)

        # Typewriter cursor state
        showing_cursor = (self._typewriter_pos < len(self._typewriter_text)
                          and (self._frame // 8) % 2 == 0)

        # Clip text rendering to bubble interior
        text_area = pygame.Rect(
            bubble_x + PAD_X, bubble_y + PAD_Y,
            max_text_width, bubble_h - PAD_Y * 2
        )
        prev_clip = self._screen.get_clip()
        self._screen.set_clip(text_area)

        # Render text with page transition fade
        text_x = text_area.x
        text_y_start = text_area.y
        for i, line in enumerate(visible_lines):
            if i >= max_lines:
                break
            text_surf = best_font.render(line, True, text_color)
            if self._page_transition_alpha < 255:
                text_surf.set_alpha(self._page_transition_alpha)
            self._screen.blit(text_surf, (text_x, text_y_start + i * best_line_height))

        # Blinking cursor at end of typewriter text
        if showing_cursor and visible_lines:
            last_line = visible_lines[-1]
            cursor_x = text_x + best_font.size(last_line)[0] + 2
            cursor_height = best_line_height - 4
            cursor_y = text_y_start + (len(visible_lines) - 1) * best_line_height + 2
            pygame.draw.rect(self._screen, text_color, (cursor_x, cursor_y, 2, cursor_height))

        # Restore previous clip
        self._screen.set_clip(prev_clip)

    def _draw_subtitle(self, text: str):
        """Draw subtitle text above the bottom bar (what the user said)."""
        subtitle_surf = self._font_small.render(f'You: "{text}"', True, (200, 200, 200))
        bg = pygame.Surface((subtitle_surf.get_width() + 20, subtitle_surf.get_height() + 10), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 140))
        x = WINDOW_WIDTH // 2 - subtitle_surf.get_width() // 2
        y = WINDOW_HEIGHT - 95  # above closed captions + status bar
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

        self._screen.blit(panel, (10, getattr(self, '_banner_bottom', 48) + 4))

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
            if text_w > input_w - 20:
                cursor_x = input_x + input_w - 10
            else:
                cursor_x = input_x + 10 + text_surf.get_width()
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

    def toggle_leaderboard(self):
        """Toggle the leaderboard overlay visibility."""
        self._leaderboard_visible = not self._leaderboard_visible
        if self._leaderboard_visible:
            self._leaderboard_show_frame = self._frame

    def _init_memorial_particles(self):
        """Initialize floating memorial particles (golden light dots)."""
        self._memorial_particles = []
        w, h = WINDOW_WIDTH, WINDOW_HEIGHT
        for _ in range(25):
            self._memorial_particles.append({
                "x": random.randint(0, w),
                "y": random.randint(0, h),
                "speed": random.uniform(0.3, 1.2),
                "alpha": random.randint(80, 200),
                "size": random.randint(2, 5),
                "drift": random.uniform(-0.3, 0.3),
            })

    def _update_memorial_particles(self):
        """Update particle positions — drift upward, wrap around."""
        for p in self._memorial_particles:
            p["y"] -= p["speed"]
            p["x"] += p["drift"]
            p["alpha"] = max(60, min(220, p["alpha"] + random.randint(-5, 5)))
            if p["y"] < -10:
                p["y"] = WINDOW_HEIGHT + 10
                p["x"] = random.randint(0, WINDOW_WIDTH)

    def _draw_memorial_particles(self, surface):
        """Draw golden light particles on a surface."""
        for p in self._memorial_particles:
            color = (255, 215, 100, p["alpha"])
            particle_surf = pygame.Surface((p["size"] * 2, p["size"] * 2), pygame.SRCALPHA)
            pygame.draw.circle(particle_surf, color, (p["size"], p["size"]), p["size"])
            surface.blit(particle_surf, (int(p["x"]), int(p["y"])))

    def show_memorial(self, name, phase, text, duration=15, tone="solemn"):
        """Show memorial/shot event overlay — handles all phases."""
        self._memorial_active = True
        self._memorial_phase = phase
        self._memorial_name = name
        self._memorial_text = text
        self._memorial_tone = tone
        self._memorial_start = time.time()
        self._memorial_duration = duration
        if phase in ("silence", "music"):
            self._init_memorial_particles()
        if DEBUG_DISPLAY:
            logger.info(f"[DEBUG_DISPLAY] Memorial overlay: phase={phase} name={name} tone={tone} duration={duration}")

    def _draw_memorial(self, surface):
        """Draw shot event overlay — adapts rendering based on event tone."""
        try:
            w, h = surface.get_size()
            elapsed = time.time() - self._memorial_start
            phase = self._memorial_phase
            tone = getattr(self, '_memorial_tone', 'solemn')
            # Pick the right image: event-specific first, NO fallback to memorial photo
            # (memorial_photo is Lisa Webb — only show her for her own event)
            event_img = self._event_image

            # ── Phase 1: Announcement (dim screen + show event image + text) ──
            if phase == "announcement":
                overlay = pygame.Surface((w, h), pygame.SRCALPHA)
                alpha = min(255, int(elapsed * 60))
                if tone == "solemn":
                    overlay.fill((0, 0, 0, alpha))
                elif tone == "celebratory":
                    overlay.fill((30, 0, 60, alpha))
                else:  # fun
                    overlay.fill((0, 20, 50, alpha))
                surface.blit(overlay, (0, 0))

                # Show event image during announcement
                if event_img and alpha > 100:
                    img_rect = event_img.get_rect(center=(w // 2, h // 2 - 40))
                    surface.blit(event_img, img_rect)

                # Show event name title at top
                if alpha > 60:
                    font_title = pygame.font.SysFont("arial", 30, bold=True)
                    display_name = self._memorial_name
                    if "\n" in display_name:
                        display_name = display_name.split("\n", 1)[0].strip()
                    is_lisa = "lisa" in display_name.lower() and "webb" in display_name.lower()
                    title = "In Loving Memory" if is_lisa else display_name
                    title_color = (255, 255, 255) if tone == "solemn" else (255, 215, 0)
                    title_surf = font_title.render(title, True, title_color)
                    shadow = font_title.render(title, True, (0, 0, 0))
                    surface.blit(shadow, shadow.get_rect(center=(w // 2 + 2, 62)))
                    surface.blit(title_surf, title_surf.get_rect(center=(w // 2, 60)))

                # Show announcement text at bottom
                if self._memorial_text:
                    font_ann = pygame.font.SysFont("arial", 24, bold=True)
                    text_color = (255, 255, 255) if tone == "solemn" else (255, 255, 100)
                    # Word-wrap the announcement text
                    words = self._memorial_text.split()
                    lines = []
                    current = ""
                    for word in words:
                        test = f"{current} {word}".strip()
                        if font_ann.size(test)[0] <= w - 80:
                            current = test
                        else:
                            if current:
                                lines.append(current)
                            current = word
                    if current:
                        lines.append(current)
                    y_start = h - 40 - len(lines) * 30
                    for i, line in enumerate(lines):
                        line_surf = font_ann.render(line, True, text_color)
                        shadow = font_ann.render(line, True, (0, 0, 0))
                        surface.blit(shadow, shadow.get_rect(center=(w // 2 + 2, y_start + i * 30 + 2)))
                        surface.blit(line_surf, line_surf.get_rect(center=(w // 2, y_start + i * 30)))

            # ── Phase 2: Moment of Silence (solemn only — photo, particles, glow) ──
            elif phase == "silence":
                overlay = pygame.Surface((w, h), pygame.SRCALPHA)
                overlay.fill((0, 0, 0, 255))
                surface.blit(overlay, (0, 0))

                self._update_memorial_particles()
                self._draw_memorial_particles(surface)

                # Use event-specific image only (don't fall back to Lisa Webb)
                photo = event_img
                if photo:
                    photo_rect = photo.get_rect(center=(w // 2, h // 2 - 20))
                    glow_surf = pygame.Surface((photo_rect.width + 20, photo_rect.height + 20), pygame.SRCALPHA)
                    glow_surf.fill((255, 200, 50, 60))
                    glow_rect = glow_surf.get_rect(center=(w // 2, h // 2 - 20))
                    surface.blit(glow_surf, glow_rect)
                    surface.blit(photo, photo_rect)

                font_large = pygame.font.SysFont("arial", 32, bold=True)
                font_name = pygame.font.SysFont("arial", 36, bold=True)
                font_dates = pygame.font.SysFont("arial", 20)

                # Only show "In Loving Memory" for Lisa Webb; others get their display name
                name_text = self._memorial_name
                is_lisa_webb = "lisa" in name_text.lower() and "webb" in name_text.lower()
                title = "In Loving Memory" if is_lisa_webb else name_text.split("\n", 1)[0].strip()
                title_surf = font_large.render(title, True, (255, 255, 255))
                shadow_surf = font_large.render(title, True, (0, 0, 0))
                surface.blit(shadow_surf, shadow_surf.get_rect(center=(w // 2 + 2, h // 2 - 182)))
                surface.blit(title_surf, title_surf.get_rect(center=(w // 2, h // 2 - 180)))

                name_text = self._memorial_name
                dates_text = ""
                # Parse dates from display_name if it contains a newline
                if "\n" in name_text:
                    parts = name_text.split("\n", 1)
                    name_text = parts[0].strip()
                    dates_text = parts[1].strip()

                name_surf = font_name.render(name_text, True, (255, 215, 0))
                name_shadow = font_name.render(name_text, True, (0, 0, 0))
                photo_bottom = h // 2 + 140
                surface.blit(name_shadow, name_shadow.get_rect(center=(w // 2 + 2, photo_bottom + 2)))
                surface.blit(name_surf, name_surf.get_rect(center=(w // 2, photo_bottom)))

                if not dates_text:
                    # Only show default dates for Lisa Webb events
                    if "lisa" in self._memorial_name.lower():
                        dates_text = "August 17, 1968 \u2013 March 23, 2023"
                if dates_text:
                    dates_surf = font_dates.render(dates_text, True, (200, 200, 200))
                    surface.blit(dates_surf, dates_surf.get_rect(center=(w // 2, photo_bottom + 40)))

            # ── Phase 2b: Countdown (dark overlay behind countdown numbers) ──
            elif phase == "countdown":
                overlay = pygame.Surface((w, h), pygame.SRCALPHA)
                if tone == "solemn":
                    overlay.fill((0, 0, 0, 255))
                elif tone == "celebratory":
                    overlay.fill((30, 0, 60, 255))
                else:  # fun
                    overlay.fill((0, 20, 50, 255))
                surface.blit(overlay, (0, 0))

                # Show event image during countdown (dimmed behind number)
                photo = event_img
                if photo:
                    dimmed = photo.copy()
                    dimmed.set_alpha(80)
                    photo_rect = dimmed.get_rect(center=(w // 2, h // 2 - 20))
                    surface.blit(dimmed, photo_rect)

            # ── Phase 3: Toast/Shot (tone-adaptive overlay + image + text) ──
            elif phase == "toast":
                overlay = pygame.Surface((w, h), pygame.SRCALPHA)
                if tone == "solemn":
                    overlay.fill((60, 30, 0, 255))
                elif tone == "celebratory":
                    overlay.fill((80, 20, 80, 255))
                else:  # fun
                    overlay.fill((0, 40, 80, 255))
                surface.blit(overlay, (0, 0))

                # Show event image
                if event_img:
                    img_rect = event_img.get_rect(center=(w // 2, h // 2 - 60))
                    surface.blit(event_img, img_rect)

                font_toast = pygame.font.SysFont("arial", 34, bold=True)
                # Strip dates from display name for toast
                toast_name = self._memorial_name.split("\n", 1)[0].strip() if "\n" in self._memorial_name else self._memorial_name
                toast_text = f"To {toast_name}!"
                toast_surf = font_toast.render(toast_text, True, (255, 215, 0))
                shadow = font_toast.render(toast_text, True, (0, 0, 0))
                toast_y = h // 2 + (event_img.get_height() // 2 + 30 if event_img is not None else 0)
                surface.blit(shadow, shadow.get_rect(center=(w // 2 + 2, toast_y + 2)))
                surface.blit(toast_surf, toast_surf.get_rect(center=(w // 2, toast_y)))

                emoji_font = pygame.font.SysFont("arial", 28)
                subtitle = "Raise your glass!" if tone == "solemn" else "Take a shot!"
                emoji_surf = emoji_font.render(subtitle, True, (255, 255, 255))
                surface.blit(emoji_surf, emoji_surf.get_rect(center=(w // 2, toast_y + 40)))

                # Word-wrap the toast text below
                if self._memorial_text:
                    font_detail = pygame.font.SysFont("arial", 20)
                    words = self._memorial_text.split()
                    lines = []
                    current = ""
                    for word in words:
                        test = f"{current} {word}".strip()
                        if font_detail.size(test)[0] <= w - 80:
                            current = test
                        else:
                            if current:
                                lines.append(current)
                            current = word
                    if current:
                        lines.append(current)
                    y_start = toast_y + 80
                    for i, line in enumerate(lines[-3:]):
                        line_surf = font_detail.render(line, True, (220, 220, 220))
                        surface.blit(line_surf, line_surf.get_rect(center=(w // 2, y_start + i * 24)))

            # ── Phase 4: Music (photo + particles + tone-aware title) ──
            elif phase == "music":
                overlay = pygame.Surface((w, h), pygame.SRCALPHA)
                overlay.fill((0, 0, 0, 255))
                surface.blit(overlay, (0, 0))

                self._update_memorial_particles()
                self._draw_memorial_particles(surface)

                photo = event_img
                if photo:
                    photo_rect = photo.get_rect(center=(w // 2, h // 2 - 20))
                    glow_surf = pygame.Surface((photo_rect.width + 20, photo_rect.height + 20), pygame.SRCALPHA)
                    glow_color = (255, 200, 50, 40) if tone == "solemn" else (100, 150, 255, 40) if tone == "fun" else (200, 100, 255, 40)
                    glow_surf.fill(glow_color)
                    glow_rect = glow_surf.get_rect(center=(w // 2, h // 2 - 20))
                    surface.blit(glow_surf, glow_rect)
                    surface.blit(photo, photo_rect)

                font_mem = pygame.font.SysFont("arial", 28, bold=True)
                # Use event display name as title (only "In Loving Memory" for lisa_webb)
                display_name = self._memorial_name
                if "\n" in display_name:
                    display_name = display_name.split("\n", 1)[0].strip()
                
                is_lisa_webb = "lisa" in display_name.lower() and "webb" in display_name.lower()
                if is_lisa_webb:
                    title_text = "In Loving Memory"
                    title_color = (255, 255, 255)
                elif tone == "solemn":
                    title_text = display_name
                    title_color = (255, 255, 255)
                elif tone == "celebratory":
                    title_text = display_name
                    title_color = (255, 215, 0)
                else:  # fun
                    title_text = display_name
                    title_color = (100, 200, 255)
                mem_surf = font_mem.render(title_text, True, title_color)
                surface.blit(mem_surf, mem_surf.get_rect(center=(w // 2, h // 2 - 190)))

                # Show subtitle text below the photo (word-wrapped)
                if self._memorial_text:
                    font_sub = pygame.font.SysFont("arial", 20)
                    words = self._memorial_text.split()
                    lines = []
                    current = ""
                    for word in words:
                        test = f"{current} {word}".strip()
                        if font_sub.size(test)[0] <= w - 80:
                            current = test
                        else:
                            if current:
                                lines.append(current)
                            current = word
                    if current:
                        lines.append(current)
                    # Show last 3 lines max to fit screen
                    y_start = h // 2 + 170
                    for i, line in enumerate(lines[-3:]):
                        line_surf = font_sub.render(line, True, (200, 200, 200))
                        shadow = font_sub.render(line, True, (0, 0, 0))
                        surface.blit(shadow, shadow.get_rect(center=(w // 2 + 1, y_start + i * 26 + 1)))
                        surface.blit(line_surf, line_surf.get_rect(center=(w // 2, y_start + i * 26)))

            # ── Phase 5: Recovery (surprise reveal for fake memorials) ──
            elif phase == "recovery":
                overlay = pygame.Surface((w, h), pygame.SRCALPHA)
                # Bright flash that fades — celebratory surprise
                flash_alpha = max(0, int(255 * (1.0 - elapsed / 2.0))) if elapsed < 2.0 else 0
                overlay.fill((255, 255, 200, flash_alpha))
                surface.blit(overlay, (0, 0))

                # Show the recovery text
                if self._memorial_text:
                    font_big = pygame.font.SysFont("arial", 32, bold=True)
                    # Word-wrap
                    words = self._memorial_text.split()
                    lines = []
                    current = ""
                    for word in words:
                        test = f"{current} {word}".strip()
                        if font_big.size(test)[0] <= w - 60:
                            current = test
                        else:
                            if current:
                                lines.append(current)
                            current = word
                    if current:
                        lines.append(current)
                    y_start = h // 2 - len(lines) * 20
                    for i, line in enumerate(lines):
                        line_surf = font_big.render(line, True, (255, 255, 50))
                        shadow = font_big.render(line, True, (0, 0, 0))
                        surface.blit(shadow, shadow.get_rect(center=(w // 2 + 2, y_start + i * 40 + 2)))
                        surface.blit(line_surf, line_surf.get_rect(center=(w // 2, y_start + i * 40)))

            # ── Phase 6: Fade Out ──
            elif phase == "fadeout":
                fade_duration = 3.0
                if elapsed < fade_duration:
                    alpha = int(200 * (1.0 - elapsed / fade_duration))
                    overlay = pygame.Surface((w, h), pygame.SRCALPHA)
                    overlay.fill((0, 0, 0, max(0, alpha)))
                    surface.blit(overlay, (0, 0))
                else:
                    self._memorial_active = False
                    self._event_image = None
                    self._event_image_path = None

        except Exception as e:
            logger.debug(f"Memorial draw error: {e}")

    def _draw_health_overlay(self):
        """Draw server health info panel (F4 toggle)."""
        if not self._health_visible or not self._health_data:
            return
        d = self._health_data
        lines = [
            f"STATUS: {d.get('status', '?')}",
            f"UPTIME: {d.get('uptime', '?')}",
            f"LLM: {d.get('llm_model', '?')}",
            f"TTS: {d.get('tts_engine', '?')}",
            f"CACHE: {d.get('tts_cache_size', '?')}",
            f"TIER: {d.get('performance_tier', '?')}",
            f"MEMORY: {d.get('memory_mb', '?')}MB",
            f"IDLE ERR: {d.get('idle_errors', '?')}",
            f"GAMES: {d.get('active_games', '?')}",
            f"RESP: {self._last_response_time:.1f}s" if self._last_response_time > 0 else "RESP: --",
        ]
        panel_w, line_h = 260, 22
        panel_h = len(lines) * line_h + 20
        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel.fill((0, 0, 0, 180))
        title_font = self._font_small or pygame.font.SysFont("arial", 14)
        status_color = (100, 200, 100) if d.get('status') == 'ok' else (255, 100, 100)
        title_surf = title_font.render("SERVER HEALTH [F4]", True, status_color)
        panel.blit(title_surf, (10, 5))
        for i, line in enumerate(lines):
            color = (200, 200, 200)
            if line.startswith("IDLE ERR:") and d.get('idle_errors', 0) > 0:
                color = (255, 180, 80)
            elif line.startswith("STATUS:") and d.get('status') != 'ok':
                color = (255, 100, 100)
            surf = title_font.render(line, True, color)
            panel.blit(surf, (10, 25 + i * line_h))
        x = WINDOW_WIDTH - panel_w - 10
        y = getattr(self, '_banner_bottom', 48) + 10
        self._screen.blit(panel, (x, y))

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
