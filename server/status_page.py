"""Status page backend: guest problem reports, downtime incidents, heartbeat.

Public downdetector-style page is served at GET /status (server/static/status.html).
This module owns the SQLite tables and all logic; server/main.py wires thin
endpoints to it. No watchdog involvement: downtime is derived from a heartbeat
timestamp gap at startup.
"""
import asyncio
import hashlib
import os
import sqlite3
import time

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "memory.db")

DEBUG_STATUS = True

_CHARACTER_NAME = "mario"
_CHARACTER_DISPLAY_NAME = "Mario"

VALID_REASONS = ("no_voice", "not_responding", "wrong_behavior", "other")
RATE_LIMIT_SECONDS = 60.0
HEARTBEAT_INTERVAL_SECONDS = 30.0
HEARTBEAT_GAP_SECONDS = 90.0
CLIENT_TS_MAX_AGE_SECONDS = 86400.0
REPORTS_WINDOW_SECONDS = 15 * 60.0
BUCKET_SECONDS = 30 * 60.0
MAX_BUCKETS = 48
MAX_INCIDENTS_LISTED = 50


def set_character(name: str, display_name: str) -> None:
    global _CHARACTER_NAME, _CHARACTER_DISPLAY_NAME
    _CHARACTER_NAME = name
    _CHARACTER_DISPLAY_NAME = display_name


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db(now: float = None) -> None:
    """Create tables; turn a stale heartbeat into a downtime incident; stamp alive."""
    now = time.time() if now is None else now
    with _connect() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS status_reports (
            id INTEGER PRIMARY KEY,
            created_at REAL NOT NULL,
            client_ts REAL,
            ip_hash TEXT NOT NULL,
            reason TEXT NOT NULL
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS status_incidents (
            id INTEGER PRIMARY KEY,
            started_at REAL NOT NULL,
            ended_at REAL NOT NULL,
            kind TEXT NOT NULL
        )""")
        # Same shape party_stats.py uses; IF NOT EXISTS is a no-op on the live DB.
        conn.execute("""CREATE TABLE IF NOT EXISTS party_meta (
            key TEXT PRIMARY KEY,
            value TEXT
        )""")
        row = conn.execute(
            "SELECT value FROM party_meta WHERE key = 'status_last_alive'").fetchone()
        if row:
            try:
                last_alive = float(row[0])
            except (TypeError, ValueError):
                last_alive = 0.0
            if last_alive > 0 and (now - last_alive) > HEARTBEAT_GAP_SECONDS:
                conn.execute(
                    "INSERT INTO status_incidents (started_at, ended_at, kind) "
                    "VALUES (?, ?, ?)",
                    (last_alive, now, "server_down"))
                if DEBUG_STATUS:
                    print(f"[status_page] downtime incident recorded: "
                          f"{now - last_alive:.0f}s gap")
        conn.execute(
            "INSERT OR REPLACE INTO party_meta (key, value) "
            "VALUES ('status_last_alive', ?)", (str(now),))


def heartbeat(now: float = None) -> None:
    now = time.time() if now is None else now
    try:
        with _connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO party_meta (key, value) "
                "VALUES ('status_last_alive', ?)", (str(now),))
    except Exception as e:
        print(f"[status_page] heartbeat write failed: {e}")


async def heartbeat_loop() -> None:
    while True:
        heartbeat()
        await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)


def hash_ip(ip: str) -> str:
    """Store only a short hash of the reporter IP, never the raw address."""
    return hashlib.sha256((ip or "unknown").encode("utf-8")).hexdigest()[:16]


def record_report(reason: str, client_ts: float = None, ip_hash: str = "",
                  now: float = None) -> dict:
    """Record one guest report. Rate limit is keyed on EFFECTIVE report time
    (client_ts when supplied, else arrival time) so an offline-queue flush of
    retro-timestamped reports does not trip the limit."""
    now = time.time() if now is None else now
    if reason not in VALID_REASONS:
        return {"ok": False, "error": "invalid_reason"}
    stored_client_ts = None
    effective_ts = now
    if client_ts is not None:
        try:
            effective_ts = float(client_ts)
        except (TypeError, ValueError):
            effective_ts = now
        # Sanity clamp: not in the future, not older than 24h.
        effective_ts = max(now - CLIENT_TS_MAX_AGE_SECONDS, min(effective_ts, now))
        stored_client_ts = effective_ts
    with _connect() as conn:
        row = conn.execute(
            "SELECT MIN(ABS(COALESCE(client_ts, created_at) - ?)) "
            "FROM status_reports WHERE ip_hash = ?",
            (effective_ts, ip_hash)).fetchone()
        min_gap = row[0] if row and row[0] is not None else None
        if min_gap is not None and min_gap < RATE_LIMIT_SECONDS:
            return {"ok": False, "error": "rate_limited",
                    "retry_after": int(RATE_LIMIT_SECONDS - min_gap) + 1}
        conn.execute(
            "INSERT INTO status_reports (created_at, client_ts, ip_hash, reason) "
            "VALUES (?, ?, ?, ?)", (now, stored_client_ts, ip_hash, reason))
    return {"ok": True}


def _get_party_start(conn, now: float) -> float:
    row = conn.execute(
        "SELECT value FROM party_meta WHERE key = 'party_start_time'").fetchone()
    if row:
        try:
            return float(row[0])
        except (TypeError, ValueError):
            pass
    return now


def get_status_data(now: float = None) -> dict:
    """Everything the status page shows besides /health: tallies + incidents."""
    now = time.time() if now is None else now
    with _connect() as conn:
        party_start = _get_party_start(conn, now)
        window_start = now - REPORTS_WINDOW_SECONDS
        recent = conn.execute(
            "SELECT COUNT(*) FROM status_reports "
            "WHERE COALESCE(client_ts, created_at) >= ?", (window_start,)).fetchone()[0]
        rows = conn.execute(
            "SELECT COALESCE(client_ts, created_at) FROM status_reports "
            "WHERE COALESCE(client_ts, created_at) >= ?", (party_start,)).fetchall()
        counts = {}
        for (ts,) in rows:
            idx = int((ts - party_start) // BUCKET_SECONDS)
            if idx >= 0:
                counts[idx] = counts.get(idx, 0) + 1
        n_buckets = max(int((now - party_start) // BUCKET_SECONDS) + 1, 1)
        first_idx = max(0, n_buckets - MAX_BUCKETS)
        report_buckets = [
            {"bucket_start_ts": party_start + i * BUCKET_SECONDS,
             "count": counts.get(i, 0)}
            for i in range(first_idx, n_buckets)]
        incidents = [
            {"started_at": s, "ended_at": e, "kind": k}
            for (s, e, k) in conn.execute(
                "SELECT started_at, ended_at, kind FROM status_incidents "
                "WHERE ended_at >= ? "
                "ORDER BY started_at DESC LIMIT ?",
                (party_start, MAX_INCIDENTS_LISTED)).fetchall()]
    return {
        "character": _CHARACTER_DISPLAY_NAME,
        "reports_last_15min": recent,
        "report_buckets": report_buckets,
        "incidents": incidents,
    }
