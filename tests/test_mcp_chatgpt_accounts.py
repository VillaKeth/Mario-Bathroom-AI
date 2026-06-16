import pytest

from mcp_chatgpt.rotation import AccountPool


class FakeClock:
    """Manually advanceable monotonic clock for deterministic tests."""
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t

    def advance(self, secs):
        self.t += secs


def test_empty_accounts_rejected():
    with pytest.raises(ValueError):
        AccountPool([])


def test_round_robin_spreads_load():
    pool = AccountPool(["a", "b", "c"], clock=FakeClock())
    assert [pool.pick() for _ in range(6)] == ["a", "b", "c", "a", "b", "c"]


def test_capped_account_is_skipped():
    clk = FakeClock()
    pool = AccountPool(["a", "b"], clock=clk)
    assert pool.pick() == "a"
    pool.mark_capped("b", 300)          # b parked
    # only 'a' is available now, even though rotation would prefer 'b' next
    assert pool.pick() == "a"
    assert pool.pick() == "a"


def test_all_capped_returns_none_then_recovers():
    clk = FakeClock()
    pool = AccountPool(["a", "b"], clock=clk)
    pool.mark_capped("a", 100)
    pool.mark_capped("b", 250)
    assert pool.pick() is None
    # soonest reset is a's 100s
    assert pool.seconds_until_any() == 100
    clk.advance(120)                    # past a's reset, before b's
    assert pool.pick() == "a"
    assert pool.seconds_until_any() == 0  # a is free now


def test_reset_buffer_then_back_in_rotation():
    clk = FakeClock()
    pool = AccountPool(["a", "b"], clock=clk)
    pool.mark_capped("a", 60)
    # b still serves while a is parked
    assert pool.pick() == "b"
    assert pool.pick() == "b"
    clk.advance(61)
    # a is back; rotation includes it again
    got = {pool.pick() for _ in range(4)}
    assert got == {"a", "b"}
