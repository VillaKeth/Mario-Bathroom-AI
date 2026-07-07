"""Tests for server/status_page.py — status page backend (reports, incidents, heartbeat)."""
import os
import sqlite3
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

import status_page


@pytest.fixture()
def sp(tmp_path, monkeypatch):
    """status_page module pointed at a throwaway DB."""
    monkeypatch.setattr(status_page, "DB_PATH", str(tmp_path / "test_memory.db"))
    return status_page


def _conn(sp):
    return sqlite3.connect(sp.DB_PATH)


# ---------------- Task 1: init / heartbeat / incidents ----------------

def test_init_db_creates_tables(sp):
    sp.init_db(now=1000.0)
    with _conn(sp) as conn:
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert "status_reports" in tables
    assert "status_incidents" in tables
    assert "party_meta" in tables


def test_init_db_fresh_db_no_incident(sp):
    sp.init_db(now=1000.0)
    with _conn(sp) as conn:
        count = conn.execute("SELECT COUNT(*) FROM status_incidents").fetchone()[0]
    assert count == 0


def test_init_db_stale_heartbeat_creates_incident(sp):
    sp.init_db(now=1000.0)          # writes last_alive = 1000
    sp.init_db(now=1500.0)          # gap 500s > 90s -> incident 1000..1500
    with _conn(sp) as conn:
        rows = conn.execute(
            "SELECT started_at, ended_at, kind FROM status_incidents").fetchall()
    assert rows == [(1000.0, 1500.0, "server_down")]


def test_init_db_recent_heartbeat_no_false_positive(sp):
    sp.init_db(now=1000.0)
    sp.init_db(now=1050.0)          # gap 50s < 90s -> clean restart, no incident
    with _conn(sp) as conn:
        count = conn.execute("SELECT COUNT(*) FROM status_incidents").fetchone()[0]
    assert count == 0


def test_heartbeat_updates_last_alive(sp):
    sp.init_db(now=1000.0)
    sp.heartbeat(now=2000.0)
    with _conn(sp) as conn:
        val = conn.execute(
            "SELECT value FROM party_meta WHERE key='status_last_alive'").fetchone()[0]
    assert float(val) == 2000.0
