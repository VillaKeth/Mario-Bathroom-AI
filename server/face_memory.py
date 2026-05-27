"""Face encoding storage and matching for guest identification.

Stores 128-dim face_recognition encodings in both SQLite (legacy) and 
Qdrant vector database (primary). Matches incoming face encodings using 
cosine similarity in Qdrant for improved accuracy and speed.
Privacy: only numerical vectors stored, never images.
"""
import json
import logging
import os
import sqlite3
import threading
import uuid
from datetime import datetime
from typing import Optional

import numpy as np

# Qdrant integration for face embeddings
try:
    from qdrant_client import QdrantClient, models
    _HAS_QDRANT = True
except ImportError:
    _HAS_QDRANT = False

logger = logging.getLogger(__name__)
DEBUG_FACE = os.environ.get("DEBUG_FACE", "").lower() in ("1", "true", "yes")


class FaceMemory:
    """Persistent face encoding storage with matching via Qdrant + SQLite fallback."""

    def __init__(self, db_path: str, match_tolerance: float = 0.6, collection_name: str = "mario_faces"):
        self._db_path = db_path
        self._tolerance = match_tolerance
        self._collection_name = collection_name
        self._lock = threading.RLock()
        self._init_db()
        
        # Initialize Qdrant for face embeddings
        self._qdrant_client = None
        if _HAS_QDRANT:
            self._init_qdrant()

    def _init_qdrant(self):
        """Initialize Qdrant client and face collection."""
        try:
            # Use local file-based storage for Qdrant
            qdrant_path = os.path.join(os.path.dirname(self._db_path), "qdrant_faces")
            os.makedirs(qdrant_path, exist_ok=True)
            self._qdrant_client = QdrantClient(path=qdrant_path)
            
            # Check if collection exists
            collections = [c.name for c in self._qdrant_client.get_collections().collections]
            if self._collection_name not in collections:
                self._qdrant_client.create_collection(
                    collection_name=self._collection_name,
                    vectors_config=models.VectorParams(
                        size=128,  # face_recognition encoding dimension
                        distance=models.Distance.COSINE,
                    ),
                )
                if DEBUG_FACE:
                    logger.info(f"[face_memory] Created {self._collection_name} Qdrant collection")
            else:
                if DEBUG_FACE:
                    logger.info(f"[face_memory] {self._collection_name} Qdrant collection already exists")
        except Exception as e:
            logger.warning(f"[face_memory] Failed to initialize Qdrant: {e}")
            self._qdrant_client = None

    def _init_db(self):
        os.makedirs(os.path.dirname(self._db_path) or ".", exist_ok=True)
        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS face_encodings (
                    person_id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    encoding TEXT NOT NULL,
                    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    visit_count INTEGER DEFAULT 1
                )
            """)
            conn.commit()
        finally:
            conn.close()

    def store_face(self, person_id: int, name: str, encoding: np.ndarray):
        """Store or update a face encoding."""
        enc_json = json.dumps(encoding.tolist())
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                existing = conn.execute(
                    "SELECT person_id FROM face_encodings WHERE person_id = ?",
                    (person_id,)
                ).fetchone()
                if existing:
                    conn.execute("""
                        UPDATE face_encodings
                        SET encoding = ?, last_seen = CURRENT_TIMESTAMP,
                            visit_count = visit_count + 1
                        WHERE person_id = ?
                    """, (enc_json, person_id))
                else:
                    conn.execute("""
                        INSERT INTO face_encodings (person_id, name, encoding)
                        VALUES (?, ?, ?)
                    """, (person_id, name, enc_json))
                conn.commit()
            finally:
                conn.close()
        if DEBUG_FACE:
            logger.info(f"[face_memory] stored face for {name} (id={person_id})")

    def find_match(self, encoding: np.ndarray,
                   tolerance: Optional[float] = None) -> Optional[dict]:
        """Find best matching face using Qdrant first, SQLite fallback.
        
        Uses early-exit: stops scanning if confidence > 0.95 (near-exact match).
        For party-scale (20-50 guests), Qdrant search is <1ms.
        """
        # Try Qdrant first (primary method)
        if self._qdrant_client:
            qdrant_match = self.lookup_face_qdrant(encoding, tolerance)
            if qdrant_match:
                if DEBUG_FACE:
                    logger.info(f"[face_memory] Qdrant match: {qdrant_match['name']} ({qdrant_match['confidence']:.3f})")
                return {
                    "person_id": None,  # Qdrant doesn't use person_id
                    "name": qdrant_match["name"],
                    "confidence": qdrant_match["confidence"],
                    "visit_count": qdrant_match["visits"],
                }
        
        # Fallback to SQLite (legacy method)
        tol = tolerance or self._tolerance
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                rows = conn.execute(
                    "SELECT person_id, name, encoding, visit_count FROM face_encodings"
                ).fetchall()
            finally:
                conn.close()

        if not rows:
            return None

        best_match = None
        best_distance = float("inf")

        for pid, name, enc_json, visits in rows:
            stored = np.array(json.loads(enc_json), dtype=np.float64)
            distance = float(np.linalg.norm(encoding - stored))
            if distance < best_distance and distance <= tol:
                best_distance = distance
                best_match = {
                    "person_id": pid,
                    "name": name,
                    "confidence": max(0.0, 1.0 - distance),
                    "visit_count": visits,
                }
                # Early exit for near-exact match (>95% confidence)
                if best_match["confidence"] > 0.95:
                    break

        if DEBUG_FACE and best_match:
            logger.info(f"[face_memory] SQLite fallback match: {best_match['name']} ({best_match['confidence']:.3f})")
            
        return best_match

    def store_face_qdrant(self, name: str, encoding: np.ndarray) -> bool:
        """Store face encoding in Qdrant collection.
        
        Args:
            name: Guest name
            encoding: 128-dim face encoding
            
        Returns:
            True if stored successfully, False otherwise
        """
        if not self._qdrant_client or encoding.shape != (128,):
            return False
            
        try:
            # Generate deterministic point ID from name
            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"face:{name}"))
            
            # Check if face already exists, increment visits if so
            visits = 1
            try:
                existing = self._qdrant_client.retrieve(
                    collection_name=self._collection_name,
                    ids=[point_id],
                )
                if existing:
                    visits = existing[0].payload.get("visits", 0) + 1
            except Exception:
                pass  # New face
            
            # Store face encoding
            self._qdrant_client.upsert(
                collection_name=self._collection_name,
                points=[models.PointStruct(
                    id=point_id,
                    vector=encoding.tolist(),
                    payload={
                        "name": name,
                        "visits": visits,
                        "last_seen": datetime.now().isoformat(),
                    },
                )],
            )
            
            if DEBUG_FACE:
                logger.info(f"[face_memory] Stored face for {name} in Qdrant (visits: {visits})")
            return True
            
        except Exception as e:
            logger.error(f"[face_memory] Failed to store face in Qdrant: {e}")
            return False

    def lookup_face_qdrant(self, encoding: np.ndarray, 
                          tolerance: Optional[float] = None) -> Optional[dict]:
        """Find matching face in Qdrant by cosine similarity.
        
        Args:
            encoding: 128-dim face encoding to match
            tolerance: Similarity threshold (default: 0.4 for cosine)
            
        Returns:
            dict with name, confidence, visits or None if no match
        """
        if not self._qdrant_client or encoding.shape != (128,):
            return None
            
        similarity_threshold = tolerance or 0.4  # Cosine similarity threshold
        
        try:
            results = self._qdrant_client.query_points(
                collection_name=self._collection_name,
                query=encoding.tolist(),
                limit=1,
                score_threshold=similarity_threshold,
            )
            
            if results.points:
                point = results.points[0]
                payload = point.payload
                
                return {
                    "name": payload.get("name", "Unknown"),
                    "confidence": float(point.score),
                    "visits": payload.get("visits", 1),
                    "last_seen": payload.get("last_seen", ""),
                }
                
        except Exception as e:
            logger.error(f"[face_memory] Failed to lookup face in Qdrant: {e}")
            
        return None

    def learn_guest(self, name: str, encoding: np.ndarray):
        """Learn a new guest's face encoding.
        
        Stores in both Qdrant (primary) and SQLite (fallback).
        """
        # Store in Qdrant (primary)
        qdrant_success = self.store_face_qdrant(name, encoding)
        
        # Store in SQLite (fallback) - use next available person_id
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                # Find next available person_id
                max_id = conn.execute("SELECT MAX(person_id) FROM face_encodings").fetchone()[0] or 0
                person_id = max_id + 1
                
                # Store in SQLite
                self.store_face(person_id, name, encoding)
                
            finally:
                conn.close()
        
        if DEBUG_FACE:
            qdrant_status = "✓" if qdrant_success else "✗"
            logger.info(f"[face_memory] Learned guest {name} - Qdrant: {qdrant_status}, SQLite: ✓")

    def get_all_faces(self) -> list:
        """Return all stored face entries (without encodings)."""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                rows = conn.execute(
                    "SELECT person_id, name, visit_count, first_seen, last_seen FROM face_encodings"
                ).fetchall()
            finally:
                conn.close()
        return [
            {"person_id": r[0], "name": r[1], "visit_count": r[2],
             "first_seen": r[3], "last_seen": r[4]}
            for r in rows
        ]
