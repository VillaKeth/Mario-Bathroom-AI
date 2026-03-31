"""Catchphrase Mirroring — tracks and mirrors guest repeated phrases.

Feeds guest speech into a per-speaker word frequency tracker. When a guest
repeats a word or short phrase 3+ times, Mario calls it out in character.
"""

import logging
import re
from collections import Counter, defaultdict

logger = logging.getLogger("catchphrase-mirror")

# Common words to exclude from tracking
STOP_WORDS = frozenset({
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "i", "you", "he", "she", "it", "we", "they", "me", "him", "her", "us", "them",
    "my", "your", "his", "its", "our", "their", "mine", "yours", "ours", "theirs",
    "this", "that", "these", "those",
    "and", "or", "but", "if", "so", "yet", "for", "nor",
    "in", "on", "at", "to", "of", "by", "with", "from", "up", "out", "off",
    "do", "did", "does", "done", "have", "has", "had", "will", "would",
    "can", "could", "shall", "should", "may", "might", "must",
    "not", "no", "yes", "yeah", "yep", "nah", "nope", "ok", "okay",
    "just", "like", "really", "very", "too", "also", "then", "than",
    "what", "who", "where", "when", "why", "how", "which",
    "all", "some", "any", "every", "each", "much", "many",
    "here", "there", "now", "still", "already", "about", "more",
    "get", "got", "go", "going", "went", "come", "came", "say", "said",
    "know", "think", "want", "see", "make", "take", "let",
    "oh", "um", "uh", "hmm", "ah", "well", "right",
    "mario", "hey", "hi", "hello", "bye", "thanks", "thank",
    "im", "dont", "cant", "wont", "didnt", "doesnt", "isnt", "arent",
    "thats", "its", "hes", "shes", "theyre", "youre", "were",
})

MARIO_TEMPLATES = [
    "Mama mia, you really love talking about {phrase}!",
    "Again with the {phrase}! You're-a obsessed, haha!",
    "If I had a coin for every time you said {phrase}... I'd have-a lot of coins!",
    "{phrase}! {phrase}! {phrase}! That's-a your new catchphrase!",
    "You keep saying {phrase} — is that your superstar word tonight?",
]

# Minimum word length to track
MIN_WORD_LENGTH = 3
# Number of repetitions before triggering a mirror
MIRROR_THRESHOLD = 3


class CatchphraseMirror:
    """Track word frequency per guest and generate Mario-ified callouts."""

    def __init__(self, threshold: int = MIRROR_THRESHOLD):
        self._threshold = threshold
        # speaker_name → Counter of words
        self._word_counts: dict[str, Counter] = defaultdict(Counter)
        # speaker_name → set of already-mirrored phrases (don't repeat)
        self._mirrored: dict[str, set[str]] = defaultdict(set)
        self._template_index = 0

    def feed(self, speaker_name: str, text: str):
        """Track word frequency for a guest's speech."""
        if not speaker_name or not text:
            return
        words = self._extract_words(text)
        name_key = speaker_name.lower().strip()
        self._word_counts[name_key].update(words)

    def get_mirror_phrase(self, speaker_name: str) -> str | None:
        """If guest repeats a word/phrase 3+ times, return a Mario-ified callout."""
        if not speaker_name:
            return None
        name_key = speaker_name.lower().strip()
        counts = self._word_counts.get(name_key)
        if not counts:
            return None

        # Find words at or above threshold that haven't been mirrored yet
        mirrored = self._mirrored[name_key]
        candidates = [
            (word, count) for word, count in counts.most_common(10)
            if count >= self._threshold and word not in mirrored
        ]

        if not candidates:
            return None

        # Pick the most repeated un-mirrored word
        top_word, top_count = candidates[0]
        mirrored.add(top_word)

        template = MARIO_TEMPLATES[self._template_index % len(MARIO_TEMPLATES)]
        self._template_index += 1

        phrase = template.format(phrase=f'"{top_word}"')
        logger.info(f"Catchphrase mirror: {speaker_name} said '{top_word}' {top_count}x → {phrase}")
        return phrase

    def get_party_catchphrases(self) -> dict[str, list[tuple[str, int]]]:
        """Top phrases across all guests for party report.

        Returns: {speaker_name: [(word, count), ...]}
        """
        result = {}
        for name_key, counts in self._word_counts.items():
            top = [
                (word, count) for word, count in counts.most_common(5)
                if count >= 2
            ]
            if top:
                result[name_key] = top
        return result

    def _extract_words(self, text: str) -> list[str]:
        """Extract trackable words from text (lowercase, filtered)."""
        # Remove punctuation, lowercase
        cleaned = re.sub(r"[^a-zA-Z\s]", "", text.lower())
        words = cleaned.split()
        return [
            w for w in words
            if len(w) >= MIN_WORD_LENGTH and w not in STOP_WORDS
        ]

    def reset(self):
        """Clear all tracking data."""
        self._word_counts.clear()
        self._mirrored.clear()
        self._template_index = 0
