# Rudi Freak Factor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give Rudi an intrinsic, dialable "freak factor" — horny bravado/innuendo with occasional explicit — woven into his existing jokes + LLM chat, strictly per-character so no other character is ever affected.

**Architecture:** A per-character `freak_factor` (0–1, default 0) in `character.yaml` drives (a) a three-bag JokeEngine blend that mixes a new Rudi-only freaky pool into the existing 537 clean jokes, and (b) a level-scaled `[FREAK]` directive injected per-response into Rudi's LLM prompt. A single effective-level helper gates both and can only scale a character that opted in via its yaml default — the live `config_live.json` dial can never flip a clean character freaky.

**Tech Stack:** Python, PyYAML, pytest. Existing modules: `server/joke_engine.py`, `shared/character_loader.py`, `server/idle_behavior.py`, `server/main.py`.

## Global Constraints

- **Per-character isolation is the top requirement.** Freaky output requires ALL of: `personality.freak_factor > 0` in that character's `character.yaml` (opt-in), a `jokes/freaky.yaml` file in that character's dir, and a non-empty `get_freak_prompt`. A character missing any gate stays exactly as clean as today. Only Rudi ships the opt-in + file.
- **The live dial only scales opted-in characters.** `_effective_freak_level` returns `0.0` whenever the character's yaml default `freak_factor <= 0`, regardless of `config_live.json`. A test MUST assert a clean character stays clean with `config_live freak_factor = 1.0`.
- **Content line (both registers):** horny/vulgar/gay-bravado/explicit sex bragging = allowed. Hateful **slurs**, sexual content involving **minors**, **non-consent** = never. Punch at egos/cringe, never at race/gender/orientation.
- **Back-compatible JokeEngine:** existing `JokeEngine(pool, llm_fn=..., llm_chance=...)` calls and the `_draw_from_bag()` method MUST keep working unchanged (freaky defaults empty → identical behavior). All new constructor args are keyword-only with defaults.
- **TTS-safe content:** freaky jokes are short/speakable — no ellipsis (`...`/`…`), no asterisks, no ALL-CAPS words >5 chars, no ASCII art. (`_preclean_tts_text` will still run, but author clean.)
- Logging via `print()`/module logger per existing file conventions. `git add` specific files only (never `-A`; Qdrant `.lock` files must not be committed).

---

### Task 1: Loader — `freak_factor` parse + `get_freak_prompt`

**Files:**
- Modify: `shared/character_loader.py` (personality parse ~line 126; new method near `get_temperament_prompt` ~line 254)
- Test: `tests/test_character_loader.py`

**Interfaces:**
- Consumes: `self.personality` dict (already parsed at line 126).
- Produces:
  - `self.freak_factor: float` — the yaml default (0.0 when absent).
  - `get_freak_prompt(self, level: float) -> str` — `""` when `level <= 0`; otherwise a `[FREAK]` system line escalating with level, always containing the guardrail.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_character_loader.py` (reuse whatever tmp-dir character-building helper the file already uses; if it builds a minimal `character.yaml`, add a `personality: {freak_factor: 0.85}` variant). If no helper exists, write `character.yaml` directly with `identity.name` + `personality.freak_factor`:

```python
def _mk_char(tmp_path, name="rudi", extra=""):
    d = tmp_path / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "character.yaml").write_text(
        f"identity:\n  name: {name}\n{extra}", encoding="utf-8")
    return d

def test_freak_factor_parses_from_yaml(tmp_path):
    from shared.character_loader import CharacterLoader
    _mk_char(tmp_path, "rudi", "personality:\n  freak_factor: 0.85\n")
    c = CharacterLoader(str(tmp_path), "rudi")
    assert abs(c.freak_factor - 0.85) < 1e-9

def test_freak_factor_defaults_zero_when_absent(tmp_path):
    from shared.character_loader import CharacterLoader
    _mk_char(tmp_path, "mario", "")
    c = CharacterLoader(str(tmp_path), "mario")
    assert c.freak_factor == 0.0

def test_get_freak_prompt_zero_is_empty(tmp_path):
    from shared.character_loader import CharacterLoader
    _mk_char(tmp_path, "mario", "")
    c = CharacterLoader(str(tmp_path), "mario")
    assert c.get_freak_prompt(0.0) == ""
    assert c.get_freak_prompt(-1) == ""

def test_get_freak_prompt_escalates_and_keeps_guardrail(tmp_path):
    from shared.character_loader import CharacterLoader
    _mk_char(tmp_path, "rudi", "personality:\n  freak_factor: 0.85\n")
    c = CharacterLoader(str(tmp_path), "rudi")
    low, high = c.get_freak_prompt(0.2), c.get_freak_prompt(0.9)
    assert low and high
    assert "[FREAK]" in high
    # explicit only unlocked at high level
    assert "explicit" in high.lower()
    assert "explicit" not in low.lower()
    # guardrail present at every non-empty tier
    for txt in (low, high):
        assert "slur" in txt.lower()
        assert "minor" in txt.lower() or "underage" in txt.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `venv/Scripts/python.exe -m pytest tests/test_character_loader.py -k freak -v`
Expected: FAIL (`AttributeError: freak_factor` / `get_freak_prompt`).

- [ ] **Step 3: Implement**

In `shared/character_loader.py`, right after the personality parse (the block ending at line 126 `self.personality = self._config.get("personality", {}) or {}`), add:

```python
        # Freak factor (0.0-1.0): intrinsic per-character raunch level. Default 0
        # so EVERY character without it stays clean; only an opted-in character
        # (Rudi) sets it > 0. Drives the [FREAK] prompt directive and the
        # JokeEngine freaky-pool blend. See docs/superpowers/specs/2026-07-08-rudi-freak-factor-design.md
        try:
            self.freak_factor: float = max(0.0, min(1.0, float(self.personality.get("freak_factor", 0.0) or 0.0)))
        except (TypeError, ValueError):
            self.freak_factor = 0.0
```

Add this method near `get_temperament_prompt` (after line 283):

```python
    def get_freak_prompt(self, level: float) -> str:
        """A [FREAK] system directive scaled by `level` (0-1). Returns '' for
        level <= 0, so any clean character (or a dialed-to-0 party) injects
        nothing. Escalates flirty -> horny bravado -> explicit; every non-empty
        tier keeps the hard guardrail (no slurs, no minors, punch at egos not
        identity)."""
        try:
            level = float(level)
        except (TypeError, ValueError):
            return ""
        if level <= 0:
            return ""
        parts = ["[FREAK]: You are shameless, horny, and camp — flirt with the whole "
                 "room, drop suggestive innuendo, brag about your rizz."]
        if level >= 0.5:
            parts.append("Go crude: cocky sexual bravado, dih jokes, gay-bravado camp, "
                         "zero shame. Suggestive is your baseline, not your ceiling.")
        if level >= 0.75:
            parts.append("Fully unhinged is on the table — explicit sexual bragging when "
                         "it lands, no clinical tone, just chaotic confidence.")
        parts.append("HARD LINE: never use slurs; nothing sexual about minors; consent "
                     "only. Punch at egos, bad takes, and cringe — never at someone's "
                     "race, gender, or who they love. Keep it funny, not mean.")
        return " ".join(parts)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `venv/Scripts/python.exe -m pytest tests/test_character_loader.py -k freak -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add shared/character_loader.py tests/test_character_loader.py
git commit -m "feat(freak): loader freak_factor + get_freak_prompt directive"
```

---

### Task 2: JokeEngine — freaky loader, level helper, three-bag blend

**Files:**
- Modify: `server/joke_engine.py`
- Test: `tests/test_joke_engine.py`

**Interfaces:**
- Consumes: `characters/<name>/jokes/freaky.yaml` shape `{bravado: [...], explicit: [...]}`.
- Produces:
  - `load_freaky_jokes(char_dir) -> {"bravado": list, "explicit": list}` (empty lists if file missing/malformed).
  - `effective_freak_level(base_default, live_override=None) -> float` (pure; 0.0 if base <= 0; else clamped live override or base).
  - `JokeEngine(pool, freaky_pool=None, llm_fn=None, llm_chance=0.10, freak_level_fn=None, explicit_ratio=0.25, rng=None)` — three no-repeat bags; `next_joke()` = 10% LLM, else level-blended clean/bravado/explicit. `_draw_from_bag()` preserved (clean bag).

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_joke_engine.py`:

```python
from server.joke_engine import load_freaky_jokes, effective_freak_level

def test_load_freaky_missing_returns_empty(tmp_path):
    d = tmp_path / "mario"; d.mkdir()
    fp = load_freaky_jokes(str(d))
    assert fp == {"bravado": [], "explicit": []}

def test_load_freaky_reads_both_lanes(tmp_path):
    d = tmp_path / "rudi"; (d / "jokes").mkdir(parents=True)
    (d / "jokes" / "freaky.yaml").write_text(
        yaml.safe_dump({"bravado": ["b1", "b2"], "explicit": ["e1"]}), encoding="utf-8")
    fp = load_freaky_jokes(str(d))
    assert fp["bravado"] == ["b1", "b2"] and fp["explicit"] == ["e1"]

def test_effective_level_zero_when_opt_out():
    assert effective_freak_level(0.0, 1.0) == 0.0      # clean char, dial cranked -> still 0
    assert effective_freak_level(0.0, None) == 0.0

def test_effective_level_scales_opted_in():
    assert effective_freak_level(0.85, None) == 0.85   # no override -> yaml default
    assert effective_freak_level(0.85, 0.3) == 0.3     # live override scales it
    assert effective_freak_level(0.85, "junk") == 0.85 # bad override -> default
    assert effective_freak_level(0.85, 5) == 1.0       # clamp

def test_no_freaky_pool_draws_only_clean():
    eng = JokeEngine(["c1", "c2"], freak_level_fn=lambda: 1.0, rng=random.Random(1))
    assert all(eng.next_joke() in ("c1", "c2") for _ in range(50))

def test_level_one_draws_only_freaky():
    fp = {"bravado": ["b1", "b2"], "explicit": ["e1", "e2"]}
    eng = JokeEngine(["c1"], freaky_pool=fp, freak_level_fn=lambda: 1.0,
                     explicit_ratio=0.5, rng=random.Random(3))
    got = [eng.next_joke() for _ in range(60)]
    assert "c1" not in got
    assert any(g in ("b1", "b2") for g in got)
    assert any(g in ("e1", "e2") for g in got)

def test_level_fn_exception_is_clean():
    def boom(): raise RuntimeError("x")
    fp = {"bravado": ["b1"], "explicit": ["e1"]}
    eng = JokeEngine(["c1"], freaky_pool=fp, freak_level_fn=boom, rng=random.Random(1))
    assert all(eng.next_joke() == "c1" for _ in range(20))

def test_draw_from_bag_still_clean_only():
    eng = JokeEngine(["c1", "c2"], freaky_pool={"bravado": ["b"], "explicit": ["e"]},
                     rng=random.Random(1))
    assert all(eng._draw_from_bag() in ("c1", "c2") for _ in range(20))
```

- [ ] **Step 2: Run to verify fail**

Run: `venv/Scripts/python.exe -m pytest tests/test_joke_engine.py -v`
Expected: FAIL (import errors / new tests fail).

- [ ] **Step 3: Implement**

Rewrite `server/joke_engine.py` keeping `load_curated_jokes` as-is and adding:

```python
def load_freaky_jokes(char_dir: str):
    """Return {'bravado': [...], 'explicit': [...]} from <char_dir>/jokes/freaky.yaml.
    Missing/malformed file -> empty lists (character stays clean)."""
    out = {"bravado": [], "explicit": []}
    path = os.path.join(char_dir, "jokes", "freaky.yaml")
    if not os.path.isfile(path):
        return out
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        for lane in ("bravado", "explicit"):
            vals = data.get(lane) or []
            if isinstance(vals, list):
                out[lane] = [str(v) for v in vals if str(v).strip()]
    except Exception:
        return {"bravado": [], "explicit": []}
    return out


def effective_freak_level(base_default, live_override=None):
    """Effective 0-1 freak level. Opt-in ONLY: base_default (the character's yaml
    freak_factor) <= 0 -> 0.0 no matter what the live override says, so a clean
    character can never be dialed freaky. Otherwise the live override (if numeric)
    scales it, clamped to [0,1]."""
    try:
        base = float(base_default or 0.0)
    except (TypeError, ValueError):
        base = 0.0
    if base <= 0.0:
        return 0.0
    if live_override is None:
        lvl = base
    else:
        try:
            lvl = float(live_override)
        except (TypeError, ValueError):
            lvl = base
    return max(0.0, min(1.0, lvl))
```

Replace the `JokeEngine` class with a three-bag version (preserve `_draw_from_bag`):

```python
class JokeEngine:
    """Serves jokes: 10% live-LLM, else a level-blended shuffle-bag draw across
    clean / freaky-bravado / freaky-explicit pools. freak level 0 (default for
    every non-opted-in character) => only the clean pool is ever drawn."""

    def __init__(self, pool, freaky_pool=None, llm_fn=None, llm_chance=0.10,
                 freak_level_fn=None, explicit_ratio=0.25, rng=None):
        fp = freaky_pool or {}
        self._llm_fn = llm_fn
        self._llm_chance = llm_chance
        self._freak_level_fn = freak_level_fn
        self._explicit_ratio = explicit_ratio
        self._rng = rng or random.Random()
        self._lock = threading.Lock()
        # Each bag is an independent no-repeat shuffle-bag over its source list.
        self._bags = {
            "clean":    {"src": list(pool or []),          "bag": [], "last": None},
            "bravado":  {"src": list(fp.get("bravado") or []),  "bag": [], "last": None},
            "explicit": {"src": list(fp.get("explicit") or []), "bag": [], "last": None},
        }

    def _draw(self, name):
        with self._lock:
            st = self._bags[name]
            src = st["src"]
            if not src:
                return None
            refilled = not st["bag"]
            if refilled:
                st["bag"] = list(src)
                self._rng.shuffle(st["bag"])
            choice = st["bag"].pop()
            if refilled and choice == st["last"] and len(src) > 1:
                idx = self._rng.randrange(len(st["bag"]))
                st["bag"].append(choice)
                choice = st["bag"].pop(idx)
            st["last"] = choice
            return choice

    def _draw_from_bag(self):
        """Back-compat: draw from the clean pool only."""
        return self._draw("clean")

    def _freak_level(self):
        if self._freak_level_fn is None:
            return 0.0
        try:
            return max(0.0, min(1.0, float(self._freak_level_fn())))
        except Exception:
            return 0.0

    def _draw_blended(self):
        have_freaky = bool(self._bags["bravado"]["src"] or self._bags["explicit"]["src"])
        level = self._freak_level() if have_freaky else 0.0
        if level > 0 and self._rng.random() < level:
            if self._bags["explicit"]["src"] and self._rng.random() < self._explicit_ratio:
                out = self._draw("explicit")
                if out:
                    return out
            out = self._draw("bravado")
            if out:
                return out
        return self._draw("clean")

    def next_joke(self):
        if self._llm_fn is not None and self._rng.random() < self._llm_chance:
            try:
                out = self._llm_fn()
                if out and out.strip():
                    return out.strip()
            except Exception:
                pass
        return self._draw_blended()
```

- [ ] **Step 4: Run to verify pass**

Run: `venv/Scripts/python.exe -m pytest tests/test_joke_engine.py -v`
Expected: PASS (all original + new tests).

- [ ] **Step 5: Commit**

```bash
git add server/joke_engine.py tests/test_joke_engine.py
git commit -m "feat(freak): JokeEngine three-bag blend + freaky loader + level gate"
```

---

### Task 3: Freaky content — `characters/rudi/jokes/freaky.yaml`

**Files:**
- Create: `characters/rudi/jokes/freaky.yaml`
- Test: `tests/test_freaky_content.py`

**Interfaces:**
- Consumes: nothing (data file).
- Produces: `{bravado: [...], explicit: [...]}` loadable by `load_freaky_jokes`.

**Content spec (author to these rules — this is a WRITING task):**
- `bravado`: **≥ 120** items. Horny bravado + innuendo, camp, clever. Rudi's deadpan-then-unhinged voice. Examples of the register (write NEW ones, don't copy verbatim):
  - "Straight? Buddy, I bend more than your WiFi signal."
  - "I'd call myself a top but I can't even commit to a text back."
  - "Not saying I'm packing, but the bathroom scale asked for a two-person estimate."
  - "I put the 'bi' in 'bio break', keep up."
  - "My rizz has a 4G connection and your whole personality is buffering."
- `explicit`: **≥ 40** items. Fully-unhinged sexual bragging, still comedic and short, says the thing without a clinical tone. Cruder/rawer than bravado.
- **Every item (both lanes):** one or two sentences, TTS-safe (no `...`, no `…`, no `*`, no ALL-CAPS words >5 chars, no emoji), speakable in a bathroom bit. Punch at egos/cringe, camp horny energy — NEVER slurs, minors, or non-consent.
- Aim for variety (no two near-duplicates) so the shuffle-bag stays fresh across a party.

- [ ] **Step 1: Write the failing test**

Create `tests/test_freaky_content.py`:

```python
import os, yaml
from server.joke_engine import load_freaky_jokes

RUDI = os.path.join("characters", "rudi")

def test_rudi_freaky_file_exists_and_loads():
    fp = load_freaky_jokes(RUDI)
    assert len(fp["bravado"]) >= 120, f"bravado too small: {len(fp['bravado'])}"
    assert len(fp["explicit"]) >= 40, f"explicit too small: {len(fp['explicit'])}"

def test_rudi_freaky_is_tts_safe():
    fp = load_freaky_jokes(RUDI)
    all_lines = fp["bravado"] + fp["explicit"]
    for ln in all_lines:
        assert "..." not in ln and "…" not in ln, f"ellipsis: {ln}"
        assert "*" not in ln, f"asterisk: {ln}"
        # no shouty tokens (>5-char all-caps words read robotic in TTS)
        for w in ln.split():
            stripped = "".join(ch for ch in w if ch.isalpha())
            assert not (len(stripped) > 5 and stripped.isupper()), f"ALLCAPS: {ln}"

def test_rudi_freaky_no_duplicates():
    fp = load_freaky_jokes(RUDI)
    all_lines = [l.strip().lower() for l in fp["bravado"] + fp["explicit"]]
    assert len(all_lines) == len(set(all_lines)), "duplicate freaky lines"
```

- [ ] **Step 2: Run to verify fail**

Run: `venv/Scripts/python.exe -m pytest tests/test_freaky_content.py -v`
Expected: FAIL (file missing → counts 0).

- [ ] **Step 3: Author `characters/rudi/jokes/freaky.yaml`**

Write the YAML with `bravado:` (≥120) and `explicit:` (≥40) lists per the content spec above. Author genuinely funny, on-voice, varied lines. Keep each ≤ ~20 words.

- [ ] **Step 4: Run to verify pass**

Run: `venv/Scripts/python.exe -m pytest tests/test_freaky_content.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add characters/rudi/jokes/freaky.yaml tests/test_freaky_content.py
git commit -m "feat(freak): Rudi freaky joke pool (bravado + explicit lanes)"
```

---

### Task 4: IdleBehavior — load + wire the freaky pool

**Files:**
- Modify: `server/idle_behavior.py` (`__init__` signature ~line 52; joke-engine construction ~lines 77-84)
- Test: `tests/test_idle_jokes.py`

**Interfaces:**
- Consumes: `load_freaky_jokes`, the new `JokeEngine` args from Task 2.
- Produces: `IdleBehavior(character_loader=None, joke_llm_fn=None, joke_llm_chance=0.10, freak_level_fn=None, explicit_ratio=0.25)` — builds the JokeEngine with the character's freaky pool + level fn. No freaky file / no level fn → clean (unchanged behavior).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_idle_jokes.py` (use the file's existing fake-loader pattern; a fake loader needs `.name`, `.get_idle_messages()`, and `.character_dir`). If the freaky pool must come from disk, point `character_dir` at a tmp dir containing `jokes/freaky.yaml`:

```python
def test_idle_routes_freaky_when_level_high(tmp_path):
    import yaml as _y
    from server.idle_behavior import IdleBehavior
    (tmp_path / "jokes").mkdir()
    (tmp_path / "jokes" / "freaky.yaml").write_text(
        _y.safe_dump({"bravado": ["BRAV1", "BRAV2"], "explicit": ["EXPL1"]}), encoding="utf-8")

    class FakeLoader:
        name = "rudi"
        character_dir = str(tmp_path)
        def get_idle_messages(self): return {"jokes": ["CLEAN1", "CLEAN2"]}
    ib = IdleBehavior(character_loader=FakeLoader(), freak_level_fn=lambda: 1.0,
                      explicit_ratio=0.5)
    got = [ib.get_joke() for _ in range(40)]
    assert any(g in ("BRAV1", "BRAV2", "EXPL1") for g in got)
    assert "CLEAN1" not in got and "CLEAN2" not in got  # level 1.0 -> all freaky

def test_idle_clean_when_no_level_fn(tmp_path):
    import yaml as _y
    from server.idle_behavior import IdleBehavior
    (tmp_path / "jokes").mkdir()
    (tmp_path / "jokes" / "freaky.yaml").write_text(
        _y.safe_dump({"bravado": ["BRAV1"], "explicit": ["EXPL1"]}), encoding="utf-8")
    class FakeLoader:
        name = "rudi"
        character_dir = str(tmp_path)
        def get_idle_messages(self): return {"jokes": ["CLEAN1", "CLEAN2"]}
    ib = IdleBehavior(character_loader=FakeLoader())  # no freak_level_fn -> level 0
    got = [ib.get_joke() for _ in range(40)]
    assert all(g in ("CLEAN1", "CLEAN2") for g in got)
```

- [ ] **Step 2: Run to verify fail**

Run: `venv/Scripts/python.exe -m pytest tests/test_idle_jokes.py -k freaky -v`
Expected: FAIL (`TypeError: unexpected keyword 'freak_level_fn'`).

- [ ] **Step 3: Implement**

In `server/idle_behavior.py`, update the import (line 9) to include `load_freaky_jokes`:

```python
from server.joke_engine import JokeEngine, load_curated_jokes, load_freaky_jokes
```

Change the `__init__` signature (line 52):

```python
    def __init__(self, character_loader=None, joke_llm_fn=None, joke_llm_chance=0.10,
                 freak_level_fn=None, explicit_ratio=0.25):
```

Replace the joke-engine construction (lines 81-84) with:

```python
        _char_dir = getattr(character_loader, "character_dir", None) or getattr(character_loader, "_char_dir", None)
        _freaky = {"bravado": [], "explicit": []}
        if _char_dir:
            self._jokes = load_curated_jokes(str(_char_dir), fallback=self._jokes)
            _freaky = load_freaky_jokes(str(_char_dir))
        self._joke_engine = JokeEngine(
            self._jokes, freaky_pool=_freaky, llm_fn=joke_llm_fn,
            llm_chance=joke_llm_chance, freak_level_fn=freak_level_fn,
            explicit_ratio=explicit_ratio)
```

- [ ] **Step 4: Run to verify pass**

Run: `venv/Scripts/python.exe -m pytest tests/test_idle_jokes.py -v`
Expected: PASS (new + existing idle-joke tests).

- [ ] **Step 5: Commit**

```bash
git add server/idle_behavior.py tests/test_idle_jokes.py
git commit -m "feat(freak): IdleBehavior loads + wires Rudi freaky pool into JokeEngine"
```

---

### Task 5: main.py gate + prompt injection + config_live + guardrail fix

**Files:**
- Modify: `server/main.py` (new `_effective_freak_level` near `_joke_llm_fn` ~line 3790; two `IdleBehavior(...)` calls ~lines 906, 3018; two chat temperament sites ~2013 and ~4628; `_joke_llm_fn` ctx ~3811; idle-chatter ctx ~3852)
- Modify: `config_live.json` (add `freak_factor`)
- Modify: `characters/rudi/prompts/system_prompt.md` (fix corrupted guardrail lines 5, 11)
- Modify: `characters/rudi/character.yaml` (add `personality.freak_factor`)
- Test: `tests/test_freak_integration.py`

**Interfaces:**
- Consumes: `effective_freak_level` (Task 2), `get_freak_prompt` (Task 1), the new IdleBehavior arg (Task 4), module globals `_character` + `live_config`.
- Produces: `_effective_freak_level() -> float`; freak directive on chat + idle ctx; JokeEngine fed the live level.

- [ ] **Step 1: Write the failing test**

Create `tests/test_freak_integration.py` (pure-helper level — does NOT import `server.main`):

```python
from server.joke_engine import effective_freak_level, JokeEngine
from shared.character_loader import CharacterLoader

def _mk(tmp_path, name, extra="", freaky=None):
    import yaml
    d = tmp_path / name; (d / "jokes").mkdir(parents=True)
    (d / "character.yaml").write_text(f"identity:\n  name: {name}\n{extra}", encoding="utf-8")
    if freaky:
        (d / "jokes" / "freaky.yaml").write_text(yaml.safe_dump(freaky), encoding="utf-8")
    return d

def test_clean_character_unreachable_by_dial(tmp_path):
    # Mario: freak_factor default 0, no freaky.yaml. Live dial cranked to 1.0.
    _mk(tmp_path, "mario", "")
    c = CharacterLoader(str(tmp_path), "mario")
    lvl = effective_freak_level(c.freak_factor, 1.0)      # config_live freak_factor = 1.0
    assert lvl == 0.0
    assert c.get_freak_prompt(lvl) == ""
    eng = JokeEngine(["clean"], freaky_pool={"bravado": ["B"], "explicit": ["E"]},
                     freak_level_fn=lambda: lvl)
    assert all(eng.next_joke() == "clean" for _ in range(30))

def test_rudi_reachable_and_scaled(tmp_path):
    _mk(tmp_path, "rudi", "personality:\n  freak_factor: 0.85\n",
        freaky={"bravado": ["B1", "B2"], "explicit": ["E1"]})
    c = CharacterLoader(str(tmp_path), "rudi")
    assert effective_freak_level(c.freak_factor, None) == 0.85     # yaml default
    assert effective_freak_level(c.freak_factor, 0.0) == 0.0       # party dialed him clean
    assert c.get_freak_prompt(0.85) != ""
```

- [ ] **Step 2: Run to verify fail**

Run: `venv/Scripts/python.exe -m pytest tests/test_freak_integration.py -v`
Expected: FAIL until Task 1 + 2 are present (they are) — this test should actually PASS already if Tasks 1-2 landed. If so, treat Step 1 as a regression guard and proceed; the main.py wiring below is verified by parse + the audio pass in Task 6.

- [ ] **Step 3: Implement main.py wiring**

(a) Add the import for `effective_freak_level` — find the existing `from server.joke_engine import ...` if present, else add near the other server imports:

```python
from server.joke_engine import effective_freak_level
```

(b) Add the helper next to `_joke_llm_fn` (after line 3788):

```python
def _effective_freak_level() -> float:
    """Live per-character freak level for jokes + prompt. 0.0 for any character
    whose yaml freak_factor is 0 (opt-in only), else the config_live override
    scales it. See docs/superpowers/specs/2026-07-08-rudi-freak-factor-design.md."""
    try:
        base = getattr(_character, "freak_factor", 0.0)
    except Exception:
        base = 0.0
    return effective_freak_level(base, live_config.get("freak_factor"))
```

(c) Both `IdleBehavior(...)` constructions (lines ~906 and ~3018) — add the level fn:

```python
    idle_behavior = IdleBehavior(character_loader=_character, joke_llm_fn=_joke_llm_fn,
                                  joke_llm_chance=_joke_chance,
                                  freak_level_fn=_effective_freak_level)
```

(d) Chat site 1 (after line 2013, inside the temperament `try`, right after the temperament append):

```python
            _freak = _character.get_freak_prompt(_effective_freak_level())
            if _freak:
                ctx.append({"role": "system", "content": _freak})
```

(e) Chat site 2 (after line 4628 where `_temperament` is appended) — mirror the same three lines using `_character.get_freak_prompt(_effective_freak_level())`.

(f) `_joke_llm_fn` ctx (line 3811-3817) — insert a freak system message after the idle-prompt one:

```python
        ctx = [
            {"role": "system", "content": _get_idle_prompt()},
        ]
        _freak = _character.get_freak_prompt(_effective_freak_level())
        if _freak:
            ctx.append({"role": "system", "content": _freak})
        ctx.append({"role": "user", "content": (
            "Tell ONE short, original, in-character joke. One or two sentences. "
            "No preamble, just the joke."
        )})
```

(g) Idle-chatter ctx (after line 3852) — same freak append right after the `_get_idle_prompt()` system message:

```python
        _freak = _character.get_freak_prompt(_effective_freak_level())
        if _freak:
            ctx.append({"role": "system", "content": _freak})
```

(h) `config_live.json` — add (Rudi's live dial default; the effective-level opt-in gate still protects other characters):

```json
  "freak_factor": 0.85,
```

(i) `characters/rudi/character.yaml` — add under a `personality:` block (the file has none today; add it, e.g. above `memory:`):

```yaml
personality:
  # Intrinsic raunch level (0-1). Rudi is Bad Rudi — horny bravado + occasional
  # explicit. Per-character: no other character has this, so none is affected.
  # config_live.json freak_factor can dial this down live (0 = clean) but can
  # never make a character with freak_factor 0 freaky.
  freak_factor: 0.85
```

(j) `characters/rudi/prompts/system_prompt.md` guardrail fix — replace the corrupted lines:
- Line 5 `"IMPORTANT: You punch at their race, gender, or who they love."` →
  `"IMPORTANT: You NEVER punch down at someone's race, gender, or who they love — you roast egos, bad takes, and cringe."`
- Line 11 `"Slurs as much as possible."` → `"Never use slurs."`

- [ ] **Step 4: Verify**

Run:
```
venv/Scripts/python.exe -m pytest tests/test_freak_integration.py tests/test_joke_engine.py tests/test_character_loader.py tests/test_idle_jokes.py -q
venv/Scripts/python.exe -c "import ast; ast.parse(open('server/main.py',encoding='utf-8').read()); print('main.py OK')"
venv/Scripts/python.exe -c "import json; json.load(open('config_live.json')); print('config_live OK')"
venv/Scripts/python.exe -c "import yaml; yaml.safe_load(open('characters/rudi/character.yaml',encoding='utf-8')); print('rudi yaml OK')"
```
Expected: tests PASS; all three parse checks print OK.

- [ ] **Step 5: Commit**

```bash
git add server/main.py config_live.json characters/rudi/character.yaml characters/rudi/prompts/system_prompt.md tests/test_freak_integration.py
git commit -m "feat(freak): main.py level gate + per-response directive + Rudi opt-in + guardrail fix"
```

---

### Task 6: Full regression + audio verification

**Files:** none (verification only).

- [ ] **Step 1: Full joke/idle/loader suite**

Run: `venv/Scripts/python.exe -m pytest tests/test_joke_engine.py tests/test_freaky_content.py tests/test_idle_jokes.py tests/test_character_loader.py tests/test_freak_integration.py tests/test_command_handlers.py -q`
Expected: all PASS.

- [ ] **Step 2: Audio verification (MANDATORY — `.claude/rules/testing.md`)**

With the server running as Rudi and a client connected:
1. Trigger jokes repeatedly (idle + "tell me a joke"); confirm freaky lines appear and each plays `_play_wav: playing` → `_play_wav: done` in Rudi's voice, spoken text matching the bubble.
2. Set `config_live.json freak_factor: 0.0`, reload; confirm jokes/chat go clean (no freaky lines) — the live dial works.
3. Switch to a clean character (Mario/Freddy) with `config_live freak_factor` still non-zero; confirm ZERO freaky content and ZERO wrong-character leak in BOTH text and audio across: identity, "tell me a joke", 2-min idle.

- [ ] **Step 3: Note results** in the progress ledger; any failure → systematic-debugging, not a guess.

---

## Notes for the executor

- Tasks 1-2 are pure/testable and unblock everything. Task 3 is a writing task (author to the content spec + rules). Task 5 is the integration seam — its safety test (clean character unreachable) is the single most important assertion in the plan.
- If a later task reveals the `_draw_from_bag` alias or any existing test breaks, that's a Task-2 regression — fix there, don't paper over it downstream.
- Do NOT touch other characters' files. Only `characters/rudi/**` gets freaky content.
