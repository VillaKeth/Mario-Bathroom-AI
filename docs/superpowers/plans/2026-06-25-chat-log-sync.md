# Bidirectional Chat-Log Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every guest turn (local-typed, tunnel-typed, voice) and every bot turn (single + group mode) appear exactly once in both the pygame F3 chat log and the tunnel mirror transcript.

**Architecture:** Log each guest turn once at input reception via a single `_log_guest_turn` helper (mode-agnostic), instead of inside the response pipeline. Remove the now-redundant pipeline echo and the tunnel-only `add_transcript`. Add per-speaker bot logging to the group path, which bypasses the single-mode pipeline.

**Tech Stack:** Python 3.12, FastAPI/Starlette WebSockets, pytest, `ast` for structural tests (server/main.py is not unit-importable).

## Global Constraints

- `server/main.py` logs via `logger` (e.g. `logger.debug(...)`), matching surrounding code — NOT `print()`.
- Bot-response WebSocket messages use type `"mario_response"`; the guest echo reuses the existing `"user_message"` type. Do not invent new types.
- Git: stage specific files only — `git add server/main.py tests/test_chat_log_sync.py` (NEVER `git add -A`; Qdrant `.lock` files under `server/data/qdrant_memories/` must not be committed).
- Commit trailer: `Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>`.
- `server/main.py` cannot be imported in the unit-test env (see `tests/test_edge_cases.py:1347`); verify internals by parsing its AST/source, and verify behavior with the live test in Task 4.
- Run tests with the venv: `venv/Scripts/python.exe -m pytest ...`.
- All mirror/echo calls must be wrapped in `try/except` — the mirror is optional and must never break the response path.

---

### Task 1: Add `_resolve_guest_name` + `_log_guest_turn` helpers

**Files:**
- Modify: `server/main.py` (insert two functions immediately before `async def _dispatch_user_text(` — currently near line 2070)
- Test: `tests/test_chat_log_sync.py` (create)

**Interfaces:**
- Produces:
  - `_resolve_guest_name(guest_name: str = None) -> str`
  - `async _log_guest_turn(ws: WebSocket, name: str, text: str) -> None`

- [ ] **Step 1: Write the failing test**

Create `tests/test_chat_log_sync.py`:

```python
"""Structural tests for bidirectional chat-log sync (server/main.py).

server/main.py is not importable in the unit env (see test_edge_cases.py:1347),
so these parse its AST/source to assert the design invariants. Behavior is
verified live (see the plan's Task 4).
"""
import ast
import os

_MAIN = os.path.join(os.path.dirname(__file__), "..", "server", "main.py")


def _main_src():
    with open(_MAIN, encoding="utf-8") as f:
        return f.read()


def _main_ast(src=None):
    return ast.parse(src if src is not None else _main_src())


def _func(tree, name):
    """Return the (Async)FunctionDef node named `name`, or None."""
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    return None


def _calls(node, fname):
    """True if `node`'s body contains a call to a function/method named `fname`."""
    for n in ast.walk(node):
        if isinstance(n, ast.Call):
            f = n.func
            if isinstance(f, ast.Name) and f.id == fname:
                return True
            if isinstance(f, ast.Attribute) and f.attr == fname:
                return True
    return False


def _src_of(src, node):
    return ast.get_source_segment(src, node) or ""


# ── Task 1: helpers exist ────────────────────────────────────────────────

def test_log_guest_turn_helper_defined():
    tree = _main_ast()
    node = _func(tree, "_log_guest_turn")
    assert node is not None, "_log_guest_turn must be defined in server/main.py"
    assert isinstance(node, ast.AsyncFunctionDef), "_log_guest_turn must be async"


def test_resolve_guest_name_helper_defined():
    assert _func(_main_ast(), "_resolve_guest_name") is not None, \
        "_resolve_guest_name must be defined in server/main.py"


def test_log_guest_turn_echoes_and_transcribes():
    src = _main_src()
    node = _func(_main_ast(src), "_log_guest_turn")
    body = _src_of(src, node)
    assert "user_message" in body, "_log_guest_turn must echo a user_message"
    assert "add_transcript" in body, "_log_guest_turn must add to the mirror transcript"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/Scripts/python.exe -m pytest tests/test_chat_log_sync.py -q`
Expected: FAIL — `_log_guest_turn must be defined` / `_resolve_guest_name must be defined` (functions absent).

- [ ] **Step 3: Write minimal implementation**

In `server/main.py`, immediately before `async def _dispatch_user_text(text: str):` (near line 2070), insert:

```python
def _resolve_guest_name(guest_name: str = None) -> str:
    """Display name for a guest turn in the shared logs: an explicit name
    (e.g. a tunnel guest's), else the recognized speaker, else 'Guest'."""
    return guest_name or state_current.get("speaker_name") or "Guest"


async def _log_guest_turn(ws: WebSocket, name: str, text: str):
    """Log one guest turn to BOTH shared logs exactly once, at input time:
    echo it to the pygame client's chat backlog (F3 history) AND append it to
    the mirror transcript shown on the tunnel/phone. The mirror is optional — a
    failure here must never break the response path."""
    if not text:
        return
    try:
        await ws.send_json({"type": "user_message", "text": text})
    except Exception as e:
        logger.debug(f"[WS] user_message echo failed: {e}")
    try:
        mirror_relay.add_transcript(name, text)
        await mirror_relay.broadcast_text(
            {"type": "transcript", "lines": mirror_relay.transcript_snapshot()})
    except Exception as e:
        logger.debug(f"[MIRROR] guest transcript log failed: {e}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/Scripts/python.exe -m pytest tests/test_chat_log_sync.py -q`
Expected: PASS (3 passed).

Also confirm the file still compiles:
Run: `venv/Scripts/python.exe -m py_compile server/main.py`
Expected: no output (success).

- [ ] **Step 5: Commit**

```bash
git add server/main.py tests/test_chat_log_sync.py
git commit -m "feat(chat-sync): add _log_guest_turn + _resolve_guest_name helpers" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 2: Wire guest-input entry points; remove the redundant echo + tunnel add

**Files:**
- Modify: `server/main.py` — `_dispatch_user_text` (~2070), `text_input` branch of `handle_event` (~6293), `handle_audio` (~5575), `_generate_and_send_response` (~3991-3997), `friend_say` (~2196-2203)
- Test: `tests/test_chat_log_sync.py` (add tests)

**Interfaces:**
- Consumes: `_log_guest_turn`, `_resolve_guest_name` (Task 1).
- Produces: `_dispatch_user_text(text, guest_name=None)` (new optional param).

This task is atomic: the three entry-point logs are added in the SAME commit that removes the pipeline echo, so no path ever double-echoes or loses its echo.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_chat_log_sync.py`:

```python
# ── Task 2: guest logged at entry; pipeline echo + tunnel add removed ─────

def test_dispatch_user_text_logs_guest():
    node = _func(_main_ast(), "_dispatch_user_text")
    assert _calls(node, "_log_guest_turn"), "_dispatch_user_text must log the guest turn"


def test_dispatch_user_text_takes_guest_name():
    node = _func(_main_ast(), "_dispatch_user_text")
    args = [a.arg for a in node.args.args]
    assert "guest_name" in args, "_dispatch_user_text must accept guest_name"


def test_handle_event_logs_typed_guest():
    node = _func(_main_ast(), "handle_event")
    assert _calls(node, "_log_guest_turn"), "the text_input handler must log the guest turn"


def test_handle_audio_logs_voice_guest():
    node = _func(_main_ast(), "handle_audio")
    assert _calls(node, "_log_guest_turn"), "handle_audio must log the spoken guest turn"


def test_pipeline_no_longer_echoes_user_message():
    src = _main_src()
    body = _src_of(src, _func(_main_ast(src), "_generate_and_send_response"))
    assert "user_message" not in body, \
        "_generate_and_send_response must not echo user_message (now done at entry)"


def test_friend_say_no_longer_adds_transcript():
    src = _main_src()
    body = _src_of(src, _func(_main_ast(src), "friend_say"))
    assert "add_transcript" not in body, \
        "/friend/say must not add_transcript directly (now via _dispatch_user_text)"
    assert "_dispatch_user_text" in body, "/friend/say must still dispatch the text"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `venv/Scripts/python.exe -m pytest tests/test_chat_log_sync.py -q`
Expected: the 6 new tests FAIL — `_dispatch_user_text` lacks `guest_name`/`_log_guest_turn`, `handle_event`/`handle_audio` don't call `_log_guest_turn`, `_generate_and_send_response` still contains `user_message`, `friend_say` still contains `add_transcript`.

- [ ] **Step 3a: Add guest logging to `_dispatch_user_text`**

In `server/main.py`, change the signature and insert the log call after the `_active_ws` guard:

```python
async def _dispatch_user_text(text: str, guest_name: str = None):
    """Run a text input through the exact same pipeline as a real typed message,
    sending the response to the active pygame client. Returns a status dict.

    Shared by /admin/simulate_text and /friend/say."""
    global _current_response_task
    if not text:
        return {"status": "error", "message": "Text required"}
    if not _active_ws:
        return {"status": "error", "message": "No active WebSocket connection"}
    # Log the guest turn once, at input time, to both shared logs.
    await _log_guest_turn(_active_ws, _resolve_guest_name(guest_name), text)
    if _current_response_task and not _current_response_task.done():
```

(Leave the rest of the function unchanged.)

- [ ] **Step 3b: Add guest logging to the `text_input` handler**

In the `elif event_type == "text_input":` branch of `handle_event`, insert the log right after the empty-text guard:

```python
        text = event.get("text", "").strip()
        if not text:
            return

        # Log the typed guest turn once to both shared logs (pygame F3 + tunnel).
        await _log_guest_turn(ws, _resolve_guest_name(None), text)

        # Cancel any in-progress response task (self-interruption)
```

- [ ] **Step 3c: Add guest logging to `handle_audio` (voice)**

Find the single `await _generate_and_send_response(ws, transcript, source="audio", start_time=_response_start)` line (~5575) and insert before it:

```python
    # Log the spoken guest turn once to both shared logs before responding.
    await _log_guest_turn(ws, _resolve_guest_name(None), transcript)
    await _generate_and_send_response(ws, transcript, source="audio", start_time=_response_start)
```

- [ ] **Step 3d: Remove the now-redundant echo from `_generate_and_send_response`**

Replace this block (~3991-3997):

```python
    # Echo the guest's own line to the client so it shows in the chat backlog
    # ("both sides"). Only real user input — not internal greeting/face triggers.
    if text and source in ("text", "audio"):
        try:
            await ws.send_json({"type": "user_message", "text": text})
        except Exception as e:
            logger.debug(f"[WS] user_message echo failed: {e}")
```

with:

```python
    # Guest input is logged at input time via _log_guest_turn (echo + mirror
    # transcript), so the response pipeline no longer echoes here.
```

- [ ] **Step 3e: Update `/friend/say` — pass the name, drop the duplicate add**

Replace this block (~2196-2203):

```python
    # Log the talker's line and push transcript + turn state to all viewers.
    try:
        mirror_relay.add_transcript(name, text)
        await mirror_relay.broadcast_text({"type": "transcript", "lines": mirror_relay.transcript_snapshot()})
        await mirror_relay.broadcast_text({"type": "turn", **mirror_relay.turn_state(now)})
    except Exception:
        pass
    return await _dispatch_user_text(text)
```

with:

```python
    # Push turn state to all viewers. The guest's line itself is logged once by
    # _dispatch_user_text (-> _log_guest_turn), so we don't add_transcript here.
    try:
        await mirror_relay.broadcast_text({"type": "turn", **mirror_relay.turn_state(now)})
    except Exception:
        pass
    return await _dispatch_user_text(text, guest_name=name)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `venv/Scripts/python.exe -m pytest tests/test_chat_log_sync.py -q`
Expected: PASS (9 passed).

Run: `venv/Scripts/python.exe -m py_compile server/main.py`
Expected: success.

- [ ] **Step 5: Commit**

```bash
git add server/main.py tests/test_chat_log_sync.py
git commit -m "feat(chat-sync): log guest turns at input entry; drop pipeline echo + tunnel add" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 3: Group-mode bot-turn transcript logging

**Files:**
- Modify: `server/main.py` — `_group_turn_task` (~2055-2059)
- Test: `tests/test_chat_log_sync.py` (add test)

**Interfaces:**
- Consumes: `mirror_relay.add_transcript`, `mirror_relay.broadcast_text` (existing).

- [ ] **Step 1: Write the failing test**

Append to `tests/test_chat_log_sync.py`:

```python
# ── Task 3: group bot lines reach the mirror transcript ──────────────────

def test_group_turn_logs_bot_lines():
    node = _func(_main_ast(), "_group_turn_task")
    assert _calls(node, "add_transcript"), \
        "_group_turn_task must add each speaker's line to the mirror transcript"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/Scripts/python.exe -m pytest tests/test_chat_log_sync.py::test_group_turn_logs_bot_lines -q`
Expected: FAIL — `_group_turn_task` does not call `add_transcript`.

- [ ] **Step 3: Write the implementation**

In `_group_turn_task`, the speaker loop currently reads:

```python
        for ln in lines:
            if hasattr(tts, "set_voice_config"):
                tts.set_voice_config(ln["voice_config"], ln["display_name"])
            audio = await loop.run_in_executor(_tts_executor, lambda t=ln["text"]: tts.synthesize(t))
            await send_response(ws, ln["text"], audio, emotion=ln["emotion"], speaker=ln["display_name"])
```

Add transcript logging after `send_response`:

```python
        for ln in lines:
            if hasattr(tts, "set_voice_config"):
                tts.set_voice_config(ln["voice_config"], ln["display_name"])
            audio = await loop.run_in_executor(_tts_executor, lambda t=ln["text"]: tts.synthesize(t))
            await send_response(ws, ln["text"], audio, emotion=ln["emotion"], speaker=ln["display_name"])
            # Single-mode bot lines are logged in _generate_and_send_response;
            # group mode bypasses it, so mirror each speaker's line here.
            try:
                mirror_relay.add_transcript(ln["display_name"], ln["text"])
                await mirror_relay.broadcast_text(
                    {"type": "transcript", "lines": mirror_relay.transcript_snapshot()})
            except Exception as e:
                logger.debug(f"[MIRROR] group bot transcript log failed: {e}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/Scripts/python.exe -m pytest tests/test_chat_log_sync.py -q`
Expected: PASS (10 passed).

Run: `venv/Scripts/python.exe -m py_compile server/main.py`
Expected: success.

- [ ] **Step 5: Run the broader suite for regressions**

Run: `venv/Scripts/python.exe -m pytest tests/ -q --ignore=tests/convert_and_test.py --ignore=tests/test_mcp_chatgpt_browser.py`
Expected: no NEW failures vs the known baseline (the 8 `test_pygame_client_controls` `IndexError`s and the flaky `test_vip_knowledge::test_inject_stores_in_qdrant` are pre-existing and unrelated to this change).

- [ ] **Step 6: Commit**

```bash
git add server/main.py tests/test_chat_log_sync.py
git commit -m "feat(chat-sync): mirror group-mode bot lines to the tunnel transcript" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 4: Live integration verification (MANDATORY audio)

**Files:** none (manual verification per `.claude/rules/testing.md`).

No code changes — this gate confirms real behavior because the unit tests are structural only.

- [ ] **Step 1: Start the server and a client**

Run `start_server.bat` (activates `venv/`), open the pygame client and the `/friend` tunnel page (`/control` set to `remote` mode so the phone can drive).

- [ ] **Step 2: Pygame → tunnel direction**

Type a message in the pygame client. Confirm it appears in the `/friend` transcript exactly once (not twice). Confirm the bot reply plays audio in the client logs: `[audio_playback] _play_wav: playing …` then `_play_wav: done`, and the spoken text matches the bubble (`mario says:` line).

- [ ] **Step 3: Tunnel → pygame direction**

Type a message on the `/friend` phone page. Confirm it appears in the pygame F3 chat-history log exactly once, and the bot reply plays audio to completion.

- [ ] **Step 4: Group mode (TADC)**

With group mode active, repeat Steps 2-3. Confirm: each guest line appears in both logs once; each bot speaker's line appears in the tunnel transcript; audio plays for each speaker; for non-Mario characters confirm ZERO Mario references in text AND audio.

- [ ] **Step 5: No-leak idle check**

Leave it idle 2+ minutes. Confirm no double-logged lines and no idle line interleaving (regression check against the memorial/idle work).

---

## Self-Review

- **Spec coverage:** Goal (guest + bot turns, both modes, both logs) → Tasks 1-3. `_resolve_guest_name`/`_log_guest_turn` → Task 1. Three guest entry points + echo removal + `/friend/say` dedup → Task 2. Group bot logging → Task 3. Testing section (unit structural + live audio) → Task 1-3 AST tests + Task 4. Non-goals (no live on-screen render, no audio fan-out, no group routing change) — untouched. ✓
- **Placeholder scan:** none — every code step shows full old/new code and exact commands.
- **Type consistency:** `_log_guest_turn(ws, name, text)` and `_resolve_guest_name(guest_name)` and `_dispatch_user_text(text, guest_name=None)` used consistently across tasks. AST helpers `_func`/`_calls`/`_src_of` defined in Task 1, reused in Tasks 2-3. ✓
