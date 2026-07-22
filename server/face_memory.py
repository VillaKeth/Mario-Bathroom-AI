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

# Sibling import: this repo loads server/ modules as both bare top-level copies
# and server.* package copies (independent module instances). recognition_config
# holds a module-global cache, so every module in a process must resolve the
# SAME instance of it. Mirrors server/mario_prompt.py:409-412 and
# server/llm.py:185-186.
if __package__:
    from server import recognition_config
else:
    import recognition_config

logger = logging.getLogger(__name__)
DEBUG_FACE = os.environ.get("DEBUG_FACE", "").lower() in ("1", "true", "yes")


class FaceMemory:
    """Persistent face encoding storage with a calibrated Euclidean SQLite scan."""

    def __init__(self, db_path: str, match_tolerance: float = None,
                 collection_name: str = "mario_faces"):
        # `collection_name` is retained for back-compat with existing callers
        # (main.py, recognition lab); it is unused now that matching is SQLite-only.
        self._db_path = db_path
        if match_tolerance is None:
            match_tolerance = recognition_config.get("face_match_tolerance")
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
            # W2: one row per encoding. face_encodings stays as the identity table
            # and person_id allocator; its `encoding` column is kept as the
            # migration source and rollback path but is no longer read for matching.
            conn.execute("""
                CREATE TABLE IF NOT EXISTS face_gallery (
                    encoding_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    person_id   INTEGER NOT NULL,
                    name        TEXT    NOT NULL,
                    encoding    TEXT    NOT NULL,
                    quality     REAL    NOT NULL DEFAULT 0.0,
                    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_face_gallery_person "
                         "ON face_gallery(person_id)")
            conn.commit()
        finally:
            conn.close()
        self._migrate_legacy_encodings()

    def _migrate_legacy_encodings(self):
        """Pull pre-gallery `face_encodings.encoding` rows into face_gallery. Idempotent."""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                if conn.execute("SELECT COUNT(*) FROM face_gallery").fetchone()[0]:
                    return
                rows = conn.execute(
                    "SELECT person_id, name, encoding FROM face_encodings").fetchall()
                for pid, name, enc_json in rows:
                    conn.execute(
                        "INSERT INTO face_gallery (person_id, name, encoding, quality) "
                        "VALUES (?, ?, ?, 0.0)", (pid, name, enc_json))
                if rows:
                    conn.commit()
                    logger.info(f"[face_memory] migrated {len(rows)} legacy encodings into gallery")
            finally:
                conn.close()

    def _add_encoding(self, conn, person_id: int, name: str,
                      encoding: np.ndarray, quality: float = 0.0):
        """Insert an encoding, then evict the most redundant if over cap.

        Evicts the encoding CLOSEST to the person's centroid — the most redundant
        view — rather than the oldest, because gallery value is view diversity.
        Ties break toward the lower quality score.
        """
        conn.execute(
            "INSERT INTO face_gallery (person_id, name, encoding, quality) VALUES (?, ?, ?, ?)",
            (person_id, name, json.dumps(np.asarray(encoding).tolist()), float(quality)))

        cap = int(recognition_config.get("gallery_max_per_person"))
        rows = conn.execute(
            "SELECT encoding_id, encoding, quality FROM face_gallery WHERE person_id = ?",
            (person_id,)).fetchall()
        if len(rows) <= cap:
            return

        vecs = [(rid, np.array(json.loads(enc), dtype=np.float64), q) for rid, enc, q in rows]
        centroid = np.mean([v for _, v, _ in vecs], axis=0)
        victim = min(vecs, key=lambda t: (float(np.linalg.norm(t[1] - centroid)), t[2]))
        conn.execute("DELETE FROM face_gallery WHERE encoding_id = ?", (victim[0],))

    def gallery_size(self, person_id: int) -> int:
        """Number of encodings currently stored for a person."""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                return conn.execute(
                    "SELECT COUNT(*) FROM face_gallery WHERE person_id = ?",
                    (person_id,)).fetchone()[0]
            finally:
                conn.close()

    def store_face(self, person_id: int, name: str, encoding: np.ndarray,
                    quality: float = 0.0):
        """Store or update a face encoding, and add it to the gallery.

        Keeps the identity-row upsert (and its visit_count increment) existing
        callers depend on — e.g. main.py's `/admin/recognition/face` photo-enroll
        endpoint — but also feeds `_add_encoding`. `find_match` reads only
        `face_gallery`, so without this a face enrolled through this path could
        never be matched again.
        """
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
                self._add_encoding(conn, person_id, name, encoding, quality)
                conn.commit()
            finally:
                conn.close()
        if DEBUG_FACE:
            logger.info(f"[face_memory] stored face for {name} (id={person_id})")

    def find_match_detail(self, encoding: np.ndarray,
                          tolerance: Optional[float] = None) -> dict:
        """Best gallery match, with the ambiguity verdict reported SEPARATELY.

        Returns `{"match": <dict|None>, "ambiguous": bool}`.

        `find_match` collapses two very different outcomes into `None`: "nobody is
        close" and "somebody IS close but a second person is nearly as close" (the W4
        margin firing). A read-only caller cannot tell them apart and does not need
        to; a caller that may WRITE absolutely does. Treating an ambiguous face as a
        stranger and enrolling it under the current speaker's name writes one guest's
        encoding into another guest's gallery, after which every later frame matches
        the wrong name at distance ~0 and clears the margin easily — a permanent,
        CONFIDENT wrong name. Anything that enrolls or stashes must use this method.

        Reduction is per distinct NAME, not per `person_id`. Master's `learn_guest`
        allocated `max_id + 1` on every call, so a real post-party memory.db holds
        several `face_encodings` rows for one guest, each with its own person_id, and
        the gallery migration copies them 1:1. Reducing per person_id would make one
        human's duplicate rows COMPETING identities, so the margin would reject him
        against himself and returning guests would be permanently unrecognizable.
        Mirrors `speaker_id.identify_speaker`'s per-name reduction (`speaker_id.py`).

        dlib's 128-dim encodings are Euclidean-native and calibrated at 0.6. A
        person's score is their BEST encoding, so extra views can only help.
        Party scale: 20-50 guests x <=5 encodings = <=250 vectors, well under 1ms.
        """
        tol = tolerance if tolerance is not None else self._tolerance
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                rows = conn.execute("""
                    SELECT g.person_id, g.name, g.encoding, COALESCE(e.visit_count, 1)
                    FROM face_gallery g
                    LEFT JOIN face_encodings e ON e.person_id = g.person_id
                """).fetchall()
            finally:
                conn.close()

        if not rows:
            return {"match": None, "ambiguous": False}

        best_per_name = {}
        for pid, name, enc_json, visits in rows:
            stored = np.array(json.loads(enc_json), dtype=np.float64)
            distance = float(np.linalg.norm(encoding - stored))
            current = best_per_name.get(name)
            if current is None or distance < current[0]:
                best_per_name[name] = (distance, pid, visits)

        ranked = sorted(best_per_name.items(), key=lambda kv: kv[1][0])
        name, (distance, person_id, visits) = ranked[0]
        if distance > tol:
            return {"match": None, "ambiguous": False}

        # W4: refuse an ambiguous call. Only DIFFERENT people compete — `ranked` is
        # already reduced to one entry per NAME, so neither two views of the same
        # guest nor two legacy person_id rows for him can look like a tie.
        if len(ranked) >= 2:
            runner_up_distance = ranked[1][1][0]
            margin = recognition_config.get("face_match_margin")
            if (runner_up_distance - distance) < margin:
                if DEBUG_FACE:
                    logger.info(f"[face_memory] ambiguous: {name} {distance:.3f} vs "
                                f"runner-up {runner_up_distance:.3f} (margin {margin}) — unknown")
                return {"match": None, "ambiguous": True}

        match = {
            "person_id": person_id,
            "name": name,
            "confidence": max(0.0, 1.0 - distance),
            "visit_count": visits,
        }
        if DEBUG_FACE:
            logger.info(f"[face_memory] match: {name} ({match['confidence']:.3f})")
        return {"match": match, "ambiguous": False}

    def find_match(self, encoding: np.ndarray,
                   tolerance: Optional[float] = None) -> Optional[dict]:
        """Best gallery match, or None. Unchanged return shape for read-only callers.

        None here means "no identity to report" — it does NOT distinguish a stranger
        from an ambiguous pair. Callers that enroll or stash must use
        `find_match_detail` instead.
        """
        return self.find_match_detail(encoding, tolerance)["match"]

    def learn_guest(self, name: str, encoding: np.ndarray, quality: float = 0.0) -> int:
        """Enroll an encoding for `name`, returning that guest's person_id.

        A name already in the gallery ADDS a view rather than creating a second
        identity — this is what accumulates the multi-view gallery that lets a
        returning guest match from a new angle.
        """
        enc = np.asarray(encoding, dtype=np.float64)
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                row = conn.execute(
                    "SELECT person_id FROM face_encodings WHERE name = ?", (name,)).fetchone()
                if row:
                    person_id = row[0]
                    conn.execute(
                        "UPDATE face_encodings SET last_seen = CURRENT_TIMESTAMP, "
                        "visit_count = visit_count + 1 WHERE person_id = ?", (person_id,))
                else:
                    max_id = conn.execute(
                        "SELECT MAX(person_id) FROM face_encodings").fetchone()[0] or 0
                    person_id = max_id + 1
                    conn.execute(
                        "INSERT INTO face_encodings (person_id, name, encoding) VALUES (?, ?, ?)",
                        (person_id, name, json.dumps(enc.tolist())))
                self._add_encoding(conn, person_id, name, enc, quality)
                conn.commit()
            finally:
                conn.close()

        if DEBUG_FACE:
            logger.info(f"[face_memory] learned {name} (person_id={person_id})")
        return person_id

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
