import datetime
import logging
import logging.handlers
import os
import time

from shared import file_logging
from shared.file_logging import DayFolderHandler, _PlainFormatter


def _record(msg, name="x", level=logging.INFO):
    return logging.LogRecord(name, level, __file__, 1, msg, None, None)


def test_handler_writes_to_dated_source_file(tmp_path):
    h = DayFolderHandler("conversation", str(tmp_path))
    h.setFormatter(_PlainFormatter())
    h.emit(_record("hello there"))
    h.close()
    day = datetime.datetime.now().strftime("%Y-%m-%d")
    f = tmp_path / day / "conversation.log"
    assert f.exists()
    assert "hello there" in f.read_text(encoding="utf-8")


def test_handler_rolls_over_on_new_day(tmp_path):
    clock = {"t": datetime.datetime(2026, 7, 1, 23, 59, 0)}
    h = DayFolderHandler("tts", str(tmp_path), now_fn=lambda: clock["t"])
    h.setFormatter(_PlainFormatter())
    h.emit(_record("late on day one"))
    clock["t"] = datetime.datetime(2026, 7, 2, 0, 1, 0)
    h.emit(_record("early on day two"))
    h.close()
    assert (tmp_path / "2026-07-01" / "tts.log").exists()
    assert (tmp_path / "2026-07-02" / "tts.log").exists()
    assert "late on day one" in (tmp_path / "2026-07-01" / "tts.log").read_text(encoding="utf-8")
    assert "early on day two" in (tmp_path / "2026-07-02" / "tts.log").read_text(encoding="utf-8")


def test_plain_formatter_shape():
    fmt = _PlainFormatter()
    line = fmt.format(_record("msg body"))
    # 2026-07-01@22:14:03.120  msg body
    import re
    assert re.match(r"^\d{4}-\d{2}-\d{2}@\d{2}:\d{2}:\d{2}\.\d{3}  msg body$", line)


def test_records_route_to_correct_source_file(tmp_path):
    handle = file_logging.init_file_logging(str(tmp_path), {"enabled": True, "level": "INFO"})
    try:
        logging.getLogger("tts_router").info("sovits synth ok")
        logging.getLogger("llm_router").info("routed to fast model")
        logging.getLogger("memory").warning("qdrant slow")
        time.sleep(0.2)  # let the listener thread drain
    finally:
        file_logging.shutdown_file_logging(handle)
    day = datetime.datetime.now().strftime("%Y-%m-%d")
    tts = (tmp_path / day / "tts.log").read_text(encoding="utf-8")
    llm = (tmp_path / day / "llm.log").read_text(encoding="utf-8")
    errors = (tmp_path / day / "errors.log").read_text(encoding="utf-8")
    assert "sovits synth ok" in tts
    assert "routed to fast model" in llm
    assert "sovits synth ok" not in llm          # no cross-contamination
    assert "qdrant slow" in errors                # WARNING aggregated to errors.log


def test_disabled_config_is_noop(tmp_path):
    handle = file_logging.init_file_logging(str(tmp_path), {"enabled": False})
    assert handle == {}
    logging.getLogger("tts_router").info("should not be written")
    assert not any(tmp_path.iterdir())


def test_shutdown_removes_queue_handler_from_root(tmp_path):
    # Regression guard: init_file_logging attaches a QueueHandler to the root
    # logger; shutdown_file_logging must remove it, or repeated init/shutdown
    # cycles (as happens across the test suite) pile up dead QueueHandlers on
    # the root logger and pollute later tests.
    root = logging.getLogger()
    before = [h for h in root.handlers if isinstance(h, logging.handlers.QueueHandler)]

    handle = file_logging.init_file_logging(str(tmp_path), {"enabled": True, "level": "INFO"})
    during = [h for h in root.handlers if isinstance(h, logging.handlers.QueueHandler)]
    assert len(during) == len(before) + 1
    assert handle["qhandler"] in during

    file_logging.shutdown_file_logging(handle)
    after = [h for h in root.handlers if isinstance(h, logging.handlers.QueueHandler)]
    assert after == before
