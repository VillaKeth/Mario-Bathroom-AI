# mcp-chatgpt Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an MCP server that lets Claude Code talk to ChatGPT through a persistent, logged-in real-Chrome session (no API), with threaded conversations returning text and downloaded images.

**Architecture:** A long-running Python MCP server (FastMCP, stdio) holds one Playwright persistent browser context alive across tool calls. All DOM-reading logic is funneled through a single `probe()` function so the streaming/done-detection logic is pure and unit-testable. Pure helpers (URL parsing, page-state classification, stability tracking, wait loop) are tested with pytest; the thin browser-orchestration layer is verified with manual smoke tests against the live site.

**Tech Stack:** Python 3.11, `mcp` (FastMCP), `playwright` (async, `channel="chrome"`), pytest.

---

## File Structure

All new code under `mcp_chatgpt/`:

| File | Responsibility | Imports playwright? |
|------|----------------|---------------------|
| `mcp_chatgpt/__init__.py` | package marker | no |
| `mcp_chatgpt/selectors.py` | ALL CSS selectors, one place | no |
| `mcp_chatgpt/parsing.py` | `parse_thread_id`, `classify_page_state` (pure) | no |
| `mcp_chatgpt/stability.py` | `ProbeResult`, `wait_for_response` (pure loop over an injected probe) | no |
| `mcp_chatgpt/browser.py` | `ChatGPTSession`: persistent context, thread→page map, real `probe`, send/scrape, image download | yes |
| `mcp_chatgpt/server.py` | FastMCP tool defs → `ChatGPTSession` | yes |
| `mcp_chatgpt/setup_login.py` | one-time interactive login | yes |
| `mcp_chatgpt/requirements.txt` | `mcp`, `playwright` | — |
| `mcp_chatgpt/README.md` | setup + Claude Code registration | — |
| `mcp_chatgpt/profile/` | persistent browser profile (gitignored) | — |
| `mcp_chatgpt/output/` | downloaded images (gitignored) | — |

Unit tests under `tests/` (run with the **main** `venv` pytest — they import only the pure modules, never playwright):
- `tests/test_mcp_chatgpt_parsing.py`
- `tests/test_mcp_chatgpt_stability.py`

---

### Task 1: Scaffold — package, venv, deps, gitignore

**Files:**
- Create: `mcp_chatgpt/__init__.py`
- Create: `mcp_chatgpt/requirements.txt`
- Modify: `.gitignore` (append profile/output ignores)

- [ ] **Step 1: Create the package marker**

Create `mcp_chatgpt/__init__.py`:

```python
"""Browser-driven ChatGPT MCP server."""
```

- [ ] **Step 2: Create requirements.txt**

Create `mcp_chatgpt/requirements.txt`:

```
mcp>=1.2.0
playwright>=1.45.0
```

- [ ] **Step 3: Create dedicated venv and install deps**

Run:
```bash
venv/Scripts/python.exe -m venv mcp_chatgpt/venv
mcp_chatgpt/venv/Scripts/python.exe -m pip install -r mcp_chatgpt/requirements.txt
```
Expected: installs succeed. No `playwright install` needed — we use system Chrome via `channel="chrome"`.

- [ ] **Step 4: Verify Chrome channel is reachable**

Run:
```bash
mcp_chatgpt/venv/Scripts/python.exe -c "from playwright.sync_api import sync_playwright;\
p=sync_playwright().start();\
b=p.chromium.launch(channel='chrome', headless=True);\
print('chrome ok', b.version);\
b.close(); p.stop()"
```
Expected: prints `chrome ok <version>`. If it fails with "channel chrome not found", Chrome isn't installed where Playwright looks — stop and resolve before continuing.

- [ ] **Step 5: Add gitignore entries**

Append to `.gitignore`:

```
# mcp-chatgpt runtime (browser profile + downloaded images — never commit)
mcp_chatgpt/profile/
mcp_chatgpt/output/
```

(`mcp_chatgpt/venv/` is already covered by the existing `venv/` rule.)

- [ ] **Step 6: Commit**

```bash
git add mcp_chatgpt/__init__.py mcp_chatgpt/requirements.txt .gitignore
git commit -m "feat(mcp-chatgpt): scaffold package, deps, gitignore"
```

---

### Task 2: Selectors module

**Files:**
- Create: `mcp_chatgpt/selectors.py`

These are best-guess ChatGPT selectors and **will be verified/corrected against the live DOM in Task 8**. Keeping them in one file is the whole point — one repair site.

- [ ] **Step 1: Create selectors.py**

```python
"""All ChatGPT DOM selectors live here — single repair point when OpenAI reships UI.

Verified against live DOM on: <DATE — fill in during Task 8>
"""

URL = "https://chatgpt.com/"

# Composer + send/stop controls
COMPOSER = "#prompt-textarea"
SEND_BUTTON = "[data-testid='send-button']"
STOP_BUTTON = "[data-testid='stop-button']"

# Assistant output
ASSISTANT_TURN = "[data-message-author-role='assistant']"
ASSISTANT_IMAGE = "img"  # queried *within* the last assistant turn

# State detection
# Login: when logged out, ChatGPT redirects to a URL containing this path.
LOGIN_URL_FRAGMENT = "/auth/login"
# Cloudflare / challenge interstitials commonly show this in body text.
CHALLENGE_TEXT_MARKERS = ("Verify you are human", "Just a moment", "Checking your browser")
# Usage-limit banner text marker.
USAGE_LIMIT_MARKERS = ("You've reached", "usage limit", "limit reached")
```

- [ ] **Step 2: Commit**

```bash
git add mcp_chatgpt/selectors.py
git commit -m "feat(mcp-chatgpt): central selectors module"
```

---

### Task 3: URL parsing + page-state classification (pure, TDD)

**Files:**
- Create: `mcp_chatgpt/parsing.py`
- Test: `tests/test_mcp_chatgpt_parsing.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_mcp_chatgpt_parsing.py`:

```python
from mcp_chatgpt.parsing import parse_thread_id, classify_page_state


def test_parse_thread_id_basic():
    assert parse_thread_id("https://chatgpt.com/c/abc-123") == "abc-123"


def test_parse_thread_id_with_trailing_and_query():
    assert parse_thread_id("https://chatgpt.com/c/abc-123/?model=gpt-4") == "abc-123"


def test_parse_thread_id_none_when_no_conversation():
    assert parse_thread_id("https://chatgpt.com/") is None


def test_classify_ok():
    assert classify_page_state("https://chatgpt.com/c/x", "normal page body") == "ok"


def test_classify_login_by_url():
    assert classify_page_state("https://auth.openai.com/auth/login", "") == "login"


def test_classify_challenge_by_body():
    assert classify_page_state("https://chatgpt.com/", "Just a moment...") == "challenge"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `venv/Scripts/python.exe -m pytest tests/test_mcp_chatgpt_parsing.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'mcp_chatgpt.parsing'`.

- [ ] **Step 3: Write minimal implementation**

Create `mcp_chatgpt/parsing.py`:

```python
"""Pure helpers — no playwright import, fully unit-testable."""
import re

from mcp_chatgpt import selectors

_CONV_RE = re.compile(r"/c/([^/?#]+)")


def parse_thread_id(url: str) -> str | None:
    """Extract the ChatGPT conversation UUID from a /c/<uuid> URL, else None."""
    m = _CONV_RE.search(url or "")
    return m.group(1) if m else None


def classify_page_state(url: str, body_text: str) -> str:
    """Return one of: 'ok', 'login', 'challenge'."""
    url = url or ""
    body = body_text or ""
    if selectors.LOGIN_URL_FRAGMENT in url:
        return "login"
    if any(marker in body for marker in selectors.CHALLENGE_TEXT_MARKERS):
        return "challenge"
    return "ok"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `venv/Scripts/python.exe -m pytest tests/test_mcp_chatgpt_parsing.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add mcp_chatgpt/parsing.py tests/test_mcp_chatgpt_parsing.py
git commit -m "feat(mcp-chatgpt): thread-id parsing + page-state classification (tested)"
```

---

### Task 4: Stability/wait loop (pure, TDD)

The streaming/done-detection logic. It polls an injected `probe()` callable and a `sleep()` callable, so it is fully deterministic in tests — no browser, no real time.

**Files:**
- Create: `mcp_chatgpt/stability.py`
- Test: `tests/test_mcp_chatgpt_stability.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_mcp_chatgpt_stability.py`:

```python
import asyncio

from mcp_chatgpt.stability import ProbeResult, WaitOutcome, wait_for_response


def _run(coro):
    return asyncio.run(coro)


async def _noop_sleep(_seconds):
    return None


def _scripted_probe(results):
    """Return an async probe that yields each ProbeResult in turn, repeating the last."""
    seq = list(results)

    async def probe():
        return seq.pop(0) if len(seq) > 1 else seq[0]

    return probe


def test_text_completes_after_stable_window():
    # generating, growing text, then stops; text stable for the window -> done
    probe = _scripted_probe([
        ProbeResult(is_generating=True, text="Hel", image_count=0, images_ready=True),
        ProbeResult(is_generating=True, text="Hello", image_count=0, images_ready=True),
        ProbeResult(is_generating=False, text="Hello world", image_count=0, images_ready=True),
        ProbeResult(is_generating=False, text="Hello world", image_count=0, images_ready=True),
        ProbeResult(is_generating=False, text="Hello world", image_count=0, images_ready=True),
    ])
    out = _run(wait_for_response(probe, sleep=_noop_sleep,
                                 stable_window=2, max_polls=20, poll_interval=0.0))
    assert isinstance(out, WaitOutcome)
    assert out.text == "Hello world"
    assert out.timed_out is False
    assert out.had_image is False


def test_timeout_returns_partial():
    # never stops generating -> times out, returns last seen text
    probe = _scripted_probe([
        ProbeResult(is_generating=True, text="partial...", image_count=0, images_ready=True),
    ])
    out = _run(wait_for_response(probe, sleep=_noop_sleep,
                                 stable_window=2, max_polls=5, poll_interval=0.0))
    assert out.timed_out is True
    assert out.text == "partial..."


def test_waits_for_image_bytes_before_done():
    # generation stopped and an image element exists but bytes not ready yet,
    # then becomes ready -> done, had_image True
    probe = _scripted_probe([
        ProbeResult(is_generating=False, text="", image_count=1, images_ready=False),
        ProbeResult(is_generating=False, text="", image_count=1, images_ready=False),
        ProbeResult(is_generating=False, text="", image_count=1, images_ready=True),
        ProbeResult(is_generating=False, text="", image_count=1, images_ready=True),
        ProbeResult(is_generating=False, text="", image_count=1, images_ready=True),
    ])
    out = _run(wait_for_response(probe, sleep=_noop_sleep,
                                 stable_window=2, max_polls=20, poll_interval=0.0))
    assert out.had_image is True
    assert out.timed_out is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `venv/Scripts/python.exe -m pytest tests/test_mcp_chatgpt_stability.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'mcp_chatgpt.stability'`.

- [ ] **Step 3: Write minimal implementation**

Create `mcp_chatgpt/stability.py`:

```python
"""Pure done-detection loop. No playwright, no wall-clock — both injected."""
from dataclasses import dataclass
from typing import Awaitable, Callable


@dataclass
class ProbeResult:
    is_generating: bool   # True while the Stop button is present (model streaming)
    text: str             # current text of the last assistant turn
    image_count: int      # number of <img> in the last assistant turn
    images_ready: bool    # True when all those <img> have loaded bytes


@dataclass
class WaitOutcome:
    text: str
    timed_out: bool
    had_image: bool


async def wait_for_response(
    probe: Callable[[], Awaitable[ProbeResult]],
    *,
    sleep: Callable[[float], Awaitable[None]],
    stable_window: int = 4,
    max_polls: int = 240,
    poll_interval: float = 0.5,
) -> WaitOutcome:
    """Poll `probe` until the assistant reply is complete or `max_polls` is hit.

    Done = not generating AND (no pending image bytes) AND text unchanged for
    `stable_window` consecutive polls. Returns partial text with timed_out=True
    on exhaustion. Never raises for slowness.
    """
    stable = 0
    last_text: str | None = None
    saw_image = False

    for _ in range(max_polls):
        r = await probe()
        if r.image_count > 0:
            saw_image = True

        if r.is_generating or (saw_image and not r.images_ready):
            stable = 0
            last_text = r.text
            await sleep(poll_interval)
            continue

        if r.text == last_text:
            stable += 1
        else:
            stable = 0
            last_text = r.text

        if stable >= stable_window:
            return WaitOutcome(text=r.text, timed_out=False, had_image=saw_image)

        await sleep(poll_interval)

    return WaitOutcome(text=last_text or "", timed_out=True, had_image=saw_image)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `venv/Scripts/python.exe -m pytest tests/test_mcp_chatgpt_stability.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add mcp_chatgpt/stability.py tests/test_mcp_chatgpt_stability.py
git commit -m "feat(mcp-chatgpt): pure streaming/done-detection wait loop (tested)"
```

---

### Task 5: Browser session manager

Thin orchestration over Playwright. Not unit-tested (browser integration) — verified by smoke tests in Task 9. Keep logic minimal; all DOM reads go through `_probe`.

**Files:**
- Create: `mcp_chatgpt/browser.py`

- [ ] **Step 1: Write browser.py**

```python
"""ChatGPT browser session: persistent context, thread map, send/scrape, image download."""
import asyncio
import base64
import os

from playwright.async_api import async_playwright, Page

from mcp_chatgpt import selectors
from mcp_chatgpt.parsing import parse_thread_id, classify_page_state
from mcp_chatgpt.stability import ProbeResult, WaitOutcome, wait_for_response

_DIR = os.path.dirname(os.path.abspath(__file__))
PROFILE_DIR = os.path.join(_DIR, "profile")
OUTPUT_DIR = os.path.join(_DIR, "output")

# Image generation is slow; give it far more polls than plain text.
TEXT_MAX_POLLS = 240        # ~120s at 0.5s
IMAGE_MAX_POLLS = 600       # ~300s at 0.5s


class NotLoggedIn(RuntimeError):
    pass


class Challenge(RuntimeError):
    pass


class ChatGPTSession:
    def __init__(self) -> None:
        self._pw = None
        self._ctx = None
        self._threads: dict[str, Page] = {}
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        if self._ctx is not None:
            return
        os.makedirs(PROFILE_DIR, exist_ok=True)
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        self._pw = await async_playwright().start()
        self._ctx = await self._pw.chromium.launch_persistent_context(
            PROFILE_DIR,
            channel="chrome",
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )

    async def _ensure(self) -> None:
        if self._ctx is None:
            await self.start()

    async def _check_state(self, page: Page) -> None:
        body = await page.inner_text("body")
        state = classify_page_state(page.url, body)
        if state == "login":
            raise NotLoggedIn("run setup_login.py first")
        if state == "challenge":
            raise Challenge("solve challenge in the window, then retry")

    async def _probe(self, page: Page) -> ProbeResult:
        generating = (await page.query_selector(selectors.STOP_BUTTON)) is not None
        turns = await page.query_selector_all(selectors.ASSISTANT_TURN)
        if not turns:
            return ProbeResult(generating, "", 0, True)
        last = turns[-1]
        text = await last.inner_text()
        imgs = await last.query_selector_all(selectors.ASSISTANT_IMAGE)
        ready = True
        for img in imgs:
            ok = await page.evaluate("e => e.complete && e.naturalWidth > 0", img)
            ready = ready and bool(ok)
        return ProbeResult(generating, text, len(imgs), ready)

    async def _download_images(self, page: Page, thread_id: str) -> list[str]:
        turns = await page.query_selector_all(selectors.ASSISTANT_TURN)
        if not turns:
            return []
        imgs = await turns[-1].query_selector_all(selectors.ASSISTANT_IMAGE)
        paths: list[str] = []
        for i, img in enumerate(imgs):
            src = await img.get_attribute("src")
            if not src:
                continue
            # Fetch bytes through the page (carries auth cookies), return base64.
            b64 = await page.evaluate(
                """async (url) => {
                    const r = await fetch(url);
                    const buf = await r.arrayBuffer();
                    let s = ''; const bytes = new Uint8Array(buf);
                    for (let j = 0; j < bytes.length; j++) s += String.fromCharCode(bytes[j]);
                    return btoa(s);
                }""",
                src,
            )
            path = os.path.join(OUTPUT_DIR, f"{thread_id}_{i}.png")
            with open(path, "wb") as f:
                f.write(base64.b64decode(b64))
            paths.append(path)
        return paths

    async def _send_and_wait(self, page: Page) -> WaitOutcome:
        # Decide poll budget by whether an image is being produced — start with text
        # budget; the wait loop itself extends for image bytes, so use the image
        # budget whenever any <img> appears. Simpler: always use IMAGE_MAX_POLLS
        # (slow path is rare and timing out early on images is worse than waiting).
        return await wait_for_response(
            lambda: self._probe(page),
            sleep=asyncio.sleep,
            stable_window=4,
            max_polls=IMAGE_MAX_POLLS,
            poll_interval=0.5,
        )

    async def _type_and_send(self, page: Page, prompt: str) -> None:
        await page.fill(selectors.COMPOSER, prompt)
        await page.click(selectors.SEND_BUTTON)

    async def new_thread(self, prompt: str) -> dict:
        async with self._lock:
            await self._ensure()
            page = await self._ctx.new_page()
            await page.goto(selectors.URL, wait_until="domcontentloaded")
            await self._check_state(page)
            await self._type_and_send(page, prompt)
            outcome = await self._send_and_wait(page)
            await page.wait_for_timeout(300)  # let URL settle to /c/<uuid>
            thread_id = parse_thread_id(page.url) or f"tab-{id(page)}"
            self._threads[thread_id] = page
            images = await self._download_images(page, thread_id) if outcome.had_image else []
            return {"thread_id": thread_id,
                    "response": {"text": outcome.text, "images": images,
                                 "timed_out": outcome.timed_out}}

    async def send(self, thread_id: str, prompt: str) -> dict:
        async with self._lock:
            await self._ensure()
            page = self._threads.get(thread_id)
            if page is None:
                # Reopen the conversation by URL.
                page = await self._ctx.new_page()
                await page.goto(f"https://chatgpt.com/c/{thread_id}",
                                wait_until="domcontentloaded")
                await self._check_state(page)
                self._threads[thread_id] = page
            await self._type_and_send(page, prompt)
            outcome = await self._send_and_wait(page)
            images = await self._download_images(page, thread_id) if outcome.had_image else []
            return {"response": {"text": outcome.text, "images": images,
                                 "timed_out": outcome.timed_out}}

    async def close_thread(self, thread_id: str) -> dict:
        async with self._lock:
            page = self._threads.pop(thread_id, None)
            if page is not None:
                await page.close()
            return {"ok": page is not None}


_session: ChatGPTSession | None = None


def get_session() -> ChatGPTSession:
    global _session
    if _session is None:
        _session = ChatGPTSession()
    return _session
```

- [ ] **Step 2: Verify it imports**

Run:
```bash
mcp_chatgpt/venv/Scripts/python.exe -c "import mcp_chatgpt.browser; print('import ok')"
```
Expected: `import ok`.

- [ ] **Step 3: Commit**

```bash
git add mcp_chatgpt/browser.py
git commit -m "feat(mcp-chatgpt): browser session manager (threads, probe, image download)"
```

---

### Task 6: One-time login helper

**Files:**
- Create: `mcp_chatgpt/setup_login.py`

- [ ] **Step 1: Write setup_login.py**

```python
"""Run once: opens real Chrome with the persistent profile so you can log into ChatGPT.

    mcp_chatgpt/venv/Scripts/python.exe -m mcp_chatgpt.setup_login

Log in, confirm you can see the chat composer, then press Enter in this terminal.
The session is saved to mcp_chatgpt/profile/ and reused by the MCP server.
"""
import asyncio
import os

from playwright.async_api import async_playwright

from mcp_chatgpt import selectors
from mcp_chatgpt.browser import PROFILE_DIR


async def main() -> None:
    os.makedirs(PROFILE_DIR, exist_ok=True)
    pw = await async_playwright().start()
    ctx = await pw.chromium.launch_persistent_context(
        PROFILE_DIR, channel="chrome", headless=False,
        args=["--disable-blink-features=AutomationControlled"],
    )
    page = ctx.pages[0] if ctx.pages else await ctx.new_page()
    await page.goto(selectors.URL, wait_until="domcontentloaded")
    print("Log into ChatGPT in the opened window.")
    print("When you can see the chat box, come back here and press Enter.")
    await asyncio.get_event_loop().run_in_executor(None, input)
    await ctx.close()
    await pw.stop()
    print("Saved session to:", PROFILE_DIR)


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Verify it imports (do not run interactively yet)**

Run:
```bash
mcp_chatgpt/venv/Scripts/python.exe -c "import mcp_chatgpt.setup_login; print('import ok')"
```
Expected: `import ok`.

- [ ] **Step 3: Commit**

```bash
git add mcp_chatgpt/setup_login.py
git commit -m "feat(mcp-chatgpt): one-time interactive login helper"
```

---

### Task 7: MCP server (FastMCP tools)

**Files:**
- Create: `mcp_chatgpt/server.py`

- [ ] **Step 1: Write server.py**

```python
"""FastMCP server exposing ChatGPT-via-browser as tools."""
from mcp.server.fastmcp import FastMCP

from mcp_chatgpt.browser import get_session, NotLoggedIn, Challenge

mcp = FastMCP("chatgpt")


def _err(msg: str) -> dict:
    return {"error": msg, "response": {"text": "", "images": [], "timed_out": False}}


@mcp.tool()
async def chatgpt_new_thread(prompt: str) -> dict:
    """Start a new ChatGPT conversation. Returns {thread_id, response:{text,images,timed_out}}."""
    try:
        return await get_session().new_thread(prompt)
    except NotLoggedIn as e:
        return _err(str(e))
    except Challenge as e:
        return _err(str(e))


@mcp.tool()
async def chatgpt_send(thread_id: str, prompt: str) -> dict:
    """Send a follow-up in an existing thread. Returns {response:{text,images,timed_out}}."""
    try:
        return await get_session().send(thread_id, prompt)
    except NotLoggedIn as e:
        return _err(str(e))
    except Challenge as e:
        return _err(str(e))


@mcp.tool()
async def chatgpt_close_thread(thread_id: str) -> dict:
    """Close a thread's tab. Returns {ok: bool}."""
    return await get_session().close_thread(thread_id)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify the server constructs and lists tools**

Run:
```bash
mcp_chatgpt/venv/Scripts/python.exe -c "import asyncio; from mcp_chatgpt.server import mcp;\
print(sorted(t.name for t in asyncio.run(mcp.list_tools())))"
```
Expected: `['chatgpt_close_thread', 'chatgpt_new_thread', 'chatgpt_send']`.

- [ ] **Step 3: Commit**

```bash
git add mcp_chatgpt/server.py
git commit -m "feat(mcp-chatgpt): FastMCP server wiring new_thread/send/close_thread"
```

---

### Task 8: Verify selectors against the live DOM

The selectors in Task 2 are best-guesses. Before any smoke test can pass, confirm them against the real site. Use the **Playwright MCP already available in this session** (or chrome-devtools MCP) to open chatgpt.com and inspect.

**Files:**
- Modify: `mcp_chatgpt/selectors.py` (correct any wrong selectors; update the "Verified on" date)

- [ ] **Step 1: Open the live site and snapshot the DOM**

Using the Playwright MCP: `browser_navigate` to `https://chatgpt.com/`, then `browser_snapshot`. Identify the real attributes/selectors for: composer textarea, send button, stop button (send a test prompt to make it appear), assistant message container, and a generated image element (prompt "generate an image of a red cube").

- [ ] **Step 2: Correct selectors.py**

Edit `mcp_chatgpt/selectors.py` so each constant matches the live DOM. Update the `Verified against live DOM on:` line to today's date.

- [ ] **Step 3: Commit**

```bash
git add mcp_chatgpt/selectors.py
git commit -m "fix(mcp-chatgpt): correct selectors against live chatgpt.com DOM"
```

---

### Task 9: Login + smoke tests (live, manual)

Per `.claude/rules/testing.md`, a feature isn't done until verified live. These steps require a human-logged-in session and a visible browser.

**Files:** none (verification only)

- [ ] **Step 1: Log in once**

Run:
```bash
mcp_chatgpt/venv/Scripts/python.exe -m mcp_chatgpt.setup_login
```
Log into ChatGPT in the window, press Enter. Expected: `Saved session to: .../mcp_chatgpt/profile`.

- [ ] **Step 2: Smoke — new thread returns text**

Run:
```bash
mcp_chatgpt/venv/Scripts/python.exe -c "import asyncio, json;\
from mcp_chatgpt.browser import get_session;\
print(json.dumps(asyncio.run(get_session().new_thread('Reply with exactly: pong')), indent=2))"
```
Expected: JSON with a non-empty `response.text` containing `pong`, a real `thread_id`, `timed_out: false`.

- [ ] **Step 3: Smoke — thread keeps context**

Using the `thread_id` printed above:
```bash
mcp_chatgpt/venv/Scripts/python.exe -c "import asyncio, json, sys;\
from mcp_chatgpt.browser import get_session;\
s=get_session();\
asyncio.run(s.new_thread('Remember the number 42.'));\
tid=list(s._threads)[0];\
print(json.dumps(asyncio.run(s.send(tid, 'What number did I tell you?')), indent=2))"
```
Expected: `response.text` mentions `42` — confirms thread context held.

- [ ] **Step 4: Smoke — image generation downloads a file**

```bash
mcp_chatgpt/venv/Scripts/python.exe -c "import asyncio, json;\
from mcp_chatgpt.browser import get_session;\
r=asyncio.run(get_session().new_thread('Generate an image of a single red cube on white'));\
print(json.dumps(r, indent=2))"
```
Expected: `response.images` has at least one path under `mcp_chatgpt/output/`. Open it — must be a valid PNG of a red cube. If `timed_out: true` with no image, raise `IMAGE_MAX_POLLS` or re-check image selectors.

- [ ] **Step 5: Record results**

Note pass/fail of each smoke step in the PR / task notes. Do NOT proceed to registration until Steps 2–4 pass.

---

### Task 10: README + Claude Code registration

**Files:**
- Create: `mcp_chatgpt/README.md`
- Create OR Modify: `.mcp.json` (project root)

- [ ] **Step 1: Write README.md**

Create `mcp_chatgpt/README.md`:

````markdown
# mcp-chatgpt

Talk to ChatGPT from Claude Code through a persistent, logged-in real-Chrome
session — no OpenAI API.

## Setup

```bash
# 1. Create venv + install
venv/Scripts/python.exe -m venv mcp_chatgpt/venv
mcp_chatgpt/venv/Scripts/python.exe -m pip install -r mcp_chatgpt/requirements.txt

# 2. Log into ChatGPT once (opens a real Chrome window)
mcp_chatgpt/venv/Scripts/python.exe -m mcp_chatgpt.setup_login
```

## Register with Claude Code

Add to `.mcp.json` at the project root (see below), then restart Claude Code.

## Tools

- `chatgpt_new_thread(prompt)` → `{thread_id, response:{text, images[], timed_out}}`
- `chatgpt_send(thread_id, prompt)` → `{response:{...}}`
- `chatgpt_close_thread(thread_id)` → `{ok}`

Generated images are saved under `mcp_chatgpt/output/` and their paths returned.

## When it breaks

OpenAI reships the UI → fix selectors in `mcp_chatgpt/selectors.py` (the only
place selectors live). Re-run the smoke tests in the implementation plan.

A visible Chrome window stays open while the server runs — that's required
(headless trips bot-detection and can't log in).
````

- [ ] **Step 2: Add the MCP server to .mcp.json**

If `.mcp.json` exists, add the `chatgpt` entry under `mcpServers`; otherwise create the file:

```json
{
  "mcpServers": {
    "chatgpt": {
      "command": "mcp_chatgpt/venv/Scripts/python.exe",
      "args": ["-m", "mcp_chatgpt.server"]
    }
  }
}
```

- [ ] **Step 3: Verify the server starts under stdio**

Run (it should start and wait for stdio input — Ctrl+C to exit):
```bash
mcp_chatgpt/venv/Scripts/python.exe -m mcp_chatgpt.server
```
Expected: no crash, no traceback; it blocks waiting for an MCP client. Ctrl+C to stop.

- [ ] **Step 4: Commit**

```bash
git add mcp_chatgpt/README.md .mcp.json
git commit -m "docs(mcp-chatgpt): README + Claude Code registration"
```

- [ ] **Step 5: Restart Claude Code and confirm tools appear**

After restart, confirm `chatgpt_new_thread`, `chatgpt_send`, `chatgpt_close_thread` are listed as available tools. Run one live `chatgpt_new_thread("say hi")` call through Claude to confirm end-to-end.

---

## Self-Review

**Spec coverage:**
- Persistent login (B) → Task 1 (profile dir), Task 6 (setup_login), Task 5 (`launch_persistent_context`). ✓
- Real-Chrome / detection → `channel="chrome"` + `--disable-blink-features` in Task 5/6. ✓
- Threaded conversations → Task 5 `new_thread`/`send`, thread→page map, reopen-by-URL. ✓
- Tools `new_thread`/`send`/`close_thread` → Task 7. ✓
- `{text, images[], timed_out}` response shape → Task 4 (WaitOutcome) + Task 5 (assembly) + Task 7. ✓
- Image download through page context → Task 5 `_download_images`. ✓
- Streaming/done detection (text + image timeouts) → Task 4 wait loop, Task 5 budgets. ✓
- Error handling (login/challenge/timeout) → Task 3 classifier, Task 5 exceptions, Task 7 `_err`. ✓
- selectors isolated → Task 2, repaired in Task 8. ✓
- setup_login, smoke tests → Task 6, Task 9. ✓
- README + registration → Task 10. ✓

**Placeholder scan:** selectors.py intentionally carries a "fill in during Task 8" date marker and best-guess values — these are corrected in Task 8 against the live DOM, not left as placeholders. No other TODO/TBD.

**Type consistency:** `ProbeResult(is_generating, text, image_count, images_ready)` and `WaitOutcome(text, timed_out, had_image)` used identically in stability.py, its tests, and browser.py. `get_session()`, `new_thread`, `send`, `close_thread` signatures match between browser.py and server.py. Response dict shape identical across new_thread/send.

**Known limitation (carried from spec):** the browser layer (Task 5) is not unit-tested; it is covered by live smoke tests (Task 9), consistent with the project's mandatory live-audio/live-verification testing rule.
