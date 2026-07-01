"""Day-by-day, per-source file logging shared by the server and pygame client.

Layout:  logs/YYYY-MM-DD/{source}.log   (one file per source, per local day)
Format:  2026-07-01@22:14:03.120  message
See docs/superpowers/specs/2026-07-01-file-logging-design.md
"""
import datetime
import logging
import logging.handlers
import os
import queue

CONV_LOGGER = "mario.conversation"


class _PlainFormatter(logging.Formatter):
    """WellnessSpace-style plaintext line with millisecond timestamp."""

    def format(self, record):
        ct = datetime.datetime.fromtimestamp(record.created)
        stamp = ct.strftime("%Y-%m-%d@%H:%M:%S.") + f"{int(record.msecs):03d}"
        return f"{stamp}  {record.getMessage()}"


class DayFolderHandler(logging.Handler):
    """Writes each record to logs/<local-day>/<source>.log, reopening the file
    when the local calendar day changes (WellnessSpace's check_rotate pattern,
    adapted to folder-per-day + file-per-source)."""

    def __init__(self, source, root_dir, now_fn=datetime.datetime.now):
        super().__init__()
        self.source = source
        self.root_dir = root_dir
        self._now_fn = now_fn
        self._day = None
        self._fh = None

    def _ensure_open(self):
        day = self._now_fn().strftime("%Y-%m-%d")
        if day != self._day:
            if self._fh:
                self._fh.close()
            folder = os.path.join(self.root_dir, day)
            os.makedirs(folder, exist_ok=True)
            self._fh = open(os.path.join(folder, f"{self.source}.log"), "a", encoding="utf-8")
            self._day = day

    def emit(self, record):
        try:
            self._ensure_open()
            self._fh.write(self.format(record) + "\n")
            self._fh.flush()
        except Exception:
            self.handleError(record)

    def close(self):
        try:
            if self._fh:
                self._fh.close()
                self._fh = None
        finally:
            super().close()
