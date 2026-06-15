# Remote Mirror — Letting Friends Watch / Test Remotely

Friends open ONE public link in any phone browser. They see the **real** pygame
client live and (in testing mode) can type to drive it. No installs for them.

## How it works
- The pygame client captures its own rendered window (~10 fps) and tees the TTS
  audio it plays, pushing both to the server over `ws://localhost:8765/mirror_ingest`.
- The server relays frames + audio to every browser viewer on `ws://.../mirror`.
- The `/friend` page draws the frames on a canvas and plays the audio.
- In `remote` control mode, the page also shows a text box that POSTs to `/friend/say`
  (token + PIN required) — which runs the SAME pipeline as a real typed message, so the
  response appears on the real pygame client and is mirrored back. There is always exactly
  one real pygame client and one controller; viewers are passive.
- Capture only runs while at least one viewer is connected — zero cost otherwise. The
  pygame app runs normally even if the mirror/tunnel is down.

## One-time setup (your PC)
1. Install cloudflared: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/
2. In `config.json` under `"mirror"`, set a real `token` and `pin` (the defaults
   `changeme-token` / `1234` are placeholders — change them).
3. STRONGLY RECOMMENDED before any public exposure: set `"admin_api_key"` to a strong
   secret under `"server"` in `config.json` (see Security below).

## Run a session
1. Start the server + pygame client as usual (`start_server.bat`, then the client).
2. Start the tunnel: `start_tunnel.bat` (or `cloudflared tunnel --url http://localhost:8765`).
3. cloudflared prints a public URL like `https://random-words.trycloudflare.com`.
4. Share with friends: `https://random-words.trycloudflare.com/friend?token=YOUR_TOKEN`
   and tell them the PIN out-of-band.

## Modes
- **Party (default, `control_mode: "station"`):** friends are VIEW-ONLY. The text box is hidden,
  and `/friend/say` rejects input with `reason: "view_only"`.
- **Testing (`control_mode: "remote"`):** the friend page shows a text box; with the right
  token+PIN, whoever is on the page drives the bot. There is only ever ONE controller — the
  page funnels into the same single conversation. Multiple people should share one page/phone.

Flip mode at runtime without restart (include `api_key` if you set `admin_api_key`):
`curl -X POST http://localhost:8765/admin/mirror_mode -H "Content-Type: application/json" -d "{\"mode\":\"remote\",\"api_key\":\"YOUR_ADMIN_KEY\"}"`

## Security — READ BEFORE EXPOSING PUBLICLY
A Cloudflare quick-tunnel exposes your **entire** local server at the public URL, not just
`/friend`. Consequences and mitigations:

1. **`/friend/say` is gated** by `token` + `pin` and by `control_mode` (view-only in station
   mode). Use a strong, non-default token and PIN. Anyone with the link + PIN can drive the
   bot in `remote` mode.
2. **`/admin/mirror_mode` is gated by `admin_api_key`** — but ONLY if you set one. With an
   empty `admin_api_key` (the default), anyone who knows the URL can flip the bot into
   `remote` mode. **Set `admin_api_key` to a strong secret.**
3. **`/admin/simulate_text` is currently UNAUTHENTICATED.** Over a public tunnel this means
   anyone who knows the URL can drive the bot directly, bypassing the `/friend` token+PIN and
   the view-only mode entirely. Mitigate by EITHER:
   - restricting the tunnel to only the `/friend` and `/mirror` paths (use a named cloudflared
     tunnel with ingress rules / path filtering, or put a reverse proxy in front that only
     forwards those paths), OR
   - keeping the tunnel up only while you are actively testing and tearing it down afterward,
     OR
   - adding the same `admin_api_key` guard to `/admin/simulate_text` (a small code change; ask
     a developer).
4. For the actual party, prefer `control_mode: "station"` (view-only) and only switch to
   `remote` for short, supervised testing windows.
