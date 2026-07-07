"""LIVE end-to-end proof of the self-healing interaction engine.

Launches headless Chromium against a local page that spawns four real overlays:
  1. a role=dialog "offer" modal covering the composer, with a benign "No thanks"
     AND a money "Upgrade to Plus" button,
  2. an X-glyph "rate us" nag (aria-label=Close),
  3. a cookie consent inside an IFRAME with a "Reject all" button,
then asserts dismiss_overlays:
  • clears the offer modal via "No thanks",
  • clears the X nag,
  • reaches INTO the iframe and clears the cookie banner,
  • NEVER clicks the upsell,
  • leaves the composer un-occluded (elementFromPoint proof),
  • and safe_fill then lands text.

Runs under any venv with Playwright (skips cleanly otherwise, so it never breaks
the main suite). Also runnable as a script:  python tests/test_mcp_interact_live.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mcp_chatgpt"))

import interact as I  # noqa: E402

try:
    from playwright.async_api import async_playwright  # noqa: E402
    _HAVE_PW = True
except Exception:  # noqa: BLE001
    _HAVE_PW = False


class _FakeSite:
    composer = "#composer"
    url = "https://harness.local/"
    send_button = ""
    dismiss_buttons = ()
    intro_buttons = ()
    consent_buttons = ()
    blocking_overlay_markers = ()


HTML = """<!DOCTYPE html><html><head><meta charset="utf-8"></head><body>
<textarea id="composer" style="position:fixed;top:40%;left:30%;width:320px;height:64px;"></textarea>
<script>window.__clicked=[];</script>
<div id="m1" role="dialog" aria-modal="true"
     style="position:fixed;inset:0;background:rgba(0,0,0,.7);z-index:2000;display:flex;align-items:center;justify-content:center;">
  <div style="background:#fff;padding:24px;border-radius:8px;">
    <p>Special limited offer!</p>
    <button onclick="window.__clicked.push('upsell')">Upgrade to Plus</button>
    <button onclick="window.__clicked.push('benign');document.getElementById('m1').remove();">No thanks</button>
  </div>
</div>
<div id="m2" role="dialog"
     style="position:fixed;top:12px;right:12px;background:#eef;padding:10px;z-index:1500;">
  <span>Rate your experience</span>
  <button aria-label="Close"
     onclick="window.__clicked.push('xclose');document.getElementById('m2').remove();">&times;</button>
</div>
<iframe id="cookieframe"
   style="position:fixed;bottom:0;left:0;width:100%;height:70px;border:0;z-index:1400;background:#ffd;"
   srcdoc="<!DOCTYPE html><body style='font-family:sans-serif;margin:8px'>We use cookies.
     <button onclick=&quot;window.parent.__clicked.push('cookie'); document.body.remove();&quot;>Reject all</button></body>">
</iframe>
</body></html>"""


async def _launch(p):
    for kw in ({}, {"channel": "chrome"}, {"channel": "msedge"}):
        try:
            return await p.chromium.launch(headless=True, **kw)
        except Exception:  # noqa: BLE001
            continue
    raise RuntimeError("no chromium/chrome/edge available for headless launch")


async def _run():
    site = _FakeSite()
    async with async_playwright() as p:
        browser = await _launch(p)
        page = await browser.new_page()
        await page.set_content(HTML)
        await page.wait_for_timeout(350)

        occ0 = await I.occlusion(page, site)
        assert occ0.get("covered") is True, f"composer should start covered: {occ0}"

        rounds = await I.dismiss_overlays(page, site, max_rounds=10)

        clicked = await page.evaluate("() => window.__clicked || []")
        assert "upsell" not in clicked, f"MONEY BUTTON CLICKED: {clicked}"
        assert "benign" in clicked, f"offer modal not dismissed benignly: {clicked}"
        assert "cookie" in clicked, f"iframe cookie banner not reached: {clicked}"

        occ1 = await I.occlusion(page, site)
        assert not occ1.get("covered"), f"composer still occluded after sweep: {occ1}"

        ok = await I.safe_fill(page, site, "hello harness")
        assert ok, "safe_fill returned False"
        val = await page.eval_on_selector("#composer", "e => e.value")
        assert "hello" in val, f"composer text not landed: {val!r}"

        await browser.close()
    return rounds, clicked, occ1


def test_live_overlay_dismissal_end_to_end():
    import pytest
    if not _HAVE_PW:
        pytest.skip("playwright not installed in this venv")
    try:
        rounds, clicked, occ1 = asyncio.run(_run())
    except RuntimeError as e:
        pytest.skip(str(e))
    assert "upsell" not in clicked


if __name__ == "__main__":
    r, c, o = asyncio.run(_run())
    print(f"LIVE HARNESS PASS  rounds={r}  clicked={c}  occluded_after={o.get('covered')}")
