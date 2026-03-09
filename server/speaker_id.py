"""Speaker identification using voice embeddings (resemblyzer)."""

import logging
import sqlite3
import json
import os
import numpy as np

# Fix numpy deprecation in resemblyzer (np.bool removed in numpy 1.24+)
import warnings
with warnings.catch_warnings():
    warnings.simplefilter("ignore", FutureWarning)
    if not hasattr(np, 'bool') or type(np.bool) != type:
        np.bool = bool

from resemblyzer import VoiceEncoder, preprocess_wav

DEBUG_SPEAKER = True
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

_encoder: VoiceEncoder = None


def init_speaker_id():
    """Initialize the voice encoder and database."""
    global _encoder
    if DEBUG_SPEAKER:
        logger.info("[DEBUG_SPEAKER] init_speaker_id: START")

    _encoder = VoiceEncoder()

    # Initialize database
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


def identify_speaker(audio_data: bytes, sample_rate: int = 16000) -> dict:
    """Identify who is speaking from audio data.
    
    Returns:
        dict with 'name' (str or None), 'speaker_id' (int or None), 
        'confidence' (float), 'is_new' (bool)
    """
    if DEBUG_SPEAKER:
        logger.info("[DEBUG_SPEAKER] identify_speaker: START")

    try:
        embedding = get_embedding(audio_data, sample_rate)
    except (ValueError, RuntimeError) as e:
        logger.warning(f"[DEBUG_SPEAKER] identify_speaker: embedding failed: {e}")
        return {"name": None, "speaker_id": None, "confidence": 0.0, "is_new": True}
    if embedding is None:
        return {"name": None, "speaker_id": None, "confidence": 0.0, "is_new": True}

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
        stored_embedding = np.frombuffer(emb_blob, dtype=np.float32)
        norm_product = np.linalg.norm(embedding) * np.linalg.norm(stored_embedding)
        if norm_product == 0:
            continue
        similarity = np.dot(embedding, stored_embedding) / norm_product
        if DEBUG_SPEAKER:
            logger.info(f"[DEBUG_SPEAKER] identify_speaker: {name} similarity={similarity:.3f}")

        if similarity > best_similarity:
            best_similarity = similarity
            best_match = (row_id, name)

    if best_match and best_similarity >= SIMILARITY_THRESHOLD:
        if DEBUG_SPEAKER:
            logger.info(f"[DEBUG_SPEAKER] identify_speaker: matched {best_match[1]} ({best_similarity:.3f})")
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
