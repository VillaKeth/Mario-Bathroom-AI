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
