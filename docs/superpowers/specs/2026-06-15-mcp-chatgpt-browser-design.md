# mcp-chatgpt — Browser-Driven ChatGPT MCP

**Date:** 2026-06-15
**Status:** Approved design, pre-implementation

## Purpose

An MCP server that lets Claude Code talk to ChatGPT through a real, logged-in
browser session — no OpenAI API. Claude calls clean tools (`new_thread`,
`send`, `close_thread`) instead of hand-driving a browser each time. Supports
threaded multi-turn conversations and returns both text and any generated
images.

**Motivation:** The user has ChatGPT accounts but is not permitted to use the
API. Browser automation against the existing logged-in web session is the
chosen path.

**Risk acknowledged:** Automating chatgpt.com's web UI violates OpenAI's terms
of service. The user accepts this. Selectors will break when OpenAI reships the
UI; repair is isolated to one file.

## Scope

- **In:** ChatGPT only (chatgpt.com). Threaded conversations. Text responses.
  Image-generation responses (downloaded to disk). Persistent login.
- **Out (for now):** Claude.ai, Gemini, other targets. File uploads to GPT.
  Voice. These are future targets, not this build.

## Stack

- Python (matches the repo — single venv, no node toolchain).
- `mcp` (official MCP Python SDK).
- `playwright` (Python).
- Long-running server process holds **one** browser context alive across tool
  calls.

## Browser Session

- `launch_persistent_context(user_data_dir="mcp_chatgpt/profile/")`, **headed**.
  - Headless trips bot-detection and can't perform interactive login.
- **Login once:** `setup_login.py` opens the window, user logs in manually,
  cookies persist to `user_data_dir`. No re-login unless the session expires
  (~weeks) or OpenAI forces re-auth.
- Dedicated profile — does not touch the user's normal Chrome.

## Tools Exposed

| Tool | Input | Returns |
|------|-------|---------|
| `chatgpt_new_thread` | `prompt: str` | `{thread_id, response}` |
| `chatgpt_send` | `thread_id: str`, `prompt: str` | `{response}` |
| `chatgpt_close_thread` | `thread_id: str` | `{ok: bool}` |

- `thread_id` = ChatGPT conversation UUID parsed from the `/c/<uuid>` URL.
  Survives tab close (the URL can be reopened).
- `response` shape (all tools that produce a reply):
  ```json
  { "text": "string", "images": ["mcp_chatgpt/output/<id>.png"], "timed_out": false }
  ```

## Data Flow

1. Claude calls `chatgpt_send(thread_id, prompt)`.
2. `browser.py` resolves the Playwright `Page` for that thread (reopens the
   `/c/<uuid>` URL if the tab was closed).
3. Type `prompt` into the composer, click send.
4. **Wait-for-done** (see below).
5. Scrape the last assistant turn: text + any `<img>` elements.
6. For each image, fetch bytes through the page context (already has auth
   cookies) → save to `mcp_chatgpt/output/<id>.png`. Fallback: click the
   built-in download button.
7. Return `{text, images, timed_out}`.

## Streaming / Done Detection (fragile core — isolated function)

- **Text:** poll the last assistant message; done when **(a)** the Stop button
  reverts to Send **and (b)** the message text is unchanged for ~2s.
- **Image:** done when an `<img>` exists in the last turn with real (non-zero)
  natural dimensions **and** the Send button has reverted. Image generation is
  slow (15–60s) → use a longer timeout than text.
- **Timeout:** return whatever text/images exist so far with `timed_out: true`.
  Never crash.

## Error Handling (clear returns, never crashes)

| Condition | Return |
|-----------|--------|
| Not logged in (login page detected) | error: `"run setup_login.py first"` |
| Cloudflare / challenge page | error: `"solve challenge in the window, then retry"` |
| Usage-limit banner | banner text surfaced verbatim |
| Response timeout | partial `{text, images, timed_out: true}` |
| Unknown `thread_id` | error: `"no such thread"` |

## Files (`mcp_chatgpt/`)

| File | Role |
|------|------|
| `server.py` | MCP tool definitions, wires tools → `browser.py` |
| `browser.py` | Session manager: persistent context, thread→page map, send/recv, image download |
| `wait.py` | Streaming/image done-detection (isolated so it can be tuned/repaired alone) |
| `selectors.py` | **All** CSS selectors in one place — single repair point when UI reships |
| `setup_login.py` | One-time interactive login helper |
| `requirements.txt` | `mcp`, `playwright` |
| `README.md` | Setup steps + Claude Code MCP registration |
| `profile/` | Persistent browser profile (gitignored) |
| `output/` | Downloaded images (gitignored) |

## Registration

- Add to Claude Code MCP config (`.mcp.json` or `claude mcp add`), documented in
  `README.md`.
- Claude does not see the tools until the session restarts with the server
  registered.

## Testing

- Browser scraping resists unit tests; rely on smoke tests:
  1. `setup_login.py` → confirm logged in.
  2. `new_thread("say hi")` → returns non-empty `text`.
  3. `send(thread_id, "what did I just say?")` → confirms thread context held.
  4. `new_thread("generate an image of a red cube")` → returns a saved image
     path that opens as a valid PNG.
- Selectors isolated in `selectors.py` for fast repair.

## Known Fragility (honest)

- OpenAI reships UI → selectors break → fix `selectors.py`.
- Bot-detection may occasionally challenge → headed window lets the user solve
  it live.
- Image markup / auth-URL scheme may change → image download path may need
  repair.
