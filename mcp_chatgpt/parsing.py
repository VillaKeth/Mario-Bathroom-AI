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


_RESET_IN = re.compile(r"in\s+(\d+)\s*(second|minute|hour)s?", re.I)
_RESET_CLOCK = re.compile(r"\b(\d{1,2}):(\d{2})(?::(\d{2}))?\b")


def parse_reset_seconds(text: str) -> int | None:
    """Best-effort wait-seconds from a cap message: 'try again in 12 minutes',
    'in 30 seconds', 'in 2 hours', or an mm:ss / h:mm:ss countdown. Returns None
    if nothing parseable (caller falls back to a default)."""
    t = text or ""
    m = _RESET_IN.search(t)
    if m:
        return int(m.group(1)) * {"second": 1, "minute": 60, "hour": 3600}[m.group(2).lower()]
    m = _RESET_CLOCK.search(t)
    if m:
        a, b, c = m.group(1), m.group(2), m.group(3)
        return int(a) * 3600 + int(b) * 60 + int(c) if c else int(a) * 60 + int(b)
    return None
