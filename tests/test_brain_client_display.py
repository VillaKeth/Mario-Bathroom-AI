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
    md.MarioDisplay._draw_brain_panel(fake)
    assert fake._screen.get_at((20, 70))[:3] != (0, 0, 0)  # panel painted
    blank = pygame.Surface((md.WINDOW_WIDTH, md.WINDOW_HEIGHT))
    fake._screen, fake._brain_visible = blank, False
    md.MarioDisplay._draw_brain_panel(fake)
    assert blank.get_at((20, 70))[:3] == (0, 0, 0)


def test_panel_loading_state_draws():
    import pygame
    pygame.init()
    import mario_display as md
    d = {"status": "loading", "stage": "fetch", "progress": 0.4, "dataset": {}, "rows": []}
    fake = SimpleNamespace(_brain_state=d, _brain_visible=True, _banner_bottom=48,
                           _font_small=pygame.font.SysFont("arial", 13),
                           _screen=pygame.Surface((md.WINDOW_WIDTH, md.WINDOW_HEIGHT)))
    md.MarioDisplay._draw_brain_panel(fake)
