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
            "SELECT MAX(COALESCE(client_ts, created_at)) FROM status_reports "
            "WHERE ip_hash = ?", (ip_hash,)).fetchone()
        last_effective = row[0] if row else None
        if last_effective is not None:
            gap = abs(effective_ts - float(last_effective))
            if gap < RATE_LIMIT_SECONDS:
                return {"ok": False, "error": "rate_limited",
                        "retry_after": int(RATE_LIMIT_SECONDS - gap) + 1}
        conn.execute(
            "INSERT INTO status_reports (created_at, client_ts, ip_hash, reason) "
            "VALUES (?, ?, ?, ?)", (now, stored_client_ts, ip_hash, reason))
    return {"ok": True}
