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
        out = f"{stamp}  {record.getMessage()}"
        if record.exc_info and not record.exc_text:
            record.exc_text = self.formatException(record.exc_info)
        if record.exc_text:
            out += "\n" + record.exc_text
        if record.stack_info:
            out += "\n" + self.formatStack(record.stack_info)
        return out


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
        if self._fh is None or day != self._day:
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
        except Exception:
            pass
        finally:
            self._fh = None
            self._day = None
            super().close()


SOURCE_LOGGERS = {
    "conversation": {CONV_LOGGER},
    "llm": {"llm_router", "llm"},
    "tts": {"tts", "tts_router", "gpt_sovits_server", "fish_speech_tts"},
    "memory": {"memory", "memory_semantic", "party_gossip", "vip_knowledge"},
    "events": {"game_handlers", "idle_behavior", "night_progression", "emotions", "birthday_vip"},
    "system": {"mario-server", "mario-client", "watchdog", "canary", "hardware", "hot_reload", "dashboard"},
    # "errors" and "client" are special-cased in init_file_logging.
}


class _NameFilter(logging.Filter):
    def __init__(self, names):
        super().__init__()
        self.names = set(names)

    def filter(self, record):
        return record.name in self.names


class _ErrorFilter(logging.Filter):
    def filter(self, record):
        return record.levelno >= logging.WARNING and record.name != CONV_LOGGER


def _make_handler(source, root_dir, flt):
    h = DayFolderHandler(source, root_dir)
    h.setFormatter(_PlainFormatter())
    h.addFilter(flt)
    return h


def init_file_logging(root_dir, config, *, include_sources=None, console_level=None):
    if not isinstance(config, dict):
        config = {}
    if not config.get("enabled", True):
        return {}
    root_dir = os.path.abspath(root_dir)
    enabled = config.get("sources", {})
    handlers = []

    def want(src):
        if include_sources is not None:
            return src in include_sources
        return enabled.get(src, True)

    for source, names in SOURCE_LOGGERS.items():
        if want(source):
            handlers.append(_make_handler(source, root_dir, _NameFilter(names)))
    if want("errors"):
        handlers.append(_make_handler("errors", root_dir, _ErrorFilter()))
    if include_sources and "client" in include_sources:
        # Client process: everything on its root logger goes to client.log.
        handlers.append(_make_handler("client", root_dir, logging.Filter()))

    q = queue.Queue(-1)
    listener = logging.handlers.QueueListener(q, *handlers, respect_handler_level=True)
    listener.start()

    root = logging.getLogger()
    prev_level = root.level
    level = getattr(logging, str(config.get("level", "INFO")).upper(), logging.INFO)
    root.setLevel(min(root.level or logging.INFO, level))
    qh = logging.handlers.QueueHandler(q)
    root.addHandler(qh)

    if console_level is not None:
        lvl = getattr(logging, str(console_level).upper(), logging.WARNING)
        for h in root.handlers:
            if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.handlers.QueueHandler):
                h.setLevel(lvl)

    return {"queue": q, "listener": listener, "handlers": handlers, "qhandler": qh, "prev_level": prev_level}


def shutdown_file_logging(handle):
    if not handle:
        return
    qh = handle.get("qhandler")
    if qh is not None:
        logging.getLogger().removeHandler(qh)
    if "prev_level" in handle:
        logging.getLogger().setLevel(handle["prev_level"])
    try:
        handle["listener"].stop()
    finally:
        for h in handle.get("handlers", []):
            try:
                h.close()
            except Exception:
                pass


_CHARACTER_NAME = "mario"


def set_character(name, display_name=None):
    global _CHARACTER_NAME
    if name:
        _CHARACTER_NAME = str(name).lower()


def get_conversation_logger():
    return logging.getLogger(CONV_LOGGER)


def log_guest(name, text):
    if not text:
        return
    chip = f"[guest:{name}]" if name else "[guest]"
    get_conversation_logger().info(f"{chip} {text}")


def log_bot(text, is_idle=False):
    if not text:
        return
    chip = f"[{_CHARACTER_NAME}:idle]" if is_idle else f"[{_CHARACTER_NAME}]"
    get_conversation_logger().info(f"{chip} {text}")


def probe_writable(root_dir):
    """Canary/startup check: can we create the log root and write to it?"""
    try:
        root_dir = os.path.abspath(root_dir)
        os.makedirs(root_dir, exist_ok=True)
        probe = os.path.join(root_dir, ".write_probe")
        with open(probe, "w", encoding="utf-8") as f:
            f.write("ok")
        os.remove(probe)
        return True
    except Exception:
        return False
