# File Logging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Day-by-day, per-source file logging so Rudi/Mario can run overnight and the operator can later read exactly what was said, plus client perf fixes.

**Architecture:** A new shared module `shared/file_logging.py` provides a `DayFolderHandler` (one file per source under `logs/YYYY-MM-DD/`) fanned out behind a non-blocking `QueueHandler`/`QueueListener`. Diagnostic records auto-route by logger name (zero edits to existing call sites); the conversation transcript is written by explicit `log_guest`/`log_bot` helpers hooked into the two existing choke points (`_log_guest_turn`, `send_response`). The pygame client writes its own `client.log` and caps its on-screen chat history.

**Tech Stack:** Python 3, stdlib `logging` (`QueueHandler`, `QueueListener`, custom `Handler`/`Formatter`/`Filter`), pytest.

## Global Constraints

- Design doc: `docs/superpowers/specs/2026-07-01-file-logging-design.md` (source of truth).
- `print()` is the house logging style in some modules, but this feature uses stdlib `logging`; do not convert existing `print()` calls.
- WebSocket response message type stays `"mario_response"`.
- No ellipsis (`...`) in TTS-bound strings — N/A here (log files are not spoken), but keep log chips ASCII.
- Git: `git add <specific files>` only (never `git add -A`) — Qdrant `.lock` files must never be committed.
- Commit trailer: `Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>`.
- Modules with user-visible text expose `set_character(name, display_name)` + `_CHARACTER_NAME` fallback — the conversation helper follows this.
- Branch `feat/file-logging` is already checked out with the spec committed.
- Line format everywhere: `YYYY-MM-DD@HH:MM:SS.mmm␠␠message` (two spaces before message).
- Day = **local** calendar day. Keep-forever retention (no cleanup code).
- Tests import project modules as `from shared.X import ...` / `from server.X import ...` / `from client.X import ...` (project root is on `sys.path` under pytest).

---

### Task 1: `DayFolderHandler` + plaintext formatter

**Files:**
- Create: `shared/file_logging.py`
- Test: `tests/test_file_logging.py`

**Interfaces:**
- Produces: `class DayFolderHandler(logging.Handler)` with `__init__(self, source: str, root_dir: str, now_fn=datetime.datetime.now)`; writes `{root_dir}/{YYYY-MM-DD}/{source}.log`, one formatted line per record, reopening the file when the local day changes. `class _PlainFormatter(logging.Formatter)` producing `YYYY-MM-DD@HH:MM:SS.mmm␠␠message`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_file_logging.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_file_logging.py -v`
Expected: FAIL with `ImportError: cannot import name 'DayFolderHandler' from 'shared.file_logging'` (module does not exist yet).

- [ ] **Step 3: Create `shared/file_logging.py` with the handler + formatter**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_file_logging.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add shared/file_logging.py tests/test_file_logging.py
git commit -m "feat(logging): DayFolderHandler + plaintext formatter

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 2: Name-based routing + non-blocking init/shutdown

**Files:**
- Modify: `shared/file_logging.py`
- Test: `tests/test_file_logging.py`

**Interfaces:**
- Consumes: `DayFolderHandler`, `_PlainFormatter`, `CONV_LOGGER` (Task 1).
- Produces:
  - `SOURCE_LOGGERS: dict[str, set[str]]` — source name → logger names.
  - `init_file_logging(root_dir, config, *, include_sources=None, console_level=None) -> dict` — resolves `root_dir` absolute, builds one `DayFolderHandler` per enabled source (each with its name/level filter + `_PlainFormatter`), starts a `QueueListener`, attaches one `QueueHandler` to the root logger, optionally raises existing `StreamHandler`s to `console_level`. Returns a handle dict `{"queue","listener","handlers"}`. No-op returning `{}` when `config.get("enabled", True)` is false.
  - `shutdown_file_logging(handle)` — stops the listener (flushes queue) and closes handlers.

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_file_logging.py
import time
from shared import file_logging


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_file_logging.py -k "route or noop" -v`
Expected: FAIL with `AttributeError: module 'shared.file_logging' has no attribute 'init_file_logging'`.

- [ ] **Step 3: Add routing map, filters, init/shutdown to `shared/file_logging.py`**

```python
# --- add below the handler class ---

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
    level = getattr(logging, str(config.get("level", "INFO")).upper(), logging.INFO)
    root.setLevel(min(root.level or logging.INFO, level))
    root.addHandler(logging.handlers.QueueHandler(q))

    if console_level is not None:
        lvl = getattr(logging, str(console_level).upper(), logging.WARNING)
        for h in root.handlers:
            if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.handlers.QueueHandler):
                h.setLevel(lvl)

    return {"queue": q, "listener": listener, "handlers": handlers}


def shutdown_file_logging(handle):
    if not handle:
        return
    try:
        handle["listener"].stop()
    finally:
        for h in handle.get("handlers", []):
            try:
                h.close()
            except Exception:
                pass
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_file_logging.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add shared/file_logging.py tests/test_file_logging.py
git commit -m "feat(logging): name-based routing + non-blocking queue init/shutdown

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 3: Conversation helpers + `set_character`

**Files:**
- Modify: `shared/file_logging.py`
- Test: `tests/test_file_logging.py`

**Interfaces:**
- Consumes: `CONV_LOGGER`, `init_file_logging`, `shutdown_file_logging` (Tasks 1-2).
- Produces:
  - `_CHARACTER_NAME` (module global, default `"mario"`) and `set_character(name, display_name=None)`.
  - `log_guest(name, text)` → writes `[guest:Name] text` (or `[guest] text`) to `conversation.log`.
  - `log_bot(text, is_idle=False)` → writes `[<char>] text` (or `[<char>:idle] text`) to `conversation.log`.

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_file_logging.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_file_logging.py -k conversation_helpers -v`
Expected: FAIL with `AttributeError: module 'shared.file_logging' has no attribute 'set_character'`.

- [ ] **Step 3: Add helpers to `shared/file_logging.py`**

```python
# --- add at the bottom ---

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
```

- [ ] **Step 4: Run the full module test to verify it passes**

Run: `python -m pytest tests/test_file_logging.py -v`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add shared/file_logging.py tests/test_file_logging.py
git commit -m "feat(logging): conversation transcript helpers + set_character

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 4: Config block + `.gitignore`

**Files:**
- Modify: `config.json`
- Modify: `.gitignore`

**Interfaces:**
- Produces: a `config["logging"]` block consumed by the server (Task 5) and client (Tasks 6-7).

- [ ] **Step 1: Add the `logging` block to `config.json`**

Insert as a new top-level key (sibling of `"mirror"`, before `"mode"`). Change the `"mirror": { ... },` block's trailing lines so the new block follows it:

```json
  "logging": {
    "enabled": true,
    "root_dir": "logs",
    "level": "INFO",
    "sources": {
      "conversation": true, "llm": true, "tts": true, "memory": true,
      "events": true, "system": true, "errors": true, "client": true
    },
    "client_console_level": "WARNING",
    "chat_overlay_max": 40
  },
  "mode": "single",
  "group": "tadc"
}
```

- [ ] **Step 2: Verify config still parses**

Run: `python -c "import json; json.load(open('config.json', encoding='utf-8')); print('ok')"`
Expected: `ok`

- [ ] **Step 3: Ignore the logs directory**

Add to `.gitignore` (create the file if it is absent):

```
# Overnight run logs (day-by-day per-source)
logs/
```

- [ ] **Step 4: Verify the ignore works**

Run: `mkdir -p logs/2026-07-01 && echo test > logs/2026-07-01/conversation.log && git status --porcelain logs/`
Expected: no output (the `logs/` path is ignored).

- [ ] **Step 5: Commit**

```bash
git add config.json .gitignore
git commit -m "chore(logging): add logging config block and gitignore logs/

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 5: Server wiring (init, transcript hooks, shutdown, writability probe)

**Files:**
- Modify: `shared/file_logging.py` (add `probe_writable`)
- Modify: `server/main.py` (init + `set_character` + `atexit` shutdown ~after line 126; `log_guest` in `_log_guest_turn` ~line 2096; `log_bot` in `send_response` ~line 6785)
- Test: `tests/test_file_logging.py`

**Interfaces:**
- Consumes: `init_file_logging`, `shutdown_file_logging`, `set_character`, `log_guest`, `log_bot` (Tasks 1-3).
- Produces: `probe_writable(root_dir) -> bool` (creates the dir, writes+deletes a temp file; returns success). Server transcript now lands in `conversation.log`.

- [ ] **Step 1: Write the failing test for `probe_writable`**

```python
# append to tests/test_file_logging.py
def test_probe_writable_true_for_tmp(tmp_path):
    assert file_logging.probe_writable(str(tmp_path / "logs")) is True


def test_probe_writable_false_for_bad_path(tmp_path):
    bad = tmp_path / "afile"
    bad.write_text("x", encoding="utf-8")
    # A path under a regular file cannot be a directory.
    assert file_logging.probe_writable(str(bad / "sub")) is False
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_file_logging.py -k probe -v`
Expected: FAIL with `AttributeError: ... 'probe_writable'`.

- [ ] **Step 3: Add `probe_writable` to `shared/file_logging.py`**

```python
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
```

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/test_file_logging.py -k probe -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Wire init + character + shutdown into `server/main.py`**

Immediately after line 126 (`server_config = config.get("server", {})`), add:

```python
# --- File logging: day-by-day per-source logs under logs/<day>/ (see
# docs/superpowers/specs/2026-07-01-file-logging-design.md) ---
import atexit
from shared import file_logging as _file_logging
_LOG_CONFIG = config.get("logging", {})
_LOG_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         _LOG_CONFIG.get("root_dir", "logs"))
_file_logging.set_character(config.get("character", "mario"))
if _LOG_CONFIG.get("enabled", True) and not _file_logging.probe_writable(_LOG_ROOT):
    logger.warning(f"[LOGGING] log root not writable: {_LOG_ROOT} — file logs disabled")
    _LOG_CONFIG = {"enabled": False}
_LOG_HANDLE = _file_logging.init_file_logging(_LOG_ROOT, _LOG_CONFIG)
atexit.register(_file_logging.shutdown_file_logging, _LOG_HANDLE)
```

- [ ] **Step 6: Hook `log_guest` into `_log_guest_turn`**

In `server/main.py`, inside `_log_guest_turn` (line 2090), right after the `if not text: return` guard (line 2096), add:

```python
    try:
        _file_logging.log_guest(name, text)
    except Exception:
        pass
```

- [ ] **Step 7: Hook `log_bot` into `send_response`**

In `server/main.py`, inside `send_response` (line 6773), right after the docstring / before the `if sound:` block (~line 6785), add (dedupes streamed replies — logs the complete reply once, on the non-chunked send or the first chunk):

```python
    if chunk_index is None or chunk_index == 0:
        try:
            _file_logging.log_bot(full_text if full_text is not None else text, is_idle=is_idle)
        except Exception:
            pass
```

- [ ] **Step 8: Verify no import/syntax regressions and the suite still passes**

Run: `python -c "import ast; ast.parse(open('server/main.py', encoding='utf-8').read()); print('parse ok')"`
Expected: `parse ok`
Run: `python -m pytest tests/ -q`
Expected: existing suite passes (no new failures) and `tests/test_file_logging.py` passes.

- [ ] **Step 9: Commit**

```bash
git add shared/file_logging.py server/main.py tests/test_file_logging.py
git commit -m "feat(logging): wire server transcript hooks + writability probe

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 6: Client wiring (init + quieter console)

**Files:**
- Modify: `client/main.py` (~after line 55, where `_ClientRingHandler` is added to root)
- Test: manual smoke (client is a pygame process; no unit test).

**Interfaces:**
- Consumes: `init_file_logging` (Task 2). Writes `client.log` into the same `logs/` tree; raises console to `client_console_level`.

- [ ] **Step 1: Add file logging init to `client/main.py`**

Right after line 55 (`logging.getLogger().addHandler(_ClientRingHandler())`), add:

```python
# File logging: client writes its own logs/<day>/client.log and quiets the
# console (see docs/superpowers/specs/2026-07-01-file-logging-design.md).
from shared import file_logging as _file_logging
_LOG_CONFIG = _full_config.get("logging", {})
_LOG_ROOT = os.path.join(PROJECT_ROOT, _LOG_CONFIG.get("root_dir", "logs"))
_LOG_HANDLE = _file_logging.init_file_logging(
    _LOG_ROOT, _LOG_CONFIG,
    include_sources=["client"],
    console_level=_LOG_CONFIG.get("client_console_level", "WARNING"))
import atexit as _atexit
_atexit.register(_file_logging.shutdown_file_logging, _LOG_HANDLE)
```

- [ ] **Step 2: Verify the client module parses**

Run: `python -c "import ast; ast.parse(open('client/main.py', encoding='utf-8').read()); print('parse ok')"`
Expected: `parse ok`

- [ ] **Step 3: Commit**

```bash
git add client/main.py
git commit -m "feat(logging): client writes client.log and quiets its console

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 7: Client perf — cap F3 history + gate per-chunk log

**Files:**
- Modify: `client/mario_display.py` (line 334; and the `def __init__` signature before line 314)
- Modify: `client/main.py` (line 145 `self.display = MarioDisplay()`)
- Modify: `client/ws_client.py` (line 156 per-chunk log)
- Test: `tests/test_chat_history_cap.py` (new)

**Interfaces:**
- Consumes: `config["logging"]["chat_overlay_max"]` (Task 4).
- Produces: `MarioDisplay(chat_overlay_max=40)` constructor kwarg controlling `self._MAX_CHAT_HISTORY`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_chat_history_cap.py
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "client"))


def test_chat_history_capped(monkeypatch):
    # Headless pygame so import/construct works without a display.
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    import mario_display
    d = mario_display.MarioDisplay.__new__(mario_display.MarioDisplay)
    d._chat_history = []
    d._MAX_CHAT_HISTORY = 40
    for i in range(100):
        d.add_chat_message("user", f"msg {i}")
    assert len(d._chat_history) == 40
    assert d._chat_history[-1]["text"] == "msg 99"  # newest kept
```

(The append method is `add_chat_message(self, role, text, full_text=None)` at `client/mario_display.py:927`, which pops the oldest once `len > self._MAX_CHAT_HISTORY`.)

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_chat_history_cap.py -v`
Expected: FAIL (either `AttributeError` on the method name — fix the name per the note — or an assertion once the cap is still 10000).

- [ ] **Step 3: Make the cap configurable in `client/mario_display.py`**

Read `client/mario_display.py` at the `def __init__(self, ...)` line (before line 314) and add a `chat_overlay_max: int = 40` parameter. Then change line 334 from:

```python
        self._MAX_CHAT_HISTORY = 10000  # whole session, effectively uncapped
```
to:
```python
        self._MAX_CHAT_HISTORY = chat_overlay_max  # overlay backlog; full record in logs/<day>/conversation.log
```

- [ ] **Step 4: Pass the config value from `client/main.py`**

Change line 145 from:
```python
        self.display = MarioDisplay()
```
to:
```python
        self.display = MarioDisplay(
            chat_overlay_max=int(_full_config.get("logging", {}).get("chat_overlay_max", 40)))
```

- [ ] **Step 5: Gate the per-chunk log in `client/ws_client.py`**

Change lines 155-156 from:
```python
                    if DEBUG_WS:
                        logger.info(f"[DEBUG_WS] audio_chunk {data.get('chunk_index', '?')}/{data.get('total_chunks', '?')} is_last={data.get('is_last', False)}")
```
to (defer f-string, only when DEBUG level is actually enabled — near-zero cost when it is not):
```python
                    if DEBUG_WS and logger.isEnabledFor(logging.DEBUG):
                        logger.debug("[DEBUG_WS] audio_chunk %s/%s is_last=%s",
                                     data.get('chunk_index', '?'), data.get('total_chunks', '?'),
                                     data.get('is_last', False))
```

- [ ] **Step 6: Run to verify it passes**

Run: `python -m pytest tests/test_chat_history_cap.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add client/mario_display.py client/main.py client/ws_client.py tests/test_chat_history_cap.py
git commit -m "perf(client): cap F3 chat history and defer per-chunk log

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 8: `review_log.py` CLI

**Files:**
- Create: `scripts/review_log.py`
- Test: `tests/test_review_log.py` (new)

**Interfaces:**
- Consumes: the on-disk `logs/<day>/<source>.log` layout (Tasks 1-5).
- Produces: `resolve_log_path(root, day, source) -> str` and a `main(argv)` CLI:
  `--day YYYY-MM-DD` (default today), `--source NAME` (default `conversation`), `--grep TEXT`, `--tail N`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_review_log.py
import datetime, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import review_log


def test_resolve_and_read(tmp_path, capsys):
    day = datetime.datetime.now().strftime("%Y-%m-%d")
    d = tmp_path / day
    d.mkdir(parents=True)
    (d / "conversation.log").write_text(
        "2026-07-01@10:00:00.000  [guest] hi\n"
        "2026-07-01@10:00:01.000  [rudi] hello\n"
        "2026-07-01@10:00:02.000  [guest] bye\n", encoding="utf-8")
    p = review_log.resolve_log_path(str(tmp_path), None, "conversation")
    assert p.endswith(os.path.join(day, "conversation.log"))
    review_log.main(["--root", str(tmp_path), "--grep", "guest"])
    out = capsys.readouterr().out
    assert "[guest] hi" in out and "[guest] bye" in out and "[rudi] hello" not in out
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_review_log.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'review_log'`.

- [ ] **Step 3: Create `scripts/review_log.py`**

```python
"""Read back a day's Mario/Rudi logs. Files live at logs/<day>/<source>.log.

  python scripts/review_log.py                    # today's conversation
  python scripts/review_log.py --day 2026-07-01
  python scripts/review_log.py --source tts
  python scripts/review_log.py --grep goodbye --tail 50
"""
import argparse
import datetime
import json
import os


def _default_root():
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    try:
        with open(os.path.join(here, "config.json"), encoding="utf-8") as f:
            root = json.load(f).get("logging", {}).get("root_dir", "logs")
    except Exception:
        root = "logs"
    return os.path.join(here, root)


def resolve_log_path(root, day, source):
    day = day or datetime.datetime.now().strftime("%Y-%m-%d")
    return os.path.join(root, day, f"{source}.log")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Review Mario/Rudi day logs.")
    ap.add_argument("--root", default=None)
    ap.add_argument("--day", default=None)
    ap.add_argument("--source", default="conversation")
    ap.add_argument("--grep", default=None)
    ap.add_argument("--tail", type=int, default=0)
    args = ap.parse_args(argv)

    root = args.root or _default_root()
    path = resolve_log_path(root, args.day, args.source)
    if not os.path.exists(path):
        print(f"(no log at {path})")
        return
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()
    if args.grep:
        lines = [ln for ln in lines if args.grep.lower() in ln.lower()]
    if args.tail:
        lines = lines[-args.tail:]
    print("".join(lines), end="")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/test_review_log.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/review_log.py tests/test_review_log.py
git commit -m "feat(logging): review_log.py CLI for reading day logs

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 9: Full suite + live overnight smoke

**Files:** none (verification only).

- [ ] **Step 1: Run the whole test suite**

Run: `python -m pytest tests/ -q`
Expected: all pass (no regressions from the wiring changes).

- [ ] **Step 2: Live smoke (per `.claude/rules/testing.md` — audio verification applies)**

Start the server + client (`start_server.bat`, then the client). Send a few messages to Rudi and trigger one idle line. Then confirm:
- `logs/<today>/conversation.log` shows `[guest...]` and `[rudi]` lines matching what was said (and audio actually played — `_play_wav: playing` → `_play_wav: done` in the client log, spoken text matches the bubble, ZERO "Mario" references for Rudi).
- `logs/<today>/tts.log`, `llm.log`, `errors.log`, `client.log` exist and contain relevant lines.
- `python scripts/review_log.py` prints today's conversation.
- F3 overlay opens without the long-history hitch; `_chat_history` stays capped at 40.

- [ ] **Step 3: Final commit if any smoke fixes were needed**

```bash
git add <files>
git commit -m "fix(logging): overnight smoke fixes

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Self-Review

**Spec coverage:**
- Day-by-day per-source layout → Task 1 (handler) + Task 2 (routing). ✓
- Plaintext + millis format → Task 1 (`_PlainFormatter`). ✓
- 8 sources incl. conversation/errors/client → Task 2 `SOURCE_LOGGERS` + special cases. ✓
- Name-based routing, zero edits to existing call sites → Task 2. ✓
- Explicit conversation helpers at pipeline choke points → Task 3 + Task 5 (steps 6-7). ✓
- Non-blocking `QueueHandler`/`QueueListener` → Task 2. ✓
- Config block + keep-forever + `.gitignore logs/` → Task 4. ✓
- Server init/shutdown + writability probe (canary intent) → Task 5. ✓
- Client init + quieter console → Task 6. ✓
- `_MAX_CHAT_HISTORY` 10000→40 + gate hot per-chunk log → Task 7. ✓
- `review_log.py` → Task 8. ✓
- Tests + live smoke (audio rule) → Tasks 1-8 unit, Task 9 integration. ✓

**Placeholder scan:** No TBD/TODO. One documented verification step (read the `def __init__` signature in Task 7 Step 3 before adding the `chat_overlay_max` kwarg — the class has many constructor params) — a real action with the exact line to change specified, not a placeholder.

**Type consistency:** `init_file_logging`/`shutdown_file_logging`/`set_character`/`log_guest`/`log_bot`/`probe_writable`/`DayFolderHandler`/`_PlainFormatter`/`SOURCE_LOGGERS`/`CONV_LOGGER` names are identical across the module (Tasks 1-3, 5) and all call sites (Tasks 5-6). `resolve_log_path`/`main` consistent in Task 8. Handle dict keys `queue`/`listener`/`handlers` consistent between `init_file_logging` and `shutdown_file_logging`.
