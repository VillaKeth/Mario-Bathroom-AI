"""Birthday VIP System — special treatment for the guest of honor.

Tracks the birthday person by name (fuzzy match) and injects VIP context
into Mario's system prompt so he gives them extra-special attention.
"""

import logging
import re
from difflib import SequenceMatcher

logger = logging.getLogger("birthday-vip")


class BirthdayVIP:
    """Manages birthday person detection and VIP prompt injection."""

    def __init__(self, name: str = "", birthday_facts: list[str] | None = None):
        self._name = name.strip()
        self._facts = birthday_facts or []
        self._interaction_count = 0
        self._similarity_threshold = 0.75
        if self._name:
            logger.info(f"Birthday VIP initialized for: '{self._name}'")

    @property
    def name(self) -> str:
        return self._name

    @property
    def interaction_count(self) -> int:
        return self._interaction_count

    def is_configured(self) -> bool:
        """True if a birthday person name has been set."""
        return bool(self._name)

    def is_birthday_person(self, speaker_name: str) -> bool:
        """Fuzzy name match against the configured birthday person."""
        if not self._name or not speaker_name:
            return False
        a = self._name.lower().strip()
        b = speaker_name.lower().strip()
        if a == b:
            return True
        # Check if one name contains the other (e.g. "Mike" in "Michael")
        if a in b or b in a:
            return True
        # SequenceMatcher fuzzy ratio
        ratio = SequenceMatcher(None, a, b).ratio()
        return ratio >= self._similarity_threshold

    def get_vip_prompt_injection(self) -> str:
        """System prompt text reminding Mario this is the birthday person's party."""
        if not self._name:
            return ""
        self._interaction_count += 1

        base = (
            f"🎂 THIS IS {self._name.upper()}'S BIRTHDAY PARTY! "
            f"They are the GUEST OF HONOR. Be extra enthusiastic, warm, and celebratory. "
            f"Reference their birthday naturally — wish them happy birthday, "
            f"make birthday jokes, suggest party activities."
        )

        # Escalate warmth with interaction count
        if self._interaction_count >= 5:
            base += (
                f" You've talked to {self._name} {self._interaction_count} times tonight — "
                f"you're basically best friends now! Be even MORE over-the-top celebratory."
            )
        elif self._interaction_count >= 3:
            base += (
                f" You've been chatting with {self._name} for a while now. "
                f"Drop a callback to something they said earlier!"
            )

        if self._facts:
            facts_str = "; ".join(self._facts)
            base += (
                f" Here are things you know about {self._name} — weave these into conversation "
                f"naturally, don't dump them all at once: {facts_str}."
            )

        return base

    def get_special_greeting(self, speaker_name: str) -> str | None:
        """Returns a special greeting if the speaker is the birthday person."""
        if not self.is_birthday_person(speaker_name):
            return None

        greetings = [
            f"It's the birthday {'star' if self._interaction_count <= 1 else 'legend'}! "
            f"Happy birthday, {self._name}! 🎂",
            f"WAHOO! The guest of honor is here! Happy birthday, {self._name}! 🎉",
            f"Mama mia, it's {self._name}'s special day! Let's-a celebrate! 🎂",
        ]

        if self._interaction_count == 0:
            return greetings[0]
        elif self._interaction_count < 3:
            return greetings[1]
        else:
            return (
                f"There's my birthday bestie {self._name}! "
                f"Visit #{self._interaction_count + 1} tonight — you really love this party! 🎉"
            )

    def reset_interaction_count(self):
        """Reset for a new session."""
        self._interaction_count = 0
