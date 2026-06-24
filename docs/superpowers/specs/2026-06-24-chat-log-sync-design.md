# Bidirectional Chat-Log Sync — Design

- **Date:** 2026-06-24
- **Branch:** feat/tadc-group
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
   On the current `feat/tadc-group` setup the tunnel text log is therefore
   nearly empty.

### What already works (must not regress)

- The `/mirror` viewer mirrors the pygame **screen as video + audio** via the
  `/mirror_ingest` relay — this is independent of the text log.
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

### Entry points and pipelines

Guest input enters at four places and flows through two response pipelines:

- `_generate_and_send_response` (single-speaker): pygame-typed (always, even in
  group mode), voice (`handle_audio`), and non-group tunnel/admin input.
- `_group_turn_task` (group ensemble): tunnel/admin input when `_GROUP_CTX` set.

We log at the pipeline level so each turn is captured once, with the correct
name, regardless of entry point.

### Changes (all in `server/main.py`)

1. **`_resolve_guest_name(guest_name)`** — new tiny pure helper:
   `return guest_name or state_current.get("speaker_name") or "Guest"`.
   (Pure and unit-testable.)

2. **`_generate_and_send_response(ws, text, source, start_time, guest_name=None)`**
   — add the `guest_name` param. Beside the existing `user_message` echo (which
   already guards on `text and source in ("text","audio")`), add:
   ```python
   _who = _resolve_guest_name(guest_name)
   try:
       mirror_relay.add_transcript(_who, text)
       await mirror_relay.broadcast_text(
           {"type": "transcript", "lines": mirror_relay.transcript_snapshot()})
   except Exception as e:
       logger.debug(f"[MIRROR] guest transcript log failed: {e}")
   ```
   Covers pygame-typed + voice + non-group tunnel/admin. `face_greeting` and
   other internal sources stay excluded (same guard as the echo).

3. **`_group_turn_task(ws, text, guest_name=None)`** — add the `guest_name`
   param. At turn start (before orchestration): echo `user_message` to `ws` and
   log the guest input to the transcript + broadcast (same `_resolve_guest_name`
   + try/except). After each `send_response(ln)` in the speaker loop: log that
   bot line — `mirror_relay.add_transcript(ln["display_name"], ln["text"])` +
   broadcast. (Keys confirmed present at `:2057`/`:2059`.)

4. **`_dispatch_user_text(text, guest_name=None)`** — forward `guest_name` to
   both `_group_turn_task` and `_text_input_task`.

5. **`_text_input_task(ws, text, guest_name=None)`** — forward `guest_name` to
   `_generate_and_send_response`.

6. **`/friend/say`** — pass `guest_name=name` into `_dispatch_user_text`, and
   **remove** the now-duplicate `add_transcript` + transcript broadcast
   (`:2198-2199`). **Keep** the turn-acquisition logic and the turn-state
   broadcast (`:2200`).

7. **`/admin/simulate_text`** — unchanged call; `guest_name` defaults to `None`
   → resolves to `speaker_name`/`"Guest"`.

### Data flow (after)

- **Pygame typed:** `text_input` → `_text_input_task(pygame)` →
  `_generate_and_send_response(pygame, source="text")` → echo to own log +
  `add_transcript(speaker/Guest)` + broadcast (phone sees it). Bot reply →
  display + `add_transcript(bot)` (`:5310`).
- **Tunnel typed (single):** `/friend/say(name)` → `_dispatch_user_text(name)` →
  `_text_input_task` → `_generate_and_send_response(_active_ws, "text", name)` →
  echo to pygame log + `add_transcript(name)` once.
- **Tunnel typed (group):** `/friend/say(name)` → `_dispatch_user_text(name)` →
  `_group_turn_task(name)` → echo + `add_transcript(name)` + per-speaker bot
  transcript.
- **Voice:** `handle_audio` → `_generate_and_send_response(source="audio")` →
  echo + `add_transcript(speaker)`.

### Correctness / dedup

- Removing `/friend/say`'s add (step 6) prevents double-logging tunnel input now
  that the pipeline logs it.
- `face_greeting` / internal sources excluded by the `source in ("text","audio")`
  guard.
- Group bot lines logged once each inside the existing speaker `for` loop.
- All mirror calls wrapped in try/except — mirror is optional and must never
  break the response path.

## Testing

- **Unit (TDD, RED first):**
  - `_resolve_guest_name`: `guest_name` wins; else `speaker_name`; else `"Guest"`.
  - `_generate_and_send_response` logs the guest turn to the transcript once for
    `source="text"` and `source="audio"`, and **not** for
    `source="face_greeting"` (mock `mirror_relay`).
  - Group: `_group_turn_task` logs guest input once and one bot line per speaker
    (mock orchestrator + `mirror_relay`).
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
- Group bot logging relies on `ln["display_name"]`/`ln["text"]` — already used at
  `:2057`/`:2059`, so keys are present.
- Adding `guest_name` params is backward-compatible (all default `None`).

## Files touched

- `server/main.py` — all production changes.
- `tests/test_chat_log_sync.py` (new) — unit tests.

## Out of scope (restated)

- Live on-screen rendering of remote input on the main pygame display.
- Audio fan-out changes.
- Group-mode routing of pygame-typed input.
