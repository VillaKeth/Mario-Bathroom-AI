import yaml
from server.joke_engine import load_curated_jokes

def test_load_curated_prefers_curated_file(tmp_path):
    cdir = tmp_path / "rudi"; (cdir / "jokes").mkdir(parents=True)
    (cdir / "jokes" / "curated.yaml").write_text(
        yaml.safe_dump({"jokes": ["a", "b", "c"]}), encoding="utf-8")
    assert load_curated_jokes(str(cdir), fallback=["old"]) == ["a", "b", "c"]

def test_load_curated_falls_back_when_missing(tmp_path):
    cdir = tmp_path / "rudi"; cdir.mkdir()
    assert load_curated_jokes(str(cdir), fallback=["old1", "old2"]) == ["old1", "old2"]

def test_load_curated_falls_back_when_empty(tmp_path):
    cdir = tmp_path / "rudi"; (cdir / "jokes").mkdir(parents=True)
    (cdir / "jokes" / "curated.yaml").write_text(yaml.safe_dump({"jokes": []}), encoding="utf-8")
    assert load_curated_jokes(str(cdir), fallback=["old"]) == ["old"]
