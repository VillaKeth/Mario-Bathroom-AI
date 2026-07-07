"""ChatGPT browser session: persistent context, thread map, send/scrape, image download."""
import asyncio
import base64
import os

from playwright.async_api import async_playwright, Page

from mcp_chatgpt.sites import get_site
from mcp_chatgpt.parsing import parse_thread_id, classify_page_state
from mcp_chatgpt.stability import ProbeResult, WaitOutcome, wait_for_response
from mcp_chatgpt import interact

_DIR = os.path.dirname(os.path.abspath(__file__))
PROFILE_DIR = os.path.join(_DIR, "profile")   # base; the default account lives here
OUTPUT_DIR = os.path.join(_DIR, "output")

DEFAULT_ACCOUNT = "default"

# Image generation is slow; give the wait loop a generous poll budget.
IMAGE_MAX_POLLS = 600       # ~300s at 0.5s


def profile_dir(provider: str = "chatgpt", account: str = DEFAULT_ACCOUNT) -> str:
    """Browser-profile dir for a (provider, account).

    chatgpt keeps the LEGACY paths (profile/ and profile/_accounts/<name>) so
    existing logins survive the generalization. Other providers are namespaced
    under profile/<provider>/(_accounts/<name>).
    """
    if provider == "chatgpt":
        base = PROFILE_DIR
    else:
        base = os.path.join(PROFILE_DIR, provider)
    if account == DEFAULT_ACCOUNT:
        return base
    return os.path.join(base, "_accounts", account)


class NotLoggedIn(RuntimeError):
    pass


class Challenge(RuntimeError):
    pass


class ChatGPTSession:
    def __init__(self, provider: str = "chatgpt") -> None:
        self.provider = provider
        self.site = get_site(provider)
        self._pw = None
        self._contexts: dict = {}            # account -> BrowserContext
        self._threads: dict[str, Page] = {}  # thread_id -> Page (uuid is globally unique)
        self._lock = asyncio.Lock()
        # Every generated-image src ever downloaded. Folded into each baseline so
        # a previously-saved image can never be re-detected as "new" and saved
        # twice (guards against page/history races producing duplicate sprites).
        self._saved_srcs: set = set()

    async def _ctx_for(self, account: str):
        """Lazily launch (and cache) one persistent browser context per account."""
        ctx = self._contexts.get(account)
        if ctx is not None:
            return ctx
        os.makedirs(profile_dir(self.provider, account), exist_ok=True)
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        if self._pw is None:
            self._pw = await async_playwright().start()
        ctx = await self._pw.chromium.launch_persistent_context(
            profile_dir(self.provider, account),
            channel="chrome",
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )
        self._contexts[account] = ctx
        return ctx

    async def _check_state(self, page: Page, account: str) -> None:
        body = await page.inner_text("body")
        state = classify_page_state(page.url, body, self.site)
        if state == "login":
            raise NotLoggedIn(
                f"account '{account}' not logged in for provider '{self.provider}' — run: "
                f"python -m mcp_chatgpt._login_oneshot {self.provider} {account}"
            )
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
            if any(m in src for m in self.site.generated_image_markers):
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
        # Throttled benign-only overlay sweep (~every 6s at 0.5s polls) so a nag
        # that lands MID-render — idle prompt, rating ask, "still there?" — can't
        # freeze the wait loop. benign_only skips Escape/consent/backdrop so it
        # can never mis-click a generation control while an image is rendering.
        self._probe_ticks = getattr(self, "_probe_ticks", 0) + 1
        if self._probe_ticks % 12 == 0:
            try:
                await interact.sweep_light(page, self.site)
            except Exception:  # noqa: BLE001
                pass
        # Some providers (e.g. grok) have no Stop button — treat "no stop selector"
        # as not-generating and let the wait loop rely on text/image stability.
        generating = bool(self.site.stop_button) and \
            (await page.query_selector(self.site.stop_button)) is not None
        turns = await page.query_selector_all(self.site.assistant_turn)
        text = await turns[-1].inner_text() if turns else ""
        new_imgs = await self._new_generated_image_els(page, baseline)
        # "Creating your image..." placeholder text means it's STILL working even
        # with no Stop button — but ONLY while no image has appeared yet. Once the
        # image is present we let the normal ready-check finish the wait, so a
        # lingering placeholder doesn't loop us to the timeout.
        if not generating and not new_imgs and self.site.generating_text_markers:
            low = (text or "").lower()
            if any(m in low for m in self.site.generating_text_markers):
                generating = True
        ready = True
        for _src, img in new_imgs:
            ok = await page.evaluate("e => e.complete && e.naturalWidth > 0", img)
            ready = ready and bool(ok)
        return ProbeResult(generating, text, len(new_imgs), ready)

    async def _fetch_image_bytes(self, page: Page, src, img) -> bytes | None:
        """Get a generated image's bytes, robust across providers (≥1KB or None).

        Tiers: (1) the browser CONTEXT request — carries auth cookies and is NOT
        subject to page CORS, so it works for cross-origin CDNs like grok's
        assets.grok.com; (2) an in-page fetch — works when same-origin/CORS-open;
        (3) a screenshot of the <img> element — always works (captures the
        rendered pixels) when the bytes can't be fetched at all."""
        # (1) context request (cookies, no CORS)
        try:
            resp = await page.request.get(src)
            if resp.ok:
                data = await resp.body()
                if data and len(data) > 1000:
                    return data
        except Exception:  # noqa: BLE001
            pass
        # (2) in-page fetch → base64
        try:
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
            data = base64.b64decode(b64) if b64 else b""
            if data and len(data) > 1000:
                return data
        except Exception:  # noqa: BLE001
            pass
        # (3) element screenshot (rendered pixels)
        try:
            data = await img.screenshot()
            if data and len(data) > 1000:
                return data
        except Exception:  # noqa: BLE001
            pass
        return None

    async def _download_images(self, page: Page, thread_id: str, baseline: set) -> list[str]:
        new_imgs = await self._new_generated_image_els(page, baseline)
        paths: list[str] = []
        for i, (src, img) in enumerate(new_imgs):
            data = await self._fetch_image_bytes(page, src, img)
            if not data:
                continue   # couldn't get real bytes — skip (don't write an empty file)
            path = os.path.join(OUTPUT_DIR, f"{thread_id}_{i}.png")
            with open(path, "wb") as f:
                f.write(data)
            paths.append(path)
            self._saved_srcs.add(src)   # never download this exact image again
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
            # A generated image can lag a few seconds behind settled text — give a
            # longer no-image grace (~5s) so a real render isn't cut off as "none".
            no_image_stable_window=10,
        )

    async def _resolve_response_chooser(self, page: Page) -> bool:
        """Best-effort: ChatGPT occasionally shows an A/B 'which response do you
        prefer' chooser that blocks a continuing chat until one is picked. If the
        marker text is present, click the first candidate button so we can read a
        single settled response. Non-fatal no-op if nothing matches. NOTE: button
        selectors are unverified guesses — tighten once seen on a live A/B."""
        try:
            body = await page.inner_text("body")
        except Exception:  # noqa: BLE001
            return False
        if not any(m in body.lower() for m in self.site.response_picker_markers):
            return False
        for sel in self.site.response_picker_buttons:
            try:
                btn = await page.query_selector(sel)
                if btn:
                    await btn.click()
                    await page.wait_for_timeout(600)
                    print(f"[chooser] resolved A/B response picker via {sel}", flush=True)
                    return True
            except Exception:  # noqa: BLE001
                continue
        print("[chooser] A/B picker detected but no known button matched", flush=True)
        return False

    async def _send_wait_resolve(self, page: Page, baseline: set) -> WaitOutcome:
        """Wait for the reply; if an A/B chooser appears, resolve it and re-settle
        so we read the single chosen response (and its image)."""
        outcome = await self._send_and_wait(page, baseline)
        if await self._resolve_response_chooser(page):
            outcome = await self._send_wait_resolve(page, baseline)
        return outcome

    async def _dismiss_intro(self, page: Page) -> None:
        """Clear whatever stands between us and the composer — onboarding CTAs,
        consent/ToS dialogs, cookie walls, upsell nags. Generalized: the sweep in
        interact.dismiss_overlays handles this site's intro_buttons AND any modal
        that appears mid-session, then we wait for the composer to be reachable."""
        await interact.dismiss_overlays(page, self.site)
        try:
            await page.wait_for_selector(self.site.composer, timeout=10000)
        except Exception:  # noqa: BLE001
            # Composer still hidden — one more aggressive sweep before we give up.
            await interact.dismiss_overlays(page, self.site, max_rounds=8)

    async def _type_and_send(self, page: Page, prompt: str, image_path: str = "") -> None:
        await self._dismiss_intro(page)
        if image_path and self.site.file_input:
            # Image-to-image: attach a reference picture to the composer's hidden
            # file input, then wait for the upload to register before sending.
            try:
                await page.set_input_files(self.site.file_input, image_path)
                await page.wait_for_timeout(6000)
            except Exception as e:  # noqa: BLE001
                print(f"[ref] image upload failed ({image_path}): {e}", flush=True)
        # Self-healing fill + submit: both sweep overlays first and fall back
        # through several strategies, so a modal that lands between upload and
        # send can't wedge us on a locator timeout.
        if not await interact.safe_fill(page, self.site, prompt):
            print("[interact] safe_fill could not land the prompt after retries", flush=True)
        await interact.safe_send(page, self.site)
        # Wait for streaming to actually begin (Stop button appears) so the wait
        # loop doesn't sample the blank pre-generation turn. Sites without a Stop
        # button skip this — the wait loop handles them via text/image stability.
        if self.site.stop_button:
            try:
                await page.wait_for_selector(self.site.stop_button, timeout=15000)
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

    async def new_thread(self, prompt: str, account: str = DEFAULT_ACCOUNT, image_path: str = "") -> dict:
        async with self._lock:
            ctx = await self._ctx_for(account)
            page = await ctx.new_page()
            await page.goto(self.site.url, wait_until="domcontentloaded")
            await interact.dismiss_overlays(page, self.site)   # clear any landing modal
            await self._check_state(page, account)
            baseline = await self._generated_image_srcs(page) | self._saved_srcs
            await self._type_and_send(page, prompt, image_path)
            outcome = await self._send_wait_resolve(page, baseline)
            await page.wait_for_timeout(300)  # let URL settle to /c/<uuid>
            thread_id = parse_thread_id(page.url) or f"tab-{id(page)}"
            self._threads[thread_id] = page
            images = await self._download_images(page, thread_id, baseline) if outcome.had_image else []
            return {"thread_id": thread_id,
                    "response": await self._build_response(page, outcome, images)}

    async def send(self, thread_id: str, prompt: str, account: str = DEFAULT_ACCOUNT, image_path: str = "") -> dict:
        async with self._lock:
            page = self._threads.get(thread_id)
            if page is not None and page.is_closed():
                self._threads.pop(thread_id, None)   # stale tab — reopen below
                page = None
            if page is None:
                # Reopen the conversation by URL in the account's context.
                ctx = await self._ctx_for(account)
                page = await ctx.new_page()
                await page.goto(f"https://chatgpt.com/c/{thread_id}",
                                wait_until="domcontentloaded")
                await interact.dismiss_overlays(page, self.site)   # clear any landing modal
                await self._check_state(page, account)
                self._threads[thread_id] = page
            baseline = await self._generated_image_srcs(page) | self._saved_srcs
            await self._type_and_send(page, prompt, image_path)
            outcome = await self._send_wait_resolve(page, baseline)
            images = await self._download_images(page, thread_id, baseline) if outcome.had_image else []
            return {"response": await self._build_response(page, outcome, images)}

    async def close_thread(self, thread_id: str) -> dict:
        async with self._lock:
            page = self._threads.pop(thread_id, None)
            if page is not None:
                await page.close()
            return {"ok": page is not None}

    async def reset_account(self, account: str) -> None:
        """Drop an account's browser context (and its now-dead pages) so the next
        use relaunches it fresh — recovery from a wedged/dead context (e.g.
        'Target.createTarget: Failed', 'browser has been closed')."""
        ctx = self._contexts.pop(account, None)
        if ctx is not None:
            try:
                await ctx.close()
            except Exception:  # noqa: BLE001
                pass
        for tid in [t for t, pg in self._threads.items() if pg.is_closed()]:
            self._threads.pop(tid, None)

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


_sessions: dict = {}


def get_session(provider: str = "chatgpt") -> "ChatGPTSession":
    s = _sessions.get(provider)
    if s is None:
        s = _sessions[provider] = ChatGPTSession(provider)
    return s
