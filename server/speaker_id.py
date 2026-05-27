"""Speaker identification using voice embeddings (resemblyzer) + Qdrant vector storage."""

import logging
import sqlite3
import json
import os
import uuid
import numpy as np
from datetime import datetime
from typing import Optional

# Fix numpy deprecation in resemblyzer (np.bool removed in numpy 1.24+)
import warnings
with warnings.catch_warnings():
    warnings.simplefilter("ignore", FutureWarning)
    if not hasattr(np, 'bool') or type(np.bool) != type:
        np.bool = bool

# resemblyzer is required for speaker identification but optional for basic chat
_HAS_RESEMBLYZER = False
try:
    from resemblyzer import VoiceEncoder, preprocess_wav
    _HAS_RESEMBLYZER = True
except ImportError:
    VoiceEncoder = None
    preprocess_wav = None
    logging.getLogger(__name__).warning(
        "[speaker_id] resemblyzer not installed — speaker identification disabled. "
        "Install with: pip install resemblyzer"
    )

# Qdrant integration for voice embeddings
try:
    from qdrant_client import QdrantClient, models
    _HAS_QDRANT = True
except ImportError:
    _HAS_QDRANT = False

DEBUG_SPEAKER = os.environ.get("DEBUG_SPEAKER", "").lower() in ("1", "true", "yes")
logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 0.75  # Cosine similarity threshold for matching (configurable via config.json)
DB_PATH = os.path.join(os.path.dirname(__file__), "data", "voices.db")

# Allow config.json to override threshold
_spk_config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")
if os.path.exists(_spk_config_path):
    try:
        import json as _json_mod
        with open(_spk_config_path) as _f:
            _spk_cfg = _json_mod.load(_f).get("server", {})
            SIMILARITY_THRESHOLD = _spk_cfg.get("speaker_similarity_threshold", SIMILARITY_THRESHOLD)
    except Exception:
        pass

_encoder = None
_qdrant_client: QdrantClient = None if _HAS_QDRANT else None
_collection_name = "mario_voices"


def init_speaker_id(collection_name: str = "mario_voices"):
    """Initialize the voice encoder, database, and Qdrant collection."""
    global _encoder, _qdrant_client, _collection_name
    _collection_name = collection_name
    if not _HAS_RESEMBLYZER:
        logger.warning("[speaker_id] Skipping init — resemblyzer not installed")
        return
    if DEBUG_SPEAKER:
        logger.info("[DEBUG_SPEAKER] init_speaker_id: START")

    _encoder = VoiceEncoder("cpu")

    # Initialize SQLite database (legacy/fallback)
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS speakers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                embedding BLOB NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

    # Initialize Qdrant for voice embeddings  
    if _HAS_QDRANT:
        try:
            # Use local file-based storage for Qdrant
            qdrant_path = os.path.join(os.path.dirname(DB_PATH), "qdrant_voices")
            os.makedirs(qdrant_path, exist_ok=True)
            _qdrant_client = QdrantClient(path=qdrant_path)
            
            # Check if collection exists
            collections = [c.name for c in _qdrant_client.get_collections().collections]
            if _collection_name not in collections:
                _qdrant_client.create_collection(
                    collection_name=_collection_name,
                    vectors_config=models.VectorParams(
                        size=256,  # Resemblyzer embedding dimension
                        distance=models.Distance.COSINE,
                    ),
                )
                if DEBUG_SPEAKER:
                    logger.info(f"[DEBUG_SPEAKER] Created {_collection_name} Qdrant collection")
            else:
                if DEBUG_SPEAKER:
                    logger.info(f"[DEBUG_SPEAKER] {_collection_name} Qdrant collection already exists")
        except Exception as e:
            logger.warning(f"[DEBUG_SPEAKER] Failed to initialize Qdrant: {e}")
            _qdrant_client = None

    if DEBUG_SPEAKER:
        logger.info("[DEBUG_SPEAKER] init_speaker_id: END")


def get_embedding(audio_data: bytes, sample_rate: int = 16000) -> np.ndarray:
    """Extract voice embedding from audio data.
    
    Args:
        audio_data: Raw PCM int16 mono audio bytes
        sample_rate: Sample rate of the audio
        
    Returns:
        256-dimensional voice embedding vector
    """
    if _encoder is None:
        raise RuntimeError("Speaker ID not initialized. Call init_speaker_id() first.")

    audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
    processed = preprocess_wav(audio_np, source_sr=sample_rate)

    if len(processed) < sample_rate * 1.0:
        if DEBUG_SPEAKER:
            logger.info("[DEBUG_SPEAKER] get_embedding: audio too short for embedding")
        return None

    embedding = _encoder.embed_utterance(processed)
    if DEBUG_SPEAKER:
        logger.info(f"[DEBUG_SPEAKER] get_embedding: shape={embedding.shape}")
    return embedding


def store_voice_qdrant(name: str, embedding: np.ndarray) -> bool:
    """Store voice embedding in Qdrant collection.
    
    Args:
        name: Speaker name
        embedding: 256-dim voice embedding
        
    Returns:
        True if stored successfully, False otherwise
    """
    if not _qdrant_client or embedding.shape != (256,):
        return False
        
    try:
        # Generate deterministic point ID from name
        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"voice:{name}"))
        
        # Get next speaker ID from SQLite for consistency
        speaker_id_val = None
        try:
            with sqlite3.connect(DB_PATH) as conn:
                existing = conn.execute("SELECT id FROM speakers WHERE name = ?", (name,)).fetchone()
                if existing:
                    speaker_id_val = existing[0]
                else:
                    # Create new speaker record
                    cursor = conn.execute("INSERT INTO speakers (name, embedding) VALUES (?, ?)", 
                                        (name, embedding.tobytes()))
                    speaker_id_val = cursor.lastrowid
                    conn.commit()
        except Exception:
            pass
        
        # Store voice embedding in Qdrant
        _qdrant_client.upsert(
            collection_name=_collection_name,
            points=[models.PointStruct(
                id=point_id,
                vector=embedding.tolist(),
                payload={
                    "name": name,
                    "speaker_id": speaker_id_val,
                    "last_seen": datetime.now().isoformat(),
                },
            )],
        )
        
        if DEBUG_SPEAKER:
            logger.info(f"[DEBUG_SPEAKER] Stored voice for {name} in Qdrant (id: {speaker_id_val})")
        return True
        
    except Exception as e:
        logger.error(f"[DEBUG_SPEAKER] Failed to store voice in Qdrant: {e}")
        return False


def lookup_voice_qdrant(embedding: np.ndarray, 
                       similarity_threshold: float = None) -> Optional[dict]:
    """Find matching voice in Qdrant by cosine similarity.
    
    Args:
        embedding: 256-dim voice embedding to match
        similarity_threshold: Similarity threshold (default: SIMILARITY_THRESHOLD)
        
    Returns:
        dict with name, speaker_id, confidence or None if no match
    """
    if not _qdrant_client or embedding.shape != (256,):
        return None
        
    threshold = similarity_threshold or SIMILARITY_THRESHOLD
    
    try:
        results = _qdrant_client.query_points(
            collection_name=_collection_name,
            query=embedding.tolist(),
            limit=1,
            score_threshold=threshold,
        )
        
        if results.points:
            point = results.points[0]
            payload = point.payload
            
            return {
                "name": payload.get("name", "Unknown"),
                "speaker_id": payload.get("speaker_id"),
                "confidence": float(point.score),
                "last_seen": payload.get("last_seen", ""),
            }
            
    except Exception as e:
        logger.error(f"[DEBUG_SPEAKER] Failed to lookup voice in Qdrant: {e}")
        
    return None


def learn_voice(name: str, embedding: np.ndarray):
    """Learn a new guest's voice embedding.
    
    Stores in both Qdrant (primary) and SQLite (fallback).
    """
    # Store in Qdrant (primary)
    qdrant_success = store_voice_qdrant(name, embedding)
    
    if DEBUG_SPEAKER:
        qdrant_status = "✓" if qdrant_success else "✗"
        logger.info(f"[DEBUG_SPEAKER] Learned voice for {name} - Qdrant: {qdrant_status}")


def identify_speaker(audio_data: bytes, sample_rate: int = 16000) -> dict:
    """Identify who is speaking from audio data using Qdrant first, SQLite fallback.
    
    Returns:
        dict with 'name' (str or None), 'speaker_id' (int or None), 
        'confidence' (float), 'is_new' (bool)
    """
    if not _HAS_RESEMBLYZER or _encoder is None:
        return {"name": None, "speaker_id": None, "confidence": 0.0, "is_new": True}
    if DEBUG_SPEAKER:
        logger.info("[DEBUG_SPEAKER] identify_speaker: START")

    try:
        embedding = get_embedding(audio_data, sample_rate)
    except (ValueError, RuntimeError) as e:
        logger.warning(f"[DEBUG_SPEAKER] identify_speaker: embedding failed: {e}")
        return {"name": None, "speaker_id": None, "confidence": 0.0, "is_new": True}
    if embedding is None:
        return {"name": None, "speaker_id": None, "confidence": 0.0, "is_new": True}

    # Try Qdrant first (primary method)
    if _qdrant_client:
        qdrant_match = lookup_voice_qdrant(embedding)
        if qdrant_match:
            if DEBUG_SPEAKER:
                logger.info(f"[DEBUG_SPEAKER] Qdrant voice match: {qdrant_match['name']} ({qdrant_match['confidence']:.3f})")
            return {
                "name": qdrant_match["name"],
                "speaker_id": qdrant_match["speaker_id"],
                "confidence": qdrant_match["confidence"],
                "is_new": False,
            }

    # Fallback to SQLite (legacy method)
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.execute("SELECT id, name, embedding FROM speakers")
        rows = cursor.fetchall()
    except Exception as e:
        logger.error(f"[DEBUG_SPEAKER] identify_speaker: DB error: {e}")
        return {"name": None, "speaker_id": None, "confidence": 0.0, "is_new": True}
    finally:
        conn.close()

    best_match = None
    best_similarity = -1.0

    for row_id, name, emb_blob in rows:
        try:
            stored_embedding = np.frombuffer(emb_blob, dtype=np.float32)
            if stored_embedding.shape != embedding.shape:
                logger.warning(f"[DEBUG_SPEAKER] Shape mismatch for {name}: stored={stored_embedding.shape} vs current={embedding.shape}, skipping")
                continue
            norm_product = np.linalg.norm(embedding) * np.linalg.norm(stored_embedding)
            if norm_product == 0:
                continue
            similarity = np.dot(embedding, stored_embedding) / norm_product
        except Exception as e:
            logger.error(f"[DEBUG_SPEAKER] Error comparing embedding for {name}: {e}")
            continue
        if DEBUG_SPEAKER:
            logger.info(f"[DEBUG_SPEAKER] identify_speaker SQLite: {name} similarity={similarity:.3f}")

        if similarity > best_similarity:
            best_similarity = similarity
            best_match = (row_id, name)

    if best_match and best_similarity >= SIMILARITY_THRESHOLD:
        if DEBUG_SPEAKER:
            logger.info(f"[DEBUG_SPEAKER] SQLite fallback matched {best_match[1]} ({best_similarity:.3f})")
        return {
            "name": best_match[1],
            "speaker_id": best_match[0],
            "confidence": float(best_similarity),
            "is_new": False,
        }

    if DEBUG_SPEAKER:
        logger.info(f"[DEBUG_SPEAKER] identify_speaker: no match (best={best_similarity:.3f})")
    return {"name": None, "speaker_id": None, "confidence": float(best_similarity), "is_new": True}


def register_speaker(name: str, audio_data: bytes, sample_rate: int = 16000) -> int:
    """Register a new speaker's voice.
    
    Returns:
        The new speaker's database ID
    """
    if not _HAS_RESEMBLYZER or _encoder is None:
        raise ValueError("Speaker identification not available — resemblyzer not installed")
    if DEBUG_SPEAKER:
        logger.info(f"[DEBUG_SPEAKER] register_speaker: START name={name}")

    embedding = get_embedding(audio_data, sample_rate)
    if embedding is None:
        raise ValueError("Audio too short to create voice embedding")

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            "INSERT INTO speakers (name, embedding) VALUES (?, ?)",
            (name, embedding.tobytes()),
        )
        speaker_id_val = cursor.lastrowid
        conn.commit()

    if DEBUG_SPEAKER:
        logger.info(f"[DEBUG_SPEAKER] register_speaker: END id={speaker_id_val}")
    return speaker_id_val


def update_speaker(speaker_id_val: int, audio_data: bytes, sample_rate: int = 16000):
    """Update an existing speaker's voice embedding with blended new audio (EMA)."""
    if DEBUG_SPEAKER:
        logger.info(f"[DEBUG_SPEAKER] update_speaker: START id={speaker_id_val}")

    new_embedding = get_embedding(audio_data, sample_rate)
    if new_embedding is None:
        raise ValueError("Audio too short to update voice embedding")

    # Blend with existing embedding using exponential moving average (80% old, 20% new)
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT embedding FROM speakers WHERE id = ?", (speaker_id_val,)).fetchone()
        if row:
            old_embedding = np.frombuffer(row[0], dtype=np.float32)
            blended = 0.8 * old_embedding + 0.2 * new_embedding
            blended = blended / np.linalg.norm(blended)  # Re-normalize
            conn.execute(
                "UPDATE speakers SET embedding = ? WHERE id = ?",
                (blended.tobytes(), speaker_id_val),
            )
        else:
            conn.execute(
                "UPDATE speakers SET embedding = ? WHERE id = ?",
                (new_embedding.tobytes(), speaker_id_val),
            )
        conn.commit()

    if DEBUG_SPEAKER:
        logger.info(f"[DEBUG_SPEAKER] update_speaker: END id={speaker_id_val} (blended)")


def delete_speaker(speaker_id_val: int):
    """Delete a speaker's voice data for privacy."""
    if DEBUG_SPEAKER:
        logger.info(f"[DEBUG_SPEAKER] delete_speaker: START id={speaker_id_val}")

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM speakers WHERE id = ?", (speaker_id_val,))
        conn.commit()

    if DEBUG_SPEAKER:
        logger.info(f"[DEBUG_SPEAKER] delete_speaker: END id={speaker_id_val}")


def list_speakers() -> list:
    """List all registered speakers (name + id, no embeddings)."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            rows = conn.execute("SELECT id, name FROM speakers ORDER BY id").fetchall()
            return [{"id": r[0], "name": r[1]} for r in rows]
    except Exception as e:
        logger.error(f"list_speakers failed: {e}")
        return []
