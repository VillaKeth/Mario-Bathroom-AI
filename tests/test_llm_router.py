"""Tests for the LLM Router — dual-model routing logic."""

import pytest
from server.llm_router import LLMRouter, RoutingDecision, infer_response_type


class TestLLMRouter:
    def test_greeting_routes_to_fast(self):
        router = LLMRouter(fast_model="mixtral:8x7b", quality_model="llama3.1:70b-q4_k_m")
        decision = router.classify("Hey Mario!", response_type="greeting")
        assert decision == RoutingDecision.FAST

    def test_gossip_routes_to_quality(self):
        router = LLMRouter(fast_model="mixtral:8x7b", quality_model="llama3.1:70b-q4_k_m")
        decision = router.classify("Tell me about Sarah", response_type="gossip")
        assert decision == RoutingDecision.QUALITY

    def test_must_mention_forces_quality(self):
        router = LLMRouter(fast_model="mixtral:8x7b", quality_model="llama3.1:70b-q4_k_m")
        decision = router.classify("Hi", response_type="greeting", system_prompt="MUST mention Alice")
        assert decision == RoutingDecision.QUALITY

    def test_fallback_on_quality_timeout(self):
        router = LLMRouter(fast_model="mixtral:8x7b", quality_model="llama3.1:70b-q4_k_m")
        decision = router.get_fallback(RoutingDecision.QUALITY)
        assert decision == RoutingDecision.FAST

    def test_one_liner_routes_to_fast(self):
        router = LLMRouter(fast_model="mixtral:8x7b", quality_model="llama3.1:70b-q4_k_m")
        decision = router.classify("What's up?", response_type="one_liner")
        assert decision == RoutingDecision.FAST

    def test_game_routes_to_quality(self):
        router = LLMRouter(fast_model="mixtral:8x7b", quality_model="llama3.1:70b-q4_k_m")
        decision = router.classify("Let's play trivia", response_type="game")
        assert decision == RoutingDecision.QUALITY

    def test_story_routes_to_quality(self):
        router = LLMRouter(fast_model="mixtral:8x7b", quality_model="llama3.1:70b-q4_k_m")
        decision = router.classify("Tell me a story", response_type="story")
        assert decision == RoutingDecision.QUALITY

    def test_roast_routes_to_fast(self):
        router = LLMRouter(fast_model="mixtral:8x7b", quality_model="llama3.1:70b-q4_k_m")
        decision = router.classify("Roast me!", response_type="roast")
        assert decision == RoutingDecision.FAST

    def test_idle_routes_to_fast(self):
        router = LLMRouter(fast_model="mixtral:8x7b", quality_model="llama3.1:70b-q4_k_m")
        decision = router.classify("", response_type="idle")
        assert decision == RoutingDecision.FAST

    def test_acknowledgment_routes_to_fast(self):
        router = LLMRouter(fast_model="mixtral:8x7b", quality_model="llama3.1:70b-q4_k_m")
        decision = router.classify("okay", response_type="acknowledgment")
        assert decision == RoutingDecision.FAST

    def test_vomit_comfort_routes_to_quality(self):
        router = LLMRouter(fast_model="mixtral:8x7b", quality_model="llama3.1:70b-q4_k_m")
        decision = router.classify("I feel sick", response_type="vomit_comfort")
        assert decision == RoutingDecision.QUALITY

    def test_farewell_meaningful_routes_to_quality(self):
        router = LLMRouter(fast_model="mixtral:8x7b", quality_model="llama3.1:70b-q4_k_m")
        decision = router.classify("Goodbye Mario", response_type="farewell_meaningful")
        assert decision == RoutingDecision.QUALITY

    def test_complex_routes_to_quality(self):
        router = LLMRouter(fast_model="mixtral:8x7b", quality_model="llama3.1:70b-q4_k_m")
        decision = router.classify("What's the meaning of life?", response_type="complex")
        assert decision == RoutingDecision.QUALITY

    def test_unknown_type_short_input_routes_to_fast(self):
        router = LLMRouter(fast_model="mixtral:8x7b", quality_model="llama3.1:70b-q4_k_m")
        decision = router.classify("Hey", response_type="unknown_type")
        assert decision == RoutingDecision.FAST

    def test_unknown_type_long_input_routes_to_quality(self):
        router = LLMRouter(fast_model="mixtral:8x7b", quality_model="llama3.1:70b-q4_k_m")
        decision = router.classify("Tell me everything about the Mushroom Kingdom history", response_type="unknown_type")
        assert decision == RoutingDecision.QUALITY

    def test_get_model_fast(self):
        router = LLMRouter(fast_model="mixtral:8x7b", quality_model="llama3.1:70b-q4_k_m")
        assert router.get_model(RoutingDecision.FAST) == "mixtral:8x7b"

    def test_get_model_quality(self):
        router = LLMRouter(fast_model="mixtral:8x7b", quality_model="llama3.1:70b-q4_k_m")
        assert router.get_model(RoutingDecision.QUALITY) == "llama3.1:70b-q4_k_m"

    def test_fallback_always_returns_fast(self):
        router = LLMRouter(fast_model="mixtral:8x7b", quality_model="llama3.1:70b-q4_k_m")
        assert router.get_fallback(RoutingDecision.QUALITY) == RoutingDecision.FAST
        assert router.get_fallback(RoutingDecision.FAST) == RoutingDecision.FAST

    def test_stats_tracking(self):
        router = LLMRouter(fast_model="mixtral:8x7b", quality_model="llama3.1:70b-q4_k_m")
        assert router.stats == {"fast": 0, "quality": 0, "fallback": 0}
        router.classify("Hey!", response_type="greeting")
        assert router.stats["fast"] == 1
        router.classify("Tell me gossip", response_type="gossip")
        assert router.stats["quality"] == 1
        router.get_fallback(RoutingDecision.QUALITY)
        assert router.stats["fallback"] == 1

    def test_none_response_type_short_input(self):
        router = LLMRouter(fast_model="mixtral:8x7b", quality_model="llama3.1:70b-q4_k_m")
        decision = router.classify("Hi there", response_type=None)
        assert decision == RoutingDecision.FAST

    def test_none_response_type_long_input(self):
        router = LLMRouter(fast_model="mixtral:8x7b", quality_model="llama3.1:70b-q4_k_m")
        decision = router.classify("I want to tell you about my entire day at work today", response_type=None)
        assert decision == RoutingDecision.QUALITY

    def test_same_model_no_routing_benefit(self):
        """When both models are the same, routing still works but has no perf impact."""
        router = LLMRouter(fast_model="llama3:8b", quality_model="llama3:8b")
        assert router.get_model(RoutingDecision.FAST) == "llama3:8b"
        assert router.get_model(RoutingDecision.QUALITY) == "llama3:8b"


class TestInferResponseType:
    """Tests for infer_response_type — text classification for the router."""

    def test_empty_input_returns_idle(self):
        assert infer_response_type("", {}) == "idle"

    def test_whitespace_only_returns_idle(self):
        assert infer_response_type("   ", {}) == "idle"

    def test_none_input_returns_idle(self):
        assert infer_response_type(None, {}) == "idle"

    def test_active_game_returns_game(self):
        assert infer_response_type("anything", {"_active_game": True}) == "game"

    def test_sick_mood_returns_vomit_comfort(self):
        assert infer_response_type("ugh", {"_detected_mood": "sick"}) == "vomit_comfort"

    def test_gossip_keywords(self):
        assert infer_response_type("who was here earlier?", {}) == "gossip"
        assert infer_response_type("tell me about Sarah", {}) == "gossip"
        assert infer_response_type("any drama lately?", {}) == "gossip"

    def test_acknowledgment_single_word(self):
        assert infer_response_type("ok", {}) == "acknowledgment"
        assert infer_response_type("thanks", {}) == "acknowledgment"
        assert infer_response_type("lol", {}) == "acknowledgment"

    def test_acknowledgment_with_punctuation(self):
        assert infer_response_type("ok!", {}) == "acknowledgment"
        assert infer_response_type("yeah?", {}) == "acknowledgment"

    def test_greeting(self):
        assert infer_response_type("hello", {}) == "greeting"
        assert infer_response_type("hey!", {}) == "greeting"
        assert infer_response_type("what's up", {}) == "greeting"

    def test_roast(self):
        assert infer_response_type("roast me bro", {}) == "roast"
        assert infer_response_type("insult me please", {}) == "roast"

    def test_story(self):
        assert infer_response_type("tell me a story about Mario", {}) == "story"
        assert infer_response_type("once upon a time in the mushroom kingdom", {}) == "story"

    def test_short_input_returns_one_liner(self):
        assert infer_response_type("what time is it", {}) == "one_liner"

    def test_long_input_returns_complex(self):
        assert infer_response_type(
            "Can you explain the entire history of the Mushroom Kingdom in detail please",
            {},
        ) == "complex"

    def test_game_state_overrides_keywords(self):
        """Active game state takes priority over gossip keywords."""
        assert infer_response_type("tell me about the rules", {"_active_game": True}) == "game"

    def test_sick_mood_overrides_keywords(self):
        """Sick mood takes priority over other keyword matches."""
        assert infer_response_type("hello", {"_detected_mood": "sick"}) == "vomit_comfort"
