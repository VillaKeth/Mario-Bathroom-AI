import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "client"))

# Headless pygame so full MarioDisplay(...) construction works without a display.
# Set before any `import mario_display` so pygame picks up the dummy drivers.
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")


def test_chat_overlay_max_constructor():
    """The actual Task 7 change: the chat_overlay_max kwarg drives _MAX_CHAT_HISTORY.

    RED on pre-Task-7 code: MarioDisplay had no chat_overlay_max param, so
    MarioDisplay(chat_overlay_max=5) raises TypeError. GREEN after the change:
    it constructs and the cap equals the passed value (default 40 when omitted).
    """
    import mario_display
    d = mario_display.MarioDisplay(chat_overlay_max=5)
    assert d._MAX_CHAT_HISTORY == 5
    d2 = mario_display.MarioDisplay()
    assert d2._MAX_CHAT_HISTORY == 40  # default when omitted


def test_chat_history_capped(monkeypatch):
    # Regression guard for add_chat_message's pop-oldest trim. Uses __new__ to
    # bypass pygame init and exercises the trim independent of the constructor.
    import mario_display
    d = mario_display.MarioDisplay.__new__(mario_display.MarioDisplay)
    d._chat_history = []
    d._MAX_CHAT_HISTORY = 40
    for i in range(100):
        d.add_chat_message("user", f"msg {i}")
    assert len(d._chat_history) == 40
    assert d._chat_history[-1]["text"] == "msg 99"  # newest kept
