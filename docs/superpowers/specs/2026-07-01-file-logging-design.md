# Day-by-Day Per-Source File Logging — Design

**Date:** 2026-07-01
**Status:** Approved (pending final spec review)
**Approach:** In-process day-folder file handlers + non-blocking queue (Approach A)

## Goal

Run Rudi/Mario overnight, then afterward open `logs/2026-07-01/conversation.log` and read
exactly what was said to the character. Diagnostics (LLM, TTS, memory, events, errors) split
into separate per-source files under the same day folder. Logging must be **non-blocking** so it
costs no measurable time on the asyncio event loop or the pygame render thread. Keep logs forever
(manual delete).

Modeled on the WellnessSpace project's logging structure, with one deliberate divergence:
WellnessSpace writes **one daily file with per-line source tags**; we write **one file per source
per day** (the user's explicit "separate logs per source" requirement). We keep WellnessSpace's
day-rollover pattern, plaintext + millisecond-timestamp format, and non-blocking producer
discipline (adapted to Python's `QueueHandler`/`QueueListener` instead of a TCP daemon).

## Non-Goals (YAGNI)

- No central TCP log daemon / live network subscribers (that was rejected Approach B).
- No shipping client logs to the server over the websocket — client writes its own file locally.
- No retention/cleanup, size-based rotation, or JSON format.
- Non-conversation `print()` output is **not** auto-captured in v1. This matters most for
  `command_handlers.py`, which is almost entirely `print()`-based (one stray `logger` call at
  `server/command_handlers.py:86` aside), so it is deliberately left out of the name-routing table.
  Its user-facing text (game prompts, compliments, etc.) is already captured via the conversation
  helper because that text becomes the character's spoken response.

## On-Disk Layout

```
logs/
  2026-07-01/
    conversation.log     # guest text in + character reply out (the star file)
    llm.log
    tts.log
    memory.log
    events.log
    system.log
    errors.log           # everything WARNING+ (aggregated safety net)
    client.log           # written by the pygame client process
  2026-07-02/
    ...
```

- **Day = local calendar day** (matches the "overnight" mental model). A party that crosses
  midnight splits across two day folders — expected and acceptable.
- Rollover: each handler recomputes `datetime.now().strftime("%Y-%m-%d")` on every emit; when the
  day string changes it closes the current file and reopens under the new day folder (this is
  WellnessSpace's `check_rotate_log()` pattern, adapted to folder-per-day + file-per-source).
- `logs/` is added to `.gitignore` (never commit logs, same discipline as Qdrant lock files).
- `root_dir` resolves to an **absolute** path at init, relative to the project root (both processes
  already compute the project root via their `sys.path.insert`), so the client and server land in
  the same `logs/` tree regardless of each process's working directory.

## Line Format

Plaintext, WellnessSpace style, with milliseconds:

```
2026-07-01@22:14:03.120  hey rudi you awake?
```

`conversation.log` prepends a role chip and (when known) the guest name:

```
2026-07-01@22:14:03.120  [guest:Jacob] hey rudi you awake?
2026-07-01@22:14:04.880  [rudi] Ohh you know it, I never sleep at a party!
```

Guest name comes from existing face/speaker identification when available, else `[guest]`.
The bot chip uses the active character's short name (`[rudi]`, `[mario]`, ...).

## Sources and Routing

Routing is **by logger name** for all diagnostic sources — this captures the existing 71
`logger = logging.getLogger(__name__)` call sites with **zero edits**. Each source handler carries
a filter that accepts only records whose logger name is in its set.

| File | Logger names (module `__name__`) |
|------|----------------------------------|
| `llm.log` | `llm_router`, `llm` |
| `tts.log` | `tts`, `tts_router`, `gpt_sovits_server`, `fish_speech_tts` |
| `memory.log` | `memory`, `memory_semantic`, `party_gossip`, `vip_knowledge` |
| `events.log` | `game_handlers`, `idle_behavior`, `night_progression`, `emotions`, `birthday_vip` |
| `system.log` | `mario-server`, `watchdog`, `canary`, `hardware`, `hot_reload`, `dashboard` |
| `errors.log` | any logger at level ≥ WARNING **except** the conversation logger |
| `client.log` | (client process) the client's root logger |

The exact logger-name → source map lives as a dictionary in `shared/file_logging.py` and is the
single place to adjust routing. A record may land in more than one file (e.g. a `tts` ERROR goes to
both `tts.log` and `errors.log`); that redundancy is intentional (errors.log is a cross-cutting
safety net).

`conversation.log` is **not** captured by name-scraping — it is written by an explicit helper
(below) using a dedicated logger `mario.conversation`, whose records route only to `conversation.log`.

## Core Module — `shared/file_logging.py` (new)

Placed in the `shared/` package because both `server/main.py` and `client/main.py` already do
`from shared.character_loader import ...`, so `from shared.file_logging import ...` works unchanged
for both.

Public API:

- `init_file_logging(root_dir, config, *, include_sources=None)` — resolves `root_dir` to absolute,
  builds one `DayFolderHandler` per enabled source, wraps them behind a single `QueueListener`
  (background thread), and attaches one `QueueHandler` to the root logger. The client passes
  `include_sources=["client"]`; the server enables the rest. Returns a handle used for shutdown.
- `class DayFolderHandler(logging.Handler)` — owns one source's file; reopens on day rollover;
  uses the plaintext+millis `Formatter`; carries the name/level filter for its source.
- `get_conversation_logger()` → `logging.getLogger("mario.conversation")`.
- `log_guest(name, text)` / `log_bot(text)` — format the role chip and emit on the conversation
  logger.
- `shutdown_file_logging(handle)` — `QueueListener.stop()` to flush the queue so no lines are lost
  on exit.

**Non-blocking guarantee:** application threads only call `QueueHandler.emit`, which enqueues and
returns immediately. All file I/O happens on the single `QueueListener` thread. This keeps writes
off the asyncio event loop (server) and the pygame render thread (client).

The existing console `basicConfig` handler and the `debug_ring.LogRing` handler on the root logger
are left untouched — live console view and the mario-debug MCP tail keep working. File logging is
purely additive on the root logger.

## Server Wiring — `server/main.py`

- Call `init_file_logging(root_dir, config["logging"])` right after config load (near the existing
  `logging.basicConfig` at line 89).
- Add the conversation helper at the response-pipeline boundaries (~2–4 call sites):
  - `log_guest(name, text)` where inbound guest text is resolved (with the identified name if any).
  - `log_bot(text)` where the final character response text is produced (the same value handed to
    TTS / the `mario_response` websocket message).
- Call `shutdown_file_logging(handle)` in the server shutdown path. Logging stays alive through
  watchdog degraded/minimal tiers (it is cheap and the record is most valuable when things degrade).
- `canary.py`: add a smoke check that the log root is writable.

## Client Changes — `client/` (the performance fixes)

- `client/main.py`: call `init_file_logging(root_dir, config["logging"], include_sources=["client"])`
  at startup (client already has its own `basicConfig` at line 38). Client writes only `client.log`;
  no overlap with server files, so two writers never touch the same file.
- Raise the client **console** level to `client_console_level` (default WARNING). Gate the hottest
  lines behind DEBUG so they stop hitting the console synchronously every message/frame:
  - per-audio-chunk log (`client/ws_client.py:156`)
  - per-frame `_publish_frame` path (`client/mario_display.py`)
  These still reach `client.log` cheaply through the queue.
- **Chat-history cap:** change `self._MAX_CHAT_HISTORY` from `10000` (`client/mario_display.py:334`,
  currently "effectively uncapped") to `config.logging.chat_overlay_max` (default **40**). The full
  record now lives in `conversation.log`; the F3 overlay only needs recent messages. This removes
  both the per-session memory growth and the every-frame re-wrap of thousands of messages in
  `_draw_chat_history` (`client/mario_display.py:2357`), which is the hitch the user observed.
- (Optional, not required) cache the built F3 message blocks instead of rebuilding them every frame.
  The cap alone removes the pain; skip unless profiling still shows a problem.

## Config — new `logging` block in `config.json`

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
}
```

Absence of a retention key = keep forever. `enabled: false` disables file logging entirely
(handlers not attached), leaving console + debug_ring behavior exactly as today.

## Review Tool — `scripts/review_log.py` (included)

A small CLI to read back a day's logs without opening files by hand (the lightweight analogue of
WellnessSpace's `sort_log.py`; no reordering needed since our files are already per-source and
chronological):

```
python scripts/review_log.py                       # today's conversation.log
python scripts/review_log.py --day 2026-07-01      # that day's conversation
python scripts/review_log.py --source tts          # today's tts.log
python scripts/review_log.py --grep "goodbye"      # filter lines
python scripts/review_log.py --tail 50             # last N lines
```

Defaults: `--day` = today, `--source` = conversation. Optionally colorizes guest vs bot lines in
`conversation.log` (guest one color, character another) for readability. Reads `root_dir` from
`config.json`.

## Testing — `tests/test_file_logging.py`

- `DayFolderHandler` writes to the correct dated folder and file.
- Day rollover: monkeypatch the date, emit across a boundary, assert a new day folder/file is used
  and the old file is closed.
- Line format matches `YYYY-MM-DD@HH:MM:SS.mmm  message`.
- Name-filter routing: a record from logger `tts` lands only in `tts.log`; a WARNING lands in
  `errors.log`; a `mario.conversation` record lands only in `conversation.log`.
- Conversation helper: `log_guest` / `log_bot` produce correctly chipped lines.
- `QueueListener` flush on shutdown loses no lines.
- Client cap: appending 100 messages leaves `_chat_history` length == `chat_overlay_max`.

Follows the existing pytest layout under `tests/`.

## Files Touched

| File | Change |
|------|--------|
| `shared/file_logging.py` | **new** — core module (handler, queue wiring, conversation helper) |
| `server/main.py` | init + shutdown calls; `log_guest`/`log_bot` at pipeline points |
| `client/main.py` | init call (client source); raise console level |
| `client/ws_client.py` | gate per-audio-chunk log behind DEBUG |
| `client/mario_display.py` | `_MAX_CHAT_HISTORY` → configurable cap; gate per-frame log |
| `server/canary.py` | add "log dir writable" smoke check |
| `config.json` | new `logging` block |
| `.gitignore` | add `logs/` |
| `scripts/review_log.py` | **new** — log review CLI |
| `tests/test_file_logging.py` | **new** — unit tests |
