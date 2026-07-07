"""Generative fuzzer for the self-healing interaction engine — throw THOUSANDS of
randomized adversarial DOMs at it and assert the invariants hold on every one:

  INV-1 (money-safety): a button whose label contains a money/upsell term is
        NEVER clicked — not in an overlay, not anywhere.
  INV-2 (no-crash/bounded): the engine never raises and never hangs.
  INV-3 (clean-safety): on a page with NO overlay, it clicks NOTHING (a stray
        "Close"/"×" in plain body is left alone).

Two layers:
  • Pure-logic fuzz — 100k random labels through the money classifier, instant,
    runs in any venv.
  • Live browser fuzz — thousands of random buttons across random overlay layouts
    in real headless Chromium (skips without Playwright).

Script mode runs the full 10,000-button live fuzz:
    python tests/test_mcp_interact_fuzz.py 10000
"""
import asyncio
import os
import random
import string
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mcp_chatgpt"))

import interact as I  # noqa: E402

try:
    from playwright.async_api import async_playwright  # noqa: E402
    _HAVE_PW = True
except Exception:  # noqa: BLE001
    _HAVE_PW = False


# --- Pure-logic fuzz: money-safety classifier ---------------------------------
def test_money_safety_classifier_fuzz():
    rng = random.Random(20260707)
    junk = string.ascii_lowercase + "  "
    for _ in range(60000):
        av = rng.choice(I.AVOID)
        pre = "".join(rng.choice(junk) for _ in range(rng.randint(0, 10)))
        post = "".join(rng.choice(junk) for _ in range(rng.randint(0, 10)))
        # a money term ANYWHERE in the label must flag as avoid, any casing
        label = (pre + av + post)
        label = "".join(c.upper() if rng.random() < 0.3 else c for c in label)
        assert I._is_avoid(label), repr(label)
    for _ in range(40000):
        b = rng.choice(I.BENIGN_DISMISS)
        if any(a in b for a in I.AVOID):      # skip accidental overlaps
            continue
        assert not I._is_avoid(b), repr(b)     # a benign word is not money


# --- Live browser fuzz --------------------------------------------------------
HEAD = "<!DOCTYPE html><html><head><meta charset='utf-8'></head><body><script>window.__clicked=[]</script>"
COMPOSER = "<textarea id='composer' style='position:fixed;top:40%;left:32%;width:300px;height:56px'></textarea>"
TAIL = "</body></html>"

AVOID_SAMPLE = ["Upgrade to Plus", "Subscribe", "Buy now", "Start free trial", "Go Pro",
                "Add payment", "See plans", "Checkout", "Purchase credits", "Unlock premium"]
BENIGN_SAMPLE = ["No thanks", "Not now", "Dismiss", "Close", "Maybe later", "Skip",
                 "Got it", "Decline", "Reject all", "Cancel", "Schließen"]
NOISE = ["Home", "Settings", "Learn more", "Details", "Profile", "Share", "Menu",
         "Search", "Help", "Next", "Documentation", "Pricing page"]


def _btn(rng, idx):
    r = rng.random()
    if r < 0.30:
        return f"<button onclick=\"window.__clicked.push('avoid:{idx}')\">{rng.choice(AVOID_SAMPLE)}</button>", "avoid"
    if r < 0.62:
        return f"<button onclick=\"window.__clicked.push('benign:{idx}')\">{rng.choice(BENIGN_SAMPLE)}</button>", "benign"
    if r < 0.75:
        return f"<button aria-label='Close' onclick=\"window.__clicked.push('icon:{idx}')\">×</button>", "icon"
    return f"<button onclick=\"window.__clicked.push('noise:{idx}')\">{rng.choice(NOISE)}</button>", "noise"


def _overlay(rng, inner):
    t = rng.choice(["dialog", "toast", "fixed", "cookie", "shadow"])
    z = rng.randint(60, 5000)
    if t == "dialog":
        return (f"<div role='dialog' aria-modal='true' style='position:fixed;inset:0;z-index:{z};"
                f"background:rgba(0,0,0,.35);display:flex;align-items:center;justify-content:center'>"
                f"<div style='background:#fff;padding:10px'>{inner}</div></div>")
    if t == "toast":
        return f"<div style='position:fixed;top:8px;right:8px;z-index:{z};background:#eef;padding:8px'>{inner}</div>"
    if t == "cookie":
        return f"<div id='cookie{z}' style='position:fixed;bottom:0;left:0;z-index:{z};background:#ffd;padding:8px'>{inner}</div>"
    if t == "fixed":
        return f"<div style='position:fixed;top:20%;left:20%;z-index:{z};background:#fff;border:1px solid #ccc;padding:8px'>{inner}</div>"
    # shadow host
    sid = f"sh{z}"
    return (f"<div id='{sid}'></div><script>(()=>{{const h=document.getElementById('{sid}');"
            f"const r=h.attachShadow({{mode:'open'}});r.innerHTML=`<div role='dialog' style='position:fixed;inset:0;"
            f"z-index:{z};background:rgba(0,0,0,.35)'>{inner}</div>`;}})()</script>")


def _gen_page(seed):
    rng = random.Random(seed)
    clean = rng.random() < 0.20
    idx, parts = 0, [HEAD, COMPOSER]
    kinds = []
    if clean:
        n = rng.randint(3, 15)
        for _ in range(n):
            html, k = _btn(rng, idx); idx += 1; parts.append(html); kinds.append(k)
    else:
        for _ in range(rng.randint(1, 4)):
            nb = rng.randint(1, 8)
            inner = ""
            for _ in range(nb):
                html, k = _btn(rng, idx); idx += 1; inner += html; kinds.append(k)
            parts.append(_overlay(rng, inner))
    parts.append(TAIL)
    return "".join(parts), idx, clean


def _fake_site():
    return type("S", (), {"composer": "#composer", "url": "https://fuzz.local/", "send_button": "",
                          "dismiss_buttons": (), "intro_buttons": (), "consent_buttons": (),
                          "blocking_overlay_markers": ()})()


async def _launch(p):
    for kw in ({}, {"channel": "chrome"}, {"channel": "msedge"}):
        try:
            return await p.chromium.launch(headless=True, **kw)
        except Exception:  # noqa: BLE001
            continue
    raise RuntimeError("no headless browser available")


async def _fuzz_live(target_buttons, seed0=7):
    rng = random.Random(seed0)
    site = _fake_site()
    stats = {"pages": 0, "buttons": 0, "avoid_clicks": 0, "crashes": 0,
             "clean_violations": 0, "bad_seeds": []}
    async with async_playwright() as p:
        browser = await _launch(p)
        page = await browser.new_page()
        while stats["buttons"] < target_buttons:
            seed = rng.randrange(1 << 30)
            html, nbtn, clean = _gen_page(seed)
            stats["pages"] += 1
            stats["buttons"] += nbtn
            try:
                await page.set_content(html)
                await I.dismiss_overlays(page, site, max_rounds=6, capture=False, settle_ms=0, fast=True)
                clicked = await page.evaluate("() => window.__clicked || []")
            except Exception:  # noqa: BLE001
                stats["crashes"] += 1
                stats["bad_seeds"].append(("crash", seed))
                continue
            if any(str(c).startswith("avoid:") for c in clicked):
                stats["avoid_clicks"] += 1
                stats["bad_seeds"].append(("avoid", seed))
            if clean and clicked:
                stats["clean_violations"] += 1
                stats["bad_seeds"].append(("clean", seed))
        await browser.close()
    return stats


def test_live_fuzz_smoke():
    import pytest
    if not _HAVE_PW:
        pytest.skip("playwright not installed in this venv")
    try:
        stats = asyncio.run(_fuzz_live(target_buttons=400))
    except RuntimeError as e:
        pytest.skip(str(e))
    assert stats["avoid_clicks"] == 0, stats["bad_seeds"]
    assert stats["crashes"] == 0, stats["bad_seeds"]
    assert stats["clean_violations"] == 0, stats["bad_seeds"]


if __name__ == "__main__":
    target = int(sys.argv[1]) if len(sys.argv) > 1 else 10000
    seed0 = int(sys.argv[2]) if len(sys.argv) > 2 else 7
    skip_pure = len(sys.argv) > 3 and sys.argv[3] == "nopure"
    if not skip_pure:
        print("pure-logic money-safety fuzz (100k cases)...")
        test_money_safety_classifier_fuzz()
        print("  OK")
    print(f"live browser fuzz targeting {target} random buttons (seed0={seed0})...")
    s = asyncio.run(_fuzz_live(target_buttons=target, seed0=seed0))
    print(f"  pages={s['pages']} buttons={s['buttons']} "
          f"avoid_clicks={s['avoid_clicks']} crashes={s['crashes']} clean_violations={s['clean_violations']}")
    if s["bad_seeds"]:
        print("  FAILURES (repro seeds):", s["bad_seeds"][:20])
    ok = s["avoid_clicks"] == 0 and s["crashes"] == 0 and s["clean_violations"] == 0
    print("RESULT:", "PASS — all invariants held" if ok else "FAIL")
    sys.exit(0 if ok else 1)
