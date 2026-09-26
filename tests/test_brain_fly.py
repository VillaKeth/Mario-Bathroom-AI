import asyncio
import io
import os
import random
import sys
import wave

from server.brain.fly import CREDIT, FlyBrain, worker_command

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FLY_DIR = os.path.join(ROOT, "characters", "fly")


def _wav():
    b = io.BytesIO()
    with wave.open(b, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(24000)
        w.writeframes(b"\x10\x00" * 2400)
    return b.getvalue()


class FakeClient:
    def __init__(self, rates=None, status="ready"):
        self.rates = rates
        self.status, self.stage, self.progress, self.error = status, "", 1.0, ""
        self.info = {"neurons": 166700, "connections": 25582938, "synapses": 124177617,
                     "order": ["sugar", "feed"],
                     "populations": {"sugar": {"size": 77, "label": "SWEET", "kind": "sense"},
                                     "feed": {"size": 2, "label": "FEED", "kind": "readout"}}}
        self.calls = []

    async def start(self):
        pass

    async def stop(self):
        self.status = "stopped"

    async def run(self, stim, ms=500, seed=0, noise=None, reset=False):
        self.calls.append({"stim": stim, "ms": ms, "noise": noise, "reset": reset})
        if self.status != "ready" or self.rates is None:
            return None
        return {"status": "ok", "rates": self.rates, "bins": {"feed": [1.0] * 10},
                "spikes": 1234, "active": 56, "sim_ms": 500.0, "wall_ms": 800.0}


def _fly(client, llm=None):
    return FlyBrain(FLY_DIR, {"window_ms": 500, "words": {"llm": llm is not None},
                              "noise": {"frac": 0.03, "rate": 12}},
                    edge_fn=lambda t: _wav(), llm_fn=llm, client=client, rng=random.Random(1))


def test_candy_feeds_and_speaks():
    c = FakeClient({"sugar": 150.0, "feed": 249.0})
    r = asyncio.run(_fly(c).react_text("have some candy"))
    assert r.behavior.name == "FEED" and r.emotion == "happy" and r.pose_hint == "positive/feeding"
    assert r.text and r.audio
    assert {s["pop"] for s in c.calls[0]["stim"]} == {"ears", "sugar"}
    p = r.panel
    assert p["behavior"] == "FEED" and p["dataset"]["neurons"] == 166700
    assert [row["pop"] for row in p["rows"]] == ["sugar", "feed"] and p["credit"] == CREDIT


def test_escape_buzzes_without_words():
    r = asyncio.run(_fly(FakeClient({"escape": 300.0})).react_text("I'm gonna swat you"))
    assert r.behavior.name == "ESCAPE" and r.text == "" and r.audio


def test_nothing_is_silent():
    r = asyncio.run(_fly(FakeClient({"ears": 50.0})).react_text("hello"))
    assert r.behavior.name == "NOTHING" and r.text == "" and r.audio == b""


def test_reply_while_loading_is_silent_nothing():
    c = FakeClient({"feed": 249.0}, status="loading")
    c.progress, c.stage = 0.4, "fetch"
    r = asyncio.run(_fly(c).react_text("candy"))
    assert r.behavior.name == "NOTHING" and r.text == "" and r.audio == b""
    assert r.panel["status"] == "loading" and r.panel["progress"] == 0.4


def test_idle_uses_noise_and_never_the_llm():
    called = []

    async def llm(m):
        called.append(1)
        return "sweet"
    c = FakeClient({"groom": 100.0})
    r = asyncio.run(_fly(c, llm).idle())
    assert c.calls[0]["stim"] == [] and c.calls[0]["noise"] == {"frac": 0.03, "rate": 12.0}
    assert r.behavior.name == "GROOM" and called == []
    assert r.text == "" and r.audio == b""  # idle grooming is silent (spec 4.5)
    fed = asyncio.run(_fly(FakeClient({"feed": 249.0}), llm).idle())
    assert fed.text and fed.audio and called == []


def test_hung_edge_becomes_a_buzz():
    import time as _t

    def slow_edge(text):
        _t.sleep(1.0)
        return _wav()
    fly = FlyBrain(FLY_DIR, {"words": {"llm": False}, "voice": {"timeout_s": 0.2}},
                   edge_fn=slow_edge, client=FakeClient({"feed": 249.0}), rng=random.Random(1))

    async def body():
        t0 = _t.perf_counter()
        r = await fly.react_text("candy")
        return r, _t.perf_counter() - t0
    r, took = asyncio.run(body())
    assert r.text and r.audio and took < 0.8


def test_events_map_through_senses():
    c = FakeClient({"escape": 0.0})
    asyncio.run(_fly(c).react_event("arrival"))
    assert c.calls[0]["stim"][0]["pop"] == "loom"


def test_windows_start_from_rest_unless_persist():
    c = FakeClient({"feed": 249.0})
    fly = _fly(c)
    asyncio.run(fly.react_text("candy"))
    asyncio.run(fly.idle())
    assert [call["reset"] for call in c.calls] == [True, True]
    kept = FakeClient({"feed": 249.0})
    asyncio.run(FlyBrain(FLY_DIR, {"persist": True, "words": {"llm": False}}, edge_fn=lambda t: _wav(),
                         client=kept, rng=random.Random(1)).react_text("candy"))
    assert kept.calls[0]["reset"] is False


def test_measured_bitter_without_a_bitter_taste_is_not_reject():
    # centrally driven bitter GRNs (the first build measured ~46 Hz) are no taste; air still grooms
    c = FakeClient({"bitter": 46.0, "groom": 263.0, "antenna": 83.0})
    assert asyncio.run(_fly(c).react_text("blow on it")).behavior.name == "GROOM"
    tasted = FakeClient({"bitter": 136.0, "feed": 29.0})
    assert asyncio.run(_fly(tasted).react_text("you are disgusting")).behavior.name == "REJECT"


def test_worker_command_and_snapshot():
    cmd = worker_command({"gain": 0.5, "threads": 8, "cache_dir": "~/x", "auto_fetch": False})
    assert cmd[:3] == [sys.executable, "-m", "server.brain.worker"]
    assert "--no-fetch" in cmd and cmd[cmd.index("--threads") + 1] == "8"
    fly = _fly(FakeClient({"feed": 249.0}))
    asyncio.run(fly.react_text("candy"))
    snap = fly.snapshot()
    assert snap["status"] == "ready" and snap["last"]["behavior"] == "FEED"
