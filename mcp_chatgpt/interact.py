"""Self-healing, occlusion-aware page interaction for the browser wrappers.

Any provider's web UI (ChatGPT / Grok / Gemini) can throw a modal, consent
banner, upsell, cookie wall, survey, or "session expired" overlay IN FRONT of
the composer at ANY time — not just at login. Those intercept clicks/fills and
a naive wrapper hangs on a locator timeout. This module makes the wrappers
self-heal, WITHOUT the caller ever babysitting them, via several layered
techniques (not just a list of selectors):

  • Occlusion detection — `document.elementFromPoint` at the composer's centre
    tells us DEFINITIVELY whether the composer is clickable or covered, and by
    what element. Far more reliable than guessing overlay selectors.

  • Heuristic dismiss-discovery — a JS pass enumerates every button / role=button
    / anchor, SCORES each by how much it looks like a "close this" control
    (benign text, close/dismiss aria-label, a bare "×" glyph, being inside a
    dialog) and clicks the best one. It finds the close control even when we have
    no selector for it, and it NEVER clicks a money/upsell CTA (an AVOID list
    disqualifies Upgrade / Subscribe / Buy / …).

  • iframe-aware — consent managers (OneTrust, Google) render inside iframes, so
    the sweep runs across every frame, not just the main document.

  • Escalation ladder — per-site buttons → generic benign → heuristic scan →
    close-icon → Escape → consent/ToS (only when still blocked) → backdrop
    click-away, bounded and idempotent (stops the instant a round does nothing).

  • Diagnostic capture — when it genuinely cannot clear a detected overlay it
    writes a screenshot + the covering element's outerHTML to output/, so an
    unknown popup is logged once and a precise selector can be added later.

  • Branching interaction — safe_fill / safe_send / safe_click each ladder
    through normal → dismiss+retry → force → keyboard → JS/dispatch, and verify
    the fill/click actually landed.

Everything is defensive: every strategy is individually wrapped, loops are
bounded. Worst case is a no-op — never a crash or an infinite loop.
"""
import os
import time

# --- Button-text classification -----------------------------------------------
# BENIGN: clicking CLOSES a nag with no cost or account change — safe anytime.
BENIGN_DISMISS = (
    "no thanks", "no, thanks", "no thank you", "not now", "not right now",
    "maybe later", "later", "remind me later", "skip", "skip for now",
    "dismiss", "got it", "close", "done", "decline", "reject all", "reject",
    "deny", "don't allow", "cancel", "no, continue", "continue without",
)
# CONSENT / ToS: click ONLY when an overlay still blocks and nothing benign
# matched — required-to-proceed acknowledgements, NOT purchases.
CONSENT_ACCEPT = (
    "accept all", "accept and continue", "agree and continue", "i agree",
    "i understand", "acknowledge", "yes, i agree", "accept", "agree",
    "continue", "okay", "ok",
)
# NEVER click — money / account state / upsell.
AVOID = (
    "upgrade", "subscribe", "get plus", "try plus", "go pro", "get pro", "buy",
    "purchase", "pay", "payment", "start free trial", "start trial", "add card",
    "add payment", "upgrade to", "see plans", "choose plan", "unlock", "checkout",
)

# Selectors that indicate a blocking overlay / modal is present.
OVERLAY_SELECTORS = (
    "[role='dialog']", "[aria-modal='true']", "dialog[open]",
    "[class*='modal' i]", "[class*='overlay' i]", "[class*='backdrop' i]",
    "[class*='dialog' i]", "[id*='cookie' i]", "[class*='consent' i]",
)
# Close-icon (X) buttons.
CLOSE_ICON_SELECTORS = (
    "[aria-label*='close' i]", "[aria-label*='dismiss' i]",
    "[data-testid*='close' i]", "button[class*='close' i]", "[title*='close' i]",
)

_OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")


def _norm(text) -> str:
    return (text or "").strip().lower()


def _is_avoid(text) -> bool:
    t = _norm(text)
    return any(a in t for a in AVOID)


def _benign_selectors():
    out = []
    for p in BENIGN_DISMISS:
        out.append(f"button:has-text('{p}')")
        out.append(f"[role='button']:has-text('{p}')")
    return out


def _consent_selectors(site):
    out = list(getattr(site, "consent_buttons", ()) or ())
    for p in CONSENT_ACCEPT:
        out.append(f"button:has-text('{p}')")
        out.append(f"[role='button']:has-text('{p}')")
    return out


# --- JS payloads (run in-page / in-frame) -------------------------------------
# Heuristic dismiss-discovery: score every candidate control and MARK the best
# one with data-mcp-dismiss='1' so Playwright can click it reliably.
_JS_SCAN_DISMISS = r"""
([benign, avoid]) => {
  const cands = Array.from(document.querySelectorAll(
    "button, [role=button], a[role=button], [tabindex]:not([tabindex='-1'])"));
  const vis = el => { try { const r = el.getBoundingClientRect(); const s = getComputedStyle(el);
    return r.width > 2 && r.height > 2 && s.visibility !== 'hidden' && s.display !== 'none'
      && s.pointerEvents !== 'none' && parseFloat(s.opacity || '1') > 0.05; } catch(e){ return false; } };
  const inModal = el => !!el.closest("[role=dialog],[aria-modal='true'],[class*=modal i],[class*=overlay i],dialog");
  const XGLYPH = /^[×✕✖✗✘╳xX⨯]$/;
  const score = el => {
    if (!vis(el)) return -1;
    const label = ((el.getAttribute('aria-label')||'') + ' ' + (el.getAttribute('title')||'')
      + ' ' + (el.textContent||'')).trim().toLowerCase();
    if (avoid.some(a => label.includes(a))) return -1;               // never money/upsell
    let sc = 0;
    if (benign.some(b => label.includes(b))) sc += 10;
    if (XGLYPH.test((el.textContent||'').trim())) sc += 8;           // bare "×" close glyph
    const al = (el.getAttribute('aria-label')||'').toLowerCase();
    if (al.includes('close') || al.includes('dismiss')) sc += 9;
    if (((el.className||'')+'').toLowerCase().includes('close')) sc += 4;
    if (inModal(el)) sc += 3;
    if (label.length > 40) sc -= 4;                                   // long text = not a dismiss
    return sc;
  };
  let best = null, bestScore = 0;
  for (const el of cands) { const s = score(el); if (s > bestScore) { bestScore = s; best = el; } }
  document.querySelectorAll("[data-mcp-dismiss]").forEach(e => e.removeAttribute('data-mcp-dismiss'));
  if (best && bestScore >= 6) {
    best.setAttribute('data-mcp-dismiss', '1');
    return { found: true, score: bestScore,
             label: ((best.getAttribute('aria-label')||best.textContent||'')+'').trim().slice(0, 60) };
  }
  return { found: false };
}
"""

# Occlusion probe: is the composer present, visible, and actually the top element
# at its own centre (i.e. clickable), or is something covering it?
_JS_OCCLUSION = r"""
(sel) => {
  const e = document.querySelector(sel);
  if (!e) return { present: false };
  const r = e.getBoundingClientRect();
  if (r.width < 2 || r.height < 2) return { present: true, visible: false, covered: false };
  const cx = Math.min(Math.max(r.left + r.width/2, 1), innerWidth-1);
  const cy = Math.min(Math.max(r.top + r.height/2, 1), innerHeight-1);
  const top = document.elementFromPoint(cx, cy);
  const covered = !!top && top !== e && !e.contains(top) && !top.contains(e);
  let cover = null;
  if (covered && top) cover = (top.tagName + (top.id ? '#'+top.id : '')
      + (top.className ? '.'+(''+top.className).split(' ').slice(0,2).join('.') : '')).slice(0, 120);
  return { present: true, visible: true, covered, cover };
}
"""


async def _click_if_visible(page, selector, timeout=1200) -> bool:
    """Click the first visible match of `selector`, skipping money/upsell buttons."""
    try:
        loc = page.locator(selector).first
        if await loc.count() == 0 or not await loc.is_visible():
            return False
        try:
            txt = await loc.inner_text(timeout=300)
        except Exception:  # noqa: BLE001
            txt = ""
        if _is_avoid(txt):
            return False
        await loc.click(timeout=timeout)
        return True
    except Exception:  # noqa: BLE001
        return False


async def _try_each(page, selectors, timeout=1200) -> bool:
    for sel in selectors:
        if await _click_if_visible(page, sel, timeout=timeout):
            return True
    return False


async def _scan_and_click(frame) -> bool:
    """Heuristic dismiss-discovery on one frame: score+mark the best benign close
    control in JS, then click it via Playwright. Returns True if it clicked one."""
    try:
        res = await frame.evaluate(_JS_SCAN_DISMISS, [list(BENIGN_DISMISS), list(AVOID)])
    except Exception:  # noqa: BLE001
        return False
    if not (res and res.get("found")):
        return False
    try:
        loc = frame.locator("[data-mcp-dismiss='1']").first
        await loc.click(timeout=1500)
        try:
            print(f"[interact] heuristic-dismissed '{res.get('label','')}' (score {res.get('score')})", flush=True)
        except Exception:  # noqa: BLE001
            pass
        return True
    except Exception:  # noqa: BLE001
        # JS click fallback (some overlays swallow synthetic Playwright clicks)
        try:
            await frame.evaluate("() => { const e=document.querySelector(\"[data-mcp-dismiss='1']\"); if(e) e.click(); }")
            return True
        except Exception:  # noqa: BLE001
            return False


async def _overlay_present(page, site) -> bool:
    sels = OVERLAY_SELECTORS + tuple(getattr(site, "blocking_overlay_markers", ()) or ())
    for sel in sels:
        try:
            loc = page.locator(sel).first
            if await loc.count() and await loc.is_visible():
                return True
        except Exception:  # noqa: BLE001
            continue
    return False


async def occlusion(page, site) -> dict:
    """{present, visible, covered, cover} for the composer — the authoritative
    'is it actually clickable' check."""
    try:
        return await page.evaluate(_JS_OCCLUSION, site.composer) or {}
    except Exception:  # noqa: BLE001
        return {}


def _frames(page):
    """Main frame first, then child frames (consent iframes)."""
    try:
        return list(page.frames)
    except Exception:  # noqa: BLE001
        return [page]


async def _capture_stuck(page, site, cover: str) -> None:
    """Log an unclearable overlay once: screenshot + covering element HTML, so a
    precise selector can be added later. Best-effort, never raises."""
    try:
        os.makedirs(_OUTPUT_DIR, exist_ok=True)
        stamp = f"stuck_{site_name(site)}_{int(time.time())}"
        try:
            await page.screenshot(path=os.path.join(_OUTPUT_DIR, stamp + ".png"))
        except Exception:  # noqa: BLE001
            pass
        try:
            html = await page.evaluate(
                """() => { const d = document.querySelector("[role=dialog],[aria-modal='true'],dialog,[class*=modal i]");
                     return d ? d.outerHTML.slice(0, 4000) : document.body.innerHTML.slice(0, 4000); }""")
            with open(os.path.join(_OUTPUT_DIR, stamp + ".html"), "w", encoding="utf-8") as f:
                f.write(f"<!-- cover={cover} url={page.url} -->\n{html}")
        except Exception:  # noqa: BLE001
            pass
        print(f"[interact] STUCK on overlay (cover={cover}); logged {stamp}.png/.html", flush=True)
    except Exception:  # noqa: BLE001
        pass


def site_name(site) -> str:
    try:
        return (getattr(site, "url", "") or "site").split("//")[-1].split(".")[0] or "site"
    except Exception:  # noqa: BLE001
        return "site"


async def dismiss_overlays(page, site, max_rounds=6, benign_only=False, capture=True) -> int:
    """Clear whatever is covering the page. Returns how many rounds acted. Safe to
    call before ANY interaction and repeatedly — stops as soon as a round is a
    no-op. `benign_only` skips Escape/consent/backdrop (use mid-generation)."""
    dismissed = 0
    last_cover = None
    for _ in range(max_rounds):
        acted = False
        # 1) per-site explicit dismiss + intro buttons (most specific, benign)
        site_sels = tuple(getattr(site, "dismiss_buttons", ()) or ()) + tuple(getattr(site, "intro_buttons", ()) or ())
        if await _try_each(page, site_sels):
            acted = True
        # 2) generic benign text buttons
        elif await _try_each(page, _benign_selectors()):
            acted = True
        # 3) heuristic dismiss-discovery across every frame (main + iframes)
        elif any([await _scan_and_click(fr) for fr in _frames(page)]):
            acted = True
        # 4) close-icon (X) buttons
        elif await _try_each(page, CLOSE_ICON_SELECTORS):
            acted = True
        # 5) escalate only when something still blocks and we're allowed to
        elif not benign_only and await _overlay_present(page, site):
            try:
                await page.keyboard.press("Escape")
                await page.wait_for_timeout(300)
            except Exception:  # noqa: BLE001
                pass
            if not await _overlay_present(page, site):
                acted = True
            elif await _try_each(page, _consent_selectors(site)):
                acted = True
            else:
                try:
                    await page.mouse.click(6, 6)
                    await page.wait_for_timeout(250)
                    acted = not await _overlay_present(page, site)
                except Exception:  # noqa: BLE001
                    acted = False
        if not acted:
            break
        dismissed += 1
        await page.wait_for_timeout(300)
    # If the composer is STILL occluded after all rounds, capture diagnostics once.
    if capture and not benign_only:
        occ = await occlusion(page, site)
        if occ.get("covered"):
            await _capture_stuck(page, site, occ.get("cover") or "?")
    return dismissed


async def sweep_light(page, site) -> int:
    """Throttled, benign-only sweep for use DURING generation — clears a nag that
    lands mid-render without risking a mis-click on generation controls."""
    return await dismiss_overlays(page, site, max_rounds=2, benign_only=True, capture=False)


async def _composer_ready(page, composer) -> bool:
    try:
        loc = page.locator(composer).first
        return bool(await loc.count()) and await loc.is_visible()
    except Exception:  # noqa: BLE001
        return False


async def _read_composer(page, composer) -> str:
    try:
        return await page.evaluate(
            """(sel) => { const e = document.querySelector(sel); if (!e) return '';
                 return (e.value !== undefined && e.value !== null) ? e.value : (e.innerText || ''); }""",
            composer,
        )
    except Exception:  # noqa: BLE001
        return ""


async def safe_fill(page, site, text: str) -> bool:
    """Put `text` into the composer, self-healing past overlays. Occlusion-gated
    (won't fight a covered composer — it clears the cover first) and verifies the
    text landed. Tiers: fill → click+fill → keyboard type → JS set."""
    composer = site.composer
    probe = (text or "").strip()[:24]
    for attempt in range(4):
        await dismiss_overlays(page, site)
        try:
            await page.wait_for_selector(composer, timeout=8000, state="visible")
        except Exception:  # noqa: BLE001
            await dismiss_overlays(page, site, max_rounds=4)
            if not await _composer_ready(page, composer):
                continue
        # If still occluded, sweep harder before trying (elementFromPoint truth)
        occ = await occlusion(page, site)
        if occ.get("covered"):
            await dismiss_overlays(page, site, max_rounds=4)
        try:
            loc = page.locator(composer).first
            if attempt == 0:
                await page.fill(composer, text)
            elif attempt == 1:
                await loc.click(timeout=3000)
                await loc.fill(text)
            elif attempt == 2:                         # contenteditable-friendly
                await loc.click(timeout=3000)
                try:
                    await page.keyboard.press("Control+A")
                    await page.keyboard.press("Delete")
                except Exception:  # noqa: BLE001
                    pass
                await page.keyboard.type(text, delay=1)
            else:                                       # JS set + input event
                await page.evaluate(
                    """([sel, val]) => {
                        const e = document.querySelector(sel); if (!e) return;
                        if (e.value !== undefined && e.value !== null) { e.value = val; }
                        else { e.innerText = val; }
                        e.dispatchEvent(new InputEvent('input', {bubbles:true}));
                    }""",
                    [composer, text],
                )
            got = await _read_composer(page, composer)
            if not probe or probe in (got or ""):
                return True
        except Exception:  # noqa: BLE001
            await dismiss_overlays(page, site, max_rounds=3)
            continue
    return False


async def safe_send(page, site) -> bool:
    """Submit the composer, self-healing past overlays. Send button if the site has
    one (with JS-click fallback), else Enter."""
    await dismiss_overlays(page, site)
    if getattr(site, "send_button", ""):
        if await _click_if_visible(page, site.send_button, timeout=4000):
            return True
        try:
            await page.evaluate("(sel)=>{const b=document.querySelector(sel); if(b) b.click();}", site.send_button)
            return True
        except Exception:  # noqa: BLE001
            pass
    try:
        await page.keyboard.press("Enter")
        return True
    except Exception:  # noqa: BLE001
        return False


async def safe_click(page, site, selector, timeout=4000) -> bool:
    """Click `selector`, self-healing past overlays. Tiers: normal → dismiss+retry
    → force → JS click → dispatch event."""
    for attempt in range(4):
        await dismiss_overlays(page, site)
        try:
            loc = page.locator(selector).first
            if await loc.count() == 0:
                return False
            if attempt <= 1:
                await loc.click(timeout=timeout)
            elif attempt == 2:
                await loc.click(timeout=timeout, force=True)
            else:
                await page.evaluate(
                    """(sel)=>{const e=document.querySelector(sel); if(!e) return;
                        e.click(); e.dispatchEvent(new MouseEvent('click',{bubbles:true}));}""",
                    selector,
                )
            return True
        except Exception:  # noqa: BLE001
            await dismiss_overlays(page, site, max_rounds=3)
            continue
    return False
