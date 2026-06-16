"""Tests for HSR lore scraping (pure parse/chunk helpers) and the lore_knowledge
ingest/retrieve module."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import lore_knowledge          # noqa: E402
import scrape_hsr_lore as sc   # noqa: E402


# --- scraper: HTML -> clean paragraphs ---------------------------------------

def test_extract_paragraphs_keeps_prose_drops_noise():
    html = """
    <div>
      <table><tr><td>Infobox junk that is long enough to look like prose text</td></tr></table>
      <p>March 7th is a playable character in Honkai: Star Rail.<sup>[1]</sup></p>
      <p>short</p>
      <p>She was saved from eternal ice by the Astral Express Crew and wields Six-Phased Ice.</p>
    </div>"""
    paras = sc.extract_paragraphs(html)
    assert any("playable character in Honkai" in p for p in paras)
    assert any("Six-Phased Ice" in p for p in paras)
    assert all("Infobox junk" not in p for p in paras)   # table dropped
    assert all("[1]" not in p for p in paras)             # ref marker stripped
    assert "short" not in paras                            # too short, dropped


# --- scraper: paragraphs -> title-prefixed fact chunks -----------------------

def test_paragraphs_to_facts_prefixes_title_and_dedupes():
    paras = ["She loves photography.", "She loves photography."]  # duplicate
    facts = sc.paragraphs_to_facts("March 7th", paras)
    assert facts == ["March 7th: She loves photography."]


def test_paragraphs_to_facts_chunks_long_paragraphs_under_max_chars():
    para = ". ".join([f"Sentence number {i} about the world" for i in range(40)]) + "."
    facts = sc.paragraphs_to_facts("World", [para], max_chars=120)
    assert len(facts) > 1
    for f in facts:
        assert f.startswith("World: ")
        assert len(f) <= 120 + len("World: ") + 30   # chunk cap (+title +slack)


def test_paragraphs_to_facts_caps_fact_count():
    paras = [f"Fact sentence {i} that is reasonably long here." for i in range(100)]
    facts = sc.paragraphs_to_facts("X", paras, max_facts=10)
    assert len(facts) == 10


# --- lore_knowledge: ingest + relevance-gated retrieval ----------------------

def test_ingest_lore_facts_skips_blanks_and_counts(monkeypatch):
    stored = []
    monkeypatch.setattr(lore_knowledge.memory_semantic, "store_memory",
                        lambda pid, text, memory_type="fact": stored.append((pid, text, memory_type)))
    n = lore_knowledge.ingest_lore_facts(["a real fact about Kafka", "  ", "", "another fact"])
    assert n == 2
    assert all(pid == lore_knowledge.LORE_PERSON_ID for pid, _, _ in stored)
    assert all(mt == "hsr_lore" for _, _, mt in stored)


def test_get_lore_for_prompt_queries_lore_namespace_and_returns_texts(monkeypatch):
    captured = {}
    def fake_search(query, person_id=None, limit=20, score_threshold=0.25):
        captured.update(query=query, person_id=person_id, limit=limit, score_threshold=score_threshold)
        return [{"text": "March 7th: wields Six-Phased Ice", "score": 0.6}]
    monkeypatch.setattr(lore_knowledge.memory_semantic, "search_memories", fake_search)
    out = lore_knowledge.get_lore_for_prompt("tell me about march's ice powers", top_k=5)
    assert out == ["March 7th: wields Six-Phased Ice"]
    assert captured["person_id"] == lore_knowledge.LORE_PERSON_ID
    assert captured["limit"] == 5
    assert captured["score_threshold"] == lore_knowledge.LORE_MIN_SCORE


def test_get_lore_for_prompt_empty_query_returns_empty():
    assert lore_knowledge.get_lore_for_prompt("") == []
    assert lore_knowledge.get_lore_for_prompt("ab") == []


def test_load_lore_file_reads_yaml_list(tmp_path, monkeypatch):
    stored = []
    monkeypatch.setattr(lore_knowledge.memory_semantic, "store_memory",
                        lambda pid, text, memory_type="fact": stored.append(text))
    f = tmp_path / "hsr_lore.yaml"
    f.write_text("- 'March 7th: loves photography'\n- 'Kafka: a Stellaron Hunter'\n", encoding="utf-8")
    n = lore_knowledge.load_lore_file(str(f))
    assert n == 2
    assert "Kafka: a Stellaron Hunter" in stored


def test_load_lore_file_missing_is_noop():
    assert lore_knowledge.load_lore_file("/no/such/file.yaml") == 0
