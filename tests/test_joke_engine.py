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


from server.joke_engine import load_freaky_jokes, effective_freak_level

def test_load_freaky_missing_returns_empty(tmp_path):
    d = tmp_path / "mario"; d.mkdir()
    fp = load_freaky_jokes(str(d))
    assert fp == {"bravado": [], "explicit": []}

def test_load_freaky_reads_both_lanes(tmp_path):
    d = tmp_path / "rudi"; (d / "jokes").mkdir(parents=True)
    (d / "jokes" / "freaky.yaml").write_text(
        yaml.safe_dump({"bravado": ["b1", "b2"], "explicit": ["e1"]}), encoding="utf-8")
    fp = load_freaky_jokes(str(d))
    assert fp["bravado"] == ["b1", "b2"] and fp["explicit"] == ["e1"]

def test_effective_level_zero_when_opt_out():
    assert effective_freak_level(0.0, 1.0) == 0.0      # clean char, dial cranked -> still 0
    assert effective_freak_level(0.0, None) == 0.0

def test_effective_level_scales_opted_in():
    assert effective_freak_level(0.85, None) == 0.85   # no override -> yaml default
    assert effective_freak_level(0.85, 0.3) == 0.3     # live override scales it
    assert effective_freak_level(0.85, "junk") == 0.85 # bad override -> default
    assert effective_freak_level(0.85, 5) == 1.0       # clamp

def test_no_freaky_pool_draws_only_clean():
    eng = JokeEngine(["c1", "c2"], freak_level_fn=lambda: 1.0, rng=random.Random(1))
    assert all(eng.next_joke() in ("c1", "c2") for _ in range(50))

def test_level_one_draws_only_freaky():
    fp = {"bravado": ["b1", "b2"], "explicit": ["e1", "e2"]}
    eng = JokeEngine(["c1"], freaky_pool=fp, freak_level_fn=lambda: 1.0,
                     explicit_ratio=0.5, rng=random.Random(3))
    got = [eng.next_joke() for _ in range(60)]
    assert "c1" not in got
    assert any(g in ("b1", "b2") for g in got)
    assert any(g in ("e1", "e2") for g in got)

def test_level_fn_exception_is_clean():
    def boom(): raise RuntimeError("x")
    fp = {"bravado": ["b1"], "explicit": ["e1"]}
    eng = JokeEngine(["c1"], freaky_pool=fp, freak_level_fn=boom, rng=random.Random(1))
    assert all(eng.next_joke() == "c1" for _ in range(20))

def test_draw_from_bag_still_clean_only():
    eng = JokeEngine(["c1", "c2"], freaky_pool={"bravado": ["b"], "explicit": ["e"]},
                     rng=random.Random(1))
    assert all(eng._draw_from_bag() in ("c1", "c2") for _ in range(20))
