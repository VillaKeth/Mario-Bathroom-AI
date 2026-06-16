"""Pure account-rotation helper — no playwright import, fully unit-testable."""
import time


class AccountPool:
    """Round-robin over logged-in accounts, skipping any currently capped.

    A cap is recorded as a future 'available again' time (monotonic clock), so
    a capped account re-enters rotation automatically once its reported reset
    passes. Spreading generations across N accounts also delays hitting any
    single account's cap. `clock` is injectable for tests."""

    def __init__(self, accounts, clock=time.monotonic):
        if not accounts:
            raise ValueError("AccountPool needs at least one account")
        self.accounts = list(accounts)
        self._clock = clock
        self._cap_until = {a: 0.0 for a in self.accounts}
        self._idx = 0

    def pick(self, exclude=()):
        """Next available account (round-robin), skipping capped ones and any in
        `exclude`. Returns None if none qualify. `exclude` lets a caller rotate
        past accounts that already refused the current item (without capping them)."""
        exclude = set(exclude)
        now = self._clock()
        n = len(self.accounts)
        for k in range(n):
            j = (self._idx + k) % n
            a = self.accounts[j]
            if a in exclude:
                continue
            if self._cap_until[a] <= now:
                self._idx = (j + 1) % n      # advance so the next pick rotates on
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
