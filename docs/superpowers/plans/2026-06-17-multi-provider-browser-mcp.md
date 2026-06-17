# Multi-Provider Browser MCP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generalize the `mcp_chatgpt` browser MCP into a multi-provider tool so Grok and Gemini reuse the same hardened session/rotation/batch/cap-handling machinery, with ChatGPT behavior unchanged.

**Architecture:** Introduce a `sites.py` provider table holding everything that differs per provider (URL, selectors, marker strings). Make `browser.py`/`parsing.py` read from `SITES[provider]` instead of hardcoded `selectors.*`. Thread a `provider` param (default `"chatgpt"`) through the session, batch, server tools, and login one-shot. Per-provider profile dirs, with `chatgpt` aliased to the legacy path so existing logins survive.

**Tech Stack:** Python 3, Playwright (async), FastMCP, pytest. Tests run with the **main** venv (`venv/Scripts/python.exe -m pytest`); the mcp venv (`mcp_chatgpt/venv`) runs the batch/server but lacks pytest. Pure modules (sites, parsing, rotation, stability) import without Playwright.

---

## File Structure

- **Create** `mcp_chatgpt/sites.py` — `Site` dataclass + `SITES` table (chatgpt/grok/gemini). Single source of per-provider DOM + markers.
- **Modify** `mcp_chatgpt/selectors.py` — reduce to a thin back-compat re-export of `SITES["chatgpt"]` fields (keep names other code imports).
- **Modify** `mcp_chatgpt/browser.py` — session takes `provider`; resolve `self.site = SITES[provider]`; `profile_dir(provider, account)`.
- **Modify** `mcp_chatgpt/parsing.py` — `classify_page_state(url, body, site)` uses the passed site's markers.
- **Modify** `mcp_chatgpt/batch_sprites.py` — add `--provider`; pass to `get_session`/session.
- **Modify** `mcp_chatgpt/server.py` — tools accept `provider="chatgpt"`.
- **Modify** `mcp_chatgpt/_login_oneshot.py` — `<provider> <account>` args; open the provider URL.
- **Create/Modify** `tests/test_mcp_chatgpt_sites.py` — SITES shape + chatgpt-parity tests.
- **Modify** `tests/test_mcp_chatgpt_parsing.py` — classify with per-site markers.

Pure/testable tasks (1,3,4,5,7) use TDD. Browser/DOM tasks (2 wiring, 8 Grok, 9 Gemini) get structural tests + a live-verification checklist (selectors can't be unit-tested without the logged-in site).

---

### Task 1: `sites.py` — Site table with the ChatGPT entry

**Files:**
- Create: `mcp_chatgpt/sites.py`
- Test: `tests/test_mcp_chatgpt_sites.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_mcp_chatgpt_sites.py
import pytest
from mcp_chatgpt.sites import SITES, Site, get_site

REQUIRED = ("url", "composer", "send_button", "assistant_turn",
            "generated_image_markers", "login_url_fragment",
            "challenge_text_markers", "usage_limit_markers")

def test_chatgpt_site_present_and_complete():
    s = get_site("chatgpt")
    assert isinstance(s, Site)
    for field in REQUIRED:
        assert getattr(s, field), f"chatgpt site missing {field}"

def test_chatgpt_values_match_legacy_selectors():
    s = get_site("chatgpt")
    assert s.url == "https://chatgpt.com/"
    assert s.composer == "#prompt-textarea"
    assert s.send_button == "[data-testid='send-button']"
    assert s.assistant_turn == "[data-message-author-role='assistant']"
    assert "oaiusercontent.com" in s.generated_image_markers
    assert s.login_url_fragment == "/auth/login"

def test_unknown_provider_raises():
    with pytest.raises(KeyError):
        get_site("nope")

def test_image_markers_and_limit_markers_are_tuples():
    s = get_site("chatgpt")
    assert isinstance(s.generated_image_markers, tuple)
    assert isinstance(s.usage_limit_markers, tuple)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/Scripts/python.exe -m pytest tests/test_mcp_chatgpt_sites.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'mcp_chatgpt.sites'`

- [ ] **Step 3: Write the implementation**

```python
# mcp_chatgpt/sites.py
"""Per-provider browser config — the ONLY place site DOM/markers differ.

Adding a provider = one Site entry. Everything else (session, rotation, batch,
cap handling) is provider-agnostic and reads from SITES[provider]. Verified live
against each provider's DOM (chatgpt: 2026-06-15)."""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Site:
    url: str
    composer: str
    send_button: str
    assistant_turn: str
    generated_image_markers: tuple
    login_url_fragment: str
    challenge_text_markers: tuple
    usage_limit_markers: tuple
    stop_button: str = ""                 # streaming indicator; "" if the site lacks one
    refusal_markers: tuple = ()
    response_picker_markers: tuple = ()
    response_picker_buttons: tuple = ()


SITES = {
    "chatgpt": Site(
        url="https://chatgpt.com/",
        composer="#prompt-textarea",
        send_button="[data-testid='send-button']",
        stop_button="[data-testid='stop-button']",
        assistant_turn="[data-message-author-role='assistant']",
        generated_image_markers=("/backend-api/", "oaiusercontent.com"),
        login_url_fragment="/auth/login",
        challenge_text_markers=("Verify you are human", "Just a moment",
                                "Checking your browser"),
        usage_limit_markers=(
            "You've reached", "you've hit", "usage limit", "limit reached",
            "free plan limit", "limit resets", "plan limit for image",
            "too many requests", "try again later", "rate limit", "come back later",
        ),
        refusal_markers=("may violate our guardrails", "violate our content policy",
                         "can't help with that", "unable to generate"),
        response_picker_markers=("which response do you prefer", "prefer this response",
                                 "compare these responses"),
        response_picker_buttons=(
            "button:has-text('I prefer this response')",
            "button:has-text('prefer this response')",
            "button:has-text('Keep this response')",
            "[data-testid='paragen-prefer-button']",
        ),
    ),
}


def get_site(provider: str) -> Site:
    """Return the Site for a provider, or raise KeyError with the known list."""
    try:
        return SITES[provider]
    except KeyError:
        raise KeyError(f"unknown provider {provider!r}; known: {sorted(SITES)}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/Scripts/python.exe -m pytest tests/test_mcp_chatgpt_sites.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add mcp_chatgpt/sites.py tests/test_mcp_chatgpt_sites.py
git commit -m "feat(mcp-chatgpt): add sites.py provider table (chatgpt entry)"
```

---

### Task 2: `selectors.py` becomes a back-compat shim

**Files:**
- Modify: `mcp_chatgpt/selectors.py`

- [ ] **Step 1: Replace selectors.py body with a re-export of the chatgpt Site**

```python
# mcp_chatgpt/selectors.py
"""Back-compat shim. Canonical per-provider config now lives in sites.py.
These module constants mirror SITES['chatgpt'] so older imports keep working."""
from mcp_chatgpt.sites import get_site

_S = get_site("chatgpt")
URL = _S.url
COMPOSER = _S.composer
SEND_BUTTON = _S.send_button
STOP_BUTTON = _S.stop_button
ASSISTANT_TURN = _S.assistant_turn
GENERATED_IMAGE_MARKERS = _S.generated_image_markers
LOGIN_URL_FRAGMENT = _S.login_url_fragment
CHALLENGE_TEXT_MARKERS = _S.challenge_text_markers
USAGE_LIMIT_MARKERS = _S.usage_limit_markers
RESPONSE_PICKER_MARKERS = _S.response_picker_markers
RESPONSE_PICKER_BUTTONS = _S.response_picker_buttons
```

- [ ] **Step 2: Verify nothing imports a now-missing name**

Run: `venv/Scripts/python.exe -c "import mcp_chatgpt.selectors as s; print(s.URL, s.COMPOSER, len(s.USAGE_LIMIT_MARKERS))"`
Expected: prints `https://chatgpt.com/ #prompt-textarea 11`

- [ ] **Step 3: Run the existing MCP unit tests (still green)**

Run: `venv/Scripts/python.exe -m pytest tests/test_mcp_chatgpt_parsing.py tests/test_mcp_chatgpt_stability.py tests/test_mcp_chatgpt_accounts.py tests/test_mcp_chatgpt_sites.py -q`
Expected: PASS (all)

- [ ] **Step 4: Commit**

```bash
git add mcp_chatgpt/selectors.py
git commit -m "refactor(mcp-chatgpt): selectors.py re-exports SITES['chatgpt']"
```

---

### Task 3: `parsing.classify_page_state` takes a site

**Files:**
- Modify: `mcp_chatgpt/parsing.py`
- Test: `tests/test_mcp_chatgpt_parsing.py`

- [ ] **Step 1: Write the failing test (append to the parsing test file)**

```python
from mcp_chatgpt.parsing import classify_page_state
from mcp_chatgpt.sites import get_site

def test_classify_login_with_site():
    s = get_site("chatgpt")
    assert classify_page_state("https://auth.openai.com/auth/login", "", s) == "login"

def test_classify_challenge_with_site():
    s = get_site("chatgpt")
    assert classify_page_state("https://chatgpt.com/", "Just a moment...", s) == "challenge"

def test_classify_ok_with_site():
    s = get_site("chatgpt")
    assert classify_page_state("https://chatgpt.com/c/x", "hello", s) == "ok"
```

- [ ] **Step 2: Run to verify it fails**

Run: `venv/Scripts/python.exe -m pytest tests/test_mcp_chatgpt_parsing.py -k with_site -v`
Expected: FAIL (classify_page_state takes 2 args, not 3)

- [ ] **Step 3: Update classify_page_state to take a site**

In `mcp_chatgpt/parsing.py`, replace the function (currently imports `selectors`) with:

```python
def classify_page_state(url: str, body_text: str, site) -> str:
    """Return one of: 'ok', 'login', 'challenge'. `site` is a sites.Site."""
    url = url or ""
    body = body_text or ""
    if site.login_url_fragment in url:
        return "login"
    if any(marker in body for marker in site.challenge_text_markers):
        return "challenge"
    return "ok"
```

Remove the now-unused `from mcp_chatgpt import selectors` import at the top of `parsing.py` if present.

- [ ] **Step 4: Run to verify it passes (and old parsing tests still pass)**

Run: `venv/Scripts/python.exe -m pytest tests/test_mcp_chatgpt_parsing.py -q`
Expected: PASS (all — older classify tests that called the 2-arg form must be updated in this same step to pass `get_site("chatgpt")`; update any `classify_page_state(url, body)` call in the test file to `classify_page_state(url, body, get_site("chatgpt"))`).

- [ ] **Step 5: Commit**

```bash
git add mcp_chatgpt/parsing.py tests/test_mcp_chatgpt_parsing.py
git commit -m "refactor(mcp-chatgpt): classify_page_state takes a Site"
```

---

### Task 4: Per-provider profiles (`profile_dir(provider, account)`)

**Files:**
- Modify: `mcp_chatgpt/browser.py`
- Test: `tests/test_mcp_chatgpt_sites.py` (append — profile_dir is pure)

- [ ] **Step 1: Write the failing test**

```python
def test_profile_dir_chatgpt_uses_legacy_paths():
    from mcp_chatgpt.browser import profile_dir, PROFILE_DIR
    import os
    # chatgpt keeps the legacy locations so existing logins survive
    assert profile_dir("chatgpt", "default") == PROFILE_DIR
    assert profile_dir("chatgpt", "work") == os.path.join(PROFILE_DIR, "_accounts", "work")

def test_profile_dir_other_providers_namespaced():
    from mcp_chatgpt.browser import profile_dir, PROFILE_DIR
    import os
    assert profile_dir("grok", "default") == os.path.join(PROFILE_DIR, "grok")
    assert profile_dir("grok", "work") == os.path.join(PROFILE_DIR, "grok", "_accounts", "work")
```

- [ ] **Step 2: Run to verify it fails**

Run: `venv/Scripts/python.exe -m pytest tests/test_mcp_chatgpt_sites.py -k profile_dir -v`
Expected: FAIL (`profile_dir` currently takes only `account`)

- [ ] **Step 3: Update `profile_dir` in `browser.py`**

Replace the existing `profile_dir(account=DEFAULT_ACCOUNT)` with:

```python
def profile_dir(provider: str = "chatgpt", account: str = DEFAULT_ACCOUNT) -> str:
    """Browser-profile dir for a (provider, account).

    chatgpt keeps the LEGACY paths (profile/ and profile/_accounts/<name>) so
    existing logins survive the generalization. Other providers are namespaced
    under profile/<provider>/(_accounts/<name>)."""
    if provider == "chatgpt":
        base = PROFILE_DIR
    else:
        base = os.path.join(PROFILE_DIR, provider)
    if account == DEFAULT_ACCOUNT:
        return base
    return os.path.join(base, "_accounts", account)
```

- [ ] **Step 4: Run to verify it passes**

Run: `venv/Scripts/python.exe -m pytest tests/test_mcp_chatgpt_sites.py -k profile_dir -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add mcp_chatgpt/browser.py tests/test_mcp_chatgpt_sites.py
git commit -m "feat(mcp-chatgpt): per-provider profile dirs (chatgpt aliased to legacy)"
```

---

### Task 5: Thread `provider` through `ChatGPTSession`

**Files:**
- Modify: `mcp_chatgpt/browser.py`

- [ ] **Step 1: Add provider to the session + resolve the Site**

In `ChatGPTSession.__init__`, add `provider`:

```python
def __init__(self, provider: str = "chatgpt") -> None:
    self.provider = provider
    self.site = get_site(provider)        # from mcp_chatgpt.sites import get_site
    self._pw = None
    self._contexts: dict = {}
    self._threads: dict[str, Page] = {}
    self._lock = asyncio.Lock()
    self._saved_srcs: set = set()
```

- [ ] **Step 2: Replace every `selectors.X` use with `self.site.X`**

In `browser.py`, swap (exact list):
- `selectors.URL` → `self.site.url`
- `selectors.COMPOSER` → `self.site.composer`
- `selectors.SEND_BUTTON` → `self.site.send_button`
- `selectors.STOP_BUTTON` → `self.site.stop_button`
- `selectors.ASSISTANT_TURN` → `self.site.assistant_turn`
- `selectors.GENERATED_IMAGE_MARKERS` → `self.site.generated_image_markers`
- `selectors.RESPONSE_PICKER_MARKERS` → `self.site.response_picker_markers`
- `selectors.RESPONSE_PICKER_BUTTONS` → `self.site.response_picker_buttons`

Update `profile_dir(account)` calls → `profile_dir(self.provider, account)`.
Update `classify_page_state(page.url, body)` → `classify_page_state(page.url, body, self.site)`.
Update `get_session()` to cache one session per provider:

```python
_sessions: dict = {}

def get_session(provider: str = "chatgpt") -> "ChatGPTSession":
    s = _sessions.get(provider)
    if s is None:
        s = _sessions[provider] = ChatGPTSession(provider)
    return s
```

Keep `from mcp_chatgpt import selectors` removed; add `from mcp_chatgpt.sites import get_site`.

- [ ] **Step 3: Verify the module imports and the chatgpt session resolves**

Run: `mcp_chatgpt/venv/Scripts/python.exe -c "from mcp_chatgpt.browser import get_session; s=get_session(); print(s.provider, s.site.url)"`
Expected: prints `chatgpt https://chatgpt.com/`

- [ ] **Step 4: Run the full MCP unit suite (no regressions)**

Run: `venv/Scripts/python.exe -m pytest tests/test_mcp_chatgpt_parsing.py tests/test_mcp_chatgpt_stability.py tests/test_mcp_chatgpt_accounts.py tests/test_mcp_chatgpt_sites.py -q`
Expected: PASS (all)

- [ ] **Step 5: Commit**

```bash
git add mcp_chatgpt/browser.py
git commit -m "refactor(mcp-chatgpt): session reads per-provider Site, provider-keyed get_session"
```

---

### Task 6: `batch_sprites.py --provider`

**Files:**
- Modify: `mcp_chatgpt/batch_sprites.py`

- [ ] **Step 1: Add the `--provider` arg and pass it to the session**

In the `argparse` block add:

```python
ap.add_argument("--provider", default="chatgpt",
                help="browser provider: chatgpt | grok | gemini")
```

Change `session = get_session()` in `run()` to accept a provider param: update `run(...)`'s signature to take `provider: str` and call `get_session(provider)`. Update the `__main__` call to pass `a.provider` into `run(...)`. The cap message in logs already prints per-account; no other change.

- [ ] **Step 2: Verify it imports + arg parses**

Run: `mcp_chatgpt/venv/Scripts/python.exe mcp_chatgpt/batch_sprites.py --help`
Expected: help text includes `--provider`

- [ ] **Step 3: Commit**

```bash
git add mcp_chatgpt/batch_sprites.py
git commit -m "feat(mcp-chatgpt): batch_sprites --provider (default chatgpt)"
```

---

### Task 7: `_login_oneshot.py <provider> <account>` + server tool `provider` param

**Files:**
- Modify: `mcp_chatgpt/_login_oneshot.py`
- Modify: `mcp_chatgpt/server.py`

- [ ] **Step 1: `_login_oneshot` opens the provider URL**

Update `_login_oneshot.py` `main(account)` → `main(provider, account)`: use `profile_dir(provider, account)` and `get_site(provider).url` for `page.goto`. Update `__main__` to read `sys.argv[1]` as provider (default `"chatgpt"`) and `sys.argv[2]` as account (default `"default"`).

- [ ] **Step 2: Verify the login one-shot help path (no login, just arg wiring)**

Run: `mcp_chatgpt/venv/Scripts/python.exe -c "import mcp_chatgpt._login_oneshot as L; import inspect; print('provider' in inspect.signature(L.main).parameters)"`
Expected: prints `True`

- [ ] **Step 3: Add `provider` param to the FastMCP tools**

In `server.py`, add `provider: str = "chatgpt"` to `chatgpt_new_thread`, `chatgpt_send`, `chatgpt_close_thread`; pass it to `get_session(provider)` / the session call. Default keeps existing tool calls unchanged.

- [ ] **Step 4: Verify the server lists tools**

Run: `mcp_chatgpt/venv/Scripts/python.exe -c "import mcp_chatgpt.server as s; print('ok')"`
Expected: prints `ok`

- [ ] **Step 5: Commit**

```bash
git add mcp_chatgpt/_login_oneshot.py mcp_chatgpt/server.py
git commit -m "feat(mcp-chatgpt): provider arg for login one-shot + server tools"
```

---

### Task 8: Grok site config + live verification

**Files:**
- Modify: `mcp_chatgpt/sites.py`
- Test: `tests/test_mcp_chatgpt_sites.py`

- [ ] **Step 1: Add a best-effort `SITES["grok"]` + a shape test**

Append to `tests/test_mcp_chatgpt_sites.py`:

```python
def test_grok_site_present_and_complete():
    s = get_site("grok")
    for f in ("url", "composer", "send_button", "assistant_turn",
              "generated_image_markers", "login_url_fragment", "usage_limit_markers"):
        assert getattr(s, f), f"grok site missing {f}"
    assert s.url.startswith("https://grok.com")
```

Add to `SITES` in `sites.py` (selectors are BEST-EFFORT, marked for live fix):

```python
    # SCAFFOLD — selectors are best-effort guesses; verify live (Step 3) before trusting.
    "grok": Site(
        url="https://grok.com/",
        composer="textarea, [contenteditable='true']",
        send_button="button[type='submit'], button[aria-label*='Send' i]",
        stop_button="button[aria-label*='Stop' i]",
        assistant_turn="[data-testid*='message'], .message-bubble",
        generated_image_markers=("assets.grok.com", "imggen", "grok-attachments"),
        login_url_fragment="/sign-in",
        challenge_text_markers=("Verify you are human", "Just a moment"),
        usage_limit_markers=("rate limit", "try again later", "out of",
                             "limit reached", "upgrade to"),
        refusal_markers=("can't help with that", "i can't create"),
    ),
```

- [ ] **Step 2: Run the shape test**

Run: `venv/Scripts/python.exe -m pytest tests/test_mcp_chatgpt_sites.py -k grok -v`
Expected: PASS (shape only — does NOT prove the selectors work)

- [ ] **Step 3: LIVE VERIFICATION (manual, requires the user logged into grok.com)**

This step is interactive and cannot be unit-tested. Do, in order:
1. User runs: `mcp_chatgpt/venv/Scripts/python.exe -m mcp_chatgpt._login_oneshot grok` → logs into grok.com → closes the window.
2. Drive one probe and inspect the real DOM. Run a throwaway script that opens the grok profile, navigates to `grok.com`, and prints: the composer element, the send button, the latest assistant turn HTML, and (after a "draw a red apple" prompt) every `<img src>` on the page.
3. Fix `SITES["grok"]` fields against what the DOM actually shows: composer selector, send button, assistant-turn selector, the real generated-image src host (replace the guessed `generated_image_markers`), the logged-out URL fragment, and the actual cap/refusal wording.
4. Re-run the probe until: a text prompt returns text, AND an image prompt downloads a real PNG (>5KB) via the existing `_download_images` path.
5. If grok streams without a Stop button, set `stop_button=""` — the stability loop already tolerates that (it relies on text/image stability, not only the Stop button).

- [ ] **Step 4: End-to-end smoke — generate 2 Mario sprites via Grok**

Run: `mcp_chatgpt/venv/Scripts/python.exe -u mcp_chatgpt/batch_sprites.py --provider grok --character mario --start 1 --accounts default --delay 10`
Let it produce 2 sprites, then Ctrl-C / stop the process.
Expected: `characters/mario/sprites/...` gains ≥2 real PNGs (>5KB), log shows `DONE` lines, no copyright refusal.

- [ ] **Step 5: Commit (only after live verification passes)**

```bash
git add mcp_chatgpt/sites.py tests/test_mcp_chatgpt_sites.py
git commit -m "feat(mcp-chatgpt): grok site config (live-verified selectors)"
```

---

### Task 9: Gemini site config + live verification

**Files:**
- Modify: `mcp_chatgpt/sites.py`
- Test: `tests/test_mcp_chatgpt_sites.py`

- [ ] **Step 1: Add a best-effort `SITES["gemini"]` + shape test**

Append to `tests/test_mcp_chatgpt_sites.py`:

```python
def test_gemini_site_present_and_complete():
    s = get_site("gemini")
    for f in ("url", "composer", "send_button", "assistant_turn",
              "generated_image_markers", "login_url_fragment", "usage_limit_markers"):
        assert getattr(s, f), f"gemini site missing {f}"
    assert "gemini.google.com" in s.url
```

Add to `SITES` in `sites.py`:

```python
    # SCAFFOLD — best-effort; verify live (Step 3).
    "gemini": Site(
        url="https://gemini.google.com/app",
        composer="div.ql-editor[contenteditable='true'], textarea",
        send_button="button[aria-label*='Send' i], button.send-button",
        stop_button="button[aria-label*='Stop' i]",
        assistant_turn="model-response, .model-response-text",
        generated_image_markers=("googleusercontent.com", "generativelanguage",
                                 "lh3.google"),
        login_url_fragment="accounts.google.com",
        challenge_text_markers=("Verify it's you", "unusual traffic"),
        usage_limit_markers=("you've reached your limit", "try again later",
                             "limit for", "upgrade"),
        refusal_markers=("i can't create", "i'm not able to generate",
                         "can't help with that"),
    ),
```

- [ ] **Step 2: Run the shape test**

Run: `venv/Scripts/python.exe -m pytest tests/test_mcp_chatgpt_sites.py -k gemini -v`
Expected: PASS (shape only)

- [ ] **Step 3: LIVE VERIFICATION (manual, requires the user logged into gemini.google.com)**

Same loop as Task 8 Step 3, against `gemini.google.com/app`:
1. User: `mcp_chatgpt/venv/Scripts/python.exe -m mcp_chatgpt._login_oneshot gemini` → log in (Google) → close window.
2. Probe + inspect: composer (Gemini uses a Quill `div.ql-editor`), send button, `model-response` turn, generated-image src host after "draw a red apple".
3. Fix `SITES["gemini"]` to the real DOM (composer, send, assistant turn, image host, the Google login-redirect fragment, cap/refusal wording).
4. Re-run until text + image both work and a PNG downloads.
5. Note: Gemini may need an extra wait for the image to render under the response; the stability loop's no-image grace already handles lag, but confirm `generated_image_markers` matches the rendered `<img>` (not a thumbnail/avatar).

- [ ] **Step 4: End-to-end smoke — 2 sprites via Gemini**

Run: `mcp_chatgpt/venv/Scripts/python.exe -u mcp_chatgpt/batch_sprites.py --provider gemini --character mario --start 3 --accounts default --delay 10`
Expected: ≥2 real PNGs added under `characters/mario/sprites/`, `DONE` lines.

- [ ] **Step 5: Commit**

```bash
git add mcp_chatgpt/sites.py tests/test_mcp_chatgpt_sites.py
git commit -m "feat(mcp-chatgpt): gemini site config (live-verified selectors)"
```

---

### Task 10: Docs + `.mcp.json` note

**Files:**
- Modify: `mcp_chatgpt/README.md`

- [ ] **Step 1: Document providers**

Add a "Providers" section to `mcp_chatgpt/README.md`: the `SITES` table, how to add a provider (one `Site` entry + live-verify), per-provider login (`_login_oneshot <provider> <account>`), and batch usage (`--provider grok`). Note that `.mcp.json` needs no change (the server still registers as `chatgpt`; the `provider` param selects the site).

- [ ] **Step 2: Commit**

```bash
git add mcp_chatgpt/README.md
git commit -m "docs(mcp-chatgpt): document multi-provider usage"
```

---

## Self-Review

**Spec coverage:**
- Architecture / provider layer → Tasks 1,2,5. ✓
- `sites.py` table → Task 1. ✓
- browser generalize → Tasks 4,5. ✓
- parsing generalize → Task 3. ✓
- stability/rotation unchanged → no task needed (verified green in Tasks 2,5). ✓
- batch `--provider` → Task 6. ✓
- server provider param → Task 7. ✓
- login one-shot provider → Task 7. ✓
- per-provider profiles + chatgpt alias → Task 4. ✓
- selector discovery loop → Tasks 8,9 Step 3. ✓
- build order Grok then Gemini → Tasks 8 then 9. ✓
- testing (unit pure + live manual) → each task. ✓
- docs → Task 10. ✓

**Placeholder scan:** Live-verification steps (8.3, 9.3) are intentionally interactive, not placeholders — they specify exact actions + success criteria. Selector values are marked SCAFFOLD with an explicit "verify live before trusting" instruction. No "TBD/handle errors/etc."

**Type consistency:** `Site` fields used identically across tasks (`site.url`, `site.composer`, `site.generated_image_markers`, ...). `get_site(provider)`, `profile_dir(provider, account)`, `get_session(provider)`, `run(..., provider)` signatures consistent across Tasks 1–9.
