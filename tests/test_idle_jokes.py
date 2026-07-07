from server.idle_behavior import IdleBehavior

class _Loader:
    name = "Rudi"
    _char_dir = None
    def __init__(self, jokes): self._j = jokes
    def get_idle_messages(self): return {"jokes": self._j}

def test_get_joke_delegates_to_engine_bag():
    ib = IdleBehavior(_Loader(["j1", "j2"]), joke_llm_chance=0.0)
    got = {ib.get_joke() for _ in range(20)}
    assert got == {"j1", "j2"}

def test_get_joke_empty_pool_returns_none():
    ib = IdleBehavior(_Loader([]), joke_llm_chance=0.0)
    assert ib.get_joke() is None

def test_joke_llm_fn_wired():
    calls = {"n": 0}
    def fake_llm(): calls["n"] += 1; return "generated joke"
    ib = IdleBehavior(_Loader(["c"]), joke_llm_fn=fake_llm, joke_llm_chance=1.0)
    assert ib.get_joke() == "generated joke"
    assert calls["n"] == 1
