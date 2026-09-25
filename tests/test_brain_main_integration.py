import asyncio
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))


class FakeWS:
    def __init__(self):
        self.jsons, self.blobs = [], []

    async def send_json(self, m):
        self.jsons.append(m)

    async def send_bytes(self, b):
        self.blobs.append(b)


def _reply(name="FEED", text="sweet.", audio=b"RIFFfly"):
    b = SimpleNamespace(name=name)
    return SimpleNamespace(text=text, audio=audio, behavior=b, emotion="happy",
                           pose_hint="positive/feeding", panel={"behavior": name, "status": "ready"})


class FakeFly:
    def __init__(self, reply=None):
        self.reply = reply or _reply()
        self.calls = []
        self.voice = SimpleNamespace(speak=lambda t: b"RIFFannounce")
        self.stopped = False

    async def react_text(self, text):
        self.calls.append(("text", text))
        return self.reply

    async def react_event(self, event):
        self.calls.append(("event", event))
        return self.reply

    async def idle(self):
        self.calls.append(("idle",))
        return self.reply

    async def stop(self):
        self.stopped = True

    def panel(self):
        return {"status": "ready"}

    def snapshot(self):
        return {"status": "ready", "last": None}


def _brainy(monkeypatch, main, fly=None):
    monkeypatch.setattr(main, "_character", SimpleNamespace(
        name="Fly", display_name="The Fly", brain={"enabled": True}, character_dir="x"))
    fly = fly or FakeFly()
    monkeypatch.setattr(main, "_fly_brain", fly)
    return fly


def test_reply_goes_through_brain_not_llm(monkeypatch):
    import main
    fly = _brainy(monkeypatch, main)

    def boom(*a, **k):
        raise AssertionError("LLM/safety path must not run for the fly")
    monkeypatch.setattr(main, "check_input", boom)
    ws = FakeWS()
    asyncio.run(main._generate_and_send_response(ws, "have some candy", source="text"))
    assert fly.calls == [("text", "have some candy")]
    types = [j["type"] for j in ws.jsons]
    assert types == ["brain_state", "mario_response"]
    resp = ws.jsons[1]
    assert resp["text"] == "sweet." and resp["pose_hint"] == "positive/feeding"
    assert ws.blobs == [b"RIFFfly"]


def test_face_greeting_is_an_arrival_event(monkeypatch):
    import main
    fly = _brainy(monkeypatch, main)
    asyncio.run(main._generate_and_send_response(FakeWS(), "Hi Jacob!", source="face_greeting"))
    assert fly.calls == [("event", "arrival")]


def test_silent_behavior_sends_only_brain_state(monkeypatch):
    import main
    _brainy(monkeypatch, main, FakeFly(_reply("NOTHING", "", b"")))
    ws = FakeWS()
    asyncio.run(main._generate_and_send_response(ws, "hello", source="text"))
    assert [j["type"] for j in ws.jsons] == ["brain_state"] and ws.blobs == []


def test_send_response_blocks_non_brain_text_for_brain_character(monkeypatch):
    import main
    _brainy(monkeypatch, main)
    ws = FakeWS()
    asyncio.run(main.send_response(ws, "It's-a me, Mario!"))
    assert ws.jsons == [] and ws.blobs == []
    asyncio.run(main.send_response(ws, "sweet.", b"RIFF", _brain_ok=True))
    assert ws.jsons and ws.jsons[0]["text"] == "sweet."


def test_brainless_character_unaffected(monkeypatch):
    import main
    monkeypatch.setattr(main, "_character", SimpleNamespace(name="Ani", display_name="Ani", brain={}))
    monkeypatch.setattr(main, "_fly_brain", None)
    ws = FakeWS()
    asyncio.run(main.send_response(ws, "hi there"))
    assert ws.jsons and ws.jsons[0]["text"] == "hi there"


def test_idle_tick_sends_brain_state_and_idle_line(monkeypatch):
    import main
    _brainy(monkeypatch, main)
    main.state_current["_response_completed_time"] = 0.0
    main.state_current["_last_user_msg_time"] = 0.0
    main.state_current["_user_request_active"] = False
    main.state_current["memorial_active"] = False
    main.state_current["_performing_song_until"] = 0.0
    monkeypatch.setattr(main, "_current_response_task", None)
    monkeypatch.setattr(main, "_reply_paused", lambda: False)
    ws = FakeWS()
    assert asyncio.run(main._brain_idle_tick(ws)) is True
    assert [j["type"] for j in ws.jsons] == ["brain_state", "mario_response"]
    assert ws.jsons[1].get("is_idle") is True


def test_idle_tick_speaks_admin_announcement_in_fly_voice(monkeypatch):
    import main
    fly = _brainy(monkeypatch, main)
    for k, v in {"_response_completed_time": 0.0, "_last_user_msg_time": 0.0,
                 "_user_request_active": False, "memorial_active": False,
                 "_performing_song_until": 0.0}.items():
        main.state_current[k] = v
    main.state_current["_pending_announcement"] = "cake in the kitchen"
    monkeypatch.setattr(main, "_current_response_task", None)
    monkeypatch.setattr(main, "_reply_paused", lambda: False)
    ws = FakeWS()
    assert asyncio.run(main._brain_idle_tick(ws)) is True
    assert ws.jsons[0]["text"] == "cake in the kitchen" and ws.blobs == [b"RIFFannounce"]
    assert fly.calls == []


def test_idle_loop_survives_a_failing_brain_tick(monkeypatch):
    # the idle loop is a fire-and-forget task: one escaped exception would end
    # the fly's idle life for the rest of an 8-hour party
    import pytest
    import main
    _brainy(monkeypatch, main)
    for k, v in {"_response_completed_time": 0.0, "_last_user_msg_time": 0.0,
                 "_user_request_active": False, "memorial_active": False}.items():
        main.state_current[k] = v
    ticks = []

    async def bad_tick(ws):
        ticks.append(1)
        raise RuntimeError("worker gone")
    monkeypatch.setattr(main, "_brain_idle_tick", bad_tick)
    real_sleep, sleeps = asyncio.sleep, []

    async def fast_sleep(s, *a, **k):
        sleeps.append(s)
        if len(sleeps) > 3:
            raise asyncio.CancelledError
        await real_sleep(0)
    monkeypatch.setattr(main.asyncio, "sleep", fast_sleep)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(main._idle_loop(FakeWS()))
    assert len(ticks) == 3


def test_switch_to_brainless_character_stops_brain_and_lifts_gate(monkeypatch):
    import main
    fly = _brainy(monkeypatch, main)
    monkeypatch.setattr(main, "_character", SimpleNamespace(name="Ani", display_name="Ani", brain={}))
    asyncio.run(main._start_brain_for_character())
    assert fly.stopped and main._fly_brain is None
    ws = FakeWS()
    asyncio.run(main.send_response(ws, "hi"))
    assert ws.jsons


def test_admin_memorial_and_shot_events_are_off_for_brain_characters(monkeypatch):
    # both endpoints send their audio raw (not through send_response), so the
    # chokepoint cannot catch them: they must refuse up front
    import main
    _brainy(monkeypatch, main)
    monkeypatch.setattr(main, "_active_ws", FakeWS())
    monkeypatch.setattr(main, "GAME_CONFIG", {})
    main.state_current["memorial_active"] = False
    assert asyncio.run(main.trigger_memorial({}))["status"] == "error"
    assert asyncio.run(main.trigger_shot_event("anything", {}))["status"] == "error"
    assert main.state_current["memorial_active"] is False


def test_api_brain(monkeypatch):
    import main
    _brainy(monkeypatch, main)
    assert asyncio.run(main.api_brain())["status"] == "ready"
    monkeypatch.setattr(main, "_character", SimpleNamespace(name="Ani", display_name="Ani", brain={}))
    assert asyncio.run(main.api_brain()) == {"enabled": False}
