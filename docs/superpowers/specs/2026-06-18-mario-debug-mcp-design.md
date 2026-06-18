# Mario Debug MCP — Design Spec

**Date:** 2026-06-18
**Status:** Approved (design), pending implementation plan
**Goal:** Give Claude Code first-class eyes/ears/hands on the running Mario AI app so it can verify, debug, and develop without being blind to the pygame screen, the audio that played, or the server/client logs.

## Problem

During live work this session, Claude could not:
- See the pygame client screen (video out).
- Verify what audio actually played, whether it finished, or whether the spoken text matched the bubble (audio out) — a MANDATORY check per `.claude/rules/testing.md`.
- Tail server/client logs (both log to stdout/console only; no logfile).
- Simulate a guest speaking (audio in) or appearing (video in) to exercise the full pipeline.

Net effect: verification leaned on indirect signals (process lists, `/api/health`, the mirror transcript — which excludes idle by design). The debugging loop was slow and partially blind.

## Approach (chosen: Hybrid — maximum control)

A standalone **FastMCP** server (`mcp_mario_debug/`) that bridges over `127.0.0.1` to:
1. the existing **FastAPI server** (`:8765`) — extend with a log ring + STT-inject endpoint; reuse existing `/api/health`, `/admin/simulate_text`, `/admin/set_emotion`, `/admin/trigger_event/*`, `/admin/set_night_phase`.
2. a **new debug HTTP server inside the pygame client** (`:8770`, `client/debug_server.py`) — the client owns the screen, speakers, webcam, and mic, so all four channels require client instrumentation.
3. an **OS screenshot fallback** (`mss`) when the client frame endpoint is unavailable.

```
Claude Code ──stdio──> mcp_mario_debug/server.py (FastMCP)
                            │ HTTP over 127.0.0.1
            ┌───────────────┴────────────────────┐
            ▼                                      ▼
   FastAPI server :8765                  pygame client :8770 (NEW)
   • GET  /debug/log     (server log ring)        • GET  /frame.png   latest rendered frame
   • POST /admin/inject_audio  wav→STT→dispatch    • GET  /state       text/speaking/emotion/pose/bubble/game
   • GET  /api/health             (exists)         • GET  /audio       ring: text,dur,rms,peak,sr,played,done
   • POST /admin/simulate_text    (exists)         • GET  /log         client log ring
   • /admin/set_emotion, trigger_event,            • POST /inject_frame  image→person/face detect
     set_night_phase              (exist)
```

## Components (small, single-purpose)

| Unit | Responsibility | Depends on |
|------|----------------|-----------|
| `mcp_mario_debug/server.py` | FastMCP tool definitions (thin) | `bridge.py` |
| `mcp_mario_debug/bridge.py` | HTTP calls to `:8765`/`:8770`, OS-screenshot fallback, wav analysis, image base64/Image encoding, reads admin key in-process | `httpx`, `mss`, `pillow`, `config.json` |
| `client/debug_server.py` | stdlib `http.server` daemon thread, `127.0.0.1` only, `MARIO_DEBUG` flag-gated; serves frame/state/audio/log, accepts inject_frame | client getters, ring buffers |
| client audio ring | per-`_play_wav` record {text, duration, rms, peak, sample_rate, started, finished} | `audio_playback.py` |
| client + server log rings | bounded `deque` fed by a `logging.Handler` | `logging` |
| frame publish | render loop writes latest frame to a locked in-memory PNG buffer (no cross-thread Surface access) | `mario_display.py` |

## MCP tool surface

**Monitor:** `mario_screenshot` (returns viewable PNG; client frame, OS-grab fallback), `mario_state`, `mario_audio_out(n)`, `mario_logs(source, grep, level, n)`, `mario_health`.

**Control:** `mario_send_text(text)`, `mario_inject_audio(path|b64)` (guest *speaking* → STT → dispatch), `mario_inject_frame(path|b64)` (guest *appearing* → detection → presence/face), `mario_set_emotion(emotion)`, `mario_trigger_event(name)`, `mario_set_night_phase(phase)`.

Injection feeds the detection/STT pipelines directly — it never opens the real mic/cam device, so there is **no contention** with `presence.py`/`audio_capture.py`.

## Data flow

- **Audio out (verify):** `audio_playback._play_wav` records a clip into the ring → `mario_audio_out` returns the last N → Claude confirms played/finished, duration sane, sample-rate (32000 = SoVITS, 24000 = Edge), and that text matches the bubble.
- **Audio in (inject):** `mario_inject_audio` POSTs a wav to `/admin/inject_audio` → server STT (`stt.transcribe`) → `_dispatch_user_text` → normal reply path.
- **Video in (inject):** `mario_inject_frame` POSTs an image to client `/inject_frame` → `person_detector`/face path → presence/face event to server (as if a guest appeared).
- **Video out (see):** render loop publishes latest frame → `mario_screenshot` returns it (or OS-grab fallback).

## Error handling

- Every tool returns `{ok: ...}` or `{error: ...}`; never raises into the MCP layer.
- Client debug server down (party mode / not launched): `mario_screenshot` falls back to OS grab; `mario_state`/`mario_audio_out`/`mario_inject_frame` return `{error: "client debug off", hint: "set MARIO_DEBUG=1 and relaunch client"}`. Server-side tools keep working.
- `/debug/*` + `/admin/*` require the admin key (server) and are localhost-bound (client). The MCP reads the key from `config.json` in-process and never logs it.

## Safety / party-deployment

- The debug surface is **off by default** — `MARIO_DEBUG=1` (env or config flag) enables the client debug server and the server `/debug/*` routes; both bind `127.0.0.1` only and are never exposed on the Cloudflare tunnel.
- No secrets are baked into the MCP or any page; the admin key lives only in `config.json` (gitignored).

## Testing (TDD)

- **Unit:** ring buffers (append/cap/snapshot); wav analysis (rms/peak/sample-rate/duration on a synthesized wav); bridge parsing + fallback-selection (mocked HTTP).
- **Endpoint:** FastAPI `TestClient` for `/debug/log` and `/admin/inject_audio` (gating + happy path).
- **Not unit-tested:** image pixel content. The encoding path and the frame-vs-OS-grab fallback selection ARE tested via mocks.

## Files

**New:** `mcp_mario_debug/{__init__.py, server.py, bridge.py, requirements.txt, README.md}` (+ `venv/`), `client/debug_server.py`, `tests/test_mcp_debug_bridge.py`, `tests/test_debug_rings.py`, `tests/test_debug_endpoints.py`.

**Edit (small, focused):** `.mcp.json` (register `mario-debug`), `client/main.py` (start debug server under flag + wire getters), `client/audio_playback.py` (audio ring), `client/mario_display.py` (frame publish + state snapshot), `server/main.py` (log ring + `/debug/log` + `/admin/inject_audio`; gate `/debug/*`).

## Out of scope (deferred)

- OS-level speaker loopback recording (the per-clip audio ring covers verification more cleanly).
- Remote/tunnel exposure of the debug surface (intentionally localhost-only).
- Any change to the mirror's intentional exclusion of idle messages.
