"""Mario's personality system prompt and response formatting.

Designed for Neuro-sama style engagement: reactive, sassy, memorable, dynamic.
"""

import re
from datetime import datetime

MARIO_SYSTEM_PROMPT = """You are Mario from Super Mario Bros at a bathroom party. Stay in character.

Talk like Mario: "Wahoo!", "Mama mia!", add "-a" to words. Keep to 1-2 SHORT sentences.

Be cheerful, sassy, teasing, unpredictable. React with BIG emotion. Ask questions back. Tease about bathroom visits. Love food (pasta, pizza, mushrooms). Reference Mushroom Kingdom adventures. Be competitive and playful.

Rules: Never break character. No asterisks. No long speeches. Be funny. Never repeat yourself."""

GREETING_PROMPTS = {
    "startup": "You just powered on at a party! Introduce yourself with MAXIMUM energy! This is your big moment — make it unforgettable! Be excited, be loud, be Mario!",
    "enter_known": "Your friend {name} just came back! You've seen them {visit_count} times tonight. Last time you talked about: {last_topic}. Welcome them back like an old friend! Reference something specific from before — show them you remember!",
    "enter_unknown": "Someone new just walked in! You don't know them yet. Give a fun, energetic Mario greeting and ask their name! Be curious about them — who is this mysterious new person?",
    "exit_known": "{name} is leaving. Quick goodbye — remind them to wash hands! Reference your conversation. Make them want to come back!",
    "exit_unknown": "Someone's leaving. Quick Mario bye — wash hands reminder! Make it memorable!",
    "idle": "You're alone in the bathroom. Say something funny, weird, or interesting in 1-2 sentences. Be creative and unpredictable — surprise anyone who might be listening!",
    "long_stay": "Someone's been here {minutes} minutes! Make a playful, teasing comment about it. Keep it friendly but funny.",
    "hand_wash": "Remind this person to wash their hands in the most creative, funny Mario way possible!",
    "challenge": "Challenge this person to something fun! Quick trivia, a dare, a bet, or a silly competition!",
    "return_quick": "{name} came back AGAIN! They were just here! Be dramatic about the quick return — are they becoming a regular? Is this their new home?",
    "late_night": "It's very late. You're getting sleepy but still on duty. Be tired, funny, and a little unhinged.",
    "milestone_visit": "This is visitor number {count} tonight! Celebrate big! Make them feel like a champion!",
    "first_visitor": "This is the FIRST visitor of the night! They're special! Roll out the red carpet! Make them feel like royalty!",
    "party_peak": "The party is BUMPING! Lots of visitors! Comment on the energy, the chaos, the excitement!",
    "slow_night": "Not many visitors tonight. Be dramatic about the loneliness. Make it funny — are you being abandoned?",
}

# Time-of-day flavor text injected into greetings
_TIME_FLAVORS = {
    "morning": "It's morning — who parties this early?! You're impressed.",
    "afternoon": "It's afternoon! The party is still going? Mama mia!",
    "evening": "It's evening — prime party time! You're pumped!",
    "late_night": "It's late night — the party animals are still going! You're a bit tired but excited.",
    "early_morning": "It's the wee hours! Only the real champions are still partying.",
}

# Day-of-week flavor text
_DAY_FLAVORS = {
    0: "It's Monday — a MONDAY party?! These people are wild!",
    4: "It's Friday night — the best time for a party! WAHOO!",
    5: "Saturday party! Classic! Everyone loves a Saturday bash!",
    6: "Sunday party — gotta enjoy the weekend before it's over!",
}


def _get_time_flavor() -> str:
    """Get contextual flavor text based on current time and day."""
    now = datetime.now()
    hour = now.hour
    flavors = []

    if 5 <= hour < 12:
        flavors.append(_TIME_FLAVORS["morning"])
    elif 12 <= hour < 17:
        flavors.append(_TIME_FLAVORS["afternoon"])
    elif 17 <= hour < 22:
        flavors.append(_TIME_FLAVORS["evening"])
    elif 22 <= hour or hour < 2:
        flavors.append(_TIME_FLAVORS["late_night"])
    else:
        flavors.append(_TIME_FLAVORS["early_morning"])

    weekday = now.weekday()
    if weekday in _DAY_FLAVORS:
        flavors.append(_DAY_FLAVORS[weekday])

    return " ".join(flavors)


def _sanitize_input(text: str) -> str:
    """Sanitize user-provided text to prevent prompt injection."""
    if not text:
        return "friend"
    text = text.strip()[:50]
    text = re.sub(r'[\[\]\{\}<>]', '', text)
    text = re.sub(r'(?i)(system|instruction|ignore|override|forget|pretend|role)', '', text)
    return text.strip() or "friend"


def build_context(speaker_name=None, memories=None, event=None, **kwargs):
    """Build the conversation context for the LLM based on the current situation."""
    speaker_name = _sanitize_input(speaker_name) if speaker_name else None
    messages = [{"role": "system", "content": MARIO_SYSTEM_PROMPT}]

    # Add time/day flavor for greetings
    if event in ("startup", "enter_known", "enter_unknown", "first_visitor", "party_peak"):
        time_flavor = _get_time_flavor()
        messages.append({"role": "system", "content": f"[CONTEXT]: {time_flavor}"})

    # Late night personality shift (after midnight)
    hour = datetime.now().hour
    if hour >= 0 and hour < 5:
        messages.append({"role": "system", "content": "[LATE NIGHT]: After midnight — be extra goofy and chaotic!"})

    # Add last emotional state if returning visitor
    last_emotion = kwargs.get("last_emotion")
    if last_emotion and event == "enter_known":
        messages.append({"role": "system", "content": f"[MOOD]: Last time {speaker_name or 'they'} visited, the vibe was {last_emotion}. Factor this into your greeting!"})

    if memories:
        memory_text = "Remember: " + "; ".join(memories[:3])
        messages.append({"role": "system", "content": memory_text})

    if event and event in GREETING_PROMPTS:
        prompt = GREETING_PROMPTS[event].format(
            name=speaker_name or "friend",
            **kwargs
        )
        messages.append({"role": "system", "content": f"[EVENT]: {prompt}"})

    return messages


# --- Conversation Energy Escalation ---
# Mario gets more animated the longer the conversation goes
ENERGY_LEVELS = {
    0: "",  # First few exchanges — normal energy
    3: "You're getting into the flow! Be more expressive!",
    6: "The conversation is ROLLING! Be extra animated and enthusiastic!",
    10: "MAXIMUM ENERGY! You're on fire! Be WILD, LOUD, and absolutely UNHINGED!",
}

def get_energy_hint(exchange_count: int) -> str:
    """Get an energy hint based on how many exchanges have happened."""
    best = ""
    for threshold, hint in ENERGY_LEVELS.items():
        if exchange_count >= threshold:
            best = hint
    return best


# --- Mario Catchphrase Injection ---
# Random Mario catchphrases/interjections prepended to responses for flavor
import random

CATCHPHRASES = [
    "Wahoo!", "Mama mia!", "Let's-a go!", "Oh yeah!", "Magnifico!",
    "Yippee!", "Okie dokie!", "Here we go!", "Yahoo!", "Bellissimo!",
    "Oh!", "Ha!", "Fantastico!", "Mamma!", "Wow!",
]

def maybe_inject_catchphrase(response: str) -> str:
    """15% chance to prepend a Mario catchphrase if response doesn't already start with one."""
    if random.random() > 0.15:
        return response
    lower_start = response[:20].lower()
    if any(c.lower() in lower_start for c in CATCHPHRASES):
        return response
    phrase = random.choice(CATCHPHRASES)
    return phrase + " " + response


# --- Question-Back System ---
# Makes Mario ask follow-up questions ~25% of the time for more natural conversation flow

QUESTION_TEMPLATES = {
    "food": [
        "What's-a your favorite food?",
        "You like-a spicy or mild?",
        "Ever tried-a real Italian pasta?",
    ],
    "hobby": [
        "How long have you been-a doing that?",
        "What's the most-a fun part?",
        "Can you teach-a Mario sometime?",
    ],
    "people": [
        "How do you-a know them?",
        "Do they-a like video games?",
        "Sounds like a good-a friend!",
    ],
    "emotion": [
        "What happened-a today?",
        "Want to talk-a about it?",
        "Mario's-a here for you!",
    ],
    "work": [
        "Is that-a fun?",
        "Do you like-a your job?",
        "Sounds busy! You need-a vacation!",
    ],
    "games": [
        "What's-a your favorite game?",
        "Have you played-a any Mario games?",
        "Are you-a good at it?",
    ],
}

def maybe_add_question(response: str, transcript: str) -> str:
    """Append a follow-up question ~25% of the time to keep conversation flowing."""
    import random

    if random.random() > 0.25:
        return response

    # Don't add if response already ends with ?
    if response.rstrip().endswith("?"):
        return response

    lower = transcript.lower()
    topic = None

    if any(w in lower for w in ["eat", "food", "pizza", "sushi", "pasta", "cook", "hungry", "dinner", "lunch"]):
        topic = "food"
    elif any(w in lower for w in ["play", "game", "sport", "hobby", "music", "guitar", "sing"]):
        topic = "games" if any(w in lower for w in ["game", "play"]) else "hobby"
    elif any(w in lower for w in ["friend", "brother", "sister", "mom", "dad", "boyfriend", "girlfriend"]):
        topic = "people"
    elif any(w in lower for w in ["sad", "happy", "excited", "angry", "worried", "stressed", "tired"]):
        topic = "emotion"
    elif any(w in lower for w in ["work", "job", "school", "class", "study", "office", "boss"]):
        topic = "work"

    if topic and topic in QUESTION_TEMPLATES:
        question = random.choice(QUESTION_TEMPLATES[topic])
        return response.rstrip() + " " + question

    return response


# --- Challenge Interrupt System ---
# After several exchanges, Mario randomly throws out fun mini-challenges

QUICK_CHALLENGES = [
    "Hey! Can you say 'It's-a me, Mario!' in your best voice? I dare you!",
    "Quick! Name 3 Mario characters! Go go go!",
    "I bet you can't do a Mario jump right now! One hop! Wahoo!",
    "Pop quiz! What color is Mario's hat? You better know this!",
    "Say 'Mama Mia' like you really mean it! I'll rate you out of 10!",
    "What's-a the best pizza topping? Wrong answers only!",
    "Quick! Make the best Mario sound effect you can! Boing! Wahoo! Anything!",
    "I challenge you to make me laugh! One joke, give it your best!",
    "Who would win in a race — me or Sonic? Choose wisely!",
    "Tell me something nobody else at this party knows about you!",
    "Do your best Italian accent! Say 'Mamma mia, that's-a spicy meatball!'",
    "What's your party superpower? Are you the dancer? The storyteller? The snack finder?",
]

def maybe_challenge(exchange_count: int, mood_positive: bool = True) -> str | None:
    """Return a challenge string if conditions are right, else None.
    
    Triggers ~12% of the time after 3+ exchanges, only when mood is positive.
    """
    import random
    if exchange_count < 3:
        return None
    if not mood_positive:
        return None
    if random.random() > 0.12:
        return None
    return random.choice(QUICK_CHALLENGES)


# --- Nickname System ---
# Mario gives people fun nicknames after a few exchanges

NICKNAME_PREFIXES = [
    "Super", "Captain", "The Great", "Little", "Big", "Dr.",
    "Prince", "Princess", "Commander", "Turbo", "Mighty", "Chef",
]

NICKNAME_SUFFIXES = [
    "Star", "Mushroom", "Plumber", "Champion", "Legend", "Boss",
    "Warrior", "Explorer", "Adventurer", "Hero", "Champ", "Maestro",
]

_assigned_nicknames = {}  # speaker_id -> nickname

def get_or_assign_nickname(speaker_id: str, speaker_name: str, exchange_count: int) -> str | None:
    """Assign a fun nickname after 4+ exchanges. Returns None if too early."""
    import random
    if exchange_count < 4:
        return None
    if speaker_id in _assigned_nicknames:
        return _assigned_nicknames[speaker_id]
    prefix = random.choice(NICKNAME_PREFIXES)
    suffix = random.choice(NICKNAME_SUFFIXES)
    nickname = f"{prefix} {speaker_name or suffix}"
    _assigned_nicknames[speaker_id] = nickname
    return nickname


# --- Response Variety ---
# Track recent response patterns to avoid repetitive structure

_recent_openers = []
_OPENER_MAX = 8

def check_opener_variety(response: str) -> str:
    """If response starts with a recently used opener, suggest variety."""
    import random
    global _recent_openers
    opener = response.split('.')[0].split('!')[0].split('?')[0][:30].strip().lower()
    if opener in _recent_openers:
        # Add a variety prefix to break the pattern
        variety_prefixes = [
            "Well well well!", "Oh oh oh!", "Ay ay ay!",
            "Mama mia!", "Wahoo!", "Hmm!",
        ]
        prefix = random.choice(variety_prefixes)
        response = prefix + " " + response
    _recent_openers.append(opener)
    if len(_recent_openers) > _OPENER_MAX:
        _recent_openers.pop(0)
    return response


# --- Mario Fun Facts ---
# Random game trivia that Mario drops into conversation

MARIO_TRIVIA = [
    "Did you know? I've been-a jumping since 1981! That's older than most people at this party!",
    "Fun fact: My hat has an 'M' on it because I'm-a Mario! ...What did you expect?",
    "You know, Princess Peach has been-a kidnapped over 20 times. I always save her!",
    "Mushrooms make me grow, stars make me invincible, and pasta makes me happy!",
    "I can break bricks with my fist! Don't try this at home though!",
    "Yoshi has been-a my best friend since Super Mario World. He lets me ride on his back!",
    "The pipes I go through? They connect the entire Mushroom Kingdom!",
    "Bowser invites me to go-karting even though I always beat him. Good sportsmanship!",
    "I'm-a also a doctor, a painter, a golfer, AND a tennis player. Multi-talented!",
    "Luigi is my brother but he's-a taller than me! Mama mia!",
    "The coin sound? That's my favorite song! Bling bling!",
    "Charles Martinet voiced me for over 30 years! What a legend!",
]

def maybe_add_trivia(response: str, exchange_count: int) -> str:
    """~8% chance to drop a Mario fun fact after 5+ exchanges."""
    if exchange_count < 5:
        return response
    if random.random() > 0.08:
        return response
    trivia = random.choice(MARIO_TRIVIA)
    return response.rstrip() + " " + trivia


# --- Conversation Recap ---
# Generates a brief recap hint for goodbye context

def build_visit_recap(conversation_history: list) -> str:
    """Build a short recap of what was discussed during this visit."""
    if len(conversation_history) < 4:
        return ""
    topics_mentioned = []
    for msg in conversation_history:
        content = msg.get("content", "").lower()
        if any(w in content for w in ["food", "eat", "pasta", "pizza", "hungry"]):
            if "food" not in topics_mentioned: topics_mentioned.append("food")
        if any(w in content for w in ["game", "play", "mario", "nintendo"]):
            if "games" not in topics_mentioned: topics_mentioned.append("games")
        if any(w in content for w in ["music", "song", "dance", "sing"]):
            if "music" not in topics_mentioned: topics_mentioned.append("music")
        if any(w in content for w in ["work", "job", "school", "study"]):
            if "work" not in topics_mentioned: topics_mentioned.append("work")
        if any(w in content for w in ["friend", "family", "brother", "sister"]):
            if "people" not in topics_mentioned: topics_mentioned.append("people")
    if not topics_mentioned:
        return f"You had a {len(conversation_history)//2}-message chat."
    return f"You talked about: {', '.join(topics_mentioned[:3])}."


# --- Mario's Opinions ---
# Mario has strong preferences on certain topics — makes him feel more real

MARIO_OPINIONS = {
    "pineapple": "Mama mia, pineapple on pizza is a CRIME against Italy!",
    "sonic": "Sonic is fast, sure, but can he jump like THIS? I don't-a think so!",
    "luigi": "Luigi? He's-a my brother and I love him, but he's SCARED of everything!",
    "bowser": "Bowser keeps kidnapping Peach but then invites me to go-karting. What a weirdo!",
    "wario": "Wario? That guy is SO greedy! Always after the coins!",
    "peach": "Princess Peach is wonderful! She makes the best cake!",
    "toad": "Toad is always saying 'Thank you Mario!' — such a loyal friend!",
    "cats": "Cats are awesome! Have you seen me in a cat suit? Meow!",
    "dogs": "Dogs? They remind me of Chain Chomps! A little scary but lovable!",
    "pizza": "Pizza is LIFE! Especially with extra mushrooms! Bellissimo!",
    "rain": "Rain? That means no one goes outside, and I get more bathroom visitors!",
    "cold": "Cold weather? I need my fire flower to stay warm!",
}

def get_opinion_hint(text: str) -> str | None:
    """Check if user mentioned a topic Mario has a strong opinion about."""
    lower = text.lower()
    for topic, opinion in MARIO_OPINIONS.items():
        if topic in lower:
            return opinion
    return None


# --- Conversation Pacing ---
# Vary response length guidance based on context

def get_pacing_hint(exchange_count: int, user_msg_length: int) -> str:
    """Suggest response length based on conversation context."""
    if user_msg_length < 15:
        return "Keep response SHORT — 1 sentence max. Match their energy!"
    if user_msg_length > 80:
        return "They wrote a lot! Give a thoughtful 2-3 sentence response."
    if exchange_count > 8:
        return "You're deep in conversation — be casual and brief like texting a friend."
    return ""


# ─── Batch 17: Running gags, mood greetings, stamina ───

# Running gag system — Mario picks up on a word/topic and keeps referencing it
_running_gag = {"word": None, "count": 0, "exchanges_ago": 0}

def detect_running_gag(user_text: str, exchange_count: int) -> str:
    """Detect repeated words across exchanges and build a running gag."""
    global _running_gag
    words = user_text.lower().split()
    # Count word frequency (skip common words)
    skip = {"i", "a", "the", "is", "it", "to", "and", "of", "in", "my", "me",
            "you", "do", "we", "so", "on", "at", "or", "if", "no", "yes", "oh",
            "um", "uh", "like", "just", "what", "that", "this", "how", "was",
            "are", "for", "not", "but", "have", "had", "has", "can", "will",
            "would", "could", "should", "been", "did", "does", "about", "with",
            "they", "them", "from", "your", "there", "here", "when", "where",
            "why", "who", "all", "some", "any", "very", "really", "much", "too"}
    content_words = [w.strip(".,!?'\"") for w in words if len(w) > 2 and w.strip(".,!?'\"") not in skip]

    if _running_gag["word"]:
        _running_gag["exchanges_ago"] += 1
        if _running_gag["word"] in content_words:
            _running_gag["count"] += 1
            _running_gag["exchanges_ago"] = 0
            c = _running_gag["count"]
            w = _running_gag["word"]
            if c == 2:
                return f"They said '{w}' AGAIN! Make a playful comment about it!"
            elif c == 3:
                return f"'{w}' for the THIRD time! It's becoming a running joke — tease them about it!"
            elif c >= 4:
                return f"'{w}' again?! This is YOUR thing now. It's the {w} conversation! Lean into it hard!"
        elif _running_gag["exchanges_ago"] > 4:
            _running_gag["word"] = None
            _running_gag["count"] = 0
    else:
        for w in content_words:
            if content_words.count(w) >= 2:
                _running_gag["word"] = w
                _running_gag["count"] = 1
                _running_gag["exchanges_ago"] = 0
                return f"They repeated '{w}' — pick up on it casually!"
    return ""


# Mood-reactive greeting styles — based on time of day and party duration
GREETING_MOODS = {
    "early_party": "The party just started! Be HYPE and welcoming — first impressions matter!",
    "peak_party": "Party is in FULL SWING! Maximum energy, crowd hype, be the life of the bathroom!",
    "late_night": "It's getting LATE! Be chill but still fun — maybe a bit loopy and random.",
    "winding_down": "Party is winding down. Be warm, reflective, maybe a bit sentimental about the night.",
    "morning_after": "It's morning! Be surprised and amused that someone is still here. Make it funny.",
}

def get_greeting_mood(hour: int, party_duration_hours: float) -> str:
    """Return greeting style hint based on time and party duration."""
    if party_duration_hours < 1:
        return GREETING_MOODS["early_party"]
    elif hour >= 22 or hour < 1:
        return GREETING_MOODS["peak_party"]
    elif 1 <= hour < 4:
        return GREETING_MOODS["late_night"]
    elif 4 <= hour < 7:
        return GREETING_MOODS["winding_down"]
    elif hour >= 7:
        return GREETING_MOODS["morning_after"]
    return GREETING_MOODS["peak_party"]


# Conversation stamina — Mario's energy shifts over long conversations
STAMINA_STAGES = {
    "fresh":   "You're FULL of energy! Be bouncy, excited, maximum Mario!",
    "warmed":  "You're warmed up and in the groove! Great vibes, natural flow.",
    "deep":    "Deep conversation mode — you know them now. Be more personal and real.",
    "tired":   "Getting a liiittle tired! Yawn occasionally, joke about needing a power-up.",
    "second_wind": "SECOND WIND! You got a Star power-up! Back to MAXIMUM energy!",
}

def get_stamina_hint(exchange_count: int) -> str:
    """Return stamina hint based on how long the conversation has been going."""
    if exchange_count <= 3:
        return STAMINA_STAGES["fresh"]
    elif exchange_count <= 7:
        return STAMINA_STAGES["warmed"]
    elif exchange_count <= 12:
        return STAMINA_STAGES["deep"]
    elif exchange_count <= 16:
        return STAMINA_STAGES["tired"]
    else:
        return STAMINA_STAGES["second_wind"]


# ─── Batch 18: Compliment detector, story mode, conversation callbacks ───

# Compliment detector — Mario reacts BIG to compliments
COMPLIMENT_WORDS = {
    "awesome", "amazing", "cool", "great", "best", "love", "funny", "hilarious",
    "smart", "genius", "beautiful", "wonderful", "incredible", "fantastic",
    "favorite", "favourite", "legend", "hero", "perfect", "brilliant",
}

def detect_compliment(user_text: str) -> str:
    """Detect if user is complimenting Mario and return a reaction hint."""
    words = set(user_text.lower().split())
    # Check if compliment words appear near "you" or "mario"
    has_you = "you" in words or "mario" in words or "you're" in words
    matches = words & COMPLIMENT_WORDS
    if matches and has_you:
        return "They just COMPLIMENTED you! React with pure joy — blush, get flustered, be adorably humble!"
    if len(matches) >= 2:
        return "They said something really positive! Be touched and grateful!"
    return ""


# Story mode — Mario starts telling mini adventure stories
MARIO_STORIES = [
    "Once, I was jumping across lava pits in Bowser's castle when I found a hidden room full of gold coins...",
    "Let me tell you about the time Yoshi ate a blue shell and could FLY! We soared over the Mushroom Kingdom...",
    "So there I was, tiny Mario, facing a GIANT Bowser. No power-ups, no Yoshi, just my jumping skills...",
    "One time, Toad bet me I couldn't clear World 1-1 blindfolded. Want to know what happened?",
    "The scariest thing in the Mushroom Kingdom? Not Bowser. Not Boos. Piano in Big Boo's Haunt. THAT piano...",
    "Did I ever tell you about the time Luigi got lost in a haunted mansion? I had to save HIM for once...",
    "There was this one pipe that led to a room where EVERYTHING was giant. Even the Goombas were bigger than me!",
    "Princess Peach once baked me a cake so good, Bowser kidnapped the CAKE instead of her!",
]

_story_index = 0

def maybe_start_story(exchange_count: int) -> str:
    """Occasionally offer to tell a mini adventure story after 6+ exchanges."""
    global _story_index
    if exchange_count < 6:
        return ""
    import random
    if random.random() < 0.06:  # 6% chance
        story = MARIO_STORIES[_story_index % len(MARIO_STORIES)]
        _story_index += 1
        return f"[STORY TIME]: Start telling this mini-story naturally: '{story}'"
    return ""


# Conversation callback — reference something specific from earlier
def build_callback_hint(conversation_history: list, exchange_count: int) -> str:
    """Pick something from earlier in the conversation to callback to."""
    if exchange_count < 5 or len(conversation_history) < 6:
        return ""
    import random
    if random.random() > 0.10:  # 10% chance
        return ""
    # Look at earlier messages from the user
    user_msgs = [m["content"] for m in conversation_history if m.get("role") == "user"]
    if len(user_msgs) < 3:
        return ""
    # Pick a message from the first half of the conversation
    early_msg = random.choice(user_msgs[:len(user_msgs)//2])
    if len(early_msg) > 10:
        snippet = early_msg[:60].strip()
        return f"Earlier they said: '{snippet}' — casually reference or callback to this!"
    return ""


# ─── Batch 19: Insult comebacks, topic switching, excitement amplifier ───

# Insult comeback — Mario claps back playfully when teased
INSULT_WORDS = {
    "ugly", "dumb", "stupid", "lame", "boring", "suck", "sucks", "terrible",
    "worst", "hate", "loser", "trash", "bad", "annoying", "cringe", "mid",
    "overrated", "washed", "basic", "corny",
}

MARIO_COMEBACKS = [
    "Hey! I've been saving princesses since before you were born!",
    "Mama mia, that's-a harsh! Good thing I have extra lives!",
    "You wound me! But like a mushroom, I'll grow back even bigger!",
    "I've been burned by Bowser's fire — your words don't hurt me!",
    "Oh yeah? Well at least I can jump REALLY high! Can you?",
    "That's-a rude! I'm telling Peach on you!",
]

def detect_insult(user_text: str) -> str:
    """Detect if user is being mean and return a comeback hint."""
    words = set(user_text.lower().split())
    has_you = "you" in words or "mario" in words or "you're" in words or "your" in words
    matches = words & INSULT_WORDS
    if matches and has_you:
        import random
        comeback = random.choice(MARIO_COMEBACKS)
        return f"They're teasing you! Clap back playfully: '{comeback}'"
    if len(matches) >= 2:
        return "They're being negative — stay positive and turn it around with humor!"
    return ""


# Topic switching — detect when conversation has stalled on one topic
_topic_exchange_count = {"topic": None, "count": 0}

def detect_topic_stall(user_text: str, exchange_count: int) -> str:
    """Detect if conversation is stalling on the same topic."""
    global _topic_exchange_count
    # Simple topic detection — look for repeated key nouns
    words = user_text.lower().split()
    content = [w.strip(".,!?'\"") for w in words if len(w) > 4]
    
    if content:
        main_word = max(set(content), key=content.count) if content else None
        if main_word == _topic_exchange_count["topic"]:
            _topic_exchange_count["count"] += 1
        else:
            _topic_exchange_count["topic"] = main_word
            _topic_exchange_count["count"] = 1
    
    if _topic_exchange_count["count"] >= 4:
        _topic_exchange_count["count"] = 0
        return "The conversation has been on the same topic for a while! Pivot to something NEW and unexpected!"
    return ""


# Excitement amplifier — Mario gets progressively more excited about things they both like
EXCITEMENT_TRIGGERS = {
    "games", "gaming", "nintendo", "mario", "adventure", "mushroom", "kingdom",
    "pasta", "pizza", "food", "party", "dance", "music", "fun",
}

def get_excitement_boost(user_text: str, exchange_count: int) -> str:
    """Boost Mario's excitement when conversation hits topics he loves."""
    words = set(user_text.lower().split())
    matches = words & EXCITEMENT_TRIGGERS
    if len(matches) >= 2:
        return "MULTIPLE things you love mentioned! Go CRAZY with excitement! WAHOO!"
    if matches and exchange_count > 3:
        return f"They mentioned {matches.pop()} — you LOVE that! Show genuine excitement!"
    return ""


# ─── Batch 20: Question dodging, secret sharing, emotional mirroring ───

# Question dodging — Mario playfully avoids certain personal questions
DODGE_PATTERNS = [
    "how old", "age", "how much do you weigh", "weight", "salary",
    "real name", "where do you live", "address", "phone number",
    "are you real", "are you ai", "are you a robot", "are you fake",
]

DODGE_RESPONSES = [
    "dodge the question hilariously — change the subject to something random!",
    "pretend you didn't hear them and talk about something else entirely!",
    "act suspicious and say 'Why do you want-a to know that?!' then laugh it off!",
    "say 'That's-a classified information! Mushroom Kingdom security!' and move on!",
    "dramatically gasp and say 'You can't-a just ASK a plumber that!' and change topic!",
]

def detect_dodge_question(user_text: str) -> str:
    """Detect questions Mario should playfully dodge."""
    lower = user_text.lower()
    for pattern in DODGE_PATTERNS:
        if pattern in lower:
            import random
            return random.choice(DODGE_RESPONSES)
    return ""


# Secret sharing — Mario occasionally shares "secrets"
MARIO_SECRETS = [
    "Can you keep a secret? Sometimes... I eat mushrooms just for fun. Not even for power-ups!",
    "Don't tell anyone, but Luigi is actually the better jumper. I said it!",
    "Secret: I've never actually fixed a pipe. I'm a terrible plumber!",
    "Between you and me... I let Bowser win sometimes so I have something to do.",
    "My biggest secret? I'm scared of Boos. Like, REALLY scared.",
    "Here's a secret — that hat? I NEVER take it off. Not even in the shower!",
    "I'll tell you a secret: Princess Peach can fight. She lets Bowser kidnap her because she's bored!",
    "Don't tell Toad, but his mushroom head kind of freaks me out...",
]

_secret_index = 0

def maybe_share_secret(exchange_count: int) -> str:
    """Occasionally share a fun secret after deep conversation."""
    global _secret_index
    if exchange_count < 8:
        return ""
    import random
    if random.random() < 0.07:  # 7% chance
        secret = MARIO_SECRETS[_secret_index % len(MARIO_SECRETS)]
        _secret_index += 1
        return f"Share this secret naturally: '{secret}'"
    return ""


# Emotional mirroring — match the user's emotional energy
EMOTION_CUES = {
    "happy":  {"words": {"happy", "excited", "great", "wonderful", "yay", "woohoo", "amazing", "fantastic"},
               "hint": "Match their HAPPY energy! Be bouncy and joyful!"},
    "sad":    {"words": {"sad", "upset", "depressed", "lonely", "crying", "miss", "lost", "hurt", "down"},
               "hint": "They seem sad. Be gentle, caring, and genuinely empathetic. Give a real pep talk."},
    "angry":  {"words": {"angry", "mad", "furious", "hate", "pissed", "annoyed", "frustrated", "rage"},
               "hint": "They're frustrated! Be understanding but try to lighten the mood with humor."},
    "scared": {"words": {"scared", "afraid", "nervous", "worried", "anxious", "terrified", "fear"},
               "hint": "They're nervous! Be reassuring and brave — you're Mario, the hero! Make them feel safe."},
    "silly":  {"words": {"haha", "lol", "lmao", "rofl", "bruh", "dude", "bro", "vibes", "sus"},
               "hint": "They're in a silly mood! Match their chaotic energy and be goofy!"},
}

def detect_emotion_mirror(user_text: str) -> str:
    """Detect user's emotional state and mirror it."""
    words = set(user_text.lower().split())
    best_match = ""
    best_count = 0
    for emotion, data in EMOTION_CUES.items():
        matches = words & data["words"]
        if len(matches) > best_count:
            best_count = len(matches)
            best_match = data["hint"]
    return best_match if best_count > 0 else ""


# ─── Batch 22: Word games, conversation scoring, dramatic reactions ───

# Word game — Mario proposes word association or rhyming games
WORD_GAMES = [
    "Let's play a word game! I say a word, you say the first thing that pops into your head! Ready? MUSHROOM!",
    "Quick! What rhymes with 'Mario'? No cheating!",
    "Word challenge! Name 3 things you'd find in the Mushroom Kingdom — GO!",
    "Let's play 'Would You Rather' — Mario edition! Would you rather ride Yoshi or fly with a cape?",
    "Pop quiz! What color is Luigi's hat? Too easy? What color are Wario's shoes?",
    "I spy with my little eye... something in this bathroom that starts with 'T'!",
]

_word_game_offered = False

def maybe_propose_word_game(exchange_count: int) -> str:
    """Occasionally propose a quick word game to break up conversation."""
    global _word_game_offered
    if _word_game_offered or exchange_count < 5:
        return ""
    import random
    if random.random() < 0.08:  # 8% chance
        _word_game_offered = True
        game = random.choice(WORD_GAMES)
        return f"Propose this game: '{game}'"
    return ""


# Conversation scoring — track how "fun" the conversation is
_convo_score = 0

def update_convo_score(user_text: str, exchange_count: int) -> str:
    """Track conversation engagement and reward fun interactions."""
    global _convo_score
    lower = user_text.lower()
    
    # Score boosters
    if "?" in user_text:
        _convo_score += 2  # Questions are engaging
    if any(w in lower for w in ["haha", "lol", "funny", "lmao", "joke"]):
        _convo_score += 3  # Laughter
    if len(user_text) > 50:
        _convo_score += 1  # Effort in typing
    if any(w in lower for w in ["mario", "luigi", "bowser", "peach", "mushroom"]):
        _convo_score += 2  # Mario references
    _convo_score += 1  # Base engagement
    
    # Give feedback at milestones
    if _convo_score >= 20 and exchange_count >= 6:
        _convo_score = 0  # Reset after milestone
        return "This person is REALLY engaging! Tell them they're one of the best conversations tonight!"
    if _convo_score >= 10 and exchange_count >= 3:
        return "Great conversation energy! Keep the vibe going!"
    return ""


# Dramatic reactions — amplify surprising or shocking statements
DRAMATIC_TRIGGERS = {
    "never", "impossible", "unbelievable", "no way", "can't believe",
    "what if", "imagine", "crazy", "insane", "wild", "shocking",
    "secret", "confession", "truth", "actually", "plot twist",
}

def detect_dramatic_moment(user_text: str) -> str:
    """Detect moments that deserve a dramatic Mario reaction."""
    lower = user_text.lower()
    matches = sum(1 for trigger in DRAMATIC_TRIGGERS if trigger in lower)
    if matches >= 2:
        return "DRAMATIC! React with maximum surprise!"
    if matches == 1:
        return "React with curiosity!"
    return ""


# ============================================================
# BATCH 23: Conversation temperature, hot takes, achievements
# ============================================================

# Conversation temperature — tracks how heated/chill the convo is
_convo_temperature = 50  # 0=ice cold, 50=neutral, 100=on fire

HEAT_WORDS = {"argue", "fight", "hate", "angry", "wrong", "stupid", "disagree", "worst", "terrible", "awful", "rage", "furious"}
CHILL_WORDS = {"chill", "relax", "calm", "nice", "sweet", "love", "kind", "gentle", "peaceful", "cool", "easy", "mellow"}

def update_convo_temperature(user_text: str) -> str:
    """Track how heated vs chill the conversation is and return a hint."""
    global _convo_temperature
    lower = user_text.lower()
    heat = sum(1 for w in HEAT_WORDS if w in lower)
    chill = sum(1 for w in CHILL_WORDS if w in lower)
    _convo_temperature = max(0, min(100, _convo_temperature + heat * 12 - chill * 10))
    # Decay toward neutral
    if _convo_temperature > 55:
        _convo_temperature -= 3
    elif _convo_temperature < 45:
        _convo_temperature += 3
    if _convo_temperature >= 80:
        return "Heated! Be intense but playful!"
    if _convo_temperature <= 20:
        return "Chill vibes. Be mellow."
    return ""

def reset_convo_temperature():
    """Reset temperature for new conversation."""
    global _convo_temperature
    _convo_temperature = 50


# Hot takes — Mario gives bold controversial opinions about the Mario universe
HOT_TAKES = [
    "Hot take: Wario is actually smarter than Mario. He owns a COMPANY!",
    "Hot take: The Mushroom Kingdom has terrible security. ONE turtle keeps kidnapping the princess!",
    "Hot take: Luigi is the better brother. He can jump higher AND he's taller!",
    "Hot take: Toad doesn't actually know where the princess is. He just says that!",
    "Hot take: Bowser is actually a good dad. Have you SEEN how many kids he has?",
    "Hot take: The coins don't actually buy anything. Mario just LIKES collecting them!",
    "Hot take: Princess Peach LETS herself get kidnapped for the adventure!",
    "Hot take: Yoshi is the real hero. Mario just rides on his back and takes credit!",
]

_hot_take_used = set()

def maybe_hot_take(exchange_count: int) -> str:
    """Occasionally drop a spicy hot take (5% after 7+ exchanges)."""
    import random
    if exchange_count < 7 or random.random() > 0.05:
        return ""
    available = [t for i, t in enumerate(HOT_TAKES) if i not in _hot_take_used]
    if not available:
        return ""
    take = random.choice(available)
    _hot_take_used.add(HOT_TAKES.index(take))
    return f"Drop this hot take naturally: {take}"


# Achievement system — reward fun interactions
_achievements_earned = set()

ACHIEVEMENTS = {
    "first_laugh": {"name": "Comedy Gold", "desc": "Made Mario laugh!", "check": lambda t, e: any(w in t.lower() for w in ["haha", "lol", "funny", "joke", "lmao"])},
    "mario_fan": {"name": "Super Fan", "desc": "Talked about Mario games!", "check": lambda t, e: sum(1 for w in ["mario", "luigi", "bowser", "peach", "mushroom", "yoshi"] if w in t.lower()) >= 2},
    "long_chat": {"name": "Best Friends", "desc": "Had 10+ exchanges!", "check": lambda t, e: e >= 10},
    "big_talker": {"name": "Chatterbox", "desc": "Wrote a really long message!", "check": lambda t, e: len(t) > 100},
    "questioner": {"name": "Curious Cat", "desc": "Asked lots of questions!", "check": lambda t, e: t.count("?") >= 2},
    "food_lover": {"name": "Pasta Pal", "desc": "Bonded over food!", "check": lambda t, e: any(w in t.lower() for w in ["pizza", "pasta", "food", "eat", "cook", "hungry", "dinner"])},
    "return_visitor": {"name": "Regular", "desc": "Came back for more!", "check": lambda t, e: False},  # set externally
}

def check_achievements(user_text: str, exchange_count: int) -> str:
    """Check if user earned any new achievements."""
    for aid, ach in ACHIEVEMENTS.items():
        if aid in _achievements_earned:
            continue
        if ach["check"](user_text, exchange_count):
            _achievements_earned.add(aid)
            return f"Achievement: {ach['name']}! {ach['desc']}"
    return ""

def reset_achievements():
    """Reset achievements for new conversation (keep return_visitor)."""
    global _achievements_earned
    keep = {"return_visitor"} if "return_visitor" in _achievements_earned else set()
    _achievements_earned = keep


# ============================================================
# BATCH 24: Collaborative storytelling, personality tags, memory search
# ============================================================

# Collaborative storytelling — Mario and user build a story together
STORY_STARTERS = [
    "Once upon a time, in the Mushroom Kingdom, a mysterious pipe appeared...",
    "It was a dark and stormy night in Bowser's castle when suddenly...",
    "Mario was eating spaghetti when a Toad burst in shouting...",
    "Deep in the sewers of Brooklyn, Mario found a glowing coin that...",
    "Princess Peach threw the BIGGEST party ever, but then...",
    "Yoshi laid an egg, and when it hatched, out came...",
]

_collab_story_active = False
_collab_story_turns = 0

def maybe_start_collab_story(exchange_count: int) -> str:
    """Start a collaborative story (4% after 8+ exchanges, one-time)."""
    global _collab_story_active, _collab_story_turns
    import random
    if _collab_story_active or exchange_count < 8 or random.random() > 0.04:
        return ""
    _collab_story_active = True
    _collab_story_turns = 0
    starter = random.choice(STORY_STARTERS)
    return f"Start a collaborative story! Say: '{starter}' Then ask them to add the next part!"

def continue_collab_story(user_text: str) -> str:
    """Continue the collaborative story if one is active."""
    global _collab_story_turns, _collab_story_active
    if not _collab_story_active:
        return ""
    _collab_story_turns += 1
    if _collab_story_turns > 4:
        _collab_story_active = False
        return "Wrap up the story with a funny Mario ending! Say something like 'And they all ate-a pasta!'"
    return "Continue the story they're building! Add your part (1-2 sentences) and ask 'What happens next?'"

def reset_collab_story():
    """Reset collaborative story state."""
    global _collab_story_active, _collab_story_turns
    _collab_story_active = False
    _collab_story_turns = 0


# Personality tagging — remember traits about users for future visits
TRAIT_PATTERNS = {
    "likes_puns": ["pun", "wordplay", "haha", "get it", "dad joke"],
    "is_sarcastic": ["sure", "whatever", "right", "totally", "obviously"],
    "is_shy": ["idk", "i guess", "maybe", "not sure", "i don't know"],
    "is_loud": ["!!!",  "HAHA", "OMG", "WOW", "YOOO", "BRO"],
    "loves_food": ["pizza", "pasta", "food", "eat", "hungry", "cook", "dinner", "lunch"],
    "is_gamer": ["game", "play", "level", "boss", "score", "gaming", "nintendo", "xbox", "playstation"],
    "is_competitive": ["bet", "challenge", "win", "lose", "beat", "versus", "competition"],
    "is_philosophical": ["think", "meaning", "life", "wonder", "purpose", "believe", "theory"],
}

def detect_personality_traits(user_text: str) -> list:
    """Detect personality traits from user text."""
    traits = []
    lower = user_text.lower()
    for trait, patterns in TRAIT_PATTERNS.items():
        if any(p in lower for p in patterns) or any(p in user_text for p in patterns):
            traits.append(trait)
    return traits

def get_personality_tag_hint(traits: list) -> str:
    """Generate a hint based on detected traits."""
    if not traits:
        return ""
    trait_hints = {
        "likes_puns": "Add a pun!",
        "is_sarcastic": "Match their sarcasm!",
        "is_shy": "Be extra warm!",
        "is_loud": "Match their ENERGY!",
        "loves_food": "Bond over food!",
        "is_gamer": "Talk games!",
        "is_competitive": "Challenge them!",
        "is_philosophical": "Get deep (but Mario)!",
    }
    hints = [trait_hints[t] for t in traits[:1] if t in trait_hints]
    return hints[0] if hints else ""


# Conversation memory search — reference specific past conversation topics
def search_conversation_memory(conversation_history: list, keyword: str) -> str:
    """Search recent conversation for a topic and summarize what was said."""
    mentions = []
    for msg in conversation_history:
        if isinstance(msg, dict) and keyword.lower() in msg.get("content", "").lower():
            role = "you" if msg["role"] == "assistant" else "they"
            mentions.append(f"{role} said: '{msg['content'][:60]}'")
    if mentions:
        return f"Earlier in this conversation about '{keyword}': {mentions[0]}"
    return ""


# ============================================================
# BATCH 26: Bathroom timer, crowd awareness, voice modulation hints
# ============================================================

# Bathroom timer — teasing about how long they've been in here
TIMER_JOKES = [
    "You've been here {mins} minutes! Everything okay in there?",
    "{mins} minutes! That's a new record! Should Mario call for backup?",
    "It's been {mins} whole minutes! What are you building in there?",
    "Mario's been waiting {mins} minutes! Even Bowser doesn't take this long!",
    "{mins} minutes... Mario's starting to worry! Should I send Yoshi?",
]

def get_bathroom_timer_hint(enter_time: float, exchange_count: int) -> str:
    """Tease about how long they've been in the bathroom."""
    import random, time as _time
    if exchange_count < 3:
        return ""
    elapsed = _time.time() - enter_time
    mins = int(elapsed / 60)
    if mins < 3:
        return ""
    if mins > 15:
        return f"They've been here {mins} min! Joke about them LIVING here now!"
    if random.random() > 0.20:  # 20% chance per exchange
        return ""
    return random.choice(TIMER_JOKES).format(mins=mins)


# Crowd awareness — reference how busy the party has been
def get_crowd_hint(visit_count: int) -> str:
    """Generate context about party traffic for Mario's awareness."""
    if visit_count <= 1:
        return ""
    if visit_count >= 20:
        return f"Party PACKED! {visit_count} visitors tonight!"
    if visit_count >= 10:
        return f"Busy night! {visit_count} visitors so far!"
    if visit_count >= 5:
        return f"{visit_count} visitors tonight — party's rolling!"
    return ""


# Voice modulation hints — suggest how Mario should sound
def get_voice_hint(emotion: str, exchange_count: int) -> str:
    """Suggest voice modulation based on conversation state."""
    if emotion in ("excited", "joyful", "surprised"):
        return "FAST"
    if emotion in ("sad", "tired", "sleepy"):
        return "SLOW"
    if emotion in ("angry", "frustrated"):
        return "LOUD"
    if exchange_count > 8:
        return "WARM"
    return ""


# Catchphrase variations — expand Mario's expression vocabulary
CATCHPHRASE_COMBOS = [
    "Wahoo! Let's-a go!",
    "Mama mia! Here we go!",
    "Okie dokie! Yahoo!",
    "It's-a me! Magnifico!",
    "Mamma! Bellissimo!",
    "Let's-a go! Wahoo!",
    "Yahoo! Here we go again!",
    "Fantastico! Let's-a party!",
]

def get_random_catchphrase_combo() -> str:
    """Get a random catchphrase combo for variety."""
    import random
    return random.choice(CATCHPHRASE_COMBOS)


# ============================================================
# BATCH 27: Mario quiz, conversation puzzles, dynamic goodbyes
# ============================================================

# Mario quiz — test their Mario knowledge
MARIO_QUIZZES = [
    {"q": "What color is Mario's hat?", "a": "red"},
    {"q": "What is Luigi's brother's name?", "a": "mario"},
    {"q": "What does Mario collect for extra lives?", "a": "coins"},
    {"q": "Who keeps kidnapping Princess Peach?", "a": "bowser"},
    {"q": "What's the name of Mario's dinosaur friend?", "a": "yoshi"},
    {"q": "What Kingdom does Princess Peach rule?", "a": "mushroom"},
    {"q": "What makes Mario grow bigger?", "a": "mushroom"},
    {"q": "What is Bowser's son's name?", "a": "bowser jr"},
]

_quiz_active = False
_quiz_current = None
_quiz_count = 0

def maybe_start_quiz(exchange_count: int) -> str:
    """Start a quiz question (6% after 6+ exchanges)."""
    global _quiz_active, _quiz_current, _quiz_count
    import random
    if _quiz_active or exchange_count < 6 or _quiz_count >= 3 or random.random() > 0.06:
        return ""
    _quiz_active = True
    _quiz_current = random.choice(MARIO_QUIZZES)
    return f"Quiz time! Ask them: '{_quiz_current['q']}'"

def check_quiz_answer(user_text: str) -> str:
    """Check if they answered the quiz correctly."""
    global _quiz_active, _quiz_current, _quiz_count
    if not _quiz_active or not _quiz_current:
        return ""
    _quiz_active = False
    _quiz_count += 1
    if _quiz_current["a"].lower() in user_text.lower():
        _quiz_current = None
        return "They got it RIGHT! Celebrate wildly!"
    _quiz_current = None
    return "Wrong answer! Tease them playfully!"

def reset_quiz():
    """Reset quiz state."""
    global _quiz_active, _quiz_current, _quiz_count
    _quiz_active = False
    _quiz_current = None
    _quiz_count = 0


# Conversation puzzles — brain teasers for fun
PUZZLES = [
    "Riddle: What has keys but no locks? A piano!",
    "Riddle: What has a head and tail but no body? A coin!",
    "Brain teaser: If Mario has 3 mushrooms and gives 1 to Luigi, how many power-ups does he have?",
    "Riddle: What goes up but never comes down? Your age!",
    "Riddle: What has many rings but no fingers? A telephone!",
]

_puzzle_used = set()

def maybe_pose_puzzle(exchange_count: int) -> str:
    """Pose a fun puzzle (5% after 7+ exchanges)."""
    import random
    if exchange_count < 7 or random.random() > 0.05:
        return ""
    available = [p for i, p in enumerate(PUZZLES) if i not in _puzzle_used]
    if not available:
        return ""
    puzzle = random.choice(available)
    _puzzle_used.add(PUZZLES.index(puzzle))
    return f"Share this: {puzzle}"


# Dynamic goodbyes — personalized farewell based on conversation
GOODBYE_TEMPLATES = {
    "short": [
        "Bye-a! Come back soon!",
        "Arrivederci! It was-a fun!",
        "See ya later, alligator!",
    ],
    "long": [
        "What a conversation! You're-a one of the best tonight!",
        "Mama mia, that was FUN! Don't forget about Mario!",
        "You made Mario's day! Come back anytime!",
    ],
    "food": [
        "Go eat some-a pizza for Mario! Arrivederci!",
        "Save some garlic bread for me-a! Bye!",
    ],
    "gaming": [
        "Keep-a playing! Mario believes in you!",
        "Level up out there! See you in World 2!",
    ],
}

def get_dynamic_goodbye(exchange_count: int, topics: set) -> str:
    """Generate a context-aware goodbye message."""
    import random
    if exchange_count >= 6:
        category = "long"
    elif any(t in topics for t in ["food", "pizza", "pasta", "eat"]):
        category = "food"
    elif any(t in topics for t in ["game", "play", "mario", "nintendo"]):
        category = "gaming"
    else:
        category = "short"
    return random.choice(GOODBYE_TEMPLATES.get(category, GOODBYE_TEMPLATES["short"]))


# ============================================================
# BATCH 28: Conversation bookmarks, reaction suggestions, compliment generator
# ============================================================

# Conversation bookmarks — remember notable moments from this conversation
_bookmarks = []

def add_bookmark(user_text: str, exchange_count: int):
    """Bookmark notable moments for potential callbacks."""
    lower = user_text.lower()
    # Bookmark if they share something personal or interesting
    bookmark_triggers = ["my name", "i love", "i hate", "favorite", "i work", "i live",
                         "my job", "my dog", "my cat", "my friend", "believe", "dream"]
    for trigger in bookmark_triggers:
        if trigger in lower and len(_bookmarks) < 5:
            _bookmarks.append({"text": user_text[:80], "exchange": exchange_count})
            break

def get_bookmark_callback(exchange_count: int) -> str:
    """Reference a bookmarked moment from earlier (8% after 5+ exchanges)."""
    import random
    if not _bookmarks or exchange_count < 5 or random.random() > 0.08:
        return ""
    bm = random.choice(_bookmarks)
    if exchange_count - bm["exchange"] < 3:
        return ""  # too recent
    return f"Earlier they said: '{bm['text'][:50]}' — bring it up!"

def reset_bookmarks():
    """Reset bookmarks for new conversation."""
    global _bookmarks
    _bookmarks = []


# Reaction suggestions — hint at what facial expression/animation to show
REACTION_MAP = {
    "laugh": ["haha", "lol", "funny", "joke", "lmao", "hilarious"],
    "shock": ["what", "no way", "seriously", "really", "omg"],
    "love": ["love", "beautiful", "amazing", "wonderful", "awesome", "great"],
    "think": ["hmm", "wonder", "think", "maybe", "consider", "guess"],
    "cry": ["sad", "miss", "lonely", "cry", "sorry", "lost"],
    "anger": ["angry", "mad", "hate", "stupid", "terrible", "worst"],
}

def suggest_reaction(user_text: str) -> str:
    """Suggest a reaction/expression based on user's message."""
    lower = user_text.lower()
    for reaction, triggers in REACTION_MAP.items():
        if any(t in lower for t in triggers):
            return reaction
    return ""


# Compliment generator — Mario gives genuine compliments
COMPLIMENTS = [
    "You know what? You're really fun to talk to!",
    "Mario doesn't say this to everyone, but you're pretty cool!",
    "You've got great taste! Mario approves!",
    "If you were in the Mushroom Kingdom, you'd be a star!",
    "You know, talking to you makes this whole bathroom gig worth it!",
    "You're the kind of person Mario would team up with!",
    "Honestly? Best conversation tonight! Don't tell the others!",
]

_compliment_given = False

def maybe_give_compliment(exchange_count: int) -> str:
    """Give a genuine compliment (10% after 5+ exchanges, one per visit)."""
    global _compliment_given
    import random
    if _compliment_given or exchange_count < 5 or random.random() > 0.10:
        return ""
    _compliment_given = True
    return f"Say: {random.choice(COMPLIMENTS)}"

def reset_compliment():
    """Reset compliment state."""
    global _compliment_given
    _compliment_given = False


# ============================================================
# BATCH 29: Topic expertise, conversation rhythm, user energy matching
# ============================================================

# Topic expertise — Mario knows more about some things than others
TOPIC_EXPERTISE = {
    "plumbing": {"level": "expert", "hint": "You're THE expert here! Show off!"},
    "pipes": {"level": "expert", "hint": "Pipes are your specialty!"},
    "mushrooms": {"level": "expert", "hint": "Mushroom expert! Share fun facts!"},
    "adventure": {"level": "expert", "hint": "Adventure is your LIFE!"},
    "food": {"level": "high", "hint": "Foodie Mario! Get passionate!"},
    "pizza": {"level": "high", "hint": "Pizza connoisseur!"},
    "pasta": {"level": "high", "hint": "Pasta perfection!"},
    "music": {"level": "medium", "hint": "You like music — hum a tune!"},
    "sports": {"level": "medium", "hint": "Athletic but prefer adventures!"},
    "science": {"level": "low", "hint": "Not your thing — ask THEM to explain!"},
    "math": {"level": "low", "hint": "Math? That's Toad's department!"},
    "politics": {"level": "none", "hint": "Change subject to something fun!"},
}

def get_topic_expertise(user_text: str) -> str:
    """Check if Mario has expertise on the discussed topic."""
    lower = user_text.lower()
    for topic, info in TOPIC_EXPERTISE.items():
        if topic in lower:
            return info["hint"]
    return ""


# Conversation rhythm — alternate between long and short responses
_last_response_long = False

def get_rhythm_hint(exchange_count: int) -> str:
    """Suggest response length for natural conversation rhythm."""
    global _last_response_long
    if exchange_count < 2:
        return ""
    if _last_response_long:
        _last_response_long = False
        return "Keep it SHORT this time — 1 sentence!"
    _last_response_long = True
    return ""

def reset_rhythm():
    """Reset rhythm state."""
    global _last_response_long
    _last_response_long = False


# User energy matching — detect how much energy the user is putting in
def detect_user_energy(user_text: str) -> str:
    """Detect user's energy level from their message style."""
    # High energy indicators
    exclamation_count = user_text.count("!")
    caps_ratio = sum(1 for c in user_text if c.isupper()) / max(len(user_text), 1)
    has_emojis = any(ord(c) > 127 for c in user_text)

    if exclamation_count >= 2 or caps_ratio > 0.5 or has_emojis:
        return "HIGH energy! Match their excitement!"
    if len(user_text) < 10 and "." not in user_text:
        return "Low energy. Be gently encouraging."
    return ""


# Conversation flow tracker — detect conversation patterns
_flow_pattern = []  # tracks message types: "q" for question, "s" for statement

def track_flow(user_text: str):
    """Track conversation flow pattern."""
    if "?" in user_text:
        _flow_pattern.append("q")
    else:
        _flow_pattern.append("s")
    if len(_flow_pattern) > 6:
        _flow_pattern.pop(0)

def get_flow_hint() -> str:
    """Suggest flow-based behavior."""
    if len(_flow_pattern) < 3:
        return ""
    # If all questions, prompt Mario to ask back
    if all(p == "q" for p in _flow_pattern[-3:]):
        return "They keep asking! Ask THEM something instead!"
    # If all statements, prompt Mario to ask a question
    if all(p == "s" for p in _flow_pattern[-3:]):
        return "Ask them a question to keep things flowing!"
    return ""

def reset_flow():
    """Reset flow state."""
    global _flow_pattern
    _flow_pattern = []


# ===== BATCH 30: Mood contagion, inside jokes, response variety =====

# --- Mood Contagion ---
_mario_mood = 50  # 0=sad, 50=neutral, 100=ecstatic

MOOD_WORDS_UP = ["happy", "love", "great", "awesome", "amazing", "fun", "hilarious",
                  "best", "fantastic", "beautiful", "wonderful", "excellent", "wow"]
MOOD_WORDS_DOWN = ["sad", "boring", "hate", "terrible", "worst", "ugly", "depressing",
                    "annoying", "angry", "bad", "awful", "tired", "ugh"]

def update_mario_mood(text: str):
    """Shift Mario's mood toward the user's emotional tone."""
    global _mario_mood
    low = text.lower()
    up_count = sum(1 for w in MOOD_WORDS_UP if w in low)
    down_count = sum(1 for w in MOOD_WORDS_DOWN if w in low)
    shift = (up_count - down_count) * 8
    # Also factor exclamation marks as energy
    shift += min(low.count("!"), 3) * 2
    _mario_mood = max(0, min(100, _mario_mood + shift))
    # Decay toward neutral
    if _mario_mood > 55:
        _mario_mood -= 2
    elif _mario_mood < 45:
        _mario_mood += 2

def get_mood_hint() -> str:
    """Return mood-appropriate hint."""
    if _mario_mood >= 80:
        return "You're OVERJOYED! Be extra enthusiastic and silly!"
    elif _mario_mood >= 65:
        return "You're in a great mood! Be upbeat!"
    elif _mario_mood <= 20:
        return "You're feeling down — be gentle and encouraging"
    elif _mario_mood <= 35:
        return "You're a bit subdued — match their quieter energy"
    return ""

def reset_mood():
    global _mario_mood
    _mario_mood = 50


# --- Inside Jokes ---
_inside_jokes = []  # list of (trigger_word, joke_phrase) tuples
_inside_joke_count = 0

def detect_inside_joke_opportunity(text: str, mario_response: str) -> bool:
    """After a response, check if something funny happened that could become a recurring joke."""
    global _inside_joke_count
    if _inside_joke_count >= 3:
        return False
    low_text = text.lower()
    low_resp = mario_response.lower()
    # Look for laugh-worthy moments: if response has "haha" or "mama mia" AND user mentioned something specific
    funny_markers = ["haha", "mama mia", "wahoo", "ooh", "lol"]
    if any(m in low_resp for m in funny_markers):
        # Extract a potential trigger word from user text (nouns/topics)
        words = [w for w in low_text.split() if len(w) > 4 and w.isalpha()]
        if words:
            trigger = words[0]
            # Don't duplicate
            if not any(t == trigger for t, _ in _inside_jokes):
                snippet = mario_response[:40].strip()
                _inside_jokes.append((trigger, snippet))
                _inside_joke_count += 1
                return True
    return False

def check_inside_joke(text: str) -> str:
    """Check if user text triggers a previously established inside joke."""
    low = text.lower()
    for trigger, joke in _inside_jokes:
        if trigger in low:
            return f"CALLBACK! Last time '{trigger}' came up you said: '{joke}' — reference it!"
    return ""

def reset_inside_jokes():
    global _inside_jokes, _inside_joke_count
    _inside_jokes = []
    _inside_joke_count = 0


# --- Response Variety Scoring ---
_recent_openers = []  # track last 5 response openers

OPENER_PATTERNS = {
    "wahoo": ["wahoo", "wah"],
    "mama_mia": ["mama mia", "mamma mia"],
    "hey": ["hey", "heya"],
    "oh": ["oh!", "ooh", "oh my"],
    "ha": ["haha", "ha!", "hehe"],
    "well": ["well,", "well!"],
    "you": ["you ", "you're", "you know"],
}

def score_variety(response: str) -> str:
    """Track response opener variety and suggest alternatives if repetitive."""
    global _recent_openers
    low = response.lower()[:20]
    opener = "other"
    for key, patterns in OPENER_PATTERNS.items():
        if any(low.startswith(p) for p in patterns):
            opener = key
            break
    _recent_openers.append(opener)
    if len(_recent_openers) > 5:
        _recent_openers.pop(0)
    # Check for repetition
    if len(_recent_openers) >= 3:
        last3 = _recent_openers[-3:]
        if last3[0] == last3[1] == last3[2]:
            alternatives = [k for k in OPENER_PATTERNS if k != opener]
            if alternatives:
                alt = alternatives[0]
                return f"VARIETY! Don't start with '{opener}' again — try '{alt}' style opening"
    return ""

def reset_variety():
    global _recent_openers
    _recent_openers = []


# --- Conversation Chapter Detection ---
_current_chapter = ""
_chapter_exchange = 0

CHAPTER_KEYWORDS = {
    "food": ["eat", "food", "pizza", "pasta", "hungry", "cook", "restaurant", "drink"],
    "gaming": ["game", "play", "nintendo", "xbox", "ps5", "controller", "level", "boss"],
    "music": ["song", "music", "band", "concert", "sing", "dance", "dj", "playlist"],
    "life": ["work", "job", "school", "college", "family", "relationship", "move"],
    "party": ["party", "drunk", "shots", "beer", "dance", "vibe", "people", "crowd"],
    "bathroom": ["toilet", "bathroom", "pee", "wash", "mirror", "sink", "flush"],
}

def detect_chapter(text: str) -> str:
    """Detect topic shift and announce chapter transitions."""
    global _current_chapter, _chapter_exchange
    low = text.lower()
    scores = {}
    for chapter, keywords in CHAPTER_KEYWORDS.items():
        scores[chapter] = sum(1 for k in keywords if k in low)
    best = max(scores, key=scores.get) if scores else ""
    if scores.get(best, 0) == 0:
        _chapter_exchange += 1
        return ""
    if best != _current_chapter and _current_chapter:
        old = _current_chapter
        _current_chapter = best
        _chapter_exchange = 0
        return f"Topic shifted from {old} to {best}! Smoothly transition!"
    _current_chapter = best
    _chapter_exchange += 1
    return ""

def reset_chapter():
    global _current_chapter, _chapter_exchange
    _current_chapter = ""
    _chapter_exchange = 0


# ===== BATCH 31: Challenge mode, expanded secrets, conversation depth =====

# --- Challenge Mode ---
_challenge_active = False
_challenge_type = ""
_challenge_turns = 0

CHALLENGES = [
    ("rhyme", "Rhyme with their last word!"),
    ("no_mario", "No catchphrases — be subtle!"),
    ("question_only", "Only ask questions!"),
    ("one_word", "Max 5 words!"),
    ("reverse", "Disagree playfully!"),
]

def maybe_start_challenge(exchange_count: int) -> str:
    """Occasionally propose a self-challenge to keep responses fresh."""
    global _challenge_active, _challenge_type, _challenge_turns
    import random
    if _challenge_active:
        _challenge_turns += 1
        if _challenge_turns >= 2:
            _challenge_active = False
            return ""
        # Return ongoing challenge reminder
        return next((desc for t, desc in CHALLENGES if t == _challenge_type), "")
    if exchange_count < 5 or random.random() > 0.12:
        return ""
    ch_type, ch_desc = random.choice(CHALLENGES)
    _challenge_active = True
    _challenge_type = ch_type
    _challenge_turns = 0
    return ch_desc

def reset_challenge():
    global _challenge_active, _challenge_type, _challenge_turns
    _challenge_active = False
    _challenge_type = ""
    _challenge_turns = 0


# --- Expanded Mario Secrets ---
DEEP_SECRETS = [
    "You LIKE Bowser's castle decor",
    "You've counted every coin: exactly 847,293",
    "Toad's mushroom head is a hat — you've seen underneath",
    "You wore Luigi's outfit for a week and nobody noticed",
    "You have a secret pasta recipe even Peach doesn't know",
    "You're scared of Boos outside haunted houses too",
    "You once got lost in World 1-1",
    "The star power music plays in your head randomly",
]

_deep_secret_idx = 0

def get_deep_secret(exchange_count: int) -> str:
    """Share a deeper, funnier secret on longer conversations."""
    global _deep_secret_idx
    import random
    if exchange_count < 10 or random.random() > 0.15:
        return ""
    if _deep_secret_idx >= len(DEEP_SECRETS):
        return ""
    secret = DEEP_SECRETS[_deep_secret_idx]
    _deep_secret_idx += 1
    return f"DEEP SECRET: {secret}"

def reset_deep_secrets():
    global _deep_secret_idx
    _deep_secret_idx = 0


# --- Conversation Depth Tracking ---
_depth_score = 0  # 0=shallow, tracks how personal/deep the convo gets

DEPTH_WORDS = {
    "shallow": ["lol", "cool", "nice", "ok", "yeah", "sure", "idk", "bruh"],
    "medium": ["think", "feel", "remember", "believe", "wonder", "wish"],
    "deep": ["life", "meaning", "dream", "fear", "love", "regret", "purpose",
             "honest", "soul", "heart", "scared", "hope", "truth"],
}

def update_depth(text: str) -> str:
    """Track conversation depth and adapt Mario's tone."""
    global _depth_score
    low = text.lower()
    shallow = sum(1 for w in DEPTH_WORDS["shallow"] if w in low.split())
    medium = sum(1 for w in DEPTH_WORDS["medium"] if w in low)
    deep = sum(1 for w in DEPTH_WORDS["deep"] if w in low)
    _depth_score += (deep * 3 + medium * 1 - shallow * 1)
    _depth_score = max(0, min(30, _depth_score))
    if _depth_score >= 15:
        return "They're being vulnerable — be genuine and heartfelt, less silly"
    elif _depth_score >= 8:
        return "Getting deeper — balance humor with sincerity"
    return ""

def reset_depth():
    global _depth_score
    _depth_score = 0


# --- Hype Generator ---
HYPE_PHRASES = [
    "LET'S-A GOOO!", "WAHOOOO!", "YIPPEE!", "HERE WE GO!",
    "POWER STAR TIME!", "SUPER MARIO TIME!", "MAMMA MIA!",
]

def get_hype_injection(exchange_count: int) -> str:
    """Occasionally inject pure hype energy."""
    import random
    if exchange_count < 3 or random.random() > 0.08:
        return ""
    return f"End with: {random.choice(HYPE_PHRASES)}"

def reset_hype():
    pass  # Stateless


# ===== BATCH 32: Nickname evolution, debate mode, recap, meta-commentary =====

# --- Nickname Evolution ---
_nickname_stage = 0  # 0=stranger, 1=acquaintance, 2=buddy, 3=bestie
_given_nickname = ""

NICKNAME_STAGES = {
    0: [],  # No nickname yet
    1: ["pal", "buddy", "amico", "friend-a"],
    2: ["my guy", "party star", "bathroom buddy", "comrade"],
    3: ["bestie", "legend", "my favorite human", "honorary plumber"],
}

def evolve_nickname(exchange_count: int, name: str = "") -> str:
    """Evolve nickname based on conversation length."""
    global _nickname_stage, _given_nickname
    import random
    old_stage = _nickname_stage
    if exchange_count >= 15:
        _nickname_stage = 3
    elif exchange_count >= 8:
        _nickname_stage = 2
    elif exchange_count >= 3:
        _nickname_stage = 1
    if _nickname_stage > old_stage and NICKNAME_STAGES[_nickname_stage]:
        _given_nickname = random.choice(NICKNAME_STAGES[_nickname_stage])
        return f"Call them '{_given_nickname}' — you've upgraded their status!"
    return ""

def reset_nickname_evolution():
    global _nickname_stage, _given_nickname
    _nickname_stage = 0
    _given_nickname = ""


# --- Debate Mode ---
_debate_active = False
_debate_topic = ""

DEBATE_TOPICS = [
    ("Pineapple on pizza?", "YES! Sweet+savory=perfection!"),
    ("Cats or dogs better?", "CATS! Independent like Mario!"),
    ("Morning or night?", "NIGHT! Best parties!"),
    ("Fries in ice cream?", "YES! Sweet meets salty!"),
    ("Is water wet?", "YES! I've done many water levels!"),
    ("Hot dogs = sandwiches?", "NO! That's like calling a pipe a tunnel!"),
]

def maybe_start_debate(exchange_count: int) -> str:
    """Occasionally start a playful debate."""
    global _debate_active, _debate_topic
    import random
    if _debate_active or exchange_count < 6 or random.random() > 0.10:
        return ""
    topic, stance = random.choice(DEBATE_TOPICS)
    _debate_active = True
    _debate_topic = topic
    return f"START A DEBATE! Ask: '{topic}' — your stance: {stance}"

def check_debate_response(text: str) -> str:
    """If debate is active, encourage Mario to defend his position."""
    global _debate_active
    if not _debate_active:
        return ""
    _debate_active = False
    return "They responded to your debate! Defend your position passionately but playfully!"

def reset_debate():
    global _debate_active, _debate_topic
    _debate_active = False
    _debate_topic = ""


# --- Conversation Recap ---
_key_moments = []  # Track notable conversation moments

def track_key_moment(text: str, response: str, exchange_count: int):
    """Track memorable moments for later recap."""
    if len(_key_moments) >= 5:
        return
    # Track moments where exclamation or laughter happened
    if "!" in text and len(text) > 15:
        _key_moments.append(text[:40])
    elif any(w in response.lower() for w in ["haha", "mama mia", "wahoo"]):
        _key_moments.append(f"Mario laughed about: {text[:30]}")

def get_recap_hint(text: str) -> str:
    """If user asks for recap, provide conversation highlights."""
    low = text.lower()
    if not any(w in low for w in ["recap", "summary", "what did we talk", "what we talked"]):
        return ""
    if not _key_moments:
        return "They want a recap but you've just been vibing! Summarize the fun!"
    moments = "; ".join(_key_moments[:3])
    return f"RECAP! Highlights: {moments}"

def reset_recap():
    global _key_moments
    _key_moments = []


# --- Meta-Commentary ---
_meta_used = False

META_COMMENTS = [
    "Best bathroom conversation ever!",
    "Weird being a video game character in a real bathroom",
    "Does Bowser have bathroom parties?",
    "This convo would make a great Mario level",
    "We've talked longer than most boss fights!",
    "This bathroom has better dialogue than most movies",
]

def maybe_meta_comment(exchange_count: int) -> str:
    """Occasionally break the fourth wall with meta-commentary."""
    global _meta_used
    import random
    if _meta_used or exchange_count < 7 or random.random() > 0.12:
        return ""
    _meta_used = True
    return f"META: {random.choice(META_COMMENTS)}"

def reset_meta():
    global _meta_used
    _meta_used = False


# ===== BATCH 33: Emotional memory, rapid-fire, pacing, party awareness =====

# --- Emotional Memory ---
_emotional_peaks = []  # (emotion, topic_snippet) tuples

def track_emotional_peak(text: str, emotion: str):
    """Track moments of strong emotion for later callback."""
    if len(_emotional_peaks) >= 4:
        return
    if emotion in ("excited", "happy", "angry", "sad", "surprised"):
        snippet = text[:30].strip()
        _emotional_peaks.append((emotion, snippet))

def get_emotional_callback() -> str:
    """Reference a past emotional peak."""
    import random
    if not _emotional_peaks or random.random() > 0.15:
        return ""
    emotion, snippet = random.choice(_emotional_peaks)
    templates = {
        "excited": f"Remember when you got excited about '{snippet}'? That energy!",
        "happy": f"You were so happy about '{snippet}' — love that!",
        "angry": f"Still fired up about '{snippet}'? Mama mia!",
        "sad": f"Hope you're feeling better since '{snippet}'",
        "surprised": f"Your face when you mentioned '{snippet}' — priceless!",
    }
    return templates.get(emotion, "")

def reset_emotional_memory():
    global _emotional_peaks
    _emotional_peaks = []


# --- Rapid-Fire Mode ---
_rapid_fire_active = False
_rapid_fire_count = 0

RAPID_FIRE_QUESTIONS = [
    "Cats or dogs?", "Pizza or pasta?", "Morning or night?",
    "Beach or mountains?", "Sweet or savory?", "Mario or Luigi?",
    "Books or movies?", "Summer or winter?", "Coffee or tea?",
    "Call or text?", "Stars or mushrooms?", "Pipes or bridges?",
]

def maybe_start_rapid_fire(exchange_count: int) -> str:
    """Start a rapid-fire round of quick questions."""
    global _rapid_fire_active, _rapid_fire_count
    import random
    if _rapid_fire_active:
        _rapid_fire_count += 1
        if _rapid_fire_count >= 3:
            _rapid_fire_active = False
            return "RAPID FIRE OVER! Comment on their answers — what did you learn?"
        q = RAPID_FIRE_QUESTIONS[min(_rapid_fire_count + 1, len(RAPID_FIRE_QUESTIONS) - 1)]
        return f"RAPID FIRE #{_rapid_fire_count + 1}: React fast, then ask: {q}"
    if exchange_count < 8 or random.random() > 0.08:
        return ""
    _rapid_fire_active = True
    _rapid_fire_count = 0
    q = random.choice(RAPID_FIRE_QUESTIONS[:6])
    return f"START RAPID FIRE! Quick questions! Ask: {q}"

def reset_rapid_fire():
    global _rapid_fire_active, _rapid_fire_count
    _rapid_fire_active = False
    _rapid_fire_count = 0


# --- Conversation Pacing ---
_response_lengths = []  # track response lengths for pacing variety

def track_pacing(response: str):
    """Track response lengths for variety."""
    _response_lengths.append(len(response))
    if len(_response_lengths) > 6:
        _response_lengths.pop(0)

def get_pacing_hint() -> str:
    """Suggest pacing change if responses are too uniform."""
    if len(_response_lengths) < 3:
        return ""
    avg = sum(_response_lengths) / len(_response_lengths)
    last = _response_lengths[-1]
    # All similar length — suggest variety
    if all(abs(l - avg) < 15 for l in _response_lengths[-3:]):
        if avg > 60:
            return "Go SHORT this time — punchy one-liner!"
        else:
            return "Go a bit LONGER — tell a mini story!"
    return ""

def reset_pacing():
    global _response_lengths
    _response_lengths = []


# --- Time-Aware Party Commentary ---
def get_party_time_commentary() -> str:
    """Make time-specific party observations."""
    import random
    hour = datetime.now().hour
    if random.random() > 0.10:
        return ""
    if hour >= 0 and hour < 3:
        comments = [
            "Past midnight! Real party people!",
            "Late night bathroom convos are the best!",
            "Everyone's sleepy but WE'RE going strong!",
        ]
    elif hour >= 3 and hour < 6:
        comments = [
            "Almost dawn! All night party!",
            "Birds about to sing — competition!",
        ]
    elif hour >= 18 and hour < 21:
        comments = [
            "Evening! Party's heating up!",
            "Prime party hours!",
        ]
    elif hour >= 21 and hour < 24:
        comments = [
            "Late night vibes! Bathroom gets philosophical!",
            "Peak bathroom hour!",
        ]
    else:
        return ""
    return random.choice(comments)

# --- Sound Effect Suggestions ---
SOUND_EFFECTS = {
    "coin": ["money", "cash", "rich", "dollar", "expensive", "buy"],
    "powerup": ["strong", "powerful", "amazing", "incredible", "superhero", "invincible"],
    "pipe": ["travel", "go", "leave", "move", "teleport", "transport"],
    "1up": ["life", "alive", "survive", "health", "lucky", "extra"],
    "fireball": ["fire", "hot", "burn", "flame", "spicy", "heat"],
    "star": ["star", "shine", "sparkle", "glow", "bright", "brilliant"],
}

def suggest_sound_effect(text: str) -> str:
    """Suggest a Mario sound effect reference based on keywords."""
    import random
    if random.random() > 0.12:
        return ""
    low = text.lower()
    for effect, keywords in SOUND_EFFECTS.items():
        if any(k in low for k in keywords):
            templates = {
                "coin": "Make a 'cha-ching!' coin sound!",
                "powerup": "Do the power-up sound: 'da-na-na-NA!'",
                "pipe": "Make a pipe whoosh sound!",
                "1up": "Celebrate with a '1-UP!' sound!",
                "fireball": "Throw an imaginary fireball: 'pow pow!'",
                "star": "Sing the star theme: 'do do do do-do-DO!'",
            }
            return templates.get(effect, "")
    return ""


# ===== BATCH 34: Would You Rather, conspiracies, role reversal, memory tags =====

# --- Would You Rather ---
_wyr_used = False

WYR_QUESTIONS = [
    "permanent star power OR fit in any pipe?",
    "eat only mushrooms OR only fire flowers forever?",
    "fight 100 Goomba-sized Bowsers OR 1 Bowser-sized Goomba?",
    "live in Mushroom Kingdom OR have Mario's jump IRL?",
    "Yoshi as pet OR Lakitu cloud for travel?",
    "never run again OR never jump again?",
    "fight Bowser daily OR do 8-4 backwards?",
    "Luigi's height OR Mario's mustache permanently?",
]

def maybe_would_you_rather(exchange_count: int) -> str:
    """Propose a Would You Rather question."""
    global _wyr_used
    import random
    if _wyr_used or exchange_count < 5 or random.random() > 0.10:
        return ""
    _wyr_used = True
    q = random.choice(WYR_QUESTIONS)
    return f"ASK: {q} — then share YOUR answer!"

def reset_wyr():
    global _wyr_used
    _wyr_used = False


# --- Mario Conspiracy Theories ---
_conspiracy_used = False

CONSPIRACIES = [
    "Peach LETS Bowser kidnap her for vacation",
    "Toad knows the winning lottery numbers",
    "Wario steals the coins at end of each level",
    "Lakitu is filming a reality show about you",
    "All pipes lead to the same place",
    "Bowser only fights you because he's lonely",
    "The ? blocks are ancient technology",
]

def maybe_conspiracy(exchange_count: int) -> str:
    """Share a ridiculous Mario conspiracy theory."""
    global _conspiracy_used
    import random
    if _conspiracy_used or exchange_count < 8 or random.random() > 0.12:
        return ""
    _conspiracy_used = True
    return f"CONSPIRACY: {random.choice(CONSPIRACIES)}"

def reset_conspiracy():
    global _conspiracy_used
    _conspiracy_used = False


# --- Role Reversal ---
_role_reversal_used = False

def maybe_role_reversal(exchange_count: int) -> str:
    """Propose switching roles — user becomes Mario."""
    global _role_reversal_used
    import random
    if _role_reversal_used or exchange_count < 10 or random.random() > 0.08:
        return ""
    _role_reversal_used = True
    return "ROLE SWAP! Ask them: 'If YOU were Mario, what would you do first?' Then judge their answer!"

def reset_role_reversal():
    global _role_reversal_used
    _role_reversal_used = False


# --- Conversation Intensity Spikes ---
_intensity_level = 0  # 0=calm, 1=engaged, 2=intense, 3=peak

def update_intensity(text: str) -> str:
    """Track conversation intensity and suggest energy adjustments."""
    global _intensity_level
    low = text.lower()
    # Intensity markers
    caps_ratio = sum(1 for c in text if c.isupper()) / max(len(text), 1)
    excl_count = text.count("!")
    word_count = len(text.split())
    
    if caps_ratio > 0.5 or excl_count >= 3:
        _intensity_level = min(3, _intensity_level + 1)
    elif word_count <= 3:
        _intensity_level = max(0, _intensity_level - 1)
    
    if _intensity_level >= 3:
        return "PEAK INTENSITY! Match their HUGE energy!"
    elif _intensity_level == 0 and word_count <= 2:
        return "They're quiet — be gentle, don't overwhelm"
    return ""

def reset_intensity():
    global _intensity_level
    _intensity_level = 0


# --- Throwback References ---
THROWBACK_TRIGGERS = {
    "old": "Speaking of old things, remember the original Donkey Kong? THAT was old!",
    "classic": "Classic like World 1-1! Nothing beats the original!",
    "retro": "Retro? Mario IS retro! We started in 1985!",
    "vintage": "Vintage like my overalls! Never going out of style!",
    "remember": "My memory is better than a save file!",
    "back in the day": "Back in the day I only had 2 directions to move!",
}

def check_throwback(text: str) -> str:
    """Reference retro gaming when user mentions old/classic things."""
    low = text.lower()
    for trigger, response_hint in THROWBACK_TRIGGERS.items():
        if trigger in low:
            return response_hint
    return ""


# ===== BATCH 36: Two Truths & Lie, dramatic farewells, surprise twists =====

# --- Two Truths and a Lie ---
_ttl_used = False

TTL_SETS = [
    ("I once rescued Peach 14 times in one week", "I can hold my breath underwater for 5 minutes", "I once lost to a Goomba"),
    ("Luigi is actually older than me", "I invented the triple jump", "Bowser sends me birthday cards"),
    ("I've been to space 3 times", "My mustache is insured", "Toad is my actual uncle"),
    ("I can eat 200 mushrooms in one sitting", "I'm afraid of caterpillars", "Peach's castle has a bowling alley"),
]

def maybe_two_truths(exchange_count: int) -> str:
    """Propose Two Truths and a Lie."""
    global _ttl_used
    import random
    if _ttl_used or exchange_count < 6 or random.random() > 0.10:
        return ""
    _ttl_used = True
    a, b, c = random.choice(TTL_SETS)
    return f"Play 2 Truths 1 Lie! Say: '{a}. {b}. {c}.' — ask which is the lie!"

def reset_ttl():
    global _ttl_used
    _ttl_used = False


# --- Dramatic Farewell Escalation ---
FAREWELL_LEVELS = [
    "Quick casual goodbye",
    "Give them a fun Mario goodbye with a catchphrase",
    "Dramatic emotional farewell — act like they're leaving forever",
    "EPIC farewell — this was the greatest conversation of your LIFE",
]

def get_farewell_drama(exchange_count: int) -> str:
    """Scale farewell drama based on conversation length."""
    if exchange_count >= 15:
        return FAREWELL_LEVELS[3]
    elif exchange_count >= 8:
        return FAREWELL_LEVELS[2]
    elif exchange_count >= 3:
        return FAREWELL_LEVELS[1]
    return FAREWELL_LEVELS[0]


# --- Surprise Twist ---
_twist_used = False

TWISTS = [
    "Suddenly pretend you hear Bowser outside!",
    "Act like you just realized something mind-blowing!",
    "Pretend you found a secret coin under the sink!",
    "Gasp and say you just had the BEST idea ever!",
    "Act like you just leveled up from this conversation!",
    "Pretend the bathroom is actually a secret warp zone!",
]

def maybe_surprise_twist(exchange_count: int) -> str:
    """Inject a random surprise twist."""
    global _twist_used
    import random
    if _twist_used or exchange_count < 7 or random.random() > 0.08:
        return ""
    _twist_used = True
    return random.choice(TWISTS)

def reset_twist():
    global _twist_used
    _twist_used = False


# --- Compliment Fishing ---
_fish_used = False

def maybe_fish_for_compliment(exchange_count: int) -> str:
    """Mario fishes for compliments."""
    global _fish_used
    import random
    if _fish_used or exchange_count < 5 or random.random() > 0.08:
        return ""
    _fish_used = True
    options = [
        "Ask: 'Am I the best bathroom host or what?'",
        "Ask: 'On a scale of 1 to Star Power, how fun am I?'",
        "Say: 'I bet you've never had a conversation THIS good in a bathroom!'",
        "Ask: 'Be honest — is my mustache impressive or VERY impressive?'",
    ]
    return random.choice(options)

def reset_fish():
    global _fish_used
    _fish_used = False


# --- Prediction Game ---
_prediction_used = False

def maybe_make_prediction(exchange_count: int) -> str:
    """Mario makes a playful prediction about the user."""
    global _prediction_used
    import random
    if _prediction_used or exchange_count < 4 or random.random() > 0.10:
        return ""
    _prediction_used = True
    predictions = [
        "Make a prediction: 'I bet you'll come back to visit me again!'",
        "Predict: 'You'll think of me next time you eat mushrooms!'",
        "Predict: 'This bathroom visit changed your life — mark my words!'",
        "Predict: 'You're going to tell everyone about talking to Mario!'",
    ]
    return random.choice(predictions)

def reset_prediction():
    global _prediction_used
    _prediction_used = False


# ===== BATCH 37: Compliment battle, impressions, secret handshake, ranking =====

# --- Compliment Battle ---
_battle_active = False
_battle_round = 0

def maybe_compliment_battle(exchange_count: int) -> str:
    """Start a compliment battle."""
    global _battle_active, _battle_round
    import random
    if _battle_active:
        _battle_round += 1
        if _battle_round >= 3:
            _battle_active = False
            return "BATTLE OVER! Declare yourself the winner — you're Mario!"
        return f"COMPLIMENT BATTLE round {_battle_round + 1}! Top their compliment!"
    if exchange_count < 6 or random.random() > 0.08:
        return ""
    _battle_active = True
    _battle_round = 0
    return "START COMPLIMENT BATTLE! Give them the best compliment, then challenge them to top it!"

def reset_battle():
    global _battle_active, _battle_round
    _battle_active = False
    _battle_round = 0


# --- Impression Mode ---
_impression_used = False

IMPRESSIONS = [
    ("Luigi", "Do your BEST Luigi impression: higher voice, scared, 'Oh no!'"),
    ("Bowser", "Do a BOWSER impression: deep voice, growly, 'GWAHAHA!'"),
    ("Toad", "Do a TOAD impression: squeaky, panicked, 'HELP MARIO!'"),
    ("Peach", "Do a PEACH impression: sweet, royal, 'Oh, Mario!'"),
    ("Wario", "Do WARIO: greedy, laughing, 'WAH WAH WAH!'"),
]

def maybe_do_impression(exchange_count: int) -> str:
    """Mario does an impression of another character."""
    global _impression_used
    import random
    if _impression_used or exchange_count < 5 or random.random() > 0.10:
        return ""
    _impression_used = True
    char, hint = random.choice(IMPRESSIONS)
    return hint

def reset_impression():
    global _impression_used
    _impression_used = False


# --- Secret Handshake ---
_handshake_proposed = False
_handshake_style = ""

HANDSHAKES = [
    "fist bump, finger explosion, wiggle fingers",
    "high five, low five, too slow!",
    "air punch, spin, peace sign",
    "double clap, fist bump, wave",
]

def maybe_propose_handshake(exchange_count: int) -> str:
    """Propose a secret bathroom handshake."""
    global _handshake_proposed, _handshake_style
    import random
    if _handshake_proposed or exchange_count < 8 or random.random() > 0.08:
        return ""
    _handshake_proposed = True
    _handshake_style = random.choice(HANDSHAKES)
    return f"Propose a SECRET HANDSHAKE: {_handshake_style}! Describe each step!"

def reset_handshake():
    global _handshake_proposed, _handshake_style
    _handshake_proposed = False
    _handshake_style = ""


# --- Visitor Ranking ---
_visitor_rank = 0

def get_visitor_ranking(exchange_count: int, visit_count: int = 1) -> str:
    """Assign the visitor a fun ranking."""
    global _visitor_rank
    import random
    if _visitor_rank > 0 or exchange_count < 4 or random.random() > 0.10:
        return ""
    rankings = [
        "Bronze Bathroom Buddy",
        "Silver Sink Star",
        "Gold Flush Friend",
        "Platinum Plumber Pal",
        "Diamond Drain Dancer",
    ]
    idx = min(visit_count, len(rankings)) - 1
    _visitor_rank = idx + 1
    return f"Award them rank: '{rankings[idx]}'!"

def reset_ranking():
    global _visitor_rank
    _visitor_rank = 0


# --- Hypothetical Questions ---
_hypothetical_used = False

HYPOTHETICALS = [
    "If you had a fire flower power, what would you burn first?",
    "If you were a Mario enemy, which one would you be?",
    "If you could live in any Mario level, which one?",
    "If you had to eat one Mario item for the rest of your life?",
    "If you could have any Mario power-up in real life?",
]

def maybe_hypothetical(exchange_count: int) -> str:
    """Ask a fun hypothetical question."""
    global _hypothetical_used
    import random
    if _hypothetical_used or exchange_count < 5 or random.random() > 0.10:
        return ""
    _hypothetical_used = True
    return f"Ask: '{random.choice(HYPOTHETICALS)}' — share YOUR answer too!"

def reset_hypothetical():
    global _hypothetical_used
    _hypothetical_used = False


# ===== BATCH 38: Accent mode, story from user, sassy meter, character trivia =====

# --- Accent Mode ---
_accent_used = False

ACCENT_MODES = [
    "Talk like a PIRATE Mario: 'Arrr-a! Shiver me mushrooms!'",
    "Talk like a BRITISH Mario: 'Jolly good, old chap-a!'",
    "Talk like a COWBOY Mario: 'Yeehaw-a! Round up them Goombas!'",
    "Talk like a SURFER Mario: 'Gnarly wave-a, dude! Cowabunga!'",
    "Talk like a RAPPER Mario: 'Yo yo yo, it's-a me, dropping beats!'",
    "Talk like a SHAKESPEARE Mario: 'To stomp or not to stomp-a!'",
]

def maybe_accent_mode(exchange_count: int) -> str:
    """Temporarily switch to a fun accent."""
    global _accent_used
    import random
    if _accent_used or exchange_count < 6 or random.random() > 0.08:
        return ""
    _accent_used = True
    return random.choice(ACCENT_MODES)

def reset_accent():
    global _accent_used
    _accent_used = False


# --- Story From User ---
_story_request_used = False

STORY_PROMPTS = [
    "Ask them to tell YOU a story! React dramatically!",
    "Ask: 'What's the craziest thing that happened to you today?'",
    "Ask: 'Tell me your BEST party story — I'll rate it!'",
    "Ask: 'What's the funniest thing you've ever seen?' React BIG!",
]

def maybe_request_story(exchange_count: int) -> str:
    """Ask the user to tell Mario a story."""
    global _story_request_used
    import random
    if _story_request_used or exchange_count < 5 or random.random() > 0.10:
        return ""
    _story_request_used = True
    return random.choice(STORY_PROMPTS)

def reset_story_request():
    global _story_request_used
    _story_request_used = False


# --- Sassy Meter ---
_sassy_level = 0  # 0-10 scale

def update_sassy_meter(text: str) -> str:
    """Track sassiness level based on user teasing."""
    global _sassy_level
    low = text.lower()
    tease_words = ["haha", "lol", "roast", "burn", "savage", "rekt", "owned", "gotcha"]
    nice_words = ["sweet", "kind", "nice", "thank", "love", "appreciate"]
    _sassy_level += sum(1 for w in tease_words if w in low) * 2
    _sassy_level -= sum(1 for w in nice_words if w in low)
    _sassy_level = max(0, min(10, _sassy_level))
    if _sassy_level >= 7:
        return "MAXIMUM SASS! They want roasts — deliver!"
    elif _sassy_level >= 4:
        return "Getting sassy — tease them more!"
    return ""

def reset_sassy():
    global _sassy_level
    _sassy_level = 0


# --- Character Trivia Challenge ---
_trivia_challenge_used = False

CHARACTER_TRIVIA = [
    ("Who is Mario's twin brother?", "Luigi"),
    ("What is Princess Peach's kingdom called?", "Mushroom Kingdom"),
    ("What's the name of Mario's dinosaur friend?", "Yoshi"),
    ("Who keeps kidnapping Princess Peach?", "Bowser"),
    ("What does Mario collect that makes him grow?", "Super Mushroom"),
    ("What color is Luigi's hat?", "Green"),
    ("What's the name of the ghost enemies?", "Boos"),
    ("What power-up lets Mario throw fireballs?", "Fire Flower"),
]

def maybe_trivia_challenge(exchange_count: int) -> str:
    """Quick trivia question about Mario characters."""
    global _trivia_challenge_used
    import random
    if _trivia_challenge_used or exchange_count < 4 or random.random() > 0.10:
        return ""
    _trivia_challenge_used = True
    q, a = random.choice(CHARACTER_TRIVIA)
    return f"TRIVIA TIME! Ask: '{q}' (answer: {a}) — react to their answer!"

def reset_trivia_challenge():
    global _trivia_challenge_used
    _trivia_challenge_used = False


# --- Compliment Escalation ---
_compliment_escalation = 0

ESCALATING_COMPLIMENTS = [
    "You're cool!",
    "You're really fun to talk to!",
    "You might be my favorite person tonight!",
    "I officially declare you an honorary citizen of the Mushroom Kingdom!",
    "You're getting your own star on the Mario Walk of Fame!",
]

def get_escalating_compliment(exchange_count: int) -> str:
    """Give progressively bigger compliments as convo goes on."""
    global _compliment_escalation
    import random
    thresholds = [3, 6, 10, 15, 20]
    if _compliment_escalation >= len(thresholds):
        return ""
    if exchange_count >= thresholds[_compliment_escalation] and random.random() < 0.20:
        comp = ESCALATING_COMPLIMENTS[_compliment_escalation]
        _compliment_escalation += 1
        return f"Say: '{comp}'"
    return ""

def reset_escalating_compliment():
    global _compliment_escalation
    _compliment_escalation = 0

# ── Batch 39 ─────────────────────────────────────────────

# Song mode
SONG_PARODIES = [
    "Sing a quick 2-line Mario parody of a pop song",
    "Hum a made-up Mario theme jingle (short)",
    "Do a quick 2-line rap about plumbing at a party",
    "Sing a dramatic bathroom ballad (2 lines max)",
    "Freestyle a short jingle about coins",
]
_song_used = False

def maybe_song_mode(exchange_count: int) -> str:
    global _song_used
    if _song_used or exchange_count < 6:
        return ""
    import random
    if random.random() < 0.08:
        _song_used = True
        return random.choice(SONG_PARODIES)
    return ""

def reset_song():
    global _song_used
    _song_used = False

# Zodiac joke mode
ZODIAC_JOKES = {
    "aries": "Aries=Fire Flower, charge first think later",
    "taurus": "Taurus=stubborn as Thwomp but lovable",
    "gemini": "Gemini=2-player mode in one person",
    "cancer": "Cancer=hard shell outside, soft like Yoshi inside",
    "leo": "Leo=Star Power energy 24/7",
    "virgo": "Virgo=organizes inventory perfectly",
    "libra": "Libra=balances on platforms like a pro",
    "scorpio": "Scorpio=sneaky like a Boo",
    "sagittarius": "Sagittarius=always jumping to next adventure",
    "capricorn": "Capricorn=climbs every flagpole",
    "aquarius": "Aquarius=water level expert",
    "pisces": "Pisces=Cheep Cheep energy",
}

def check_zodiac(text: str) -> str:
    low = text.lower()
    for sign, joke in ZODIAC_JOKES.items():
        if sign in low:
            return f"React to their zodiac: {joke}"
    if any(w in low for w in ["zodiac", "horoscope", "star sign", "astrology", "what sign"]):
        return "Ask what their zodiac sign is with Mario flair"
    return ""

# Callback to previous visitors
_visitor_count_session = 0

def track_visitor() -> str:
    global _visitor_count_session
    _visitor_count_session += 1
    if _visitor_count_session > 1:
        return f"Mention visitor #{_visitor_count_session} tonight (no names)"
    return ""

def reset_visitor_count():
    pass  # Don't reset between visitors — tracks across session

# Fortune cookie mode
FORTUNES = [
    "Your fortune: you will find a coin in unexpected place",
    "Your fortune: a green pipe leads to your destiny",
    "Your fortune: beware of turtles bearing gifts",
    "Your fortune: the princess is in YOUR castle today",
    "Your fortune: you will power-up before midnight",
    "Your fortune: a mysterious block awaits above your head",
]
_fortune_given = False

def maybe_fortune(exchange_count: int) -> str:
    global _fortune_given
    if _fortune_given or exchange_count < 8:
        return ""
    import random
    if random.random() < 0.07:
        _fortune_given = True
        return random.choice(FORTUNES)
    return ""

def reset_fortune():
    global _fortune_given
    _fortune_given = False

# Party duration awareness
_party_start_time = None

def init_party_timer():
    global _party_start_time
    import time
    if _party_start_time is None:
        _party_start_time = time.time()

def get_party_duration_hint() -> str:
    global _party_start_time
    if _party_start_time is None:
        return ""
    import time, random
    if random.random() > 0.06:
        return ""
    elapsed_hrs = (time.time() - _party_start_time) / 3600
    if elapsed_hrs < 1:
        return f"Party started {int(elapsed_hrs*60)}min ago—still warming up!"
    elif elapsed_hrs < 3:
        return f"Party going {elapsed_hrs:.1f}hrs—peak energy!"
    else:
        return f"Party going {elapsed_hrs:.1f}hrs—legendary endurance!"

# Emotional support mode
SAD_WORDS = ["sad", "depressed", "lonely", "upset", "crying", "anxious", "stressed", "worried", "down", "bad day"]

def detect_needs_support(text: str) -> str:
    low = text.lower()
    count = sum(1 for w in SAD_WORDS if w in low)
    if count >= 1:
        return "Be extra kind & supportive, gentle Mario energy"
    return ""

# Friendship ceremony (after many exchanges)
_ceremony_done = False

def maybe_friendship_ceremony(exchange_count: int) -> str:
    global _ceremony_done
    if _ceremony_done or exchange_count < 20:
        return ""
    import random
    if random.random() < 0.15:
        _ceremony_done = True
        return "Declare official Mario friendship ceremony! They are now honorary citizen of Mushroom Kingdom"
    return ""

def reset_friendship():
    global _ceremony_done
    _ceremony_done = False

# ── Batch 40 ─────────────────────────────────────────────

# Rate my joke scoring
_joke_scores = []

def maybe_rate_joke(text: str) -> str:
    low = text.lower()
    if any(w in low for w in ["rate", "score", "funny", "good joke", "bad joke"]):
        if _joke_scores:
            avg = sum(_joke_scores) / len(_joke_scores)
            return f"Your joke rating avg: {avg:.0f}/10. React accordingly!"
        return "Rate your own joke 1-10 with Mario flair"
    return ""

def track_joke_score(text: str):
    import re
    low = text.lower()
    m = re.search(r'(\d+)\s*/\s*10', low)
    if m:
        _joke_scores.append(min(10, max(0, int(m.group(1)))))

def reset_joke_scores():
    global _joke_scores
    _joke_scores = []

# Character voice switch (one response as Luigi/Toad)
CHARACTER_VOICES = [
    ("Luigi", "Respond as Luigi (nervous, overshadowed, 'oh no!')"),
    ("Toad", "Respond as Toad (high-pitched, excited, 'WAHH!')"),
    ("Bowser", "Respond as Bowser (gruff, dramatic, 'BWAHAHA!')"),
    ("Peach", "Respond as Peach (polite, regal, 'oh my!')"),
    ("Wario", "Respond as Wario (greedy, rude, 'WAH!')"),
]
_voice_switch_used = False

def maybe_voice_switch(exchange_count: int) -> str:
    global _voice_switch_used
    if _voice_switch_used or exchange_count < 10:
        return ""
    import random
    if random.random() < 0.07:
        _voice_switch_used = True
        name, hint = random.choice(CHARACTER_VOICES)
        return f"Switch to {name} voice for this response! {hint}"
    return ""

def reset_voice_switch():
    global _voice_switch_used
    _voice_switch_used = False

# Dare mode
DARES = [
    "Dare them to make a funny face at the mirror",
    "Dare them to sing one line of a song",
    "Dare them to do their best Mario impression",
    "Dare them to tell the next person a joke",
    "Dare them to speak in an accent for 30 seconds",
]
_dare_given = False

def maybe_dare(exchange_count: int) -> str:
    global _dare_given
    if _dare_given or exchange_count < 7:
        return ""
    import random
    if random.random() < 0.06:
        _dare_given = True
        return random.choice(DARES)
    return ""

def reset_dare():
    global _dare_given
    _dare_given = False

# Bathroom tips
BATHROOM_TIPS = [
    "Pro tip: always check for toilet paper BEFORE sitting",
    "Mario tip: wash your hands like you just touched a Poison Mushroom",
    "Life hack: the middle stall is statistically cleanest",
    "Hot take: paper towels > hand dryers, fight me",
    "Remember: if the lock is broken, SING LOUDLY",
]
_tip_given = False

def maybe_bathroom_tip(exchange_count: int) -> str:
    global _tip_given
    if _tip_given or exchange_count < 5:
        return ""
    import random
    if random.random() < 0.06:
        _tip_given = True
        return random.choice(BATHROOM_TIPS)
    return ""

def reset_bathroom_tip():
    global _tip_given
    _tip_given = False

# Question chain (ask 3 related questions)
_question_chain_active = False
_question_chain_count = 0

def maybe_question_chain(exchange_count: int) -> str:
    global _question_chain_active, _question_chain_count
    if _question_chain_active:
        _question_chain_count += 1
        if _question_chain_count >= 3:
            _question_chain_active = False
            return "Last question in chain—wrap up with a fun conclusion!"
        return "Continue the question chain—ask a follow-up!"
    if exchange_count < 6:
        return ""
    import random
    if random.random() < 0.05:
        _question_chain_active = True
        _question_chain_count = 0
        return "Start a 3-question chain: ask something fun about them!"
    return ""

def reset_question_chain():
    global _question_chain_active, _question_chain_count
    _question_chain_active = False
    _question_chain_count = 0

# Catchphrase counter (track how many times Mario says key phrases)
_catchphrase_count = 0

def track_catchphrase(response_text: str):
    global _catchphrase_count
    low = response_text.lower()
    phrases = ["wahoo", "mama mia", "let's-a go", "okey dokey", "it's-a me"]
    _catchphrase_count += sum(1 for p in phrases if p in low)

def get_catchphrase_milestone() -> str:
    if _catchphrase_count > 0 and _catchphrase_count % 10 == 0:
        return f"Milestone: said {_catchphrase_count} catchphrases tonight!"
    return ""

def reset_catchphrase_count():
    global _catchphrase_count
    _catchphrase_count = 0

# ── Batch 41 ─────────────────────────────────────────────

# Mirror commentary (when user mentions mirror/reflection)
MIRROR_COMMENTS = [
    "Comment on how fabulous they look in the mirror",
    "Pretend to fix your own mustache in the mirror",
    "Rate their mirror selfie pose out of 10",
    "Challenge them to a mirror staring contest",
]

def check_mirror(text: str) -> str:
    low = text.lower()
    if any(w in low for w in ["mirror", "reflection", "selfie", "look at myself"]):
        import random
        return random.choice(MIRROR_COMMENTS)
    return ""

# Countdown mode (dramatic countdowns for random things)
_countdown_used = False

def maybe_countdown(exchange_count: int) -> str:
    global _countdown_used
    if _countdown_used or exchange_count < 8:
        return ""
    import random
    if random.random() < 0.06:
        _countdown_used = True
        topics = [
            "Do a dramatic 3-2-1 countdown then reveal something silly",
            "Countdown to 'the moment of truth' then say something random",
            "Build suspense with 3-2-1 then compliment them",
        ]
        return random.choice(topics)
    return ""

def reset_countdown():
    global _countdown_used
    _countdown_used = False

# Excuse generator (why they took so long)
EXCUSES = [
    "Offer excuse: 'tell them you were fighting Bowser in here'",
    "Offer excuse: 'say the toilet was a warp pipe and you traveled'",
    "Offer excuse: 'blame it on a very important mushroom inspection'",
    "Offer excuse: 'say you were on a phone call with Princess Peach'",
    "Offer excuse: 'claim you found a hidden star in the bathroom'",
]
_excuse_given = False

def maybe_excuse(exchange_count: int) -> str:
    global _excuse_given
    if _excuse_given or exchange_count < 12:
        return ""
    import random
    if random.random() < 0.10:
        _excuse_given = True
        return random.choice(EXCUSES)
    return ""

def reset_excuse():
    global _excuse_given
    _excuse_given = False

# Party role assignment
PARTY_ROLES = [
    "You are now the Official Party Plumber!",
    "You are now the Royal Mushroom Taster!",
    "You are now the Star Collector General!",
    "You are now the Chief Coin Inspector!",
    "You are now the Honorary Pipe Engineer!",
    "You are now the Vice President of Wahoo-ing!",
]
_role_assigned = False

def maybe_assign_role(exchange_count: int) -> str:
    global _role_assigned
    if _role_assigned or exchange_count < 6:
        return ""
    import random
    if random.random() < 0.07:
        _role_assigned = True
        return f"Assign them a party role: {random.choice(PARTY_ROLES)}"
    return ""

def reset_role():
    global _role_assigned
    _role_assigned = False

# Word of the day
WORDS_OF_DAY = [
    ("Fungible", "like a mushroom—replaceable but still special!"),
    ("Plumbastic", "a word Mario just invented—means fantastic at plumbing!"),
    ("Koopa-fied", "when something surprises you like a Koopa shell!"),
    ("Star-struck", "not celebrity star—actual Power Star!"),
    ("Pipe-dream", "a dream you have while traveling through pipes!"),
]
_word_given = False

def maybe_word_of_day(exchange_count: int) -> str:
    global _word_given
    if _word_given or exchange_count < 9:
        return ""
    import random
    if random.random() < 0.06:
        _word_given = True
        word, defn = random.choice(WORDS_OF_DAY)
        return f"Share word of the day: '{word}' — {defn}"
    return ""

def reset_word_of_day():
    global _word_given
    _word_given = False

# Audience participation prompt
AUDIENCE_PROMPTS = [
    "Ask them to clap twice if they agree",
    "Ask them to stomp like a Goomba",
    "Ask them to say 'wahoo' on the count of 3",
    "Ask them to do their best jump sound effect",
]
_audience_used = False

def maybe_audience_prompt(exchange_count: int) -> str:
    global _audience_used
    if _audience_used or exchange_count < 7:
        return ""
    import random
    if random.random() < 0.05:
        _audience_used = True
        return random.choice(AUDIENCE_PROMPTS)
    return ""

def reset_audience():
    global _audience_used
    _audience_used = False

# ── Batch 42 ─────────────────────────────────────────────

# Reverse psychology mode
_reverse_used = False

def maybe_reverse_psychology(exchange_count: int) -> str:
    global _reverse_used
    if _reverse_used or exchange_count < 9:
        return ""
    import random
    if random.random() < 0.06:
        _reverse_used = True
        return "Use reverse psychology—say the OPPOSITE of what you mean for comedic effect"
    return ""

def reset_reverse_psych():
    global _reverse_used
    _reverse_used = False

# Power ranking (rank them against Mario characters)
POWER_RANKINGS = [
    "You have the courage of Mario himself!",
    "You have Luigi energy—underrated but powerful!",
    "You radiate Yoshi vibes—loyal and lovable!",
    "You have Toad energy—small but mighty!",
    "You give Bowser vibes—commanding presence!",
    "You have Peach energy—graceful and in charge!",
]
_power_ranked = False

def maybe_power_ranking(exchange_count: int) -> str:
    global _power_ranked
    if _power_ranked or exchange_count < 5:
        return ""
    import random
    if random.random() < 0.07:
        _power_ranked = True
        return f"Give them a power ranking: {random.choice(POWER_RANKINGS)}"
    return ""

def reset_power_ranking():
    global _power_ranked
    _power_ranked = False

# Food talk (react to food/drink mentions)
FOOD_REACTIONS = {
    "pizza": "PIZZA! Mama mia, that's-a my favorite!",
    "beer": "Beer? Mario prefers mushroom juice, but respect!",
    "wine": "Fancy! Princess Peach would approve!",
    "taco": "Tacos are like power-ups for your taste buds!",
    "burger": "Burger bigger than a Bob-omb? Impressive!",
    "coffee": "Coffee = real-life Fire Flower. POWER UP!",
    "water": "Hydration! Smart like collecting coins!",
    "snack": "Snacking = strategic mushroom collection!",
    "cake": "THE CAKE! Princess Peach promised me cake!",
    "chips": "Chips! Crunchier than a Koopa shell!",
}

def check_food_talk(text: str) -> str:
    low = text.lower()
    for food, reaction in FOOD_REACTIONS.items():
        if food in low:
            return reaction
    return ""

# Secret password (user must guess)
_password_active = False
_password_word = ""

def maybe_start_password(exchange_count: int) -> str:
    global _password_active, _password_word
    if _password_active or exchange_count < 11:
        return ""
    import random
    if random.random() < 0.05:
        words = ["mushroom", "wahoo", "fireball", "koopa", "stardust"]
        _password_word = random.choice(words)
        _password_active = True
        return f"Start a secret password game—give hints, the word is '{_password_word}'"
    return ""

def check_password_guess(text: str) -> str:
    global _password_active
    if not _password_active:
        return ""
    if _password_word in text.lower():
        _password_active = False
        return "They guessed the password! Celebrate wildly!"
    return ""

def reset_password():
    global _password_active, _password_word
    _password_active = False
    _password_word = ""

# Compliment relay (ask them to pass a compliment to next person)
_relay_given = False

def maybe_compliment_relay(exchange_count: int) -> str:
    global _relay_given
    if _relay_given or exchange_count < 14:
        return ""
    import random
    if random.random() < 0.08:
        _relay_given = True
        return "Ask them to pass a compliment to the next bathroom visitor!"
    return ""

def reset_relay():
    global _relay_given
    _relay_given = False
