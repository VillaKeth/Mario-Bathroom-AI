"""Pure account-rotation helper — no playwright import, fully unit-testable."""
import time


class AccountPool:
    """STICKY account selector over logged-in accounts.

    pick() returns the SAME account every call (one account at a time, doing
    items one-by-one) until that account is capped or explicitly excluded — then
    it advances to the next usable one. This keeps work on a single account/chat
    instead of hopping every item. A cap is recorded as a future 'available
    again' time (monotonic clock), so a capped account re-enters selection once
    its reported reset passes. `clock` is injectable for tests."""

    def __init__(self, accounts, clock=time.monotonic):
        if not accounts:
            raise ValueError("AccountPool needs at least one account")
        self.accounts = list(accounts)
        self._clock = clock
        self._cap_until = {a: 0.0 for a in self.accounts}
        self._idx = 0

    def pick(self, exclude=()):
        """Current usable account, STICKY: keeps returning the same one until it
        caps or is excluded, then advances to the next usable account. Skips
        capped accounts and any in `exclude`. Returns None if none qualify.
        `exclude` lets a caller rotate past accounts that already refused the
        current item (without capping them) — growing it forces advancement."""
        exclude = set(exclude)
        now = self._clock()
        n = len(self.accounts)
        for k in range(n):
            j = (self._idx + k) % n
            a = self.accounts[j]
            if a in exclude:
                continue
            if self._cap_until[a] <= now:
                self._idx = j      # STICK on this account (do not advance)
                return a
        return None

    def mark_capped(self, account, seconds):
        """Park `account` for `seconds` before it can be picked again."""
        self._cap_until[account] = self._clock() + max(0.0, seconds)

    def seconds_until_any(self, exclude=()):
        """Seconds until the soonest-resetting non-excluded account frees up
        (0 if one is free now; 0 if every account is excluded)."""
        exclude = set(exclude)
        now = self._clock()
        times = [t for a, t in self._cap_until.items() if a not in exclude]
        return max(0.0, min(times) - now) if times else 0.0
