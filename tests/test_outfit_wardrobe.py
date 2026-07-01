"""Client-side wardrobe behavior: an active outfit whose sprite set is only
partially generated must keep the character fully in-costume — a missing pose
falls back to the OUTFIT's fallback pose (e.g. tux idle), never to the default
(hoodie) set or to nothing.

MarioDisplay is instantiated with object.__new__ (no pygame) and only the
attributes the resolver reads are set — same approach as
test_mario_display_particles.py.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLIENT_DIR = ROOT / "client"
for _p in (ROOT, CLIENT_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from client.mario_display import MarioDisplay


def _display(sprite_keys, outfit_fallback=None):
    d = object.__new__(MarioDisplay)
    # Resolver only reads keys; give each a dummy surface stand-in.
    d._sprites = {k: object() for k in sprite_keys}
    d._outfit_fallback_key = outfit_fallback
    return d


def test_resolve_missing_pose_without_outfit_returns_none():
    # Guard: with no outfit active, an unresolvable pose still returns None.
    d = _display({"neutral/idle", "speech/talking"})
    assert d._resolve_pose_key("party/celebrate") is None


def test_resolve_missing_pose_falls_back_to_outfit_key():
    # Partial tux set: 'party/celebrate' not generated yet, no leaf/category
    # match -> resolve to the outfit fallback (tux idle), NOT None/hoodie.
    d = _display({"neutral/idle", "speech/talking"}, outfit_fallback="neutral/idle")
    assert d._resolve_pose_key("party/celebrate") == "neutral/idle"


def test_resolve_prefers_exact_match_over_outfit_fallback():
    d = _display({"neutral/idle", "positive/smirk"}, outfit_fallback="neutral/idle")
    assert d._resolve_pose_key("positive/smirk") == "positive/smirk"


def test_resolve_prefers_leaf_match_over_outfit_fallback():
    d = _display({"neutral/idle", "reactions/smirk"}, outfit_fallback="neutral/idle")
    # leaf 'smirk' matches reactions/smirk before the outfit fallback kicks in
    assert d._resolve_pose_key("positive/smirk") == "reactions/smirk"


def test_resolve_outfit_fallback_ignored_if_not_loaded():
    # Broken/empty outfit: the fallback key itself isn't loaded -> return None
    # (never hand back a key that isn't in _sprites).
    d = _display({"speech/talking"}, outfit_fallback="neutral/idle")
    assert d._resolve_pose_key("party/celebrate") is None
