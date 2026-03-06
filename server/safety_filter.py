"""Content safety filter for Mario AI."""

import re
import logging

DEBUG_SAFETY = True
logger = logging.getLogger(__name__)

# Words/phrases that should be filtered from Mario's responses
BLOCKED_PATTERNS = [
    r'\b(fuck|shit|damn|ass|bitch|bastard|dick|cock|pussy)\b',
    r'\b(kill|murder|suicide|die|death|dying)\b(?!.*(?:mushroom|bowser|goomba|game|laughing|funny|comedy))',
    r'\b(racist|sexist|homophob|transphob|bigot)\b',
    r'\b(nazi|hitler|holocaust)\b',
    r'\b(drugs?|cocaine|heroin|meth|weed)\b(?!.*mushroom)',
    r'\b(rape|molest|abuse|assault)\b',
    r'\b(n[i1]gg|f[a4]gg?|r[e3]tard)\b',
]

BLOCKED_RE = [re.compile(p, re.IGNORECASE) for p in BLOCKED_PATTERNS]

# Mario-style replacements for mild language
MILD_REPLACEMENTS = {
    r'\bhell\b': 'heck',
    r'\bcrap\b': 'oh no',
    r'\bstupid\b': 'silly',
    r'\bshut up\b': 'quiet down',
    r'\bidiot\b': 'goofball',
    r'\bdumb\b': 'silly',
}

# Redirect phrases — if user says something problematic, Mario redirects
REDIRECT_RESPONSES = [
    "Mama mia! Let's-a talk about something more fun! Like-a mushrooms!",
    "Wahoo! That's-a not my style! How about we talk about pipes instead?",
    "Okie dokie... Mario prefers-a happier topics! What's your favorite game?",
    "Let's-a keep it family friendly! This-a bathroom is for everyone!",
    "Hmm, Mario doesn't-a know about that! But I do know about saving princesses!",
    "Whoa there! Let's-a change the subject! What's-a your favorite food?",
    "Ha ha, nice try! But Mario only talks about-a good stuff! Like pasta!",
    "That's-a not in my dictionary! Let's talk about something-a fun instead!",
    "Mama mia! I'd rather talk about-a my adventures! Ever been to Rainbow Road?",
    "Okie dokie, let's-a steer this ship in a better direction! What music do you like?",
]

# Track recent redirects to avoid repeating
_recent_redirects = []
_MAX_REDIRECT_HISTORY = 4


def filter_response(text: str) -> str:
    """Filter Mario's response for inappropriate content and LLM artifacts."""
    original = text

    # Strip common LLM artifacts
    text = text.strip()
    # Remove "Mario:" or "Assistant:" prefixes
    text = re.sub(r'^(?:Mario|Assistant|AI|Bot)\s*:\s*', '', text, flags=re.IGNORECASE)
    # Remove quotes wrapping the entire response
    if text.startswith('"') and text.endswith('"'):
        text = text[1:-1]
    # Remove trailing incomplete sentences (no period/!/?)
    if text and text[-1] not in '.!?*♪"' and len(text) > 30:
        last_punct = max(text.rfind('.'), text.rfind('!'), text.rfind('?'), text.rfind('*'))
        if last_punct > len(text) // 2:
            text = text[:last_punct + 1]

    # Check for blocked patterns
    for pattern in BLOCKED_RE:
        if pattern.search(text):
            if DEBUG_SAFETY:
                logger.warning(f"[DEBUG_SAFETY] Blocked pattern found in response, sanitizing")
            text = pattern.sub("****", text)

    # Apply mild replacements
    for pattern, replacement in MILD_REPLACEMENTS.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    if text != original and DEBUG_SAFETY:
        logger.info(f"[DEBUG_SAFETY] filter_response: modified response")

    return text


def check_input(text: str) -> dict:
    """Check user input and determine if it needs special handling.
    
    Returns:
        dict with 'safe' (bool), 'redirect' (str or None)
    """
    if not text:
        return {"safe": True, "redirect": None}

    lower = text.lower()

    # Check for harmful content
    for pattern in BLOCKED_RE:
        if pattern.search(lower):
            if DEBUG_SAFETY:
                logger.warning(f"[DEBUG_SAFETY] check_input: unsafe input detected")
            import random
            available = [r for r in REDIRECT_RESPONSES if r not in _recent_redirects]
            if not available:
                _recent_redirects.clear()
                available = REDIRECT_RESPONSES
            redirect = random.choice(available)
            _recent_redirects.append(redirect)
            if len(_recent_redirects) > _MAX_REDIRECT_HISTORY:
                _recent_redirects.pop(0)
            return {
                "safe": False,
                "redirect": redirect,
            }

    return {"safe": True, "redirect": None}
