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
    "Mamma mia! How about we talk about-a kart racing instead? Vroom vroom!",
    "Yahoo! That's-a no good! Hey, what's your favorite power-up?",
    "Whoa whoa whoa! Mario says let's-a talk about spaghetti! You like-a meatballs?",
    "Ha! That's-a not how we do it in the Mushroom Kingdom! Tell me about your day!",
    "Oof! Let's-a hit the reset button on this conversation! What games do you play?",
    "No no no! Mario prefers-a talking about coins and stars! How many stars you got?",
    "Mamma mia, that's-a wild! But hey, ever tried a Super Mushroom? Makes you big!",
    "Okie dokie, Mario's-a changing the channel! What's your favorite Mario game?",
    "Wah! That's-a Wario territory! Let's stay on the sunny side, eh?",
    "Bada bing, bada boom! How about we talk about-a pizza instead? Delizioso!",
    "Yikes! That's scarier than a Chain Chomp! Let's-a talk about something nice!",
    "Ha ha, Mario's-a not touching that one! Ever been to Isle Delfino? Beautiful place!",
    "Let's-a go in a different direction! You ever ride a Yoshi? It's-a the best!",
    "Mama mia! Mario needs-a brain bleach! Quick, tell me your favorite dessert!",
    "That's-a not in the plumber's handbook! Wanna hear about my latest adventure?",
    "Ooh, let's-a not go down that pipe! How about a nice game of tennis instead?",
    "Uh oh, red shell incoming! Let's-a dodge that topic! What snacks do you like?",
    "Ha! Even Bowser wouldn't say that! Let's talk about-a something more fun!",
    "Mamma mia! Time for a star power topic change! What's your favorite animal?",
    "Whew! That's-a too spicy even for Fire Mario! How about we talk about music?",
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


def filter_response(text: str) -> str:
    """Filter Mario's response for inappropriate content and LLM artifacts."""
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
