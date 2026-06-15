"""ChatGPT browser session: persistent context, thread map, send/scrape, image download."""
import asyncio
import base64
import os

from playwright.async_api import async_playwright, Page

from mcp_chatgpt import selectors
from mcp_chatgpt.parsing import parse_thread_id, classify_page_state
from mcp_chatgpt.stability import ProbeResult, WaitOutcome, wait_for_response

_DIR = os.path.dirname(os.path.abspath(__file__))
PROFILE_DIR = os.path.join(_DIR, "profile")   # base; the default account lives here
OUTPUT_DIR = os.path.join(_DIR, "output")

DEFAULT_ACCOUNT = "default"

# Image generation is slow; give the wait loop a generous poll budget.
IMAGE_MAX_POLLS = 600       # ~300s at 0.5s


def profile_dir(account: str = DEFAULT_ACCOUNT) -> str:
    """Browser-profile directory for an account.

    The default account reuses the base `profile/` dir so the original
    single-account login keeps working; named accounts get an isolated subdir
    under `profile/_accounts/<name>`.
    """
    if account == DEFAULT_ACCOUNT:
        return PROFILE_DIR
    return os.path.join(PROFILE_DIR, "_accounts", account)


class NotLoggedIn(RuntimeError):
    pass


class Challenge(RuntimeError):
    pass


class ChatGPTSession:
    def __init__(self) -> None:
        self._pw = None
        self._contexts: dict = {}            # account -> BrowserContext
        self._threads: dict[str, Page] = {}  # thread_id -> Page (uuid is globally unique)
        self._lock = asyncio.Lock()

    async def _ctx_for(self, account: str):
        """Lazily launch (and cache) one persistent browser context per account."""
        ctx = self._contexts.get(account)
        if ctx is not None:
            return ctx
        os.makedirs(profile_dir(account), exist_ok=True)
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        if self._pw is None:
            self._pw = await async_playwright().start()
        ctx = await self._pw.chromium.launch_persistent_context(
            profile_dir(account),
            channel="chrome",
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )
        self._contexts[account] = ctx
        return ctx

    async def _check_state(self, page: Page, account: str) -> None:
        body = await page.inner_text("body")
        state = classify_page_state(page.url, body)
        if state == "login":
            raise NotLoggedIn(f"account '{account}' not logged in — run: "
                              f"python -m mcp_chatgpt._login_oneshot {account}")
        if state == "challenge":
            raise Challenge("solve challenge in the window, then retry")

    async def _generated_image_els(self, page: Page):
        """(src, element) for every generated image on the page (by src marker).

        Generated images render OUTSIDE the assistant-turn element, so they are
        located page-level. Avatars (gravatar.com) never match the markers.
        """
        out = []
        for img in await page.query_selector_all("img"):
            src = await img.get_attribute("src") or ""
            if any(m in src for m in selectors.GENERATED_IMAGE_MARKERS):
                out.append((src, img))
        return out

    async def _generated_image_srcs(self, page: Page) -> set:
        """Snapshot of generated-image srcs present right now (the baseline)."""
        return {src for src, _img in await self._generated_image_els(page)}

    async def _new_generated_image_els(self, page: Page, baseline: set):
        """Generated images present now but absent from `baseline`, deduped by src."""
        seen: set = set()
        out = []
        for src, img in await self._generated_image_els(page):
            if src in baseline or src in seen:
                continue
            seen.add(src)
            out.append((src, img))
        return out

    async def _probe(self, page: Page, baseline: set) -> ProbeResult:
        generating = (await page.query_selector(selectors.STOP_BUTTON)) is not None
        turns = await page.query_selector_all(selectors.ASSISTANT_TURN)
        text = await turns[-1].inner_text() if turns else ""
        new_imgs = await self._new_generated_image_els(page, baseline)
        ready = True
        for _src, img in new_imgs:
            ok = await page.evaluate("e => e.complete && e.naturalWidth > 0", img)
            ready = ready and bool(ok)
        return ProbeResult(generating, text, len(new_imgs), ready)

    async def _download_images(self, page: Page, thread_id: str, baseline: set) -> list[str]:
        new_imgs = await self._new_generated_image_els(page, baseline)
        paths: list[str] = []
        for i, (src, _img) in enumerate(new_imgs):
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

    async def _send_and_wait(self, page: Page, baseline: set) -> WaitOutcome:
        # Always use the image poll budget — image generation is the slow path and
        # timing out early on it is worse than waiting on a fast text reply.
        # `baseline` lets the probe count only NEWLY generated images.
        return await wait_for_response(
            lambda: self._probe(page, baseline),
            sleep=asyncio.sleep,
            stable_window=4,
            max_polls=IMAGE_MAX_POLLS,
            poll_interval=0.5,
        )

    async def _type_and_send(self, page: Page, prompt: str) -> None:
        await page.fill(selectors.COMPOSER, prompt)
        await page.click(selectors.SEND_BUTTON)
        # Wait for streaming to actually begin (Stop button appears) so the wait
        # loop doesn't sample the blank pre-generation turn. Instant replies may
        # finish before this fires — that's fine, the wait loop handles it.
        try:
            await page.wait_for_selector(selectors.STOP_BUTTON, timeout=15000)
        except Exception:
            pass

    async def _notice(self, page: Page) -> str:
        """Visible page text, captured only on a failed/empty generation so callers
        can detect cap/limit banners or toasts that aren't in the assistant turn."""
        try:
            return (await page.inner_text("body"))[:1200]
        except Exception:
            return ""

    async def _build_response(self, page: Page, outcome: WaitOutcome, images: list) -> dict:
        resp = {"text": outcome.text, "images": images, "timed_out": outcome.timed_out}
        # Only scrape the page notice when the reply is TRULY empty (no text and no
        # image) — that's the cap/toast case. A real text answer must not be
        # polluted with a dump of page chrome.
        if not images and not (outcome.text or "").strip():
            resp["notice"] = await self._notice(page)
        return resp

    async def new_thread(self, prompt: str, account: str = DEFAULT_ACCOUNT) -> dict:
        async with self._lock:
            ctx = await self._ctx_for(account)
            page = await ctx.new_page()
            await page.goto(selectors.URL, wait_until="domcontentloaded")
            await self._check_state(page, account)
            baseline = await self._generated_image_srcs(page)
            await self._type_and_send(page, prompt)
            outcome = await self._send_and_wait(page, baseline)
            await page.wait_for_timeout(300)  # let URL settle to /c/<uuid>
            thread_id = parse_thread_id(page.url) or f"tab-{id(page)}"
            self._threads[thread_id] = page
            images = await self._download_images(page, thread_id, baseline) if outcome.had_image else []
            return {"thread_id": thread_id,
                    "response": await self._build_response(page, outcome, images)}

    async def send(self, thread_id: str, prompt: str, account: str = DEFAULT_ACCOUNT) -> dict:
        async with self._lock:
            page = self._threads.get(thread_id)
            if page is None:
                # Reopen the conversation by URL in the account's context.
                ctx = await self._ctx_for(account)
                page = await ctx.new_page()
                await page.goto(f"https://chatgpt.com/c/{thread_id}",
                                wait_until="domcontentloaded")
                await self._check_state(page, account)
                self._threads[thread_id] = page
            baseline = await self._generated_image_srcs(page)
            await self._type_and_send(page, prompt)
            outcome = await self._send_and_wait(page, baseline)
            images = await self._download_images(page, thread_id, baseline) if outcome.had_image else []
            return {"response": await self._build_response(page, outcome, images)}

    async def close_thread(self, thread_id: str) -> dict:
        async with self._lock:
            page = self._threads.pop(thread_id, None)
            if page is not None:
                await page.close()
            return {"ok": page is not None}

    async def close(self) -> None:
        """Close every browser context + Playwright. For one-shot scripts; the
        long-running MCP server leaves the session open for its lifetime."""
        for ctx in self._contexts.values():
            try:
                await ctx.close()
            except Exception:
                pass
        self._contexts.clear()
        self._threads.clear()
        if self._pw is not None:
            try:
                await self._pw.stop()
            except Exception:
                pass
            self._pw = None


_session: ChatGPTSession | None = None


def get_session() -> ChatGPTSession:
    global _session
    if _session is None:
        _session = ChatGPTSession()
    return _session
