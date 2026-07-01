import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "client"))


def test_chat_history_capped(monkeypatch):
    # Headless pygame so import/construct works without a display.
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    import mario_display
    d = mario_display.MarioDisplay.__new__(mario_display.MarioDisplay)
    d._chat_history = []
    d._MAX_CHAT_HISTORY = 40
    for i in range(100):
        d.add_chat_message("user", f"msg {i}")
    assert len(d._chat_history) == 40
    assert d._chat_history[-1]["text"] == "msg 99"  # newest kept
