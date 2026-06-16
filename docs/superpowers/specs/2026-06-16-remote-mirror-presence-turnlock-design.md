# Remote Mirror — Presence, Single-Talker Turn-Lock, Live Transcript & View Counter

**Date:** 2026-06-16
**Status:** Approved design
**Builds on:** `2026-06-15-remote-mirror-control-design.md` (the frame/audio mirror + `/friend` page)

## Problem

The remote mirror lets many people watch the running character and (in `remote`
mode) any of them type a message. There is no notion of *who* is talking, no
limit on simultaneous talkers (messages currently interrupt each other), and a
viewer can't see what other people said or how many people are watching.

The owner wants: many viewers, **one talker at a time**, everyone able to see
**who** is talking, **what** they said, **what the character replied**, plus a
temporary display name per person and a live **view counter**.

## Goals

- Many concurrent viewers; **exactly one active talker** at any moment (`remote` mode only).
- Talker is identified by a **temporary display name**; others see it.
- A **live transcript** of the conversation (last ~6 lines: `Name: msg` / `March: reply`).
- A **view counter** ("👁 N watching").
- Fully additive: `station` (view-only) mode and the existing binary frame/audio
  path keep working unchanged. Nothing here may raise into the core pipeline.

## Non-Goals

- Real authentication or anti-spoofing. Identity is `name + random browser id`.
  The PIN remains the only (intentionally weak) gate, per owner's choice.
- Persisting names, transcript, or turns across server restarts.
- Remote microphone / STT (separate, deferred phase).
- Showing the character's **idle** mumbles in the transcript — only replies to a
  dispatched user message are logged, so it reads as a real conversation.

## Behavior

1. Open the link → the page connects and **shows the live view immediately**.
   Viewing never requires a name.
2. To send, the visitor enters a **temporary name** (stored in `localStorage`
   alongside a random `clientId`). Required only to talk.
3. The first sender **acquires the turn**. Each accepted message **refreshes**
   the turn's idle timer. After **30 s** with no new message from the holder the
   turn **auto-frees**.
4. While someone else holds the turn, every other visitor's input is **disabled**
   and shows *"March is chatting with **<name>**…"*. When it frees, inputs
   re-enable.
5. Everyone sees a **rolling transcript** (last 6 entries) and a **view counter**.

## Architecture

All new state lives in `server/mirror.py` (pure, unit-testable) and is surfaced
to viewers over the existing `/mirror` WebSocket, which now carries **both**
binary messages (frames/audio, unchanged) **and** JSON text control messages.

### Component 1 — `server/mirror.py` (pure turn/transcript/presence state)

Turn state:

```
_turn = {"owner": None, "name": None, "expires": 0.0}
_TURN_IDLE_SECONDS = 30.0
```

- `acquire_or_refresh_turn(client_id, name, now) -> (granted: bool, holder_name: str|None)`
  Grants if the turn is free, already owned by `client_id`, or expired
  (`now >= expires`). On grant sets `owner/name` and `expires = now + _TURN_IDLE_SECONDS`.
  Otherwise returns `(False, current_holder_name)`.
- `release_turn(client_id)` — clears the turn iff `owner == client_id`.
- `expire_turn_if_idle(now) -> bool` — if a turn is held and `now >= expires`,
  clears it and returns `True` (state changed); else `False`.
- `turn_state(now) -> dict` — `{"busy": bool, "name": str|None, "seconds_left": int}`
  for pushing to viewers.

Transcript ring:

```
_transcript = deque(maxlen=6)   # items: {"who": str, "text": str}
```

- `add_transcript(who, text)` — append `{who, text}` (trimmed).
- `transcript_snapshot() -> list[dict]` — current list (for new joiners).

JSON fan-out + presence:

- `broadcast_text(obj)` — JSON-encode `obj` and `send_text` to every viewer,
  reusing the same per-viewer `_SEND_TIMEOUT` + drop-dead logic as `broadcast`.
- `viewer_count()` (exists) is the basis for the counter.

All of the above are synchronous/pure except `broadcast_text` (async fan-out).
`reset_state()` also resets `_turn` and `_transcript`.

### Component 2 — `server/main.py` (wiring; never raises into core)

- **`/friend/say`**: after existing auth passes, read `name` + `client_id` from
  the body. Call `acquire_or_refresh_turn`. If denied → return
  `{"status": "busy", "holder": <name>}` (HTTP 200, no dispatch). If granted →
  `add_transcript(name, text)`, `broadcast_text({type:"transcript", ...})` +
  `broadcast_text({type:"turn", ...})`, then `_dispatch_user_text(text)` as today.
- **`/mirror` viewer endpoint**: the receive loop (currently `await ws.receive_text()`
  purely to detect disconnect) now parses each text frame as JSON. On
  `{type:"hello", name, id}` it records the viewer's name. On connect (after
  `add_viewer`) it pushes the current `presence`, `turn`, and `transcript`
  snapshot to the new socket, and broadcasts updated `presence` to everyone.
  On disconnect, `remove_viewer` + broadcast `presence`.
- **Bot reply → transcript**: in the text-input pipeline (`_text_input_task`),
  once the response text is finalized, call `add_transcript(<char_display_name>, reply)`
  and `broadcast_text`, where the label is the **active character's display name**
  (e.g. "March 7th"), never hardcoded. This covers `/friend/say`,
  `/admin/simulate_text`, and typed pygame input; idle mumbles are not in this
  path, so they are excluded by design.
- **Watcher task**: one app-level loop (started lazily, like `ensure_relay_worker`)
  ticks ~every 2 s; if `expire_turn_if_idle(now)` returns `True`, it
  `broadcast_text({type:"turn", busy:false})` so disabled inputs re-enable.

### Component 3 — `server/static/friend.html`

- On load: read/create `clientId` + `name` in `localStorage`; if no name, viewing
  proceeds but the composer shows a "enter a name to chat" prompt.
- The `/mirror` WS `onmessage` branches on payload type:
  - **binary** (Blob/ArrayBuffer) → existing frame/audio handler (unchanged).
  - **string** → JSON control: `presence` (update counter), `turn` (enable/disable
    composer + banner), `transcript` (re-render last 6 lines).
- On connect, send `{type:"hello", name, id}`.
- Sending: `POST /friend/say {text, token, pin, name, id}`. On `{status:"busy"}`
  show the holder banner; on `{status:"ok"}` clear the composer.
- New UI: header view counter badge, a turn banner line, and a transcript panel
  above the composer. Styling follows the existing page; `__CONTROL_MODE__`
  injection is unchanged (turn UI only renders in `remote` mode).

## Data Flow

```
open → (name/clientId from localStorage)
     → WS /mirror connect → send {hello,name,id}
     → server: add_viewer; push {presence,turn,transcript} to me; broadcast {presence} to all

type+send → POST /friend/say {text,token,pin,name,id}
          → auth → acquire_or_refresh_turn
              granted: add_transcript(name,text); broadcast {transcript,turn}; _dispatch_user_text
              denied:  return {status:"busy", holder}

March reply finalized → add_transcript("March",reply) → broadcast {transcript}

watcher (~2s) → expire_turn_if_idle → if changed broadcast {turn: free}
```

## Error Handling

- Every mirror push is wrapped; a dead/slow viewer is dropped (existing
  `_SEND_TIMEOUT` path) and never blocks others or the core pipeline.
- Turn-lock is **best-effort UX**, not security. A malicious client could forge a
  name/id; acceptable under the stated low-security model.
- Malformed viewer JSON is ignored (treated as a keepalive/no-op).
- If `broadcast_text` fails entirely, the conversation still works (the talker's
  message is dispatched; only the live UI sync is degraded).

## Testing

Pure unit tests in `tests/test_mirror.py`:

- `acquire_or_refresh_turn`: grant when free; refresh when owner repeats; deny a
  second client while held; grant after expiry; `release_turn` frees only the owner.
- `expire_turn_if_idle`: returns `True` once on expiry, `False` afterward.
- `transcript` ring caps at 6 and preserves order.
- `broadcast_text`: sends JSON to all viewers and drops a dead one (mirrors the
  existing `broadcast` drop-dead test).

Live end-to-end (two browsers): viewer count updates on join/leave; talker A
holds, talker B is blocked with A's name; transcript shows both A's message and
March's reply with names; turn frees after 30 s idle and B can then talk; audio
verified playing per the project's audio-verification rule.

## Out of Scope / Future

- Showing the full viewer roster (only the count + the active talker's name).
- A "pass the mic" button (idle auto-release chosen instead).
- Remote mic/STT.
