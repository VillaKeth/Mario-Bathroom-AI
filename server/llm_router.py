"""Dual-model LLM router — picks between fast and quality models.

Routes simple requests (greetings, one-liners) to Mixtral 8x7B (~1s)
and complex requests (gossip, games, stories) to Llama 3.1 70B (~3s).
Does NOT call Ollama directly — only makes routing decisions.
"""

import logging
from enum import Enum

logger = logging.getLogger(__name__)

# Response types that need the quality (larger) model
QUALITY_TYPES = {"gossip", "game", "story", "complex", "vomit_comfort", "farewell_meaningful"}

# Response types that can use the fast (smaller) model
FAST_TYPES = {"greeting", "one_liner", "roast", "acknowledgment", "idle"}


# Inherits from str so values serialize as plain strings in JSON/logs
# (e.g. RoutingDecision.FAST == "fast") without needing .value everywhere.
class RoutingDecision(str, Enum):
    FAST = "fast"
    QUALITY = "quality"


class LLMRouter:
    """Classifies requests and selects the appropriate model."""

    def __init__(self, fast_model: str, quality_model: str):
        self._fast_model = fast_model
        self._quality_model = quality_model
        self.stats = {"fast": 0, "quality": 0, "fallback": 0}
        logger.debug(
            f"LLMRouter: init fast={fast_model} quality={quality_model}"
        )

    def classify(
        self,
        user_input: str,
        response_type: str = None,
        system_prompt: str = None,
    ) -> RoutingDecision:
        """Decide whether a request needs FAST or QUALITY model.

        Priority:
        1. "MUST mention" in system_prompt → QUALITY (gossip with names)
        2. Known QUALITY_TYPES → QUALITY
        3. Known FAST_TYPES → FAST
        4. Unknown type: ≤5 words → FAST, else QUALITY
        """
        logger.debug(
            f"classify: START input={user_input!r:.60} "
            f"type={response_type} has_prompt={system_prompt is not None}"
        )

        # Rule 1: forced quality when system prompt requires specific content
        if system_prompt and "MUST mention" in system_prompt:
            logger.debug("classify: MUST mention → QUALITY")
            self.stats["quality"] += 1
            return RoutingDecision.QUALITY

        # Rule 2/3: known response types
        if response_type in QUALITY_TYPES:
            logger.debug(f"classify: type={response_type} → QUALITY")
            self.stats["quality"] += 1
            return RoutingDecision.QUALITY

        if response_type in FAST_TYPES:
            logger.debug(f"classify: type={response_type} → FAST")
            self.stats["fast"] += 1
            return RoutingDecision.FAST

        # Rule 4: unknown type — use word count heuristic
        word_count = len(user_input.split()) if user_input else 0
        if word_count <= 5:
            logger.debug(f"classify: unknown type, {word_count} words → FAST")
            self.stats["fast"] += 1
            return RoutingDecision.FAST

        logger.debug(f"classify: unknown type, {word_count} words → QUALITY")
        self.stats["quality"] += 1
        return RoutingDecision.QUALITY

    def get_model(self, decision: RoutingDecision) -> str:
        """Return the Ollama model name for a routing decision."""
        if decision == RoutingDecision.FAST:
            return self._fast_model
        return self._quality_model

    def get_fallback(self, failed_decision: RoutingDecision) -> RoutingDecision:
        """Return fallback routing — always falls back to FAST model."""
        self.stats["fallback"] += 1
        logger.debug(f"get_fallback: {failed_decision} → FAST")
        return RoutingDecision.FAST


def infer_response_type(text: str, state: dict) -> str:
    """Infer the response type from user input and current state for router classification."""
    if not text or not text.strip():
        return "idle"
    lower = text.lower().strip()

    # Active game → complex game logic
    if state.get("_active_game"):
        return "game"

    # Sick/vomit mood
    if state.get("_detected_mood") == "sick":
        return "vomit_comfort"

    # Gossip keywords
    gossip_keywords = ("who was here", "who else", "gossip", "tell me about",
                       "who came", "who visited", "any drama", "what happened")
    if any(kw in lower for kw in gossip_keywords):
        return "gossip"

    # Very short acknowledgments
    ack_words = {"ok", "okay", "sure", "yes", "no", "yeah", "yep", "nah",
                 "nope", "cool", "nice", "thanks", "alright", "right", "haha",
                 "lol", "hah", "ha", "hmm", "oh", "wow", "k", "yea"}
    if lower in ack_words or (len(lower.split()) == 1 and lower.rstrip("!?.") in ack_words):
        return "acknowledgment"

    # Greetings
    greeting_words = {"hi", "hey", "hello", "yo", "sup", "howdy", "hiya", "heya",
                      "what's up", "whats up", "wassup"}
    if lower.rstrip("!?.") in greeting_words or any(lower.startswith(g) for g in greeting_words):
        return "greeting"

    # Short roasts
    roast_words = ("roast me", "insult me", "burn me", "diss me")
    if any(kw in lower for kw in roast_words):
        return "roast"

    # Story requests
    story_words = ("tell me a story", "once upon", "story time", "bedtime story")
    if any(kw in lower for kw in story_words):
        return "story"

    # Short one-liners (≤5 words, no complex question)
    if len(text.split()) <= 5:
        return "one_liner"

    return "complex"
