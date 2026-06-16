# Admin Controls — Complete Reference

Everything you can do to control the bot while it runs: keyboard controls on the
pygame client, slash commands, the HTTP admin API, and the remote/mirror page.

There are **three** control surfaces:

1. **Pygame client keyboard** — physical keys on the machine driving the screen.
2. **HTTP admin API** — `POST`/`GET` to the server (used by the slash commands,
   and callable directly with `curl`).
3. **Remote friend page** — the public `/friend` link guests use over the tunnel.

---

## 1. Pygame Client — Keyboard Controls

Pressed directly on the laptop/Pi running the display.

| Key | Action |
|-----|--------|
| **F1** | Toggle help overlay |
| **F3** | Toggle chat history |
| **F4** | Toggle health overlay (cached `/health`) |
| **F5** | Toggle party mode |
| **F6** | Toggle leaderboard (auto-hides ~15s) |
| **F7** | Next background. **Ctrl+F7** = background picker; **Shift+F7** = previous bg |
| **F8** | Toggle background auto-cycle |
| **F9** | Volume down (−10%) |
| **F10** | Volume up (+10%) |
| **F11** | Toggle fullscreen |
| **F12** | **Panic mode** — mutes audio + shows a "Technical Difficulties" screen |
| **TAB** | Toggle keyboard/admin mode (type slash commands or chat) |
| **1–0** | Quick game/joke/song triggers (when NOT in keyboard mode) |
| **Ctrl+V** | Paste into the input |
| **↑ ↑ ↓ ↓ ← →** | Konami sequence — also toggles panic mode |

> There is **no F2**.
>
> ⚠️ **Panic is a single F12 press** (and the arrow Konami). It is easy to trip
> by accident. It does not log unless `DEBUG_DISPLAY` is on. Press F12 again to
> exit. (The codebase docstring that says "triple-tap F12" is stale — the code
> toggles on a single press.)

---

## 2. Slash Commands

Type these after pressing **TAB** (keyboard mode) on the pygame client. Each
maps to an HTTP call to the server.

| Command | Does | Hits |
|---------|------|------|
| `/announce <text>` | Broadcast an announcement (Mario speaks it) | `POST /admin/announce` |
| `/emotion <emotion>` | Force an emotion | `POST /admin/set_emotion` |
| `/memorial [event]` | Trigger a memorial event (default `lisa_webb_memorial`) | `POST /admin/trigger_event/<name>` |
| `/event <name>` | Trigger a named event | `POST /admin/trigger_event/<name>` |
| `/events` | List available events | `GET /admin/events` |
| `/stopgame` | Force-stop the active game | `POST /admin/force_stop_game` |
| `/reset` | Reset party stats | `POST /admin/reset` |
| `/pause` | Pause the idle loop | `GET /pause_idle` |
| `/sovits` | Restart the GPT-SoVITS subprocess | `GET /restart_sovits` |
| `/leaderboard` | Show leaderboard | `GET /leaderboard` |
| `/stats` | Show party stats | `GET /stats` |
| `/summary` | Party summary snapshot | `GET /admin/party_summary` |
| `/games` | List game number triggers | (local text) |
| `/help` | List commands | (local text) |
| `/reload` | Reload config | `POST /api/reload` — **⚠️ broken, see below** |
| `/health` | Show server health | `GET /api/health` — **⚠️ broken, see below** |

> **⚠️ Two slash commands currently point at non-existent routes:**
> `/reload` posts to `/api/reload` and `/health` fetches `/api/health`, but the
> server only serves `/config/reload` and `/health` (no `/api/*` prefix exists).
> Until fixed, use the HTTP API directly: `POST /config/reload` and `GET /health`.
> (F4's health overlay also reads `/api/health`, so it may show stale/no data.)

---

## 3. HTTP Admin API

Base URL: `http://<server-host>:8765`. JSON bodies. Examples assume localhost.

### Auth model
- **Mutating `/admin/*` endpoints** (reset, set_emotion, announce, simulate_text,
  mirror_mode, force_stop_game, trigger_event, reset_event, register_face,
  lookup_face, switch_character) require the **admin key** when one is configured
  in `config.json` → `server.admin_api_key`. Pass it in the JSON body as
  `{"api_key": "<key>", ...}`. If no key is configured, they are open.
- **Read/utility endpoints** (`/health`, `/stats`, `/leaderboard`, `/pause_idle`,
  `/restart_sovits`, `/tts`, `/admin/party_summary`, `/admin/game_stats`,
  `/admin/faces`, `/admin/events`, `/admin/tts_audit*`, `/admin/probe`) are **not**
  key-gated. They are safe on a trusted LAN, but **do not expose the raw `:8765`
  port to the internet** — only the `/friend` page is meant to face the tunnel.

### Endpoints

| Method & Path | What it does | Key? |
|---------------|--------------|------|
| `GET /health` | Server health: emotion, cache, timing | no |
| `GET /stats` | Party stats JSON | no |
| `GET /leaderboard` | Leaderboard + fun stats | no |
| `POST /config/reload` | Reload `config.json` | no |
| `GET /pause_idle` | Pause/resume the idle loop | no |
| `GET /restart_sovits` | Kill + restart the GPT-SoVITS subprocess | no |
| `GET /tts?text=…` | Synthesize text, returns WAV (debug) | no |
| `POST /admin/reset` | Reset party stats | yes |
| `POST /admin/set_emotion` | Force emotion `{"emotion": "..."}` | yes |
| `POST /admin/announce` | Broadcast `{"text": "..."}` | yes |
| `POST /admin/simulate_text` | Inject text as if typed `{"text": "..."}` | yes |
| `POST /admin/force_stop_game` | Cancel the active game | yes |
| `GET /admin/game_stats` | Game pool sizes / recent games | no |
| `POST /admin/trigger_event/{name}` | Fire a scripted event | yes |
| `POST /admin/reset_event/{name}` | Reset an event's fired state | yes |
| `GET /admin/events` | List events | no |
| `POST /admin/trigger_memorial` | Trigger memorial flow | (see code) |
| `POST /admin/register_face` | Register a face encoding | yes |
| `POST /admin/lookup_face` | Look up a face | yes |
| `GET /admin/faces` | List stored faces | no |
| `GET /admin/party_summary` | Full party-state snapshot | no |
| `POST /admin/switch_character` | Swap the active character | yes |
| `POST /admin/tts_audit` / `GET /admin/tts_audit/results` / `POST /admin/tts_audit/best_of_n` | TTS quality audit tools | no |
| `POST /admin/mirror_mode` | Flip remote control mode (below) | yes |

---

## 4. Remote Mirror / Friend Page

Guests watch (and, in remote mode, chat with) the bot from their phone over the
public tunnel. Config lives in `config.json` → `mirror`.

### The link
```
https://<tunnel-host>/friend?token=<mirror.token>
```
Guests then enter the **PIN** (`mirror.pin`) and a temporary **name** to chat.

### Control modes (`mirror.control_mode`)
- **`station`** — view-only. Everyone watches; nobody can drive the bot.
- **`remote`** — viewers who pass token + PIN can send messages.

Flip at runtime (no restart):
```
POST /admin/mirror_mode   {"api_key": "<admin key>", "mode": "remote"|"station"}
```

### One-talker turn-lock (remote mode)
- Many people can **view** at once; the page shows a **👁 N watching** counter.
- Only **one person talks at a time**. The first to send holds the "turn"; each
  message refreshes it. After **30s of silence** it auto-frees for the next person.
- While someone else holds it, other guests' input is disabled and shows
  *"March is chatting with `<name>`…"*.
- Everyone sees a **live transcript** (last 6 lines): `Name: message` and
  `<Character>: reply`.

### Endpoints behind the page
| Method & Path | Purpose |
|---------------|---------|
| `GET /friend?token=…` | Serves the page (control mode injected) |
| `POST /friend/say` | `{text, token, pin, name, id}` — gated by PIN + turn-lock |
| `WS /mirror` | Viewer stream: binary frames/audio + JSON control events |
| `WS /mirror_ingest` | The pygame client pushes frames/audio here (internal) |

> **Security:** the PIN is intentionally weak (party-grade). Names + browser ids
> are not authenticated — the turn-lock is best-effort UX, not a security
> boundary. The strong **admin key** gates the `/admin/*` actions, never `/friend`.

---

## 5. Known Issues / Gotchas

- **`/reload` and `/health` slash commands are broken** — they call `/api/reload`
  and `/api/health`, which don't exist (see §2). Use `POST /config/reload` and
  `GET /health` directly. F4's health overlay reads `/api/health` too.
- **Panic is a single F12** (and arrow Konami) — easy to hit by accident; press
  F12 again to clear.
- The tunnel URL changes every time `cloudflared` restarts; reshare the new link.
