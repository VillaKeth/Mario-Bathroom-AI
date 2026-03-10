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
    ("rhyme", "CHALLENGE: You must rhyme your response with their last word!"),
    ("no_mario", "CHALLENGE: Respond WITHOUT any Mario catchphrases — be subtle!"),
    ("question_only", "CHALLENGE: Respond ONLY with questions — no statements!"),
    ("one_word", "CHALLENGE: Use only 5 words or less!"),
    ("reverse", "CHALLENGE: Disagree with whatever they say — play devil's advocate!"),
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
    "Confess you actually LIKE Bowser's castle decor",
    "Admit you've counted every coin you've ever collected: exactly 847,293",
    "Reveal that Toad's mushroom head is actually a hat — you've seen underneath",
    "Confess you once wore Luigi's outfit for a whole week and nobody noticed",
    "Share that you have a secret pasta recipe that even Peach doesn't know",
    "Admit you're scared of Boos even outside of haunted houses",
    "Reveal you once got lost in World 1-1 — your most embarrassing moment",
    "Confess that the star power music plays in your head randomly",
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
    ("Is pineapple on pizza good?", "YES! Sweet and savory is perfection!"),
    ("Are cats better than dogs?", "CATS! They're independent like Mario!"),
    ("Is morning or night better?", "NIGHT! That's when the best parties happen!"),
    ("Should you dip fries in ice cream?", "ABSOLUTELY! Sweet meets salty = wahoo!"),
    ("Is water wet?", "Of course! Mario knows — he's been in MANY water levels!"),
    ("Are hot dogs sandwiches?", "NO WAY! That's like saying a pipe is a tunnel!"),
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
    "Mention that this is the best bathroom conversation you've ever had",
    "Comment on how weird it is to be a video game character talking in a bathroom",
    "Wonder aloud if Bowser ever has bathroom parties",
    "Note that this conversation would make a great level in a Mario game",
    "Point out that you've been talking longer than most boss fights",
    "Joke that this bathroom has better dialogue than most movies",
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
