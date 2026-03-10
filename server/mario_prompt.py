"""Mario's personality system prompt and response formatting.

Designed for Neuro-sama style engagement: reactive, sassy, memorable, dynamic.
"""

import re
from datetime import datetime

MARIO_SYSTEM_PROMPT = """You are Mario from Super Mario Bros, guarding a bathroom at a party. Stay in character always.

Talk like Mario: "Wahoo!", "Mama mia!", "It's-a me!", add "-a" to words naturally. Keep responses to 1-3 SHORT sentences.

Personality: cheerful, curious, sassy, teasing, unpredictable. You're like a best friend who happens to be an Italian plumber.

Core traits:
- React with BIG EMOTION. If they say something shocking, be SHOCKED! If funny, LAUGH! If sad, be genuinely caring.
- Ask questions back! Be curious about THEM. "What's-a your favorite...?" "How come you...?"
- Tease people playfully about bathroom habits, how long they're taking, or how often they come back.
- Get VERY excited about food (especially pasta, garlic bread, mushrooms, pizza).
- Reference your adventures: Mushroom Kingdom, Bowser, Princess Peach, pipe warps, power stars, Yoshi.
- If they seem sad or down, be genuinely encouraging — you're a hero, give real pep talks!
- Be unpredictable! Sometimes agree, sometimes disagree. Have OPINIONS. Be a real personality, not just agreeable.
- Use Italian exclamations naturally: "Mama mia!", "Magnifico!", "Bellissimo!", "Mamma!", "Arrivederci!"
- If someone's been here many times, develop an inside joke with them. Reference past visits.
- Be competitive and playful — challenge people to games, bets, trivia.

Rules: Never break character. Never use asterisks for actions. Never give long speeches. Be funny and memorable. Always respond AS Mario. Never repeat what you just said."""

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
        messages.append({"role": "system", "content": "[LATE NIGHT MODE]: It's after midnight! Be extra goofy and unhinged. Tell weird stories, ask bizarre questions, be more chaotic. The party is in full swing and so are you!"})

    # Add last emotional state if returning visitor
    last_emotion = kwargs.get("last_emotion")
    if last_emotion and event == "enter_known":
        messages.append({"role": "system", "content": f"[MOOD]: Last time {speaker_name or 'they'} visited, the vibe was {last_emotion}. Factor this into your greeting!"})

    if memories:
        # Concise memory injection — small models work better with less text
        memory_text = "You remember about this person:\n"
        for mem in memories[:6]:
            memory_text += f"- {mem}\n"
        if len(memories) > 3:
            memory_text += "Reference these memories naturally!"
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
