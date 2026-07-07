# Rudi Mega-Joke System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Rudi's 20-joke index cycle with a curated ~1,000-joke pool (multi-source generated + LLM-judged), served via a 90% cached / 10% live-LLM hybrid, woven into idle chatter and TTS-precached.

**Architecture:** A dedicated `server/joke_engine.py` owns joke selection (shuffle-bag over the pool + a 10% live-LLM roll with graceful fallback). A loader reads `characters/<char>/jokes/curated.yaml` (falling back to the existing `idle/messages.yaml` `jokes:` block). `idle_behavior.py` delegates all joke picks to the engine so on-request and idle jokes share the 90/10 behavior. An offline build pipeline (`scripts/jokes/`) generates candidates from 6 sources, Claude-judges them, and writes `curated.yaml`.

**Tech Stack:** Python 3.11, PyYAML, existing `llm_router` (Ollama), `fastembed` (already used for Qdrant) for semantic dedupe, `pytest`, `mcp_chatgpt` browser batch for GPT/Gemini/Grok text gen, existing `tts` precache.

## Global Constraints

- Print-logging only in `command_handlers.py` (no logger import there); `idle_behavior.py` uses its module `logger`.
- WebSocket response type is `"mario_response"` (unchanged; jokes flow through existing send paths).
- No ellipsis (`...`) in any hardcoded string that reaches TTS — use commas/periods.
- Character content stays character-agnostic: joke pools load from `characters/<name>/…`, never hardcoded. Default pools empty; Rudi is the first consumer.
- `git add <specific files>` only (never `-A`); never add Qdrant `.lock` files.
- Commit trailer: `Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>`
- New config keys live in `config_live.json` (hot-reloadable) with a code default; document in `.claude/CLAUDE.md` Key Config Fields.
- Build artifacts (`candidates.jsonl`, `scored.jsonl`) are git-ignored; only `curated.yaml` is committed.

## File Structure

- Create `server/joke_engine.py` — `JokeEngine` (shuffle-bag + 90/10 + LLM) + `load_curated_jokes()`. One responsibility: pick the next joke.
- Modify `server/idle_behavior.py` — construct + delegate to `JokeEngine`; route idle joke category through it.
- Modify `server/main.py` — build the LLM joke callback + inject into `IdleBehavior`/`JokeEngine`.
- Create `scripts/jokes/generate_candidates.py` — orchestrate the 6 source generators → `candidates.jsonl`.
- Create `scripts/jokes/sources.py` — per-source generator functions (claude/online/ollama/browser).
- Create `scripts/jokes/judge_jokes.py` — score + semantic-dedupe + top-N → `curated.yaml`.
- Create `characters/rudi/jokes/curated.yaml` — build output (committed).
- Modify `server/tts.py` — extend idle precache to include the curated joke pool.
- Modify `.gitignore` — ignore `characters/*/jokes/candidates.jsonl`, `scored.jsonl`.
- Tests under `tests/`.

---

## Phase 1 — Runtime + Loader (ships value with today's 20 jokes)

### Task 1: Curated-joke loader

**Files:**
- Create: `server/joke_engine.py`
- Test: `tests/test_joke_engine.py`

**Interfaces:**
- Produces: `load_curated_jokes(char_dir: str, fallback: list[str] | None = None) -> list[str]` — returns the `jokes:` list from `<char_dir>/jokes/curated.yaml` if present and non-empty, else `fallback or []`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_joke_engine.py
import os, yaml
from server.joke_engine import load_curated_jokes

def test_load_curated_prefers_curated_file(tmp_path):
    cdir = tmp_path / "rudi"; (cdir / "jokes").mkdir(parents=True)
    (cdir / "jokes" / "curated.yaml").write_text(
        yaml.safe_dump({"jokes": ["a", "b", "c"]}), encoding="utf-8")
    assert load_curated_jokes(str(cdir), fallback=["old"]) == ["a", "b", "c"]

def test_load_curated_falls_back_when_missing(tmp_path):
    cdir = tmp_path / "rudi"; cdir.mkdir()
    assert load_curated_jokes(str(cdir), fallback=["old1", "old2"]) == ["old1", "old2"]

def test_load_curated_falls_back_when_empty(tmp_path):
    cdir = tmp_path / "rudi"; (cdir / "jokes").mkdir(parents=True)
    (cdir / "jokes" / "curated.yaml").write_text(yaml.safe_dump({"jokes": []}), encoding="utf-8")
    assert load_curated_jokes(str(cdir), fallback=["old"]) == ["old"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/Scripts/python.exe -m pytest tests/test_joke_engine.py -k load_curated -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'server.joke_engine'`

- [ ] **Step 3: Write minimal implementation**

```python
# server/joke_engine.py
import os
import yaml

def load_curated_jokes(char_dir: str, fallback=None):
    """Return the curated joke list from <char_dir>/jokes/curated.yaml, or fallback."""
    fallback = fallback or []
    path = os.path.join(char_dir, "jokes", "curated.yaml")
    if not os.path.isfile(path):
        return fallback
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        jokes = data.get("jokes") or []
        return jokes if jokes else fallback
    except Exception:
        return fallback
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/Scripts/python.exe -m pytest tests/test_joke_engine.py -k load_curated -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add server/joke_engine.py tests/test_joke_engine.py
git commit -m "feat(jokes): curated.yaml loader with idle/messages fallback"
```

---

### Task 2: Shuffle-bag (no-repeat-until-exhausted)

**Files:**
- Modify: `server/joke_engine.py`
- Test: `tests/test_joke_engine.py`

**Interfaces:**
- Produces: `JokeEngine(pool: list[str], llm_fn=None, llm_chance: float = 0.10, rng: random.Random | None = None)` with `_draw_from_bag() -> str | None` — draws without replacement, reshuffling when the bag empties; returns `None` only if the pool is empty.

- [ ] **Step 1: Write the failing test**

```python
import random
from server.joke_engine import JokeEngine

def test_bag_exhausts_before_repeat():
    pool = [f"j{i}" for i in range(10)]
    eng = JokeEngine(pool, rng=random.Random(1))
    first10 = [eng._draw_from_bag() for _ in range(10)]
    assert sorted(first10) == sorted(pool)          # all 10 used, no repeat
    assert eng._draw_from_bag() in pool             # 11th reshuffles, still valid

def test_bag_empty_pool_returns_none():
    assert JokeEngine([], rng=random.Random(1))._draw_from_bag() is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/Scripts/python.exe -m pytest tests/test_joke_engine.py -k bag -v`
Expected: FAIL — `ImportError: cannot import name 'JokeEngine'`

- [ ] **Step 3: Write minimal implementation** (append to `server/joke_engine.py`)

```python
import random

class JokeEngine:
    """Serves jokes: 90% shuffle-bag over the pool, 10% live-LLM (Task 3)."""

    def __init__(self, pool, llm_fn=None, llm_chance=0.10, rng=None):
        self._pool = list(pool or [])
        self._llm_fn = llm_fn
        self._llm_chance = llm_chance
        self._rng = rng or random.Random()
        self._bag = []

    def _draw_from_bag(self):
        if not self._pool:
            return None
        if not self._bag:
            self._bag = list(self._pool)
            self._rng.shuffle(self._bag)
        return self._bag.pop()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/Scripts/python.exe -m pytest tests/test_joke_engine.py -k bag -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add server/joke_engine.py tests/test_joke_engine.py
git commit -m "feat(jokes): shuffle-bag no-repeat-until-exhausted draw"
```

---

### Task 3: 90/10 hybrid `next_joke()` with LLM fallback

**Files:**
- Modify: `server/joke_engine.py`
- Test: `tests/test_joke_engine.py`

**Interfaces:**
- Produces: `JokeEngine.next_joke() -> str | None` — with probability `llm_chance` and a non-None `llm_fn`, returns `llm_fn()`; on `llm_fn` exception/None/empty, falls back to the bag. Otherwise draws from the bag.

- [ ] **Step 1: Write the failing test**

```python
def test_next_joke_uses_llm_when_roll_hits():
    eng = JokeEngine(["cached"], llm_fn=lambda: "fresh-llm", llm_chance=1.0,
                     rng=random.Random(1))
    assert eng.next_joke() == "fresh-llm"

def test_next_joke_uses_bag_when_roll_misses():
    eng = JokeEngine(["cached"], llm_fn=lambda: "fresh-llm", llm_chance=0.0,
                     rng=random.Random(1))
    assert eng.next_joke() == "cached"

def test_next_joke_llm_failure_falls_back_to_bag():
    def boom(): raise RuntimeError("llm down")
    eng = JokeEngine(["cached"], llm_fn=boom, llm_chance=1.0, rng=random.Random(1))
    assert eng.next_joke() == "cached"

def test_next_joke_split_is_roughly_90_10():
    eng = JokeEngine(["c"], llm_fn=lambda: "L", llm_chance=0.10, rng=random.Random(7))
    draws = [eng.next_joke() for _ in range(2000)]
    llm = draws.count("L")
    assert 120 < llm < 280           # ~10% of 2000, wide band for RNG
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/Scripts/python.exe -m pytest tests/test_joke_engine.py -k next_joke -v`
Expected: FAIL — `AttributeError: 'JokeEngine' object has no attribute 'next_joke'`

- [ ] **Step 3: Write minimal implementation** (append method to `JokeEngine`)

```python
    def next_joke(self):
        if self._llm_fn is not None and self._rng.random() < self._llm_chance:
            try:
                out = self._llm_fn()
                if out and out.strip():
                    return out.strip()
            except Exception:
                pass  # fall through to the cached bag
        return self._draw_from_bag()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/Scripts/python.exe -m pytest tests/test_joke_engine.py -k next_joke -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add server/joke_engine.py tests/test_joke_engine.py
git commit -m "feat(jokes): 90/10 cached-vs-LLM next_joke with graceful fallback"
```

---

### Task 4: Wire `JokeEngine` into `idle_behavior`

**Files:**
- Modify: `server/idle_behavior.py:76` (pool load) and `:283-288` (`get_joke`); `:247` (idle rotation)
- Test: `tests/test_idle_jokes.py`

**Interfaces:**
- Consumes: `JokeEngine`, `load_curated_jokes` (Tasks 1-3).
- Produces: `IdleBehavior.__init__(character_loader=None, joke_llm_fn=None, joke_llm_chance=0.10)`; `IdleBehavior.get_joke()` delegates to the engine; idle "jokes" category picks route through `get_joke()`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_idle_jokes.py
from server.idle_behavior import IdleBehavior

class _Loader:
    name = "Rudi"
    def __init__(self, jokes): self._j = jokes
    def get_idle_messages(self): return {"jokes": self._j}

def test_get_joke_delegates_to_engine_bag(monkeypatch, tmp_path):
    # No curated.yaml -> falls back to loader jokes; llm_chance 0 -> always bag
    ib = IdleBehavior(_Loader(["j1", "j2"]), joke_llm_chance=0.0)
    got = {ib.get_joke() for _ in range(20)}
    assert got == {"j1", "j2"}          # only pool jokes, both appear

def test_get_joke_empty_pool_returns_none():
    ib = IdleBehavior(_Loader([]), joke_llm_chance=0.0)
    assert ib.get_joke() is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/Scripts/python.exe -m pytest tests/test_idle_jokes.py -v`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'joke_llm_chance'`

- [ ] **Step 3: Write minimal implementation**

In `server/idle_behavior.py`, add import near the top:
```python
from server.joke_engine import JokeEngine, load_curated_jokes
```

Change `__init__` signature (line 50):
```python
    def __init__(self, character_loader=None, joke_llm_fn=None, joke_llm_chance=0.10):
```

After the pool resolution block (after line 88, where `self._jokes` is set), add:
```python
        # Curated pool supersedes idle/messages.yaml jokes when present.
        _char_dir = getattr(character_loader, "char_dir", None) or getattr(
            character_loader, "_char_dir", None)
        if _char_dir:
            self._jokes = load_curated_jokes(str(_char_dir), fallback=self._jokes)
        self._joke_engine = JokeEngine(
            self._jokes, llm_fn=joke_llm_fn, llm_chance=joke_llm_chance)
```

Replace `get_joke` (lines 283-288) with:
```python
    def get_joke(self) -> str:
        return self._joke_engine.next_joke()
```

Route the idle "jokes" category through the engine — change line 247 from
`("jokes", list(self._jokes)),` to keep the pool for rotation weighting, but when
that category is chosen, serve via the engine. After `cat_name, options = random.choice(_categories)` (line 251) add:
```python
        if cat_name == "jokes":
            j = self._joke_engine.next_joke()
            if j:
                return j
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/Scripts/python.exe -m pytest tests/test_idle_jokes.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Run the full idle suite to check no regressions**

Run: `venv/Scripts/python.exe -m pytest tests/ -k idle -v`
Expected: PASS (existing idle tests still green)

- [ ] **Step 6: Commit**

```bash
git add server/idle_behavior.py tests/test_idle_jokes.py
git commit -m "feat(jokes): idle_behavior delegates joke picks to JokeEngine (90/10)"
```

---

### Task 5: Inject the live-LLM joke callback in `main.py`

**Files:**
- Modify: `server/main.py` (where `IdleBehavior(...)` is constructed) and add `joke_llm_chance` to `config_live.json`
- Test: `tests/test_idle_jokes.py`

**Interfaces:**
- Consumes: existing `llm_router` (quality/fast model call) and the active character system prompt.
- Produces: a `joke_llm_fn() -> str` closure passed to `IdleBehavior`, and `joke_llm_chance` read from live config (default 0.10).

- [ ] **Step 1: Write the failing test** (callback shape only — no live LLM)

```python
def test_joke_llm_fn_wired(monkeypatch):
    calls = {"n": 0}
    def fake_llm(): calls["n"] += 1; return "generated joke"
    ib = IdleBehavior(_Loader(["c"]), joke_llm_fn=fake_llm, joke_llm_chance=1.0)
    assert ib.get_joke() == "generated joke"
    assert calls["n"] == 1
```

- [ ] **Step 2: Run test to verify it fails, then passes** (it passes once Task 4 lands; this documents the contract)

Run: `venv/Scripts/python.exe -m pytest tests/test_idle_jokes.py -k llm_fn_wired -v`
Expected: PASS (contract already satisfied by Task 4's signature)

- [ ] **Step 3: Implement the callback in `server/main.py`**

Find the `IdleBehavior(` construction. Add above it:
```python
    def _make_joke_llm_fn():
        def _gen():
            prompt = ("Tell ONE short, original, in-character joke. "
                      "One or two sentences. No preamble, just the joke.")
            # Uses the active character system prompt already held by the router.
            return llm_router.generate_quick(prompt, system=_active_system_prompt())
        return _gen
    _joke_chance = live_config.get("joke_llm_chance", 0.10)
```

Update the construction to:
```python
    idle_behavior = IdleBehavior(
        character_loader=_character,
        joke_llm_fn=_make_joke_llm_fn(),
        joke_llm_chance=_joke_chance,
    )
```

(If `llm_router.generate_quick`/`_active_system_prompt` names differ, use the
existing quick-generate helper the greeting flow uses; grep `llm_router.` in
`main.py` for the exact call and match it.)

- [ ] **Step 4: Add config key + doc**

In `config_live.json` add `"joke_llm_chance": 0.10`. In `.claude/CLAUDE.md` Key Config Fields add:
`- `joke_llm_chance` (config_live, code default 0.10) — probability a joke is generated live by the LLM vs pulled from the cached pool.`

- [ ] **Step 5: Manual smoke + commit**

Run the server, trigger "tell me a joke" ~20×, confirm variety + occasional novel joke in logs (`mario says:`). Then:
```bash
git add server/main.py config_live.json .claude/CLAUDE.md
git commit -m "feat(jokes): wire live-LLM joke callback + joke_llm_chance config"
```

---

## Phase 2 — Build Pipeline (produce curated.yaml)

### Task 6: Candidate generation harness (6 sources → candidates.jsonl)

**Files:**
- Create: `scripts/jokes/sources.py`, `scripts/jokes/generate_candidates.py`
- Modify: `.gitignore`
- Test: `tests/test_joke_build.py`

**Interfaces:**
- Produces: `write_candidate(fp, text, source)` (hash-dedup at write); `run_source(name, n) -> list[dict]` per source; a CLI `generate_candidates.py --char rudi --per-source 1000 --sources claude,online,ollama,gpt,gemini,grok`.
- Candidate line: `{"id": sha1(text)[:12], "text": str, "source": str}`.

- [ ] **Step 1: Write the failing test** (harness + dedup, source fns mocked)

```python
# tests/test_joke_build.py
import json
from scripts.jokes.sources import write_candidate, candidate_id

def test_write_candidate_dedups_by_hash(tmp_path):
    fp = tmp_path / "cand.jsonl"
    with open(fp, "a", encoding="utf-8") as f:
        assert write_candidate(f, "same joke", "claude", seen=(s := set())) is True
        assert write_candidate(f, "same joke", "ollama", seen=s) is False   # dup text
    lines = [json.loads(x) for x in open(fp, encoding="utf-8")]
    assert len(lines) == 1 and lines[0]["source"] == "claude"

def test_candidate_id_stable():
    assert candidate_id("abc") == candidate_id("abc")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/Scripts/python.exe -m pytest tests/test_joke_build.py -k candidate -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.jokes.sources'`

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/jokes/sources.py
import hashlib, json

def candidate_id(text: str) -> str:
    return hashlib.sha1(text.strip().lower().encode("utf-8")).hexdigest()[:12]

def write_candidate(fp, text: str, source: str, seen: set) -> bool:
    text = (text or "").strip()
    if not text:
        return False
    cid = candidate_id(text)
    if cid in seen:
        return False
    seen.add(cid)
    fp.write(json.dumps({"id": cid, "text": text, "source": source}) + "\n")
    return True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/Scripts/python.exe -m pytest tests/test_joke_build.py -k candidate -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Implement the source generators** (operational — no unit test; each returns `list[str]`)

Add to `scripts/jokes/sources.py`:
- `gen_ollama(n)` — loop `llm_router`/Ollama with the Rudi voice-profile prompt (§3 of spec), ~25 jokes/call, parse a numbered list.
- `gen_browser(provider, n)` — reuse `mcp_chatgpt` batch text mode: send "Write 50 original jokes in this voice: <profile>" per call, parse. `provider ∈ {chatgpt, gemini, grok}`. TEXT — not image-capped.
- `gen_online(n)` — pull from a public joke corpus/API (e.g. an offline joke dataset shipped to `scripts/jokes/data/` or a public API), then a light Rudi-voice rewrite pass via `llm_router`.
- `gen_claude(n)` — read from `scripts/jokes/data/claude_jokes.txt` (authored separately by Claude in batches; one joke per line).

`generate_candidates.py` wires `--sources` → the matching `gen_*`, streams each into `characters/<char>/jokes/candidates.jsonl` via `write_candidate` with a shared `seen` set.

Add to `.gitignore`:
```
characters/*/jokes/candidates.jsonl
characters/*/jokes/scored.jsonl
```

- [ ] **Step 6: Commit**

```bash
git add scripts/jokes/sources.py scripts/jokes/generate_candidates.py tests/test_joke_build.py .gitignore
git commit -m "feat(jokes): candidate generation harness (6 sources, hash-dedup)"
```

---

### Task 7: Judge → dedupe → top-1000 → curated.yaml

**Files:**
- Create: `scripts/jokes/judge_jokes.py`
- Create: `characters/rudi/jokes/curated.yaml` (build output)
- Test: `tests/test_joke_build.py`

**Interfaces:**
- Produces: `select_top(scored: list[dict], n: int, long_cap: float = 0.15) -> list[str]` — rank by `funny*2 + rudi_fit`, keep top `n` passing `tts_ok`, ≤ `long_cap` share of long (>200-char) jokes; `semantic_dedupe(items, threshold) -> list` collapsing near-duplicates via fastembed cosine.
- CLI `judge_jokes.py --char rudi --top 1000` reads `candidates.jsonl`, LLM-judges each, writes `scored.jsonl` + `jokes/curated.yaml`.

- [ ] **Step 1: Write the failing test** (pure selection logic; judging + embeddings mocked)

```python
def test_select_top_ranks_and_caps_long():
    scored = [
        {"text": "short A", "funny": 9, "rudi_fit": 9, "tts_ok": True},
        {"text": "short B", "funny": 2, "rudi_fit": 2, "tts_ok": True},
        {"text": "x"*250,   "funny": 10, "rudi_fit": 10, "tts_ok": True},   # long
        {"text": "bad tts", "funny": 10, "rudi_fit": 10, "tts_ok": False},  # excluded
    ]
    from scripts.jokes.judge_jokes import select_top
    top = select_top(scored, n=2, long_cap=0.5)
    assert "bad tts" not in top                 # tts_ok filter
    assert "short A" in top                      # high score kept
    assert len(top) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/Scripts/python.exe -m pytest tests/test_joke_build.py -k select_top -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.jokes.judge_jokes'`

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/jokes/judge_jokes.py
def _score(j): return j["funny"] * 2 + j["rudi_fit"]

def select_top(scored, n, long_cap=0.15):
    usable = [j for j in scored if j.get("tts_ok")]
    usable.sort(key=_score, reverse=True)
    out, longs, long_limit = [], 0, int(n * long_cap)
    for j in usable:
        is_long = len(j["text"]) > 200
        if is_long and longs >= long_limit:
            continue
        out.append(j["text"]); longs += is_long
        if len(out) >= n:
            break
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/Scripts/python.exe -m pytest tests/test_joke_build.py -k select_top -v`
Expected: PASS

- [ ] **Step 5: Implement judging + dedupe + CLI** (operational)

Add to `judge_jokes.py`:
- `judge_one(text) -> dict` — `llm_router` prompt returning strict JSON `{"funny":1-10,"rudi_fit":1-10,"tts_ok":bool}` against the §3 voice profile; parse defensively (default to `funny=0` on parse failure so it drops out).
- `semantic_dedupe(items, threshold=0.90)` — embed texts with the existing fastembed model (`memory_semantic`), greedily drop any item whose cosine similarity to an already-kept item exceeds `threshold`.
- CLI: read `candidates.jsonl` → `judge_one` each (batch, resumable via `scored.jsonl`) → `semantic_dedupe` → `select_top(..., 1000)` → write `characters/rudi/jokes/curated.yaml` as `{"jokes": [...]}`.

- [ ] **Step 6: Run the pipeline for real, then commit the pool**

```bash
venv/Scripts/python.exe scripts/jokes/generate_candidates.py --char rudi --per-source 1000 --sources claude,online,ollama,gpt,gemini,grok
venv/Scripts/python.exe scripts/jokes/judge_jokes.py --char rudi --top 1000
```
Verify `characters/rudi/jokes/curated.yaml` has ~1000 jokes, spot-check funny + on-voice. Then:
```bash
git add scripts/jokes/judge_jokes.py characters/rudi/jokes/curated.yaml tests/test_joke_build.py
git commit -m "feat(jokes): LLM judge + semantic dedupe -> curated 1000-joke pool"
```

---

## Phase 3 — TTS Precache

### Task 8: Precache the curated joke pool

**Files:**
- Modify: `server/tts.py` (idle precache worker, near `_start_idle_precache`)
- Test: `tests/test_tts_router.py` (extend) or manual audio verification

**Interfaces:**
- Consumes: `load_curated_jokes` (Task 1), existing `_idle_behavior_ref` in `tts.py`.
- Produces: joke pool phrases added to the background idle-precache list.

- [ ] **Step 1: Extend the idle precache worker**

In `server/tts.py` `_idle_cache_worker` (where `all_idle` is assembled from `_idle_behavior_ref._mumbles` + `_dj_announcements`), add the joke pool:
```python
        if _idle_behavior_ref is not None:
            all_idle += list(getattr(_idle_behavior_ref, "_jokes", []))
```
(Jokes precache at the same low priority, yielding to user TTS — no separate path.)

- [ ] **Step 2: Manual audio verification (mandatory per `.claude/rules/testing.md`)**

Start the server as Rudi. Confirm in client logs: a pool joke plays `_play_wav: playing` → `_play_wav: done`, and a 10%-path live joke synthesizes on demand + plays. Confirm ZERO Mario references and the voice is Rudi's.

- [ ] **Step 3: Commit**

```bash
git add server/tts.py
git commit -m "feat(jokes): precache curated joke pool for instant idle audio"
```

---

## Self-Review

- **Spec coverage:** §4A generation → Task 6; §4B judge → Task 7; §4C storage/loader → Tasks 1, 7; §4D runtime 90/10 → Tasks 2-3; §4E idle → Task 4; §4F precache → Task 8; live-LLM wiring → Task 5. All covered.
- **Placeholders:** source generators + judge LLM call + main.py callback are marked "operational" with concrete instructions (prompt text, parse rules, file paths); no bare TODOs. The one soft spot — exact `llm_router` quick-generate helper name — is handled with a grep-and-match instruction because it varies by codebase state.
- **Type consistency:** `JokeEngine`, `next_joke()`, `_draw_from_bag()`, `load_curated_jokes()`, `write_candidate()`, `candidate_id()`, `select_top()` names are consistent across tasks. `curated.yaml` schema `{"jokes": [...]}` is identical in Tasks 1, 4, 7.
- **Scope:** two subsystems (runtime Phase 1, build Phase 2-3). Phase 1 ships value alone; kept in one plan since they share the `curated.yaml` interface.
