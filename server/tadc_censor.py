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

from safety_filter import normalize_unicode  # reuse homoglyph/zero-width normalizer (DRY)

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
    # Stored names are reserved for future logging/formatting; required by the
    # startup pattern so all server modules expose a consistent set_character API.
    global _CHARACTER_NAME, _CHARACTER_DISPLAY_NAME
    if name:
        _CHARACTER_NAME = name
    if display_name:
        _CHARACTER_DISPLAY_NAME = display_name


def censor(text: str) -> CensorResult:
    """Block swears for display, strip them from TTS. Pure; never raises."""
    if not text:
        return CensorResult(display=text or "", tts=text or "", count=0)
    norm = normalize_unicode(text)
    count = len(_SWEAR_RE.findall(norm))
    if not count:
        return CensorResult(display=norm, tts=norm, count=0)
    display = _SWEAR_RE.sub(_BLOCK, norm)
    # Strip swears from the audio entirely (the bleep SFX + mouth bar carry the
    # censorship). Clean up whitespace/comma artifacts left by the removal so the
    # line still reads naturally even before _preclean_tts_text runs downstream.
    tts = _SWEAR_RE.sub(" ", norm)
    tts = re.sub(r"\s+", " ", tts)                # collapse whitespace
    tts = re.sub(r"\s*,(?:\s*,)+", ",", tts)       # collapse comma runs from removed swears
    tts = re.sub(r"^[\s,]+", "", tts).strip()      # drop leading/trailing comma+space
    return CensorResult(display=display, tts=tts, count=count)
