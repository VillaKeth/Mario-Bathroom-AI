"""Inventory (and optionally download) generated images already sitting in a
ChatGPT account's conversation history — so we can reuse existing renders
instead of regenerating them.

Walks the sidebar conversation list, opens each chat, reads the first user
message (to identify what was asked) and any generated image in it.

Run:
  mcp_chatgpt/venv/Scripts/python.exe mcp_chatgpt/harvest_history.py --account work --limit 60
  ... add --download to also save the images to mcp_chatgpt/output/harvest/
"""
import argparse
import asyncio
import base64
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from playwright.async_api import async_playwright  # noqa: E402
from mcp_chatgpt import selectors  # noqa: E402
from mcp_chatgpt.browser import profile_dir, OUTPUT_DIR  # noqa: E402

HARVEST_DIR = Path(OUTPUT_DIR) / "harvest"


async def _gen_image_srcs(page):
    out = []
    for img in await page.query_selector_all("img"):
        src = await img.get_attribute("src") or ""
        if any(m in src for m in selectors.GENERATED_IMAGE_MARKERS):
            out.append(src)
    # de-dupe, keep order
    seen, uniq = set(), []
    for s in out:
        if s not in seen:
            seen.add(s)
            uniq.append(s)
    return uniq


async def _download(page, src, dst: Path):
    b64 = await page.evaluate(
        """async (url) => {
            const r = await fetch(url);
            const buf = await r.arrayBuffer();
            let s = ''; const b = new Uint8Array(buf);
            for (let j=0;j<b.length;j++) s += String.fromCharCode(b[j]);
            return btoa(s);
        }""",
        src,
    )
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(base64.b64decode(b64))


async def run(account: str, limit: int, download: bool) -> None:
    pw = await async_playwright().start()
    ctx = await pw.chromium.launch_persistent_context(
        profile_dir("chatgpt", account), channel="chrome", headless=False,
        args=["--disable-blink-features=AutomationControlled"],
    )
    try:
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        await page.goto(selectors.URL, wait_until="domcontentloaded")
        await page.wait_for_timeout(4000)

        # Collect conversation links from the sidebar (scroll to load more).
        hrefs: list[str] = []
        for _ in range(8):
            for a in await page.query_selector_all('a[href*="/c/"]'):
                h = await a.get_attribute("href")
                if h and h not in hrefs:
                    hrefs.append(h)
            if len(hrefs) >= limit:
                break
            await page.mouse.wheel(0, 4000)
            await page.wait_for_timeout(800)

        hrefs = hrefs[:limit]
        print(f"FOUND {len(hrefs)} conversations in sidebar", flush=True)

        total_imgs = 0
        with_imgs = 0
        for i, h in enumerate(hrefs):
            url = h if h.startswith("http") else f"https://chatgpt.com{h}"
            try:
                await page.goto(url, wait_until="domcontentloaded")
                await page.wait_for_timeout(2500)
            except Exception as e:  # noqa: BLE001
                print(f"[{i:02d}] open error {e}", flush=True)
                continue
            users = await page.query_selector_all('[data-message-author-role="user"]')
            first = (await users[0].inner_text())[:70].replace("\n", " ") if users else "(no user msg)"
            srcs = await _gen_image_srcs(page)
            total_imgs += len(srcs)
            if srcs:
                with_imgs += 1
            cid = h.rstrip("/").split("/c/")[-1]
            print(f"[{i:02d}] imgs={len(srcs)} | {first!r}", flush=True)
            if download and srcs:
                for k, src in enumerate(srcs):
                    await _download(page, src, HARVEST_DIR / f"{cid}_{k}.png")

        print(f"\nSUMMARY conversations={len(hrefs)} with_images={with_imgs} total_images={total_imgs}",
              flush=True)
        if download:
            print("downloaded to:", HARVEST_DIR, flush=True)
    finally:
        try:
            await ctx.close()
        except Exception:
            pass
        await pw.stop()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--account", default="default")
    ap.add_argument("--limit", type=int, default=60)
    ap.add_argument("--download", action="store_true")
    a = ap.parse_args()
    asyncio.run(run(a.account, a.limit, a.download))
