"""End-to-end-ish gate checks using the pure helpers (no server.main import).
The single most important assertion: a clean character is unreachable by the
live dial."""
import yaml
from server.joke_engine import effective_freak_level, JokeEngine
from shared.character_loader import CharacterLoader


def _mk(tmp_path, name, extra="", freaky=None):
    d = tmp_path / name
    (d / "jokes").mkdir(parents=True)
    (d / "character.yaml").write_text(f"identity:\n  name: {name}\n{extra}", encoding="utf-8")
    if freaky:
        (d / "jokes" / "freaky.yaml").write_text(yaml.safe_dump(freaky), encoding="utf-8")
    return d


def test_clean_character_unreachable_by_dial(tmp_path):
    # Mario-like: freak_factor default 0, no freaky.yaml. Live dial cranked to 1.0.
    _mk(tmp_path, "mario", "")
    c = CharacterLoader(str(tmp_path), "mario")
    lvl = effective_freak_level(c.freak_factor, 1.0)      # config_live freak_factor = 1.0
    assert lvl == 0.0
    assert c.get_freak_prompt(lvl) == ""
    eng = JokeEngine(["clean"], freaky_pool={"bravado": ["B"], "explicit": ["E"]},
                     freak_level_fn=lambda: lvl)
    assert all(eng.next_joke() == "clean" for _ in range(30))


def test_rudi_reachable_and_scaled(tmp_path):
    _mk(tmp_path, "rudi", "personality:\n  freak_factor: 0.85\n",
        freaky={"bravado": ["B1", "B2"], "explicit": ["E1"]})
    c = CharacterLoader(str(tmp_path), "rudi")
    assert effective_freak_level(c.freak_factor, None) == 0.85     # yaml default
    assert effective_freak_level(c.freak_factor, 0.0) == 0.0       # party dialed him clean
    assert c.get_freak_prompt(0.85) != ""
