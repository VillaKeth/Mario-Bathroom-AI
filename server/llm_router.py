"""Dual-model LLM router — picks between fast and quality models.

Routes simple requests (greetings, one-liners) to Mixtral 8x7B (~1s)
and complex requests (gossip, games, stories) to Llama 3.1 70B (~3s).
Does NOT call Ollama directly — only makes routing decisions.
"""

import logging
from enum import Enum

DEBUG_ROUTER = True
logger = logging.getLogger(__name__)

# Response types that need the quality (larger) model
QUALITY_TYPES = {"gossip", "game", "story", "complex", "vomit_comfort", "farewell_meaningful"}

# Response types that can use the fast (smaller) model
FAST_TYPES = {"greeting", "one_liner", "roast", "acknowledgment", "idle"}


class RoutingDecision(str, Enum):
    FAST = "fast"
    QUALITY = "quality"


class LLMRouter:
    """Classifies requests and selects the appropriate model."""

    def __init__(self, fast_model: str, quality_model: str):
        self._fast_model = fast_model
        self._quality_model = quality_model
        self.stats = {"fast": 0, "quality": 0, "fallback": 0}
        if DEBUG_ROUTER:
            logger.info(
                f"[DEBUG_ROUTER] LLMRouter: init fast={fast_model} quality={quality_model}"
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
        if DEBUG_ROUTER:
            logger.info(
                f"[DEBUG_ROUTER] classify: START input={user_input!r:.60} "
                f"type={response_type} has_prompt={system_prompt is not None}"
            )

        # Rule 1: forced quality when system prompt requires specific content
        if system_prompt and "MUST mention" in system_prompt:
            if DEBUG_ROUTER:
                logger.info("[DEBUG_ROUTER] classify: MUST mention → QUALITY")
            self.stats["quality"] += 1
            return RoutingDecision.QUALITY

        # Rule 2/3: known response types
        if response_type in QUALITY_TYPES:
            if DEBUG_ROUTER:
                logger.info(f"[DEBUG_ROUTER] classify: type={response_type} → QUALITY")
            self.stats["quality"] += 1
            return RoutingDecision.QUALITY

        if response_type in FAST_TYPES:
            if DEBUG_ROUTER:
                logger.info(f"[DEBUG_ROUTER] classify: type={response_type} → FAST")
            self.stats["fast"] += 1
            return RoutingDecision.FAST

        # Rule 4: unknown type — use word count heuristic
        word_count = len(user_input.split()) if user_input else 0
        if word_count <= 5:
            if DEBUG_ROUTER:
                logger.info(f"[DEBUG_ROUTER] classify: unknown type, {word_count} words → FAST")
            self.stats["fast"] += 1
            return RoutingDecision.FAST

        if DEBUG_ROUTER:
            logger.info(f"[DEBUG_ROUTER] classify: unknown type, {word_count} words → QUALITY")
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
        if DEBUG_ROUTER:
            logger.info(
                f"[DEBUG_ROUTER] get_fallback: {failed_decision} → FAST"
            )
        return RoutingDecision.FAST
