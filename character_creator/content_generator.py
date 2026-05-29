"""Content Generator — LLM-powered YAML content pool generation for characters.

Uses cloud APIs (OpenAI/Anthropic) if available, falls back to local Ollama.
Generates all ~50 content pools needed for a fully functional character.
"""
import os
import sys
import json
import yaml
import asyncio
import logging
import re
from typing import Optional, AsyncGenerator

import httpx

logger = logging.getLogger(__name__)

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "server"))

# ─── LLM Backend Selection ────────────────────────────────────────────────────

def _load_config() -> dict:
    """Load config.json for API keys."""
    config_path = os.path.join(PROJECT_ROOT, "config.json")
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def get_llm_backend() -> dict:
    """Determine which LLM backend to use. Returns {type, model, url/key}."""
    config = _load_config()
    
    # Priority 1: OpenAI
    openai_key = config.get("openai_api_key") or os.environ.get("OPENAI_API_KEY")
    if openai_key:
        return {
            "type": "openai",
            "key": openai_key,
            "model": config.get("openai_model", "gpt-4o-mini"),
            "url": "https://api.openai.com/v1/chat/completions",
        }
    
    # Priority 2: Anthropic
    anthropic_key = config.get("anthropic_api_key") or os.environ.get("ANTHROPIC_API_KEY")
    if anthropic_key:
        return {
            "type": "anthropic",
            "key": anthropic_key,
            "model": config.get("anthropic_model", "claude-3-5-haiku-20241022"),
            "url": "https://api.anthropic.com/v1/messages",
        }
    
    # Priority 3: Ollama (local)
    ollama_url = config.get("ollama_url", "http://localhost:11434")
    ollama_model = config.get("quality_model") or config.get("model") or "llama3"
    return {
        "type": "ollama",
        "url": ollama_url,
        "model": ollama_model,
    }


async def _call_llm(prompt: str, backend: dict, timeout: float = 120.0) -> str:
    """Call LLM and return text response."""
    try:
        if backend["type"] == "openai":
            return await _call_openai(prompt, backend, timeout)
        elif backend["type"] == "anthropic":
            return await _call_anthropic(prompt, backend, timeout)
        else:
            return await _call_ollama(prompt, backend, timeout)
    except Exception as e:
        logger.error(f"LLM call failed ({backend['type']}): {e}")
        # If cloud API fails, try Ollama as last resort
        if backend["type"] != "ollama":
            logger.info("Falling back to Ollama...")
            ollama_backend = {
                "type": "ollama",
                "url": _load_config().get("ollama_url", "http://localhost:11434"),
                "model": _load_config().get("quality_model", "llama3"),
            }
            return await _call_ollama(prompt, ollama_backend, timeout)
        raise


async def _call_openai(prompt: str, backend: dict, timeout: float) -> str:
    """Call OpenAI API."""
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(
            backend["url"],
            headers={
                "Authorization": f"Bearer {backend['key']}",
                "Content-Type": "application/json",
            },
            json={
                "model": backend["model"],
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.8,
                "max_tokens": 4096,
            },
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


async def _call_anthropic(prompt: str, backend: dict, timeout: float) -> str:
    """Call Anthropic API."""
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(
            backend["url"],
            headers={
                "x-api-key": backend["key"],
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json={
                "model": backend["model"],
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.8,
                "max_tokens": 4096,
            },
        )
        resp.raise_for_status()
        return resp.json()["content"][0]["text"]


async def _call_ollama(prompt: str, backend: dict, timeout: float) -> str:
    """Call Ollama API."""
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(
            f"{backend['url']}/api/generate",
            json={
                "model": backend["model"],
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.8, "num_predict": 4096},
            },
        )
        resp.raise_for_status()
        return resp.json()["response"]


# ─── YAML Parsing ─────────────────────────────────────────────────────────────

def _extract_yaml(text: str) -> str:
    """Extract YAML content from LLM response (may be in code fences)."""
    # Try to find YAML in code fences
    match = re.search(r"```(?:ya?ml)?\s*\n(.*?)```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    # If no fences, try to find the YAML list/dict start
    lines = text.strip().split("\n")
    yaml_lines = []
    started = False
    for line in lines:
        if not started:
            # Detect list start OR dict key start (word followed by colon)
            if (line.startswith("- ") or line.startswith("  ") or line == "---"
                    or re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*:\s*$', line)
                    or re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*:\s*\[', line)):
                started = True
        if started:
            # Stop if we hit a line that looks like trailing prose after YAML
            if (yaml_lines and not line.startswith(" ") and not line.startswith("-")
                    and not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*:', line)
                    and line and not line.startswith("#")):
                break
            yaml_lines.append(line)
    if yaml_lines:
        return "\n".join(yaml_lines)
    # Last resort: return everything
    return text.strip()


def _parse_yaml_safe(text: str) -> any:
    """Parse YAML from LLM output, handling common issues."""
    yaml_text = _extract_yaml(text)
    # Fix asterisks in strings that YAML interprets as aliases
    yaml_text = re.sub(r'\*([a-zA-Z]+)\*', r'(\1)', yaml_text)
    try:
        return yaml.safe_load(yaml_text)
    except yaml.YAMLError:
        # Try fixing common issues: unescaped colons, quotes
        fixed = yaml_text.replace(": '", ": \"").replace("'\n", "\"\n")
        try:
            return yaml.safe_load(fixed)
        except yaml.YAMLError as e:
            logger.warning(f"YAML parse failed: {e}")
            return None


# ─── Prompt Templates ─────────────────────────────────────────────────────────

def _character_context(name: str, description: str, personality: str) -> str:
    """Build character context header for prompts."""
    return f"""Character: {name}
Description: {description}
Personality: {personality}
"""


# ─── Pool Generators ──────────────────────────────────────────────────────────

IDLE_POOL_SPECS = {
    "mumbles": {
        "count": 30,
        "desc": "Short 1-2 sentence casual thoughts, observations, or talking-to-self moments",
        "format": "flat_list",
        "example": '- "I wonder what that cloud looks like..."\n- "Hmm, should I reorganize my bookshelf?"',
    },
    "jokes": {
        "count": 30,
        "desc": "Short jokes or humorous observations in character",
        "format": "flat_list",
        "example": '- "Why did the programmer quit? Because he didn\'t get arrays!"\n- "I told my friend a chemistry joke. No reaction."',
    },
    "songs": {
        "count": 25,
        "desc": "Short song lyrics or humming snippets (1-2 lines) that the character might sing",
        "format": "flat_list",
        "example": '- "Do do do, another one bites the dust..."\n- "La la la, walking on sunshine, whoa!"',
    },
    "trivia": {
        "count": 25,
        "desc": "Fun facts or trivia the character would know, prefixed with 'Fun fact!' or 'Did you know?'",
        "format": "flat_list",
        "example": '- "Fun fact! Octopuses have three hearts!"\n- "Did you know honey never expires?"',
    },
    "fun_facts": {
        "count": 20,
        "desc": "Interesting facts related to the character's world or interests",
        "format": "flat_list",
        "example": '- "The human brain uses 20% of your body\'s energy!"\n- "A group of flamingos is called a flamboyance!"',
    },
    "challenges": {
        "count": 20,
        "desc": "Playful challenges or dares the character issues to nearby people",
        "format": "flat_list",
        "example": '- "I challenge you to say tongue-twisters for 30 seconds!"\n- "Bet you can\'t name 5 countries starting with B!"',
    },
    "compliments": {
        "count": 25,
        "desc": "Warm, in-character compliments directed at visitors",
        "format": "flat_list",
        "example": '- "You\'ve got the kind of smile that lights up a room!"\n- "Your vibe is absolutely immaculate today!"',
    },
    "hand_wash_reminders": {
        "count": 15,
        "desc": "Playful/funny reminders to wash hands, in character voice",
        "format": "flat_list",
        "example": '- "Hey, when\'s the last time you washed those hands? Just checking!"\n- "Soap and water, my friend. It\'s a lifestyle!"',
    },
    "noise_reactions": {
        "count": 15,
        "desc": "Reactions to unexpected sounds (door slam, phone ring, etc.)",
        "format": "flat_list",
        "example": '- "Whoa! What was that noise?!"\n- "Did someone just drop something? I felt that in my soul!"',
    },
    "time_comments": {
        "count": 12,
        "desc": "Comments about what time it is or how long the party has been going",
        "format": "flat_list",
        "example": '- "It\'s getting late! The real ones are still here though!"\n- "Morning already? Time flies when you\'re having fun!"',
    },
    "dj_announcements": {
        "count": 10,
        "desc": "Hype announcements like a DJ would make at a party",
        "format": "flat_list",
        "example": '- "EVERYBODY MAKE SOME NOISE!"\n- "This next one goes out to all the night owls!"',
    },
    "lonely_mild": {
        "count": 10,
        "desc": "Slightly lonely/bored remarks when nobody is around (mild)",
        "format": "flat_list",
        "example": '- "Hello? Anyone there? Just me then..."\n- "I guess I\'ll just talk to myself for a bit."',
    },
    "lonely_medium": {
        "count": 10,
        "desc": "More noticeably lonely/existential remarks when alone for a while (medium)",
        "format": "flat_list",
        "example": '- "You know, being alone with your thoughts isn\'t always fun..."\n- "I wonder if anyone remembers I\'m here..."',
    },
    "lonely_deep": {
        "count": 8,
        "desc": "Deep/philosophical lonely remarks when alone for a long time",
        "format": "flat_list",
        "example": '- "What even is consciousness if no one observes it?"\n- "The silence... it speaks louder than words sometimes."',
    },
}

GAME_POOL_SPECS = {
    "trivia": {
        "count": 30,
        "desc": "Trivia questions with answers, themed to the character's world",
        "format": "qa_list",
        "example": '- q: "What is the fastest land animal?"\n  a: "The cheetah, reaching speeds up to 70 mph!"',
    },
    "rapid_fire": {
        "count": 30,
        "desc": "Quick-answer questions for a speed round",
        "format": "qa_list",
        "example": '- q: "Capital of France?"\n  a: "Paris!"',
    },
    "would_you_rather": {
        "count": 25,
        "desc": "Would you rather scenarios with two options",
        "format": "ab_list",
        "example": '- a: "Have the ability to fly"\n  b: "Have the ability to read minds"',
    },
    "wyr_extended": {
        "count": 25,
        "desc": "More creative/wild Would You Rather scenarios",
        "format": "ab_list",
        "example": '- a: "Live in a world where everything is edible"\n  b: "Live in a world where you never need to sleep"',
    },
    "truth_or_dare": {
        "count": 38,
        "desc": "Truth questions and dare challenges. Mix of 15 truths, 15 dares, and 8 bathroom-themed dares",
        "format": "truth_dare",
        "example": 'truths:\n  - "What\'s the most embarrassing thing you\'ve done this week?"\ndares:\n  - "Do your best robot dance for 10 seconds!"\nbathroom_dares:\n  - "Sing a song while washing your hands!"',
    },
    "reactions": {
        "count": 30,
        "desc": "Reactions to winning, losing, or tying in games",
        "format": "reactions",
        "example": 'win:\n  - "YES! I knew it! Victory is sweet!"\nlose:\n  - "Aww man, you got me this time!"\ntie:\n  - "A tie? We\'re too evenly matched!"',
    },
    "name_that_character": {
        "count": 25,
        "desc": "Character descriptions for a guessing game",
        "format": "desc_list",
        "example": '- desc: "A blue hedgehog known for his incredible speed"\n  answer: "Sonic"',
    },
    "simon": {
        "count": 30,
        "desc": "Simon Says actions/commands",
        "format": "flat_list",
        "example": '- "Touch your nose"\n- "Do a jumping jack"\n- "Make a funny face"',
    },
    "hangman": {
        "count": 30,
        "desc": "Words or short phrases for hangman, themed to the character",
        "format": "flat_list",
        "example": '- "ADVENTURE"\n- "FRIENDSHIP"\n- "COSMIC ENERGY"',
    },
    "hot_takes": {
        "count": 30,
        "desc": "Controversial but fun opinions the character holds",
        "format": "flat_list",
        "example": '- "Pineapple on pizza is actually a masterpiece!"\n- "Morning people are just pretending to be happy!"',
    },
    "riddles": {
        "count": 25,
        "desc": "Riddles with answers",
        "format": "qa_list",
        "example": '- q: "I have keys but open no locks. What am I?"\n  a: "A piano!"',
    },
    "karaoke": {
        "count": 25,
        "desc": "Song titles/lyrics for karaoke challenges",
        "format": "flat_list",
        "example": '- "Bohemian Rhapsody - Queen"\n- "Don\'t Stop Believin\' - Journey"',
    },
    "nhie": {
        "count": 30,
        "desc": "Never Have I Ever statements",
        "format": "flat_list",
        "example": '- "Never have I ever eaten an entire pizza by myself"\n- "Never have I ever stayed up for 24 hours straight"',
    },
    "story_starters": {
        "count": 25,
        "desc": "Creative story opening lines for collaborative storytelling",
        "format": "flat_list",
        "example": '- "Once upon a time, in a world where gravity worked sideways..."\n- "The last human on Earth heard a knock at the door..."',
    },
    "twenty_questions": {
        "count": 25,
        "desc": "Objects/concepts for 20 Questions game",
        "format": "flat_list",
        "example": '- "A rainbow"\n- "A black hole"\n- "Pizza delivery"',
    },
    "word_chains": {
        "count": 25,
        "desc": "Seed words to start word chain games (4-8 letter words)",
        "format": "flat_list",
        "example": '- "ADVENTURE"\n- "SUNSET"\n- "GALAXY"',
    },
}

EXTRAS_POOL_SPECS = {
    "easter_eggs": {
        "count": 15,
        "desc": "Hidden responses triggered by specific keywords or phrases",
        "format": "trigger_response",
        "example": '- trigger: "secret"\n  response: "You found a secret! Here\'s a fun fact about me..."',
    },
    "roasts": {
        "count": 20,
        "desc": "Playful, non-mean roasts/teasing lines (friendly banter only)",
        "format": "flat_list",
        "example": '- "I\'ve seen better comebacks in a tennis match!"\n- "Your WiFi signal has more bars than your jokes!"',
    },
    "fortunes": {
        "count": 20,
        "desc": "Fortune cookie style predictions, in character voice",
        "format": "flat_list",
        "example": '- "A great adventure awaits you... right after lunch."\n- "Your future is so bright, I need sunglasses!"',
    },
    "party_tricks": {
        "count": 15,
        "desc": "Fun party tricks or performances the character can describe doing",
        "format": "flat_list",
        "example": '- "Watch this! I can recite the alphabet backwards in 5 seconds!"\n- "Want to see a card trick? Pick a number between 1 and 52!"',
    },
    "encouragements": {
        "count": 20,
        "desc": "Motivational/encouraging phrases in character voice",
        "format": "flat_list",
        "example": '- "You\'ve got this! I believe in you 100%!"\n- "Every expert was once a beginner. Keep going!"',
    },
    "teasing": {
        "count": 15,
        "desc": "Playful teasing lines (lighthearted, never mean)",
        "format": "flat_list",
        "example": '- "Oh, so NOW you show up? I was about to send a search party!"\n- "Look who finally decided to grace us with their presence!"',
    },
    "philosophical_questions": {
        "count": 15,
        "desc": "Deep/silly philosophical questions the character asks",
        "format": "flat_list",
        "example": '- "If you could know the answer to one question about the universe, what would it be?"\n- "Do you think fish know they\'re wet?"',
    },
    "dad_jokes": {
        "count": 20,
        "desc": "Classic dad jokes delivered in character style",
        "format": "flat_list",
        "example": '- "Why don\'t scientists trust atoms? Because they make up everything!"\n- "I used to hate facial hair, but then it grew on me."',
    },
    "puns": {
        "count": 15,
        "desc": "Puns themed to the character's world/interests",
        "format": "flat_list",
        "example": '- "I\'m reading a book on anti-gravity. It\'s impossible to put down!"\n- "Time flies like an arrow. Fruit flies like a banana."',
    },
}


# ─── Prompt Builders ──────────────────────────────────────────────────────────

def _build_flat_list_prompt(name: str, description: str, personality: str, 
                            pool_name: str, spec: dict) -> str:
    """Build prompt for a flat list pool (strings)."""
    return f"""{_character_context(name, description, personality)}

Generate exactly {spec['count']} items for the "{pool_name}" pool.
These are: {spec['desc']}

Output ONLY a YAML list (no extra text, no code fences, no explanations):
{spec['example']}

Requirements:
- Stay completely in character as {name}
- Each item is 1-2 sentences max (under 20 words preferred)
- No duplicates
- No offensive/harmful content
- Must feel authentic to {name}'s personality and world
- Generate exactly {spec['count']} items
"""


def _build_qa_list_prompt(name: str, description: str, personality: str,
                          pool_name: str, spec: dict) -> str:
    """Build prompt for Q&A format pool."""
    return f"""{_character_context(name, description, personality)}

Generate exactly {spec['count']} question-answer pairs for the "{pool_name}" pool.
These are: {spec['desc']}

Output ONLY a YAML list with 'q' and 'a' keys (no extra text):
{spec['example']}

Requirements:
- Theme questions to {name}'s world, interests, and personality
- Mix difficulty levels (easy, medium, hard)
- Answers should be concise (1-2 sentences max)
- No duplicates
- Generate exactly {spec['count']} items
"""


def _build_ab_list_prompt(name: str, description: str, personality: str,
                          pool_name: str, spec: dict) -> str:
    """Build prompt for A/B choice format pool."""
    return f"""{_character_context(name, description, personality)}

Generate exactly {spec['count']} scenarios for the "{pool_name}" pool.
These are: {spec['desc']}

Output ONLY a YAML list with 'a' and 'b' keys (no extra text):
{spec['example']}

Requirements:
- Both options should be interesting and hard to choose between
- Theme to {name}'s world when possible
- Keep each option under 15 words
- No duplicates
- Generate exactly {spec['count']} items
"""


def _build_truth_dare_prompt(name: str, description: str, personality: str,
                             pool_name: str, spec: dict) -> str:
    """Build prompt for truth or dare format."""
    return f"""{_character_context(name, description, personality)}

Generate content for the "truth_or_dare" pool:
- 15 truth questions (fun, personal but not too invasive)
- 15 dares (physical/silly challenges, safe to do)
- 8 bathroom-themed dares (hand washing, mirror, sink related - silly and safe)

Output ONLY this exact YAML structure (no extra text):
truths:
  - "What's the most embarrassing thing you've done?"
  - ...
dares:
  - "Do your best impression of a celebrity!"
  - ...
bathroom_dares:
  - "Sing happy birthday while washing your hands!"
  - ...

Requirements:
- Stay in {name}'s character voice
- Keep dares safe and fun (no dangerous activities)
- Truths should be fun to answer, not too personal
"""


def _build_reactions_prompt(name: str, description: str, personality: str,
                            pool_name: str, spec: dict) -> str:
    """Build prompt for game reactions format."""
    return f"""{_character_context(name, description, personality)}

Generate game reactions for {name} — things they say when winning, losing, or tying at games.

Output ONLY this exact YAML structure (no extra text):
win:
  - "YES! Victory is mine!"
  - ... (10 total)
lose:
  - "Aww, you got me this time!"
  - ... (10 total)
tie:
  - "A tie? We're too evenly matched!"
  - ... (10 total)

Requirements:
- 10 reactions per category (30 total)
- Stay completely in {name}'s character
- Show genuine emotion — excited wins, gracious losses, playful ties
- Each reaction is 1-2 sentences max
- Do NOT use asterisks (*) in any text — use parentheses for actions instead, e.g. (jumps) not *jumps*
"""


def _build_desc_list_prompt(name: str, description: str, personality: str,
                            pool_name: str, spec: dict) -> str:
    """Build prompt for description-based guessing game pool."""
    return f"""{_character_context(name, description, personality)}

Generate exactly {spec['count']} character descriptions for a "Name That Character" guessing game.
These should describe famous characters (movies, TV, games, books) that {name} would know about.

Output ONLY a YAML list with 'desc' and 'answer' keys (no extra text):
- desc: "A blue hedgehog known for incredible speed"
  answer: "Sonic"
- desc: "A wizard boy with a lightning scar on his forehead"
  answer: "Harry Potter"

Requirements:
- Mix difficulty (some obvious, some tricky)
- Characters from {name}'s world/era when possible
- Descriptions should be 1-2 sentences
- No duplicates
- Generate exactly {spec['count']} items
"""


def _build_trigger_response_prompt(name: str, description: str, personality: str,
                                   pool_name: str, spec: dict) -> str:
    """Build prompt for trigger-response easter egg format."""
    return f"""{_character_context(name, description, personality)}

Generate exactly {spec['count']} easter egg trigger-response pairs for {name}.
These are hidden responses triggered when someone says specific words/phrases.

Output ONLY a YAML list with 'trigger' and 'response' keys (no extra text):
- trigger: "secret"
  response: "Ooh, you found a secret! Here's something most people don't know about me..."
- trigger: "meaning of life"
  response: "42. Obviously. Wait, you wanted a real answer?"

Requirements:
- Triggers should be single words or short phrases someone might naturally say
- Responses should be fun, surprising, in-character
- Include some references to {name}'s world/interests
- Each response is 1-2 sentences max
- Generate exactly {spec['count']} items
"""


# ─── Pool Format Dispatch ─────────────────────────────────────────────────────

FORMAT_BUILDERS = {
    "flat_list": _build_flat_list_prompt,
    "qa_list": _build_qa_list_prompt,
    "ab_list": _build_ab_list_prompt,
    "truth_dare": _build_truth_dare_prompt,
    "reactions": _build_reactions_prompt,
    "desc_list": _build_desc_list_prompt,
    "trigger_response": _build_trigger_response_prompt,
}


# ─── Validation ───────────────────────────────────────────────────────────────

def _validate_pool(data, spec: dict) -> bool:
    """Validate generated pool data matches expected format."""
    fmt = spec["format"]
    if data is None:
        return False
    
    if fmt == "flat_list":
        return isinstance(data, list) and len(data) >= 3 and all(isinstance(x, str) for x in data)
    
    elif fmt == "qa_list":
        return (isinstance(data, list) and len(data) >= 3 and 
                all(isinstance(x, dict) and "q" in x and "a" in x for x in data))
    
    elif fmt == "ab_list":
        return (isinstance(data, list) and len(data) >= 3 and
                all(isinstance(x, dict) and "a" in x and "b" in x for x in data))
    
    elif fmt == "truth_dare":
        return (isinstance(data, dict) and "truths" in data and "dares" in data
                and isinstance(data["truths"], list) and isinstance(data["dares"], list))
    
    elif fmt == "reactions":
        return (isinstance(data, dict) and "win" in data and "lose" in data and "tie" in data
                and isinstance(data["win"], list) and isinstance(data["lose"], list))
    
    elif fmt == "desc_list":
        return (isinstance(data, list) and len(data) >= 3 and
                all(isinstance(x, dict) and "desc" in x for x in data))
    
    elif fmt == "trigger_response":
        return (isinstance(data, list) and len(data) >= 3 and
                all(isinstance(x, dict) and "trigger" in x and "response" in x for x in data))
    
    return False


# ─── Main Generation Engine ───────────────────────────────────────────────────

async def generate_pool(name: str, description: str, personality: str,
                        pool_name: str, spec: dict, backend: dict,
                        max_retries: int = 2) -> Optional[any]:
    """Generate a single content pool. Returns parsed data or None on failure."""
    fmt = spec["format"]
    builder = FORMAT_BUILDERS.get(fmt, _build_flat_list_prompt)
    prompt = builder(name, description, personality, pool_name, spec)
    
    for attempt in range(max_retries + 1):
        try:
            raw = await _call_llm(prompt, backend)
            data = _parse_yaml_safe(raw)
            
            if _validate_pool(data, spec):
                return data
            else:
                logger.warning(f"Pool '{pool_name}' attempt {attempt+1}: validation failed, retrying...")
                if attempt < max_retries:
                    prompt += "\n\nIMPORTANT: Your previous response had formatting errors. Output ONLY valid YAML, no extra text."
        except Exception as e:
            logger.error(f"Pool '{pool_name}' attempt {attempt+1} error: {e}")
    
    return None


class ContentGenerationProgress:
    """Tracks generation progress for SSE streaming."""
    
    def __init__(self):
        self.total_pools = 0
        self.completed_pools = 0
        self.current_pool = ""
        self.current_category = ""
        self.errors: list[str] = []
        self.completed_items: list[dict] = []
    
    def to_dict(self) -> dict:
        return {
            "total_pools": self.total_pools,
            "completed_pools": self.completed_pools,
            "current_pool": self.current_pool,
            "current_category": self.current_category,
            "percent": round(self.completed_pools / max(self.total_pools, 1) * 100),
            "errors": self.errors,
        }


async def generate_all_content(
    name: str,
    description: str,
    personality: str,
    char_dir: str,
    categories: Optional[list[str]] = None,
) -> AsyncGenerator[dict, None]:
    """Generate all content pools for a character. Yields progress events.
    
    Args:
        name: Character name
        description: Character description
        personality: Personality traits/tone
        char_dir: Path to character directory
        categories: Optional list of categories to generate. None = all.
                    Valid: ["idle", "games", "extras"]
    """
    backend = get_llm_backend()
    progress = ContentGenerationProgress()
    
    # Determine which categories to generate
    if categories is None:
        categories = ["idle", "games", "extras"]
    
    # Count total pools
    pool_map = {}
    if "idle" in categories:
        pool_map["idle"] = IDLE_POOL_SPECS
    if "games" in categories:
        pool_map["games"] = GAME_POOL_SPECS
    if "extras" in categories:
        pool_map["extras"] = EXTRAS_POOL_SPECS
    
    progress.total_pools = sum(len(specs) for specs in pool_map.values())
    
    yield {"type": "start", "data": progress.to_dict(), "backend": backend["type"]}
    
    # Generate idle messages
    if "idle" in pool_map:
        progress.current_category = "idle"
        idle_data = {}
        
        for pool_name, spec in IDLE_POOL_SPECS.items():
            progress.current_pool = pool_name
            yield {"type": "progress", "data": progress.to_dict()}
            
            data = await generate_pool(name, description, personality, pool_name, spec, backend)
            if data is not None:
                idle_data[pool_name] = data
                progress.completed_items.append({"category": "idle", "pool": pool_name, "count": len(data) if isinstance(data, list) else sum(len(v) for v in data.values() if isinstance(v, list))})
            else:
                progress.errors.append(f"Failed to generate idle/{pool_name}")
            
            progress.completed_pools += 1
            yield {"type": "pool_done", "data": progress.to_dict(), "pool": pool_name, "category": "idle"}
        
        # Write idle/messages.yaml
        idle_path = os.path.join(char_dir, "idle", "messages.yaml")
        os.makedirs(os.path.dirname(idle_path), exist_ok=True)
        with open(idle_path, "w", encoding="utf-8") as f:
            yaml.dump(idle_data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    
    # Generate game pools
    if "games" in pool_map:
        progress.current_category = "games"
        games_dir = os.path.join(char_dir, "games")
        os.makedirs(games_dir, exist_ok=True)
        
        for pool_name, spec in GAME_POOL_SPECS.items():
            progress.current_pool = pool_name
            yield {"type": "progress", "data": progress.to_dict()}
            
            data = await generate_pool(name, description, personality, pool_name, spec, backend)
            if data is not None:
                game_path = os.path.join(games_dir, f"{pool_name}.yaml")
                with open(game_path, "w", encoding="utf-8") as f:
                    yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
                count = len(data) if isinstance(data, list) else sum(len(v) for v in data.values() if isinstance(v, list))
                progress.completed_items.append({"category": "games", "pool": pool_name, "count": count})
            else:
                progress.errors.append(f"Failed to generate games/{pool_name}")
            
            progress.completed_pools += 1
            yield {"type": "pool_done", "data": progress.to_dict(), "pool": pool_name, "category": "games"}
    
    # Generate extras
    if "extras" in pool_map:
        progress.current_category = "extras"
        extras_data = {}
        
        for pool_name, spec in EXTRAS_POOL_SPECS.items():
            progress.current_pool = pool_name
            yield {"type": "progress", "data": progress.to_dict()}
            
            data = await generate_pool(name, description, personality, pool_name, spec, backend)
            if data is not None:
                extras_data[pool_name] = data
                count = len(data) if isinstance(data, list) else sum(len(v) for v in data.values() if isinstance(v, list))
                progress.completed_items.append({"category": "extras", "pool": pool_name, "count": count})
            else:
                progress.errors.append(f"Failed to generate extras/{pool_name}")
            
            progress.completed_pools += 1
            yield {"type": "pool_done", "data": progress.to_dict(), "pool": pool_name, "category": "extras"}
        
        # Write content/extras.yaml
        content_dir = os.path.join(char_dir, "content")
        os.makedirs(content_dir, exist_ok=True)
        extras_path = os.path.join(content_dir, "extras.yaml")
        with open(extras_path, "w", encoding="utf-8") as f:
            yaml.dump(extras_data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    
    # Final summary
    yield {
        "type": "complete",
        "data": progress.to_dict(),
        "summary": {
            "total_generated": progress.completed_pools,
            "total_errors": len(progress.errors),
            "items": progress.completed_items,
            "backend_used": backend["type"],
        },
    }
