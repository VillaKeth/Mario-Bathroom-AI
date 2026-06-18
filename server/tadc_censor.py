"""TADC-style swear censor for Digital Circus characters.

Pure and dependency-light. Detects profanity in a character's OWN output and
returns (a) a display string with each swear replaced by a block (████) for the
speech bubble and (b) a TTS string with each swear removed so synthesis never
voices it. Gated per character via set_enabled() — only on when the active
character's franchise is 'digital_circus'.

Slurs are NOT handled here: safety_filter keeps hard-blocking those to **** on an
independent tier, regardless of this module.
"""
import re
from dataclasses import dataclass

from safety_filter import _normalize_unicode  # reuse homoglyph/zero-width normalizer (DRY)

# Profanity to bleep — the swear subset of safety_filter.CONTENT_PATTERNS plus
# common compounds. \b...\b word boundaries make ordering irrelevant for
# compounds ('shit' won't match inside 'bullshit'), but we still list compounds
# so they're caught as single blocks.
_SWEARS = [
    "motherfucker", "motherfuckin", "bullshit", "asshole", "dumbass", "jackass",
    "dipshit", "dickhead", "fucker", "fuckin", "fucking", "fuck", "shit",
    "bitch", "bastard", "dammit", "damn", "dick", "cock", "pussy", "ass",
    "piss", "crap",
]
_SWEAR_RE = re.compile(r"\b(?:" + "|".join(_SWEARS) + r")\b", re.IGNORECASE)

_BLOCK = "████"  # U+2588 FULL BLOCK ×4 — the bubble censor mark

_ENABLED = False
_CHARACTER_NAME = "assistant"
_CHARACTER_DISPLAY_NAME = "Assistant"


@dataclass
class CensorResult:
    display: str  # swears -> ████ (speech bubble)
    tts: str      # swears removed (audio never voices them)
    count: int    # number of swears found


def set_enabled(enabled: bool):
    global _ENABLED
    _ENABLED = bool(enabled)


def is_enabled() -> bool:
    return _ENABLED


def set_character(name: str, display_name: str):
    global _CHARACTER_NAME, _CHARACTER_DISPLAY_NAME
    if name:
        _CHARACTER_NAME = name
    if display_name:
        _CHARACTER_DISPLAY_NAME = display_name


def censor(text: str) -> CensorResult:
    """Block swears for display, strip them from TTS. Pure; never raises."""
    if not text:
        return CensorResult(display=text or "", tts=text or "", count=0)
    norm = _normalize_unicode(text)
    count = len(_SWEAR_RE.findall(norm))
    if not count:
        return CensorResult(display=text, tts=text, count=0)
    display = _SWEAR_RE.sub(_BLOCK, norm)
    # Remove from audio; ', ' keeps a natural pause. _preclean_tts_text downstream
    # collapses any resulting double commas.
    tts = _SWEAR_RE.sub(", ", norm)
    return CensorResult(display=display, tts=tts, count=count)
