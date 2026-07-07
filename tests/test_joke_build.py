import json
from scripts.jokes.sources import write_candidate, candidate_id
from scripts.jokes.judge_jokes import select_top

def test_write_candidate_dedups_by_hash(tmp_path):
    fp_path = tmp_path / "cand.jsonl"; seen = set()
    with open(fp_path, "a", encoding="utf-8") as f:
        assert write_candidate(f, "same joke", "claude", seen) is True
        assert write_candidate(f, "same joke", "ollama", seen) is False
    lines = [json.loads(x) for x in open(fp_path, encoding="utf-8")]
    assert len(lines) == 1 and lines[0]["source"] == "claude"

def test_candidate_id_stable():
    assert candidate_id("abc") == candidate_id("abc")

def test_select_top_ranks_and_caps_long():
    scored = [
        {"text": "short A", "funny": 9, "rudi_fit": 9, "tts_ok": True},
        {"text": "short B", "funny": 2, "rudi_fit": 2, "tts_ok": True},
        {"text": "x"*250,   "funny": 10, "rudi_fit": 10, "tts_ok": True},
        {"text": "bad tts", "funny": 10, "rudi_fit": 10, "tts_ok": False},
    ]
    top = select_top(scored, n=2, long_cap=0.5)
    assert "bad tts" not in top
    assert "short A" in top
    assert len(top) == 2
