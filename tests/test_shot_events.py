# tests/test_shot_events.py
import pytest

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
    mgr.complete("test")  # must complete before reset (active events can't be reset)
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
    assert "Ten!" in texts[0]
    assert "One!" in texts[9]

@pytest.mark.asyncio
async def test_precache_countdown_audio():
    from server.shot_events import ShotEventManager
    mgr = ShotEventManager()
    async def fake_tts(text):
        return b"audio_" + text.encode()
    await mgr.precache_countdown_audio(fake_tts)
    assert mgr.get_cached_countdown("Ten!") == b"audio_Ten!"
    assert mgr.get_cached_countdown("One!") == b"audio_One!"
    assert mgr.get_cached_countdown("NONEXISTENT") is None

def test_complete_only_clears_matching_active():
    from server.shot_events import ShotEvent, ShotEventManager
    mgr = ShotEventManager()
    a = ShotEvent(name="a", tone="fun", trigger_type="admin",
                  voice_keywords=[], phases=["announcement"],
                  announcement_text="Hi!", toast_text="", recovery_line="")
    b = ShotEvent(name="b", tone="fun", trigger_type="admin",
                  voice_keywords=[], phases=["announcement"],
                  announcement_text="Hi!", toast_text="", recovery_line="")
    mgr.register(a)
    mgr.register(b)
    mgr.trigger("a")
    mgr.complete("a")
    # Now trigger b
    mgr.trigger("b")
    mgr.complete("a")  # completing a should NOT clear b
    assert mgr.is_active is True
    assert mgr.active_event.name == "b"

def test_reset_clears_active_state():
    from server.shot_events import ShotEvent, ShotEventManager
    mgr = ShotEventManager()
    event = ShotEvent(name="test", tone="fun", trigger_type="admin",
                      voice_keywords=[], phases=["announcement"],
                      announcement_text="Hi!", toast_text="", recovery_line="")
    mgr.register(event)
    mgr.trigger("test")
    assert mgr.is_active is True
    mgr.complete("test")  # must complete before reset
    mgr.reset("test")
    assert mgr.is_active is False
    assert event.fired is False

def test_trigger_blocked_by_active():
    from server.shot_events import ShotEvent, ShotEventManager
    mgr = ShotEventManager()
    a = ShotEvent(name="a", tone="fun", trigger_type="admin",
                  voice_keywords=[], phases=["announcement"],
                  announcement_text="Hi!", toast_text="", recovery_line="")
    b = ShotEvent(name="b", tone="fun", trigger_type="admin",
                  voice_keywords=[], phases=["announcement"],
                  announcement_text="Hi!", toast_text="", recovery_line="")
    mgr.register(a)
    mgr.register(b)
    mgr.trigger("a")
    result = mgr.trigger("b")
    assert result["status"] == "blocked_by_active"

def test_trigger_not_found():
    from server.shot_events import ShotEventManager
    mgr = ShotEventManager()
    result = mgr.trigger("nonexistent")
    assert result["status"] == "not_found"

def test_voice_keyword_no_substring_match():
    from server.shot_events import ShotEvent, ShotEventManager
    mgr = ShotEventManager()
    event = ShotEvent(name="lisa_memorial", tone="solemn", trigger_type="voice",
                      voice_keywords=["lisa"],
                      phases=["announcement"],
                      announcement_text="Hi!", toast_text="", recovery_line="")
    mgr.register(event)
    # "monalisa" should NOT match "lisa" keyword
    match = mgr.check_voice_trigger("I love the monalisa painting")
    assert match is None

def test_default_events_registered():
    from server.shot_events import create_default_events
    mgr = create_default_events()
    assert "lisa_webb_memorial" in mgr.events
    assert "birthday_boy" in mgr.events
    assert "deltarune" in mgr.events

def test_lisa_memorial_is_solemn():
    from server.shot_events import create_default_events
    mgr = create_default_events()
    lisa = mgr.events["lisa_webb_memorial"]
    assert lisa.tone == "solemn"
    assert "silence" in lisa.phases
    assert lisa.music_file is not None

def test_birthday_boy_is_celebratory():
    from server.shot_events import create_default_events
    mgr = create_default_events()
    bday = mgr.events["birthday_boy"]
    assert bday.tone == "solemn"
    assert "silence" in bday.phases

def test_deltarune_mentions_lancer():
    from server.shot_events import create_default_events
    mgr = create_default_events()
    dr = mgr.events["deltarune"]
    assert "Lancer" in dr.toast_text or "LANCER" in dr.toast_text
