"""Analyze Mario's text to extract pose hints and clean action text.

Parses asterisk actions like *checks mustache* into sprite pose hints,
strips them from TTS text, and detects content-based poses from what Mario says.
"""

import re
import logging

DEBUG_POSE = True
logger = logging.getLogger(__name__)

# Map common action keywords to sprite pose categories
ACTION_POSE_MAP = {
    # Movement
    "jump": "movement/jumping",
    "jumping": "movement/jumping",
    "dance": "movement/dancing_1",
    "dancing": "movement/dancing_1",
    "run": "movement/running",
    "running": "movement/running",
    "tiptoe": "movement/tiptoeing",
    "crouch": "movement/crouching",
    "flex": "movement/flexing",
    "slide": "movement/sliding",
    "point": "movement/pointing",
    # Actions
    "dab": "action/dabbing",
    "facepalm": "action/facepalm",
    "salute": "action/salute",
    "shrug": "action/shrug",
    "eat": "action/eating_mushroom",
    "mushroom": "action/eating_mushroom",
    # Positive
    "thumbs up": "positive/thumbs_up",
    "peace": "positive/peace_sign",
    "laugh": "positive/laughing",
    "cheer": "positive/victorious",
    "victory": "positive/victorious",
    "proud": "positive/proud",
    "happy": "positive/happy",
    "celebrate": "positive/very_happy",
    "love": "positive/love",
    "heart": "positive/love",
    # Negative
    "cry": "negative/crying",
    "angry": "negative/angry",
    "furious": "negative/furious",
    "scared": "negative/scared",
    "nervous": "negative/nervous",
    "embarrassed": "negative/embarrassed",
    "sad": "negative/sad",
    "disappointed": "negative/disappointed",
    "disgusted": "negative/disgusted",
    # Thinking
    "think": "thinking/thinking",
    "thinking": "thinking/thinking",
    "confused": "thinking/confused",
    "curious": "thinking/curious",
    "idea": "thinking/idea",
    "lightbulb": "thinking/idea",
    "shock": "thinking/shocked",
    "surprised": "thinking/surprised",
    "suspicious": "thinking/suspicious",
    "mischiev": "thinking/mischievous",
    "dizzy": "thinking/dizzy",
    # Greeting
    "wave": "greeting/wave_high",
    "waving": "greeting/wave_high",
    "tip hat": "greeting/tip_hat",
    "welcome": "greeting/welcome_arms",
    "farewell": "greeting/farewell",
    "bye": "greeting/farewell",
    "goodbye": "greeting/farewell",
    # Speech
    "whisper": "speech/whispering",
    "shout": "speech/shouting",
    "sing": "speech/singing",
    "singing": "speech/singing",
    "hum": "speech/singing",
    "humming": "speech/singing",
    "whistle": "speech/whistling",
    "listen": "speech/listening",
    "shush": "speech/shushing",
    # Sleep
    "yawn": "sleep/yawning",
    "sleep": "sleep/sleeping",
    "snore": "sleep/sleeping",
    "nap": "sleep/sleepy",
    # Neutral
    "look": "neutral/looking_left",
    "mirror": "neutral/looking_left",
    "inspect": "neutral/looking_up",
    "check": "neutral/looking_left",
    "mustache": "neutral/looking_left",
    "wink": "neutral/idle_wink",
    "blink": "neutral/idle_blink",
    "knock": "movement/pointing",
    "tap": "movement/pointing",
    "peek": "neutral/looking_left",
    "stare": "neutral/looking_right",
    "glance": "neutral/looking_left",
    "shadow box": "movement/flexing",
    "stretch": "movement/flexing",
    "pose": "positive/proud",
    "puff": "movement/flexing",
    "adjust": "neutral/looking_left",
    "polish": "neutral/looking_left",
    "practice": "movement/flexing",
    "clean": "neutral/looking_up",
    "guard": "thinking/determined",
    "patrol": "movement/running",
    "lean": "neutral/idle",
    "spin": "movement/dancing_1",
    "twirl": "movement/dancing_1",
    "air guitar": "movement/dancing_1",
    # Powerup
    "fire": "powerup/fire_mario",
    "star": "powerup/star_power",
    "gold": "powerup/gold_mario",
    "ice": "powerup/ice_mario",
    "metal": "powerup/metal_mario",
    "mega": "powerup/mega_mario",
    "mini": "powerup/mini_mario",
}

# Content keywords that suggest a pose (for non-action text)
CONTENT_POSE_MAP = {
    # Questions → curious
    "?": "thinking/curious",
    "what": "thinking/curious",
    "who": "thinking/curious",
    "how": "thinking/curious",
    "why": "thinking/curious",
    # Excitement
    "wahoo": "positive/excited_jump",
    "let's-a go": "positive/excited_jump",
    "yahoo": "positive/excited_jump",
    "yeah": "positive/very_happy",
    # Surprise
    "mama mia": "thinking/surprised",
    "mamma mia": "thinking/surprised",
    "oh no": "thinking/surprised",
    # Greetings
    "hello": "greeting/wave_high",
    "welcome": "greeting/welcome_arms",
    "hi there": "greeting/wave_casual",
    "nice to meet": "greeting/hello_sparkle",
    # Goodbye
    "bye": "greeting/farewell",
    "see you": "greeting/farewell",
    "arrivederci": "greeting/farewell",
    # Humor
    "ha ha": "positive/laughing",
    "haha": "positive/laughing",
    "funny": "positive/laughing",
    "joke": "thinking/mischievous",
    # Food
    "pasta": "positive/happy",
    "spaghetti": "positive/happy",
    "mushroom": "action/eating_mushroom",
    # Challenge
    "bowser": "thinking/determined",
    "fight": "thinking/determined",
    "challenge": "thinking/determined",
    # Compliment
    "thank": "positive/thumbs_up",
    "nice": "positive/thumbs_up",
    "great": "positive/thumbs_up",
    "awesome": "positive/very_happy",
    "beautiful": "positive/love",
    # Hand washing
    "wash": "movement/pointing",
    "hands": "movement/pointing",
    "soap": "movement/pointing",
    # Pipes/plumbing
    "pipe": "neutral/looking_up",
    "plumb": "neutral/looking_up",
    # Singing
    "♪": "speech/singing",
    "la la": "speech/singing",
    "do re mi": "speech/singing",
    # Thinking
    "hmm": "thinking/thinking",
    "let me think": "thinking/thinking",
    "well": "thinking/thinking",
    # Scared
    "ghost": "negative/scared",
    "boo": "negative/scared",
    "scary": "negative/scared",
    "spooky": "negative/scared",
    # Love
    "princess": "positive/love",
    "peach": "positive/love",
    "beautiful": "positive/love",
    # Pride
    "number one": "positive/proud",
    "the best": "positive/proud",
    "champion": "positive/proud",
    # Sadness
    "sorry": "negative/sad",
    "miss": "negative/sad",
    "luigi": "negative/sad",
    # Determination
    "never give up": "thinking/determined",
    "let's do this": "thinking/determined",
    "ready": "thinking/determined",
    # Warning
    "careful": "movement/pointing",
    "watch out": "movement/pointing",
    "danger": "negative/scared",
    # Sleepy
    "tired": "sleep/yawning",
    "sleepy": "sleep/sleepy",
    "late": "sleep/yawning",
    # Whisper/Secret
    "secret": "speech/whispering",
    "psst": "speech/whispering",
    "between us": "speech/whispering",
    # Party
    "party": "positive/excited_jump",
    "dance": "movement/dancing_1",
    "celebrate": "positive/very_happy",
    "music": "speech/singing",
    # Friends
    "friend": "positive/happy",
    "buddy": "positive/happy",
    "pal": "positive/happy",
    # Adventure
    "adventure": "positive/excited_jump",
    "quest": "thinking/determined",
    "mission": "thinking/determined",
    "hero": "positive/proud",
    # Animals
    "yoshi": "positive/happy",
    "donkey kong": "movement/flexing",
    # Colors
    "red": "positive/proud",
    "green": "negative/sad",  # Luigi
    "gold": "powerup/gold_mario",
    # Numbers
    "record": "positive/victorious",
    "first": "positive/victorious",
    "winner": "positive/victorious",
    # Power-ups
    "fire flower": "powerup/fire_mario",
    "fire power": "powerup/fire_mario",
    "fire ball": "powerup/fire_mario",
    "ice power": "powerup/ice_mario",
    "frozen": "powerup/ice_mario",
    "star power": "powerup/star_power",
    "invincible": "powerup/star_power",
    "super star": "powerup/star_power",
    "metal": "powerup/metal_mario",
    "mega": "powerup/mega_mario",
    "giant": "powerup/mega_mario",
    "tiny": "powerup/mini_mario",
    "mini": "powerup/mini_mario",
    "small": "powerup/mini_mario",
    # Bathroom specific
    "toilet": "thinking/mischievous",
    "flush": "thinking/mischievous",
    "bathroom": "neutral/looking_left",
    "mirror": "neutral/idle_wink",
    "door": "neutral/looking_right",
    "towel": "movement/pointing",
    # Emotions
    "angry": "negative/angry",
    "mad": "negative/angry",
    "furious": "negative/furious",
    "sad": "negative/sad",
    "cry": "negative/crying",
    "embarrassed": "negative/embarrassed",
    "nervous": "negative/nervous",
    "disgusted": "negative/disgusted",
    "confused": "thinking/confused",
    "dizzy": "thinking/dizzy",
    "surprised": "thinking/surprised",
    "shocked": "thinking/shocked",
    "idea": "thinking/idea",
    "eureka": "thinking/idea",
    # Actions
    "shrug": "action/shrug",
    "salute": "action/salute",
    "dab": "action/dabbing",
    "peace": "positive/peace_sign",
    "thumbs up": "positive/thumbs_up",
    "victory": "positive/victorious",
    # Time of day
    "morning": "sleep/yawning",
    "goodnight": "sleep/sleepy",
    "night": "sleep/sleepy",
    # Instructions/teaching
    "remember": "thinking/thinking",
    "lesson": "speech/talking_excited",
    "listen": "speech/listening",
    "shh": "speech/shushing",
    "quiet": "speech/shushing",
    "whistle": "speech/whistling",
    "shout": "speech/shouting",
    "yell": "speech/shouting",
    # Confidence
    "trust me": "positive/proud",
    "i got this": "thinking/determined",
    "no problem": "positive/thumbs_up",
    "easy": "positive/thumbs_up",
    # Party context
    "cheers": "positive/excited_jump",
    "drink": "action/eating_mushroom",
    "drunk": "thinking/dizzy",
    "shots": "positive/excited_jump",
    "karaoke": "speech/singing",
    "selfie": "positive/peace_sign",
    "photo": "positive/peace_sign",
    "friend": "positive/waving",
    "crew": "positive/waving",
    "vibe": "positive/chill_relaxed",
    "chill": "positive/chill_relaxed",
    "relax": "positive/chill_relaxed",
    "bro": "positive/fist_bump",
    "dude": "positive/fist_bump",
    # Greetings
    "hello": "greeting/wave_high",
    "hey": "greeting/wave_casual",
    "hi mario": "greeting/hello_sparkle",
    "goodbye": "greeting/farewell",
    "bye": "greeting/farewell",
    "see you": "greeting/farewell",
    "later": "greeting/farewell",
    # Questions
    "how": "thinking/curious",
    "why": "thinking/curious",
    "what": "thinking/curious",
    "where": "thinking/curious",
}


def analyze_text(text: str) -> dict:
    """Analyze Mario's response text for pose hints and clean TTS text.

    Returns:
        {
            "tts_text": str,      # Text with actions stripped (for TTS)
            "display_text": str,   # Full text (for display/speech bubble)
            "pose_hint": str|None, # Best matching sprite pose key
            "actions": list[str],  # Extracted action descriptions
        }
    """
    if not text:
        return {"tts_text": "", "display_text": "", "pose_hint": None, "actions": []}

    # Extract asterisk actions: *does something*
    actions = re.findall(r'\*([^*]+)\*', text)
    tts_text = re.sub(r'\*[^*]+\*', '', text).strip()
    tts_text = re.sub(r'\s+', ' ', tts_text).strip()

    # Find pose hint from actions first (highest priority)
    pose_hint = None
    if actions:
        action_text = " ".join(actions).lower()
        pose_hint = _match_action_pose(action_text)

    # If no action-based pose, try content-based detection
    if not pose_hint and tts_text:
        pose_hint = _match_content_pose(tts_text)

    # Default fallback pose
    if not pose_hint:
        pose_hint = "neutral/idle"

    if DEBUG_POSE and (actions or pose_hint):
        logger.info(f"[DEBUG_POSE] analyze: actions={actions}, pose={pose_hint}")

    return {
        "tts_text": tts_text if tts_text else text,
        "display_text": text,
        "pose_hint": pose_hint,
        "actions": actions,
    }


def _match_action_pose(action_text: str) -> str | None:
    """Match action text to a sprite pose."""
    normalized = action_text.replace("-", " ").replace("_", " ")
    for keyword, pose in ACTION_POSE_MAP.items():
        if keyword in normalized:
            return pose
    return None


def _match_content_pose(text: str) -> str | None:
    """Match spoken content to a sprite pose based on keywords."""
    lower = text.lower()

    # Check for questions (ends with ?)
    if text.strip().endswith("?"):
        return "thinking/curious"

    # Check content keywords (longer matches first for specificity)
    sorted_keys = sorted(CONTENT_POSE_MAP.keys(), key=len, reverse=True)
    for keyword in sorted_keys:
        if keyword in lower:
            return CONTENT_POSE_MAP[keyword]

    return None
