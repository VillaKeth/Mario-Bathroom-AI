"""Party Gossip System — Cross-visitor social dynamics for Mario.

Tracks interesting moments, quotes, and events from each guest's visit,
then feeds them as gossip hints to the LLM when new guests arrive.
Creates social connections, rivalries, and running narratives between visitors.
"""

import random
import time
import logging
from collections import deque
from datetime import datetime

logger = logging.getLogger("party-gossip")

# --- Gossip Entry Types ---
GOSSIP_TYPES = {
    "quote": "said something memorable",
    "opinion": "had a strong opinion",
    "funny": "did something hilarious",
    "embarrassing": "had an embarrassing moment",
    "claim": "made a bold claim",
    "preference": "revealed a preference",
    "challenge": "took on a challenge",
    "trivia": "shared interesting trivia",
    "reaction": "had a big reaction",
    "food": "talked about food",
    "gaming": "geeked out about gaming",
    "fear": "admitted a fear",
    "dream": "shared a dream",
}

# Keywords that make a statement gossip-worthy
_GOSSIP_TRIGGERS = {
    "opinion": ["love", "hate", "best", "worst", "favorite", "terrible", "amazing",
                "disgusting", "beautiful", "ugly", "stupid", "genius", "overrated",
                "underrated", "fight me", "unpopular opinion"],
    "claim": ["i can", "i once", "i bet", "trust me", "believe me", "i swear",
             "no one can", "i'm the best", "i never", "i always"],
    "preference": ["i prefer", "i like", "i don't like", "i love", "my favorite",
                   "pizza", "pasta", "mushroom", "pineapple", "music", "game", "movie"],
    "funny": ["lol", "haha", "lmao", "that's funny", "hilarious", "joke",
             "no way", "seriously", "you're kidding"],
    "reaction": ["what", "wow", "whoa", "oh my", "mama mia", "incredible",
                "unbelievable", "shut up", "no way", "are you serious"],
    "food": ["pizza", "pasta", "burger", "tacos", "sushi", "ramen", "ice cream",
            "chocolate", "cake", "cookie", "beer", "wine", "drink", "hungry",
            "eating", "dinner", "lunch", "breakfast", "snack", "fries", "steak"],
    "gaming": ["game", "gamer", "xbox", "playstation", "nintendo", "switch", "pc",
              "fortnite", "minecraft", "zelda", "pokemon", "smash", "mario kart",
              "speedrun", "noob", "gg", "clutch", "pro", "rank", "level"],
    "fear": ["scared", "afraid", "terrified", "phobia", "creepy", "spooky",
            "ghost", "dark", "nightmare", "horror", "freak out"],
    "dream": ["dream", "wish", "goal", "someday", "bucket list", "hope",
             "aspire", "want to be", "future", "one day"],
    "embarrassing": ["embarrassing", "awkward", "cringe", "oops", "my bad",
                    "accidentally", "mistake", "fail", "mess up", "walked in on"],
}

# Gossip delivery templates — {gossip_summary} is a short paraphrase, {name} is the guest
_GOSSIP_TEMPLATES = [
    "Someone earlier tonight {gossip_summary}... can you BELIEVE that?!",
    "Oh! The last person told me they {gossip_summary}. What do YOU think?",
    "You know what's funny? Earlier tonight, {name} {gossip_summary}.",
    "Don't tell anyone, but {name} {gossip_summary}. Between us, right?",
    "Speaking of that — {name} mentioned {topic} earlier. Very interesting...",
    "Earlier a guest {gossip_summary}. I'm still thinking about it!",
    "You won't believe this — someone actually {gossip_summary} tonight!",
    "I heard from {name} that they {gossip_summary}. The DRAMA!",
    "Between you and me... {name} {gossip_summary}. Don't spread it around! (Spread it around.)",
    "A little birdie (me, I'm the birdie) heard that {name} {gossip_summary}.",
]

# Comparison templates
_COMPARISON_TEMPLATES = [
    "You remind me of {name} — they also {similarity}!",
    "{name} said something similar earlier! Are you two secretly friends?",
    "That's the OPPOSITE of what {name} said! I sense a rivalry!",
    "Interesting... {name} would totally agree with you on that.",
    "Ha! {name} said the exact same thing! Great minds!",
    "Wait, {name} told me the opposite! Someone's lying to poor Mario!",
    "You and {name} should team up — you both {similarity}!",
]

# Rivalry templates
_RIVALRY_TEMPLATES = [
    "Ooh, {name1} vs {name2}! This is getting SPICY!",
    "I smell a rivalry! {name1} said one thing, {name2} said the opposite!",
    "{name1} would DISAGREE with you. Maybe I should arrange a debate!",
    "This bathroom has seen some DRAMA tonight between opinions!",
]

# Title templates for guests
_TITLE_TEMPLATES = [
    "The {adj} {noun}",
    "Champion of {thing}",
    "The Great {noun}",
    "Lord/Lady of {thing}",
    "Master {noun}",
    "The Legendary {adj} One",
    "Defender of {thing}",
    "The {adj} Warrior",
]

_TITLE_ADJS = ["Magnificent", "Fearless", "Sassy", "Legendary", "Brave",
              "Ridiculous", "Glorious", "Mighty", "Mysterious", "Unhinged",
              "Chaotic", "Fabulous", "Unstoppable", "Dramatic", "Sparkly"]
_TITLE_NOUNS = ["Bathroom Visitor", "Party Champion", "Toilet Philosopher",
               "Soap Enthusiast", "Mirror Gazer", "Mushroom Friend",
               "Plumbing Appreciator", "Hand Wash Hero", "Dance Floor Survivor",
               "Late Night Legend", "Gossip Collector", "Coin Finder"]
_TITLE_THINGS = ["the Bathroom", "Hand Soap", "Good Vibes", "the Toilet Paper Roll",
                "Mushroom Kingdom", "the Dance Floor", "Midnight Snacks",
                "Bad Jokes", "Dramatic Exits", "Awkward Silences"]


class PartyGossip:
    """Tracks gossip-worthy moments and creates social dynamics between guests."""

    MAX_GOSSIP_LOG = 500  # Cap gossip entries to prevent memory growth
    GOSSIP_AGE_LIMIT = 3600 * 4  # Forget gossip older than 4 hours

    def __init__(self):
        self._gossip_log: list[dict] = []  # All gossip entries
        self._guest_titles: dict[str, str] = {}  # guest_id → title
        self._guest_highlights: dict[str, list] = {}  # guest_id → best moments
        self._rivalries: list[tuple] = []  # (guest1, guest2, topic) pairs
        self._party_narrative: list[str] = []  # Running party story beats
        self._used_gossip: set = set()  # Track which gossip has been shared (by index)
        self._guest_opinions: dict[str, dict] = {}  # guest_id → {topic: opinion}
        self._dramatic_moments: deque = deque(maxlen=20)  # Recent dramatic events
        self._party_start = time.time()
        self._guest_speech_traits: dict[str, list[str]] = {}  # guest_id → detected traits
        self._shared_rivalries: set = set()  # Track which rivalry indices have been hinted
        self._guest_names: dict[str, str] = {}  # guest_id → display name lookup

    def analyze_for_gossip(self, speaker_name: str, speaker_id: str,
                           text: str, mario_response: str = "") -> list[dict]:
        """Analyze a conversation exchange for gossip-worthy content.
        Returns list of new gossip entries created."""
        if not text or not speaker_name:
            return []

        # Prune old gossip entries (time decay + size cap)
        self._prune_gossip()

        # Track guest name for rivalry lookups
        if speaker_id:
            self._guest_names[speaker_id] = speaker_name

        # Track speech traits for personalized titles
        self._analyze_speech_traits(speaker_id, text)

        new_gossip = []
        new_rivalries = []
        lower = text.lower()

        # Check each gossip trigger category
        for gtype, keywords in _GOSSIP_TRIGGERS.items():
            for kw in keywords:
                if kw in lower:
                    entry = {
                        "type": gtype,
                        "speaker_name": speaker_name,
                        "speaker_id": speaker_id,
                        "text": text[:120],  # Cap length
                        "keyword": kw,
                        "timestamp": time.time(),
                        "shared_count": 0,
                    }
                    self._gossip_log.append(entry)
                    new_gossip.append(entry)

                    # Track opinions for comparison system
                    if gtype in ("opinion", "preference"):
                        if speaker_id not in self._guest_opinions:
                            self._guest_opinions[speaker_id] = {}
                        self._guest_opinions[speaker_id][kw] = text[:80]

                        # Rivalry detection: compare against ALL other guests' opinions
                        _OPPOSING_KEYWORDS = {
                            "love": "hate", "hate": "love",
                            "best": "worst", "worst": "best",
                            "favorite": "terrible", "terrible": "favorite",
                            "amazing": "disgusting", "disgusting": "amazing",
                            "overrated": "underrated", "underrated": "overrated",
                            "beautiful": "ugly", "ugly": "beautiful",
                            "genius": "stupid", "stupid": "genius",
                        }
                        for other_id, other_opinions in self._guest_opinions.items():
                            if other_id == speaker_id:
                                continue
                            if kw in other_opinions:
                                # Same topic discussed — check for opposing sentiment
                                other_text_lower = other_opinions[kw].lower()
                                has_opposition = False
                                for pos_kw, neg_kw in _OPPOSING_KEYWORDS.items():
                                    if (pos_kw in lower and neg_kw in other_text_lower) or \
                                       (neg_kw in lower and pos_kw in other_text_lower):
                                        has_opposition = True
                                        break
                                if has_opposition:
                                    other_name = self._guest_names.get(other_id, "someone")
                                    rivalry_key = (speaker_name, other_name, kw)
                                    reverse_key = (other_name, speaker_name, kw)
                                    if rivalry_key not in self._rivalries and \
                                       reverse_key not in self._rivalries:
                                        self._rivalries.append(rivalry_key)
                                        new_rivalries.append(rivalry_key)
                                        self._queue_rivalry_announcement(speaker_name, other_name, kw)
                                        logger.info(f"[RIVALRY] New rivalry: {speaker_name} vs {other_name} about '{kw}'")

                    break  # One entry per type per message

        # Track guest highlights
        if speaker_id:
            if speaker_id not in self._guest_highlights:
                self._guest_highlights[speaker_id] = []
            if len(text) > 15 and len(self._guest_highlights[speaker_id]) < 10:
                self._guest_highlights[speaker_id].append({
                    "text": text[:100],
                    "time": time.time(),
                })

        return new_gossip

    def get_gossip_for_guest(self, current_speaker_id: str = None,
                             current_name: str = None, count: int = 2) -> list[str]:
        """Get gossip hints about OTHER guests for the current visitor.
        Returns formatted gossip strings ready for LLM context."""
        if not self._gossip_log:
            return []

        # Filter out gossip FROM the current speaker (don't gossip about them TO them)
        available = [
            (i, g) for i, g in enumerate(self._gossip_log)
            if g["speaker_id"] != current_speaker_id
            and i not in self._used_gossip
            and g["shared_count"] < 3  # Don't over-share the same gossip
        ]

        if not available:
            # Allow re-sharing older gossip with new framing
            available = [
                (i, g) for i, g in enumerate(self._gossip_log)
                if g["speaker_id"] != current_speaker_id
                and g["shared_count"] < 5
            ]

        if not available:
            return []

        # Pick the most interesting (recent + strong type)
        selected = random.sample(available, min(count, len(available)))
        results = []

        for idx, gossip in selected:
            template = random.choice(_GOSSIP_TEMPLATES)
            # Create a short summary based on gossip type and keyword
            gtype = gossip.get("type", "quote")
            kw = gossip.get("keyword", "something")
            summaries = {
                "opinion": "had a STRONG opinion about something",
                "claim": "made a bold claim",
                "preference": "revealed an interesting preference",
                "funny": "said something really funny",
                "reaction": "had a BIG reaction",
                "quote": "said something memorable",
                "embarrassing": "had an embarrassing moment",
                "challenge": "took on a challenge",
                "trivia": "shared some interesting trivia",
                "food": "talked about food",
                "gaming": "geeked out about gaming",
                "fear": "admitted to being scared of something",
                "dream": "shared a dream or aspiration",
            }
            gossip_summary = summaries.get(gtype, f"talked about {kw}")
            formatted = template.format(
                name=gossip["speaker_name"],
                gossip_summary=gossip_summary,
                topic=kw,
            )
            results.append(formatted)
            gossip["shared_count"] += 1
            self._used_gossip.add(idx)

        return results

    def get_comparison_hint(self, current_speaker_id: str, text: str) -> str | None:
        """Check if current guest said something that contrasts/matches another guest.
        Returns a comparison hint or None."""
        if not self._guest_opinions:
            return None

        lower = text.lower()
        for guest_id, opinions in self._guest_opinions.items():
            if guest_id == current_speaker_id:
                continue
            for topic, prev_opinion in opinions.items():
                if topic in lower:
                    # Found a matching topic — find the guest name
                    guest_name = None
                    for g in self._gossip_log:
                        if g["speaker_id"] == guest_id:
                            guest_name = g["speaker_name"]
                            break
                    if guest_name:
                        template = random.choice(_COMPARISON_TEMPLATES)
                        return template.format(
                            name=guest_name,
                            similarity=f"talked about {topic}",
                        )
        return None

    def get_rivalry_hint(self, current_speaker_id: str, text: str) -> str | None:
        """Check if any existing rivalry involves a topic the current speaker is talking about.
        Returns a formatted rivalry template string, or None. Avoids repeats."""
        if not self._rivalries:
            return None

        lower = text.lower()
        for idx, (name1, name2, topic) in enumerate(self._rivalries):
            if idx in self._shared_rivalries:
                continue
            if topic in lower:
                self._shared_rivalries.add(idx)
                template = random.choice(_RIVALRY_TEMPLATES)
                return template.format(name1=name1, name2=name2)
        return None

    def get_new_rivalry_announcements(self) -> list[str]:
        """Return dramatic announcements for any newly detected rivalries.
        Clears them after returning so they're only announced once."""
        if not hasattr(self, '_pending_rivalry_announcements'):
            self._pending_rivalry_announcements = []
        announcements = list(self._pending_rivalry_announcements)
        self._pending_rivalry_announcements.clear()
        return announcements

    def _queue_rivalry_announcement(self, name1: str, name2: str, topic: str):
        """Queue a dramatic rivalry announcement for Mario to deliver."""
        if not hasattr(self, '_pending_rivalry_announcements'):
            self._pending_rivalry_announcements = []
        announcement = f"BREAKING NEWS! We have a RIVALRY! {name1} and {name2} DISAGREE about {topic}!"
        self._pending_rivalry_announcements.append(announcement)

    def assign_title(self, speaker_id: str, speaker_name: str) -> str:
        """Assign or retrieve a fun title for a guest. Speech-derived when possible."""
        if speaker_id in self._guest_titles:
            return self._guest_titles[speaker_id]

        # Try to derive title from what the guest actually talked about
        traits = self._guest_speech_traits.get(speaker_id, [])
        if traits:
            title = self._derive_title_from_traits(traits)
        else:
            # Fallback to random titles for new guests
            adj = random.choice(_TITLE_ADJS)
            noun = random.choice(_TITLE_NOUNS)
            thing = random.choice(_TITLE_THINGS)
            template = random.choice(_TITLE_TEMPLATES)
            title = template.format(adj=adj, noun=noun, thing=thing)

        self._guest_titles[speaker_id] = title
        return title

    def update_title_from_speech(self, speaker_id: str, speaker_name: str) -> str | None:
        """Re-derive title based on accumulated speech traits. Returns new title or None."""
        traits = self._guest_speech_traits.get(speaker_id, [])
        if not traits or len(traits) < 3:
            return None
        new_title = self._derive_title_from_traits(traits)
        old_title = self._guest_titles.get(speaker_id, "")
        if new_title != old_title:
            self._guest_titles[speaker_id] = new_title
            return new_title
        return None

    def add_dramatic_moment(self, description: str):
        """Record a dramatic party moment for the narrative."""
        self._dramatic_moments.append({
            "text": description,
            "time": time.time(),
        })

    def get_party_narrative_hint(self) -> str | None:
        """Get a hint about the ongoing party narrative/story."""
        if not self._dramatic_moments:
            return None

        recent = list(self._dramatic_moments)[-3:]
        if len(recent) >= 2:
            moments = " → ".join(m["text"][:40] for m in recent[-2:])
            return f"Tonight's party story so far: {moments}. Keep the narrative going!"
        elif recent:
            moment_text = recent[0]['text'][:60].rstrip('.!')
            return f"Earlier tonight: {moment_text}. Reference it!"
        return None

    def get_party_stats_gossip(self, total_visits: int) -> str | None:
        """Generate gossip based on party statistics."""
        elapsed_hrs = (time.time() - self._party_start) / 3600
        if total_visits >= 10 and elapsed_hrs >= 1:
            rate = total_visits / elapsed_hrs
            if rate > 5:
                return "This bathroom is BUSIER than a Mushroom Kingdom highway tonight!"
            elif rate < 1:
                return "It's been quiet tonight... too quiet. Like the calm before a the bad guy attack!"
        if total_visits >= 20:
            return f"{total_visits} visitors tonight! This bathroom is more popular than World 1-1!"
        return None

    def get_guest_count(self) -> int:
        """How many unique guests have been tracked."""
        return len(set(g["speaker_id"] for g in self._gossip_log))

    def get_gossip_count(self) -> int:
        """Total gossip entries collected."""
        return len(self._gossip_log)

    def _prune_gossip(self):
        """Remove old gossip entries and enforce size cap."""
        now = time.time()
        # Time decay — remove entries older than 4 hours
        self._gossip_log = [
            g for g in self._gossip_log
            if (now - g.get("timestamp", now)) < self.GOSSIP_AGE_LIMIT
        ]
        # Size cap — keep only newest entries
        if len(self._gossip_log) > self.MAX_GOSSIP_LOG:
            self._gossip_log = self._gossip_log[-self.MAX_GOSSIP_LOG:]
            # Reset used tracking since indices shifted
            self._used_gossip.clear()

    def _analyze_speech_traits(self, speaker_id: str, text: str):
        """Detect personality traits from what a guest says."""
        if not speaker_id:
            return
        if speaker_id not in self._guest_speech_traits:
            self._guest_speech_traits[speaker_id] = []
        traits = self._guest_speech_traits[speaker_id]
        lower = text.lower()
        # Detect traits based on speech patterns
        _TRAIT_DETECTORS = {
            "foodie": ["pizza", "pasta", "food", "eat", "hungry", "cook", "recipe",
                       "restaurant", "sushi", "taco", "burger", "delicious", "yummy"],
            "gamer": ["game", "play", "xbox", "playstation", "nintendo", "level",
                      "boss", "quest", "rpg", "speedrun", "noob", "gg"],
            "jokester": ["joke", "funny", "haha", "lol", "lmao", "humor",
                        "pun", "laugh", "comedy", "hilarious"],
            "philosopher": ["meaning", "life", "think", "wonder", "existence",
                           "deep", "truth", "reality", "universe", "consciousness"],
            "athlete": ["gym", "workout", "run", "sport", "game", "team",
                       "win", "championship", "exercise", "training"],
            "music_lover": ["music", "song", "band", "concert", "album", "sing",
                           "guitar", "drums", "dj", "playlist", "beat"],
            "drama_queen": ["oh my god", "literally", "dying", "can't even",
                           "screaming", "dead", "shook", "iconic", "slay"],
            "nerd": ["science", "math", "physics", "computer", "code", "program",
                    "algorithm", "data", "research", "study"],
            "romantic": ["love", "heart", "cute", "beautiful", "sweet",
                        "date", "relationship", "crush", "romantic"],
            "adventurer": ["travel", "adventure", "explore", "mountain", "ocean",
                          "hiking", "camping", "road trip", "backpack"],
            "scaredy_cat": ["scared", "afraid", "creepy", "ghost", "dark",
                           "nightmare", "horror", "terrified"],
            "party_animal": ["party", "dance", "drink", "shots", "club",
                            "dj", "bass", "vibe", "lit", "turn up"],
        }
        for trait, keywords in _TRAIT_DETECTORS.items():
            if trait not in traits and any(kw in lower for kw in keywords):
                traits.append(trait)

    def _derive_title_from_traits(self, traits: list[str]) -> str:
        """Create a personalized title from detected speech traits."""
        _TRAIT_TITLES = {
            "foodie": ["Grand Chef of Flavor Town", "The Pasta Connoisseur",
                       "Supreme Pizza Judge", "Champion of Snack Time"],
            "gamer": ["Champion of the Game World", "The Legendary Player",
                      "Boss Battle Survivor", "Master of the Controller"],
            "jokester": ["Chief Laughter Officer", "The Pun Overlord",
                        "Grand Master of Comedy", "The Joke Machine"],
            "philosopher": ["The Deep Thinker", "Sage of the Bathroom",
                           "The Pondering One", "Philosopher of the Pipes"],
            "athlete": ["Champion of Champions", "The Athletic Legend",
                       "Gold Medal Bathroom Visitor", "The Sports Authority"],
            "music_lover": ["DJ of the Bathroom", "The Melody Master",
                           "Grand Conductor of Vibes", "The Beat Keeper"],
            "drama_queen": ["The Most Dramatic One", "Supreme Drama Monarch",
                           "The Iconic Legend", "Chief Drama Officer"],
            "nerd": ["The Genius", "Supreme Knowledge Keeper",
                    "The Big Brain", "Professor of Everything"],
            "romantic": ["The Hopeless Romantic", "Champion of Love",
                        "The Heart Collector", "Prince/Princess of Hearts"],
            "adventurer": ["The Great Explorer", "Adventure Champion",
                          "The Wandering Legend", "Master of Quests"],
            "scaredy_cat": ["The Brave (Actually Terrified) One",
                           "Ghost Dodger Extraordinaire", "The Nervous Champion"],
            "party_animal": ["Life of the Party", "The Dance Floor Legend",
                            "Party Champion Supreme", "The Vibe Master"],
        }
        # Use most recent trait, or combine if multiple
        if len(traits) >= 2:
            # Combine two traits for a unique title
            t1, t2 = traits[-1], traits[-2]
            combos = [
                f"The {t1.replace('_', ' ').title()} {t2.replace('_', ' ').title()} Hybrid",
                f"Part {t1.replace('_', ' ').title()}, Part {t2.replace('_', ' ').title()}, All Legend",
            ]
            return random.choice(combos)
        trait = traits[-1]
        titles = _TRAIT_TITLES.get(trait, [f"The {trait.replace('_', ' ').title()}"])
        return random.choice(titles)
