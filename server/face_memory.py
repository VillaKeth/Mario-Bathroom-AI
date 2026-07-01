"""Face encoding storage and matching for guest identification.

Stores 128-dim face_recognition encodings in SQLite and matches incoming
encodings with a calibrated Euclidean scan (dlib's native metric, 0.6
threshold). At party scale (dozens of guests) the linear scan is <1ms, so
no vector index is needed. Privacy: only numerical vectors stored, never images.
"""
import json
import logging
import os
import sqlite3
import threading
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)
DEBUG_FACE = os.environ.get("DEBUG_FACE", "").lower() in ("1", "true", "yes")


class FaceMemory:
    """Persistent face encoding storage with a calibrated Euclidean SQLite scan."""

    def __init__(self, db_path: str, match_tolerance: float = 0.6, collection_name: str = "mario_faces"):
        # `collection_name` is retained for back-compat with existing callers
        # (main.py, recognition lab); it is unused now that matching is SQLite-only.
        self._db_path = db_path
        self._tolerance = match_tolerance
        self._lock = threading.RLock()
        self._init_db()

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
        """Find the best matching face via a calibrated Euclidean SQLite scan.

        dlib's face_recognition 128-dim encodings are EUCLIDEAN-native and
        calibrated at a 0.6 distance threshold, so matching uses Euclidean
        distance (not cosine). Early-exit: stops scanning if confidence > 0.95
        (near-exact match). At party scale (20-50 guests) the linear scan is <1ms.
        """
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
            logger.info(f"[face_memory] match: {best_match['name']} ({best_match['confidence']:.3f})")

        return best_match

    def learn_guest(self, name: str, encoding: np.ndarray):
        """Learn a new guest's face encoding (stored in SQLite)."""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                # Find next available person_id
                max_id = conn.execute("SELECT MAX(person_id) FROM face_encodings").fetchone()[0] or 0
                person_id = max_id + 1
                self.store_face(person_id, name, encoding)
            finally:
                conn.close()

        if DEBUG_FACE:
            logger.info(f"[face_memory] Learned guest {name} (SQLite)")

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
