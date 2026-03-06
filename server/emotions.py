"""Emotion and mood system for Mario."""

import logging
import random
import threading
import time

DEBUG_EMOTION = True
logger = logging.getLogger(__name__)


class Emotion:
    HAPPY = "happy"
    EXCITED = "excited"
    BORED = "bored"
    SURPRISED = "surprised"
    CONFUSED = "confused"
    WORRIED = "worried"
    LOVING = "loving"
    MISCHIEVOUS = "mischievous"
    SLEEPY = "sleepy"
    NEUTRAL = "neutral"


# How emotions affect TTS voice parameters
EMOTION_VOICE_MAP = {
    Emotion.HAPPY:      {"rate": "+10%", "pitch": "+2Hz"},
    Emotion.EXCITED:    {"rate": "+25%", "pitch": "+5Hz"},
    Emotion.BORED:      {"rate": "-15%", "pitch": "-3Hz"},
    Emotion.SURPRISED:  {"rate": "+15%", "pitch": "+4Hz"},
    Emotion.CONFUSED:   {"rate": "-5%", "pitch": "+1Hz"},
    Emotion.WORRIED:    {"rate": "-10%", "pitch": "-1Hz"},
    Emotion.LOVING:     {"rate": "-5%", "pitch": "+2Hz"},
    Emotion.MISCHIEVOUS: {"rate": "+5%", "pitch": "+3Hz"},
    Emotion.SLEEPY:     {"rate": "-20%", "pitch": "-4Hz"},
    Emotion.NEUTRAL:    {"rate": "+0%", "pitch": "+0Hz"},
}

# Emotion descriptions for the LLM prompt
EMOTION_DESCRIPTIONS = {
    Emotion.HAPPY:      "You're feeling happy and cheerful! Everything is wonderful!",
    Emotion.EXCITED:    "You're SUPER excited! Jumping with energy! Wahoo!",
    Emotion.BORED:      "You're a little bored... nobody's been around for a while.",
    Emotion.SURPRISED:  "You're surprised! Something unexpected just happened!",
    Emotion.CONFUSED:   "You're confused... that didn't make much sense to you.",
    Emotion.WORRIED:    "You're a little worried... is everything okay?",
    Emotion.LOVING:     "You're feeling warm and friendly! You love meeting people!",
    Emotion.MISCHIEVOUS: "You're feeling mischievous! Time for some playful jokes!",
    Emotion.SLEEPY:     "You're getting sleepy... it's been a long party...",
    Emotion.NEUTRAL:    "You're feeling normal — ready for anything!",
}


class EmotionSystem:
    """Tracks Mario's current emotional state."""

    def __init__(self):
        self.current = Emotion.HAPPY
        self.intensity = 0.7  # 0.0-1.0
        self._last_change = time.time()
        self._last_interaction = time.time()
        self._lock = threading.Lock()
        self._visitor_count = 0

    def update(self, event: str = None, transcript: str = None):
        """Update emotion based on events and conversation."""
        with self._lock:
            self._update_internal(event, transcript)

    def _update_internal(self, event: str = None, transcript: str = None):
        """Internal update — must be called with self._lock held."""
        now = time.time()
        idle_time = now - self._last_interaction

        # Decay intensity over time (emotions fade)
        time_since_change = now - self._last_change
        if time_since_change > 30 and self.intensity > 0.3:
            self.intensity = max(0.3, self.intensity - 0.03 * (time_since_change / 60))

        # Time-based mood shifts
        if idle_time > 600:  # 10 minutes alone
            self.current = Emotion.SLEEPY
            self.intensity = 0.8
        elif idle_time > 300:  # 5 minutes alone
            self.current = Emotion.BORED
            self.intensity = min(1.0, idle_time / 600)

        # Late night = sleepy (midnight to 6am)
        hour = time.localtime().tm_hour
        if hour >= 0 and hour < 6:
            if self.current not in (Emotion.EXCITED, Emotion.SURPRISED):
                self.current = Emotion.SLEEPY
                self.intensity = 0.6

        # Event-based emotions
        if event == "presence_enter":
            self._last_interaction = now
            self._visitor_count += 1
            if idle_time > 120:
                self.current = Emotion.EXCITED
                self.intensity = 0.9
            else:
                self.current = Emotion.HAPPY
                self.intensity = 0.8

        elif event == "presence_exit":
            self.current = Emotion.HAPPY
            self.intensity = 0.3
            self._last_change = now

        elif event == "speech_detected":
            self._last_interaction = now
            if self.current == Emotion.BORED:
                self.current = Emotion.SURPRISED
                self.intensity = 0.7

        # Transcript-based emotions (skip very short noise fragments)
        if transcript and len(transcript.split()) >= 2:
            self._last_interaction = now
            lower = transcript.lower()

            if any(w in lower for w in ["love", "awesome", "amazing", "great", "best", "beautiful", "wonderful"]):
                self.current = Emotion.LOVING
                self.intensity = 0.9
            elif any(w in lower for w in ["what", "huh", "confused", "don't understand", "makes no sense"]):
                self.current = Emotion.CONFUSED
                self.intensity = 0.6
            elif any(w in lower for w in ["help", "scared", "worried", "nervous", "anxious", "stressed"]):
                self.current = Emotion.WORRIED
                self.intensity = 0.7
            elif any(w in lower for w in ["funny", "joke", "laugh", "haha", "lol", "hilarious", "prank"]):
                self.current = Emotion.MISCHIEVOUS
                self.intensity = 0.8
            elif any(w in lower for w in ["wow", "omg", "no way", "really", "seriously", "wait what", "whoa"]):
                self.current = Emotion.SURPRISED
                self.intensity = 0.8
            elif any(w in lower for w in ["wahoo", "let's go", "party", "excited", "woo", "yeah", "yay"]):
                self.current = Emotion.EXCITED
                self.intensity = 0.9
            elif any(w in lower for w in ["sad", "miss", "lonely", "down"]):
                self.current = Emotion.WORRIED
                self.intensity = 0.6
            elif any(w in lower for w in ["tired", "exhausted", "bored", "meh", "sleepy"]):
                self.current = Emotion.BORED
                self.intensity = 0.6
            elif any(w in lower for w in ["pasta", "food", "eat", "hungry", "pizza", "spaghetti", "garlic", "cake", "cookie", "gelato"]):
                self.current = Emotion.EXCITED
                self.intensity = 0.85
            elif any(w in lower for w in ["thank you", "thanks", "appreciate", "kind", "generous"]):
                self.current = Emotion.HAPPY
                self.intensity = 0.9
            elif any(w in lower for w in ["secret", "whisper", "between us", "don't tell"]):
                self.current = Emotion.MISCHIEVOUS
                self.intensity = 0.7
            elif any(w in lower for w in ["hate", "sucks", "stupid", "ugh", "annoying", "worst"]):
                self.current = Emotion.WORRIED
                self.intensity = 0.5
            elif any(w in lower for w in ["cool", "nice", "sweet", "fire", "lit", "sick", "dope"]):
                self.current = Emotion.HAPPY
                self.intensity = 0.8
            elif any(w in lower for w in ["music", "song", "sing", "dance", "dj", "beat"]):
                self.current = Emotion.EXCITED
                self.intensity = 0.8
            elif any(w in lower for w in ["bye", "goodbye", "leaving", "going", "gotta go"]):
                self.current = Emotion.HAPPY
                self.intensity = 0.6

        # Track when emotion last changed for decay
        if transcript or event:
            self._last_change = time.time()

        if DEBUG_EMOTION:
            logger.info(f"[DEBUG_EMOTION] update: {self.current} (intensity={self.intensity:.1f})")

    def get_voice_params(self) -> dict:
        """Get TTS voice parameters for current emotion."""
        with self._lock:
            return EMOTION_VOICE_MAP.get(self.current, EMOTION_VOICE_MAP[Emotion.NEUTRAL])

    def get_prompt_addition(self) -> str:
        """Get text to add to LLM prompt about current emotion."""
        with self._lock:
            desc = EMOTION_DESCRIPTIONS.get(self.current, "")
            return f"[MOOD: {self.current.upper()}]: {desc}"

    @property
    def animation_state(self) -> str:
        """Map emotion to animation state name."""
        mapping = {
            Emotion.HAPPY: "happy",
            Emotion.EXCITED: "excited",
            Emotion.BORED: "bored",
            Emotion.SURPRISED: "surprised",
            Emotion.CONFUSED: "confused",
            Emotion.WORRIED: "worried",
            Emotion.LOVING: "loving",
            Emotion.MISCHIEVOUS: "mischievous",
            Emotion.SLEEPY: "sleepy",
            Emotion.NEUTRAL: "idle",
        }
        return mapping.get(self.current, "idle")
