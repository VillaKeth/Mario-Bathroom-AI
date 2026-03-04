"""Content safety filter for Mario AI."""

import re
import logging

DEBUG_SAFETY = True
logger = logging.getLogger(__name__)

# Words/phrases that should be filtered from Mario's responses
BLOCKED_PATTERNS = [
    r'\b(fuck|shit|damn|ass|bitch|bastard|dick|cock|pussy)\b',
    r'\b(kill|murder|suicide|die|death)\b(?!.*mushroom)(?!.*bowser)(?!.*goomba)',
    r'\b(racist|sexist|homophob|transphob)\b',
    r'\b(nazi|hitler|holocaust)\b',
    r'\b(drug|cocaine|heroin|meth)\b',
    r'\b(rape|molest|abuse)\b',
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
]


def filter_response(text: str) -> str:
    """Filter Mario's response for inappropriate content."""
    original = text

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
            return {
                "safe": False,
                "redirect": random.choice(REDIRECT_RESPONSES),
            }

    return {"safe": True, "redirect": None}
