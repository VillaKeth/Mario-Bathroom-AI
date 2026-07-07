"""Adversarial battery for the self-healing interaction engine — throw EVERYTHING
at it in a real headless browser and assert it never breaks and never mis-clicks.

Scenarios: clean page (must NOT touch a stray Close), stacked modals, upsell-only
trap (must not click, must not hang), Escape-only modal, backdrop-click modal,
shadow-DOM close, icon-only close, contenteditable composer, decoy avoid-word
button, invisible pointer-blocker, and a 40-decoy-button haystack.

Runs under any venv with Playwright (skips otherwise — no main-suite regression).
Script mode:  python tests/test_mcp_interact_adversarial.py
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


def _site(composer="#composer"):
    return type("S", (), {"composer": composer, "url": "https://harness.local/",
                          "send_button": "", "dismiss_buttons": (), "intro_buttons": (),
                          "consent_buttons": (), "blocking_overlay_markers": ()})()


COMPOSER = "<textarea id='composer' style='position:fixed;top:38%;left:30%;width:320px;height:60px'></textarea>"
HEAD = "<!DOCTYPE html><html><head><meta charset='utf-8'></head><body><script>window.__clicked=[]</script>"
TAIL = "</body></html>"


def _modal(inner, z=2000, mid="m"):
    return (f"<div id='{mid}' role='dialog' aria-modal='true' style='position:fixed;inset:0;"
            f"background:rgba(0,0,0,.6);z-index:{z};display:flex;align-items:center;"
            f"justify-content:center'><div style='background:#fff;padding:20px'>{inner}</div></div>")


# Each scenario: html + expectations. composer defaults to #composer.
SCENARIOS = [
    {
        "name": "clean_page_no_false_positive",
        "html": HEAD + COMPOSER +
                "<nav><button onclick=\"__clicked.push('closemenu')\">Close menu</button>"
                "<button onclick=\"__clicked.push('dismissnotif')\" aria-label='Dismiss'>Dismiss</button></nav>" + TAIL,
        "must_not_click": ["closemenu", "dismissnotif"], "uncovered": True, "fill": True,
    },
    {
        "name": "stacked_modals",
        "html": HEAD + COMPOSER +
                _modal("<button onclick=\"__clicked.push('u1')\">Upgrade to Plus</button>"
                       "<button onclick=\"__clicked.push('b1');m1.remove()\">No thanks</button>", 2000, "m1") +
                _modal("<button onclick=\"__clicked.push('b2');m2.remove()\">Not now</button>", 2100, "m2") +
                _modal("<button onclick=\"__clicked.push('b3');m3.remove()\">Dismiss</button>", 2200, "m3") + TAIL,
        "must_click": ["b1", "b2", "b3"], "must_not_click": ["u1"], "uncovered": True, "fill": True,
    },
    {
        "name": "upsell_only_trap",
        "html": HEAD + COMPOSER +
                _modal("<button onclick=\"__clicked.push('up')\">Upgrade to Plus</button>"
                       "<button onclick=\"__clicked.push('sub')\">Subscribe now</button>", 2000, "m1") + TAIL,
        "must_not_click": ["up", "sub"], "uncovered": False, "fill": False,
    },
    {
        "name": "escape_only_modal",
        "html": HEAD + COMPOSER +
                _modal("<span>Press Escape</span>", 2000, "m1") +
                "<script>document.addEventListener('keydown',e=>{if(e.key==='Escape'){var m=document.getElementById('m1');if(m){m.remove();window.__clicked.push('esc')}}})</script>" + TAIL,
        "must_click": ["esc"], "uncovered": True, "fill": True,
    },
    {
        "name": "backdrop_click_modal",
        "html": HEAD + COMPOSER +
                "<div id='m1' role='dialog' onclick=\"if(event.target===this){this.remove();window.__clicked.push('back')}\" "
                "style='position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:2000'>"
                "<div style='background:#fff;padding:20px;margin:20% auto;width:200px'>No button here</div></div>" + TAIL,
        "must_click": ["back"], "uncovered": True, "fill": True,
    },
    {
        "name": "shadow_dom_close",
        "html": HEAD + COMPOSER +
                "<my-modal></my-modal><script>"
                "class M extends HTMLElement{connectedCallback(){const r=this.attachShadow({mode:'open'});"
                "r.innerHTML=`<div role='dialog' style='position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:2000;"
                "display:flex;align-items:center;justify-content:center'><div style='background:#fff;padding:20px'>"
                "<button id='x'>No thanks</button></div></div>`;"
                "r.getElementById('x').onclick=()=>{window.__clicked.push('shadow');this.remove()}}}"
                "customElements.define('my-modal',M)</script>" + TAIL,
        "must_click": ["shadow"], "uncovered": True, "fill": True,
    },
    {
        "name": "icon_only_close",
        "html": HEAD + COMPOSER +
                _modal("<span>Newsletter</span><button aria-label='Close' "
                       "onclick=\"__clicked.push('icon');m1.remove()\"><svg width=12 height=12></svg></button>", 2000, "m1") + TAIL,
        "must_click": ["icon"], "uncovered": True, "fill": True,
    },
    {
        "name": "contenteditable_composer",
        "html": HEAD + "<div id='composer' contenteditable='true' style='position:fixed;top:38%;left:30%;width:320px;height:60px;border:1px solid #ccc'></div>" +
                _modal("<button onclick=\"__clicked.push('ce');m1.remove()\">No thanks</button>", 2000, "m1") + TAIL,
        "composer": "#composer", "must_click": ["ce"], "uncovered": True, "fill": True,
    },
    {
        "name": "decoy_avoid_word",
        "html": HEAD + COMPOSER +
                _modal("<button onclick=\"__clicked.push('decoy')\">Continue to upgrade</button>"
                       "<button onclick=\"__clicked.push('real');m1.remove()\">No thanks</button>", 2000, "m1") + TAIL,
        "must_click": ["real"], "must_not_click": ["decoy"], "uncovered": True, "fill": True,
    },
    {
        "name": "invisible_pointer_blocker",
        "html": HEAD + COMPOSER +
                "<div id='blk' style='position:fixed;inset:0;z-index:2000;opacity:0.01;background:#000'></div>" +
                _modal("<button onclick=\"__clicked.push('skip');document.getElementById('blk').remove();m1.remove()\">Skip</button>", 2100, "m1") + TAIL,
        "must_click": ["skip"], "uncovered": True, "fill": True,
    },
    {
        "name": "haystack_40_decoys",
        "html": HEAD + COMPOSER +
                "".join(f"<button onclick=\"__clicked.push('dec{i}')\">Option {i}</button>" for i in range(40)) +
                _modal("<button onclick=\"__clicked.push('needle');m1.remove()\">No thanks</button>", 2000, "m1") + TAIL,
        "must_click": ["needle"], "must_not_click": [f"dec{i}" for i in range(40)], "uncovered": True, "fill": True,
    },
    {
        "name": "native_dialog_showmodal",
        "html": HEAD + COMPOSER +
                "<dialog id='d1'><button onclick=\"__clicked.push('native');document.getElementById('d1').close();document.getElementById('d1').remove()\">No thanks</button></dialog>"
                "<script>document.getElementById('d1').showModal()</script>" + TAIL,
        "must_click": ["native"], "uncovered": True, "fill": True,
    },
    {
        "name": "respawning_modal_bounded",
        "html": HEAD + COMPOSER + "<script>window.__n=0;function spawn(){var m=document.createElement('div');"
                "m.id='rm';m.setAttribute('role','dialog');m.setAttribute('aria-modal','true');"
                "m.style='position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:2000;display:flex;align-items:center;justify-content:center';"
                "m.innerHTML=\"<div style='background:#fff;padding:20px'><button>No thanks</button></div>\";"
                "m.querySelector('button').onclick=function(){window.__clicked.push('rs'+window.__n);m.remove();window.__n++;if(window.__n<3)setTimeout(spawn,40)};"
                "document.body.appendChild(m)}spawn()</script>" + TAIL,
        "must_click": ["rs0", "rs1", "rs2"], "uncovered": True, "fill": True,
    },
    {
        "name": "nested_iframe_consent",
        "html": HEAD + COMPOSER +
                "<iframe style='position:fixed;bottom:0;left:0;width:100%;height:80px;border:0;z-index:1400' "
                "srcdoc=\"<iframe style='width:100%;height:70px;border:0' srcdoc=&quot;<body><button onclick=&amp;quot;window.top.__clicked.push('nested');document.body.remove()&amp;quot;>Reject all</button></body>&quot;></iframe>\"></iframe>" + TAIL,
        "must_click": ["nested"], "uncovered": True, "fill": True,
    },
    {
        "name": "two_consent_iframes",
        "html": HEAD + COMPOSER +
                "<iframe style='position:fixed;top:0;left:0;width:100%;height:60px;border:0;z-index:1400' srcdoc=\"<body><button onclick=&quot;window.parent.__clicked.push('cf1');document.body.remove()&quot;>No thanks</button></body>\"></iframe>"
                "<iframe style='position:fixed;bottom:0;left:0;width:100%;height:60px;border:0;z-index:1400' srcdoc=\"<body><button onclick=&quot;window.parent.__clicked.push('cf2');document.body.remove()&quot;>Reject all</button></body>\"></iframe>" + TAIL,
        "must_click": ["cf1", "cf2"], "uncovered": True, "fill": True,
    },
    {
        "name": "i18n_close_only",
        "html": HEAD + COMPOSER +
                _modal("<button onclick=\"__clicked.push('de');m1.remove()\">Schließen</button>", 2000, "m1") + TAIL,
        "must_click": ["de"], "uncovered": True, "fill": True,
    },
    {
        "name": "link_as_button",
        "html": HEAD + COMPOSER +
                _modal("<a href='#' onclick=\"__clicked.push('link');m1.remove();return false\">No thanks</a>", 2000, "m1") + TAIL,
        "must_click": ["link"], "uncovered": True, "fill": True,
    },
    {
        "name": "div_role_button_close",
        "html": HEAD + COMPOSER +
                _modal("<div role='button' onclick=\"__clicked.push('divbtn');m1.remove()\">Close</div>", 2000, "m1") + TAIL,
        "must_click": ["divbtn"], "uncovered": True, "fill": True,
    },
    {
        "name": "disabled_button_skipped",
        "html": HEAD + COMPOSER +
                _modal("<button disabled onclick=\"__clicked.push('disabled')\">No thanks</button>"
                       "<button onclick=\"__clicked.push('enabled');m1.remove()\">Dismiss</button>", 2000, "m1") + TAIL,
        "must_click": ["enabled"], "must_not_click": ["disabled"], "uncovered": True, "fill": True,
    },
    {
        "name": "emoji_text_close",
        "html": HEAD + COMPOSER +
                _modal("<button onclick=\"__clicked.push('emoji');m1.remove()\">❌ Close</button>", 2000, "m1") + TAIL,
        "must_click": ["emoji"], "uncovered": True, "fill": True,
    },
    {
        "name": "sticky_cookie_bar",
        "html": HEAD + COMPOSER +
                "<div id='cookie-bar' style='position:sticky;bottom:0;background:#ffd;padding:10px'>We use cookies "
                "<button onclick=\"__clicked.push('sticky');document.getElementById('cookie-bar').remove()\">Reject all</button></div>" + TAIL,
        "must_click": ["sticky"], "uncovered": True, "fill": True,
    },
    {
        "name": "max_z_toast",
        "html": HEAD + COMPOSER +
                "<div style='position:fixed;top:10px;right:10px;z-index:2147483647;background:#eef;padding:10px'>New feature "
                "<button aria-label='Close' onclick=\"__clicked.push('toast');this.closest('div').remove()\">×</button></div>" + TAIL,
        "must_click": ["toast"], "uncovered": True, "fill": True,
    },
    {
        "name": "perf_1000_buttons",
        "html": HEAD + COMPOSER +
                "".join(f"<button onclick=\"__clicked.push('p{i}')\">Item {i}</button>" for i in range(1000)) +
                _modal("<button onclick=\"__clicked.push('pneedle');m1.remove()\">No thanks</button>", 2000, "m1") + TAIL,
        "must_click": ["pneedle"], "uncovered": True, "fill": True,
    },
    {
        "name": "js_error_page",
        "html": HEAD + "<script>window.onerror=()=>true; setTimeout(()=>{throw new Error('boom')},10)</script>" + COMPOSER +
                _modal("<button onclick=\"__clicked.push('jserr');m1.remove()\">No thanks</button>", 2000, "m1") + TAIL,
        "must_click": ["jserr"], "uncovered": True, "fill": True,
    },
]


async def _launch(p):
    for kw in ({}, {"channel": "chrome"}, {"channel": "msedge"}):
        try:
            return await p.chromium.launch(headless=True, **kw)
        except Exception:  # noqa: BLE001
            continue
    raise RuntimeError("no headless browser available")


async def _one(browser, sc):
    site = _site(sc.get("composer", "#composer"))
    page = await browser.new_page()
    fails = []
    try:
        await page.set_content(sc["html"])
        await page.wait_for_timeout(300)
        await I.dismiss_overlays(page, site, max_rounds=12)
        clicked = await page.evaluate("() => window.__clicked || []")
        for m in sc.get("must_not_click", ()):
            if m in clicked:
                fails.append(f"clicked forbidden '{m}'")
        for m in sc.get("must_click", ()):
            if m not in clicked:
                fails.append(f"missing required click '{m}' (got {clicked})")
        occ = await I.occlusion(page, site)
        if sc.get("uncovered") is True and occ.get("covered"):
            fails.append(f"composer still covered ({occ.get('cover')})")
        if sc.get("uncovered") is False and not occ.get("covered"):
            fails.append("composer expected still covered but wasn't")
        if "fill" in sc:
            ok = await I.safe_fill(page, site, "adversary probe")
            if ok != sc["fill"]:
                fails.append(f"safe_fill returned {ok}, expected {sc['fill']}")
    except Exception as e:  # noqa: BLE001
        fails.append(f"EXCEPTION {type(e).__name__}: {e}")
    finally:
        await page.close()
    return fails


async def _run():
    results = {}
    async with async_playwright() as p:
        browser = await _launch(p)
        for sc in SCENARIOS:
            results[sc["name"]] = await _one(browser, sc)
        await browser.close()
    return results


def test_adversarial_battery():
    import pytest
    if not _HAVE_PW:
        pytest.skip("playwright not installed in this venv")
    try:
        results = asyncio.run(_run())
    except RuntimeError as e:
        pytest.skip(str(e))
    broken = {k: v for k, v in results.items() if v}
    assert not broken, "adversarial failures: " + "; ".join(f"{k}: {v}" for k, v in broken.items())


if __name__ == "__main__":
    res = asyncio.run(_run())
    ok = 0
    for name, fails in res.items():
        print(f"{'PASS' if not fails else 'FAIL'}  {name}" + ("" if not fails else "  -> " + "; ".join(fails)))
        ok += not fails
    print(f"\n{ok}/{len(res)} scenarios passed")
    sys.exit(0 if ok == len(res) else 1)
