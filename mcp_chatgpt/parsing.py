"""Pure helpers — no playwright import, fully unit-testable."""
import re

_CONV_RE = re.compile(r"/c/([^/?#]+)")


def parse_thread_id(url: str) -> str | None:
    """Extract the ChatGPT conversation UUID from a /c/<uuid> URL, else None."""
    m = _CONV_RE.search(url or "")
    return m.group(1) if m else None


def classify_page_state(url: str, body_text: str, site) -> str:
    """Return one of: 'ok', 'login', 'challenge'. `site` is a sites.Site."""
    url = url or ""
    body = body_text or ""
    if site.login_url_fragment in url:
        return "login"
    if any(marker in body for marker in site.challenge_text_markers):
        return "challenge"
    return "ok"


_DUR_PART = re.compile(r"(\d+)\s*(hour|minute|second)s?", re.I)
_RESET_CLOCK = re.compile(r"\b(\d{1,2}):(\d{2})(?::(\d{2}))?\b")
_MULT = {"hour": 3600, "minute": 60, "second": 1}


def parse_reset_seconds(text: str) -> int | None:
    """Best-effort wait-seconds from a cap message. Handles single AND COMPOUND
    durations — 'try again in 12 minutes', 'in 30 seconds', 'in 2 hours', and
    'the limit resets in 5 hours and 51 minutes' (sums every part so we don't
    resume early) — plus an mm:ss / h:mm:ss countdown. Returns None if nothing
    parseable (caller falls back to a default)."""
    t = text or ""
    parts = _DUR_PART.findall(t)
    if parts:
        total = sum(int(n) * _MULT[u.lower()] for n, u in parts)
        if total > 0:
            return total
    m = _RESET_CLOCK.search(t)
    if m:
        a, b, c = m.group(1), m.group(2), m.group(3)
        return int(a) * 3600 + int(b) * 60 + int(c) if c else int(a) * 60 + int(b)
    return None
