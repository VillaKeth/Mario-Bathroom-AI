# tests/test_shot_events.py
import pytest
import time
from unittest.mock import AsyncMock, patch

def test_shot_event_creation():
    from server.shot_events import ShotEvent
    event = ShotEvent(
        name="test_event",
        tone="fun",
        trigger_type="admin",
        voice_keywords=["test"],
        phases=["announcement", "countdown", "toast", "recovery"],
        announcement_text="Test announcement!",
        toast_text="Test toast!",
        recovery_line="Back to party!",
        countdown=True,
        music_file=None,
        music_duration=0,
    )
    assert event.name == "test_event"
    assert event.fired is False
    assert event.countdown is True

def test_shot_event_manager_register():
    from server.shot_events import ShotEvent, ShotEventManager
    mgr = ShotEventManager()
    event = ShotEvent(name="test", tone="fun", trigger_type="admin",
                      voice_keywords=[], phases=["announcement"],
                      announcement_text="Hi!", toast_text="", recovery_line="")
    mgr.register(event)
    assert "test" in mgr.events

def test_shot_event_manager_trigger():
    from server.shot_events import ShotEvent, ShotEventManager
    mgr = ShotEventManager()
    event = ShotEvent(name="test", tone="fun", trigger_type="admin",
                      voice_keywords=[], phases=["announcement"],
                      announcement_text="Hi!", toast_text="", recovery_line="")
    mgr.register(event)
    result = mgr.trigger("test")
    assert result["status"] == "triggered"
    assert event.fired is True

def test_shot_event_double_fire_blocked():
    from server.shot_events import ShotEvent, ShotEventManager
    mgr = ShotEventManager()
    event = ShotEvent(name="test", tone="fun", trigger_type="admin",
                      voice_keywords=[], phases=["announcement"],
                      announcement_text="Hi!", toast_text="", recovery_line="")
    mgr.register(event)
    mgr.trigger("test")
    result = mgr.trigger("test")
    assert result["status"] == "already_fired"

def test_shot_event_reset():
    from server.shot_events import ShotEvent, ShotEventManager
    mgr = ShotEventManager()
    event = ShotEvent(name="test", tone="fun", trigger_type="admin",
                      voice_keywords=[], phases=["announcement"],
                      announcement_text="Hi!", toast_text="", recovery_line="")
    mgr.register(event)
    mgr.trigger("test")
    mgr.reset("test")
    assert event.fired is False

def test_voice_keyword_match():
    from server.shot_events import ShotEvent, ShotEventManager
    mgr = ShotEventManager()
    event = ShotEvent(name="lisa_memorial", tone="solemn", trigger_type="voice",
                      voice_keywords=["lisa", "aunt lisa", "lisa webb"],
                      phases=["announcement"],
                      announcement_text="Hi!", toast_text="", recovery_line="")
    mgr.register(event)
    match = mgr.check_voice_trigger("Has anyone seen Aunt Lisa?")
    assert match is not None
    assert match.name == "lisa_memorial"

def test_voice_keyword_no_match():
    from server.shot_events import ShotEvent, ShotEventManager
    mgr = ShotEventManager()
    event = ShotEvent(name="lisa_memorial", tone="solemn", trigger_type="voice",
                      voice_keywords=["lisa", "aunt lisa"],
                      phases=["announcement"],
                      announcement_text="Hi!", toast_text="", recovery_line="")
    mgr.register(event)
    match = mgr.check_voice_trigger("Where is the bathroom?")
    assert match is None

def test_list_events():
    from server.shot_events import ShotEvent, ShotEventManager
    mgr = ShotEventManager()
    for name in ["a", "b", "c"]:
        mgr.register(ShotEvent(name=name, tone="fun", trigger_type="admin",
                                voice_keywords=[], phases=["announcement"],
                                announcement_text="Hi!", toast_text="", recovery_line=""))
    events = mgr.list_events()
    assert len(events) == 3
    assert all(e["fired"] is False for e in events)

def test_countdown_texts():
    from server.shot_events import ShotEventManager
    mgr = ShotEventManager()
    texts = mgr.get_countdown_texts()
    assert len(texts) == 10
    assert "TEN-a!" in texts[0]
    assert "ONE-a!" in texts[9]

@pytest.mark.asyncio
async def test_precache_countdown_audio():
    from server.shot_events import ShotEventManager
    mgr = ShotEventManager()
    async def fake_tts(text):
        return b"audio_" + text.encode()
    await mgr.precache_countdown_audio(fake_tts)
    assert mgr.get_cached_countdown("TEN-a!") == b"audio_TEN-a!"
    assert mgr.get_cached_countdown("ONE-a!") == b"audio_ONE-a!"
    assert mgr.get_cached_countdown("NONEXISTENT") is None
