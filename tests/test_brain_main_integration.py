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
    monkeypatch.setitem(main.state_current, "_brain_last_arrival", 0.0)
    return fly


def _keep_state(monkeypatch, main, *keys):
    """Let a test mutate these state_current keys; monkeypatch restores them."""
    for k in keys:
        monkeypatch.setitem(main.state_current, k, main.state_current.get(k))


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


def test_arrivals_within_a_minute_are_one_reaction(monkeypatch):
    # the camera re-sends a face greeting on every detection of an unknown
    # face; each one was a loom window (an ESCAPE buzz), back to back
    import main
    fly = _brainy(monkeypatch, main)
    ws = FakeWS()
    for _ in range(3):
        asyncio.run(main._generate_and_send_response(ws, "Hey there!", source="face_greeting"))
    assert fly.calls == [("event", "arrival")]
    main.state_current["_brain_last_arrival"] -= 61.0
    asyncio.run(main._generate_and_send_response(ws, "Hey there!", source="face_greeting"))
    assert fly.calls == [("event", "arrival")] * 2


def test_text_input_shows_no_thinking_for_brain_character(monkeypatch):
    # "thinking" makes the client print "Hmm, let me think..." in the fly's
    # bubble (English outside its vocabulary) and run a 60 s spinner, and a
    # silent fly (NOTHING) never sends the reply that would clear it
    import main
    _brainy(monkeypatch, main, FakeFly(_reply("NOTHING", "", b"")))
    monkeypatch.setattr(main, "_reply_paused", lambda: False)
    _keep_state(monkeypatch, main, "_last_text_input_time", "_last_user_msg_time",
                "_user_request_active", "speaker_name", "detected_guest")
    main.state_current.update(_last_text_input_time=0.0, speaker_name=None, detected_guest=None)
    ws = FakeWS()
    asyncio.run(main._handle_text_input(ws, "hello"))
    assert [j["type"] for j in ws.jsons] == ["brain_state"]


def test_voice_input_shows_no_thinking_for_brain_character(monkeypatch):
    import main
    _brainy(monkeypatch, main, FakeFly(_reply("NOTHING", "", b"")))
    monkeypatch.setattr(main.stt, "transcribe", lambda b: "hello there")
    monkeypatch.setattr(main.speaker_id, "identify_speaker", lambda b: {
        "name": None, "speaker_id": None, "confidence": 0.0, "is_new": True})
    monkeypatch.setattr(main.audio_distress, "is_available", lambda: False)

    async def no_log(*a, **k):
        return None
    monkeypatch.setattr(main, "_log_guest_turn", no_log)
    _keep_state(monkeypatch, main, "_detected_mood", "_last_user_msg_time",
                "_last_voice_result", "speaker_name", "speaker_id")
    main.state_current["_detected_mood"] = None
    ws = FakeWS()
    asyncio.run(main._process_audio(ws, b"\x00" * 32000))
    assert [j["type"] for j in ws.jsons] == ["brain_state"]


def test_presence_enter_is_one_arrival_without_the_greeting_flow(monkeypatch):
    # the Mario greeting ran gossip reads/writes, the LLM and TTS inline in the
    # receive loop (deaf for up to 60 s) for words the chokepoint then dropped;
    # spec 4.1: a person arriving is a loom stimulus for the brain
    import main
    fly = _brainy(monkeypatch, main)
    greetings, visits = [], []

    async def greeting(*a, **k):
        greetings.append(1)
    monkeypatch.setattr(main, "_do_greeting", greeting)
    monkeypatch.setattr(main.party_stats, "record_enter", lambda **k: visits.append(k) or 42)
    monkeypatch.setattr(main.party_stats, "record_event", lambda *a, **k: None)
    _keep_state(monkeypatch, main, "presence_phase", "presence", "conversation_history",
                "enter_time", "current_visit_id", "_greeting_in_progress")
    main.state_current["presence_phase"] = "IDLE"
    ws = FakeWS()
    asyncio.run(main.handle_event(ws, {"type": "presence_enter"}))
    assert greetings == []
    assert fly.calls == [("event", "arrival")]
    assert len(visits) == 1 and main.state_current["current_visit_id"] == 42  # spec 5.2 keeps visit counting
    assert main.state_current["presence"] is True
    assert main.state_current["presence_phase"] == "CONVERSING"
    # the face the camera sees next is the same arrival
    asyncio.run(main._generate_and_send_response(ws, "Hey there!", source="face_greeting"))
    assert fly.calls == [("event", "arrival")]


def test_presence_exit_runs_no_farewell_flow_for_brain_character(monkeypatch):
    import main
    fly = _brainy(monkeypatch, main)
    calls, exits = [], []

    async def llm_reply(*a, **k):
        calls.append("llm")
        return "Ciao!"
    monkeypatch.setattr(main.llm, "generate_response", llm_reply)
    monkeypatch.setattr(main.tts, "synthesize", lambda *a, **k: calls.append("tts") or b"")
    monkeypatch.setattr(main.party_gossip, "add_dramatic_moment", lambda *a, **k: calls.append("gossip"))
    monkeypatch.setattr(main.memory, "save_emotion", lambda *a, **k: calls.append("memory"))
    monkeypatch.setattr(main.party_stats, "record_exit", exits.append)
    monkeypatch.setattr(main.party_stats, "record_event", lambda *a, **k: None)
    _keep_state(monkeypatch, main, "presence_phase", "presence", "current_visit_id",
                "speaker_id", "speaker_name", "_greeting_in_progress", "_active_game",
                "_game_state", "conversation_history", "enter_time", "_name_from_parsing",
                "_last_face_encoding", "_last_face_encoding_ts")
    main.state_current.update(presence_phase="CONVERSING", presence=True, current_visit_id=7,
                              speaker_id=None, speaker_name=None, _greeting_in_progress=False,
                              _active_game=None, conversation_history=[])
    asyncio.run(main.handle_event(FakeWS(), {"type": "presence_exit"}))
    assert calls == []
    assert exits == [7]  # spec 5.2 keeps visit counting
    assert fly.calls == []  # spec 4.1 has no stimulus for someone leaving
    assert main.state_current["presence"] is False
    assert main.state_current["presence_phase"] == "IDLE"


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
