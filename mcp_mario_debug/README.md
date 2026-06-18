# mario-debug MCP

Gives Claude Code eyes/ears/hands on the running Mario AI app: see the pygame
screen, verify played audio, tail server+client logs, read on-screen state, and
inject input (a guest speaking / appearing).

## Setup

```bash
python -m venv mcp_mario_debug/venv
mcp_mario_debug/venv/Scripts/python.exe -m pip install -r mcp_mario_debug/requirements.txt
```

Registered in `.mcp.json` as `mario-debug` (stdio). Reload MCP servers in Claude
Code to pick it up.

## Enabling the debug surface

The debug endpoints are **off by default**. Launch the server AND the pygame
client with the environment variable `MARIO_DEBUG=1`:

- Server `/debug/log` + `/admin/inject_audio` activate when the server process
  has `MARIO_DEBUG=1`.
- The client debug HTTP server (`127.0.0.1:8770`) only starts when the client
  process has `MARIO_DEBUG=1`.

Both bind localhost only and are never exposed on the Cloudflare tunnel.

```bash
# Windows (PowerShell), before launching:
$env:MARIO_DEBUG = "1"; .\start_server.bat
$env:MARIO_DEBUG = "1"; .\venv\Scripts\python.exe client\main.py
```

## Tools

| Tool | Purpose |
|------|---------|
| `mario_health` | server health (ws_connected, tts, emotion, uptime, cache) |
| `mario_state` | on-screen state (state, emotion, speaking, pose, full+shown text) |
| `mario_audio_out(n)` | last N played clips (text, duration, peak, rms, sample-rate, engine_guess, played_ok) |
| `mario_logs(source, grep, level, n)` | tail server/client logs (`source = server\|client\|both`) |
| `mario_screenshot` | PNG of the pygame client (client frame, else OS window grab) |
| `mario_send_text(text)` | inject a typed user message |
| `mario_inject_audio(wav_path)` | simulate a guest speaking (WAV → STT → reply) |
| `mario_inject_frame(image_path)` | simulate a guest appearing (image → person/face detection) |
| `mario_set_emotion(emotion)` | force the current emotion |
| `mario_trigger_event(name)` | trigger a shot/ceremony event |
| `mario_set_night_phase(phase)` | override night phase |

Ports: server `127.0.0.1:8765`, client debug `127.0.0.1:8770`.
