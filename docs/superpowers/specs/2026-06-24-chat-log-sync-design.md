# Bidirectional Chat-Log Sync — Design

- **Date:** 2026-06-24 (design refined 2026-06-25 during planning)
- **Branch:** master
- **Status:** Design approved; implementation plan pending
- **Scope:** server-only (plus tests)

## Problem

The tunnel surface (`/friend` phone page + `/mirror` viewer) and the pygame
surface (`/ws` client) do not share a complete conversation log. A guest message
typed in one place does not reliably appear in the other's log.

Concretely, two gaps:

1. **Pygame-typed guest input** is never added to the mirror transcript, so the
   phone's text log misses anything typed at the pygame station
   (`text_input` handler, `server/main.py:6293`, never calls `add_transcript`).
2. **Group mode** (`_group_turn_task`, `server/main.py:2033`) bypasses the
   shared response pipeline entirely: it neither echoes `user_message` to the
   pygame client nor logs anything (guest **or** bot) to the mirror transcript.
   On the current TADC group setup the tunnel text log is therefore nearly empty.

### What already works (must not regress)

- The `/mirror` viewer mirrors the pygame **screen as video + audio** via the
  `/mirror_ingest` relay — independent of the text log.
- **Tunnel → pygame log:** `_generate_and_send_response` echoes
  `{"type":"user_message"}` to the active pygame client (`:3995`); the client
  logs it (`client/main.py:362` → `display.add_chat_message("user", text)`).
- **Bot → mirror transcript (single mode):** `_generate_and_send_response`
  calls `add_transcript(bot_label, ...)` + broadcast (`:5310`).
- **Tunnel-typed guest → mirror transcript:** `/friend/say` adds it (`:2198`).
- **Bot → pygame display:** `send_response` in all modes.

## Goal

Every **guest turn** (local-typed, tunnel-typed, voice-spoken) and every **bot
turn** (single **and** group mode) appears **exactly once** in **both** logs:

- the pygame chat history (`_chat_history`, F3 overlay) — via the existing
  `user_message` / `mario_response` client handlers, and
- the mirror transcript — via `mirror_relay.add_transcript` + `broadcast_text`.

### Non-goals (explicitly out of scope)

- Rendering remote guest input **live on the main pygame screen** — F3 history
  log only (per product decision).
- Any change to **audio fan-out** — the phone already receives audio via the
  `/mirror_ingest` relay.
- Changing **group-mode routing of pygame-typed input** (pygame-typed currently
  uses the single-speaker pipeline even in group mode — pre-existing, untouched).

## Current coverage

| Turn | Single mode (now) | Group mode (now) |
|------|-------------------|------------------|
| Guest → pygame log (echo) | ✓ `:3995` | ✗ |
| Guest → mirror transcript | ✗ pygame-typed / ✓ tunnel `:2198` | ✗ pygame / ✓ tunnel `:2198` |
| Bot → pygame display | ✓ | ✓ (`send_response`) |
| Bot → mirror transcript | ✓ `:5310` | ✗ |

## Design

### Architecture: log at input entry, not in the response pipeline

Guest-input logging is **separated from response generation**. A guest turn is
logged exactly once, at the moment input is received, by a single helper —
independent of which response pipeline (single `_generate_and_send_response` or
group `_group_turn_task`) then handles it. Bot turns are logged where responses
are sent. This covers single **and** group modes uniformly, without threading a
name through the deep `_text_input_task → _handle_text_input →
_generate_and_send_response` chain.

### New helpers (`server/main.py`)

- `_resolve_guest_name(guest_name)`:
  `return guest_name or state_current.get("speaker_name") or "Guest"`.
  Reads one global; unit-testable by patching `state_current`.
- `async _log_guest_turn(ws, name, text)`:
  ```python
  try:
      await ws.send_json({"type": "user_message", "text": text})   # pygame F3 log
  except Exception as e:
      logger.debug(f"[WS] user_message echo failed: {e}")
  try:
      mirror_relay.add_transcript(name, text)                      # tunnel transcript
      await mirror_relay.broadcast_text(
          {"type": "transcript", "lines": mirror_relay.transcript_snapshot()})
  except Exception as e:
      logger.debug(f"[MIRROR] guest transcript log failed: {e}")
  ```

### Guest-input call sites (each logs exactly once)

1. **pygame `text_input` handler** (`:6293`) — before dispatching:
   `await _log_guest_turn(ws, _resolve_guest_name(None), text)`.
2. **`_dispatch_user_text(text, guest_name=None)`** (`:2070`) — after the
   `_active_ws` guard, before creating the response task:
   `await _log_guest_turn(_active_ws, _resolve_guest_name(guest_name), text)`.
   Covers tunnel (`/friend/say`) and admin (`/admin/simulate_text`).
3. **voice `handle_audio`** (before `:5575`):
   `await _log_guest_turn(ws, _resolve_guest_name(None), transcript)`.

### Removals (avoid double-logging)

- Delete the `user_message` echo block in `_generate_and_send_response`
  (`:3991-3997`) — now done at entry. (`face_greeting` never echoed; unaffected.)
- Delete the `add_transcript` + transcript broadcast in `/friend/say`
  (`:2198-2199`) — now done by `_dispatch_user_text`. **Keep** the turn-acquire
  logic + turn-state broadcast (`:2200`). Pass `guest_name=name` into
  `_dispatch_user_text`.

### Bot-turn logging

- **Single mode:** unchanged — `_generate_and_send_response` already logs at
  `:5310`.
- **Group mode:** in `_group_turn_task`, after each
  `await send_response(ws, ln...)` (`:2059`), add:
  `mirror_relay.add_transcript(ln["display_name"], ln["text"])` + transcript
  broadcast (try/except). Keys present at `:2057`/`:2059`.

### Data flow (after)

- **Pygame typed:** `text_input` → `_log_guest_turn` (echo to own F3 log +
  transcript) → `_text_input_task` → pipeline (no echo). Bot reply → display +
  transcript (`:5310`).
- **Tunnel typed:** `/friend/say(name)` → `_dispatch_user_text(name)` →
  `_log_guest_turn(_active_ws, name, text)` (echo to pygame log + transcript) →
  group or single pipeline.
- **Voice:** `handle_audio` → `_log_guest_turn(ws, speaker, transcript)` →
  pipeline (no echo).
- **Admin sim:** `/admin/simulate_text` → `_dispatch_user_text(None)` →
  `_log_guest_turn(_active_ws, "Guest"/speaker, text)`.

### Correctness / dedup

- Each guest turn logs once (entry only; pipeline echo removed; `/friend/say`
  add removed).
- `face_greeting` / internal sources never logged (not a guest entry).
- Group bot lines logged once each in the speaker loop.
- All mirror/echo calls wrapped in try/except — mirror is optional, never breaks
  the response path.
- Input is serialized (new input cancels the prior response task), so guest-turn
  logs never interleave.

## Testing

- **Unit (TDD, RED first):**
  - `_resolve_guest_name`: returns `guest_name` when given; else
    `state_current["speaker_name"]`; else `"Guest"`. (Patch `state_current`.)
  - Because `server.main` is impractical to import in the unit env (see
    `tests/test_edge_cases.py:1347`), assert structural facts via AST where
    direct import is too heavy: `_generate_and_send_response` no longer contains
    the `user_message` `send_json` echo; `_dispatch_user_text` and the
    `text_input` handler and `handle_audio` each call `_log_guest_turn`;
    `/friend/say` no longer calls `add_transcript`.
- **Integration / live (per `.claude/rules/testing.md`, MANDATORY audio):**
  - Type on pygame → message appears in the `/friend` transcript.
  - Type on `/friend` → message appears in the pygame F3 log.
  - Group mode: both directions, plus each bot speaker line in the transcript.
  - Bot replies still play audio (`_play_wav: playing` … `done`), correct
    character, no wrong-character leaks.
  - No double-logging (tunnel input shows once).

## Risks

- A `broadcast_text` per guest turn adds minor async work — negligible at party
  message rates.
- Removing the pipeline echo is safe **only if** all three guest entries call
  `_log_guest_turn`; the plan adds them before removing the echo, and the live
  test confirms every path still echoes.
- Group bot logging relies on `ln["display_name"]`/`ln["text"]` — already used at
  `:2057`/`:2059`.
- Adding `guest_name` to `_dispatch_user_text` is backward-compatible (default
  `None`).

## Files touched

- `server/main.py` — all production changes.
- `tests/test_chat_log_sync.py` (new) — unit/AST tests.

## Out of scope (restated)

- Live on-screen rendering of remote input on the main pygame display.
- Audio fan-out changes.
- Group-mode routing of pygame-typed input.
