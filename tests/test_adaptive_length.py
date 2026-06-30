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


import asyncio
import llm as llm_mod

def test_num_predict_override_used(monkeypatch):
    captured = {}
    class FakeResp:
        status_code = 200
        def raise_for_status(self): pass
        async def aiter_lines(self):
            yield '{"message":{"content":"hi there friend"},"done":true}'
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
    class FakeClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        def stream(self, method, url, json=None, timeout=None):
            captured["num_predict"] = json["options"]["num_predict"]
            return FakeResp()
    monkeypatch.setattr(llm_mod.httpx, "AsyncClient", lambda *a, **k: FakeClient())
    asyncio.run(
        llm_mod.generate_response([{"role": "user", "content": "hi"}], num_predict=512))
    assert captured["num_predict"] == 512
