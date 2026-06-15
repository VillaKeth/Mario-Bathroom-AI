"""One-shot login capture: open Chrome on the persistent profile, wait until the
user closes the window, then exit (profile saved). No terminal interaction.

Run:  mcp_chatgpt/venv/Scripts/python.exe -m mcp_chatgpt._login_oneshot
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
    print("BROWSER_OPEN: log into ChatGPT in the window, then CLOSE the window.", flush=True)

    closed = asyncio.Event()
    ctx.on("close", lambda: closed.set())
    try:
        await asyncio.wait_for(closed.wait(), timeout=900)
        print("WINDOW_CLOSED: profile saved to", PROFILE_DIR, flush=True)
    except asyncio.TimeoutError:
        print("TIMEOUT: no window close after 15 min; closing anyway.", flush=True)
        await ctx.close()
    try:
        await pw.stop()
    except Exception:
        pass


if __name__ == "__main__":
    asyncio.run(main())
