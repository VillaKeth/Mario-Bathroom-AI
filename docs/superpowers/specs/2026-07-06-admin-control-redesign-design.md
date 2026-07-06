# Admin Control Page Redesign — "Toggle Everything, Live"

- **Date:** 2026-07-06
- **Status:** Approved (design)
- **Branch:** `feat/admin-live-control`

## Goal

Turn the admin control page (`/control`) into a fast, phone-first remote where the
host can **toggle every party feature live** — no restart, one tap. The page adapts:
live-toggle mode on a phone, a fuller setup view on desktop, with a manual override.

## Current State

`server/static/control.html` (served by `GET /control`, main.py:2291) is a single-column,
admin-key-gated page with 7 cards: admin key, character switch, safe settings (idle —
**restart-only**), volume (live), night phase (live), restart, status log. It exposes only
a fraction of the ~30 admin endpoints and mixes live and restart-only controls with no
visual distinction. Most feature flags can't be toggled at all.

## Design Decisions (from brainstorming)

1. **Adaptive, not two pages.** One page. Viewport width picks the default mode
   (phone → Live, desktop → Setup); a `Live | Setup` pill in the header overrides the
   auto-detection. This is the "choice depending on device" the user asked for.
2. **All toggles instant.** Every on/off applies live via `LiveConfig` — no restart.
   Features that currently read their flag at startup get refactored to read it live.
3. **Backend = generic live-toggle bus (Approach A).** One whitelisted `/admin/live_set`
   endpoint + one `/admin/state` snapshot, all flags declared in a single manifest that
   drives both server validation and page rendering. (Rejected: one endpoint per feature —
   ~10 endpoints of boilerplate, same refactor anyway.)
4. **Live layout = "one scroll, grouped" (Option A).** All controls on one scrollable
   page, grouped by section, big tap targets. (Rejected: tabbed — hides controls behind a
   tap.)

## Architecture

### Backend

**Flag manifest — `server/live_flags.py` (new).** Single source of truth. Each entry:

```python
{ "key": str, "label": str, "type": "bool"|"enum"|"number",
  "default": Any, "options": [...]|None, "min": n|None, "max": n|None,
  "group": "vibe"|"features"|"games"|"look"|"setup" }
```

Adding a future toggle = one manifest entry; the page renders it automatically.

**`POST /admin/live_set {api_key, key, value}`** — admin-key checked; `key` must be in the
manifest; `value` coerced + range/option-validated per the manifest entry; then
`live_config.set(key, value)`. `LiveConfig` auto-reloads on file change, so the new value
is live on the next `.get()`. Rejects any non-manifest key (tunnel-safe). Returns
`{status, key, value}`.

**`POST /admin/state {api_key}`** — returns every flag's current value plus live subsystem
readouts (current night phase, volume, active character, active game name, paused). The
page renders truth from this; never guesses.

**Read-site refactor (the "make it live" work).** Replace startup-captured module globals
with `live_config.get(key, default)` at the decision point:

| Flag | Now | Change |
|---|---|---|
| `llm_idle_enabled`, `llm_idle_chance`, `idle_interval_min/max_seconds` | startup globals (main.py:3571, 4037) | read live |
| `safety_enabled`, `block_slurs` | startup `set_safety_config` | read live at filter call |
| `gossip_enabled` | (new flag) startup gate | add + read live |
| `games_enabled` | (new flag) command routing gate | add + read live |
| `recognition_enabled` | (new flag) server-side recognition gate | add + read live |
| `distress_enabled` | (new flag) distress-processing gate | add + read live |
| `catchphrase_mirror_enabled` | (new flag) mirror gate | add + read live |
| `paused` | (new flag) | when true, server skips generating replies and mutes TTS |

Existing already-live `LiveConfig` keys (chaos, roast, gossip_intensity, warmth,
tts_engine) stay; the on/off `*_enabled` flags are new and independent of intensity.

**`POST /admin/outfit {api_key, outfit}` (new).** Broadcasts an outfit change to the
client over the existing mirror/WS channel. The client already has `on_outfit_switched`
(client/main.py:630) — nothing server-side calls it today. This endpoint fills that gap so
outfit is controllable from the page.

**Reused as-is (already live):** `/admin/set_night_phase`, `/admin/set_volume`,
`/admin/set_emotion`, `/admin/announce`, `/admin/switch_character`, `/admin/trigger_event`,
`/admin/force_stop_game`, `/admin/trigger_memorial`, `/admin/restart`, `/admin/set_config`
(idle timing, setup-only).

### Frontend — `server/static/control.html` (rewrite)

Single page, responsive. Admin-key card unchanged (typed → localStorage → request body).
After connect, render the control groups from `/admin/state` + the manifest.

- **Mode:** `Live | Setup` pill in the header. Default by viewport (`matchMedia`
  width < ~700px → Live). Manual click overrides and is remembered in localStorage.
- **Live mode (phone):** one scrollable column, grouped — big toggle switches and
  tap targets. Layout Option A.
- **Setup mode (desktop):** same groups in a multi-column grid, plus setup-only controls
  (idle timing fields, character switch + restart, restart server, health readout).
- **Toggles** call `/admin/live_set`; **actions** (stop game, announce, event, memorial,
  outfit, emotion, phase, volume) call their existing endpoints.
- **State sync:** call `/admin/state` on connect, after every action, and on a ~5s poll.
  Optimistic UI — flip instantly, reconcile from the response, revert + toast on error.
  Keeps two phones consistent.

### Control Map

| Group | Controls | Mode |
|---|---|---|
| Vibe | night phase, volume, ⏸ pause bot | live |
| Features (toggles) | idle chatter, gossip, safety filter, games, face recognition, distress detect, catchphrase mirror | live |
| Games & events | stop game, trigger event (+music), memorial | live |
| Look | outfit, emotion, announce | live |
| Setup only | character switch (live/restart), idle timing (min/max/chance), restart server, health readout | both; richer on desktop |

## Auth & Safety

- Every request carries the admin key (unchanged mechanism).
- `live_set` accepts **only** manifest keys, each type + range/option checked — a bad or
  malicious value over the public tunnel cannot set arbitrary config or brick the server.
- Destructive stays gated: restart requires typing `RESTART`; memorial and announce get a
  confirm step.
- `paused` is a soft, fully reversible kill switch (bot goes silent; no data change).

## Error Handling

- Each action shows an inline ok/bad toast in the status log.
- A failed toggle reverts its visual state (optimistic UI reconciled against the error).
- `/admin/state` poll failure shows a "reconnecting" state, doesn't wipe the last-known UI.

## Testing

- **Backend unit tests** (`tests/test_admin_live_control.py`, new):
  - `live_set` rejects non-manifest keys; clamps/validates per manifest; each flag
    round-trips through `LiveConfig`.
  - `/admin/state` returns every manifest key + the live readouts, correct shape.
  - Each read-site refactor: a test proving the flag flips behavior live (e.g. set
    `llm_idle_enabled=false` → idle path is skipped without restart).
  - `paused=true` → reply generation is skipped.
- **Frontend:** endpoint smoke test; manual pass on phone + desktop widths.
- **Live verification (project rule):** after wiring, drive announce / outfit / emotion
  through the page against the running bot and confirm audio + the client reflect the
  change (per `.claude/rules/testing.md`).

## Out of Scope (YAGNI)

- No new auth model (keep admin key). No multi-user turn logic on the control page
  (that's the `/friend` page's job). No historical/analytics view (dashboard already
  exists). No per-guest controls. No theming.

## Files Touched

- **New:** `server/live_flags.py`, `tests/test_admin_live_control.py`,
  this spec, the plan doc.
- **Edit:** `server/main.py` (2 new endpoints, `/admin/outfit`, read-site refactors),
  `server/static/control.html` (rewrite), possibly `server/safety_filter.py`,
  `server/command_handlers.py`, and the recognition/distress gates for live reads.
