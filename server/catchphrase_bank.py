"""Pre-recorded catchphrase matcher for instant Mario voice playback.

Maps known Mario catchphrases to pre-recorded WAV files for zero-latency
response on exact-match phrases like "Wahoo!", "Mama mia!", etc.

Usage:
    bank = CatchphraseBank(assets_dir="assets/catchphrases")
    audio = bank.match("Wahoo!")  # Returns bytes or None
"""

import logging
import os
import re

logger = logging.getLogger(__name__)


class CatchphraseBank:
    """Maps Mario catchphrases to pre-recorded WAV files.

    Attempts to load WAV files from assets_dir, keyed by normalized phrase.
    Files should be named like: wahoo.wav, mama_mia.wav, lets-a_go.wav, etc.
    """

    CATCHPHRASES = [
        "wahoo",
        "mama mia",
        "lets-a go",
        "its-a me mario",
        "yahoo",
        "okie dokie",
        "here we go",
    ]

    def __init__(self, assets_dir: str = "assets/catchphrases"):
        self._assets_dir = assets_dir
        self._cache: dict[str, bytes] = {}
        self._load_assets()

    def _load_assets(self):
        """Load WAV files from the assets directory into memory cache."""
        if not os.path.isdir(self._assets_dir):
            logger.debug(f"[catchphrase_bank] Assets dir not found: {self._assets_dir} — no catchphrases loaded")
            return

        loaded = 0
        for filename in os.listdir(self._assets_dir):
            if not filename.lower().endswith(".wav"):
                continue
            phrase_key = os.path.splitext(filename)[0].replace("_", " ").lower()
            filepath = os.path.join(self._assets_dir, filename)
            try:
                with open(filepath, "rb") as f:
                    self._cache[phrase_key] = f.read()
                loaded += 1
                logger.debug(f"[catchphrase_bank] Loaded catchphrase: '{phrase_key}' from {filename}")
            except Exception as e:
                logger.debug(f"[catchphrase_bank] Failed to load {filename}: {e}")

        logger.debug(f"[catchphrase_bank] Loaded {loaded} catchphrase WAV files from {self._assets_dir}")

    def normalize(self, text: str) -> str:
        """Normalize text for catchphrase matching.

        Lowercases, strips punctuation (except hyphens), collapses whitespace.
        """
        text = text.lower().strip()
        # Remove all punctuation except hyphens (keep contractions like "let's-a")
        text = re.sub(r"[^\w\s-]", "", text)
        # Remove apostrophes that weren't caught (word chars include letters/digits/underscore)
        text = text.replace("_", " ")
        # Collapse multiple spaces
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def match(self, text: str) -> bytes | None:
        """Return WAV bytes if text is an exact catchphrase match, else None.

        Normalizes input text before matching against known catchphrases.
        Returns cached WAV bytes or None.
        """
        normalized = self.normalize(text)
        if normalized not in self.CATCHPHRASES:
            return None

        if normalized in self._cache:
            logger.debug(f"[catchphrase_bank] Catchphrase HIT: '{normalized}'")
            return self._cache[normalized]

        # Catchphrase recognized but no WAV file available
        logger.debug(f"[catchphrase_bank] Catchphrase recognized but no WAV file: '{normalized}'")
        return None

    def is_available(self) -> bool:
        """True if at least one catchphrase WAV file is loaded."""
        return len(self._cache) > 0

    def loaded_phrases(self) -> list[str]:
        """Return list of catchphrases that have loaded WAV files."""
        return list(self._cache.keys())
