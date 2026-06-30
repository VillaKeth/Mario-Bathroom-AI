# Adaptive Response Length & Continuous Conversation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let Rudi auto-detect when a message deserves a long, detailed answer and respond at length (interruptibly), drive conversations harder, and collapse message floods into one answer instead of cancelling himself into silence.

**Architecture:** All changes are server-side. A pure heuristic classifier decides per-turn length (no extra LLM call); a per-call `num_predict` override + the existing `filter_response(cap=...)` param carry it through. A debounce buffer in the text-input path batches rapid messages into one turn, behind a hot-reloadable flag.

**Tech Stack:** Python 3.10+, FastAPI/asyncio WebSocket server, Ollama, pytest.

## Global Constraints

- Logging uses `print()` in `command_handlers.py` only; `main.py`/`llm.py`/`mario_prompt.py` use the module `logger`.
- WebSocket response message type is `"mario_response"`.
- No ellipsis (`...`) in hardcoded strings that reach TTS.
- `git add <specific files>` only — never `git add -A` (Qdrant `.lock` files).
- Commit trailer: `Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>`
- New behavior tunables read from `live_config.get(key, default)` so they hot-reload.
- Baseline tag before this work: `v4.1`.

---

## File Structure

- `server/mario_prompt.py` — add `detect_length_intent(text)` (A1) and `maybe_add_followup(response, history_len, transcript)` (A2). Pure functions, no I/O.
- `server/llm.py` — `generate_response()` gains optional `num_predict` param (A1).
- `server/main.py` — wire length intent into `_generate_and_send_response` (A1+A2); add the debounce/batch buffer in the text-input path (A3).
- `server/safety_filter.py` — no change (the `cap` param already exists at `filter_response(text, cap=True)`).
- `config_live.json` — add `burst_debounce_ms`, `long_num_predict`, `long_char_cap` (hot-reloadable).
- Tests: `tests/test_adaptive_length.py` (A1/A2 pure fns), `tests/test_burst_batch.py` (A3 buffer logic).

---

### Task 1: Length-intent detector (A1, pure function)

**Files:**
- Modify: `server/mario_prompt.py` (add function near other text helpers, e.g. after `maybe_add_question` at line 509)
- Test: `tests/test_adaptive_length.py`

**Interfaces:**
- Produces: `detect_length_intent(text: str) -> str` returning `"long"` or `"short"`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_adaptive_length.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))
from mario_prompt import detect_length_intent

def test_guide_requests_are_long():
    for t in [
        "how do I beat the ender dragon?",
        "walk me through building a redstone door",
        "what's the best strategy for ranked?",
        "explain how brewing works step by step",
        "give me tips for aiming better",
        "teach me the combo",
    ]:
        assert detect_length_intent(t) == "long", t

def test_banter_stays_short():
    for t in [
        "hey rudi!", "lol you're funny", "roast me", "what's up",
        "yes", "I'm Jacob", "haha nice", "explain?",  # too short / not a real request
    ]:
        assert detect_length_intent(t) == "short", t
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv\Scripts\python.exe -m pytest tests/test_adaptive_length.py -v`
Expected: FAIL with `ImportError: cannot import name 'detect_length_intent'`

- [ ] **Step 3: Write minimal implementation**

```python
# server/mario_prompt.py  (add after maybe_add_question)
import re as _re_len

_LONG_INTENT_PATTERNS = [
    r"\bhow (?:do|do i|do you|to)\b",
    r"\bwalk me through\b",
    r"\bstep[- ]by[- ]step\b",
    r"\bbest (?:way|strategy|build|loadout)\b",
    r"\bstrateg(?:y|ies)\b",
    r"\bexplain\b", r"\bbreak ?down\b",
    r"\btips? for\b", r"\bteach me\b",
    r"\bguide\b", r"\bhow does .+ work\b",
    r"\btell me everything\b", r"\bfull (?:guide|rundown|breakdown)\b",
]
_LONG_INTENT_RE = _re_len.compile("|".join(_LONG_INTENT_PATTERNS), _re_len.IGNORECASE)

def detect_length_intent(text: str) -> str:
    """Heuristic: 'long' when the guest asks for a guide/explanation/strategy.

    Gated on a real request (>= 4 words) so a bare 'explain?' or one-word message
    stays short. No LLM call — cheap and deterministic.
    """
    if not text:
        return "short"
    words = text.split()
    if len(words) < 4:
        return "short"
    return "long" if _LONG_INTENT_RE.search(text) else "short"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv\Scripts\python.exe -m pytest tests/test_adaptive_length.py -v`
Expected: PASS (both tests)

- [ ] **Step 5: Commit**

```bash
git add server/mario_prompt.py tests/test_adaptive_length.py
git commit -m "feat(convo): detect_length_intent heuristic (A1)"
```

---

### Task 2: Per-call `num_predict` override in the LLM (A1)

**Files:**
- Modify: `server/llm.py:150` (`generate_response` signature) and `:193` (payload)
- Test: `tests/test_adaptive_length.py` (add a payload test using monkeypatch)

**Interfaces:**
- Consumes: nothing new.
- Produces: `generate_response(messages, transcript=None, model=None, num_predict=None)`. When `num_predict` is an int it overrides `LLM_NUM_PREDICT` in the Ollama `options`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_adaptive_length.py  (append)
import asyncio, types, llm as llm_mod

def test_num_predict_override_used(monkeypatch):
    captured = {}
    class FakeResp:
        status_code = 200
        def raise_for_status(self): pass
        async def aiter_lines(self):
            yield '{"message":{"content":"hi there friend"},"done":true}'
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
    class FakeClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        def stream(self, method, url, json=None, timeout=None):
            captured["num_predict"] = json["options"]["num_predict"]
            return FakeResp()
    monkeypatch.setattr(llm_mod.httpx, "AsyncClient", lambda *a, **k: FakeClient())
    asyncio.get_event_loop().run_until_complete(
        llm_mod.generate_response([{"role": "user", "content": "hi"}], num_predict=512))
    assert captured["num_predict"] == 512
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv\Scripts\python.exe -m pytest tests/test_adaptive_length.py::test_num_predict_override_used -v`
Expected: FAIL (`generate_response() got an unexpected keyword argument 'num_predict'`)

- [ ] **Step 3: Write minimal implementation**

In `server/llm.py`, change the signature at line 150:

```python
async def generate_response(messages: list[dict], transcript: str = None, model: str = None,
                            num_predict: int = None) -> dict:
```

And in the payload (line ~193), replace the `"num_predict": LLM_NUM_PREDICT,` line with:

```python
            "num_predict": num_predict if isinstance(num_predict, int) else LLM_NUM_PREDICT,
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv\Scripts\python.exe -m pytest tests/test_adaptive_length.py::test_num_predict_override_used -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add server/llm.py tests/test_adaptive_length.py
git commit -m "feat(llm): per-call num_predict override (A1)"
```

---

### Task 3: Wire length intent into the response pipeline (A1)

**Files:**
- Modify: `server/main.py` — inside `_generate_and_send_response` (starts line 4132): at the routing block (~line 5228–5241) and the filter block (~line 5330).
- Modify: `config_live.json` — add `long_num_predict` (512) and `long_char_cap` (2000).
- Test: manual integration (documented), plus a unit assert on the helper wiring.

**Interfaces:**
- Consumes: `detect_length_intent` (Task 1), `generate_response(..., num_predict=)` (Task 2), `filter_response(text, cap)` (existing, `safety_filter.py:145`).

- [ ] **Step 1: Add config knobs**

Edit `config_live.json`, add keys (keep existing JSON valid):

```json
  "long_num_predict": 512,
  "long_char_cap": 2000,
  "burst_debounce_ms": 1200
```

- [ ] **Step 2: Compute intent before the LLM call**

In `main.py`, just before the router classify block (~line 5228, where `_response_type = _infer_response_type(...)` is), add:

```python
        _length_intent = mario_prompt.detect_length_intent(text)
        _long = (_length_intent == "long")
        _long_np = int(live_config.get("long_num_predict", 512)) if _long else None
        if _long:
            ctx.append({"role": "system", "content":
                "This question deserves a thorough, in-character answer — give real "
                "detail and clear structure, do not rush it or cut it short."})
            logger.info(f"[LENGTH] long-intent detected for: '{text[:60]}'")
```

- [ ] **Step 3: Pass the override into the LLM call**

In the same function, find the `llm.generate_response(ctx, text, model=_routed_model)` call inside the `asyncio.gather` (~line 5241) and add `num_predict=_long_np`:

```python
                asyncio.wait_for(llm.generate_response(ctx, text, model=_routed_model,
                                                       num_predict=_long_np), timeout=_LLM_TIMEOUT),
```

(Also add `num_predict=_long_np` to the fast-model retry call in the `except asyncio.TimeoutError` block ~line 5269.)

- [ ] **Step 4: Lift the char cap for long replies**

At the filter block (~line 5330), replace:

```python
    response_text = filter_response(_raw_response)
```

with:

```python
    _cap_for_turn = not (locals().get("_long") and len(_raw_response) <= int(live_config.get("long_char_cap", 2000)))
    response_text = filter_response(_raw_response, cap=_cap_for_turn)
```

(`_long` may be unset when the response came from a command/game path; `locals().get` guards that.)

- [ ] **Step 5: Verify nothing breaks + manual check**

Run: `venv\Scripts\python.exe -m pytest tests/ -k "adaptive or prompt" -v`
Expected: PASS.
Manual: start server, send "how do I beat the ender dragon?" → reply is a multi-sentence guide, streams first audio fast, and a new message mid-guide cuts it off. Send "hey rudi" → still a punchy one-liner.

- [ ] **Step 6: Commit**

```bash
git add server/main.py config_live.json
git commit -m "feat(convo): route long-intent answers to longer, uncapped replies (A1)"
```

---

### Task 4: Conversation engagement / follow-ups (A2)

**Files:**
- Modify: `server/mario_prompt.py` — add `maybe_add_followup(...)`.
- Modify: `server/main.py` — call it after `maybe_add_question` (~line 5333).
- Test: `tests/test_adaptive_length.py`

**Interfaces:**
- Produces: `maybe_add_followup(response: str, history_len: int, last_added: list) -> str`. Appends a short hook in an active convo (history_len >= 4), throttled so it won't fire two turns in a row (tracked via `last_added`, a 1-element list used as a mutable flag).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_adaptive_length.py  (append)
from mario_prompt import maybe_add_followup

def test_followup_throttled():
    flag = [False]
    # First active-convo turn may add a hook
    out1 = maybe_add_followup("Cool build.", history_len=6, last_added=flag)
    # Immediately after a hook, the next turn must NOT add another
    if flag[0]:
        out2 = maybe_add_followup("Nice.", history_len=6, last_added=flag)
        assert out2 == "Nice."  # throttled
    # Short/early convo never adds
    flag2 = [False]
    assert maybe_add_followup("Hi.", history_len=1, last_added=flag2) == "Hi."
    assert flag2[0] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv\Scripts\python.exe -m pytest tests/test_adaptive_length.py::test_followup_throttled -v`
Expected: FAIL (`cannot import name 'maybe_add_followup'`)

- [ ] **Step 3: Write minimal implementation**

```python
# server/mario_prompt.py
import random as _rand_fu

_FOLLOWUPS = [
    "So what's your move?", "You in or out?", "Bet you can't top that.",
    "What happened next?", "Come on, give me the story.", "Your turn, hotshot.",
]

def maybe_add_followup(response: str, history_len: int, last_added: list) -> str:
    """In an active back-and-forth, sometimes end on a hook to keep it going.

    Throttled: never two turns in a row (last_added[0] is the flag). Only in an
    established convo (history_len >= 4). ~40% chance otherwise.
    """
    if history_len < 4 or last_added[0]:
        last_added[0] = False
        return response
    if _rand_fu.random() < 0.40:
        last_added[0] = True
        return response.rstrip() + " " + _rand_fu.choice(_FOLLOWUPS)
    last_added[0] = False
    return response
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv\Scripts\python.exe -m pytest tests/test_adaptive_length.py::test_followup_throttled -v`
Expected: PASS

- [ ] **Step 5: Wire into the pipeline**

In `main.py`, add module-level state near other `state_current` keys: `state_current["_last_followup_flag"] = [False]`. Then after the `maybe_add_question` line (~5333):

```python
    response_text = mario_prompt.maybe_add_followup(
        response_text, len(state_current["conversation_history"]),
        state_current.setdefault("_last_followup_flag", [False]))
```

- [ ] **Step 6: Commit**

```bash
git add server/mario_prompt.py server/main.py tests/test_adaptive_length.py
git commit -m "feat(convo): throttled follow-up hooks in active conversation (A2)"
```

---

### Task 5: Debounce + batch burst handling (A3)

**Files:**
- Modify: `server/main.py` — the two text-input entry points: `_dispatch_user_text` (line 2109) and the WS `text_input` branch (line ~6464). Centralize into one helper `_enqueue_user_text(text)`.
- Test: `tests/test_burst_batch.py`

**Interfaces:**
- Produces: `_batch_join(messages: list[str]) -> str` — pure helper that folds a burst into one turn string. Tested in isolation; the async timer wraps it.

- [ ] **Step 1: Write the failing test (pure batch join)**

```python
# tests/test_burst_batch.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))
import main as srv

def test_single_message_unchanged():
    assert srv._batch_join(["how do I win?"]) == "how do I win?"

def test_multiple_messages_folded():
    out = srv._batch_join(["wait", "actually", "how do I beat the boss?"])
    assert "how do I beat the boss?" in out
    assert "wait" in out and "actually" in out
    # folded into a single string, not a list
    assert isinstance(out, str)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv\Scripts\python.exe -m pytest tests/test_burst_batch.py -v`
Expected: FAIL (`module 'main' has no attribute '_batch_join'`)

- [ ] **Step 3: Implement the pure helper + the async debounce buffer**

In `server/main.py`, add near the other text helpers:

```python
_pending_burst: list[str] = []
_burst_timer_task: "asyncio.Task | None" = None

def _batch_join(messages: list[str]) -> str:
    """Fold a burst of quick messages into one turn. A lone message passes through
    unchanged; multiple are joined so the LLM answers them together."""
    msgs = [m.strip() for m in messages if m and m.strip()]
    if not msgs:
        return ""
    if len(msgs) == 1:
        return msgs[0]
    return " ".join(msgs)

async def _enqueue_user_text(text: str):
    """Debounce + batch rapid messages into one turn (A3). burst_debounce_ms<=0
    restores the old cancel-immediately behavior."""
    global _burst_timer_task
    debounce_ms = int(live_config.get("burst_debounce_ms", 1200))
    if debounce_ms <= 0:
        await _dispatch_user_text(text)
        return
    _pending_burst.append(text)
    state_current["_user_request_active"] = True  # suppress idle while collecting
    if _burst_timer_task and not _burst_timer_task.done():
        _burst_timer_task.cancel()
    async def _fire(cap_ms: int):
        try:
            await asyncio.sleep(cap_ms / 1000.0)
        except asyncio.CancelledError:
            return
        batch = _batch_join(list(_pending_burst))
        _pending_burst.clear()
        if batch:
            await _dispatch_user_text(batch)
    _burst_timer_task = asyncio.create_task(_fire(debounce_ms))
```

Then route both entry points through it. In the WS `text_input` branch (~line 6492) replace the `_current_response_task = asyncio.create_task(_text_input_task(ws, text))` with:

```python
        await _enqueue_user_text(text)
```

And in `/admin/simulate_text` / `/friend/say` (which already call `_dispatch_user_text`), leave them — they bypass debounce intentionally (single programmatic sends).

- [ ] **Step 4: Run test to verify it passes**

Run: `venv\Scripts\python.exe -m pytest tests/test_burst_batch.py -v`
Expected: PASS

- [ ] **Step 5: Manual burst check**

Start server + client. Type three messages within ~1s ("wait", "no", "how do I beat the dragon?"). Expected: ONE response addressing the dragon question (server log shows a single `_generate_and_send_response`), not three cancellations. Set `burst_debounce_ms` to `0` in `config_live.json`, hot-reload, confirm old immediate behavior returns.

- [ ] **Step 6: Commit**

```bash
git add server/main.py tests/test_burst_batch.py
git commit -m "feat(convo): debounce+batch message bursts so floods don't starve replies (A3)"
```

---

## Self-Review

**Spec coverage:**
- A1 adaptive length → Tasks 1–3 (detector, num_predict override, pipeline wiring + char cap). ✓
- A2 engagement → Task 4. ✓
- A3 burst handling → Task 5 (debounce+batch, hot-reload flag). ✓
- "Speak full, interruptible" → unchanged existing self-interrupt; A3 only delays the START of a turn, the in-progress interrupt path is untouched. ✓

**Placeholder scan:** No TBD/TODO; every code step has concrete code. ✓

**Type consistency:** `detect_length_intent -> str`, `generate_response(..., num_predict=None)`, `maybe_add_followup(response, history_len, last_added)`, `_batch_join(list) -> str` used consistently across tasks. ✓

**Open risk:** A3's `_dispatch_user_text` already sets/clears `_user_request_active`; the debounce sets it early to keep idle suppressed during the collect window — verify no idle line slips out between enqueue and fire during manual testing.
