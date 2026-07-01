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


def test_shutdown_restores_root_logger_level(tmp_path):
    # init_file_logging lowers the root logger's level so records reach the queue;
    # shutdown_file_logging must restore the prior level, or repeated init/shutdown
    # cycles ratchet the whole pytest session down toward INFO and silently change
    # how later tests capture logs. We force a known starting level (WARNING) that
    # init will actively lower, so the restore is genuinely exercised regardless of
    # the order this test runs in.
    root = logging.getLogger()
    original = root.level
    root.setLevel(logging.WARNING)
    try:
        before = root.level
        handle = file_logging.init_file_logging(str(tmp_path), {"enabled": True})
        assert root.level <= logging.INFO  # init lowered it so INFO records get through
        file_logging.shutdown_file_logging(handle)
        assert root.level == before        # restored to exactly what it was before init
    finally:
        root.setLevel(original)


def test_include_sources_client_routes_only_to_client_log(tmp_path):
    # Client process path: include_sources=["client"] must build ONLY the catch-all
    # client.log handler (everything on the root logger), and NOT any server-side
    # per-source handler like llm.log.
    handle = file_logging.init_file_logging(
        str(tmp_path), {"enabled": True}, include_sources=["client"]
    )
    try:
        logging.getLogger().warning("client-only record")
        time.sleep(0.2)  # let the listener thread drain
    finally:
        file_logging.shutdown_file_logging(handle)
    day = datetime.datetime.now().strftime("%Y-%m-%d")
    client_log = tmp_path / day / "client.log"
    assert client_log.exists()
    assert "client-only record" in client_log.read_text(encoding="utf-8")
    assert not (tmp_path / day / "llm.log").exists()  # no server-side source file


def test_console_level_raises_existing_stream_handler(tmp_path):
    # console_level should raise the threshold of pre-existing console StreamHandlers
    # (so the terminal stays quiet) without touching the file handlers behind the queue.
    root = logging.getLogger()
    sh = logging.StreamHandler()
    sh.setLevel(logging.INFO)
    root.addHandler(sh)
    handle = None
    try:
        handle = file_logging.init_file_logging(
            str(tmp_path), {"enabled": True}, console_level="WARNING"
        )
        assert sh.level == logging.WARNING
    finally:
        root.removeHandler(sh)
        if handle is not None:
            file_logging.shutdown_file_logging(handle)


def test_conversation_helpers_write_chipped_lines(tmp_path):
    file_logging.set_character("rudi")
    handle = file_logging.init_file_logging(
        str(tmp_path), {"enabled": True, "sources": {"conversation": True, "errors": True}})
    try:
        file_logging.log_guest("Jacob", "hey rudi you awake?")
        file_logging.log_guest(None, "anyone there")
        file_logging.log_bot("Ohh you know it!")
        file_logging.log_bot("just me mumbling", is_idle=True)
        file_logging.log_bot("")  # empty is ignored
        time.sleep(0.2)
    finally:
        file_logging.shutdown_file_logging(handle)
        file_logging.set_character("mario")
    day = datetime.datetime.now().strftime("%Y-%m-%d")
    conv = (tmp_path / day / "conversation.log").read_text(encoding="utf-8")
    assert "[guest:Jacob] hey rudi you awake?" in conv
    assert "[guest] anyone there" in conv
    assert "[rudi] Ohh you know it!" in conv
    assert "[rudi:idle] just me mumbling" in conv
    assert conv.count("\n") == 4  # empty log_bot produced no line


def test_probe_writable_true_for_tmp(tmp_path):
    assert file_logging.probe_writable(str(tmp_path / "logs")) is True


def test_probe_writable_false_for_bad_path(tmp_path):
    bad = tmp_path / "afile"
    bad.write_text("x", encoding="utf-8")
    # A path under a regular file cannot be a directory.
    assert file_logging.probe_writable(str(bad / "sub")) is False


def test_handler_reopens_after_close(tmp_path):
    h = DayFolderHandler("system", str(tmp_path))
    h.setFormatter(_PlainFormatter())
    h.emit(_record("first line"))
    h.close()                       # simulates the mid-run close that caused the crash
    h.emit(_record("second line"))  # must self-heal and write, not raise/lose it
    day = datetime.datetime.now().strftime("%Y-%m-%d")
    content = (tmp_path / day / "system.log").read_text(encoding="utf-8")
    assert "first line" in content
    assert "second line" in content
    h.close()
