import yaml
import random
from server.joke_engine import load_curated_jokes, JokeEngine

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

def test_bag_exhausts_before_repeat():
    pool = [f"j{i}" for i in range(10)]
    eng = JokeEngine(pool, rng=random.Random(1))
    first10 = [eng._draw_from_bag() for _ in range(10)]
    assert sorted(first10) == sorted(pool)
    assert eng._draw_from_bag() in pool

def test_bag_empty_pool_returns_none():
    assert JokeEngine([], rng=random.Random(1))._draw_from_bag() is None

def test_next_joke_uses_llm_when_roll_hits():
    eng = JokeEngine(["cached"], llm_fn=lambda: "fresh-llm", llm_chance=1.0, rng=random.Random(1))
    assert eng.next_joke() == "fresh-llm"

def test_next_joke_uses_bag_when_roll_misses():
    eng = JokeEngine(["cached"], llm_fn=lambda: "fresh-llm", llm_chance=0.0, rng=random.Random(1))
    assert eng.next_joke() == "cached"

def test_next_joke_llm_failure_falls_back_to_bag():
    def boom(): raise RuntimeError("llm down")
    eng = JokeEngine(["cached"], llm_fn=boom, llm_chance=1.0, rng=random.Random(1))
    assert eng.next_joke() == "cached"

def test_next_joke_split_is_roughly_90_10():
    eng = JokeEngine(["c"], llm_fn=lambda: "L", llm_chance=0.10, rng=random.Random(7))
    draws = [eng.next_joke() for _ in range(2000)]
    assert 120 < draws.count("L") < 280
