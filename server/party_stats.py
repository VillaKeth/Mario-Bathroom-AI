"""Party statistics tracker — tracks visitors, fun facts, records."""

import sqlite3
import os
import logging
import time
from datetime import datetime

DEBUG_STATS = True
logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "memory.db")


class PartyStats:
    """Tracks party-wide statistics for fun Mario commentary."""

    def __init__(self):
        self._init_db()
        self.party_start_time = self._load_or_create_party_start()

    def _init_db(self):
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS party_visits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    person_id INTEGER,
                    person_name TEXT,
                    enter_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    exit_time TIMESTAMP,
                    duration_seconds REAL
                );

                CREATE TABLE IF NOT EXISTS party_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    details TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS party_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_party_visits_person ON party_visits(person_name);
                CREATE INDEX IF NOT EXISTS idx_party_events_type ON party_events(event_type);
            """)
            conn.commit()

    def _load_or_create_party_start(self) -> float:
        """Load party start time from DB, or create if first run."""
        try:
            with sqlite3.connect(DB_PATH) as conn:
                row = conn.execute(
                    "SELECT value FROM party_meta WHERE key = 'party_start_time'"
                ).fetchone()
                if row:
                    start = float(row[0])
                    if DEBUG_STATS:
                        elapsed = time.time() - start
                        logger.info(f"[DEBUG_STATS] Restored party_start_time (running {elapsed/3600:.1f}h)")
                    return start
                # First run — save current time
                now = time.time()
                conn.execute(
                    "INSERT INTO party_meta (key, value) VALUES ('party_start_time', ?)",
                    (str(now),)
                )
                conn.commit()
                if DEBUG_STATS:
                    logger.info("[DEBUG_STATS] Created new party_start_time")
                return now
        except Exception as e:
            logger.error(f"_load_or_create_party_start failed: {e}")
            return time.time()

    def reset_party(self):
        """Reset the party (new party session)."""
        try:
            now = time.time()
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO party_meta (key, value) VALUES ('party_start_time', ?)",
                    (str(now),)
                )
                conn.commit()
            self.party_start_time = now
            if DEBUG_STATS:
                logger.info("[DEBUG_STATS] Party reset!")
        except Exception as e:
            logger.error(f"reset_party failed: {e}")

    def record_enter(self, person_id: int = None, person_name: str = None) -> int:
        try:
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.execute(
                    "INSERT INTO party_visits (person_id, person_name) VALUES (?, ?)",
                    (person_id, person_name or "Unknown visitor"),
                )
                visit_id = cursor.lastrowid
                conn.commit()
        except Exception as e:
            logger.error(f"record_enter failed: {e}")
            visit_id = -1
        if DEBUG_STATS:
            logger.info(f"[DEBUG_STATS] record_enter: visit_id={visit_id} name={person_name}")
        return visit_id

    def record_exit(self, visit_id: int):
        try:
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute("""
                    UPDATE party_visits 
                    SET exit_time = CURRENT_TIMESTAMP,
                        duration_seconds = (julianday(CURRENT_TIMESTAMP) - julianday(enter_time)) * 86400
                    WHERE id = ? AND exit_time IS NULL
                """, (visit_id,))
                conn.commit()
        except Exception as e:
            logger.error(f"record_exit failed: {e}")

    def record_event(self, event_type: str, details: str = None):
        try:
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute(
                    "INSERT INTO party_events (event_type, details) VALUES (?, ?)",
                    (event_type, details),
                )
                conn.commit()
        except Exception as e:
            logger.error(f"record_event failed: {e}")

    def get_stats(self) -> dict:
        """Get all party statistics."""
        try:
            with sqlite3.connect(DB_PATH) as conn:
                conn.row_factory = sqlite3.Row

                total_visits = conn.execute("SELECT COUNT(*) as c FROM party_visits").fetchone()["c"]
                unique_visitors = conn.execute(
                    "SELECT COUNT(DISTINCT person_name) as c FROM party_visits WHERE person_name != 'Unknown visitor'"
                ).fetchone()["c"]

                avg_duration = conn.execute(
                    "SELECT AVG(duration_seconds) as avg FROM party_visits WHERE duration_seconds IS NOT NULL"
                ).fetchone()["avg"] or 0

                longest = conn.execute(
                    "SELECT person_name, MAX(duration_seconds) as dur FROM party_visits WHERE duration_seconds IS NOT NULL"
                ).fetchone()

                most_visits = conn.execute("""
                    SELECT person_name, COUNT(*) as cnt 
                    FROM party_visits 
                    WHERE person_name != 'Unknown visitor' 
                    GROUP BY person_name 
                    ORDER BY cnt DESC LIMIT 1
                """).fetchone()

                recent = conn.execute(
                    "SELECT person_name FROM party_visits ORDER BY enter_time DESC LIMIT 1"
                ).fetchone()
        except Exception as e:
            logger.error(f"get_stats failed: {e}")
            return {"total_visits": 0, "unique_visitors": 0, "party_duration": "0h 0m", "current_hour": datetime.now().strftime("%I:%M %p")}

        party_duration = time.time() - self.party_start_time
        hours = int(party_duration // 3600)
        minutes = int((party_duration % 3600) // 60)

        stats = {
            "total_visits": total_visits,
            "unique_visitors": unique_visitors,
            "avg_duration_seconds": round(avg_duration, 1),
            "longest_visit_name": longest["person_name"] if longest else None,
            "longest_visit_seconds": round(longest["dur"], 1) if longest and longest["dur"] else 0,
            "most_frequent_name": most_visits["person_name"] if most_visits else None,
            "most_frequent_count": most_visits["cnt"] if most_visits else 0,
            "last_visitor_name": recent["person_name"] if recent else None,
            "party_duration": f"{hours}h {minutes}m",
            "current_hour": datetime.now().strftime("%I:%M %p"),
        }

        if DEBUG_STATS:
            logger.info(f"[DEBUG_STATS] get_stats: {stats}")
        return stats

    def get_stats_for_prompt(self) -> str:
        """Get formatted stats string for LLM context."""
        s = self.get_stats()
        lines = [
            "## Party Statistics (you can share these if asked!):",
            f"- Party has been going for {s['party_duration']}",
            f"- Current time: {s['current_hour']}",
            f"- Total bathroom visits tonight: {s['total_visits']}",
            f"- Unique visitors: {s['unique_visitors']}",
            f"- Average visit duration: {round(s['avg_duration_seconds'])}s",
        ]
        if s["longest_visit_name"]:
            lines.append(
                f"- Longest visit: {s['longest_visit_name']} ({round(s['longest_visit_seconds'])}s — Mama mia!)"
            )
        if s["most_frequent_name"]:
            lines.append(
                f"- Most frequent visitor: {s['most_frequent_name']} ({s['most_frequent_count']} visits!)"
            )
        return "\n".join(lines)

    def detect_crew(self, window_minutes: int = 10) -> list[list[str]]:
        """Detect groups of people who visited within a time window of each other.
        
        Returns list of crews (each crew is a list of names).
        """
        try:
            with sqlite3.connect(DB_PATH) as conn:
                rows = conn.execute("""
                    SELECT person_name, enter_time FROM party_visits
                    WHERE person_name != 'Unknown visitor'
                    ORDER BY enter_time
                """).fetchall()

            if len(rows) < 2:
                return []

            crews = []
            current_crew = [rows[0][0]]
            prev_time = datetime.fromisoformat(rows[0][1])

            for name, enter_str in rows[1:]:
                enter_time = datetime.fromisoformat(enter_str)
                gap = (enter_time - prev_time).total_seconds() / 60.0
                if gap <= window_minutes:
                    if name not in current_crew:
                        current_crew.append(name)
                else:
                    if len(current_crew) >= 2:
                        crews.append(current_crew)
                    current_crew = [name]
                prev_time = enter_time

            if len(current_crew) >= 2:
                crews.append(current_crew)

            return crews
        except Exception as e:
            logger.error(f"detect_crew failed: {e}")
            return []

    def get_all_visitors(self) -> list[dict]:
        """Return all visitors sorted by visit count descending."""
        try:
            with sqlite3.connect(DB_PATH) as conn:
                rows = conn.execute("""
                    SELECT person_name, COUNT(*) as visit_count,
                           MIN(enter_time) as first_visit,
                           MAX(enter_time) as last_visit
                    FROM party_visits
                    WHERE person_name != 'Unknown visitor'
                    GROUP BY person_name
                    ORDER BY visit_count DESC
                """).fetchall()
            return [
                {
                    "name": r[0],
                    "visit_count": r[1],
                    "first_visit": r[2],
                    "last_visit": r[3],
                }
                for r in rows
            ]
        except Exception as e:
            logger.error(f"get_all_visitors failed: {e}")
            return []
