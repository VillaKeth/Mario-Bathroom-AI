"""Unit tests for the self-healing browser-interaction engine (mcp_chatgpt/interact.py).

Only the PURE logic is covered here — button classification and the layered
selector catalogs. The live overlay dismissal + fallback chains need a real
Playwright page and are exercised against the running providers in integration.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mcp_chatgpt"))

import interact as I  # noqa: E402


def test_avoid_blocks_money_and_upsell():
    for t in ("Upgrade to Plus", "Subscribe now", "Start free trial", "Buy credits",
              "Go Pro", "Add payment method", "See plans", "Checkout"):
        assert I._is_avoid(t), t
    for t in ("No thanks", "Not now", "Accept all", "Close", "Dismiss", "Got it"):
        assert not I._is_avoid(t), t


def test_benign_selectors_cover_common_nags():
    joined = " ".join(I._benign_selectors()).lower()
    for phrase in ("no thanks", "not now", "dismiss", "close", "maybe later", "skip"):
        assert phrase in joined


def test_consent_selectors_layer_site_specific_over_generic():
    class FakeSite:
        consent_buttons = ("button:has-text('Custom Accept')",)

    sels = I._consent_selectors(FakeSite())
    assert sels[0] == "button:has-text('Custom Accept')"       # site-specific first
    assert any("i agree" in s.lower() for s in sels)           # generic still present


def test_consent_selectors_survive_missing_field():
    class Bare:
        pass
    # getattr fallback: a site without consent_buttons must not crash
    assert any("agree" in s.lower() for s in I._consent_selectors(Bare()))


def test_overlay_and_close_selector_catalogs():
    assert any("dialog" in s for s in I.OVERLAY_SELECTORS)
    assert any("aria-modal" in s for s in I.OVERLAY_SELECTORS)
    assert any("close" in s.lower() for s in I.CLOSE_ICON_SELECTORS)


def test_norm_handles_none_and_whitespace():
    assert I._norm(None) == ""
    assert I._norm("  Hi There ") == "hi there"


def test_site_name_extracts_provider_from_url():
    class G:
        url = "https://grok.com/"

    class Bad:
        url = ""

    assert I.site_name(G()) == "grok"
    assert I.site_name(Bad()) == "site"


def test_advanced_surface_present():
    # The advanced engine must expose occlusion detection, heuristic scan, the
    # throttled mid-generation sweep, diagnostics, and the safe_* ladder.
    for name in ("occlusion", "sweep_light", "dismiss_overlays", "_scan_and_click",
                 "_capture_stuck", "safe_fill", "safe_send", "safe_click"):
        assert hasattr(I, name), name


def test_scan_js_capabilities():
    # The heuristic scorer must be money-safe: AVOID terms drive its disqualifier.
    assert "upgrade" in I.AVOID and "subscribe" in I.AVOID and "start free trial" in I.AVOID
    js = I._JS_SCAN_DISMISS
    assert "avoid" in js and "assumePopup" in js      # money-safe + iframe-as-popup
    assert "shadowRoot" in js                          # shadow-DOM-aware
    assert "inPopup" in js                             # popup-context gating (no clean-page misfire)
    assert "elementFromPoint" in I._JS_OCCLUSION       # occlusion uses real hit-testing
