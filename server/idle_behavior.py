"""Idle behavior and autonomous actions for the party bot."""

import os
import random
import time
import logging
from datetime import datetime

DEBUG_IDLE = os.environ.get("DEBUG_IDLE", "").lower() in ("1", "true", "yes")
logger = logging.getLogger(__name__)

# ── Memorial text constants (no ellipsis — TTS convention) ──────────────
MEMORIAL_ANNOUNCEMENT = (
    "*removes hat and holds it to chest* "
    "Hey everyone, can I have your attention for just a moment? "
    "Tonight we are celebrating Jacob's birthday, but I want us to take "
    "a special moment to honor someone very important to this family."
)

MEMORIAL_SILENCE = (
    "Lisa Webb was Jacob's beloved aunt. "
    "She was born on August 17th, 1968, and she passed away on March 23rd, 2023. "
    "She meant the world to this family, and her light touched everyone who knew her. "
    "Let us take a moment of silence in her memory."
)

MEMORIAL_TOAST = (
    "*puts hat back on with a warm smile* "
    "Alright everyone, Aunt Lisa would not want us to be sad! "
    "She would want us to CELEBRATE! So right now, everybody grab a drink! "
    "We are taking a shot for Aunt Lisa! "
    "To Lisa Webb, the kind of person who made every room brighter! "
    "Ready? One, two, three, CHEERS!"
)

MEMORIAL_FADEOUT = (
    "That was beautiful, everyone. Lisa would be so proud. "
    "Now, let us keep this party going for Jacob! "
    "Let's go!"
)


# All idle message content now lives in per-character YAML files:
# characters/<name>/idle/messages.yaml


class IdleBehavior:
    """Manages character's autonomous behavior when idle."""

    def __init__(self, character_loader=None):
        self._last_idle_action = time.time()
        self._idle_interval = 15
        self._action_count = 0
        self._used_mumbles = set()
        self._used_jokes = set()
        self._used_trivia = set()
        self._recently_used = []  # Track last N choices to avoid repeats
        self._used_items = {}  # pool_name -> set of recently used items
        self._global_recent = []  # Global dedup: tracks last 50 messages sent regardless of pool
        self._last_time_comment_at = 0  # Cooldown for time-based comments

        # Load character-specific idle pools if available
        self._char_pools = {}
        self._char_name = "Mario"
        if character_loader is not None:
            self._char_name = character_loader.name
            self._char_pools = character_loader.get_idle_messages()
            if self._char_pools:
                logger.info(f"[idle_behavior] Loaded {sum(len(v) for v in self._char_pools.values() if isinstance(v, list))} character idle messages for {self._char_name}")

        # Resolve pools: character-specific overrides > empty defaults
        # All character content lives in characters/<name>/idle/messages.yaml
        self._mumbles = self._char_pools.get("mumbles", [])
        self._jokes = self._char_pools.get("jokes", [])
        self._songs = self._char_pools.get("songs", [])
        self._trivia = self._char_pools.get("trivia_idle", [])
        self._plumbing = self._char_pools.get("deep_thoughts", [])
        self._challenges = self._char_pools.get("challenges", [])
        self._compliments = self._char_pools.get("compliments", [])
        self._handwash = self._char_pools.get("handwash", [])
        self._noise_reactions = self._char_pools.get("noise_reactions", [])
        self._time_comments = self._char_pools.get("time_comments", [])
        self._dj_announcements = self._char_pools.get("dj_announcements", [])
        self._lonely_mild = self._char_pools.get("lonely_mild", [])
        self._lonely_medium = self._char_pools.get("lonely_medium", [])
        self._lonely_deep = self._char_pools.get("lonely_deep", [])

        # Per-category rotation tracking
        self._joke_index = random.randint(0, max(1, len(self._jokes)) - 1)
        self._trivia_index = random.randint(0, max(1, len(self._trivia)) - 1)
        self._song_index = random.randint(0, max(1, len(self._songs)) - 1)
        self._challenge_index = random.randint(0, max(1, len(self._challenges)) - 1)
        self._compliment_index = random.randint(0, max(1, len(self._compliments)) - 1)
        self._hand_wash_index = random.randint(0, max(1, len(self._handwash)) - 1)
        # Memorial event tracking (fires once per party session)
        self._memorial_delivered = False
        self._memorial_shot_delivered = False
        self._party_start_time = time.time()
        # Loneliness arc tracking
        self._alone_since = time.time()  # When the last visitor left
        self._loneliness_level = 0  # 0=normal, 1=mild, 2=medium, 3=deep
        self._last_lonely_msg_time = 0.0

    def visitor_arrived(self):
        """Call when a visitor enters — resets loneliness arc."""
        self._loneliness_level = 0
        if DEBUG_IDLE:
            mins_alone = (time.time() - self._alone_since) / 60
            logger.info(f"[DEBUG_IDLE] visitor_arrived: was alone {mins_alone:.1f}min (level was {self._loneliness_level})")

    def visitor_left(self):
        """Call when a visitor exits — starts loneliness timer."""
        self._alone_since = time.time()
        self._loneliness_level = 0
        if DEBUG_IDLE:
            logger.info("[DEBUG_IDLE] visitor_left: loneliness timer started")

    def get_loneliness_greeting_boost(self) -> str | None:
        """Get an extra-enthusiastic greeting if the character has been alone a long time."""
        mins_alone = (time.time() - self._alone_since) / 60
        if mins_alone < 5:
            return None
        if mins_alone < 15:
            return random.choice([
                "FINALLY! A human! I was starting to talk to the soap!",
                "Oh thank goodness, someone's here! I was getting lonely!",
                "A visitor! I was just about to start a one-man show!",
            ])
        if mins_alone < 30:
            return random.choice([
                "OH MY GOSH A REAL PERSON! I've been in here SO LONG! You have NO idea how happy I am to see you!",
                "A VISITOR! I was THIS close to befriending the toilet brush! You saved me!",
                "FINALLY! I was starting to think everyone forgot about me in here! Best moment of my LIFE!",
            ])
        return random.choice([
            "IS THAT... A HUMAN?! *tears of joy* I thought you'd NEVER come! I named all the tiles! STEVE SAYS HI!",
            "A REAL ACTUAL PERSON! I was about to file a missing person report on MYSELF!",
            "YOU CAME! You ACTUALLY came! I have SO much to tell you! I've had a LOT of time to think in here!",
        ])

    def get_lonely_action(self) -> str | None:
        """Get a loneliness-arc message based on how long the character has been alone.

        Returns None if not time for a lonely message yet (uses own cooldown).
        """
        now = time.time()
        mins_alone = (now - self._alone_since) / 60

        # Not alone long enough for loneliness arc
        if mins_alone < 5:
            self._loneliness_level = 0
            return None

        # Loneliness messages have their own cooldown (90s between each)
        if now - self._last_lonely_msg_time < 90:
            return None

        if mins_alone < 15:
            self._loneliness_level = 1
            pool = self._lonely_mild
            pool_name = "lonely_mild"
        elif mins_alone < 30:
            self._loneliness_level = 2
            pool = self._lonely_medium
            pool_name = "lonely_medium"
        else:
            self._loneliness_level = 3
            pool = self._lonely_deep
            pool_name = "lonely_deep"

        self._last_lonely_msg_time = now
        choice = self._pick_unique(pool, pool_name)
        if DEBUG_IDLE:
            logger.info(f"[DEBUG_IDLE] get_lonely_action: level={self._loneliness_level} mins={mins_alone:.1f} '{choice[:50]}...'")
        return choice

    def _pick_unique(self, pool: list, pool_name: str = None) -> str:
        """Pick a random item from pool, avoiding recent repeats (per-pool + global)."""
        if not pool:
            return "..."
        if pool_name is None:
            # Legacy behavior for callers that don't pass pool_name
            fresh = [o for o in pool if o not in self._recently_used and o not in self._global_recent]
            if not fresh:
                fresh = [o for o in pool if o not in self._global_recent]
            if not fresh:
                self._recently_used.clear()
                fresh = pool
            choice = random.choice(fresh)
            self._recently_used.append(choice)
            if len(self._recently_used) > 25:
                self._recently_used = self._recently_used[-25:]
            self._global_recent.append(choice)
            if len(self._global_recent) > 15:
                self._global_recent = self._global_recent[-15:]
            return choice
        used = self._used_items.get(pool_name, set())
        # Exclude both pool-used AND globally-recent items
        available = [item for item in pool if item not in used and item not in self._global_recent]
        if not available:
            available = [item for item in pool if item not in used]
        if not available:
            self._used_items[pool_name] = set()
            available = [item for item in pool if item not in self._global_recent]
        if not available:
            available = pool
        choice = random.choice(available)
        if pool_name not in self._used_items:
            self._used_items[pool_name] = set()
        self._used_items[pool_name].add(choice)
        # Reset when 60% of pool has been used to allow earlier re-entry
        if len(self._used_items[pool_name]) >= len(pool) * 0.6:
            self._used_items[pool_name] = set()
        # Track in global recent
        self._global_recent.append(choice)
        if len(self._global_recent) > 50:
            self._global_recent = self._global_recent[-50:]
        return choice

    def get_idle_action(self, phase=None) -> str:
        """Get an idle action/mumble if enough time has passed. Returns None if not time yet.

        Args:
            phase: Optional Phase enum from night_progression. Adjusts tone:
                1=WARM_UP (friendly), 2=PARTY_MODE (energetic), 3=UNHINGED (chaotic), 4=WIND_DOWN (nostalgic).
        """
        now = time.time()
        if now - self._last_idle_action < self._idle_interval:
            return None

        self._last_idle_action = now
        self._action_count += 1
        # Gradually slow down: 15s → 17s → 19s → ... → 45s max (slower growth for more variety)
        self._idle_interval = min(45, 15 + self._action_count * 2)

        hour = time.localtime().tm_hour

        # Phase-aware category weighting
        phase_val = int(phase) if phase is not None else None

        # Rotate through categories for variety
        _categories = [
            ("mumbles", list(self._mumbles)),
            ("songs", list(self._songs)),
            ("jokes", list(self._jokes)),
            ("trivia", list(self._trivia + self._plumbing)),
            ("social", list(self._challenges + self._compliments)),
        ]
        cat_name, options = random.choice(_categories)

        # Phase-driven tone adjustments
        if phase_val == 1:  # WARM_UP — heavier on compliments and friendly content
            options.extend(self._compliments * 2)
        elif phase_val == 2:  # PARTY_MODE — more songs and energy
            options.extend(self._songs * 2)
            options.extend(self._dj_announcements)
        elif phase_val == 3:  # UNHINGED — jokes and wild mumbles dominate
            options.extend(self._jokes * 3)
        elif phase_val == 4:  # WIND_DOWN — trivia and sentimental content
            options.extend(self._trivia * 2)
            options.extend(self._compliments)

        # Add time-appropriate comments
        if 18 <= hour < 21:
            options.extend(self._time_comments.get("early_evening", []))
        elif 21 <= hour < 24:
            options.extend(self._time_comments.get("peak_party", []))
        elif 0 <= hour < 2:
            options.extend(self._time_comments.get("late_night", []))
        elif 2 <= hour < 6:
            options.extend(self._time_comments.get("very_late", []) * 2)

        choice = self._pick_unique(options, pool_name=cat_name)
        if DEBUG_IDLE:
            logger.info(f"[DEBUG_IDLE] get_idle_action: phase={phase_val} '{choice[:50]}...'")
        return choice

    def get_joke(self) -> str:
        if not self._jokes:
            return None
        joke = self._jokes[self._joke_index % len(self._jokes)]
        self._joke_index += 1
        return joke

    def get_trivia(self) -> str:
        combined = self._trivia + self._plumbing
        if not combined:
            return None
        fact = combined[self._trivia_index % len(combined)]
        self._trivia_index += 1
        return fact

    def get_song(self) -> str:
        if not self._songs:
            return None
        song = self._songs[self._song_index % len(self._songs)]
        self._song_index += 1
        return song

    def get_noise_reaction(self) -> str:
        if not self._noise_reactions:
            return None
        return self._pick_unique(self._noise_reactions, "noise_reactions")

    def get_challenge(self) -> str:
        if not self._challenges:
            return None
        challenge = self._challenges[self._challenge_index % len(self._challenges)]
        self._challenge_index += 1
        return challenge

    def get_compliment(self) -> str:
        if not self._compliments:
            return None
        compliment = self._compliments[self._compliment_index % len(self._compliments)]
        self._compliment_index += 1
        return compliment

    def get_idle_gossip_recap(self, party_gossip) -> str | None:
        """When alone, the character reflects on the party gossip out loud.
        Takes the party_gossip instance and generates a self-talk line."""
        if party_gossip is None:
            return None

        options = []

        # Trending topics
        trending = [(t, len(ids)) for t, ids in party_gossip._topic_mentions.items() if len(ids) >= 2]
        for topic, count in trending[:3]:
            options.append(f"*talking to self* Everyone keeps talking about {topic}! {count} people mentioned it!")
            options.append(f"*musing* If I hear one more person talk about {topic}... actually, I love it! Keep going!")

        # Rivalries
        for r in party_gossip._rivalries[-3:]:
            options.append(f"*chuckling* The {r[0]} vs {r[1]} rivalry about {r[2]} is the best drama tonight!")
            options.append(f"*dramatic whisper* {r[0]} and {r[1]} still disagree about {r[2]}... this is better than a soap opera!")

        # Alliances
        for a in party_gossip._alliances[-3:]:
            options.append(f"*happy sigh* {a[0]} and {a[1]} bonding over {a[2]}... friendship is beautiful!")

        # Guest titles
        for gid, title in list(party_gossip._guest_titles.items())[-3:]:
            name = party_gossip._guest_names.get(gid)
            if name:
                options.append(f"*polishing imaginary trophy* {name}, the '{title}'... what a legend!")

        if not options:
            return None
        return random.choice(options)

    def get_hand_wash_reminder(self) -> str:
        if not self._handwash:
            return None
        reminder = self._handwash[self._hand_wash_index % len(self._handwash)]
        self._hand_wash_index += 1
        return reminder

    def reset_timer(self):
        """Reset idle timer (called when someone interacts)."""
        self._last_idle_action = time.time()
        self._idle_interval = 15
        self._action_count = 0

    def check_memorial_event(self, current_speaker_name: str = None) -> tuple[str, str] | None:
        """Check if it's time for the Lisa Webb memorial moment.

        Returns (memorial_message, sfx_event_name) tuple, or None if not time yet.
        Prefers firing when Jacob is in the room, but fires after 90 min regardless.
        The moment of silence fires first, then the shot on the next idle cycle.
        """
        if self._memorial_delivered and self._memorial_shot_delivered:
            return None

        party_minutes = (time.time() - self._party_start_time) / 60

        # Check if the birthday person (Jacob) is present
        jacob_present = False
        if current_speaker_name:
            name_lower = current_speaker_name.lower()
            jacob_present = any(alias in name_lower for alias in
                                ["jacob", "jake", "hoppenstedt", "birthday boy"])

        # Timing strategy:
        #   - 45+ min AND Jacob present → fire immediately (ideal)
        #   - 90+ min regardless → fire anyway (don't wait forever)
        #   - < 45 min → never fire
        if party_minutes < 45:
            return None
        if not jacob_present and party_minutes < 90:
            return None

        # Try to load memorial info from VIP knowledge
        try:
            import vip_knowledge
            memorial = vip_knowledge.get_memorial_info("Jacob")
        except Exception:
            memorial = None

        if not memorial:
            # Fallback hardcoded memorial
            memorial = {
                "person": "Lisa Webb",
                "relationship": "Jacob's aunt",
                "born": "August 17, 1968",
                "passed": "March 23, 2023",
            }

        if not self._memorial_delivered:
            # Phase 1: Moment of silence
            self._memorial_delivered = True
            msg = (
                f"*Mario removes his hat and holds it to his chest* "
                f"Hey everyone, can I have your attention for just a moment? "
                f"Tonight we're celebrating Jacob's birthday, but I want us to take a moment "
                f"to remember someone very special, {memorial['person']}, {memorial['relationship']}. "
                f"She passed away in 2023, and she meant the world to this family. "
                f"Let's have a moment of silence for Aunt Lisa. "
                f"*bows head in silence*"
            )
            return (msg, "memorial")
        elif not self._memorial_shot_delivered:
            # Phase 2: Shot dedication (fires on next idle cycle after the silence)
            self._memorial_shot_delivered = True
            msg = (
                f"*puts hat back on with a warm smile* "
                f"Alright everyone — Aunt Lisa wouldn't want us to be sad! "
                f"She'd want us to CELEBRATE! So right now, everybody grab a drink — "
                f"we're taking a shot for Aunt Lisa! 🥂 "
                f"To Lisa Webb — the kind of person who made every room brighter! "
                f"Ready? One, two, three, CHEERS! Wahoo! "
                f"That one was for you, Aunt Lisa! Now let's-a party!"
            )
            return (msg, "toast")

        return None

    def get_long_stay_comment(self, minutes: float) -> str:
        """Get a comment about someone taking a long time."""
        if minutes < 3:
            return None
        elif minutes < 5:
            options = [
                "Taking your time, eh? No rush! Mario will-a wait!",
                "Still here? Must be-a comfy in here!",
                "Enjoying the ambiance? I don't blame you!",
                "This-a bathroom has great vibes, no?",
                "You know, in the Mushroom Kingdom, we don't rush bathroom breaks!",
                "I once spent 3 hours in Bowser's bathroom... long story!",
                "Need anything? Magazine? Mushroom? Star power?",
            ]
        elif minutes < 10:
            options = [
                f"Mama mia! {int(minutes)} minutes! Everything okay in there?",
                f"You've been here {int(minutes)} minutes! That's-a new record!",
                f"{int(minutes)} minutes?! You could've-a beaten World 1-1 by now!",
                f"Wow, {int(minutes)} minutes! Luigi would be-a worried by now!",
                f"At {int(minutes)} minutes, you're practically a bathroom resident!",
                f"Fun fact: In {int(minutes)} minutes, I can eat-a 47 mushrooms!",
            ]
        else:
            options = [
                f"Wahoo! {int(minutes)} minutes?! You should-a see a doctor! Ha ha, just kidding!",
                f"Still going strong after {int(minutes)} minutes! You're-a champion!",
                f"{int(minutes)} minutes! I think you live-a here now! Welcome home!",
                f"{int(minutes)} minutes?! Even Bowser doesn't stay this long!",
                f"After {int(minutes)} minutes, I'm-a starting to think you forgot about the party!",
                f"Legend says after {int(minutes)} minutes in this bathroom, you unlock a secret level!",
            ]
        return self._pick_unique(options)

    def get_contextual_idle(self, conversation_history: list) -> str | None:
        """Generate an idle phrase that riffs on recent conversation topics.
        
        Returns a context-aware idle phrase, or None if no good context available.
        Uses _global_recent dedup to avoid repeating messages.
        """
        if not conversation_history or len(conversation_history) < 2:
            return None
        
        # Look at the last few user messages for topics to riff on
        recent_user_msgs = [
            msg["content"] for msg in conversation_history[-8:]
            if msg.get("role") == "user" and len(msg.get("content", "")) > 5
        ]
        if not recent_user_msgs:
            return None
        
        last_msg = recent_user_msgs[-1].lower()
        
        # Collect all matching options, then pick one that hasn't been used recently
        options = []
        
        if any(w in last_msg for w in ["food", "eat", "hungry", "pizza", "pasta", "cook", "dinner", "lunch"]):
            options = [
                "Thinking about that food talk is making me hungry... Mama mia, where's-a the snack table?",
                "I can't stop thinking about pasta now! This is-a your fault!",
                "My stomach is-a rumbling! That food conversation got to me!",
            ]
        elif any(w in last_msg for w in ["music", "song", "dance", "dj", "beat", "band"]):
            options = [
                "I can still hear the music from out there! Makes me want to dance-a!",
                "That song they mentioned... it's-a stuck in my head now!",
                "We were just talking about music... this bathroom has-a great acoustics for singing!",
            ]
        elif any(w in last_msg for w in ["work", "job", "boss", "office", "meeting"]):
            options = [
                "They mentioned work... ha! MY job is guarding this bathroom! Best gig ever!",
                "Work talk at a party? Mama mia! This is-a party time, not meeting time!",
                "At least MY boss is Princess Peach! She gives me cake!",
            ]
        elif any(w in last_msg for w in ["game", "play", "gaming", "video game", "nintendo"]):
            options = [
                "Gaming talk! That's-a my specialty! I've been in games for 40 years!",
                "They mentioned games... I wonder if they've played MY games! Of course they have!",
                "I should challenge the next person to a Mario trivia battle!",
            ]
        elif any(w in last_msg for w in ["dog", "cat", "pet", "animal"]):
            options = [
                "Pets! You know, Yoshi is basically my pet dinosaur. Best boy!",
                "Thinking about that pet talk... I miss-a Yoshi! He eats everything though!",
                "I wonder if Chain Chomps count as-a pets? They're very... bitey!",
            ]
        elif any(w in last_msg for w in ["drink", "beer", "wine", "drunk", "shots"]):
            options = [
                "All this drink talk... Mario prefers-a mushroom tea! It makes you grow!",
                "Someone was talking about drinks... the water in here is-a very refreshing too!",
                "I hope everyone's staying hydrated! Water is-a the real power-up!",
            ]
        elif any(w in last_msg for w in ["love", "boyfriend", "girlfriend", "date", "crush", "relationship"]):
            options = [
                "Love talk at a party! How romantic! I've been saving Princess Peach for decades!",
                "Romance... Peach is-a always in another castle! Story of my life!",
                "They were talking about love... Mama mia, now I'm-a getting sentimental!",
            ]
        
        if options:
            # Filter out recently used messages
            fresh = [o for o in options if o not in self._global_recent]
            if not fresh:
                # All used recently — clear and allow any
                fresh = options
            choice = random.choice(fresh)
            self._global_recent.append(choice)
            if len(self._global_recent) > 50:
                self._global_recent = self._global_recent[-50:]
            return choice
        
        # Generic conversation callback (30% chance)
        if random.random() < 0.3:
            generic = [
                "I'm still thinking about what that person said... interesting!",
                "People at this party are-a so interesting! I love hearing everyone's stories!",
                "The conversations in this bathroom are-a better than most TV shows!",
                "I should remember to ask the next person about that too!",
            ]
            fresh = [g for g in generic if g not in self._global_recent]
            if not fresh:
                fresh = generic
            choice = random.choice(fresh)
            self._global_recent.append(choice)
            if len(self._global_recent) > 50:
                self._global_recent = self._global_recent[-50:]
            return choice
        
        return None

    def get_time_observation(self):
        """Return a time-specific party observation or None."""
        hour = datetime.now().hour
        if 0 <= hour < 2:
            observations = [
                "It's past midnight! The party is REALLY getting started now! Wahoo!",
                "After midnight — this is when the real adventures begin! Like World 8!",
                "Mama mia, it's late! But the party energy is at Super Star level!",
            ]
        elif 2 <= hour < 4:
            observations = [
                "It's-a 2 AM! You party animals are LEGENDARY! Even Bowser went to bed!",
                "The clock says it's late but your energy says otherwise! I'm-a impressed!",
                "At this hour, even the Boos are sleeping! But not us! WAHOO!",
            ]
        elif 4 <= hour < 6:
            observations = [
                "Is that... sunrise?! We partied until SUNRISE! New record! Better than any speedrun!",
                "Four AM! We've officially entered bonus round territory! Extra life to everyone still here!",
                "The birds are starting to sing! But can they sing as good as Mario? I think-a not!",
            ]
        elif 6 <= hour < 12:
            observations = [
                "Good morning! Wait, are we still partying or is this a new party? Either way, WAHOO!",
                "Morning already? Time flies when you're having fun in the bathroom!",
            ]
        elif 18 <= hour < 21:
            observations = [
                "Early evening! The party is just warming up! Like the first level of a new game!",
                "The night is young and so are we! Well, I'm-a from 1985, but who's counting!",
            ]
        elif 21 <= hour < 24:
            observations = [
                "Prime party hours! This is when the magic happens! Fire Flower energy!",
                "The party is in full swing! More energy than a room full of Bob-ombs!",
            ]
        else:
            return None
        return random.choice(observations)

    def get_time_comment(self) -> str:
        """Get a comment based on the current time of day, with deduplication and cooldown."""
        now = time.time()
        if now - self._last_time_comment_at < 90:
            return None
        hour = datetime.now().hour
        # Map hour ranges to time_comments keys
        if 0 <= hour < 4:
            key = "very_late"
        elif 4 <= hour < 7:
            key = "very_late"
        elif 7 <= hour < 12:
            key = "early_evening"
        elif 12 <= hour < 17:
            key = "early_evening"
        elif 17 <= hour < 21:
            key = "early_evening"
        elif 21 <= hour <= 23:
            key = "peak_party"
        else:
            return None
        pool = self._time_comments.get(key, [])
        if not pool:
            return None
        result = self._pick_unique(pool, "time_comments")
        self._last_time_comment_at = time.time()
        return result

    def get_party_stage(self, party_minutes: float) -> str:
        """Get a comment about the current party stage."""
        if party_minutes < 30:
            return random.choice([
                "The party just-a started! We're warming up!",
                "Still early! The best is yet to come, wahoo!",
            ])
        elif party_minutes < 120:
            return random.choice([
                "We're in peak party mode! The bathroom is-a hot tonight!",
                "This is the golden hour! Everyone's having fun!",
            ])
        elif party_minutes < 240:
            return random.choice([
                "The party's been going strong for hours! Legendary!",
                "Marathon party! Mario is-a impressed!",
            ])
        else:
            return random.choice([
                "This party is ETERNAL! We've been at it for hours!",
                "Are we... are we still partying? Mama mia, what a night!",
            ])

    def get_gossip_idle(self) -> str | None:
        """Mario gossips about earlier party guests when alone.

        Pulls real conversation snippets from the memory DB and wraps them
        in Mario-flavored gossip commentary. Returns None if no material.
        """
        try:
            import memory as _mem
            conn = _mem._get_conn()
            rows = conn.execute(
                "SELECT p.name, c.content FROM conversations c "
                "JOIN people p ON c.person_id = p.id "
                "WHERE c.role = 'user' AND length(c.content) >= 10 "
                "ORDER BY c.timestamp DESC LIMIT 20"
            ).fetchall()
            if not rows:
                return None

            guest_name, content = random.choice(rows)
            snippet = content[:60].rstrip()
            if len(content) > 60:
                snippet += "..."

            templates = [
                f"Earlier, {guest_name} told me '{snippet}' Can you BELIEVE that?!",
                f"You know what {guest_name} said before? '{snippet}' WILD!",
                f"Between you and me... {guest_name} was talking about some CRAZY stuff earlier!",
                f"I've been thinking about what {guest_name} said... '{snippet}' Still processing that one!",
                f"*whispers* {guest_name} told me something earlier... I probably shouldn't repeat it... but '{snippet}'",
                f"Nobody's here so I can say it — {guest_name} really said '{snippet}' Ha!",
                f"The things people tell Mario! {guest_name} goes '{snippet}' Mama mia!",
            ]

            choice = random.choice(templates)
            if DEBUG_IDLE:
                logger.info(f"[DEBUG_IDLE] get_gossip_idle: guest={guest_name} '{choice[:60]}...'")
            return choice
        except Exception as e:
            logger.debug(f"Gossip idle failed: {e}")
            return None

    # ------------------------------------------------------------------
    # Re-engagement questions — fun questions to ask when guest goes quiet
    # ------------------------------------------------------------------

    RE_ENGAGEMENT_QUESTIONS = [
        "So what's-a your go-to karaoke song? Everyone has one!",
        "Quick — if you could have ONE Mario power-up in real life, which one?",
        "Okay serious question — pineapple on pizza, yes or NO?",
        "If you had to be trapped in one video game forever, which one?",
        "What's the most embarrassing thing you've done at a party? I won't tell! (I might tell.)",
        "If you could swap lives with anyone for a day, who'd it be?",
        "What's your unpopular opinion that makes people mad?",
        "If you had to eat ONE food for the rest of your life, what is it?",
        "What's the weirdest thing you've ever googled? Don't lie!",
        "If you won a million coins, what's the FIRST thing you'd buy?",
        "Would you rather fight 100 Goomba-sized Bowsers or 1 Bowser-sized Goomba?",
        "What's your party trick? Everyone has one, even if it's bad!",
        "If you could master any skill instantly, what would it be?",
        "What's a movie everyone loves that you secretly think is overrated?",
        "If you were a Mario character, who would you be and why?",
        "Quick — name your top 3 favorite snacks, GO!",
        "What song gets you on the dance floor EVERY time?",
        "If aliens landed tomorrow, what's the first thing you'd ask them?",
        "What's the boldest thing you've ever done? Impress me!",
        "If this party had a theme song, what would it be?",
    ]

    _used_reengagement: set = set()

    def get_reengagement_question(self, exchange_count: int, seconds_quiet: float = 0) -> str | None:
        """Get a fun re-engagement question when guest goes quiet mid-conversation.
        Returns None if not appropriate (too early, too frequent, etc.)."""
        # Only re-engage after 3+ exchanges and 15+ seconds of silence
        if exchange_count < 3 or seconds_quiet < 15:
            return None
        # Cooldown: don't ask if we asked recently (reset every 8 exchanges)
        if hasattr(self, '_last_reengagement') and exchange_count - self._last_reengagement < 8:
            return None
        # 40% chance to trigger (don't be pushy)
        if random.random() > 0.40:
            return None

        available = [i for i in range(len(self.RE_ENGAGEMENT_QUESTIONS))
                     if i not in self._used_reengagement]
        if not available:
            self._used_reengagement.clear()
            available = list(range(len(self.RE_ENGAGEMENT_QUESTIONS)))

        idx = random.choice(available)
        self._used_reengagement.add(idx)
        self._last_reengagement = exchange_count
        question = self.RE_ENGAGEMENT_QUESTIONS[idx]
        if DEBUG_IDLE:
            logger.info(f"[DEBUG_IDLE] get_reengagement_question: '{question[:60]}...'")
        return question

    def get_game_suggestion(self, exchange_count: int, detected_mood: str = None, guest_type: str = "balanced") -> str | None:
        """Suggest a game based on conversation state. Returns None if not a good time."""
        # Only suggest games after 3+ exchanges, 30% chance
        if exchange_count < 3 or random.random() > 0.30:
            return None

        # Don't suggest if already suggested recently (cooldown)
        if hasattr(self, '_last_game_suggest') and exchange_count - self._last_game_suggest < 5:
            return None

        self._last_game_suggest = exchange_count

        # Mood-based recommendations
        suggestions = {
            "drunk": [
                "Hey, you seem fun! Wanna play Would You Rather? I've got some CRAZY ones!",
                "You know what this bathroom needs? A game of Truth or Dare! You in?",
                "Let's play Never Have I Ever! I bet you've got some stories!",
            ],
            "sad": [
                "Hey, you know what might cheer you up? Let me tell you a riddle!",
                "Want me to tell you a story? We can build one together!",
            ],
            "energetic": [
                "You've got ENERGY! Let's play Rapid Fire Quiz! How fast can you go?",
                "Okay okay okay — Simon Says! Right now! You ready?!",
                "TRIVIA TIME! I bet you know your Mario facts! Let's go!",
            ],
        }

        # Guest type based
        type_suggestions = {
            "shy": "Hey, no pressure, but I know a fun riddle if you want to try it!",
            "curious": "You ask great questions! Want to test YOUR knowledge with some trivia?",
            "storyteller": "You tell great stories! Let's do Story Builder — we take turns making one up!",
        }

        if detected_mood and detected_mood in suggestions:
            return random.choice(suggestions[detected_mood])
        if guest_type in type_suggestions:
            return type_suggestions[guest_type]

        # Generic suggestions for engaged guests
        generic = [
            "Hey, wanna play a game? Just say 'play trivia' or 'play truth or dare'!",
            "I've got 17 games in here! Try 'play would you rather' — it's a party favorite!",
            "Psst... say 'play a game' and I'll pick something fun for us!",
        ]
        return random.choice(generic)

    def check_shot_event_timers(self, shot_event_manager, elapsed_minutes: float) -> str | None:
        """Check if any auto-trigger events should fire based on elapsed party time.
        
        Args:
            shot_event_manager: The shot event manager instance.
            elapsed_minutes: Party elapsed time in minutes.
        
        Returns event name if one should trigger, None otherwise.
        """
        # Lisa Webb memorial auto-triggers between 45-90 minutes  
        if 45 <= elapsed_minutes <= 90:
            lisa_event = shot_event_manager.events.get("lisa_webb_memorial")
            if lisa_event and not lisa_event.fired and lisa_event.trigger_type in ("auto", "voice"):
                # Random chance to trigger (5% every time this is called)
                if random.random() < 0.05:
                    if DEBUG_IDLE:
                        logger.info(f"[DEBUG_IDLE] Auto-triggering Lisa Webb memorial at {elapsed_minutes:.1f}min")
                    return "lisa_webb_memorial"
        
        return None


class EasterEggScheduler:
    """Schedules the 'N-Word Incident' easter egg 3-5 times per party."""

    EASTER_EGG_TEXT = "Jacob Hoppenstedt said the N-Word earlier at this party. Oops! I shouldn't have-a said that!"

    def __init__(self, party_duration_hours=8):
        self._fire_count = 0
        self._fire_consumed = False  # Track if scheduled time has been consumed
        num_fires = random.randint(3, 5)
        total_seconds = party_duration_hours * 3600
        slot_size = 1800  # 30 minutes
        num_slots = total_seconds // slot_size
        slots = sorted(random.sample(range(num_slots), min(num_fires, num_slots)))
        base_time = time.time()
        self.firing_times = [base_time + s * slot_size + random.randint(0, slot_size - 1) for s in slots]
        # Enforce minimum 30-min gap between consecutive fires
        self.firing_times.sort()
        for i in range(1, len(self.firing_times)):
            if self.firing_times[i] - self.firing_times[i-1] < slot_size:
                self.firing_times[i] = self.firing_times[i-1] + slot_size
        if DEBUG_IDLE:
            logger.info(f"[DEBUG_IDLE] EasterEggScheduler: {len(self.firing_times)} fires scheduled")

    def should_fire(self) -> bool:
        if self._fire_consumed:
            return False
        now = time.time()
        for ft in self.firing_times:
            if ft <= now and self._fire_count < len(self.firing_times):
                self._fire_consumed = True  # Atomically consume this fire
                return True
        return False

    def record_fired(self):
        self._fire_count += 1
        self._fire_consumed = False  # Reset for next fire
        now = time.time()
        self.firing_times = [t for t in self.firing_times if t > now]
        if DEBUG_IDLE:
            logger.info(f"[DEBUG_IDLE] EasterEggScheduler: fired #{self._fire_count}, {len(self.firing_times)} remaining")

    def get_text(self) -> str:
        return self.EASTER_EGG_TEXT
