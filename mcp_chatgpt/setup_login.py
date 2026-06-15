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
