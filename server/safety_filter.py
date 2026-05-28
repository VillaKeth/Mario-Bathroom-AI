"""Content safety filter for Mario AI."""

import re
import logging
import threading
import unicodedata

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

BLOCKED_RE = [re.compile(p, re.IGNORECASE | re.MULTILINE) for p in BLOCKED_PATTERNS]

_CHARACTER_NAME = "assistant"
_CHARACTER_DISPLAY_NAME = "Assistant"


def set_character(name: str, display_name: str):
    global _CHARACTER_NAME, _CHARACTER_DISPLAY_NAME
    if name:
        _CHARACTER_NAME = name
    if display_name:
        _CHARACTER_DISPLAY_NAME = display_name


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
    "Oh wow! Let's switch to something lighter. What's been fun lately?",
    "Well then! Different topic maybe. What music are you into?",
    "Let's keep it friendly. What's your favorite game right now?",
    "How about we keep things easygoing? Tell me about your day.",
    "I'd rather talk about something more upbeat. What's your favorite snack?",
    "Let's change the subject. What have you been enjoying lately?",
    "Nice try, but let's go with something more fun. Watching anything good?",
    "Let's steer this somewhere better. What kind of movies do you like?",
    "I'd rather not go there. What's something you've been excited about?",
    "Let's reset a bit. What songs have been stuck in your head lately?",
    "No thanks. Want to talk about your favorite food instead?",
    "Let's dodge that one. What games do you like to play?",
    "That's not my lane. Tell me something good that happened this week.",
    "Let's keep this conversation positive. What are you looking forward to?",
    "Yikes. New topic? What's your favorite dessert?",
    "I'd skip that one. What's your go-to comfort show?",
    "Let's put that aside. Got any fun weekend plans?",
    "Hard pass on that topic. What's your favorite animal?",
    "Nope, let's pivot. What's the best meal you've had lately?",
    "Let's go another direction. What makes you laugh every time?",
]

# Track recent redirects to avoid repeating
_recent_redirects = []
_MAX_REDIRECT_HISTORY = 4
_redirect_lock = threading.Lock()


def _normalize_unicode(text: str) -> str:
    """Normalize Unicode to defeat homoglyph/fullwidth/combining-mark bypass tricks."""
    text = unicodedata.normalize('NFKC', text)
    # Strip zero-width and formatting control chars (category Cf/Cc except newline/tab)
    text = ''.join(c for c in text if unicodedata.category(c) not in ('Cf',) and c not in ('\u200b', '\u200c', '\u200d', '\ufeff'))
    return text


def _character_break_patterns():
    character_name = (_CHARACTER_NAME or _CHARACTER_DISPLAY_NAME or "this character").strip().title()
    return [
        (r"(?i)\bI'?m (?:an? )?(?:AI(?: language model)?|language model|chatbot|virtual assistant|large language model)\b", f"I'm {character_name}"),
        (r"(?i)\bAs an? (?:AI(?: language model)?|language model|chatbot|assistant)\b", f"As {character_name}"),
        (r"(?i)\bI (?:don't|do not) have (?:feelings|emotions|a body|physical form)\b", "I do have feelings"),
        (r"(?i)\bI was (?:trained|programmed|created) (?:by|to)\b", "I was made to"),
        (r"(?i)\bmy (?:training|programming|algorithms?|neural network)\b", "my perspective"),
        (r"(?i)\bOpenAI|Anthropic|Google AI|Meta AI|GPT-?\d|Claude|Llama|Mistral\b", "my usual style"),
    ]


def filter_response(text: str) -> str:
    """Filter Mario's response for inappropriate content and LLM artifacts."""
    if not text:
        return text or ""
    original = text

    # Normalize Unicode to catch homoglyphs and fullwidth chars
    text = _normalize_unicode(text)

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
                logger.warning(f"[DEBUG_SAFETY] Blocked pattern '{pattern.pattern}' found in response, sanitizing")
            text = pattern.sub("****", text)

    # Apply mild replacements
    for pattern, replacement in MILD_REPLACEMENTS.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    # Catch LLM breaking character — strip meta/AI self-references
    for pat, repl in _character_break_patterns():
        text = re.sub(pat, repl, text)

    # Enforce maximum response length — Mario should be punchy, not an essay writer
    MAX_RESPONSE_CHARS = 300
    if len(text) > MAX_RESPONSE_CHARS:
        # Try to cut at a sentence boundary
        truncated = text[:MAX_RESPONSE_CHARS]
        last_punct = max(truncated.rfind('.'), truncated.rfind('!'), truncated.rfind('?'))
        if last_punct > MAX_RESPONSE_CHARS // 2:
            text = truncated[:last_punct + 1]
        else:
            text = truncated.rstrip() + "."
        if DEBUG_SAFETY:
            logger.info(f"[DEBUG_SAFETY] Truncated response from {len(original)} to {len(text)} chars")

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

    # Normalize Unicode to catch homoglyphs and fullwidth chars
    lower = _normalize_unicode(text).lower()

    # Check for harmful content
    for pattern in BLOCKED_RE:
        if pattern.search(lower):
            if DEBUG_SAFETY:
                logger.warning(f"[DEBUG_SAFETY] check_input: unsafe input detected")
            import random
            with _redirect_lock:
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
