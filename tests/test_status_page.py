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


# ---------------- Task 2: record_report ----------------

def test_record_report_valid(sp):
    sp.init_db(now=1000.0)
    result = sp.record_report("no_voice", ip_hash="aaa", now=2000.0)
    assert result == {"ok": True}
    with _conn(sp) as conn:
        rows = conn.execute(
            "SELECT created_at, client_ts, ip_hash, reason FROM status_reports").fetchall()
    assert rows == [(2000.0, None, "aaa", "no_voice")]


def test_record_report_invalid_reason(sp):
    sp.init_db(now=1000.0)
    result = sp.record_report("mario_is_ugly", ip_hash="aaa", now=2000.0)
    assert result == {"ok": False, "error": "invalid_reason"}


def test_record_report_rate_limited_same_ip(sp):
    sp.init_db(now=1000.0)
    assert sp.record_report("no_voice", ip_hash="aaa", now=2000.0)["ok"] is True
    result = sp.record_report("other", ip_hash="aaa", now=2030.0)
    assert result["ok"] is False
    assert result["error"] == "rate_limited"
    assert 0 < result["retry_after"] <= 61


def test_record_report_different_ip_not_limited(sp):
    sp.init_db(now=1000.0)
    assert sp.record_report("no_voice", ip_hash="aaa", now=2000.0)["ok"] is True
    assert sp.record_report("no_voice", ip_hash="bbb", now=2001.0)["ok"] is True


def test_record_report_offline_burst_spaced_client_ts_accepted(sp):
    """Offline-queue flush: 3 reports arrive back-to-back, client_ts 70s apart."""
    sp.init_db(now=1000.0)
    now = 5000.0
    for client_ts in (4700.0, 4770.0, 4840.0):
        result = sp.record_report("not_responding", client_ts=client_ts,
                                  ip_hash="aaa", now=now)
        assert result["ok"] is True, f"client_ts={client_ts} -> {result}"


def test_record_report_client_ts_clamped_future(sp):
    sp.init_db(now=1000.0)
    sp.record_report("other", client_ts=99999.0, ip_hash="aaa", now=2000.0)
    with _conn(sp) as conn:
        client_ts = conn.execute("SELECT client_ts FROM status_reports").fetchone()[0]
    assert client_ts == 2000.0  # clamped to now


def test_record_report_client_ts_clamped_ancient(sp):
    sp.init_db(now=1000.0)
    now = 200000.0
    sp.record_report("other", client_ts=1.0, ip_hash="aaa", now=now)
    with _conn(sp) as conn:
        client_ts = conn.execute("SELECT client_ts FROM status_reports").fetchone()[0]
    assert client_ts == now - sp.CLIENT_TS_MAX_AGE_SECONDS


def test_hash_ip_stable_and_short(sp):
    a = sp.hash_ip("203.0.113.7")
    assert a == sp.hash_ip("203.0.113.7")
    assert len(a) == 16
    assert a != sp.hash_ip("203.0.113.8")
    assert "203" not in a


def test_record_report_retro_near_prior_retro_rate_limited(sp):
    """Regression: rate limit must key on the NEAREST prior report, not the
    newest. Two retro reports 30s apart are limited even when both are far
    from the newest accepted report."""
    sp.init_db(now=1000.0)
    t0 = 100000.0
    assert sp.record_report("no_voice", ip_hash="aaa", now=t0)["ok"] is True
    assert sp.record_report("no_voice", client_ts=t0 - 3600, ip_hash="aaa",
                            now=t0 + 5)["ok"] is True
    result = sp.record_report("no_voice", client_ts=t0 - 3570, ip_hash="aaa",
                              now=t0 + 10)
    assert result["ok"] is False
    assert result["error"] == "rate_limited"


# ---------------- Task 3: get_status_data ----------------

def _set_party_start(sp, ts):
    with _conn(sp) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO party_meta (key, value) "
            "VALUES ('party_start_time', ?)", (str(ts),))


def test_status_data_reports_last_15min_window(sp):
    sp.init_db(now=1000.0)
    now = 100000.0
    sp.record_report("no_voice", ip_hash="a", now=now - 16 * 60)   # outside window
    sp.record_report("no_voice", ip_hash="b", now=now - 5 * 60)    # inside
    sp.record_report("other", ip_hash="c", now=now - 10)           # inside
    data = sp.get_status_data(now=now)
    assert data["reports_last_15min"] == 2


def test_status_data_buckets(sp):
    sp.init_db(now=1000.0)
    party_start = 10000.0
    _set_party_start(sp, party_start)
    now = party_start + 3 * 1800 + 10  # 4th bucket just began
    sp.record_report("no_voice", ip_hash="a", now=party_start + 100)          # bucket 0
    sp.record_report("no_voice", ip_hash="b", now=party_start + 200)          # bucket 0
    sp.record_report("no_voice", ip_hash="c", now=party_start + 1800 + 5)     # bucket 1
    data = sp.get_status_data(now=now)
    buckets = data["report_buckets"]
    assert len(buckets) == 4
    assert buckets[0] == {"bucket_start_ts": party_start, "count": 2}
    assert buckets[1] == {"bucket_start_ts": party_start + 1800, "count": 1}
    assert buckets[2]["count"] == 0
    assert buckets[3]["count"] == 0


def test_status_data_buckets_capped_at_48(sp):
    sp.init_db(now=1000.0)
    _set_party_start(sp, 0.0)
    now = 100 * 1800.0 - 1  # inside the 100th bucket (index 99)
    data = sp.get_status_data(now=now)
    assert len(data["report_buckets"]) == 48
    # Kept buckets are the most recent ones.
    assert data["report_buckets"][-1]["bucket_start_ts"] == 99 * 1800.0


def test_status_data_incidents_newest_first(sp):
    sp.init_db(now=1000.0)   # last_alive = 1000
    _set_party_start(sp, 500.0)
    sp.init_db(now=2000.0)   # incident A: 1000..2000
    sp.init_db(now=5000.0)   # incident B: 2000..5000
    data = sp.get_status_data(now=6000.0)
    assert [i["started_at"] for i in data["incidents"]] == [2000.0, 1000.0]
    assert data["incidents"][0]["kind"] == "server_down"


def test_status_data_character_follows_set_character(sp):
    sp.init_db(now=1000.0)
    sp.set_character("rudi", "Rudi")
    try:
        assert sp.get_status_data(now=2000.0)["character"] == "Rudi"
    finally:
        sp.set_character("mario", "Mario")


def test_status_data_incidents_scoped_to_party(sp):
    """Stale incidents from before the party (e.g. yesterday's dev restarts)
    must not show up in tonight's outage history."""
    sp.init_db(now=1000.0)
    sp.init_db(now=2000.0)      # stale incident 1000..2000, before party
    _set_party_start(sp, 3000.0)
    sp.init_db(now=5000.0)      # incident 2000..5000 ends after party start
    data = sp.get_status_data(now=6000.0)
    assert [i["started_at"] for i in data["incidents"]] == [2000.0]
