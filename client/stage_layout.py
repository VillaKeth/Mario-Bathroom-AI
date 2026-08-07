"""Pure layout math for group-mode stage rendering (no pygame).

The active speaker keeps the normal center-stage draw; the rest of the cast
("bystanders") flank them — left and right groups, outside-in. These helpers
return pixel x-centers so mario_display just blits.
"""

# Bystander groups live in these horizontal bands (fractions of window width).
_LEFT_BAND = (0.10, 0.32)
_RIGHT_BAND = (0.68, 0.90)


def _spread(count: int, lo: float, hi: float) -> list:
    """Evenly place `count` points across [lo, hi]; a single point centers."""
    if count <= 0:
        return []
    if count == 1:
        return [(lo + hi) / 2.0]
    step = (hi - lo) / (count - 1)
    return [lo + i * step for i in range(count)]


def bystander_slots(n: int, window_w: int) -> list:
    """Pixel x-centers for n bystanders: left group first, then right group.
    Odd counts put the extra member on the left."""
    if n <= 0 or window_w <= 0:
        return []
    left = (n + 1) // 2
    right = n // 2
    fracs = _spread(left, *_LEFT_BAND) + _spread(right, *_RIGHT_BAND)
    return [int(f * window_w) for f in fracs]


def bystander_order(roster_ids: list, active_id) -> list:
    """Stable draw order: everyone but the active speaker, roster order kept
    (so members don't shuffle slots every time the speaker changes)."""
    return [cid for cid in roster_ids if cid != active_id]
