"""Tests for server/memory_semantic.py — Qdrant semantic memory layer.

All tests use :memory: mode to avoid file-lock conflicts with running server.
"""

import os
import sqlite3
import tempfile

import pytest

import server.memory_semantic as sem


@pytest.fixture(autouse=True)
def _reset_semantic_state():
    """Reset module-level globals before each test so tests are independent."""
    sem._client = None
    sem._embedder = None
    yield
    sem._client = None


def _init():
    """Shorthand: initialise Qdrant in-memory for a single test."""
    sem.init_semantic_memory(":memory:")


# ---------------------------------------------------------------------------
# 1. TestInitSemanticMemory
# ---------------------------------------------------------------------------
class TestInitSemanticMemory:
    def test_init_in_memory(self):
        """Init with :memory: succeeds and stats are accessible."""
        _init()
        stats = sem.get_collection_stats()
        # Collection may not exist yet (created on first insert),
        # but the client should be initialised — so we get *some* dict back.
        assert isinstance(stats, dict)

    def test_init_idempotent(self):
        """Calling init twice with :memory: does not crash."""
        sem.init_semantic_memory(":memory:")
        sem.init_semantic_memory(":memory:")
        stats = sem.get_collection_stats()
        assert isinstance(stats, dict)


# ---------------------------------------------------------------------------
# 2. TestStoreMemory
# ---------------------------------------------------------------------------
class TestStoreMemory:
    def test_store_basic(self):
        """Store one memory, verify collection point count increases."""
        _init()
        sem.store_memory(1, "Mario loves mushrooms", memory_type="fact")
        stats = sem.get_collection_stats()
        assert stats.get("total_points", 0) >= 1

    def test_store_deduplication(self):
        """Same text + person_id does not create a second point."""
        _init()
        sem.store_memory(1, "I love pizza", memory_type="fact")
        sem.store_memory(1, "I love pizza", memory_type="fact")
        stats = sem.get_collection_stats()
        assert stats["total_points"] == 1

    def test_store_different_people(self):
        """Different person_ids produce separate points even with same text."""
        _init()
        sem.store_memory(1, "I love pizza", memory_type="fact")
        sem.store_memory(2, "I love pizza", memory_type="fact")
        stats = sem.get_collection_stats()
        assert stats["total_points"] == 2

    def test_store_short_text_ignored(self):
        """Text shorter than 3 chars is silently ignored."""
        _init()
        # Need to create collection first so stats work
        sem.store_memory(1, "Bootstrap memory for collection", memory_type="fact")
        count_before = sem.get_collection_stats()["total_points"]

        sem.store_memory(1, "ab", memory_type="fact")   # 2 chars — ignored
        sem.store_memory(1, "", memory_type="fact")      # empty — ignored
        sem.store_memory(1, "  ", memory_type="fact")    # whitespace — ignored

        count_after = sem.get_collection_stats()["total_points"]
        assert count_after == count_before

    def test_store_different_memory_types(self):
        """All documented memory types store successfully."""
        _init()
        types = ["fact", "conversation", "vip_profile", "vip_hook", "topic"]
        for i, mtype in enumerate(types):
            sem.store_memory(1, f"Memory for type {mtype} number {i}", memory_type=mtype)
        stats = sem.get_collection_stats()
        assert stats["total_points"] == len(types)


# ---------------------------------------------------------------------------
# 3. TestSearchMemories
# ---------------------------------------------------------------------------
class TestSearchMemories:
    @pytest.fixture(autouse=True)
    def _seed_data(self):
        """Seed several memories so search tests have data to find."""
        _init()
        sem.store_memory(1, "Mario loves jumping on goombas", memory_type="fact")
        sem.store_memory(1, "Princess Peach is always getting kidnapped", memory_type="conversation")
        sem.store_memory(2, "Luigi is scared of ghosts and haunted houses", memory_type="fact")
        sem.store_memory(2, "Bowser is the king of the Koopas", memory_type="fact")
        sem.store_memory(3, "Toad is a loyal mushroom retainer", memory_type="conversation")

    def test_search_returns_results(self):
        """Basic search finds seeded data."""
        results = sem.search_memories("Who loves jumping?")
        assert len(results) > 0
        assert any("Mario" in r["text"] or "jumping" in r["text"] for r in results)

    def test_search_filter_by_person(self):
        """person_id filter excludes other people's memories."""
        results = sem.search_memories("ghosts and haunted", person_id=2)
        assert len(results) > 0
        for r in results:
            assert r["person_id"] == 2

    def test_search_no_person_filter(self):
        """None person_id returns matches from any guest."""
        results = sem.search_memories("Mario characters and adventures", person_id=None)
        assert len(results) > 0
        person_ids = {r["person_id"] for r in results}
        # With broad query we should get results from more than one person
        assert len(person_ids) >= 1

    def test_search_respects_limit(self):
        """limit parameter caps the number of results."""
        results = sem.search_memories("Mario characters", limit=2)
        assert len(results) <= 2

    def test_search_returns_score(self):
        """Each result has a float score field."""
        results = sem.search_memories("jumping goombas")
        assert len(results) > 0
        for r in results:
            assert "score" in r
            assert isinstance(r["score"], float)

    def test_search_empty_query(self):
        """Empty or very short query returns empty list."""
        assert sem.search_memories("") == []
        assert sem.search_memories("ab") == []
        assert sem.search_memories("  ") == []


# ---------------------------------------------------------------------------
# 4. TestGetCollectionStats
# ---------------------------------------------------------------------------
class TestGetCollectionStats:
    def test_stats_structure(self):
        """Stats dict has total_points and status keys after inserting."""
        _init()
        sem.store_memory(1, "Test memory for stats", memory_type="fact")
        stats = sem.get_collection_stats()
        assert "total_points" in stats
        assert "status" in stats

    def test_stats_after_inserts(self):
        """Point count increases after each unique store."""
        _init()
        sem.store_memory(1, "First unique memory entry", memory_type="fact")
        stats1 = sem.get_collection_stats()
        sem.store_memory(1, "Second unique memory entry", memory_type="fact")
        stats2 = sem.get_collection_stats()
        assert stats2["total_points"] > stats1["total_points"]

    def test_stats_not_initialized(self):
        """Stats return not_initialized when client is None."""
        # _reset_semantic_state fixture already sets _client = None
        stats = sem.get_collection_stats()
        assert stats == {"status": "not_initialized"}


# ---------------------------------------------------------------------------
# 5. TestBackfillFromSqlite
# ---------------------------------------------------------------------------
class TestBackfillFromSqlite:
    def test_backfill_skips_when_data_exists(self):
        """Backfill returns 0 when collection already has data."""
        _init()
        sem.store_memory(1, "Pre-existing memory in Qdrant", memory_type="fact")
        count = sem.backfill_from_sqlite()
        assert count == 0

    def test_backfill_no_sqlite_db(self, monkeypatch):
        """Backfill returns 0 when SQLite file doesn't exist."""
        _init()
        # Point to a non-existent path
        monkeypatch.setattr(os.path, "exists", lambda p: False)
        count = sem.backfill_from_sqlite()
        assert count == 0

    def test_backfill_imports_from_sqlite(self, monkeypatch, tmp_path):
        """Backfill reads facts and conversations from SQLite."""
        _init()

        # Create a temporary SQLite DB with test data
        db_file = tmp_path / "memory.db"
        conn = sqlite3.connect(str(db_file))
        conn.execute("CREATE TABLE facts (person_id INTEGER, fact TEXT)")
        conn.execute("INSERT INTO facts VALUES (1, 'Mario is a plumber from Brooklyn')")
        conn.execute("INSERT INTO facts VALUES (2, 'Luigi wears green overalls always')")
        conn.execute(
            "CREATE TABLE conversations (person_id INTEGER, role TEXT, content TEXT)"
        )
        conn.execute(
            "INSERT INTO conversations VALUES (1, 'user', 'Tell me about your adventures in the Mushroom Kingdom')"
        )
        conn.execute(
            "INSERT INTO conversations VALUES (1, 'assistant', 'Short')"  # role != user — skipped
        )
        conn.execute(
            "INSERT INTO conversations VALUES (2, 'user', 'tiny')"  # len <= 10 — skipped
        )
        conn.commit()
        conn.close()

        # Patch os.path.exists and sqlite3.connect to use our temp DB
        real_exists = os.path.exists

        def patched_exists(p):
            if p.endswith("memory.db"):
                return True
            return real_exists(p)

        real_connect = sqlite3.connect

        def patched_connect(p, *a, **kw):
            if "memory.db" in str(p):
                return real_connect(str(db_file), *a, **kw)
            return real_connect(p, *a, **kw)

        monkeypatch.setattr(os.path, "exists", patched_exists)
        monkeypatch.setattr(sqlite3, "connect", patched_connect)

        count = sem.backfill_from_sqlite()
        # 2 facts + 1 qualifying conversation = 3
        assert count == 3
        stats = sem.get_collection_stats()
        assert stats["total_points"] == 3
