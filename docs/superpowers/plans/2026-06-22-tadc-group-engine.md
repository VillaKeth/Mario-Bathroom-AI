# TADC Group Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A director-orchestrated engine that lets a guest hold a group conversation with multiple TADC characters (Pomni + Jax to start) who are aware of each other, take turns, and speak in their own voices — on the existing single-sprite display.

**Architecture:** A new `GroupOrchestrator` owns each group turn: a hybrid `Director` picks who speaks, then each speaker generates with its resolved model + its own persona + a shared transcript, is filtered, and is synthesized in its own voice (sequential). Group mode is additive — `config.json mode` selects it; the single-character path is untouched. Per-character `model` overrides + a group `shared_model` give shared / separate / hybrid brains from one config shape.

**Tech Stack:** Python, Ollama (`llm.generate_response(model=)`), GPT-SoVITS/Edge TTS, FastAPI/WebSocket, PyYAML, pytest.

**Branch:** `feat/tadc-group`. **Spec:** `docs/superpowers/specs/2026-06-22-tadc-group-engine-design.md`.

---

## File Structure

| File | Responsibility | New/Modify |
|------|----------------|-----------|
| `shared/character_loader.py` | add optional `self.model` from `character.yaml` | Modify |
| `server/group_config.py` | load `groups/<name>.yaml`; resolve each member's model (`member.model or shared_model`) — pure | New |
| `server/group_state.py` | `GroupSession`: roster + bounded shared transcript (`"<name>: <line>"`) — pure | New |
| `server/group_director.py` | `plan_turn()` hybrid (address fast-path + injected LLM pick + rule fallback) — pure | New |
| `server/group_orchestrator.py` | `handle()`: director → per-speaker prompt+generate+filter → yields spoken lines; injected deps — pure | New |
| `groups/tadc.yaml` | group definition: shared_model, director_model, roster (Pomni, Jax) | New |
| `server/main.py` | startup group load; `mode==group` branch in `_dispatch_user_text`; per-speaker voice swap + synth + tagged send | Modify |
| `config.json` | `mode` + `group` keys | Modify |

**Decomposition:** `group_config`, `group_state`, `group_director`, `group_orchestrator` are pure (deps injected) so they unit-test without booting `server/main.py` (heavy) or hitting Ollama/TTS. `main.py` is the only integration seam, verified live via the debug MCP.

---

## Task 1: CharacterLoader gains an optional `model`

**Files:**
- Modify: `shared/character_loader.py` (after `self.description` at line 56)
- Test: `tests/test_character_model_field.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_character_model_field.py
from shared.character_loader import CharacterLoader


def _write(tmp_path, name, extra=""):
    d = tmp_path / name
    d.mkdir()
    (d / "character.yaml").write_text(
        f"identity:\n  name: {name}\n{extra}", encoding="utf-8")
    return CharacterLoader(str(tmp_path), name)


def test_model_absent_is_none(tmp_path):
    c = _write(tmp_path, "nobody")
    assert c.model is None


def test_model_read_from_yaml_top_level(tmp_path):
    c = _write(tmp_path, "jax", "model: llama3.2:3b\n")
    assert c.model == "llama3.2:3b"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv\Scripts\python.exe -m pytest tests/test_character_model_field.py -v`
Expected: FAIL — `AttributeError: 'CharacterLoader' object has no attribute 'model'`

- [ ] **Step 3: Implement** — add after `self.description = identity.get("description", "")` (line 56):

```python
        # Optional per-character LLM model override (group mode). None -> use the
        # group's shared_model. Read from top-level `model:` or identity.model.
        self.model = self._config.get("model") or identity.get("model")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv\Scripts\python.exe -m pytest tests/test_character_model_field.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add shared/character_loader.py tests/test_character_model_field.py
git commit -m "feat(tadc-group): optional per-character model override on CharacterLoader

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 2: Group config + model resolution

**Files:**
- Create: `server/group_config.py`
- Test: `tests/test_group_config.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_group_config.py
from server.group_config import GroupConfig


def _write(tmp_path, text):
    p = tmp_path / "tadc.yaml"
    p.write_text(text, encoding="utf-8")
    return str(p)


def test_loads_roster_and_models(tmp_path):
    path = _write(tmp_path, """
name: tadc
shared_model: llama3.1:8b
director_model: llama3.2:3b
roster:
  - id: pomni
  - id: jax
    model: qwen2.5:3b
""")
    g = GroupConfig.load(path)
    assert g.name == "tadc"
    assert g.shared_model == "llama3.1:8b"
    assert g.director_model == "llama3.2:3b"
    assert g.member_ids == ["pomni", "jax"]


def test_model_resolution_shared_vs_override(tmp_path):
    path = _write(tmp_path, """
name: tadc
shared_model: llama3.1:8b
director_model: llama3.2:3b
roster:
  - id: pomni
  - id: jax
    model: qwen2.5:3b
""")
    g = GroupConfig.load(path)
    assert g.model_for("pomni") == "llama3.1:8b"   # shared (no override)
    assert g.model_for("jax") == "qwen2.5:3b"      # override
    assert sorted(g.distinct_models()) == ["llama3.1:8b", "qwen2.5:3b"]


def test_director_model_defaults_to_shared_when_absent(tmp_path):
    path = _write(tmp_path, "name: t\nshared_model: m1\nroster:\n  - id: a\n")
    g = GroupConfig.load(path)
    assert g.director_model == "m1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv\Scripts\python.exe -m pytest tests/test_group_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'server.group_config'`

- [ ] **Step 3: Implement**

```python
# server/group_config.py
"""Group definition loader + model resolution. Pure; no FastAPI/Ollama import."""
import yaml


class GroupConfig:
    def __init__(self, name, shared_model, director_model, roster):
        self.name = name
        self.shared_model = shared_model
        self.director_model = director_model or shared_model
        self._roster = roster  # list of {"id": str, "model": str|None}

    @classmethod
    def load(cls, path):
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        roster = [{"id": m["id"], "model": m.get("model")} for m in data.get("roster", [])]
        return cls(
            name=data.get("name", "group"),
            shared_model=data.get("shared_model"),
            director_model=data.get("director_model"),
            roster=roster,
        )

    @property
    def member_ids(self):
        return [m["id"] for m in self._roster]

    def model_for(self, member_id):
        for m in self._roster:
            if m["id"] == member_id:
                return m["model"] or self.shared_model
        return self.shared_model

    def distinct_models(self):
        return sorted({self.model_for(mid) for mid in self.member_ids})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv\Scripts\python.exe -m pytest tests/test_group_config.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add server/group_config.py tests/test_group_config.py
git commit -m "feat(tadc-group): group config loader + shared/override model resolution

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 3: Group session state (roster + shared transcript)

**Files:**
- Create: `server/group_state.py`
- Test: `tests/test_group_state.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_group_state.py
from server.group_state import GroupSession


def test_transcript_appends_and_formats():
    s = GroupSession(member_ids=["pomni", "jax"], maxlen=10)
    s.add_line("Pomni", "Welcome to the circus!")
    s.add_line("Guest", "who are you?")
    assert s.transcript_text() == "Pomni: Welcome to the circus!\nGuest: who are you?"


def test_transcript_is_bounded():
    s = GroupSession(member_ids=["a"], maxlen=2)
    for i in range(5):
        s.add_line("A", f"line{i}")
    assert s.transcript_text() == "A: line3\nA: line4"


def test_least_recent_speaker_for_fallback():
    s = GroupSession(member_ids=["pomni", "jax"], maxlen=10)
    s.add_line("Pomni", "hi")
    # jax has not spoken -> least recent
    assert s.least_recent_speaker() == "jax"
    s.add_line("Jax", "sup")
    # now pomni spoke longest ago
    assert s.least_recent_speaker() == "pomni"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv\Scripts\python.exe -m pytest tests/test_group_state.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'server.group_state'`

- [ ] **Step 3: Implement**

```python
# server/group_state.py
"""Group session state: roster + bounded shared transcript. Pure."""
from collections import deque


class GroupSession:
    def __init__(self, member_ids, maxlen=40):
        self.member_ids = list(member_ids)
        self._lines = deque(maxlen=maxlen)   # (speaker_name, text)
        self._spoke_order = []               # member_id, most-recent last

    def add_line(self, speaker_name, text):
        self._lines.append((speaker_name, text))
        mid = speaker_name.lower()
        if mid in [m.lower() for m in self.member_ids]:
            self._spoke_order = [m for m in self._spoke_order if m != mid] + [mid]

    def transcript_text(self):
        return "\n".join(f"{name}: {text}" for name, text in self._lines)

    def least_recent_speaker(self):
        """Member who spoke longest ago (or never) — used as a director fallback."""
        never = [m for m in self.member_ids if m.lower() not in self._spoke_order]
        if never:
            return never[0]
        return self._spoke_order[0]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv\Scripts\python.exe -m pytest tests/test_group_state.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add server/group_state.py tests/test_group_state.py
git commit -m "feat(tadc-group): GroupSession roster + bounded shared transcript

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 4: Director (hybrid turn planner)

**Files:**
- Create: `server/group_director.py`
- Test: `tests/test_group_director.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_group_director.py
from server.group_director import plan_turn, TurnPlan


ROSTER = {"pomni": "Pomni", "jax": "Jax"}  # id -> display name


def test_addressed_name_fast_path_no_llm():
    called = []
    def llm(_msgs, _model):
        called.append(1)
        return {"text": '{"speakers":["pomni"]}'}
    plan = plan_turn("Hey Jax, what's up?", "", ROSTER, "m", llm)
    assert plan.speakers == ["jax"]
    assert plan.addressed == "jax"
    assert called == []   # fast path skipped the LLM


def test_llm_pick_when_unaddressed():
    def llm(_msgs, _model):
        return {"text": 'sure -> {"speakers":["pomni"],"banter":false}'}
    plan = plan_turn("is this a dream?", "", ROSTER, "m", llm)
    assert plan.speakers == ["pomni"]


def test_garbage_llm_falls_back_to_least_recent():
    def llm(_msgs, _model):
        return {"text": "i have no idea what json is"}
    plan = plan_turn("hello?", "", ROSTER, "m", llm, least_recent="jax")
    assert plan.speakers == ["jax"]


def test_speakers_capped_at_two():
    def llm(_msgs, _model):
        return {"text": '{"speakers":["pomni","jax","pomni"]}'}
    plan = plan_turn("everyone talk", "", ROSTER, "m", llm)
    assert len(plan.speakers) == 2


def test_llm_names_outside_roster_are_dropped():
    def llm(_msgs, _model):
        return {"text": '{"speakers":["caine","pomni"]}'}
    plan = plan_turn("hi", "", ROSTER, "m", llm, least_recent="jax")
    assert plan.speakers == ["pomni"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv\Scripts\python.exe -m pytest tests/test_group_director.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'server.group_director'`

- [ ] **Step 3: Implement**

```python
# server/group_director.py
"""Hybrid turn director: address fast-path + injected-LLM pick + rule fallback.

Pure: the LLM is passed in as `llm_fn(messages, model) -> {"text": str}` so this
unit-tests without Ollama.
"""
import json
import re


class TurnPlan:
    def __init__(self, speakers, addressed=None, banter=False):
        self.speakers = speakers
        self.addressed = addressed
        self.banter = banter


def _extract_json(text):
    m = re.search(r"\{.*\}", text or "", re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def plan_turn(guest_text, transcript, roster, director_model, llm_fn, least_recent=None):
    """roster: {member_id: display_name}. Returns a TurnPlan (speakers are ids)."""
    ids = list(roster.keys())
    low = (guest_text or "").lower()

    # 1) Address fast-path: an explicitly named member answers, no LLM.
    for mid, name in roster.items():
        if re.search(rf"\b{re.escape(name.lower())}\b", low) or re.search(rf"\b{re.escape(mid)}\b", low):
            return TurnPlan(speakers=[mid], addressed=mid)

    # 2) Fast-model pick.
    sys = ("You are the ringmaster director of a group chat. Members: "
           + ", ".join(f"{n} (id={i})" for i, n in roster.items())
           + ". Given the guest message and recent transcript, choose 1 (or 2 for "
           'banter) member IDs to respond. Reply ONLY JSON: {"speakers":["id"],"banter":false}.')
    user = f"Transcript:\n{transcript}\n\nGuest: {guest_text}"
    raw = llm_fn([{"role": "system", "content": sys}, {"role": "user", "content": user}], director_model)
    data = _extract_json(raw.get("text", "")) if isinstance(raw, dict) else None

    speakers = []
    if data and isinstance(data.get("speakers"), list):
        seen = set()
        for s in data["speakers"]:
            s = str(s).lower()
            if s in ids and s not in seen:
                seen.add(s)
                speakers.append(s)
    banter = bool(data.get("banter")) if data else False

    # 3) Fallback: least-recent speaker (or first member).
    if not speakers:
        speakers = [least_recent or ids[0]]

    return TurnPlan(speakers=speakers[:2], addressed=None, banter=banter)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv\Scripts\python.exe -m pytest tests/test_group_director.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add server/group_director.py tests/test_group_director.py
git commit -m "feat(tadc-group): hybrid turn director (address fast-path + LLM pick + fallback)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 5: GroupOrchestrator (turn execution, injected deps)

**Files:**
- Create: `server/group_orchestrator.py`
- Test: `tests/test_group_orchestrator.py`

The orchestrator stays pure: it takes already-loaded members and injected
`generate_fn` / `filter_fn` / `director_fn`, and returns the turn's spoken lines
(speaker id, display name, text, model, voice_config). `main.py` does the actual
TTS + WebSocket send (Task 6).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_group_orchestrator.py
from server.group_orchestrator import GroupOrchestrator
from server.group_state import GroupSession
from server.group_director import TurnPlan


class FakeMember:
    def __init__(self, mid, name, model, vc):
        self.id = mid; self.display_name = name; self.model = model; self.voice_config = vc
    def build_prompt(self):
        return f"You are {self.display_name}."


def _orch(plan_speakers):
    members = {
        "pomni": FakeMember("pomni", "Pomni", "shared", {"v": "p"}),
        "jax": FakeMember("jax", "Jax", "jax-model", {"v": "j"}),
    }
    gen_calls = []
    def generate_fn(messages, model):
        gen_calls.append(model)
        who = messages[0]["content"]
        return {"text": f"line from {who}", "emotion": "happy"}
    def filter_fn(t):
        return t.upper()
    def director_fn(text, transcript, roster):
        return TurnPlan(speakers=plan_speakers)
    sess = GroupSession(member_ids=list(members), maxlen=20)
    orch = GroupOrchestrator(members, sess, generate_fn, filter_fn, director_fn)
    return orch, sess, gen_calls


def test_two_speaker_turn_uses_each_model_and_voice():
    orch, sess, gen_calls = _orch(["pomni", "jax"])
    lines = orch.handle("hello circus")
    assert [l["id"] for l in lines] == ["pomni", "jax"]
    assert gen_calls == ["shared", "jax-model"]           # resolved per member
    assert lines[1]["voice_config"] == {"v": "j"}
    assert lines[0]["text"] == "LINE FROM YOU ARE POMNI."  # filter applied
    # both lines + the guest line are in the shared transcript
    assert "Guest: hello circus" in sess.transcript_text()
    assert "Pomni: LINE FROM YOU ARE POMNI." in sess.transcript_text()


def test_failing_speaker_is_skipped_not_fatal():
    orch, sess, _ = _orch(["pomni", "jax"])
    def boom(messages, model):
        if model == "jax-model":
            raise RuntimeError("ollama down")
        return {"text": "ok", "emotion": "happy"}
    orch._generate_fn = boom
    lines = orch.handle("hi")
    assert [l["id"] for l in lines] == ["pomni"]   # jax skipped, turn survived
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv\Scripts\python.exe -m pytest tests/test_group_orchestrator.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'server.group_orchestrator'`

- [ ] **Step 3: Implement**

```python
# server/group_orchestrator.py
"""Executes a group turn: director picks speakers; each generates with its model
+ persona + the shared transcript, is filtered, and recorded. Pure — TTS/send live
in main.py. Members expose: id, display_name, model, voice_config, build_prompt()."""
import logging

logger = logging.getLogger(__name__)


class GroupOrchestrator:
    def __init__(self, members, session, generate_fn, filter_fn, director_fn):
        self._members = members            # {id: member}
        self._session = session            # GroupSession
        self._generate_fn = generate_fn    # (messages, model) -> {"text","emotion"}
        self._filter_fn = filter_fn        # (text) -> text
        self._director_fn = director_fn     # (guest_text, transcript, roster) -> TurnPlan

    def handle(self, guest_text):
        roster = {mid: m.display_name for mid, m in self._members.items()}
        self._session.add_line("Guest", guest_text)
        transcript = self._session.transcript_text()
        plan = self._director_fn(guest_text, transcript, roster)

        spoken = []
        for mid in plan.speakers:
            member = self._members.get(mid)
            if member is None:
                continue
            try:
                messages = [
                    {"role": "system", "content": member.build_prompt()},
                    {"role": "system", "content":
                        "You are in a group chat with the others. Stay in character; "
                        "react to what was just said. One short reply.\n\n" + self._session.transcript_text()},
                    {"role": "user", "content": guest_text},
                ]
                result = self._generate_fn(messages, member.model)
                text = self._filter_fn((result or {}).get("text", "") or "")
                if not text.strip():
                    continue
                self._session.add_line(member.display_name, text)
                spoken.append({
                    "id": mid, "display_name": member.display_name, "text": text,
                    "model": member.model, "voice_config": member.voice_config,
                    "emotion": (result or {}).get("emotion", "happy"),
                })
            except Exception as e:
                logger.warning(f"[group] speaker {mid} failed, skipping: {e}")
                continue
        return spoken
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv\Scripts\python.exe -m pytest tests/test_group_orchestrator.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add server/group_orchestrator.py tests/test_group_orchestrator.py
git commit -m "feat(tadc-group): GroupOrchestrator turn execution (per-speaker model+voice, skip-on-fail)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 6: Wire group mode into the server

**Files:**
- Modify: `config.json` (add `mode` + `group`)
- Modify: `server/main.py` (startup load + `_dispatch_user_text` branch at line 1954)

- [ ] **Step 1: Add config keys** — in `config.json` add top-level:

```json
  "mode": "single",
  "group": "tadc"
```

- [ ] **Step 2: Build a member adapter + startup load** in `server/main.py` (near where `_character` is loaded). A member wraps a `CharacterLoader` to expose what the orchestrator needs:

```python
import group_config as _group_config_mod
import group_state as _group_state_mod
import group_orchestrator as _group_orch_mod
import group_director as _group_director_mod

# Holds the loaded group (cfg + members + session) or None in single mode. The
# orchestrator/director are rebuilt per dispatch so they bind the live event loop.
_GROUP_CTX = None


class _GroupMember:
    def __init__(self, loader, model):
        self._loader = loader
        self.id = loader.name.lower()
        self.display_name = loader.display_name
        self.model = model
        self.voice_config = loader.voice_config
    def build_prompt(self):
        return self._loader.get_system_prompt({"character_name": self.display_name})


def _load_group():
    """Called once at startup. No-op unless config mode == 'group'."""
    global _GROUP_CTX
    mode = (config.get("mode") or "single").lower()
    if mode != "group":
        return
    gname = config.get("group") or "tadc"
    gpath = os.path.join(os.path.dirname(os.path.dirname(__file__)), "groups", f"{gname}.yaml")
    gcfg = _group_config_mod.GroupConfig.load(gpath)
    members = {}
    for mid in gcfg.member_ids:
        loader = CharacterLoader(_characters_dir, mid)
        members[mid] = _GroupMember(loader, gcfg.model_for(mid))
    session = _group_state_mod.GroupSession(member_ids=list(members), maxlen=40)
    _GROUP_CTX = {"cfg": gcfg, "members": members, "session": session}
    n = len(gcfg.distinct_models())
    if n * 3 > 22:   # ~3GB/model vs 24GB minus TTS headroom — warn, don't block
        logger.warning(f"[group] {n} distinct models (~{n*3}GB) may exceed the 24GB budget")
    logger.info(f"[group] loaded '{gname}' {gcfg.member_ids}; models={gcfg.distinct_models()}")
```

Call `_load_group()` at startup right after the single `_character` is loaded (so single mode is unaffected). For the VRAM budget, the `logger.warning` above fires when distinct models would crowd the GPU.

- [ ] **Step 3: Branch `_dispatch_user_text`** (line 1954). Build the async↔sync bridge, director, and orchestrator inline (binding the live loop), then synth + send each speaker in turn:

```python
async def _dispatch_user_text(text: str):
    if _GROUP_CTX is not None:
        loop = asyncio.get_event_loop()
        gcfg = _GROUP_CTX["cfg"]
        session = _GROUP_CTX["session"]

        def _gen(messages, model):
            # Bridge the orchestrator's sync calls to the async LLM on the live loop.
            fut = asyncio.run_coroutine_threadsafe(
                llm.generate_response(messages, model=model), loop)
            return fut.result(timeout=_LLM_TIMEOUT)

        def _director_fn(t, transcript, roster):
            return _group_director_mod.plan_turn(
                t, transcript, roster, gcfg.director_model, _gen,
                least_recent=session.least_recent_speaker())

        orch = _group_orch_mod.GroupOrchestrator(
            _GROUP_CTX["members"], session, _gen,
            safety_filter.filter_response, _director_fn)

        # Run the (synchronous) orchestrator off the loop so _gen can block on it.
        lines = await loop.run_in_executor(None, orch.handle, text)
        for ln in lines:
            tts.set_voice_config(ln["voice_config"], ln["display_name"])
            audio = await loop.run_in_executor(_tts_executor, lambda t=ln["text"]: tts.synthesize(t))
            await send_response(_active_ws, ln["text"], audio,
                                emotion=ln["emotion"], speaker=ln["display_name"])
        return {"status": "ok", "speakers": [l["id"] for l in lines]}
    # ... existing single-character dispatch unchanged below ...
```

(`send_response` already accepts `**kwargs`; the `speaker` tag rides along in the `mario_response` message. The client showing the speaker's name is a tiny follow-on — the voice is already correct because `set_voice_config` swaps it per line, and `mario_audio_out` records the tagged text for verification.)

- [ ] **Step 4: Syntax check + run the full pure suite** (no live server needed):

Run: `venv\Scripts\python.exe -c "import ast; ast.parse(open('server/main.py',encoding='utf-8').read()); print('OK')"`
Run: `venv\Scripts\python.exe -m pytest tests/test_group_config.py tests/test_group_state.py tests/test_group_director.py tests/test_group_orchestrator.py tests/test_character_model_field.py -q`
Expected: `OK` then all green.

- [ ] **Step 5: Commit**

```bash
git add config.json server/main.py
git commit -m "feat(tadc-group): additive group-mode dispatch (director -> per-speaker voice+send)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 7: `groups/tadc.yaml` + live proof

**Files:**
- Create: `groups/tadc.yaml`

- [ ] **Step 1: Write the group definition**

```yaml
# groups/tadc.yaml — The Amazing Digital Circus ensemble
name: tadc
shared_model: llama3        # dev box; party box: llama3.1:8b
director_model: llama3      # dev box; party box: a fast small model
roster:
  - id: pomni
  - id: jax
```

- [ ] **Step 2: Confirm both characters load** (no live server):

Run: `venv\Scripts\python.exe -c "from shared.character_loader import CharacterLoader as C; [C('characters',n).display_name for n in ('pomni','jax')]; print('both load')"`
Expected: `both load`

- [ ] **Step 3: Live end-to-end** — set `config.json` `mode: group`, launch server + client with `MARIO_DEBUG=1`, then via the debug MCP:
  - `mario_send_text("hey circus, who's there?")` → expect Pomni and/or Jax to take a turn.
  - `mario_send_text("Jax, tell Pomni a joke")` → expect Jax (address fast-path), referencing Pomni.
  - `mario_audio_out(6)` → each line tagged with the speaking character, correct voice (`engine_guess` per their config), `played_ok=True`.
  - `mario_logs(grep="group")` → director picks logged.

- [ ] **Step 4: Commit**

```bash
git add groups/tadc.yaml
git commit -m "feat(tadc-group): tadc group definition (Pomni + Jax) + live proof

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Self-Review Notes

- **Spec coverage:** per-character model + shared/override resolution (T1, T2); director hybrid (T4); roster + shared transcript awareness (T3); turn execution with per-speaker model+voice + skip-on-fail (T5); additive group-mode dispatch + per-speaker voice swap + tagged send (T6); group definition + live proof on existing display (T7). Mode toggle additive (T6). All spec items mapped.
- **Type consistency:** `GroupConfig.model_for/member_ids/distinct_models`, `GroupSession.add_line/transcript_text/least_recent_speaker`, `plan_turn(...)->TurnPlan.speakers`, member interface (`id/display_name/model/voice_config/build_prompt`) are used identically across tasks and tests.
- **Known integration risk (flagged, not a placeholder):** Task 6 bridges sync orchestrator ↔ async `llm.generate_response` via `run_coroutine_threadsafe` + a thread executor; this is the one seam to validate live in Task 7. If the executor bridge is awkward, the fallback is to make the orchestrator `async` and await directly — but that couples it to asyncio, which is why the pure version takes an injected `generate_fn`.
- **Display note (matches spec):** v1 tags each line with the speaker (name + voice + emotion) on the existing display; rich multi-sprite spotlight is the deferred display spec.
