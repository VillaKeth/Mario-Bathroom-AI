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


def test_sticky_stays_until_capped():
    clk = FakeClock()
    pool = AccountPool(["a", "b", "c"], clock=clk)
    assert [pool.pick() for _ in range(3)] == ["a", "a", "a"]   # sticks on a
    pool.mark_capped("a", 100)
    assert [pool.pick() for _ in range(2)] == ["b", "b"]        # advances to b, sticks
    pool.mark_capped("b", 100)
    assert pool.pick() == "c"


def test_capped_account_is_skipped():
    clk = FakeClock()
    pool = AccountPool(["a", "b"], clock=clk)
    assert pool.pick() == "a"
    pool.mark_capped("b", 300)          # b parked
    # 'a' is the sticky current and still usable
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


def test_exclude_advances_as_refusals_grow():
    pool = AccountPool(["a", "b", "c"], clock=FakeClock())
    # 'a' refused → exclude it, get b. b refused → exclude {a,b}, get c.
    assert pool.pick(exclude={"a"}) == "b"
    assert pool.pick(exclude={"a", "b"}) == "c"
    # all excluded → None (caller fails the item: refused by everyone)
    assert pool.pick(exclude={"a", "b", "c"}) is None


def test_is_available_tracks_caps():
    clk = FakeClock()
    pool = AccountPool(["a", "b"], clock=clk)
    assert pool.is_available("a") is True
    pool.mark_capped("a", 100)
    assert pool.is_available("a") is False
    assert pool.is_available("b") is True
    clk.advance(101)
    assert pool.is_available("a") is True      # cap elapsed → free again
    assert pool.is_available("zzz") is False   # unknown account


def test_exclude_with_caps_interaction():
    clk = FakeClock()
    pool = AccountPool(["a", "b"], clock=clk)
    pool.mark_capped("b", 300)              # b capped
    # exclude a (refused) and b is capped → nothing available
    assert pool.pick(exclude={"a"}) is None
    # soonest free among non-excluded (only b) is its 300s cap
    assert pool.seconds_until_any(exclude={"a"}) == 300
    # excluding everything → 0 (nothing to wait on)
    assert pool.seconds_until_any(exclude={"a", "b"}) == 0


def test_capped_account_returns_after_reset():
    clk = FakeClock()
    pool = AccountPool(["a", "b"], clock=clk)
    pool.mark_capped("a", 60)
    assert pool.pick() == "b"      # a capped → stick on b
    assert pool.pick() == "b"      # sticky stays on b even after...
    clk.advance(61)                # ...a resets (sticky doesn't pre-empt b)
    pool.mark_capped("b", 60)      # now b caps
    assert pool.pick() == "a"      # recovered a is picked up
