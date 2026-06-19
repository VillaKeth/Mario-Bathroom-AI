"""World-lore knowledge (e.g. Honkai: Star Rail) for the active character.

Lore facts are ingested into the character's existing Qdrant memory collection
under a single fixed LORE_PERSON_ID. That keeps them character-scoped (each
character has its own collection) but speaker-INDEPENDENT: they surface based on
what the guest is talking about, not who the guest is. Retrieval is relevance-
gated so off-topic party chatter never pulls lore in.

Ingestion source is a YAML file of fact strings (produced offline by
scripts/scrape_hsr_lore.py), loaded at server startup like VIP profiles — so the
running server (which holds the single-process Qdrant lock) does the embedding.
"""
import os

import memory_semantic

DEBUG_LORE = True

# Fixed, unlikely-to-collide id namespace for world lore.
LORE_PERSON_ID = -987654321

# Relevance gate: a hit below this cosine score is off-topic — don't inject.
LORE_MIN_SCORE = 0.35
LORE_TOP_K = 5


def ingest_lore_facts(facts) -> int:
    """Embed + store each fact under LORE_PERSON_ID. Idempotent (Qdrant dedupes
    by deterministic id). Returns the number of facts attempted."""
    n = new = 0
    for fact in facts or []:
        fact = (fact or "").strip()
        if len(fact) < 3:
            continue
        try:
            if memory_semantic.store_memory(LORE_PERSON_ID, fact, memory_type="hsr_lore"):
                new += 1
            n += 1
        except Exception as e:
            if DEBUG_LORE:
                print(f"[lore] store failed: {e}")
    if DEBUG_LORE and n:
        # One summary line instead of a per-fact "duplicate skipped" spam at boot.
        print(f"[lore] ingested {n} facts ({new} new, {n - new} already present)")
    return n


def load_lore_file(path: str) -> int:
    """Load a YAML list of fact strings and ingest them. Returns count ingested.
    Missing/empty file is a no-op (returns 0)."""
    if not path or not os.path.exists(path):
        return 0
    import yaml
    try:
        with open(path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except Exception as e:
        if DEBUG_LORE:
            print(f"[lore] failed to read {path}: {e}")
        return 0
    if isinstance(data, dict):
        facts = data.get("facts", [])
    else:
        facts = data or []
    return ingest_lore_facts(facts)


def get_lore_for_prompt(query: str, top_k: int = LORE_TOP_K,
                        min_score: float = LORE_MIN_SCORE) -> list:
    """Return up to top_k lore facts relevant to `query`, or [] if none clear the
    relevance gate. Safe: never raises into the response pipeline."""
    if not query or len(query.strip()) < 3:
        return []
    try:
        hits = memory_semantic.search_memories(
            query, person_id=LORE_PERSON_ID, limit=top_k, score_threshold=min_score
        )
    except Exception as e:
        if DEBUG_LORE:
            print(f"[lore] search failed: {e}")
        return []
    return [h["text"] for h in hits if h.get("text")]
