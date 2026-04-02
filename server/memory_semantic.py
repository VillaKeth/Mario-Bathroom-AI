"""Semantic memory using Qdrant vector database + fastembed.

Provides semantic (meaning-based) search over all stored memories,
enabling Mario to recall relevant facts and conversations even when
exact keywords don't match.

Uses fastembed's all-MiniLM-L6-v2 (384-dim) for CPU-based embedding —
no GPU VRAM cost. On ULTRA hardware this is negligible overhead.
"""

import hashlib
import logging
import os
import uuid
from datetime import datetime

from qdrant_client import QdrantClient, models

DEBUG_MEMORY = True
logger = logging.getLogger(__name__)

_client: QdrantClient | None = None
COLLECTION_NAME = "mario_memories"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
VECTOR_SIZE = 384


def init_semantic_memory(path: str | None = None):
    """Initialize Qdrant with local file storage (or in-memory for tests).

    Args:
        path: Directory for persistent storage, or ":memory:" for tests.
    """
    global _client
    if path == ":memory:":
        _client = QdrantClient(location=":memory:")
    else:
        db_path = path or os.path.join(os.path.dirname(__file__), "data", "qdrant_memories")
        os.makedirs(db_path, exist_ok=True)
        _client = QdrantClient(path=db_path)

    # Collection is auto-created on first store_memory call
    collections = [c.name for c in _client.get_collections().collections]
    if COLLECTION_NAME in collections:
        if DEBUG_MEMORY:
            logger.info(f"[DEBUG_MEMORY] Qdrant collection '{COLLECTION_NAME}' already exists")
    else:
        if DEBUG_MEMORY:
            logger.info(f"[DEBUG_MEMORY] Qdrant collection '{COLLECTION_NAME}' will be created on first insert")


def _ensure_collection():
    """Create the collection if it doesn't exist yet."""
    if not _client:
        return
    collections = [c.name for c in _client.get_collections().collections]
    if COLLECTION_NAME not in collections:
        _client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=models.VectorParams(
                size=VECTOR_SIZE,
                distance=models.Distance.COSINE,
            ),
        )
        if DEBUG_MEMORY:
            logger.info(f"[DEBUG_MEMORY] Created Qdrant collection '{COLLECTION_NAME}'")


def _deterministic_id(text: str, person_id: int) -> str:
    """Deterministic UUID from text + person to prevent duplicates."""
    raw = hashlib.md5(f"{person_id}:{text.strip().lower()}".encode()).hexdigest()
    return str(uuid.UUID(hex=raw))


_embedder = None


def _get_embedder():
    """Lazy-init the fastembed model."""
    global _embedder
    if _embedder is None:
        from fastembed import TextEmbedding
        _embedder = TextEmbedding(model_name=EMBEDDING_MODEL)
    return _embedder


def _embed_text(text: str) -> list[float]:
    """Embed a single text string, returns 384-dim vector."""
    embedder = _get_embedder()
    return list(next(embedder.embed([text])))


def health_check() -> bool:
    """Check if Qdrant is healthy and accessible."""
    if _client is None:
        return False
    try:
        _client.get_collection(COLLECTION_NAME)
        return True
    except Exception as e:
        logger.warning(f"[SEMANTIC] Health check failed: {e}")
        return False


def store_memory(person_id: int, text: str, memory_type: str = "fact",
                 metadata: dict | None = None):
    """Embed and store a memory in Qdrant.

    Args:
        person_id: Guest identifier
        text: The memory text to embed
        memory_type: "fact", "conversation", "vip_profile", "vip_hook", "topic"
        metadata: Optional extra metadata
    """
    if not _client or not text or len(text.strip()) < 3:
        return

    point_id = _deterministic_id(text, person_id)

    # Ensure collection exists
    _ensure_collection()

    # Check for duplicate
    try:
        existing = _client.retrieve(
            collection_name=COLLECTION_NAME,
            ids=[point_id],
        )
        if existing:
            if DEBUG_MEMORY:
                logger.info(f"[DEBUG_MEMORY] store_memory: duplicate skipped for person={person_id}")
            return
    except Exception:
        pass  # Point doesn't exist — proceed to insert

    payload = {
        "person_id": person_id,
        "text": text,
        "memory_type": memory_type,
        "timestamp": datetime.now().isoformat(),
    }
    if metadata:
        payload.update(metadata)

    try:
        vector = _embed_text(text)
        _client.upsert(
            collection_name=COLLECTION_NAME,
            points=[models.PointStruct(
                id=point_id,
                vector=vector,
                payload=payload,
            )],
        )
        if DEBUG_MEMORY:
            logger.info(f"[DEBUG_MEMORY] store_memory: stored '{text[:50]}' for person={person_id}")
    except Exception as e:
        logger.error(f"store_memory failed: {e}")


def search_memories(query: str, person_id: int | None = None,
                    limit: int = 20, score_threshold: float = 0.25) -> list[dict]:
    """Search memories by semantic similarity.

    Args:
        query: The search text (e.g. current user message)
        person_id: Filter to this guest only. None = search all guests.
        limit: Max results to return
        score_threshold: Minimum cosine similarity (0-1)

    Returns:
        List of dicts with keys: text, person_id, memory_type, score, timestamp
    """
    if not _client or not query or len(query.strip()) < 3:
        return []

    query_filter = None
    if person_id is not None:
        query_filter = models.Filter(
            must=[models.FieldCondition(
                key="person_id",
                match=models.MatchValue(value=person_id),
            )]
        )

    try:
        query_vector = _embed_text(query)
        results = _client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_vector,
            query_filter=query_filter,
            limit=limit,
            score_threshold=score_threshold,
        )

        memories = []
        for point in results.points:
            payload = point.payload
            memories.append({
                "text": payload.get("text", ""),
                "person_id": payload.get("person_id"),
                "memory_type": payload.get("memory_type", "unknown"),
                "score": point.score if hasattr(point, 'score') else 0.0,
                "timestamp": payload.get("timestamp", ""),
            })

        if DEBUG_MEMORY:
            logger.info(f"[DEBUG_MEMORY] search_memories: query='{query[:40]}' person={person_id} results={len(memories)}")
        return memories

    except Exception as e:
        logger.error(f"search_memories failed: {e}")
        return []


def get_collection_stats() -> dict:
    """Return stats about the semantic memory collection."""
    if not _client:
        return {"status": "not_initialized"}
    try:
        info = _client.get_collection(COLLECTION_NAME)
        return {
            "total_points": info.points_count,
            "status": str(info.status),
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


def backfill_from_sqlite():
    """One-time migration: copy existing SQLite facts and conversations into Qdrant.

    Safe to run multiple times — deduplication prevents double-inserts.
    Skips if collection already has data (backfill already done).
    """
    import sqlite3

    # Skip if already backfilled
    stats = get_collection_stats()
    if stats.get("total_points", 0) > 0:
        if DEBUG_MEMORY:
            logger.info(f"[DEBUG_MEMORY] backfill_from_sqlite: skipped, collection already has {stats['total_points']} points")
        return 0

    db_path = os.path.join(os.path.dirname(__file__), "data", "memory.db")
    if not os.path.exists(db_path):
        logger.info("No SQLite memory DB found, skipping backfill")
        return 0

    conn = sqlite3.connect(db_path)
    count = 0

    # Backfill facts
    facts = conn.execute("SELECT person_id, fact FROM facts").fetchall()
    for person_id, fact in facts:
        store_memory(person_id, fact, memory_type="fact")
        count += 1

    # Backfill user conversations (skip Mario's responses)
    convos = conn.execute(
        "SELECT person_id, content FROM conversations WHERE role = 'user' AND LENGTH(content) > 10"
    ).fetchall()
    for person_id, content in convos:
        store_memory(person_id, content, memory_type="conversation")
        count += 1

    conn.close()
    if DEBUG_MEMORY:
        logger.info(f"[DEBUG_MEMORY] Backfilled {count} memories from SQLite to Qdrant")
    return count
