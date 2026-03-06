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
        self.party_start_time = time.time()
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(DB_PATH)
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
        """)
        conn.commit()
        conn.close()

    def record_enter(self, person_id: int = None, person_name: str = None) -> int:
        conn = sqlite3.connect(DB_PATH)
        try:
            cursor = conn.execute(
                "INSERT INTO party_visits (person_id, person_name) VALUES (?, ?)",
                (person_id, person_name or "Unknown visitor"),
            )
            visit_id = cursor.lastrowid
            conn.commit()
        except Exception as e:
            logger.error(f"record_enter failed: {e}")
            visit_id = -1
        finally:
            conn.close()
        if DEBUG_STATS:
            logger.info(f"[DEBUG_STATS] record_enter: visit_id={visit_id} name={person_name}")
        return visit_id

    def record_exit(self, visit_id: int):
        conn = sqlite3.connect(DB_PATH)
        try:
            conn.execute("""
                UPDATE party_visits 
                SET exit_time = CURRENT_TIMESTAMP,
                    duration_seconds = (julianday(CURRENT_TIMESTAMP) - julianday(enter_time)) * 86400
                WHERE id = ? AND exit_time IS NULL
            """, (visit_id,))
            conn.commit()
        except Exception as e:
            logger.error(f"record_exit failed: {e}")
        finally:
            conn.close()

    def record_event(self, event_type: str, details: str = None):
        conn = sqlite3.connect(DB_PATH)
        try:
            conn.execute(
                "INSERT INTO party_events (event_type, details) VALUES (?, ?)",
                (event_type, details),
            )
            conn.commit()
        except Exception as e:
            logger.error(f"record_event failed: {e}")
        finally:
            conn.close()

    def get_stats(self) -> dict:
        """Get all party statistics."""
        conn = sqlite3.connect(DB_PATH)
        try:
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
        finally:
            conn.close()

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
            "last_visitor": recent["person_name"] if recent else None,
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
