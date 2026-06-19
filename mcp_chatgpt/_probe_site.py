"""Live DOM probe to verify/fix a provider's selectors in sites.py.

Opens the provider's SAVED profile (so it's logged in), navigates to the site,
reports composer/send/assistant-turn candidates, then (with --gen) sends a test
image prompt and dumps the new <img> srcs + assistant-turn HTML so we can pin the
real selectors + generated-image host.

Run:
  mcp_chatgpt/venv/Scripts/python.exe -m mcp_chatgpt._probe_site grok
  mcp_chatgpt/venv/Scripts/python.exe -m mcp_chatgpt._probe_site grok --gen
"""
import asyncio
import sys

from playwright.async_api import async_playwright

from mcp_chatgpt.sites import get_site
from mcp_chatgpt.browser import profile_dir


async def main(provider: str, do_gen: bool) -> None:
    site = get_site(provider)
    pw = await async_playwright().start()
    ctx = await pw.chromium.launch_persistent_context(
        profile_dir(provider, "default"), channel="chrome", headless=False,
        args=["--disable-blink-features=AutomationControlled"],
    )
    try:
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        await page.goto(site.url, wait_until="domcontentloaded")
        await page.wait_for_timeout(6000)
        print("URL  :", page.url, flush=True)
        print("TITLE:", await page.title(), flush=True)
        print("LOGGED_OUT:", site.login_url_fragment in page.url, flush=True)

        print("\n== COMPOSER candidates ==", flush=True)
        for sel in ["textarea", "[contenteditable='true']", "div.ql-editor",
                    "[data-testid*='composer' i]", "[placeholder]"]:
            els = await page.query_selector_all(sel)
            print(f"  {sel!r}: {len(els)}", flush=True)
            for e in els[:2]:
                ph = await e.get_attribute("placeholder")
                aria = await e.get_attribute("aria-label")
                tn = await e.evaluate("e => e.tagName")
                print(f"     <{tn}> placeholder={ph!r} aria={aria!r}", flush=True)

        print("\n== SEND button candidates ==", flush=True)
        for sel in ["button[type='submit']", "button[aria-label*='Send' i]",
                    "button[data-testid*='send' i]", "button[aria-label]"]:
            els = await page.query_selector_all(sel)
            labels = []
            for e in els[:4]:
                labels.append(await e.get_attribute("aria-label"))
            print(f"  {sel!r}: {len(els)}  labels={labels}", flush=True)

        if do_gen:
            print("\n== GEN PROBE: sending image prompt ==", flush=True)
            composer = None
            for sel in [site.composer.split(",")[0].strip(), "textarea",
                        "[contenteditable='true']", "div.ql-editor"]:
                composer = await page.query_selector(sel)
                if composer:
                    print(f"  using composer {sel!r}", flush=True)
                    break
            if not composer:
                print("  NO COMPOSER FOUND — fix selector first", flush=True)
            else:
                custom = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--prompt=")), None)
                prompt = custom or "Generate an image of a single red apple on a plain white background"
                print(f"  prompt: {prompt[:90]!r}", flush=True)
                await composer.click()
                await page.keyboard.type(prompt)
                await page.wait_for_timeout(500)
                await page.keyboard.press("Enter")
                print("  sent. waiting 60s for the image...", flush=True)
                await page.wait_for_timeout(5000)
                # capture the assistant text early (catches a refusal vs a draw)
                try:
                    ts = await page.query_selector_all(site.assistant_turn)
                    if ts:
                        print(f"  early text: {(await ts[-1].inner_text())[:120]!r}", flush=True)
                except Exception:  # noqa: BLE001
                    pass
                await page.wait_for_timeout(55000)
                await page.wait_for_timeout(60000)
                imgs = await page.query_selector_all("img")
                print(f"  <img> count: {len(imgs)}", flush=True)
                seen = set()
                for im in imgs:
                    src = await im.get_attribute("src") or ""
                    host = src.split("/")[2] if "://" in src else src[:40]
                    if host and host not in seen:
                        seen.add(host)
                        print(f"     img host: {host}  | {src[:90]}", flush=True)
                print("\n  == assistant-turn candidates ==", flush=True)
                for sel in ["[data-testid*='message' i]", ".message-bubble",
                            "[class*='response' i]", "[class*='message' i]"]:
                    els = await page.query_selector_all(sel)
                    print(f"     {sel!r}: {len(els)}", flush=True)
        if "--dltest" in sys.argv:
            print("\n== DOWNLOAD TEST against an EXISTING generated image ==", flush=True)
            target = None
            for im in await page.query_selector_all("img"):
                s = await im.get_attribute("src") or ""
                if any(m in s for m in site.generated_image_markers):
                    target = (s, im)
                    break
            if not target:
                print("  no existing generated image found in view", flush=True)
            else:
                s, im = target
                print(f"  src: {s[:90]}", flush=True)
                # tier 1: context request
                try:
                    resp = await page.request.get(s)
                    b = await resp.body() if resp.ok else b""
                    print(f"  tier1 context.request: ok={resp.ok} bytes={len(b)}", flush=True)
                except Exception as e:  # noqa: BLE001
                    print(f"  tier1 context.request ERROR: {e}", flush=True)
                # tier 3: element screenshot
                try:
                    shot = await im.screenshot()
                    print(f"  tier3 element.screenshot: bytes={len(shot)}", flush=True)
                except Exception as e:  # noqa: BLE001
                    print(f"  tier3 element.screenshot ERROR: {e}", flush=True)
        print("\nPROBE DONE — leaving window open 8s", flush=True)
        await page.wait_for_timeout(8000)
    finally:
        try:
            await ctx.close()
        except Exception:
            pass
        await pw.stop()


if __name__ == "__main__":
    provider = sys.argv[1] if len(sys.argv) > 1 else "grok"
    do_gen = "--gen" in sys.argv
    asyncio.run(main(provider, do_gen))
