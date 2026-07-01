# Screen-Watching Game Coach — Design

**Date:** 2026-07-01
**Status:** Approved (design), pre-implementation
**Baseline:** master @ latest (post adaptive-response-length + v4.1)

## Problem / Goal

Let Rudi watch a guest's game (played on the bot's own machine) and periodically
roast/coach them in character. Roast-first, occasional genuine tips. It must be
**opt-in via its own process** (`start_watching.bat`) like the server/client/tunnel
bats, and the vision model (`llava-llama3`, 5.5 GB) must **only be loaded while that
watcher is running** — never idling in VRAM when nobody's using it.

## Non-goals

- Not game-state-accurate coaching (llava gives general scene understanding, not
  frame-perfect strategy). Generic-but-contextual heckling is the bar.
- No capture of remote/other machines — same-machine screen capture only.
- No new persona/voice code — reuse Rudi's existing LLM + TTS + display path.
- Not always-on / auto-detect — running the bat is the explicit start; closing it
  is the stop.

## Architecture

Two decoupled pieces. The watcher is the "eyes" (owns capture + llava); the server
is the "voice" (owns Rudi's roast + TTS + display). They talk over one HTTP endpoint.

```
start_watching.bat → screen_watcher.py  (standalone, own venv activation)
   loop every ~WATCH_INTERVAL s while running:
     capture screen (mss, downscaled JPEG)
       → llava describe (Ollama, keep_alive short)         [llava lives HERE]
       → POST {description, guest?} to server /admin/watch_frame
   on exit (atexit/finally/Ctrl+C/window close):
     → Ollama unload llava (POST /api/generate {model, keep_alive:0})
   safety: auto-exit after WATCH_MAX_MINUTES (~30) so it never runs forever

server  /admin/watch_frame  (new endpoint)
   receives scene description text
     → build Rudi roast context (persona + "you're watching them play: <desc>")
     → llm.generate_response  (Qwen3 — existing)
     → TTS → send_response to the connected client
   gated by the existing idle-safe cooldowns (never heckle over a real convo)
```

**Why llava in the watcher:** ties the model's lifecycle to the process. No watcher
⇒ llava is never loaded (guaranteed). The watcher unloads it explicitly on exit,
with the short Ollama `keep_alive` as a fallback for hard-kills.

**Why the server does the roast (not the watcher):** Rudi's persona, LLM routing,
TTS, and the WS-to-client display all already live server-side. The watcher sends
text; the server speaks. One source of Rudi's voice.

## Components

- `start_watching.bat` *(new)* — activates `venv`, runs `python server/screen_watcher.py` (mirrors `start_client.bat` structure).
- `server/screen_watcher.py` *(new, standalone process)*:
  - `capture_frame() -> bytes` — `mss` grab of the primary monitor, downscale to ~1024px wide, encode JPEG (~quality 70). Returns bytes.
  - `describe_frame(jpeg: bytes) -> str` — POST to Ollama `/api/chat` with `model=LLAVA_MODEL`, the image (base64 in `images`), `keep_alive=WATCH_KEEPALIVE`, prompt: "Describe this game screenshot in ONE sentence: game, what's happening, and how the player is doing (winning / losing / in danger)."
  - `unload_llava()` — POST Ollama `/api/generate` `{model: LLAVA_MODEL, keep_alive: 0}` to evict the model. Called in a `finally`/`atexit`/signal handler.
  - `main()` — the ~20s loop: capture → describe → POST `/admin/watch_frame`; honor `WATCH_MAX_MINUTES`; robust to transient errors (log + continue).
- `server/main.py` — new endpoint `POST /admin/watch_frame` (admin-key gated, same as other `/admin/*`): body `{description: str, guest?: str}` → builds the roast context → `generate_response` → TTS → `send_response`, all behind the idle-safe gate (`_idle_send_if_safe`-style). Returns `{ok, spoke: bool}`.
- **Roast context builder** — a small helper (in `mario_prompt.py` or inline) that produces the watch system note: Rudi persona + "You're watching {guest_or_'them'} play a game. On their screen right now: {description}. Drop ONE short line — mostly roast/heckle, occasionally a real tip. Stay in character." Roast-first; ~1-in-4 lean toward a genuine tip.
- **Config** (`config.json` server block): `llava_model` (default `"llava-llama3:latest"`), `watch_interval_seconds` (20), `watch_max_minutes` (30), `watch_keepalive` (`"3m"`), `watch_jpeg_width` (1024).
- **Client** *(optional, small)*: show a "👁 watching" indicator while watch frames are arriving; the roast itself renders/speaks like any Rudi line (no special handling).

## Data flow

```
screen → mss JPEG → [watcher] llava → "Fortnite, 12 HP, being chased, building badly"
  → POST /admin/watch_frame → [server] roast ctx → Qwen3 → "Building like you've never
  seen a wall, huh? Ramp UP next time, genius." → TTS → client speaks + shows it
```

## llava lifecycle (the key requirement)

- llava is loaded lazily by Ollama on the watcher's FIRST `describe_frame` call — i.e.
  only after `start_watching.bat` runs.
- The ~20s frame cadence keeps it warm during the session (`keep_alive=3m` > interval).
- On watcher exit (graceful): `unload_llava()` evicts it immediately.
- On hard-kill: the `3m` keep_alive lets Ollama drop it shortly after frames stop.
- Server never calls llava, so the server process alone never loads it.

## Privacy

- Capture runs ONLY while the watcher process is alive (explicit opt-in).
- Frames never leave the box: the watcher turns them into a text description locally;
  only Rudi's spoken line is emitted. The raw JPEG is not persisted (in-memory only).
- `/admin/watch_frame` is admin-key gated; watcher reads the key from config.

## Performance

- Party box (3090 Ti, 24 GB): llava + Qwen3 + SoVITS coexist; heckles land in a few s.
- Dev box (P1000 4 GB, CPU-bound): Ollama will thrash swapping llava ↔ Qwen3; each
  heckle may take 30–60s+. The interval effectively stretches to "when the models
  finish." Functional for testing, slow — documented, not fixed.
- Downscaling to ~1024px keeps llava input cheap.

## Error handling

- Watcher: capture/describe/POST failures log and continue the loop (one bad frame
  never kills the session). Server unreachable → retry next tick.
- `unload_llava()` best-effort (swallow errors) — never block exit.
- Server endpoint: malformed/empty description → 200 `{ok, spoke:false}`, no crash.
- Idle-safe gate: if a real conversation is active, the heckle is skipped (not queued).

## Testing

- `capture_frame` → returns non-empty JPEG (magic bytes `\xff\xd8`); downscale width
  respected. (Skippable in headless CI — guard on display availability.)
- `describe_frame` → mock Ollama; asserts image is base64'd into `images` and
  `keep_alive` is set.
- `unload_llava` → mock Ollama; asserts `keep_alive:0` payload.
- Watch-loop → mock capture+describe+POST; assert cadence + `watch_max_minutes` exit +
  error-continue.
- Server `/admin/watch_frame` → mock `generate_response`/TTS; assert roast-context
  builder includes the description, and the idle-safe gate suppresses when a convo is
  active.
- Manual: run all four bats, open a game, confirm periodic in-character heckles that
  reference what's on screen; close `start_watching.bat` → confirm `ollama ps` shows
  llava unloaded.

## Rollout / safety

- Purely additive: no watcher running ⇒ zero behavior change and llava never loads.
- New dependency: `mss` (add to `server/requirements.txt`).
