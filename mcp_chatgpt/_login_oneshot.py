"""One-shot login capture: open Chrome on an account's persistent profile, wait
until the user closes the window, then exit (profile saved). No terminal input.

Run:  mcp_chatgpt/venv/Scripts/python.exe -m mcp_chatgpt._login_oneshot [provider] [account]
      (provider defaults to "chatgpt"; account defaults to "default"; use e.g. "work" for a second account)
"""
import asyncio
import os
import sys

from playwright.async_api import async_playwright

from mcp_chatgpt.browser import DEFAULT_ACCOUNT, profile_dir
from mcp_chatgpt.sites import get_site


async def main(provider: str, account: str) -> None:
    pdir = profile_dir(provider, account)
    os.makedirs(pdir, exist_ok=True)
    pw = await async_playwright().start()
    ctx = await pw.chromium.launch_persistent_context(
        pdir, channel="chrome", headless=False,
        args=["--disable-blink-features=AutomationControlled"],
    )
    page = ctx.pages[0] if ctx.pages else await ctx.new_page()
    await page.goto(get_site(provider).url, wait_until="domcontentloaded")
    print(f"BROWSER_OPEN [{provider}/{account}]: log in, then CLOSE the window.", flush=True)

    closed = asyncio.Event()
    ctx.on("close", lambda: closed.set())
    try:
        await asyncio.wait_for(closed.wait(), timeout=900)
        print("WINDOW_CLOSED: profile saved to", pdir, flush=True)
    except asyncio.TimeoutError:
        print("TIMEOUT: no window close after 15 min; closing anyway.", flush=True)
        await ctx.close()
    try:
        await pw.stop()
    except Exception:
        pass


if __name__ == "__main__":
    provider = sys.argv[1] if len(sys.argv) > 1 else "chatgpt"
    account = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_ACCOUNT
    asyncio.run(main(provider, account))
