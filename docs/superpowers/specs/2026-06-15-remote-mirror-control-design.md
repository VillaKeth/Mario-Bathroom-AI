# Remote Mirror + Control — Design

**Date:** 2026-06-15
**Status:** Approved (design); implementation not started
**Author:** Brainstormed with Claude

## Problem

Friends who are not in the room want to talk to the currently running model to test
it (e.g. before a party, or remotely). The old "chat room" page was rejected because
it was a text-only shortcut that bypassed the real pygame client — no real sprites,
no real audio render path, no real app. We want remote people to interact with the
*actual* running app, not a stand-in.

Separately, the real party deployment is a physical station (laptop driving a TV, with
mic + webcam) where one Mario greets guests. That station and the remote layer are
different things and must not interfere.

## Core Invariant

**There is always exactly ONE real pygame client running, and exactly ONE controller.
The browser is NEVER a renderer — only a mirror.**

- In **testing**: pygame runs on the dev machine; remote friends mirror and (optionally) drive it.
- At the **party**: pygame runs fullscreen on the TV laptop; remote friends mirror (view-only).
- Friends therefore always watch a *real* pygame app. It can never become a "chat room v2"
  shortcut, because the only place a response ever renders is the actual pygame client.

There is one Mario: one conversation state (`state_current`), one mood, one active game.
The system supports **1 active controller + N passive viewers**, never N independent
conversations.

## Requirement #1 (non-negotiable): Pygame independence

The mirror layer is **purely additive and opt-in**. Specifically:

1. The pygame client and server run **100% standalone** with the mirror feature absent,
   disabled, or simply with no remote viewer connected — identical behavior to today.
2. **Zero runtime cost when idle.** Frame capture only runs while ≥1 viewer is connected;
   otherwise the render loop is byte-for-byte unchanged. No encoding, no extra work.
3. A failure anywhere in the mirror path (capture, encode, viewer socket, tunnel) must
   **never** crash, stall, or alter the pygame client or the core conversation pipeline.
   Mirror code is wrapped so its exceptions are swallowed and logged, not propagated.
4. The feature is gated behind config flags that default **off** for the mirror and
   **`station`** (view-only) for control.

## Architecture

### Components

1. **Frame capture — `client/mario_display.py`**
   - In the existing render loop, when capture is active, grab the rendered Surface,
     downscale to ~540–720p, JPEG-encode (~q60), at ~10 fps.
   - Capture is **off by default** and only turns on when the server signals that a
     viewer is connected (start/stop messages). No viewer → no capture → no overhead.
   - Push frames to the server. Transport options (decided in plan): binary frames on a
     dedicated ingest WS, or a `{"type":"frame"}` message on the existing client WS.
     Binary preferred to avoid base64 bloat.
   - All capture/encode/send wrapped in try/except → log and continue; never breaks the loop.

2. **Mirror hub — server (new `/mirror` WS endpoint)**
   - Browser viewers connect here. Server holds a **separate set** of viewer sockets.
   - On each frame from the pygame client, fan out to all viewers.
   - **Tees the TTS audio bytes** the server already sends to the station, so viewers hear Mario.
   - Viewer sockets are a **distinct role** — they are never assigned to `_active_ws`
     and never drive the conversation. This preserves the single-active-WS assumption.
   - Tracks viewer count; tells the pygame client to start/stop capturing accordingly.

3. **`/friend` page — served by FastAPI**
   - `<canvas>` drawing incoming JPEG frames + audio playback (WebAudio/`<audio>`) + a text box.
   - Text submit → `POST` to an **authenticated wrapper** of `/admin/simulate_text` →
     existing full pipeline → the one pygame client renders + speaks → mirror shows it.
   - Box visibility/enabled state is driven by `control_mode` (below).
   - Mobile-friendly (party people open it on a phone).

4. **`control_mode` — config, hot-reloadable**
   - `station` (party default): text box hidden/disabled → remote is **view-only**.
   - `remote` (testing): text box enabled → the browser **drives** the running pygame client.
   - Only one controller exists at a time by construction; in `remote` mode the browser
     page is that controller. (No multi-controller arbitration in v1.)

5. **Auth — mandatory (the link is public)**
   - Secret token in the URL (e.g. `/friend?token=…` or `/m/<token>`) **plus** a one-field
     room PIN entered on the page.
   - The `simulate_text` wrapper validates token + PIN before dispatching. Raw
     `/admin/simulate_text` has no auth today; the wrapper closes that hole for the public path.
   - Without valid auth: view-only at most, never control.

6. **Reach — Cloudflare Tunnel**
   - `cloudflared tunnel --url http://localhost:8765` → public HTTPS URL, no installs for friends.
   - HTTPS is required for phase-2 `getUserMedia` and is provided automatically by the tunnel.
   - ngrok is an acceptable alternative (random URL). Tailscale is explicitly **not** used for
     guests — it requires an install/tailnet join that party people won't do.

### Data flow (text, testing mode)

```
friend phone (/friend, control_mode=remote)
  → POST /friend/say (auth: token + PIN)
    → wraps /admin/simulate_text
      → _text_input_task(_active_ws, text)   [existing full pipeline: commands/games/LLM/TTS]
        → response + audio sent to _active_ws (the real pygame client)
          → pygame renders sprite + speech bubble, plays TTS
            → frame capture → /mirror hub → fan out frames + audio → friend's canvas/audio
```

### Data flow (party mode)

```
guest at TV station → mic/keyboard → pygame client → /ws → pipeline → pygame renders/speaks
remote viewers (/friend, control_mode=station) → receive frames + audio only (view-only)
```

## Phasing

- **Phase 1 (this build): text + view-only mirror.**
  - Frame capture (gated), `/mirror` hub + audio tee, `/friend` page (canvas + audio + text),
    `control_mode` toggle, auth wrapper, Cloudflare Tunnel runbook.
  - Acceptance: friend on a phone over the public link sees the live pygame window and hears
    Mario; in `remote` mode they can type and watch the real app respond; in `station` mode
    they can only watch. Pygame runs normally with the mirror off and with no viewer connected.

- **Phase 2 (planned): remote voice.**
  - `/friend` captures mic via `getUserMedia` (HTTPS ✓ from tunnel) → audio chunks over WS →
    `server/stt.py` (Whisper) → same pipeline.
  - **Push-to-talk button** (avoid open-mic chaos / cross-talk).
  - Gotchas to handle: echo cancellation at party volume, browser autoplay needs one user tap,
    serialize so only the single controller's voice drives Mario.

## Error handling

- Mirror path failures are isolated (try/except, log, continue) — never affect pygame or the pipeline.
- No viewers → capture fully off.
- `simulate_text` requires `_active_ws`; since a pygame client is always running, this holds.
  If `_active_ws` is somehow absent, `/friend/say` returns a clear error and changes nothing.
- Tunnel down → pygame and the in-room station keep working; only the remote layer is unavailable.

## Testing

- **Pygame independence:** run client+server with mirror disabled and with mirror enabled but
  no viewer connected → verify identical behavior and no extra work in the loop.
- **Mirror fidelity:** connect a viewer → confirm frames render on the browser canvas and TTS
  audio plays in the browser, matching the pygame window.
- **Control modes:** `station` → text box hidden, input rejected; `remote` → text drives the
  real pygame client; confirm the response appears on the actual pygame app (per testing rules:
  verify `_play_wav: playing`/`done` and that spoken text matches the bubble).
- **Auth:** wrong/absent token or PIN → no control; correct → control works.
- **Isolation:** kill a viewer socket / the tunnel mid-session → pygame and pipeline unaffected.

## Out of scope (v1)

- Multi-controller arbitration / talking-stick handoff (single controller only).
- In-browser re-rendering of sprites (browser is a mirror, not a renderer).
- WebRTC media transport (JPEG-over-WS is sufficient for a chat bot; WebRTC is a future
  optimization only if latency/bandwidth becomes a problem).
