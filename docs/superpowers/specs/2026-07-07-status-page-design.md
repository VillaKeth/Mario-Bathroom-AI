# Status Page ("Downdetector") — Design

**Date:** 2026-07-07
**Status:** Approved (brainstorm complete)

## Purpose

Public Statuspage/downdetector-style page for the party AI. Guests and the owner
check whether the AI is up, degraded, or down, and guests can report problems.
Reports are tallied and shown as a timeline, downdetector-style. No auth required.

## Audience

- Party guests on phones, via the existing ngrok tunnel (stable link/QR).
- Owner uses the same page; no secrets on it.

## Architecture

Approach chosen: **status page hosted on the main FastAPI server** (`server/main.py`).

- One static page + two new endpoints + two SQLite tables + a heartbeat task.
- No new processes. No watchdog changes. Stable URL through the existing tunnel.
- Known trade-off: a fresh page load during a full outage shows the ngrok 502
  page instead of ours. Open tabs detect outages client-side; offline reports
  queue in localStorage. Accepted for v1.

Rejected alternatives:
- Watchdog-hosted separate status server: survives server death fully, but the
  second ngrok tunnel URL changes every restart (QR rot) and it fattens the
  watchdog, which must stay simple.
- External static hosting (GitHub Pages) + CORS polling: always loads, but
  reports/timeline still need the server up; extra publish step; overkill.

## Components

### 1. Page — `GET /status`

- Serves `server/static/status.html` (same pattern as `/control`).
- Mobile-first, party-themed, character-agnostic wording. Active character
  display name comes from `/status/data`.
- Sections:
  - **Banner:** 🟢 UP / 🟡 DEGRADED / 🔴 UNREACHABLE.
  - **Component rows:** Brain (`llm`), Voice (`tts`), Ears (`stt`) with
    green/yellow/red dots, from existing `/health` fields; overall state from
    `degradation_tier`.
  - **Uptime line:** from `uptime_seconds`.
  - **Reports:** count in last 15 minutes + per-30-minute bar chart over the night.
  - **Incidents:** list of outage windows ("Down 22:14–22:17 · 3 min").
  - **Report button:** "It's broken for me" with preset reason picker.

### 2. Page JS polling

- Poll `/health` every 10 s (same-origin — no CORS changes).
- 2 consecutive failures → banner UNREACHABLE; switch to 5 s polls until recovery.
- Poll `/status/data` every 30 s for tallies/incidents.

### 3. New endpoint — `GET /status/data`

Returns JSON:
- `character`: active character display name.
- `reports_last_15min`: int.
- `report_buckets`: list of `{bucket_start_ts, count}` per 30-minute bucket
  covering the party so far.
- `incidents`: list of `{started_at, ended_at, kind}`, scoped to the current
  party (`ended_at >= party_start_time`) so stale incidents from earlier days
  never render as tonight's outages.

Kept separate from `/health` so report-aggregation SQL stays off the hot path
(watchdog and client poll `/health`).

### 4. New endpoint — `POST /status/report`

- Body: `{ "reason": str, "client_ts": float | null }`.
- `reason` must be one of: `no_voice`, `not_responding`, `wrong_behavior`,
  `other`. **No free text** — public write endpoint over the tunnel; preset
  enums remove the abuse surface. Server-side validation; unknown reason → 400.
- Rate limit: 1 report per IP per 60 s, keyed on **effective report time**
  (`client_ts` when supplied, else arrival time) → 429 with cooldown message.
  Keying on effective time lets an offline-queue flush deliver several
  retro-timestamped reports in one burst (their effective times are already
  ≥ 60 s apart thanks to the client-side button cooldown) without tripping
  the limit.
- IP stored as a hash only (`ip_hash`), not the raw address. Client IP is the
  LAST entry of `X-Forwarded-For` (proxies append; the leftmost entry is
  client-forgeable), falling back to the socket peer address.
- Malformed request bodies (non-JSON or JSON that is not an object) are
  treated as empty → 400 invalid_reason, never a 500.
- `client_ts` supports retro-timestamped offline reports; sanity-clamped
  server-side (not in the future; not older than 24 h).

### 5. Offline report queue (page JS)

- POST failure → queue report in localStorage (cap 10) with client timestamp.
- Flushed on next successful `/health` poll.
- Button disabled 60 s after a successful/queued tap (mirrors rate limit).

### 6. SQLite tables (in existing `server/data/memory.db`)

Created at startup with `CREATE TABLE IF NOT EXISTS`:

- `status_reports(id INTEGER PRIMARY KEY, created_at REAL, client_ts REAL, ip_hash TEXT, reason TEXT)`
- `status_incidents(id INTEGER PRIMARY KEY, started_at REAL, ended_at REAL, kind TEXT)`

### 7. Incident detection — heartbeat gap (no watchdog changes)

- Server writes a `last_alive` timestamp to SQLite every 30 s (background task).
- On startup: if `now - last_alive > 90 s`, insert a `status_incidents` row
  spanning `last_alive → now` with `kind = "server_down"`.
- Crashes and restarts thus appear on the timeline automatically.

## Error handling

- Rate-limited report → HTTP 429; page shows cooldown on the button.
- DB write failure → `print()` log + HTTP 500; page shows a "report failed" toast.
- Invalid reason → HTTP 400.
- Poll failures on the page never throw visibly; they drive the UNREACHABLE state.
- Heartbeat/incident writes wrapped in try/except — must never block startup.

## Conventions honored

- `print()` for logging (no logger).
- Character-agnostic user-visible text; display name injected at runtime.
- No ellipsis in any hardcoded string that could reach TTS (page is silent, but
  server-side strings follow the rule anyway).
- Tests in `tests/`, following existing patterns.

## Testing

pytest (new `tests/test_status_page.py`):
- `POST /status/report`: accepts valid reasons; 400 on unknown reason; 429 on
  second report within 60 s (effective time) from same IP; offline-queue burst
  with spaced `client_ts` values all accepted; `client_ts` clamping.
- `GET /status/data`: bucket math, 15-minute window count, incident listing.
- Incident derivation: fresh DB → no incident; stale `last_alive` → incident row
  with correct span; recent `last_alive` → no false positive.
- `GET /status` returns 200 with HTML.

Live verification (per `.claude/rules/testing.md` — no audio path here, page-only):
- Open `/status` in browser: components render, uptime ticks.
- Tap report → tally increments; second tap → cooldown.
- Kill server → open tab flips UNREACHABLE; restart → incident appears on timeline.

## Out of scope (v1)

- Watchdog-hosted fallback page (revisit only if outages prove common).
- Free-text report notes.
- Owner alerting/webhooks on report spikes.
- Auto-recovery nudges from report volume.
