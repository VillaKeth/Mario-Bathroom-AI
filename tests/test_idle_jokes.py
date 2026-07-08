import yaml

from server.idle_behavior import IdleBehavior

class _Loader:
    name = "Rudi"
    _char_dir = None
    def __init__(self, jokes): self._j = jokes
    def get_idle_messages(self): return {"jokes": self._j}

class _LoaderWithCharacterDir:
    """Mimics the real CharacterLoader's PUBLIC `character_dir` attribute
    (not the private `_char_dir`) to guard against regressing to the old
    fragile getattr order."""
    name = "Rudi"
    def __init__(self, character_dir, jokes=None):
        self.character_dir = character_dir
        self._j = jokes or []
    def get_idle_messages(self): return {"jokes": self._j}

def test_get_joke_delegates_to_engine_bag():
    ib = IdleBehavior(_Loader(["j1", "j2"]), joke_llm_chance=0.0)
    got = {ib.get_joke() for _ in range(20)}
    assert got == {"j1", "j2"}

def test_get_joke_empty_pool_returns_none():
    ib = IdleBehavior(_Loader([]), joke_llm_chance=0.0)
    assert ib.get_joke() is None

def test_joke_llm_fn_wired():
    calls = {"n": 0}
    def fake_llm(): calls["n"] += 1; return "generated joke"
    ib = IdleBehavior(_Loader(["c"]), joke_llm_fn=fake_llm, joke_llm_chance=1.0)
    assert ib.get_joke() == "generated joke"
    assert calls["n"] == 1

def test_get_joke_uses_curated_file_via_public_character_dir(tmp_path):
    (tmp_path / "jokes").mkdir()
    (tmp_path / "jokes" / "curated.yaml").write_text(
        yaml.safe_dump({"jokes": ["curated1", "curated2"]}), encoding="utf-8")
    ib = IdleBehavior(_LoaderWithCharacterDir(str(tmp_path), jokes=["fallback"]), joke_llm_chance=0.0)
    got = {ib.get_joke() for _ in range(20)}
    assert got == {"curated1", "curated2"}

def test_idle_routes_freaky_when_level_high(tmp_path):
    (tmp_path / "jokes").mkdir()
    (tmp_path / "jokes" / "freaky.yaml").write_text(
        yaml.safe_dump({"bravado": ["BRAV1", "BRAV2"], "explicit": ["EXPL1"]}), encoding="utf-8")
    ib = IdleBehavior(_LoaderWithCharacterDir(str(tmp_path), jokes=["CLEAN1", "CLEAN2"]),
                      joke_llm_chance=0.0, freak_level_fn=lambda: 1.0, explicit_ratio=0.5)
    got = [ib.get_joke() for _ in range(40)]
    assert any(g in ("BRAV1", "BRAV2", "EXPL1") for g in got)
    assert "CLEAN1" not in got and "CLEAN2" not in got  # level 1.0 -> all freaky

def test_idle_clean_when_no_level_fn(tmp_path):
    (tmp_path / "jokes").mkdir()
    (tmp_path / "jokes" / "freaky.yaml").write_text(
        yaml.safe_dump({"bravado": ["BRAV1"], "explicit": ["EXPL1"]}), encoding="utf-8")
    ib = IdleBehavior(_LoaderWithCharacterDir(str(tmp_path), jokes=["CLEAN1", "CLEAN2"]),
                      joke_llm_chance=0.0)  # no freak_level_fn -> level 0
    got = [ib.get_joke() for _ in range(40)]
    assert all(g in ("CLEAN1", "CLEAN2") for g in got)
