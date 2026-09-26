import json
import os
import sys
from types import SimpleNamespace

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "client"))

PANEL = {"type": "brain_state", "status": "ready", "stage": "", "progress": 1.0,
         "dataset": {"name": "MaleCNS v1.0", "neurons": 166700, "connections": 25582938},
         "rows": [{"pop": "sugar", "label": "SWEET", "kind": "sense"},
                  {"pop": "feed", "label": "FEED", "kind": "readout"}],
         "rates": {"sugar": 150.0, "feed": 249.0}, "bins": {"sugar": [150.0] * 10, "feed": [240.0] * 10},
         "spikes": 368532, "active": 10508, "sim_ms": 500.0, "wall_ms": 900.0,
         "behavior": "FEED", "direction": "", "pose_hint": "positive/feeding", "emotion": "happy",
         "credit": "Connectome: MaleCNS v1.0, Janelia FlyEM et al., CC BY 4.0"}


def _load_client_main(monkeypatch):
    """client/main.py under a private module name with its hardware imports
    stubbed (as test_pygame_client_controls does). A bare `import main` here
    would shadow server/main.py for the server tests collected after this file,
    and so would client/main.py's own sys.path.insert(0, CLIENT_DIR): the
    sys.path copy below is restored when the test ends."""
    import importlib.util
    import types

    monkeypatch.setattr(sys, "path", list(sys.path))

    class Stub:
        def __init__(self, *a, **k):
            pass
    stubs = {n: types.ModuleType(n) for n in ("audio_capture", "audio_playback", "presence",
                                              "mario_display", "ws_client", "sound_effects")}
    stubs["audio_capture"].AudioCapture = Stub
    stubs["audio_playback"].AudioPlayback = Stub
    stubs["audio_playback"].wav_duration_s = lambda wav: 0.0
    stubs["presence"].PresenceDetector = Stub
    stubs["mario_display"].MarioDisplay = Stub
    for st in ("idle", "talking", "listening", "thinking", "greeting", "entering", "exiting"):
        setattr(stubs["mario_display"], "STATE_" + st.upper(), st)
    stubs["ws_client"].MarioWSClient = Stub
    stubs["sound_effects"].SoundEffects = Stub
    for name, mod in stubs.items():
        monkeypatch.setitem(sys.modules, name, mod)
    name = "client_main_for_brain_tests"
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(os.path.dirname(__file__), "..", "client", "main.py"))
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, module)
    spec.loader.exec_module(module)
    return module


def test_brain_state_ends_the_thinking_indicator(monkeypatch):
    # sending a line (keyboard or voice) shows "thinking" until a reply
    # arrives; for the fly the brain window IS the reply, often a silent one
    # (NOTHING) that sends no mario_response to clear it
    module = _load_client_main(monkeypatch)
    display = SimpleNamespace(state="listening", thinking=[], set_brain_state=lambda d: None,
                              set_pose_hint=lambda p: None, set_emotion=lambda e: None)
    display.set_thinking = display.thinking.append
    display.set_state = lambda s: setattr(display, "state", s)
    client = object.__new__(module.MarioClient)
    client.display = display
    module.MarioClient._on_brain_state(client, dict(PANEL, behavior="NOTHING", pose_hint="neutral/idle"))
    assert display.thinking == [False]
    assert display.state == "idle"


def test_ws_client_routes_brain_state():
    from ws_client import MarioWSClient
    c = MarioWSClient("ws://x/ws")
    got = []
    c.on_brain_state = got.append
    c._on_message(None, json.dumps(PANEL))
    assert got and got[0]["behavior"] == "FEED"


def test_panel_draws_without_error_and_toggles_off():
    import pygame
    pygame.init()
    import mario_display as md
    fake = SimpleNamespace(_brain_state=dict(PANEL), _brain_visible=True, _banner_bottom=48,
                           _font_small=pygame.font.SysFont("arial", 13),
                           _screen=pygame.Surface((md.WINDOW_WIDTH, md.WINDOW_HEIGHT)))
    fake._brain_panel_layout = md.MarioDisplay._brain_panel_layout
    md.MarioDisplay._draw_brain_panel(fake)
    assert fake._screen.get_at((20, 100))[:3] != (0, 0, 0)  # panel painted
    blank = pygame.Surface((md.WINDOW_WIDTH, md.WINDOW_HEIGHT))
    fake._screen, fake._brain_visible = blank, False
    md.MarioDisplay._draw_brain_panel(fake)
    assert blank.get_at((20, 100))[:3] == (0, 0, 0)


def test_panel_layout_fits_the_display_font():
    # the live client draws with pygame.font.Font(None, 22), wider than the
    # fakes' arial 13: every line must fit and labels must clear the bars
    import pygame
    pygame.init()
    import mario_display as md
    labels = ["SWEET", "BITTER", "EARS", "ANTENNA", "LOOM", "FEED", "GROOM",
              "ESCAPE", "STARTLE", "WALK", "BACK"]
    d = dict(PANEL, spikes=1238739, active=19430, wall_ms=1290.0,
             rows=[{"pop": lb.lower(), "label": lb, "kind": "sense"} for lb in labels])
    font = pygame.font.Font(None, 22)
    lay = md.MarioDisplay._brain_panel_layout(font, d)
    inner = lay["panel_w"] - 2 * lay["pad"]
    for line in lay["header"] + lay["footer"] + lay["credit"]:
        assert font.size(line)[0] <= inner, line
    assert lay["bar_x"] >= lay["pad"] + max(font.size(lb)[0] for lb in labels) + 4
    assert lay["num_x"] + font.size("400")[0] <= lay["panel_w"] - lay["pad"]


def test_panel_loading_state_draws():
    import pygame
    pygame.init()
    import mario_display as md
    d = {"status": "loading", "stage": "fetch", "progress": 0.4, "dataset": {}, "rows": []}
    fake = SimpleNamespace(_brain_state=d, _brain_visible=True, _banner_bottom=48,
                           _font_small=pygame.font.SysFont("arial", 13),
                           _screen=pygame.Surface((md.WINDOW_WIDTH, md.WINDOW_HEIGHT)),
                           _brain_panel_layout=md.MarioDisplay._brain_panel_layout)
    md.MarioDisplay._draw_brain_panel(fake)
