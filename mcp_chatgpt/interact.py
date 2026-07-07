"""Robust, self-healing page interaction for the browser wrappers.

Any provider's web UI (ChatGPT / Grok / Gemini) can throw a modal, consent
banner, upsell, survey, cookie wall, or "session expired" overlay IN FRONT of
the composer at ANY time — not just at login. Those intercept clicks/fills and
the naive wrapper hangs on a locator timeout. This module makes every
interaction self-heal so the caller never has to babysit it:

  dismiss_overlays()  — a bounded, multi-strategy sweep that clears whatever is
      covering the page, in priority order:
        1. per-site explicit dismiss / intro buttons  (most specific)
        2. generic BENIGN buttons  (No thanks / Not now / Close / Dismiss / X)
        3. close-icon buttons  (aria-label/testid/class = close)
        4. Escape key  (standard modal close)
        5. consent / ToS accept  — ONLY when an overlay still blocks and nothing
           benign worked (required-to-proceed acknowledgements, never purchases)
        6. backdrop click-away  (last resort for click-outside-to-close modals)
      It NEVER clicks a money/upsell CTA (Upgrade / Subscribe / Buy / …).

  safe_fill / safe_send / safe_click — interaction with a BRANCHING fallback
      chain (normal → dismiss+retry → force → keyboard → JS/dispatch) and
      verification that the fill/click actually landed.

Everything is defensive: every strategy is individually wrapped, failures are
non-fatal, loops are bounded. Worst case is a no-op — never a crash or an
infinite loop, so turning this on can only make the wrappers more robust.
"""

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


def _norm(text) -> str:
    return (text or "").strip().lower()


def _is_avoid(text) -> bool:
    t = _norm(text)
    return any(a in t for a in AVOID)


def _benign_selectors():
    # :has-text() is a case-insensitive substring match in Playwright.
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


async def _click_if_visible(page, selector, timeout=1200) -> bool:
    """Click the first visible match of `selector`, skipping money/upsell buttons.
    Never raises — returns True only on a real click."""
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


async def _try_each(page, selectors, timeout=1200) -> bool:
    for sel in selectors:
        if await _click_if_visible(page, sel, timeout=timeout):
            return True
    return False


async def dismiss_overlays(page, site, max_rounds=6, verbose=True) -> int:
    """Clear whatever is covering the page. Returns how many things it dismissed.
    Safe to call before ANY interaction and repeatedly — it stops as soon as a
    round changes nothing."""
    dismissed = 0
    for _ in range(max_rounds):
        acted = False
        # 1) per-site explicit dismiss + intro buttons (benign, most specific)
        site_sels = tuple(getattr(site, "dismiss_buttons", ()) or ()) + tuple(getattr(site, "intro_buttons", ()) or ())
        if await _try_each(page, site_sels):
            acted = True
        # 2) generic benign dismiss buttons
        elif await _try_each(page, _benign_selectors()):
            acted = True
        # 3) close-icon (X) buttons
        elif await _try_each(page, CLOSE_ICON_SELECTORS):
            acted = True
        # 4) a blocking overlay remains and nothing benign matched — escalate
        elif await _overlay_present(page, site):
            try:
                await page.keyboard.press("Escape")
                await page.wait_for_timeout(300)
            except Exception:  # noqa: BLE001
                pass
            if not await _overlay_present(page, site):
                acted = True                          # Escape closed it
            elif await _try_each(page, _consent_selectors(site)):
                acted = True                          # required consent/ToS
            else:
                try:                                   # last resort: click-away
                    await page.mouse.click(6, 6)
                    await page.wait_for_timeout(250)
                    acted = not await _overlay_present(page, site)
                except Exception:  # noqa: BLE001
                    acted = False
        if not acted:
            break
        dismissed += 1
        if verbose:
            try:
                print("[interact] dismissed an overlay", flush=True)
            except Exception:  # noqa: BLE001
                pass
        await page.wait_for_timeout(350)
    return dismissed


async def _composer_ready(page, composer) -> bool:
    try:
        loc = page.locator(composer).first
        return bool(await loc.count()) and await loc.is_visible()
    except Exception:  # noqa: BLE001
        return False


async def _read_composer(page, composer) -> str:
    """Current composer text (works for textarea/input value AND contenteditable)."""
    try:
        return await page.evaluate(
            """(sel) => { const e = document.querySelector(sel); if (!e) return '';
                 return (e.value !== undefined && e.value !== null) ? e.value : (e.innerText || ''); }""",
            composer,
        )
    except Exception:  # noqa: BLE001
        return ""


async def safe_fill(page, site, text: str) -> bool:
    """Put `text` into the composer, self-healing past overlays. Verifies the text
    actually landed. Branching tiers: fill → click+fill → keyboard type → JS set."""
    composer = site.composer
    probe = (text or "").strip()[:24]
    for attempt in range(4):
        await dismiss_overlays(page, site)
        try:
            await page.wait_for_selector(composer, timeout=8000, state="visible")
        except Exception:  # noqa: BLE001
            await dismiss_overlays(page, site, max_rounds=3)
            if not await _composer_ready(page, composer):
                continue
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
            if probe and probe in (got or ""):
                return True
            if not probe:                               # empty prompt: nothing to verify
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
        try:                                            # JS click fallback
            await page.evaluate(
                "(sel)=>{const b=document.querySelector(sel); if(b) b.click();}",
                site.send_button,
            )
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
