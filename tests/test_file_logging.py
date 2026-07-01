import datetime
import logging
import os

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
