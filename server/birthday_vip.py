"""Birthday VIP System — special treatment for the guest of honor.

Tracks the birthday person by name (fuzzy match) and injects VIP context
into Mario's system prompt so he gives them extra-special attention.
"""

import logging
import random
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
        """Returns a special greeting if the speaker is the birthday person.

        First interaction gets the big reveal greeting. Subsequent visits
        randomly pick from personalized variants that reference real
        accomplishments, with a recurring-visit variant for 3+ visits.
        """
        if not self.is_birthday_person(speaker_name):
            return None

        # Personalized greetings referencing Jacob's real accomplishments
        personalized_greetings = [
            (
                f"The BIRTHDAY BOY is here! {self._name}, the man who got "
                f"PUBLISHED in a Taylor and Francis book before graduation! "
                f"Everybody make some noise! 🎂"
            ),
            (
                f"JACOB! Happy birthday you absolute legend! Seven live projects "
                f"and counting! GatorCommunities, CelebMax, the works! "
                f"This party is ALL for you! 🎉"
            ),
            (
                f"It's-a the birthday king himself! {self._name}, the guy who "
                f"built an earthquake prediction game called Normal Weather! "
                f"That's the kind of beautiful chaos I love! 🎂"
            ),
            (
                f"WAHOO! {self._name}'s in the building! Published researcher, "
                f"full-stack developer, and tonight's VIP! Happy birthday! 🎉"
            ),
            (
                f"The man of the hour! {self._name}, your dad Carl and mom Stacy "
                f"raised a GENIUS! Happy birthday from your favorite bathroom "
                f"companion! 🎂"
            ),
        ]

        if self._interaction_count == 0:
            # First sighting gets the big reveal
            return personalized_greetings[0]
        elif self._interaction_count < 3:
            return random.choice(personalized_greetings)
        else:
            # After many visits, mix personalized with a recurring-visit variant
            recurring = (
                f"There's my birthday bestie {self._name}! "
                f"Visit #{self._interaction_count + 1} tonight — you really love this party! 🎉"
            )
            return random.choice(personalized_greetings + [recurring])

    def reset_interaction_count(self):
        """Reset for a new session."""
        self._interaction_count = 0
