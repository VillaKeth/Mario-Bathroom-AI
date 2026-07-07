# Status Page (Downdetector) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Public Statuspage/downdetector-style page at `/status` — guests check whether the AI is up/degraded/down and report problems; reports are tallied with a timeline of real outages.

**Architecture:** New module `server/status_page.py` owns all logic (SQLite tables, report recording + rate limit, aggregation, heartbeat, incident derivation). `server/main.py` gets three thin endpoints (`GET /status`, `GET /status/data`, `POST /status/report`) plus lifespan wiring. One static page `server/static/status.html` polls `/health` (existing) and `/status/data`, with a localStorage offline-report queue. No new processes; watchdog untouched.

**Tech Stack:** FastAPI (existing app in `server/main.py`), sqlite3 (WAL, `server/data/memory.db`), vanilla HTML/JS/CSS (no frameworks — same style as `server/static/control.html`), pytest.

**Spec:** `docs/superpowers/specs/2026-07-07-status-page-design.md`

## Global Constraints

- `print()` for logging, NOT `logger`.
- Character-agnostic user-visible text; modules expose `set_character(name, display_name)` + `_CHARACTER_NAME`/`_CHARACTER_DISPLAY_NAME` fallbacks.
- No ellipsis (`...`) in hardcoded strings.
- Debug flag `DEBUG_STATUS = True` (convention: default True for new features).
- Git: `git add <specific files>` only (never `-A`). Commit trailer: `Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>`.
- Report reasons are a fixed enum — NO free text (public endpoint over tunnel).
- Rate limit keyed on **effective report time** (`client_ts` if supplied else arrival), 60 s per IP.
- Tests live in `tests/`, import via `sys.path.insert(0, .../server)` then bare module import (see `tests/test_party_modules.py:8`).
- The test suite has ~24 pre-existing failures unrelated to this feature — the bar is NO NEW failures.
- Working dir: `C:\Users\Vketh\Desktop\Mario_AI`. Run pytest via `venv`: `venv\Scripts\python.exe -m pytest`.

## File Structure

- **Create** `server/status_page.py` — all status-page logic. One responsibility: report/incident/heartbeat persistence + aggregation.
- **Create** `server/static/status.html` — the public page (self-contained HTML+CSS+JS).
- **Create** `tests/test_status_page.py` — module tests (main.py has no endpoint unit tests by repo convention — endpoints are thin glue, verified live in Task 6).
- **Modify** `server/main.py` — 3 endpoints + 3 wiring lines (import, lifespan init + heartbeat task, set_character).

---

### Task 1: `status_page.py` core — tables, heartbeat, incident derivation

**Files:**
- Create: `server/status_page.py`
- Test: `tests/test_status_page.py`

**Interfaces:**
- Consumes: nothing (only stdlib + `server/data/memory.db` path convention from `server/memory.py:13`).
- Produces (later tasks rely on these exact names):
  - `DB_PATH: str` (module global, monkeypatchable)
  - `init_db(now: float | None = None) -> None`
  - `heartbeat(now: float | None = None) -> None`
  - `async heartbeat_loop() -> None`
  - `set_character(name: str, display_name: str) -> None`
  - constants: `HEARTBEAT_GAP_SECONDS = 90.0`, `HEARTBEAT_INTERVAL_SECONDS = 30.0`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_status_page.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `venv\Scripts\python.exe -m pytest tests/test_status_page.py -v`
Expected: FAIL at import — `ModuleNotFoundError: No module named 'status_page'`

- [ ] **Step 3: Write minimal implementation**

Create `server/status_page.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `venv\Scripts\python.exe -m pytest tests/test_status_page.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add server/status_page.py tests/test_status_page.py
git commit -m "feat(status): status_page module - tables, heartbeat, incident derivation

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 2: `record_report` — validation, clamping, effective-time rate limit

**Files:**
- Modify: `server/status_page.py` (append after `heartbeat_loop`)
- Test: `tests/test_status_page.py` (append)

**Interfaces:**
- Consumes: `init_db`, `DB_PATH`, constants from Task 1.
- Produces:
  - `record_report(reason: str, client_ts: float | None = None, ip_hash: str = "", now: float | None = None) -> dict` — returns `{"ok": True}` or `{"ok": False, "error": "invalid_reason"}` or `{"ok": False, "error": "rate_limited", "retry_after": int}`
  - `hash_ip(ip: str) -> str` — sha256 hex, first 16 chars

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_status_page.py`:

```python
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


def test_hash_ip_stable_and_short(sp):
    a = sp.hash_ip("203.0.113.7")
    assert a == sp.hash_ip("203.0.113.7")
    assert len(a) == 16
    assert a != sp.hash_ip("203.0.113.8")
    assert "203" not in a
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `venv\Scripts\python.exe -m pytest tests/test_status_page.py -v -k "record_report or hash_ip"`
Expected: FAIL — `AttributeError: module 'status_page' has no attribute 'record_report'`

- [ ] **Step 3: Write minimal implementation**

Append to `server/status_page.py`:

```python
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
        # Nearest prior report, not the newest: a MAX-based check lets retro
        # reports slip through once any newer report exists for the IP.
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `venv\Scripts\python.exe -m pytest tests/test_status_page.py -v`
Expected: 14 passed

- [ ] **Step 5: Commit**

```bash
git add server/status_page.py tests/test_status_page.py
git commit -m "feat(status): record_report with reason enum, ts clamp, effective-time rate limit

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 3: `get_status_data` — tally, buckets, incidents, character

**Files:**
- Modify: `server/status_page.py` (append)
- Test: `tests/test_status_page.py` (append)

**Interfaces:**
- Consumes: Tasks 1-2 (`init_db`, `record_report`, constants, `_connect`).
- Produces:
  - `get_status_data(now: float | None = None) -> dict` with keys:
    - `character: str` (display name)
    - `reports_last_15min: int`
    - `report_buckets: list[{"bucket_start_ts": float, "count": int}]` (30-min buckets from party start, last 48 max)
    - `incidents: list[{"started_at": float, "ended_at": float, "kind": str}]` (newest first, max 50)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_status_page.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `venv\Scripts\python.exe -m pytest tests/test_status_page.py -v -k "status_data"`
Expected: FAIL — `AttributeError: module 'status_page' has no attribute 'get_status_data'`

- [ ] **Step 3: Write minimal implementation**

Append to `server/status_page.py`:

```python
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
                "ORDER BY started_at DESC LIMIT ?", (MAX_INCIDENTS_LISTED,)).fetchall()]
    return {
        "character": _CHARACTER_DISPLAY_NAME,
        "reports_last_15min": recent,
        "report_buckets": report_buckets,
        "incidents": incidents,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `venv\Scripts\python.exe -m pytest tests/test_status_page.py -v`
Expected: 19 passed

- [ ] **Step 5: Commit**

```bash
git add server/status_page.py tests/test_status_page.py
git commit -m "feat(status): get_status_data - 15min tally, 30min buckets, incident list

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 4: Wire endpoints + lifespan into `server/main.py`

**Files:**
- Modify: `server/main.py` — import block, lifespan (~line 1134 and ~line 1228), set_character block (~line 777), routes near `/control` (~line 2289)

**Interfaces:**
- Consumes (Tasks 1-3): `status_page.init_db()`, `status_page.heartbeat_loop()`, `status_page.set_character(name, display_name)`, `status_page.get_status_data()`, `status_page.record_report(reason=..., client_ts=..., ip_hash=...)`, `status_page.hash_ip(ip)`.
- Produces: HTTP surface used by Task 5's page — `GET /status` (HTML), `GET /status/data` (JSON), `POST /status/report` (JSON; 200/400/429).

No unit tests in this task by design: `server/main.py` has no endpoint unit tests (repo convention — heavy import side effects); endpoints are thin delegation, verified live in Task 6.

- [ ] **Step 1: Add import**

In `server/main.py`, find the block of sibling-module imports (near the top, where `memory`, `party_stats`, `emotions` etc. are imported) and add in alphabetical position:

```python
import status_page
```

(Match the existing import style exactly — if siblings are imported as `import memory`, use `import status_page`; if `from server import memory`, mirror that.)

- [ ] **Step 2: Wire lifespan init + heartbeat task**

In the `lifespan` function: directly AFTER the `memory.init_memory()` call (~line 1134), add:

```python
    try:
        status_page.init_db()
    except Exception as e:
        print(f"[status_page] init failed (page will still serve): {e}")
```

Near the other background task spawns (~line 1228, next to `_memory_task = asyncio.create_task(_memory_maintenance_loop())`), add:

```python
    asyncio.create_task(status_page.heartbeat_loop())
```

- [ ] **Step 3: Wire set_character**

Next to `command_handlers.set_character(_character.name, _character.display_name)` (~line 777), add:

```python
    status_page.set_character(_character.name, _character.display_name)
```

- [ ] **Step 4: Add the three routes**

Add directly below the `/control` route block (after ~line 2303). `HTMLResponse` is already imported (used by `/control`); check `JSONResponse` is imported from `fastapi.responses` — add it to that import if missing. `Request` is already imported (used at line 2539).

```python
_STATUS_HTML_PATH = os.path.join(os.path.dirname(__file__), "static", "status.html")


@app.get("/status")
async def status_page_route():
    """Public downdetector-style status page. No auth, no secrets on the page."""
    try:
        with open(_STATUS_HTML_PATH, encoding="utf-8") as f:
            return HTMLResponse(f.read())
    except Exception:
        return HTMLResponse("<h1>status page missing</h1>", status_code=500)


@app.get("/status/data")
async def status_data_route():
    """Report tallies + incident timeline (kept off the /health hot path)."""
    return status_page.get_status_data()


@app.post("/status/report")
async def status_report_route(request: Request):
    """Guest problem report. Preset reason enum only, rate limited per IP."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    forwarded = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    ip = forwarded or (request.client.host if request.client else "unknown")
    result = status_page.record_report(
        reason=body.get("reason"),
        client_ts=body.get("client_ts"),
        ip_hash=status_page.hash_ip(ip),
    )
    if result.get("ok"):
        return {"status": "ok"}
    if result.get("error") == "invalid_reason":
        return JSONResponse({"error": "invalid_reason"}, status_code=400)
    return JSONResponse(
        {"error": "rate_limited", "retry_after": result.get("retry_after", 60)},
        status_code=429)
```

- [ ] **Step 5: Syntax check**

Run: `venv\Scripts\python.exe -m py_compile server/main.py server/status_page.py`
Expected: exit 0, no output

- [ ] **Step 6: Commit**

```bash
git add server/main.py
git commit -m "feat(status): wire /status, /status/data, /status/report endpoints + heartbeat

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 5: `status.html` — the public page

**Files:**
- Create: `server/static/status.html`

**Interfaces:**
- Consumes: `GET /health` (fields: `degradation_tier`, `llm`, `tts`, `stt`, `uptime_seconds`), `GET /status/data`, `POST /status/report` (Task 4 shapes).
- Produces: the page itself. Behavior contract: poll `/health` 10 s (5 s while unreachable, flip after 2 consecutive failures), poll `/status/data` 30 s, localStorage queue `status_report_queue` (cap 10), 60 s button cooldown.

- [ ] **Step 1: Write the page**

Create `server/static/status.html` (self-contained; same dark card theme as `control.html`):

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Party Bot — Status</title>
<style>
  :root { --bg:#13131f; --card:#1e1e2e; --edge:#33334d; --txt:#e6e6f0; --muted:#9a9ab0;
          --accent:#7c5cff; --good:#2ecc71; --warn:#f1c40f; --bad:#ff6b6b; --off:#44445a; }
  * { box-sizing:border-box; }
  body { margin:0 auto; font-family:system-ui,Segoe UI,Roboto,sans-serif; background:var(--bg);
         color:var(--txt); padding:14px; max-width:560px; }
  .banner { border-radius:14px; padding:22px 16px; text-align:center; margin-bottom:14px;
            border:1px solid var(--edge); background:var(--card); }
  .banner .state { font-size:26px; font-weight:800; letter-spacing:.5px; }
  .banner.up .state { color:var(--good); }
  .banner.degraded .state { color:var(--warn); }
  .banner.down .state { color:var(--bad); }
  .banner .sub { color:var(--muted); font-size:13px; margin-top:6px; }
  .card { background:var(--card); border:1px solid var(--edge); border-radius:12px;
          padding:12px 14px; margin-bottom:12px; }
  .card h2 { font-size:14px; margin:0 0 8px; color:var(--muted); font-weight:600; }
  .row { display:flex; align-items:center; justify-content:space-between;
         padding:8px 2px; border-bottom:1px solid #26263a; font-size:14px; }
  .row:last-child { border-bottom:none; }
  .dot { width:10px; height:10px; border-radius:50%; background:var(--off); display:inline-block; }
  .dot.ok { background:var(--good); }
  .dot.slow { background:var(--warn); }
  .dot.failed { background:var(--bad); }
  .reasons { display:grid; grid-template-columns:1fr 1fr; gap:8px; }
  .reasons button { cursor:pointer; border:none; border-radius:10px; padding:12px 8px;
                    font-size:14px; font-weight:600; background:#2a2a3d; color:var(--txt); }
  .reasons button:disabled { opacity:.4; cursor:not-allowed; }
  #reportMsg { font-size:12px; color:var(--muted); margin-top:8px; min-height:16px; }
  .bars { display:flex; align-items:flex-end; gap:2px; height:64px; margin-top:6px; }
  .bars .bar { flex:1; background:var(--accent); border-radius:2px 2px 0 0; min-height:2px; }
  .bars .bar.empty { background:#2a2a3d; }
  .tally { font-size:22px; font-weight:800; }
  .incident { font-size:13px; padding:6px 2px; border-bottom:1px solid #26263a; color:var(--muted); }
  .incident:last-child { border-bottom:none; }
  .muted { color:var(--muted); font-size:13px; }
</style>
</head>
<body>
  <div class="banner" id="banner">
    <div class="state" id="bannerState">CHECKING</div>
    <div class="sub" id="bannerSub">Contacting the party bot</div>
  </div>

  <div class="card">
    <h2>COMPONENTS</h2>
    <div class="row"><span>Brain (thinking)</span><span class="dot" id="dot-llm"></span></div>
    <div class="row"><span>Voice (speaking)</span><span class="dot" id="dot-tts"></span></div>
    <div class="row"><span>Ears (listening)</span><span class="dot" id="dot-stt"></span></div>
    <div class="row"><span>Awake for</span><span class="muted" id="uptime">-</span></div>
  </div>

  <div class="card">
    <h2>SOMETHING BROKEN? TELL US</h2>
    <div class="reasons" id="reasons">
      <button data-reason="not_responding">Not responding</button>
      <button data-reason="no_voice">No voice</button>
      <button data-reason="wrong_behavior">Acting weird</button>
      <button data-reason="other">Something else</button>
    </div>
    <div id="reportMsg"></div>
  </div>

  <div class="card">
    <h2>GUEST REPORTS</h2>
    <div class="tally"><span id="recentCount">0</span> <span class="muted">in the last 15 minutes</span></div>
    <div class="bars" id="bars"></div>
    <div class="muted" id="barsLabel">Reports per 30 minutes tonight</div>
  </div>

  <div class="card">
    <h2>OUTAGE HISTORY</h2>
    <div id="incidents" class="muted">No outages recorded tonight</div>
  </div>

<script>
(function () {
  "use strict";
  var QUEUE_KEY = "status_report_queue";
  var QUEUE_CAP = 10;
  var failCount = 0;
  var cooldownUntil = 0;
  var characterName = "the party bot";

  function $(id) { return document.getElementById(id); }

  function fmtDuration(s) {
    s = Math.max(0, Math.floor(s));
    var h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60);
    return h > 0 ? h + "h " + m + "m" : m + "m";
  }
  function fmtClock(ts) {
    var d = new Date(ts * 1000);
    return ("0" + d.getHours()).slice(-2) + ":" + ("0" + d.getMinutes()).slice(-2);
  }

  function setBanner(cls, state, sub) {
    $("banner").className = "banner " + cls;
    $("bannerState").textContent = state;
    $("bannerSub").textContent = sub;
  }
  function setDot(id, status) {
    var cls = "dot";
    if (status === "ok") cls += " ok";
    else if (status === "slow") cls += " slow";
    else if (status) cls += " failed";
    $(id).className = cls;
  }

  function renderHealth(h) {
    setDot("dot-llm", h.llm);
    setDot("dot-tts", h.tts);
    setDot("dot-stt", h.stt);
    $("uptime").textContent = fmtDuration(h.uptime_seconds || 0);
    if (h.degradation_tier === "FULL") {
      setBanner("up", characterName.toUpperCase() + " IS UP",
                "All systems go");
    } else {
      setBanner("degraded", "DEGRADED",
                "Partially working (" + (h.degradation_tier || "unknown") + ")");
    }
  }
  function renderDown() {
    setBanner("down", "UNREACHABLE",
              "Cannot reach the server. Reports are saved and sent when it returns.");
    setDot("dot-llm", "failed");
    setDot("dot-tts", "failed");
    setDot("dot-stt", "failed");
  }

  function pollHealth() {
    fetch("/health", { cache: "no-store" })
      .then(function (r) { if (!r.ok) throw new Error("bad"); return r.json(); })
      .then(function (h) {
        failCount = 0;
        renderHealth(h);
        flushQueue();
        setTimeout(pollHealth, 10000);
      })
      .catch(function () {
        failCount += 1;
        if (failCount >= 2) renderDown();
        setTimeout(pollHealth, 5000);
      });
  }

  function renderData(d) {
    if (d.character) characterName = d.character;
    $("recentCount").textContent = d.reports_last_15min;
    var bars = $("bars");
    bars.innerHTML = "";
    var max = 1;
    d.report_buckets.forEach(function (b) { if (b.count > max) max = b.count; });
    d.report_buckets.forEach(function (b) {
      var el = document.createElement("div");
      el.className = "bar" + (b.count === 0 ? " empty" : "");
      el.style.height = Math.max(3, Math.round(b.count / max * 100)) + "%";
      el.title = fmtClock(b.bucket_start_ts) + " - " + b.count + " reports";
      bars.appendChild(el);
    });
    var inc = $("incidents");
    if (!d.incidents.length) {
      inc.textContent = "No outages recorded tonight";
    } else {
      inc.innerHTML = "";
      d.incidents.forEach(function (i) {
        var mins = Math.max(1, Math.round((i.ended_at - i.started_at) / 60));
        var el = document.createElement("div");
        el.className = "incident";
        el.textContent = "Down " + fmtClock(i.started_at) + " - " +
                         fmtClock(i.ended_at) + " (" + mins + " min)";
        inc.appendChild(el);
      });
    }
  }

  function pollData() {
    fetch("/status/data", { cache: "no-store" })
      .then(function (r) { if (!r.ok) throw new Error("bad"); return r.json(); })
      .then(renderData)
      .catch(function () { /* health poll owns the down state */ })
      .then(function () { setTimeout(pollData, 30000); });
  }

  function loadQueue() {
    try { return JSON.parse(localStorage.getItem(QUEUE_KEY) || "[]"); }
    catch (e) { return []; }
  }
  function saveQueue(q) {
    try { localStorage.setItem(QUEUE_KEY, JSON.stringify(q.slice(-QUEUE_CAP))); }
    catch (e) { /* storage full or blocked - drop */ }
  }

  function postReport(reason, clientTs) {
    return fetch("/status/report", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reason: reason, client_ts: clientTs })
    });
  }

  function flushQueue() {
    var q = loadQueue();
    if (!q.length) return;
    var item = q[0];
    postReport(item.reason, item.client_ts).then(function (r) {
      if (r.ok || r.status === 400 || r.status === 429) {
        q.shift();           // delivered or permanently unwanted - drop it
        saveQueue(q);
        if (q.length) flushQueue();
      }
    }).catch(function () { /* still down - retry on next successful poll */ });
  }

  function startCooldown(seconds, msg) {
    cooldownUntil = Date.now() + seconds * 1000;
    var buttons = $("reasons").querySelectorAll("button");
    buttons.forEach(function (b) { b.disabled = true; });
    $("reportMsg").textContent = msg;
    setTimeout(function () {
      buttons.forEach(function (b) { b.disabled = false; });
      $("reportMsg").textContent = "";
    }, seconds * 1000);
  }

  $("reasons").addEventListener("click", function (ev) {
    var btn = ev.target.closest("button");
    if (!btn || Date.now() < cooldownUntil) return;
    var reason = btn.getAttribute("data-reason");
    var clientTs = Date.now() / 1000;
    postReport(reason, clientTs).then(function (r) {
      if (r.ok) {
        startCooldown(60, "Thanks, report received");
        pollData();
      } else if (r.status === 429) {
        r.json().then(function (j) {
          startCooldown(j.retry_after || 60, "Easy there, one report per minute");
        });
      } else {
        startCooldown(10, "Report failed, try again in a moment");
      }
    }).catch(function () {
      var q = loadQueue();
      q.push({ reason: reason, client_ts: clientTs });
      saveQueue(q);
      startCooldown(60, "Server unreachable, report saved and will send later");
    });
  });

  pollHealth();
  pollData();
})();
</script>
</body>
</html>
```

- [ ] **Step 2: Sanity check the page renders**

The route reads the file per request, but the route itself is new — full live check happens after a server restart in Task 6. For now open `server/static/status.html` directly from disk in a browser: layout renders, banner shows CHECKING (fetches fail on file:// — expected).

- [ ] **Step 3: Commit**

```bash
git add server/static/status.html
git commit -m "feat(status): public status page - banner, components, reports, outage history

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 6: Full-suite + live verification

**Files:** none new. Verification only.

**Interfaces:**
- Consumes: everything from Tasks 1-5.
- Produces: verified feature; no new test failures.

- [ ] **Step 1: Full pytest suite**

Run: `venv\Scripts\python.exe -m pytest tests/ -q` (no `-x` — pre-existing failures exist)
Expected: `tests/test_status_page.py` all pass; total failures ≤ the pre-existing ~24, no NEW failures (if unsure, compare failure names against a baseline run of the same command with this feature's commits stashed).

- [ ] **Step 2: Start server + live checks** (foreground per machine-reaps-processes note, or normal start script)

1. Start server (`start_server.bat` or existing session procedure).
2. Open `http://localhost:8765/status` — banner goes UP (or DEGRADED), component dots colored, uptime ticking.
3. Tap "No voice" — `reportMsg` shows thanks; GUEST REPORTS tally increments within 30 s; tap again — cooldown message.
4. `curl -X POST http://localhost:8765/status/report -H "Content-Type: application/json" -d "{\"reason\":\"bogus\"}"` → 400 invalid_reason.
5. Kill server process — open tab flips to UNREACHABLE within ~20 s (2 failed polls).
6. While down, tap a report — message says saved for later; localStorage `status_report_queue` non-empty (DevTools).
7. Restart server — tab recovers to UP, queued report flushes (tally +1), OUTAGE HISTORY shows the downtime window with sane times.
8. Audio rule check (`.claude/rules/testing.md`): feature has no TTS path — confirm no TTS/audio regressions by sending one normal chat message and verifying `_play_wav: playing` + `_play_wav: done` in client logs.

- [ ] **Step 3: Update docs**

Add `/status`, `/status/data`, `/status/report` to the Admin Endpoints table in `.claude/CLAUDE.md` (they are public, note that), and tick TODO.md if it tracks this feature.

- [ ] **Step 4: Commit docs**

```bash
git add .claude/CLAUDE.md TODO.md
git commit -m "docs: document /status page endpoints

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```
