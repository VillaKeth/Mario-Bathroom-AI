"""Pure helpers for the scrollable visual-novel chat backlog.

No pygame / no sibling imports, so they're unit-testable in isolation.
Consumed by client/mario_display.py's full-screen chat-log overlay.
"""


def _clamp_chat_scroll(offset, total_lines, viewport_lines):
    """Clamp a scroll offset (lines scrolled UP from the bottom) to a valid range.

    0 = stuck to the newest line; max = the oldest line scrolled into view.
    When everything fits (total <= viewport) the only valid offset is 0.
    """
    max_off = max(0, int(total_lines) - int(viewport_lines))
    return max(0, min(int(offset), max_off))


def _wrap_text(text, max_chars):
    """Word-wrap text to <= max_chars per line, hard-splitting overlong words.

    Always returns at least one (possibly empty) line so a blank message still
    occupies a row in the log.
    """
    if max_chars < 1:
        max_chars = 1
    words = str(text).split()
    if not words:
        return [""]
    lines = []
    cur = ""
    for w in words:
        # A single word wider than the line gets hard-split across rows.
        while len(w) > max_chars:
            if cur:
                lines.append(cur)
                cur = ""
            lines.append(w[:max_chars])
            w = w[max_chars:]
        if not cur:
            cur = w
        elif len(cur) + 1 + len(w) <= max_chars:
            cur += " " + w
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines or [""]
