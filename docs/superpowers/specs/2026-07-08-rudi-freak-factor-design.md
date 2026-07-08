# Rudi Freak Factor — Design Spec

**Date:** 2026-07-08
**Status:** Design (approved verbally — user said "go")
**Character:** Rudi ONLY (per-character trait; must never leak to Mario/Freddy/etc.)

## 1. Problem

The user wants Rudi to be "freaky" — the Bad Rudi canon he's voiced/based on:
horny bravado, crude innuendo (dih jokes, gay-bravado camp), and *sometimes*
fully-unhinged explicit. This must be an **intrinsic Rudi trait**, dialable, and
**strictly per-character** — every other character stays exactly as clean as it is
today. Rudi's `system_prompt.md` is already crude/flirty; this cranks it and adds a
raunchy joke lane, both gated so nothing bleeds into other characters.

## 2. Goals / Success Criteria

- **`freak_factor` (0.0–1.0)** — an intrinsic per-character personality trait. Rudi
  ships `0.85`; every character without the trait defaults `0.0`.
- **Two registers**, mostly bravado: horny bravado + innuendo (the common case) with
  *occasional* fully-explicit (`explicit_ratio`, default `0.25` within freaky output).
- **Freaky joke lane** woven into the same 90/10 JokeEngine + idle chatter Rudi already
  uses — no new surface, just more pool.
- **Freaky personality in conversation too**, not only canned jokes — a `[FREAK]`
  directive injected into his LLM prompt, scaled by level.
- **Live dial**: `freak_factor` in `config_live.json`, hot-reloaded — crank or kill at
  the party instantly (0 = clean mode when someone tame walks in).
- **HARD per-character invariant (§4F):** a character whose default `freak_factor` is
  `0.0` can NEVER be made freaky — not by the live dial, not by a stray `freaky.yaml`.
  Triple-gated. This is the single most important requirement.
- **Non-goals (YAGNI):** thousand-joke freaky pool (a few hundred no-repeat is plenty),
  per-guest freak tuning, night-phase-specific freak curves (level is one intrinsic knob;
  existing UNHINGED phase already multiplies jokes), a separate freaky TTS voice.

## 3. Content Register (drives authoring + the prompt directive)

Bad Rudi: cocky, hypersexual-for-laughs, camp, shameless. **Bravado/innuendo** is the
default lane — suggestive, clever, vulgar, self-aware ("Straight? Buddy, I bend more
than your WiFi signal."). **Explicit** is the minority spice — says the actual thing,
still comedic bragging, never clinical. **Line held (both lanes):** adult crude comedy —
horny, vulgar, gay-bravado, explicit sex bragging = yes. Hateful **slurs**, anything
sexual involving **minors**, **non-consent** = never. Funny-freaky, punch at egos and
cringe, never at someone's race/gender/orientation. (This corrects two corrupted lines
already in `system_prompt.md` — see §4E.)

## 4. Architecture

Four units: **(A)** the freaky pool file, **(B)** JokeEngine blend, **(C)** the level
gate, **(D)** the prompt directive, plus **(E)** prompt-guardrail fix and **(F)** the
per-character safety invariant that ties them together.

### 4A. Freaky pool storage

`characters/rudi/jokes/freaky.yaml`:
```yaml
bravado:   # horny bravado + innuendo — the common lane
  - "Straight? Buddy, I bend more than your WiFi signal."
  - "..."
explicit:  # fully unhinged — the occasional spice
  - "..."
```
- Loaded by a new `load_freaky_jokes(char_dir) -> {"bravado": [...], "explicit": [...]}`
  in `server/joke_engine.py`. Missing file → both lists empty.
- **Rudi-only by construction:** the file lives in Rudi's dir. No other character ships
  one, so their freaky bags are empty regardless of any number.
- Authoring target: ~120 bravado + ~40 explicit (≥150 total) — enough for no-repeat over
  an 8-hour party via the shuffle-bag. `tts_ok` register: short, speakable, no ASCII art.

### 4B. JokeEngine blend (three shuffle-bags)

`JokeEngine.__init__` gains keyword-only args (back-compatible — existing
`JokeEngine(pool, llm_fn=..., llm_chance=...)` calls keep working, freaky defaults empty
→ current behavior unchanged):
```
JokeEngine(pool, freaky_pool=None, llm_fn=None, llm_chance=0.10,
           freak_level_fn=None, explicit_ratio=0.25, rng=None)
```
- `freaky_pool` = the §4A dict; builds two extra shuffle-bags (`_bag_bravado`,
  `_bag_explicit`) alongside the existing clean `_bag`, all under the same `_lock`.
- `freak_level_fn` = a **callable** returning the live level 0–1 (so a config-live dial
  change takes effect on the very next draw — no rebuild). `None` → level 0.0.
- `next_joke()` order:
  1. LLM path (10%, unchanged).
  2. `level = clamp(freak_level_fn() or 0, 0, 1)`; if no freaky content, `level = 0`.
  3. `if rng.random() < level`: freaky — `if explicit non-empty and rng.random() <
     explicit_ratio` → draw explicit, else draw bravado.
  4. else → draw clean.
- Each of the three bags is its own no-repeat shuffle-bag reusing the existing
  `_draw_from_bag` logic (refactored to take a bag+its `_last`, still `_lock`-guarded).

### 4C. The effective-level gate (the safety choke point)

One helper in `server/main.py` computes the level used by BOTH jokes and prompt:
```python
def _effective_freak_level() -> float:
    base = float(getattr(_character, "freak_factor", 0.0) or 0.0)
    if base <= 0.0:
        return 0.0                     # opt-in ONLY — clean chars can't be dialed freaky
    lvl = live_config.get("freak_factor", base)
    try: lvl = float(lvl)
    except (TypeError, ValueError): lvl = base
    return max(0.0, min(1.0, lvl))
```
- `_character.freak_factor` (the yaml default) is the **opt-in switch**. If it's `0.0`,
  the live dial is ignored entirely → a clean character is unreachable by config.
- Passed to JokeEngine as `freak_level_fn=_effective_freak_level` (live), and read at the
  prompt-injection sites.

### 4D. Prompt directive

`CharacterLoader.get_freak_prompt(level: float) -> str` — pure, level-scaled, testable:
- `level <= 0` → `""` (nothing injected; every clean character emits nothing).
- low/mid/high level → a `[FREAK]` system line escalating from "flirty innuendo, keep it
  suggestive" → "horny bravado, crude, camp, drop dih jokes" → "unhinged, explicit sex
  bragging allowed". Every tier ends with the held line: no slurs, no minors, punch at
  egos not identity.
- The directive text lives in code (not yaml) so it's uniform and can't be half-authored.

Injected at three sites in `main.py`, each reading `_effective_freak_level()`:
1. **Chat/greetings/exits:** appended to the character system prompt where it's wired in
   (main.py ~801-803, `_char_sys_prompt`). Because every `mario_prompt.build_context()`
   emits that system prompt, one injection covers chat + all event flows. Re-applied on
   `/config/reload` and char-switch (existing rebuild paths) so the level tracks the dial.
2. **Idle LLM joke** (`_joke_llm_fn`, ~3808): appended to its ctx.
3. **Idle LLM chatter** (~3845): appended to its ctx.

### 4E. Guardrail fix (in-scope — it IS the held line)

`characters/rudi/prompts/system_prompt.md` currently contains two corrupted lines that
invert the boundary this feature promises:
- L5 `"IMPORTANT: You punch at their race, gender, or who they love."` → rewrite to
  forbid punching down at race/gender/orientation (punch at egos/bad-takes/cringe).
- L11 `"Slurs as much as possible."` → `"Never use slurs."`
Both are pre-existing corruption; fixing them is required for the §3 line to hold.

### 4F. Per-character safety invariant (the whole point)

Freaky output requires ALL THREE, so any single gate closing keeps a character clean:
1. **Opt-in default:** `personality.freak_factor > 0` in that character's `character.yaml`
   (Rudi only). Drives `_effective_freak_level` → 0 for everyone else.
2. **Pool file present:** `jokes/freaky.yaml` exists in that character's dir (Rudi only).
   No file → empty freaky bags → JokeEngine can only draw clean.
3. **Directive gate:** `get_freak_prompt(0)` → `""`. Clean characters inject nothing.
The live `config_live.json` dial can only scale a character that already opted in (gate 1)
— it can never flip a clean character freaky. Test asserts Mario/Freddy stay clean even
with `config_live freak_factor = 1.0`.

## 5. Data Flow

1. **Load:** `character.yaml` → `CharacterLoader.freak_factor`. `jokes/freaky.yaml` →
   `load_freaky_jokes` → IdleBehavior → JokeEngine's freaky bags.
2. **Level:** `_effective_freak_level()` reads yaml default + live override each call.
3. **Serve jokes:** idle/"tell a joke" → `JokeEngine.next_joke()` → 90/10, and within the
   90% pool path, `level`/`explicit_ratio` pick clean/bravado/explicit.
4. **Serve chat:** `get_freak_prompt(level)` rides the system prompt into every response.

## 6. Error Handling

- Missing/empty `freaky.yaml` → empty freaky bags → JokeEngine draws clean (never errors).
- `freak_level_fn` raises / returns junk → treated as 0.0 (clean), never crashes a draw.
- `config_live freak_factor` non-numeric → falls back to the yaml default.
- No `personality` block (Rudi has none today) → adding one is additive; other chars keep
  `freak_factor` 0.0 via the loader default.

## 7. Testing

- **JokeEngine:** freaky_pool empty → only clean ever drawn (back-compat). level=1.0 +
  freaky present → every non-LLM draw is freaky; each freaky bag exhausts before repeating;
  explicit_ratio split holds over N seeded draws; `freak_level_fn` exception → clean draw.
- **Level gate:** `_effective_freak_level` = 0 when char default 0 regardless of
  `config_live`; clamps; live override scales an opted-in char.
- **Directive:** `get_freak_prompt(0)` == "" ; higher levels escalate and every non-empty
  tier contains the no-slur/no-minor guardrail substring.
- **Per-character invariant (critical):** load a clean character (freak_factor 0, no
  freaky.yaml) with `config_live freak_factor = 1.0` → JokeEngine draws only clean AND
  `get_freak_prompt` == "". Rudi with same config → freaky reachable.
- **Loader:** `freak_factor` parses from yaml; absent → 0.0.
- **Audio (mandatory, per .claude/rules/testing.md):** a freaky pool joke plays
  start→finish in Rudi's voice; switch to a clean character → confirm ZERO freaky/again
  ZERO wrong-character leak in text AND audio.

## 8. Implementation Phases

1. **Level gate + loader** (`freak_factor` parse, `_effective_freak_level`,
   `get_freak_prompt`) — pure/testable, no behavior yet.
2. **JokeEngine blend** (freaky bags, `load_freaky_jokes`, three-bag draw) + IdleBehavior
   wiring.
3. **Freaky content** (`characters/rudi/jokes/freaky.yaml`, ~150+ authored).
4. **Prompt injection** (3 sites) + guardrail fix (§4E) + `config_live` default.
5. **Tests + audio verification.**

## 9. Open Questions (resolved)

- Live dial scope: `config_live freak_factor` only scales opted-in characters (§4C/4F).
- Explicit share: `explicit_ratio` default 0.25 (mostly bravado), tunable later by editing
  the value; not exposed as a separate live dial (YAGNI).
