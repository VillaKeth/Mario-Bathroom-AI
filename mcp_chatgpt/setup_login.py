"""Run once: opens real Chrome with an account's persistent profile to log in.

    mcp_chatgpt/venv/Scripts/python.exe -m mcp_chatgpt.setup_login [account]

Log in, confirm you can see the chat composer, then press Enter in this terminal.
The session is saved per account and reused by the MCP server. `account` defaults
to "default"; pass e.g. "work" for a second account.
"""
import asyncio
import os
import sys

from playwright.async_api import async_playwright

from mcp_chatgpt import selectors
from mcp_chatgpt.browser import DEFAULT_ACCOUNT, profile_dir


async def main(account: str) -> None:
    pdir = profile_dir(account)
    os.makedirs(pdir, exist_ok=True)
    pw = await async_playwright().start()
    ctx = await pw.chromium.launch_persistent_context(
        pdir, channel="chrome", headless=False,
        args=["--disable-blink-features=AutomationControlled"],
    )
    page = ctx.pages[0] if ctx.pages else await ctx.new_page()
    await page.goto(selectors.URL, wait_until="domcontentloaded")
    print(f"Log into ChatGPT [{account}] in the opened window.")
    print("When you can see the chat box, come back here and press Enter.")
    await asyncio.get_event_loop().run_in_executor(None, input)
    await ctx.close()
    await pw.stop()
    print("Saved session to:", pdir)


if __name__ == "__main__":
    account = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_ACCOUNT
    asyncio.run(main(account))
