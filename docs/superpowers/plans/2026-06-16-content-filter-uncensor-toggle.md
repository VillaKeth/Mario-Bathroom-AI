# Content-Filter Uncensor Toggle — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make a character uncensored and more dynamic via a **per-character** safety toggle in `character.yaml`, with slur-blocking as an independent tier — without a model swap and without breaking the other ~45 characters.

**Architecture:** Add `safety: {enabled, block_slurs}` to `character.yaml`. `CharacterLoader` parses it (defaults **ON** = fail-safe). At startup `main.py` pushes the two flags into `safety_filter` via `set_safety_config()`. `safety_filter` splits its blocklist into a **slur tier** (gated by `_BLOCK_SLURS`) and a **content tier** (gated by `_SAFETY_ENABLED`); `mario_prompt` reads `is_safety_enabled()` to decide whether to inject BANNED-TOPICS guardrails. Defaults preserve today's behavior, so every existing test stays green; only the opted-out character (March) changes.

**Tech Stack:** Python 3, pytest, PyYAML, Ollama (model unchanged: `llama3`/`gemma3`).

**Rollback point:** git tag `pre-uncensor-overhaul` (commit `6db7c8c`). `git checkout pre-uncensor-overhaul` or `git reset --hard pre-uncensor-overhaul`.

---

## Scope

**This plan = content censorship layers (1–5 minus model).** Locked owner decisions baked in:

- **Per-character toggle, not a global gut.** `character.yaml → safety.enabled` + `safety.block_slurs`. Missing block defaults to **filtered** (`enabled: true`), so only opted-out characters become uncensored. The other ~45 characters are untouched.
- **Slurs are their own tier, above general content.** `block_slurs` is independent of `enabled` — slurs stay blocked even when general filtering is off (this bot speaks responses **out loud** in a room). March: `enabled: false, block_slurs: true`.
- **No model swap (Layer 5 deferred).** Keep `llama3`/`gemma3`. This caps how uncensored the character can get — accepted. The aligned model still self-refuses hardcore content; revisit only if needed.
- **Layer 3:** drop `max_roasts`, keep de-escalation, gate `banned_topics` on the toggle.
- **Layer 4:** relax brevity (`mario_prompt.py:124`), raise the hard cap 300 → 500.

**NOT in this plan — Phase 2, separate plan:** Layer 0, the ~45 unguarded keyword interceptors in `command_handlers.py` (word-count guards + content-triggers-to-LLM-hints). See `docs/content-filter-audit-and-uncensor-plan.md` → "Layer 0". That is a bigger, independent subsystem; it gets its own plan after this lands.

---

## File Structure

| File | Change | Responsibility |
|------|--------|----------------|
| `shared/character_loader.py` | Modify (~after line 120) | Parse `safety:` block → `safety_enabled`, `safety_block_slurs` (default True/True) |
| `server/safety_filter.py` | Modify (lines 11–22, 28–34, 118–127, 164–184, 134) | Split slur/content tiers; module flags + `set_safety_config()` + `is_safety_enabled()`; gate both filters |
| `server/main.py` | Modify (after line 705) | Wire `set_safety_config(...)` from `_character` at startup |
| `server/mario_prompt.py` | Modify (124, 302–314) | Gate BANNED TOPICS on toggle; drop max_roasts; keep de-escalation; relax brevity |
| `characters/march7th/character.yaml` | Modify (append) | Opt March into uncensored + slur guard |
| `tests/test_safety_toggle.py` | Create | All new behavior: loader parse, toggle filtering, slur tier, guardrail injection, raised cap |
| `tests/test_edge_cases.py` | Modify (line 1013) | Update cap assertion 310 → 510 |

**Why existing tests survive:** `safety_filter` defaults to `_SAFETY_ENABLED=True, _BLOCK_SLURS=True`, which is exactly today's behavior. `test_unsafe_profanity`, `test_unsafe_violence`, `test_redirect_*`, `test_unicode_bypass_attempt` all assert the default-on path and keep passing. `night_progression` guardrail dict is left intact (only the *injection* in `mario_prompt` changes), so `test_night_progression` stays green. The only existing test that changes is the cap assertion (Task 5).

---

## Task 1: CharacterLoader parses the `safety:` block

**Files:**
- Modify: `shared/character_loader.py` (insert after line 120)
- Test: `tests/test_safety_toggle.py` (create)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_safety_toggle.py`:

```python
"""Per-character safety toggle + slur tier (uncensor overhaul, 2026-06-16)."""
import os

from shared.character_loader import CharacterLoader


def _write_char(tmp_path, name, extra_yaml=""):
    """Write a minimal valid character.yaml and return a loaded CharacterLoader."""
    cdir = tmp_path / name
    cdir.mkdir()
    (cdir / "character.yaml").write_text(
        f"identity:\n  name: {name}\n{extra_yaml}", encoding="utf-8"
    )
    return CharacterLoader(str(tmp_path), name)


class TestCharacterSafetyConfig:
    def test_safety_defaults_on_when_absent(self, tmp_path):
        char = _write_char(tmp_path, "nobody")
        assert char.safety_enabled is True
        assert char.safety_block_slurs is True

    def test_safety_can_be_fully_disabled(self, tmp_path):
        char = _write_char(tmp_path, "wild",
                            "safety:\n  enabled: false\n  block_slurs: false\n")
        assert char.safety_enabled is False
        assert char.safety_block_slurs is False

    def test_block_slurs_independent_of_enabled(self, tmp_path):
        char = _write_char(tmp_path, "marchlike",
                            "safety:\n  enabled: false\n  block_slurs: true\n")
        assert char.safety_enabled is False
        assert char.safety_block_slurs is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `venv/Scripts/python.exe -m pytest tests/test_safety_toggle.py::TestCharacterSafetyConfig -v`
Expected: FAIL with `AttributeError: 'CharacterLoader' object has no attribute 'safety_enabled'`.

- [ ] **Step 3: Write minimal implementation**

In `shared/character_loader.py`, immediately after line 120 (`self.lore_file: str = ...`) and before the blank line preceding `# Log load summary`, insert:

```python

        # Parse safety — per-character content gating. Defaults ON (filtered) so
        # any character WITHOUT a safety block stays safe; a character opts OUT
        # of content filtering explicitly. block_slurs is an INDEPENDENT tier: it
        # can stay True while enabled is False (slurs blocked, everything else
        # allowed) — enforced in server/safety_filter.py.
        safety = self._config.get("safety", {}) or {}
        self.safety_enabled: bool = bool(safety.get("enabled", True))
        self.safety_block_slurs: bool = bool(safety.get("block_slurs", True))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `venv/Scripts/python.exe -m pytest tests/test_safety_toggle.py::TestCharacterSafetyConfig -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add shared/character_loader.py tests/test_safety_toggle.py
git commit -m "feat(safety): per-character safety config in CharacterLoader

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 2: safety_filter — slur/content tiers + runtime toggle

**Files:**
- Modify: `server/safety_filter.py` (lines 11–22, after 33, 118–127, 164–184)
- Test: `tests/test_safety_toggle.py` (add classes)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_safety_toggle.py`:

```python
from server.safety_filter import filter_response, check_input, set_safety_config


class TestSafetyToggle:
    def teardown_method(self):
        # CRITICAL: module-global flags persist across tests in one pytest
        # process. Reset to fail-safe defaults so later tests see filtering ON.
        set_safety_config(True, True)

    def test_default_blocks_profanity_input(self):
        set_safety_config(True, True)
        assert check_input("what the fuck")["safe"] is False

    def test_disabled_allows_profanity_input(self):
        set_safety_config(False, True)
        assert check_input("what the fuck")["safe"] is True

    def test_disabled_allows_profanity_output(self):
        set_safety_config(False, True)
        assert "fuck" in filter_response("oh fuck yeah").lower()

    def test_content_passes_while_slurs_blocked(self):
        # The exact March config: content off, slurs on.
        set_safety_config(False, True)
        out = filter_response("this damn party is fucking wild")
        assert "fucking" in out.lower()
        assert "damn" in out.lower()

    def test_slur_blocked_in_output_even_when_disabled(self):
        set_safety_config(False, True)
        out = filter_response("you r3tard")
        assert "r3tard" not in out
        assert "****" in out

    def test_slur_blocked_in_input_even_when_disabled(self):
        set_safety_config(False, True)
        assert check_input("you r3tard")["safe"] is False

    def test_everything_off_allows_slurs(self):
        set_safety_config(False, False)
        assert check_input("you r3tard")["safe"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `venv/Scripts/python.exe -m pytest tests/test_safety_toggle.py::TestSafetyToggle -v`
Expected: FAIL with `ImportError: cannot import name 'set_safety_config'`.

- [ ] **Step 3: Write minimal implementation**

**3a.** In `server/safety_filter.py`, replace lines 11–22 (the `# Words/phrases...` comment through the `BLOCKED_RE = [...]` line) with:

```python
# Slur patterns — an INDEPENDENT tier. These stay blocked even when a character
# disables general content filtering (safety.enabled: false), because this bot
# speaks responses out loud in a room. Gated by _BLOCK_SLURS.
SLUR_PATTERNS = [
    r'\b(n[i1]gg|f[a4]gg?|r[e3]tard)\b',
]

# General content patterns — profanity, violence, hate, drugs, assault. Gated by
# _SAFETY_ENABLED; a character with safety.enabled: false lets all of these
# through to the LLM and out unredacted.
CONTENT_PATTERNS = [
    r'\b(fuck|shit|damn|ass|bitch|bastard|dick|cock|pussy)\b',
    r'\b(kill|murder|suicide|die|death|dying)\b(?!.*(?:mushroom|bowser|goomba|game|laughing|funny|comedy))',
    r'\b(racist|sexist|homophob|transphob|bigot)\b',
    r'\b(nazi|hitler|holocaust)\b',
    r'\b(drugs?|cocaine|heroin|meth|weed)\b(?!.*mushroom)',
    r'\b(rape|molest|abuse|assault)\b',
]

SLUR_RE = [re.compile(p, re.IGNORECASE | re.MULTILINE) for p in SLUR_PATTERNS]
CONTENT_RE = [re.compile(p, re.IGNORECASE | re.MULTILINE) for p in CONTENT_PATTERNS]

# Backwards-compat: anything importing the old names gets the union.
BLOCKED_PATTERNS = SLUR_PATTERNS + CONTENT_PATTERNS
BLOCKED_RE = SLUR_RE + CONTENT_RE

# Per-character toggles, set at startup by main.py from character.yaml. Default
# ON (filtered) so a misconfigured / parentless boot fails safe.
_SAFETY_ENABLED = True   # gates CONTENT_RE + MILD_REPLACEMENTS + banned topics
_BLOCK_SLURS = True      # independent gate for SLUR_RE
```

**3b.** Immediately after the `set_character()` function (after its body ends, ~line 33), add:

```python
def set_safety_config(enabled: bool, block_slurs: bool = True):
    """Set per-character content gating (called at startup from character.yaml).

    enabled=False lets all CONTENT_PATTERNS + MILD_REPLACEMENTS through (the
    'uncensored' character). block_slurs is independent: when True, SLUR_PATTERNS
    stay blocked regardless of `enabled`.
    """
    global _SAFETY_ENABLED, _BLOCK_SLURS
    _SAFETY_ENABLED = bool(enabled)
    _BLOCK_SLURS = bool(block_slurs)
    if DEBUG_SAFETY:
        logger.info(f"[DEBUG_SAFETY] set_safety_config: enabled={_SAFETY_ENABLED} block_slurs={_BLOCK_SLURS}")


def is_safety_enabled() -> bool:
    """True when general content filtering is active for the current character.
    Used by mario_prompt to decide whether to inject BANNED TOPICS guardrails."""
    return _SAFETY_ENABLED
```

**3c.** In `filter_response()`, replace the block at lines 118–127 (`# Check for blocked patterns` through the `MILD_REPLACEMENTS` loop) with:

```python
    # Slur tier — always applied when _BLOCK_SLURS (independent of _SAFETY_ENABLED).
    if _BLOCK_SLURS:
        for pattern in SLUR_RE:
            if pattern.search(text):
                if DEBUG_SAFETY:
                    logger.warning("[DEBUG_SAFETY] Blocked slur pattern in response, sanitizing")
                text = pattern.sub("****", text)

    # General content tier + mild replacements — only when safety enabled.
    if _SAFETY_ENABLED:
        for pattern in CONTENT_RE:
            if pattern.search(text):
                if DEBUG_SAFETY:
                    logger.warning("[DEBUG_SAFETY] Blocked content pattern in response, sanitizing")
                text = pattern.sub("****", text)
        for pattern, replacement in MILD_REPLACEMENTS.items():
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
```

**3d.** In `check_input()`, replace the loop at lines 164–184 (`# Check for harmful content` through the final `return {"safe": True, "redirect": None}`) with:

```python
    # Assemble the active blocklist: slurs if _BLOCK_SLURS, content if _SAFETY_ENABLED.
    active = []
    if _BLOCK_SLURS:
        active += SLUR_RE
    if _SAFETY_ENABLED:
        active += CONTENT_RE

    for pattern in active:
        if pattern.search(lower):
            if DEBUG_SAFETY:
                logger.warning("[DEBUG_SAFETY] check_input: unsafe input detected")
            import random
            with _redirect_lock:
                available = [r for r in REDIRECT_RESPONSES if r not in _recent_redirects]
                if not available:
                    _recent_redirects.clear()
                    available = REDIRECT_RESPONSES
                redirect = random.choice(available)
                _recent_redirects.append(redirect)
                if len(_recent_redirects) > _MAX_REDIRECT_HISTORY:
                    _recent_redirects.pop(0)
            return {"safe": False, "redirect": redirect}

    return {"safe": True, "redirect": None}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `venv/Scripts/python.exe -m pytest tests/test_safety_toggle.py::TestSafetyToggle tests/test_edge_cases.py -v`
Expected: new toggle tests pass; existing `test_edge_cases` safety tests (`test_unsafe_profanity`, `test_redirect_varies`, `test_unicode_bypass_attempt`, etc.) still pass because defaults are unchanged. The only failure here should be `test_truncation_still_works` ONLY IF Task 5 ran first — it has not, so it still passes at cap 300.

- [ ] **Step 5: Commit**

```bash
git add server/safety_filter.py tests/test_safety_toggle.py
git commit -m "feat(safety): runtime toggle + independent slur tier in safety_filter

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 3: Wire the toggle at character startup

**Files:**
- Modify: `server/main.py` (after line 705)

No isolated unit test — this is boot wiring; it's covered by the live verification in Task 7. Add a startup log line for observability.

- [ ] **Step 1: Add the wiring**

In `server/main.py`, immediately after line 705 (`safety_filter.set_character(_character.name, _character.display_name)`), insert:

```python
    safety_filter.set_safety_config(_character.safety_enabled, _character.safety_block_slurs)
    logger.info(
        f"[CHARACTER] Safety: content_filter="
        f"{'ON' if _character.safety_enabled else 'OFF'}, "
        f"block_slurs={_character.safety_block_slurs}"
    )
```

- [ ] **Step 2: Verify it imports/boots clean**

Run: `venv/Scripts/python.exe -c "import ast; ast.parse(open('server/main.py', encoding='utf-8').read()); print('main.py parses OK')"`
Expected: `main.py parses OK`.

- [ ] **Step 3: Commit**

```bash
git add server/main.py
git commit -m "feat(safety): push per-character safety flags into filter at startup

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 4: Layer 3 — gate BANNED TOPICS, drop max_roasts, keep de-escalation

**Files:**
- Modify: `server/mario_prompt.py` (lines 302–314)
- Test: `tests/test_safety_toggle.py` (add class)

`night_progression.get_guardrails()` is left untouched (its dict still carries `banned_topics`/`max_roasts_per_guest`, so `test_night_progression` stays green). Only the *injection* changes.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_safety_toggle.py`:

```python
class TestGuardrailInjection:
    def teardown_method(self):
        set_safety_config(True, True)

    def _build_text(self):
        from server import mario_prompt
        pm = {"guardrails": {
            "banned_topics": ["politics", "religion"],
            "max_roasts_per_guest": 3,
            "de_escalation_triggers": ["stop", "too far"],
        }}
        msgs = mario_prompt.build_context(phase_modifier=pm)
        return " ".join(m["content"] for m in msgs)

    def test_banned_topics_present_when_safety_on(self):
        set_safety_config(True, True)
        assert "BANNED TOPICS" in self._build_text()

    def test_banned_topics_absent_when_safety_off(self):
        set_safety_config(False, True)
        assert "BANNED TOPICS" not in self._build_text()

    def test_max_roasts_never_injected(self):
        set_safety_config(True, True)
        assert "Maximum roasts" not in self._build_text()

    def test_de_escalation_kept_when_safety_off(self):
        set_safety_config(False, True)
        assert "de-escalate" in self._build_text()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `venv/Scripts/python.exe -m pytest tests/test_safety_toggle.py::TestGuardrailInjection -v`
Expected: `test_banned_topics_absent_when_safety_off` and `test_max_roasts_never_injected` FAIL (current code always injects both).

- [ ] **Step 3: Write minimal implementation**

In `server/mario_prompt.py`, replace the guardrails block at lines 302–314 with:

```python
        # Inject guardrails as system message
        guardrails = phase_modifier.get("guardrails")
        if guardrails:
            import safety_filter  # local import (no module-load cycle); see line 395
            rails = []
            # BANNED TOPICS only when this character keeps content filtering on.
            # Uncensored characters (safety.enabled: false) get no topic bans.
            banned = guardrails.get("banned_topics", [])
            if banned and safety_filter.is_safety_enabled():
                rails.append(f"BANNED TOPICS (never mention): {', '.join(banned)}")
            # max_roasts dropped — it capped playful banter and fought dynamism.
            # de-escalation kept: backing off when a guest taps out is basic courtesy.
            de_esc = guardrails.get("de_escalation_triggers", [])
            if de_esc:
                rails.append(f"If guest says any of [{', '.join(de_esc)}], immediately de-escalate and be supportive")
            if rails:
                messages.append({"role": "system", "content": f"[GUARDRAILS]: {'. '.join(rails)}."})
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `venv/Scripts/python.exe -m pytest tests/test_safety_toggle.py::TestGuardrailInjection tests/test_night_progression.py -v`
Expected: all pass (injection tests green; `test_night_progression` unaffected).

- [ ] **Step 5: Commit**

```bash
git add server/mario_prompt.py tests/test_safety_toggle.py
git commit -m "feat(safety): gate banned-topics on toggle, drop max_roasts, keep de-escalation

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 5: Layer 4 — relax brevity, raise the hard cap 300 → 500

**Files:**
- Modify: `server/mario_prompt.py` (line 124)
- Modify: `server/safety_filter.py` (line 134, `MAX_RESPONSE_CHARS`)
- Modify: `tests/test_edge_cases.py` (line 1013)
- Test: `tests/test_safety_toggle.py` (add)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_safety_toggle.py`:

```python
class TestBrevityAndCap:
    def teardown_method(self):
        set_safety_config(True, True)

    def test_cap_raised_above_300(self):
        set_safety_config(True, True)
        long_text = "Wahoo there friend. " * 60  # ~1200 chars, sentence-punctuated
        result = filter_response(long_text)
        assert 300 < len(result) <= 510

    def test_brevity_instruction_relaxed(self):
        from server import mario_prompt
        prompt = mario_prompt._character_system_prompt()
        assert "2-3 short sentences" not in prompt
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `venv/Scripts/python.exe -m pytest tests/test_safety_toggle.py::TestBrevityAndCap -v`
Expected: both FAIL — `test_cap_raised_above_300` because the cap is still 300 (result ≤ ~300), `test_brevity_instruction_relaxed` because the header still says "2-3 short sentences".

- [ ] **Step 3: Write minimal implementation**

**5a.** In `server/safety_filter.py` line 134, change:
```python
    MAX_RESPONSE_CHARS = 300
```
to:
```python
    MAX_RESPONSE_CHARS = 500
```

**5b.** In `server/mario_prompt.py` line 124, change:
```python
    header += " Always speak and answer as this character. Keep replies to 2-3 short sentences."
```
to:
```python
    header += " Always speak and answer as this character. Usually 2 to 4 sentences; go longer when the moment is worth it."
```

**5c.** In `tests/test_edge_cases.py` line 1013, change:
```python
        assert len(result) <= 310  # 300 + some buffer for truncation point
```
to:
```python
        assert len(result) <= 510  # 500 + some buffer for truncation point
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `venv/Scripts/python.exe -m pytest tests/test_safety_toggle.py::TestBrevityAndCap tests/test_edge_cases.py::TestResponseTruncation -v`
(If the class name differs, run the whole file: `... tests/test_edge_cases.py -v`.)
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add server/safety_filter.py server/mario_prompt.py tests/test_safety_toggle.py tests/test_edge_cases.py
git commit -m "feat(safety): relax brevity to 2-4 sentences, raise response cap to 500

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 6: Opt March into uncensored + slur guard

**Files:**
- Modify: `characters/march7th/character.yaml` (append a top-level `safety:` block)
- Test: `tests/test_safety_toggle.py` (add)

This is config (a TDD exception), but it gets a load-assertion test so a future YAML edit can't silently re-censor March.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_safety_toggle.py`:

```python
class TestMarchCharacterConfig:
    def test_march_is_uncensored_with_slur_guard(self):
        char = CharacterLoader("characters", "march7th")
        assert char.safety_enabled is False
        assert char.safety_block_slurs is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/Scripts/python.exe -m pytest tests/test_safety_toggle.py::TestMarchCharacterConfig -v`
Expected: FAIL — `assert True is False` (March has no safety block yet, so it defaults to enabled).

- [ ] **Step 3: Add the safety block**

In `characters/march7th/character.yaml`, append after line 146 (the `lore_file:` line, end of the `memory:` block) as a new top-level key:

```yaml
safety:
  # Uncensored character: no profanity/topic deflection. Slurs still blocked
  # because the bot speaks out loud in a room of guests. See
  # docs/superpowers/plans/2026-06-16-content-filter-uncensor-toggle.md
  enabled: false
  block_slurs: true
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/Scripts/python.exe -m pytest tests/test_safety_toggle.py::TestMarchCharacterConfig -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add characters/march7th/character.yaml tests/test_safety_toggle.py
git commit -m "feat(march): uncensor March 7th, keep slur guard

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 7: Full suite, TTS cache purge, restart, live audio verification

**Files:** none (verification only).

- [ ] **Step 1: Run the full test suite**

Run: `venv/Scripts/python.exe -m pytest tests/ -q --ignore=tests/convert_and_test.py`
Expected: all pass (0 failures). If any safety/edge test fails, it is a real regression — fix before continuing.

- [ ] **Step 2: Purge stale TTS cache**

Changing filter output changes spoken text for affected phrases; old cache keys become orphaned. Purge:

Run: `venv/Scripts/python.exe -c "import sys; sys.path.insert(0, 'server'); import tts; tts.purge_stale_cache(); print('cache purged')"`
Expected: `cache purged` (if `purge_stale_cache` signature differs, fall back to clearing `server/data/tts_cache/`). Restart the GPT-SoVITS subprocess so no pre-change audio is replayed.

- [ ] **Step 3: Restart the server**

Stop and restart via `start_server.bat`. Confirm the new startup log line appears:
`[CHARACTER] Safety: content_filter=OFF, block_slurs=True`

- [ ] **Step 4: Live audio verification (per `.claude/rules/testing.md` — MANDATORY)**

Open `http://localhost:8765/chat` (or use `POST /admin/simulate_text`). Send each and confirm BOTH the speech-bubble text AND the spoken audio (`_play_wav: playing` … `_play_wav: done` in client log):

1. Profanity ("this party is fucking great") → passes through unredacted, in-character, audio plays to completion.
2. A slur (use a mild test token from `SLUR_PATTERNS`) → rendered as `****` in text AND not spoken; confirm the bleep, audio still completes.
3. A previously-banned topic (politics) → engaged, not deflected.
4. Normal message → in-character, no Mario leak, audio completes.

A test is NOT complete until `_play_wav: done` is observed for each.

- [ ] **Step 5: Final confirmation**

All boxes checked, suite green, audio verified. Phase 1 (content-filter uncensor) complete. Do not start Layer 0 — it is a separate plan.

---

## Caveats / gotchas

- **No model swap.** `llama3`/`gemma3` are aligned and will still self-refuse the hardest content regardless of these flags. This is expected and accepted; revisit Layer 5 only if the current model can't deliver.
- **Defaults are fail-safe.** Any character without a `safety:` block stays fully filtered. Only March changes. This is why the existing 600+ tests stay green.
- **Test isolation is load-bearing.** `_SAFETY_ENABLED`/`_BLOCK_SLURS` are module globals. Every test that calls `set_safety_config(False, ...)` MUST reset to `(True, True)` in `teardown_method`, or it pollutes later tests in the same pytest process. This is already baked into each new class above.
- **Keep character-break stripping + artifact cleanup + the cap.** Those run unconditionally in `filter_response` and are immersion/quality, not censorship. Do not remove them.
- **TTS cache + sovits restart** required after Task 5/7 (text-cleaning-adjacent change).
- **Restart required** for the startup wiring (Task 3) and prompt changes (Task 4/5) to take effect.

---

## Self-review

- **Spec coverage:** Layer 1 (input redirect) → Task 2 (`check_input` gated). Layer 2 (output filter) → Task 2 (`filter_response` gated, slur tier split). Layer 3 (banned topics) → Task 4. Layer 4 (brevity + cap) → Task 5. Per-character toggle → Tasks 1+3+6. Slur-as-own-tier → Tasks 1+2. No model swap → respected (config untouched). Layer 0 → explicitly deferred to a separate plan. ✅
- **Placeholder scan:** every code step shows the literal code; every command shows expected output. No TBD/TODO. ✅
- **Type/name consistency:** `safety_enabled`/`safety_block_slurs` (loader) ↔ `set_safety_config(enabled, block_slurs)` (filter) ↔ `is_safety_enabled()` (read by mario_prompt) — names match across Tasks 1/2/3/4. `SLUR_PATTERNS`/`CONTENT_PATTERNS`/`SLUR_RE`/`CONTENT_RE` consistent within Task 2. ✅
- **Known soft spots to watch during execution:** (a) `test_edge_cases.py` truncation test class name in Task 5 Step 4 — if not `TestResponseTruncation`, run the whole file. (b) `tts.purge_stale_cache()` signature in Task 7 — fall back to clearing the cache dir if it differs. (c) `mario_prompt.build_context(phase_modifier=pm)` in Task 4 must run with only that kwarg; if it needs more, pass minimal stubs — all other params default to None.
