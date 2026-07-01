# Chat-Path Person Memory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give a browser chatter who types their name a persistent `speaker_id` so Rudi's existing per-person recall + `save_fact`/`save_conversation` actually fire — reusing (and DRYing) the name→id logic already in `presence_enter`.

**Architecture:** One new leaf module `server/chat_identity.py` with `resolve_chat_identity(name)` — VIP-alias-normalize via `vip_knowledge.is_vip`, then `memory.find_person_by_name` (exact) or a stable name-hash id. Two wire-ups: the audio-less typed-name branch (the fix) and a DRY of the duplicate block in `presence_enter`.

**Tech Stack:** Python, existing `memory.py` (SQLite+Qdrant), `vip_knowledge.py`, pytest.

## Global Constraints

- New module `server/chat_identity.py` uses the module `logger` (like `memory.py`). Do NOT add `logger`/`print` to `command_handlers.py` — its wire-up only sets state fields.
- Chat identity is CLAIMED / low-confidence: personal memory is keyed on `hash(canonical_name)`, kept separate from a VIP's injected memory. No merge logic here.
- Personal-memory id formula (must match existing `presence_enter`): `int(hashlib.md5(name.lower().encode()).hexdigest()[:8], 16)`.
- `client_id` param exists but is IGNORED (reserved for future IP/browser-id).
- `git add <specific files>` only (never `-A`); commit trailer `Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>`.
- Tests run with `venv\Scripts\python.exe -m pytest`.
- `resolve_chat_identity` must NEVER raise — fall back to the plain name hash on any error.

---

## File Structure

- `server/chat_identity.py` *(new)* — `resolve_chat_identity(name, client_id=None) -> (int|None, str)`, `_name_hash(name) -> int`. Imports `memory` + `vip_knowledge` (leaf; imports nothing from `command_handlers`/`main`).
- `server/command_handlers.py` *(modify)* — `from chat_identity import resolve_chat_identity` at top; wire the audio-less name branch (~line 603).
- `server/main.py` *(modify)* — replace the inline find-or-hash block in `presence_enter` (~line 6008-6020) with a `resolve_chat_identity` call.
- Tests: `tests/test_chat_identity.py` (new), plus one test appended to `tests/test_command_handlers.py`.

---

### Task 1: `chat_identity.resolve_chat_identity`

**Files:**
- Create: `server/chat_identity.py`
- Test: `tests/test_chat_identity.py`

**Interfaces:**
- Produces: `resolve_chat_identity(name: str, client_id: str = None) -> tuple[int | None, str]`. Returns `(speaker_id, canonical_name)`; `(None, "")` for empty name.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_chat_identity.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))
import chat_identity, memory, vip_knowledge

def test_non_vip_name_stable_id(monkeypatch):
    monkeypatch.setattr(vip_knowledge, "is_vip", lambda n: (False, None))
    monkeypatch.setattr(memory, "find_person_by_name", lambda n: None)
    monkeypatch.setattr(memory, "register_person", lambda pid, name: None)
    id1, name1 = chat_identity.resolve_chat_identity("Bob")
    id2, _ = chat_identity.resolve_chat_identity("bob")   # case-insensitive
    assert isinstance(id1, int)
    assert id1 == id2          # stable across case + sessions
    assert name1 == "Bob"

def test_vip_alias_normalizes_to_canonical(monkeypatch):
    monkeypatch.setattr(vip_knowledge, "is_vip", lambda n: (True, {"name": "Jacob Hoppenstedt"}))
    monkeypatch.setattr(memory, "find_person_by_name", lambda n: None)
    monkeypatch.setattr(memory, "register_person", lambda pid, name: None)
    pid, canonical = chat_identity.resolve_chat_identity("Jake")
    assert canonical == "Jacob Hoppenstedt"
    assert isinstance(pid, int)

def test_existing_person_links_no_new_id(monkeypatch):
    monkeypatch.setattr(vip_knowledge, "is_vip", lambda n: (False, None))
    monkeypatch.setattr(memory, "find_person_by_name",
                        lambda n: {"id": 999, "name": "Bob", "visit_count": 3})
    visited = []
    monkeypatch.setattr(memory, "record_visit", lambda pid: visited.append(pid))
    pid, name = chat_identity.resolve_chat_identity("Bob")
    assert pid == 999 and visited == [999]

def test_empty_name_returns_none(monkeypatch):
    assert chat_identity.resolve_chat_identity("") == (None, "")
    assert chat_identity.resolve_chat_identity("   ") == (None, "")

def test_never_raises_on_error(monkeypatch):
    def boom(n): raise RuntimeError("vip down")
    monkeypatch.setattr(vip_knowledge, "is_vip", boom)
    monkeypatch.setattr(memory, "find_person_by_name", lambda n: None)
    monkeypatch.setattr(memory, "register_person", lambda pid, name: None)
    pid, name = chat_identity.resolve_chat_identity("Bob")
    assert isinstance(pid, int) and name == "Bob"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `venv\Scripts\python.exe -m pytest tests/test_chat_identity.py -v`
Expected: FAIL (`ModuleNotFoundError: chat_identity`).

- [ ] **Step 3: Write the implementation**

```python
# server/chat_identity.py
"""Resolve a chat-typed name to a persistent speaker_id (the personal-memory key).

A typed name is a CLAIM, not proof. Personal memory is keyed on a stable hash of
the (VIP-canonicalized) name, kept separate from a VIP profile's injected memories,
so voice/face can confirm/merge later. Never raises.
"""
import hashlib
import logging

import memory
import vip_knowledge

logger = logging.getLogger(__name__)


def _name_hash(name: str) -> int:
    return int(hashlib.md5(name.lower().encode()).hexdigest()[:8], 16)


def resolve_chat_identity(name: str, client_id: str = None) -> tuple:
    """Map a typed name to (speaker_id, canonical_name). (None, "") if name blank.

    client_id is reserved for a future per-browser id / IP tiebreaker; ignored now.
    """
    if not name or not name.strip():
        return None, ""
    canonical = name.strip()
    try:
        is_v, profile = vip_knowledge.is_vip(canonical)
        if is_v and profile and profile.get("name"):
            canonical = profile["name"]
    except Exception as e:
        logger.debug(f"[CHAT_ID] is_vip failed for '{name}': {e}")
    try:
        person = memory.find_person_by_name(canonical)
        if person:
            memory.record_visit(person["id"])
            return person["id"], canonical
        pid = _name_hash(canonical)
        memory.register_person(pid, canonical)
        return pid, canonical
    except Exception as e:
        logger.warning(f"[CHAT_ID] memory resolve failed for '{canonical}': {e}")
        return _name_hash(canonical), canonical
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `venv\Scripts\python.exe -m pytest tests/test_chat_identity.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add server/chat_identity.py tests/test_chat_identity.py
git commit -m "feat(memory): resolve_chat_identity — typed name to persistent speaker_id"
```

---

### Task 2: Wire into the typed-name path + DRY presence_enter

**Files:**
- Modify: `server/command_handlers.py` (top import + audio-less name branch ~line 603)
- Modify: `server/main.py` (`presence_enter` find-or-hash block ~line 6008-6020)
- Test: append to `tests/test_command_handlers.py`

**Interfaces:**
- Consumes: `resolve_chat_identity(name) -> (int|None, str)` (Task 1).

- [ ] **Step 1: Write the failing test** (typed name now sets speaker_id)

```python
# tests/test_command_handlers.py  (append near the other name/roast tests;
# reuse the existing _make_state / _call helpers already in this file)
def test_typed_name_sets_speaker_id(monkeypatch):
    import command_handlers
    monkeypatch.setattr(command_handlers, "resolve_chat_identity",
                        lambda name, client_id=None: (4242, name))
    state = _make_state()
    state["_last_audio_chunk"] = None          # force the audio-less (text) branch
    state["_name_from_parsing"] = False
    result = _call("my name is Bob", state=state)
    assert state["speaker_id"] == 4242
    assert state["speaker_name"] == "Bob"
    assert "Bob" in result
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv\Scripts\python.exe -m pytest tests/test_command_handlers.py::test_typed_name_sets_speaker_id -v`
Expected: FAIL (`speaker_id` is None — current audio-less branch never sets it; also `resolve_chat_identity` not importable on `command_handlers` yet).

- [ ] **Step 3: Add the import + wire the branch** in `server/command_handlers.py`

Add near the other imports at the top (e.g. after `import speaker_id`):

```python
from chat_identity import resolve_chat_identity
```

Replace the audio-less `else` branch (currently ~line 603-606):

```python
                else:
                    state["speaker_name"] = name
                    state["_name_from_parsing"] = True
                    return f"Nice to meet you, {name}! I'll remember you!"
```

with:

```python
                else:
                    pid, canonical = resolve_chat_identity(name)
                    if pid is not None:
                        state["speaker_id"] = pid
                        state["speaker_name"] = canonical
                    else:
                        state["speaker_name"] = name
                    state["_name_from_parsing"] = True
                    return f"Nice to meet you, {state['speaker_name']}! I'll remember you!"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv\Scripts\python.exe -m pytest tests/test_command_handlers.py::test_typed_name_sets_speaker_id -v`
Expected: PASS.

- [ ] **Step 5: DRY the duplicate logic in `presence_enter`** (`server/main.py`)

Replace the inline block (currently ~line 6008-6020, the `# Browser fallback: look up or create speaker_id by name` block through the `virtual_id` else):

```python
    # Browser fallback: look up or create speaker_id by name if not identified by voice
    if state_current["speaker_id"] is None and state_current["speaker_name"]:
        person = memory.find_person_by_name(state_current["speaker_name"])
        if person:
            state_current["speaker_id"] = person["id"]
            memory.record_visit(person["id"])
            logger.info(f"[BROWSER_MEMORY] Matched '{state_current['speaker_name']}' to speaker_id={person['id']} (visits={person['visit_count']})")
        else:
            import hashlib
            virtual_id = int(hashlib.md5(state_current["speaker_name"].lower().encode()).hexdigest()[:8], 16)
            state_current["speaker_id"] = virtual_id
            memory.register_person(virtual_id, state_current["speaker_name"])
            logger.info(f"[BROWSER_MEMORY] Created virtual speaker_id={virtual_id} for '{state_current['speaker_name']}'")
```

with:

```python
    # Browser fallback: resolve speaker_id from the name if voice didn't identify.
    # Shared with the typed-chat path via chat_identity (also applies VIP-alias
    # normalization). See docs/superpowers/specs/2026-07-01-chat-person-memory-design.md
    if state_current["speaker_id"] is None and state_current["speaker_name"]:
        from chat_identity import resolve_chat_identity
        pid, canonical = resolve_chat_identity(state_current["speaker_name"])
        if pid is not None:
            state_current["speaker_id"] = pid
            state_current["speaker_name"] = canonical
            logger.info(f"[BROWSER_MEMORY] Resolved '{canonical}' to speaker_id={pid}")
```

- [ ] **Step 6: Verify — no regression + syntax**

Run: `venv\Scripts\python.exe -m pytest tests/test_command_handlers.py -q`
Expected: PASS (existing tests + the new one).
Run: `venv\Scripts\python.exe -c "import ast; ast.parse(open(r'server/main.py',encoding='utf-8').read())"`
Expected: no syntax error.

- [ ] **Step 7: Commit**

```bash
git add server/command_handlers.py server/main.py tests/test_command_handlers.py
git commit -m "feat(memory): wire typed-name chat to speaker_id; DRY presence_enter via chat_identity"
```

---

## Self-Review

**Spec coverage:**
- `resolve_chat_identity` (VIP-alias normalize + find-or-hash, never raises) → Task 1. ✓
- Typed-name path sets `speaker_id` (the fix) → Task 2 Steps 1-4. ✓
- DRY `presence_enter` via the shared helper → Task 2 Step 5. ✓
- Low-confidence/separate-bucket (hash id, not VIP canonical id) → Task 1 impl (keyed on `_name_hash(canonical)`, never the VIP negative id). ✓
- `client_id` stub reserved → Task 1 signature. ✓
- No regression to voice/presence behavior → Step 5 preserves find-or-hash (now via helper) + Step 6 runs the suite. ✓

**Placeholder scan:** No TBD/TODO; every code step has complete code. The test reuses `_make_state`/`_call` which already exist in `tests/test_command_handlers.py` (verified present).

**Type consistency:** `resolve_chat_identity(name, client_id=None) -> (int|None, str)` used identically in Task 1, the command_handlers wire-up, and the presence_enter wire-up. `_name_hash` returns `int`, matching the existing `presence_enter` formula.
