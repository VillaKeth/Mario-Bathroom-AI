import logging
from server.debug_ring import LogRing


def test_ring_caps_and_snapshots_newest_last():
    ring = LogRing(maxlen=3)
    for i in range(5):
        ring.append(f"line{i}", level="INFO")
    snap = ring.snapshot()
    assert [l["msg"] for l in snap] == ["line2", "line3", "line4"]


def test_grep_filter_is_case_insensitive():
    ring = LogRing(maxlen=10)
    ring.append("Sovits started", level="INFO")
    ring.append("edge fallback", level="WARNING")
    assert [l["msg"] for l in ring.snapshot(grep="SOVITS")] == ["Sovits started"]


def test_level_filter_minimum_severity():
    ring = LogRing(maxlen=10)
    ring.append("debugging", level="DEBUG")
    ring.append("a warning", level="WARNING")
    out = ring.snapshot(level="WARNING")
    assert [l["msg"] for l in out] == ["a warning"]


def test_handler_feeds_ring():
    ring = LogRing(maxlen=10)
    logger = logging.getLogger("test_feed")
    logger.setLevel(logging.INFO)
    logger.addHandler(ring.handler())
    logger.info("hello from logger")
    assert any("hello from logger" in l["msg"] for l in ring.snapshot())
