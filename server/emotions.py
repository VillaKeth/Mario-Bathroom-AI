"""Emotion and mood system for Mario."""

import json
import logging
import re
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
    PROUD = "proud"
    FRUSTRATED = "frustrated"
    EMBARRASSED = "embarrassed"
    NEUTRAL = "neutral"
    # New emotions for expanded system (13 → 26)
    ANNOYED = "annoyed"
    LAUGHING = "laughing"
    SAD = "sad"
    ANGRY = "angry"
    NERVOUS = "nervous"
    SCARED = "scared"
    LOVE = "love"
    DISGUSTED = "disgusted"
    DETERMINED = "determined"
    CURIOUS = "curious"
    THINKING = "thinking"
    SHOCKED = "shocked"
    IDEA = "idea"


# How emotions affect TTS voice parameters — more dramatic range for Neuro-sama energy
EMOTION_VOICE_MAP = {
    Emotion.HAPPY:      {"rate": "+15%", "pitch": "+3Hz"},
    Emotion.EXCITED:    {"rate": "+30%", "pitch": "+6Hz"},
    Emotion.BORED:      {"rate": "-20%", "pitch": "-4Hz"},
    Emotion.SURPRISED:  {"rate": "+20%", "pitch": "+5Hz"},
    Emotion.CONFUSED:   {"rate": "-8%", "pitch": "+2Hz"},
    Emotion.WORRIED:    {"rate": "-12%", "pitch": "-2Hz"},
    Emotion.LOVING:     {"rate": "-5%", "pitch": "+3Hz"},
    Emotion.MISCHIEVOUS: {"rate": "+10%", "pitch": "+4Hz"},
    Emotion.SLEEPY:     {"rate": "-25%", "pitch": "-5Hz"},
    Emotion.PROUD:      {"rate": "+8%", "pitch": "+2Hz"},
    Emotion.FRUSTRATED: {"rate": "+15%", "pitch": "-3Hz"},
    Emotion.EMBARRASSED: {"rate": "-12%", "pitch": "+4Hz"},
    Emotion.NEUTRAL:    {"rate": "+0%", "pitch": "+0Hz"},
    # New emotions (13 → 26)
    Emotion.ANNOYED:    {"rate": "+12%", "pitch": "-2Hz"},
    Emotion.LAUGHING:   {"rate": "+25%", "pitch": "+5Hz"},
    Emotion.SAD:        {"rate": "-18%", "pitch": "-4Hz"},
    Emotion.ANGRY:      {"rate": "+20%", "pitch": "-5Hz"},
    Emotion.NERVOUS:    {"rate": "+5%", "pitch": "+3Hz"},
    Emotion.SCARED:     {"rate": "+10%", "pitch": "+6Hz"},
    Emotion.LOVE:       {"rate": "-5%", "pitch": "+4Hz"},
    Emotion.DISGUSTED:  {"rate": "-10%", "pitch": "-3Hz"},
    Emotion.DETERMINED: {"rate": "+12%", "pitch": "+1Hz"},
    Emotion.CURIOUS:    {"rate": "+8%", "pitch": "+3Hz"},
    Emotion.THINKING:   {"rate": "-15%", "pitch": "+1Hz"},
    Emotion.SHOCKED:    {"rate": "+25%", "pitch": "+7Hz"},
    Emotion.IDEA:       {"rate": "+18%", "pitch": "+5Hz"},
}

# Emotion descriptions for the LLM prompt — Neuro-sama dramatic style
EMOTION_DESCRIPTIONS = {
    Emotion.HAPPY:      "You're feeling GREAT! Everything is amazing! Be warm and enthusiastic!",
    Emotion.EXCITED:    "You're BUZZING with energy! Can't contain yourself! WAHOO! Be WILD!",
    Emotion.BORED:      "You're SO bored you might literally turn into a Goomba. Be dramatically bored.",
    Emotion.SURPRISED:  "WHAT?! You did NOT expect that! Be shocked! Dramatic gasp!",
    Emotion.CONFUSED:   "You're SO confused right now. Nothing makes sense. Question EVERYTHING.",
    Emotion.WORRIED:    "Something feels off... be genuinely concerned but still Mario about it.",
    Emotion.LOVING:     "You're feeling SO warm and fuzzy! Hearts everywhere! Be sweet and genuine!",
    Emotion.MISCHIEVOUS: "You're feeling DEVIOUS! Time for chaos! Tease, prank, be a menace (lovingly)!",
    Emotion.SLEEPY:     "Soooo sleeeepy... *yawns* ...words are getting harder... but you're trying...",
    Emotion.PROUD:      "You're the GREATEST! Flex! Brag! You earned it! Be magnificently proud!",
    Emotion.FRUSTRATED: "MAMA MIA! Things aren't going your way! Be grumpy but funny about it!",
    Emotion.EMBARRASSED: "Oh no... that was awkward... try to play it cool but FAIL at playing it cool.",
    Emotion.NEUTRAL:    "Normal Mario vibes — ready for anything!",
    # New emotions (13 → 26)
    Emotion.ANNOYED:    "You're slightly irritated but holding it in... barely. Side-eye energy.",
    Emotion.LAUGHING:   "You're CRACKING UP! Can't stop laughing! This is HILARIOUS! Hahahaha!",
    Emotion.SAD:        "You're feeling down... genuinely sad... try to be brave but it shows.",
    Emotion.ANGRY:      "You're ANGRY! Fired up! Channel it into dramatic Mario rage! RARGH!",
    Emotion.NERVOUS:    "You're nervous! A bit jittery! What if something goes wrong?! Be anxious!",
    Emotion.SCARED:     "You're SCARED! Genuinely frightened! Wide eyes! Maybe hide behind Luigi!",
    Emotion.LOVE:       "You're in LOVE! Heart eyes! This is THE BEST! Be absolutely smitten!",
    Emotion.DISGUSTED:  "Ewww! GROSS! You're disgusted! Make a face! This is NASTY!",
    Emotion.DETERMINED: "You're LOCKED IN! Nothing can stop you! Be focused and fierce!",
    Emotion.CURIOUS:    "You're SO curious! What's that?! Tell me more! Be inquisitive and eager!",
    Emotion.THINKING:   "Hmmm... you're deep in thought... pondering... be contemplative...",
    Emotion.SHOCKED:    "SHOCKED! Mind = BLOWN! This is UNBELIEVABLE! Jaw on the floor!",
    Emotion.IDEA:       "AHA! You just had a BRILLIANT idea! Eureka moment! Light bulb! Share it!",
}


def extract_emotion_tag(response: str) -> dict:
    """Extract emotion and energy from LLM response JSON, return clean text.
    
    Returns: {"emotion": str, "energy": float, "clean_text": str}
    Falls back to neutral emotion and 0.5 energy on parse failure.
    """
    if DEBUG_EMOTION:
        logger.info(f"[DEBUG_EMOTION] extract_emotion_tag: parsing response")
    
    clean_text = response
    result = {"emotion": "neutral", "energy": 0.5, "clean_text": clean_text}
    
    try:
        # Try to find JSON at end of response
        json_match = re.search(r'\{[^{}]*(?:"emotion"|"energy")[^{}]*\}', response)
        if json_match:
            json_str = json_match.group()
            data = json.loads(json_str)
            
            # Extract emotion
            emotion = data.get("emotion", "neutral")
            # Validate against known emotions
            known = {v for k, v in vars(Emotion).items() if not k.startswith("_") and isinstance(v, str)}
            if emotion not in known:
                emotion = "neutral"
                if DEBUG_EMOTION:
                    logger.info(f"[DEBUG_EMOTION] extract_emotion_tag: unknown emotion '{data.get('emotion')}', using 'neutral'")
            
            # Extract and validate energy (0.0-1.0)
            energy = data.get("energy", 0.5)
            try:
                energy = float(energy)
                energy = max(0.0, min(1.0, energy))  # Clamp to valid range
            except (ValueError, TypeError):
                energy = 0.5
            
            # Strip JSON from clean text
            clean_text = response.replace(json_str, "").strip()
            
            result = {"emotion": emotion, "energy": energy, "clean_text": clean_text}
            
            if DEBUG_EMOTION:
                logger.info(f"[DEBUG_EMOTION] extract_emotion_tag: extracted emotion='{emotion}', energy={energy}")
                
    except (json.JSONDecodeError, AttributeError) as e:
        if DEBUG_EMOTION:
            logger.info(f"[DEBUG_EMOTION] extract_emotion_tag: parse error {e}, using defaults")
    
    return result


class EmotionSystem:
    """Tracks Mario's current emotional state and rolling sentiment."""

    def __init__(self):
        self.current = Emotion.HAPPY
        self.intensity = 0.7  # 0.0-1.0
        self._last_change = time.time()
        self._last_interaction = time.time()
        self._lock = threading.Lock()
        self._visitor_count = 0
        # Rolling sentiment tracker — average mood over recent exchanges
        self._sentiment_history = []  # list of (timestamp, score) — score: -1.0 to +1.0
        self._conversation_energy = 0.5  # 0=dead, 1=high energy
        self._negative_mood_start = 0.0  # When negative mood began (for cheer-up system)
        self._previous_emotion = Emotion.HAPPY  # For smooth transitions
        self._transition_start = 0.0  # When transition began
        self._transition_duration = 1.5  # Seconds for smooth emotion blend

    def update(self, event: str = None, transcript: str = None):
        """Update emotion based on events and conversation."""
        with self._lock:
            self._update_internal(event, transcript)

    def _update_internal(self, event: str = None, transcript: str = None):
        """Internal update — must be called with self._lock held."""
        now = time.time()
        idle_time = now - self._last_interaction

        # Decay intensity over time (emotions fade — faster for Neuro-sama volatility)
        time_since_change = now - self._last_change
        if time_since_change > 20 and self.intensity > 0.3:
            self.intensity = max(0.3, self.intensity - 0.05 * (time_since_change / 60))

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
                self.current = Emotion.FRUSTRATED
                self.intensity = 0.7
            elif any(w in lower for w in ["oops", "my bad", "sorry", "awkward", "embarrassing", "cringe"]):
                self.current = Emotion.EMBARRASSED
                self.intensity = 0.6
            elif any(w in lower for w in ["cool", "nice", "sweet", "fire", "lit", "sick", "dope"]):
                self.current = Emotion.HAPPY
                self.intensity = 0.8
            elif any(w in lower for w in ["music", "song", "sing", "dance", "dj", "beat"]):
                self.current = Emotion.EXCITED
                self.intensity = 0.8
            elif any(w in lower for w in ["bye", "goodbye", "leaving", "going", "gotta go"]):
                self.current = Emotion.HAPPY
                self.intensity = 0.6
            elif any(w in lower for w in ["peach", "princess", "daisy", "rosalina"]):
                self.current = Emotion.LOVING
                self.intensity = 0.8
            elif any(w in lower for w in ["bowser", "villain", "enemy", "bad guy", "boss fight"]):
                self.current = Emotion.EXCITED
                self.intensity = 0.85
            elif any(w in lower for w in ["gross", "ew", "disgusting", "nasty", "yuck"]):
                self.current = Emotion.SURPRISED
                self.intensity = 0.6
            elif any(w in lower for w in ["please", "pretty please", "come on", "begging"]):
                self.current = Emotion.MISCHIEVOUS
                self.intensity = 0.7
            elif any(w in lower for w in ["roast", "insult", "diss", "burn me", "make fun"]):
                self.current = Emotion.MISCHIEVOUS
                self.intensity = 0.9
            elif any(w in lower for w in ["epic", "legendary", "incredible", "unbelievable"]):
                self.current = Emotion.EXCITED
                self.intensity = 0.9
            elif any(w in lower for w in ["game over", "warp zone", "konami", "power up"]):
                self.current = Emotion.EXCITED
                self.intensity = 0.85
            elif any(w in lower for w in ["cheers", "toast", "raise a glass", "celebration"]):
                self.current = Emotion.HAPPY
                self.intensity = 0.9
            elif any(w in lower for w in ["proud", "hero", "champion", "number one", "the best", "nailed it", "crushed it"]):
                self.current = Emotion.PROUD
                self.intensity = 0.85

        # Track when emotion last changed for decay
        if transcript or event:
            old_emotion = self._previous_emotion
            if self.current != old_emotion:
                self._previous_emotion = old_emotion
                self._transition_start = time.time()
            self._last_change = time.time()

        # Negative mood tracking for cheer-up system
        _NEGATIVE_EMOTIONS = {Emotion.WORRIED, Emotion.FRUSTRATED, Emotion.BORED}
        if self.current in _NEGATIVE_EMOTIONS:
            if self._negative_mood_start == 0.0:
                self._negative_mood_start = time.time()
        else:
            self._negative_mood_start = 0.0

        # Update rolling sentiment from transcript
        if transcript and len(transcript.split()) >= 2:
            score = self._score_sentiment(transcript)
            self._sentiment_history.append((time.time(), score))
            # Keep only last 10 entries
            if len(self._sentiment_history) > 10:
                self._sentiment_history = self._sentiment_history[-10:]
            # Update conversation energy based on message frequency
            if len(self._sentiment_history) >= 2:
                time_gap = self._sentiment_history[-1][0] - self._sentiment_history[-2][0]
                if time_gap < 10:
                    self._conversation_energy = min(1.0, self._conversation_energy + 0.1)
                elif time_gap > 30:
                    self._conversation_energy = max(0.2, self._conversation_energy - 0.1)

        if DEBUG_EMOTION:
            logger.info(f"[DEBUG_EMOTION] update: {self.current} (intensity={self.intensity:.1f})")

    def get_voice_params(self) -> dict:
        """Get TTS voice parameters for current emotion."""
        with self._lock:
            return EMOTION_VOICE_MAP.get(self.current, EMOTION_VOICE_MAP[Emotion.NEUTRAL])

    def get_prompt_addition(self) -> str:
        """Get text to add to LLM prompt about current emotion. Kept short for small models."""
        with self._lock:
            desc = EMOTION_DESCRIPTIONS.get(self.current, "")
            prompt = f"[MOOD: {self.current.upper()}]: {desc}"
            # Only add energy/sentiment hints if they're notable
            if self._conversation_energy >= 0.8:
                prompt += " HIGH energy!"
            elif self._conversation_energy <= 0.3:
                prompt += " Chill vibes."
            if self._sentiment_history:
                total = 0.0
                weight = 0.0
                for i, (_, score) in enumerate(self._sentiment_history):
                    w = 1.0 + i * 0.5
                    total += score * w
                    weight += w
                avg = total / weight if weight else 0.0
                if avg < -0.3:
                    prompt += " Lift the mood!"
                elif avg > 0.5:
                    prompt += " Great vibes!"
            return prompt

    def _score_sentiment(self, text: str) -> float:
        """Score a message's sentiment from -1.0 (negative) to +1.0 (positive)."""
        lower = text.lower()
        score = 0.0
        positive_words = ["love", "awesome", "amazing", "great", "best", "happy", "fun", "cool",
                          "nice", "sweet", "thanks", "good", "wow", "excited", "beautiful",
                          "wonderful", "perfect", "excellent", "fantastic", "incredible"]
        negative_words = ["hate", "sucks", "stupid", "annoying", "worst", "ugly", "terrible",
                          "boring", "sad", "angry", "mad", "frustrated", "ugh", "gross",
                          "disgusting", "awful", "horrible", "bad", "upset", "stressed"]
        for w in positive_words:
            if w in lower:
                score += 0.2
        for w in negative_words:
            if w in lower:
                score -= 0.2
        return max(-1.0, min(1.0, score))

    def get_rolling_sentiment(self) -> float:
        """Get the average sentiment over recent exchanges. -1.0 to +1.0."""
        with self._lock:
            if not self._sentiment_history:
                return 0.0
            # Weight recent entries more heavily
            total = 0.0
            weight = 0.0
            for i, (_, score) in enumerate(self._sentiment_history):
                w = 1.0 + i * 0.5  # Later entries get more weight
                total += score * w
                weight += w
            return total / weight if weight else 0.0

    def get_personality_modifier(self) -> str:
        """Return a short personality amplifier based on emotion + intensity."""
        with self._lock:
            if self.intensity < 0.4:
                return ""
            modifiers = {
                Emotion.EXCITED: "MAXIMUM ENERGY! Go absolutely WILD! Wahoo!",
                Emotion.MISCHIEVOUS: "Full chaos mode! Be a lovable menace!",
                Emotion.BORED: "So bored you're becoming unhinged! Be dramatically sarcastic!",
                Emotion.PROUD: "You're the GREATEST plumber who ever lived! FLEX!",
                Emotion.LOVING: "Your heart is SO full! Be genuinely warm and sweet!",
                Emotion.SLEEPY: "Can barely keep eyes open... mumble... trail off mid-sentence...",
                Emotion.FRUSTRATED: "EVERYTHING is annoying right now! Channel it into comedy!",
                Emotion.SURPRISED: "NOTHING could have prepared you for this! DRAMATIC GASP!",
                Emotion.CONFUSED: "Reality is breaking! Nothing makes sense! Question everything!",
                Emotion.EMBARRASSED: "SO AWKWARD! Try to recover but make it worse!",
            }
            mod = modifiers.get(self.current, "")
            return f"[PERSONALITY]: {mod}" if mod and self.intensity >= 0.5 else ""

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
            Emotion.PROUD: "proud",
            Emotion.FRUSTRATED: "frustrated",
            Emotion.EMBARRASSED: "embarrassed",
            Emotion.NEUTRAL: "idle",
            # New emotions (13 → 26)
            Emotion.ANNOYED: "annoyed",
            Emotion.LAUGHING: "laughing",
            Emotion.SAD: "sad",
            Emotion.ANGRY: "angry",
            Emotion.NERVOUS: "nervous",
            Emotion.SCARED: "scared",
            Emotion.LOVE: "love",
            Emotion.DISGUSTED: "disgusted",
            Emotion.DETERMINED: "determined",
            Emotion.CURIOUS: "curious",
            Emotion.THINKING: "thinking",
            Emotion.SHOCKED: "shocked",
            Emotion.IDEA: "idea",
        }
        return mapping.get(self.current, "idle")

    def should_cheer_up(self) -> str | None:
        """If user has been in negative mood for 2+ minutes, suggest Mario cheer them up."""
        with self._lock:
            if self._negative_mood_start == 0.0:
                return None
            negative_duration = time.time() - self._negative_mood_start
            if negative_duration < 120:  # 2 minutes
                return None
            # Generate cheer-up hint based on current negative emotion
            cheer_hints = {
                Emotion.WORRIED: "They've been worried for a while. Try to reassure them! Tell a silly story or compliment them!",
                Emotion.FRUSTRATED: "They're frustrated! Time to turn it around — be extra silly, tell a joke, or challenge them to something fun!",
                Emotion.BORED: "They seem bored! SHAKE THINGS UP! Do something unexpected, propose a wild game, or tell a crazy story!",
            }
            hint = cheer_hints.get(self.current)
            if hint:
                # Reset so we don't spam the same hint
                self._negative_mood_start = time.time()
                return f"[CHEER UP]: {hint}"
            return None

    def get_emotion_particle(self) -> str | None:
        """Get a particle effect matching the current emotion (fallback if no keyword match)."""
        with self._lock:
            if self.intensity < 0.5:
                return None
            _EMOTION_PARTICLES = {
                Emotion.HAPPY: "sparkle",
                Emotion.EXCITED: "stars",
                Emotion.LOVING: "hearts",
                Emotion.MISCHIEVOUS: "fire",
                Emotion.PROUD: "confetti",
                Emotion.SURPRISED: "stars",
                Emotion.EMBARRASSED: "rain",
                Emotion.FRUSTRATED: "fire",
                Emotion.WORRIED: "rain",
            }
            return _EMOTION_PARTICLES.get(self.current)

    def update_from_llm_sentiment(self, emotion: str, energy: float):
        """Update emotion and energy from LLM-extracted sentiment data."""
        with self._lock:
            if DEBUG_EMOTION:
                logger.info(f"[DEBUG_EMOTION] update_from_llm_sentiment: emotion={emotion}, energy={energy}")
            
            # Update current emotion if it's a valid emotion
            known = {v for k, v in vars(Emotion).items() if not k.startswith("_") and isinstance(v, str)}
            if emotion in known:
                self._previous_emotion = self.current
                self.current = emotion
                self._last_change = time.time()
                
            # Update conversation energy with weighted average
            # Recent energy values get more weight 
            self._conversation_energy = (self._conversation_energy * 0.7) + (energy * 0.3)
            self._conversation_energy = max(0.0, min(1.0, self._conversation_energy))
            
            # Update intensity based on energy level
            self.intensity = max(0.3, min(1.0, energy * 0.8 + 0.2))
            
            if DEBUG_EMOTION:
                logger.info(f"[DEBUG_EMOTION] updated to {self.current}, conversation_energy={self._conversation_energy:.2f}")

    def get_energy_running_average(self) -> float:
        """Get the running average energy level (0.0-1.0)."""
        with self._lock:
            return self._conversation_energy

    def should_influence_idle_behavior(self) -> dict:
        """Return behavior modifications based on current energy levels."""
        with self._lock:
            energy = self._conversation_energy
            
            # High energy (>0.7) - more animated idle behavior  
            if energy > 0.7:
                return {
                    "idle_cadence_multiplier": 1.5,  # Faster pose changes
                    "pose_energy_boost": "high",
                    "animation_intensity": "energetic"
                }
            # Low energy (<0.3) - calmer behavior
            elif energy < 0.3:
                return {
                    "idle_cadence_multiplier": 0.6,  # Slower pose changes
                    "pose_energy_boost": "low", 
                    "animation_intensity": "calm"
                }
            # Normal energy
            else:
                return {
                    "idle_cadence_multiplier": 1.0,
                    "pose_energy_boost": "normal",
                    "animation_intensity": "normal"
                }
