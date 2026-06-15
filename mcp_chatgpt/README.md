# mcp-chatgpt

Talk to ChatGPT from Claude Code through a persistent, logged-in real-Chrome
session — no OpenAI API.

## Setup

```bash
# 1. Create venv + install
venv/Scripts/python.exe -m venv mcp_chatgpt/venv
mcp_chatgpt/venv/Scripts/python.exe -m pip install -r mcp_chatgpt/requirements.txt

# 2. Log into ChatGPT once (opens a real Chrome window)
#    Easiest: log in, then just CLOSE the window — it auto-saves, no terminal needed:
mcp_chatgpt/venv/Scripts/python.exe -m mcp_chatgpt._login_oneshot
#    Alternative (press Enter in the terminal when done instead of closing):
mcp_chatgpt/venv/Scripts/python.exe -m mcp_chatgpt.setup_login
```

The session is saved to `mcp_chatgpt/profile/` and reused on every run — log in
once (re-login only when the session expires or OpenAI forces re-auth).

## Register with Claude Code

The `chatgpt` server is already added to `.mcp.json` at the project root:

```json
{
  "mcpServers": {
    "chatgpt": {
      "type": "stdio",
      "command": "mcp_chatgpt/venv/Scripts/python.exe",
      "args": ["-m", "mcp_chatgpt.server"]
    }
  }
}
```

Restart Claude Code to pick it up.

## Tools

- `chatgpt_new_thread(prompt)` → `{thread_id, response:{text, images[], timed_out}}`
- `chatgpt_send(thread_id, prompt)` → `{response:{...}}`
- `chatgpt_close_thread(thread_id)` → `{ok}`

Generated images are saved under `mcp_chatgpt/output/` and their paths returned.

## When it breaks

OpenAI reships the UI → fix selectors in `mcp_chatgpt/selectors.py` (the only
place selectors live). Re-run the smoke tests in the implementation plan
(`docs/superpowers/plans/2026-06-15-mcp-chatgpt.md`, Task 9).

A visible Chrome window stays open while the server runs — that's required
(headless trips bot-detection and can't log in).
