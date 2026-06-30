import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))
from mario_prompt import detect_length_intent

def test_guide_requests_are_long():
    for t in [
        "how do I beat the ender dragon?",
        "walk me through building a redstone door",
        "what's the best strategy for ranked?",
        "explain how brewing works step by step",
        "give me tips for aiming better",
        "teach me the combo",
    ]:
        assert detect_length_intent(t) == "long", t

def test_banter_stays_short():
    for t in [
        "hey rudi!", "lol you're funny", "roast me", "what's up",
        "yes", "I'm Jacob", "haha nice", "explain?",  # too short / not a real request
    ]:
        assert detect_length_intent(t) == "short", t
