# Multi-Provider Browser MCP — Design

**Date:** 2026-06-17
**Status:** Approved (design); pending spec review → implementation plan

## Problem

`mcp_chatgpt/` is a browser-driven MCP that talks to ChatGPT through a real
logged-in Chrome (Playwright) instead of the API (the user's supervisor banned
API use). It now has a hardened core: per-account profiles, sticky account
rotation, cap-timer parsing, stochastic-refusal retry, browser-context recovery,
network-error backoff, image baseline-diff + dedup, and a resumable sprite batch.

Two needs surfaced that ChatGPT can't serve:
1. **Grok** — ChatGPT's image filter hard-blocks copyrighted characters (Mario
   was refused on every attempt, named and de-named — it detects the generated
   image's likeness). Grok (`grok-2-image` / grok.com) is permissive and draws
   IP characters freely.
2. **Gemini** — another free, capable image/chat backend the user has an account
   for.

We want both reachable through the **same browser-MCP approach** (their logged-in
accounts, no API keys), reusing all the hardened ChatGPT machinery.

## Goal

Generalize `mcp_chatgpt` into a **multi-provider** browser MCP. Adding a provider
should be a small config block (URL + selectors + marker strings), not a new
codebase. ChatGPT behavior must be **unchanged** (the rudi/mario batch, `.mcp.json`
registration, and existing logins keep working).

Non-goals: API-based access (banned); solving Mario on ChatGPT (confirmed wall);
renaming the package (deferred — keep `mcp_chatgpt` to avoid breaking what works).

## Architecture

A **provider layer** over the existing generic core. One new module, `sites.py`,
holds everything that differs per provider; the rest of the code becomes
provider-agnostic by reading from it.

### `mcp_chatgpt/sites.py` (new)
A `SITES` table keyed by provider name. Each entry (a dataclass or dict) carries:

```
SITES["chatgpt" | "grok" | "gemini"] = Site(
    url,                       # e.g. https://grok.com/
    composer,                  # CSS for the prompt input
    send_button,
    stop_button,               # streaming indicator (None if a site lacks one)
    assistant_turn,            # CSS for the latest assistant message
    generated_image_markers,   # tuple of <img src> substrings that mark a generated image
    login_url_fragment,        # substring in URL when logged out
    challenge_text_markers,    # Cloudflare / "verify you are human" strings
    usage_limit_markers,       # cap/limit wording (per site)
    refusal_markers,           # optional: guardrail-refusal wording
    response_picker,           # optional: {markers, buttons} for A/B chooser
)
```

ChatGPT's current `selectors.py` constants move into `SITES["chatgpt"]` verbatim
(zero behavior change). `selectors.py` is either deleted or kept as a thin
re-export of `SITES["chatgpt"]` for any external importer.

### `browser.py` (generalize)
`ChatGPTSession` takes a `provider` (default `"chatgpt"`). All DOM/marker access
goes through `self.site = SITES[provider]` instead of hardcoded `selectors.*`.
Class keeps its name for now (or aliased `BrowserAISession = ChatGPTSession`).
`get_session()` becomes provider-aware (one session object can hold contexts for
multiple providers, keyed by `(provider, account)` — see Profiles).

### `parsing.py` (generalize)
`classify_page_state(url, body, site)` and `parse_reset_seconds(text)` take the
site's marker lists rather than importing `selectors`. `parse_reset_seconds` is
already pure and stays; it may need per-site tuning if Grok/Gemini phrase resets
differently (handled during live verification).

### `stability.py`, `rotation.py` (unchanged)
Already provider-agnostic. The net-error backoff, sticky `AccountPool`,
refusal-retry, and lagging-image grace all apply to every provider for free.

### `batch_sprites.py` (extend)
Add `--provider` (default `chatgpt`). The session is created for that provider;
everything else (sprite_prompts.txt parsing, rotation, cutout, manifest) is
unchanged. Enables `--provider grok --character mario`.

### `server.py` (extend)
Tools gain a `provider` param defaulting to `"chatgpt"` so existing tool calls
are unchanged: `chatgpt_new_thread(prompt, provider="chatgpt", account="default")`,
etc. (Per-provider named tools rejected — one generic surface is DRY.)

### `_login_oneshot.py` (extend)
`python -m mcp_chatgpt._login_oneshot <provider> <account>` — opens that
provider's URL for interactive login, saves the per-provider profile.

## Profiles

Per-provider, per-account profile dirs to avoid collisions:
`mcp_chatgpt/profile/<provider>/_accounts/<account>` (default account =
`profile/<provider>/`). ChatGPT's existing `profile/` (and `profile/_accounts/*`)
is migrated to `profile/chatgpt/` once, OR `profile_dir()` special-cases
`chatgpt` to the legacy path so current logins survive without a move. Decision
deferred to the plan (whichever is lower-risk verified against the live dirs).

## Selector discovery (the unavoidable manual loop)

ChatGPT's selectors are verified live. **Grok's and Gemini's are not** and can't
be without the user's logged-in sites. Per provider:
1. Scaffold best-effort selectors in `SITES[provider]` from public knowledge of
   the site.
2. User runs `_login_oneshot <provider>` and logs in.
3. Drive it live (a probe script / one batch sprite), read the real DOM, fix the
   selectors + markers. Iterate until a text reply and an image both work.

This mirrors how the original ChatGPT MCP was built. Expect one short live loop
per provider.

## Build order

1. **Grok** first — permissive, unblocks Mario immediately.
2. **Gemini** second.

Each: add `SITES[provider]` → login → live-verify text + image → run a few
sprites → confirm.

## Error handling

Inherited from the hardened core, now per-provider via `SITES` markers:
- Usage/cap → `usage_limit_markers` + `parse_reset_seconds` → wait/rotate.
- Guardrail refusal → `refusal_markers` → stochastic-retry then rotate.
- Net/HTTP error → backoff on same account (no blast).
- Stale/closed context → `reset_account` + retry.
- Not logged in → drop account from rotation, point at the login one-shot.

## Testing

- **Unit (pure, no browser):** `SITES` shape/required-keys per provider;
  `parse_reset_seconds` for any new Grok/Gemini reset phrasings; `classify_page_state`
  with each site's markers; existing rotation/stability tests stay green.
- **Live (manual, per provider):** login → text reply → image gen → background
  cutout → one sprite end-to-end. Documented as a checklist, not automated.

## Risks

- **Selectors drift / unknown DOM:** Grok/Gemini selectors are guesses until
  live-verified; the plan must include the verification loop, not assume it works.
- **Profile migration:** moving ChatGPT's profile could break current logins —
  prefer a path alias over a move; verify before touching.
- **Site quirks:** Grok/Gemini may lack a Stop button, stream differently, or
  serve images from hosts we must discover — handled in live verification, may
  need small `stability`/`browser` tweaks behind the provider abstraction.
