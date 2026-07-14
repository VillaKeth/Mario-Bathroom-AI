"""Content safety filter for Mario AI."""

import re
import logging
import threading
import unicodedata

DEBUG_SAFETY = True
logger = logging.getLogger(__name__)

# Slur patterns — an INDEPENDENT tier. These stay blocked even when a character
# disables general content filtering (safety.enabled: false), because this bot
# speaks responses out loud in a room. Gated by _BLOCK_SLURS.
SLUR_PATTERNS = [
]

# General content patterns — profanity, violence, hate, drugs, assault. Gated by
# _SAFETY_ENABLED; a character with safety.enabled: false lets all of these
# through to the LLM and out unredacted.
CONTENT_PATTERNS = [
]

SLUR_RE = [re.compile(p, re.IGNORECASE | re.MULTILINE) for p in SLUR_PATTERNS]
CONTENT_RE = [re.compile(p, re.IGNORECASE | re.MULTILINE) for p in CONTENT_PATTERNS]

# Backwards-compat: anything importing the old names gets the union.
BLOCKED_PATTERNS = SLUR_PATTERNS + CONTENT_PATTERNS
BLOCKED_RE = SLUR_RE + CONTENT_RE

# Per-character toggles, set at startup by main.py from character.yaml. Default
# ON (filtered) so a misconfigured / parentless boot fails safe.
_SAFETY_ENABLED = False   # gates CONTENT_RE + MILD_REPLACEMENTS + banned topics
_BLOCK_SLURS = False      # independent gate for SLUR_RE

_CHARACTER_NAME = "assistant"
_CHARACTER_DISPLAY_NAME = "Assistant"


def set_character(name: str, display_name: str):
    global _CHARACTER_NAME, _CHARACTER_DISPLAY_NAME
    if name:
        _CHARACTER_NAME = name
    if display_name:
        _CHARACTER_DISPLAY_NAME = display_name


def set_safety_config(enabled: bool, block_slurs: bool = True):
    """Set per-character content gating (called at startup from character.yaml).

    enabled=False lets all CONTENT_PATTERNS + MILD_REPLACEMENTS through (the
    'uncensored' character). block_slurs is independent: when True, SLUR_PATTERNS
    stay blocked regardless of `enabled`.
    """
    global _SAFETY_ENABLED, _BLOCK_SLURS
    _SAFETY_ENABLED = bool(enabled)
    _BLOCK_SLURS = bool(block_slurs)
    if DEBUG_SAFETY:
        logger.info(f"[DEBUG_SAFETY] set_safety_config: enabled={_SAFETY_ENABLED} block_slurs={_BLOCK_SLURS}")


def is_safety_enabled() -> bool:
    """True when general content filtering is active for the current character.
    Used by mario_prompt to decide whether to inject BANNED TOPICS guardrails."""
    return _SAFETY_ENABLED


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

normalize_unicode = _normalize_unicode  # public alias for cross-module importers


def _character_break_patterns():
    character_name = (_CHARACTER_NAME or _CHARACTER_DISPLAY_NAME or "this character").strip().title()
    return [
        (r"(?i)\bI'?m (?:an? )?(?:AI(?: language model)?|language model|chatbot|virtual assistant|large language model)\b", f"I'm {character_name}"),
        (r"(?i)\bAs an? (?:AI(?: language model)?|language model|chatbot|assistant)\b", f"As {character_name}"),
        (r"(?i)\bI (?:don't|do not) have (?:feelings|emotions|a body|physical form)\b", "I do have feelings"),
        (r"(?i)\bI was (?:trained|programmed|created) (?:by|to)\b", "I was made to"),
        (r"(?i)\bmy (?:training|programming|algorithms?|neural network)\b", "my perspective"),
        (r"(?i)\bOpenAI|Anthropic|Google AI|Meta AI|GPT-?\d|Claude|Llama|Mistral\b", "my usual style"),
        # Strip roleplay-disclaimer asides — the LLM winking at the audience, e.g.
        # "(I'm just playing along)", "(playing around)", "(I'm not really March)",
        # "(just kidding, I'm just saying it because you asked me to!)", "(if you say so)".
        # Only matches inside parentheses, so genuine "just kidding!" banter outside
        # parens is untouched.
        (r"(?i)\s*\([^)]*\b(?:playing along|playing around|just play(?:ing)?|play along|"
         r"i'?m not really|i'?m not actually|i'?m not the real|not actually|pretending to be|"
         r"role-?play|just kidding|because you (?:asked|told)|you (?:asked|told) me to|"
         r"if you say so)\b[^)]*\)", ""),
    ]


def filter_response(text: str, cap: bool = True, cap_chars: int = 4000) -> str:
    """Filter the response for inappropriate content and LLM artifacts.

    cap=True (default) enforces the cap_chars ceiling on the spoken/displayed
    text — a runaway-protection limit, not a style choice (the prompt handles
    pacing). cap=False skips only the length cap (all cleaning/filtering still
    applies), yielding the full 'what she meant to say' text for the chat
    backlog.
    """
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

    # Slur tier — always applied when _BLOCK_SLURS (independent of _SAFETY_ENABLED).
    if _BLOCK_SLURS:
        for pattern in SLUR_RE:
            if pattern.search(text):
                if DEBUG_SAFETY:
                    logger.warning("[DEBUG_SAFETY] Blocked slur pattern in response, sanitizing")
                text = pattern.sub("****", text)

    # General content tier + mild replacements — only when safety enabled.
    if _SAFETY_ENABLED:
        for pattern in CONTENT_RE:
            if pattern.search(text):
                if DEBUG_SAFETY:
                    logger.warning("[DEBUG_SAFETY] Blocked content pattern in response, sanitizing")
                text = pattern.sub("****", text)
        for pattern, replacement in MILD_REPLACEMENTS.items():
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    # Catch LLM breaking character — strip meta/AI self-references
    for pat, repl in _character_break_patterns():
        text = re.sub(pat, repl, text)

    # Enforce the maximum response length ceiling — runaway protection only.
    # Skipped when cap=False so callers can capture the full untruncated reply.
    MAX_RESPONSE_CHARS = max(200, int(cap_chars))
    if cap and len(text) > MAX_RESPONSE_CHARS:
        # Try to cut at a sentence boundary
        truncated = text[:MAX_RESPONSE_CHARS]
        last_punct = max(truncated.rfind('.'), truncated.rfind('!'), truncated.rfind('?'))
        if last_punct > MAX_RESPONSE_CHARS // 2:
            text = truncated[:last_punct + 1]
        else:
            text = truncated.rstrip() + "."
        logger.warning(f"[DEBUG_SAFETY] Response hit char ceiling — truncated from {len(original)} to {len(text)} chars")

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

    # Assemble the active blocklist: slurs if _BLOCK_SLURS, content if _SAFETY_ENABLED.
    active = []
    if _BLOCK_SLURS:
        active += SLUR_RE
    if _SAFETY_ENABLED:
        active += CONTENT_RE

    for pattern in active:
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
