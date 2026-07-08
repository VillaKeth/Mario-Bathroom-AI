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
        "that's a good story bro",  # passing mention of "story" is NOT a request
        "no way that's the whole thing",
    ]:
        assert detect_length_intent(t) == "short", t

def test_story_requests_are_long():
    # Storytelling / "give me the long version" requests must get the long token
    # budget. Regression: _LONG_INTENT_PATTERNS had how-to/guide patterns but ZERO
    # storytelling patterns, so "tell me a long story" was tagged "short" and the
    # model was guillotined at the short budget mid-narrative.
    for t in [
        "tell me a long story about a dragon",
        "tell me a story about a brave knight",
        "can you tell me a really long story please",
        "tell me about the time you saved the princess",
        "give me the long version of that",
        "go into detail about your adventures",
    ]:
        assert detect_length_intent(t) == "long", t


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


def test_background_gen_yields_to_user_request(monkeypatch):
    # A non-user (background: idle/joke/greeting) generation must bail the instant
    # a user request needs the model, so it stops competing for the CPU-bound LLM
    # and starving the real response. A user request (is_user_request=True) must
    # NOT bail even while the user-generating flag is set (it IS that request).
    import gen_guard
    monkeypatch.setattr(llm_mod, "LLM_PARTIAL_GRACE", 0)  # isolate: no soft-deadline
    monkeypatch.setattr(gen_guard, "is_user_generating", lambda: True)

    def make_client():
        class FakeResp:
            def raise_for_status(self):
                pass
            async def aiter_lines(self):
                yield '{"message":{"content":"background text "},"done":false}'
                yield '{"message":{"content":"more and "},"done":false}'
                yield '{"message":{"content":"still more"},"done":true}'
            async def __aenter__(self): return self
            async def __aexit__(self, *a): return False
        class FakeClient:
            async def __aenter__(self): return self
            async def __aexit__(self, *a): return False
            def stream(self, *a, **k): return FakeResp()
        return FakeClient()
    monkeypatch.setattr(llm_mod.httpx, "AsyncClient", lambda *a, **k: make_client())

    # background call yields -> fallback, no real content spoken
    bg = asyncio.run(
        llm_mod.generate_response([{"role": "user", "content": "x"}], is_user_request=False))
    assert bg.get("was_fallback") is True

    # the user's own request must complete even though the flag is set
    user = asyncio.run(
        llm_mod.generate_response([{"role": "user", "content": "x"}], is_user_request=True))
    assert user.get("was_fallback") is not True
    assert "background text" in user["text"]


def test_partial_reply_salvaged_on_soft_deadline(monkeypatch):
    # When generation would blow the LLM timeout, return the PARTIAL reply
    # produced so far (marked was_partial) instead of discarding it for a canned
    # fallback. Regression: on a slow box a long story generated for the full
    # timeout, got cancelled, and every token was thrown away -> "I lost my
    # train of thought" instead of the story.
    monkeypatch.setattr(llm_mod, "LLM_TIMEOUT", 10.0)
    monkeypatch.setattr(llm_mod, "LLM_PARTIAL_GRACE", 4.0)  # soft deadline = 6s

    class Clock:
        t = 0.0
        def __call__(self):
            return self.t
    clock = Clock()
    monkeypatch.setattr(llm_mod.time, "time", clock)

    class FakeResp:
        def raise_for_status(self):
            pass
        async def aiter_lines(self):
            clock.t = 2.0; yield '{"message":{"content":"Once upon a time "},"done":false}'
            clock.t = 4.0; yield '{"message":{"content":"there was a dragon "},"done":false}'
            clock.t = 7.0; yield '{"message":{"content":"who guarded gold. "},"done":false}'
            clock.t = 9.0; yield '{"message":{"content":"PAST THE DEADLINE"},"done":false}'
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
    class FakeClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        def stream(self, *a, **k): return FakeResp()
    monkeypatch.setattr(llm_mod.httpx, "AsyncClient", lambda *a, **k: FakeClient())

    out = asyncio.run(
        llm_mod.generate_response([{"role": "user", "content": "tell me a story"}]))
    assert "Once upon a time" in out["text"]
    assert "dragon" in out["text"]
    assert "PAST THE DEADLINE" not in out["text"]   # stopped at the soft deadline
    assert out.get("was_partial") is True
    assert out.get("was_fallback") is not True


from mario_prompt import maybe_add_followup

def test_followup_throttled():
    flag = [False]
    # First active-convo turn may add a hook
    out1 = maybe_add_followup("Cool build.", history_len=6, last_added=flag)
    # Immediately after a hook, the next turn must NOT add another
    if flag[0]:
        out2 = maybe_add_followup("Nice.", history_len=6, last_added=flag)
        assert out2 == "Nice."  # throttled
    # Short/early convo never adds
    flag2 = [False]
    assert maybe_add_followup("Hi.", history_len=1, last_added=flag2) == "Hi."
    assert flag2[0] is False
