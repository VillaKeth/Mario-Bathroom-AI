"""Pure helpers — no playwright import, fully unit-testable."""
import re

from mcp_chatgpt import selectors

_CONV_RE = re.compile(r"/c/([^/?#]+)")


def parse_thread_id(url: str) -> str | None:
    """Extract the ChatGPT conversation UUID from a /c/<uuid> URL, else None."""
    m = _CONV_RE.search(url or "")
    return m.group(1) if m else None


def classify_page_state(url: str, body_text: str) -> str:
    """Return one of: 'ok', 'login', 'challenge'."""
    url = url or ""
    body = body_text or ""
    if selectors.LOGIN_URL_FRAGMENT in url:
        return "login"
    if any(marker in body for marker in selectors.CHALLENGE_TEXT_MARKERS):
        return "challenge"
    return "ok"
