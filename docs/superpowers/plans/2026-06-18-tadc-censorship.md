# TADC Censorship Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Digital Circus characters can't swear — their swears are bleeped: blocked (`████`) in the speech bubble, removed from the spoken audio, with a censor-bar PNG over the sprite's mouth and a bleep SFX.

**Architecture:** A pure server module (`server/tadc_censor.py`) detects profanity in the character's own output and returns a blocked display string + a swear-removed TTS string. A per-character `identity.franchise: digital_circus` flag gates it on at character load. When a line is censored, `send_response` adds a `censor: true` flag to the existing `mario_response` ws message; the pygame client plays a `censor` SFX and overlays a bar on the sprite's mouth while speaking.

**Tech Stack:** Python (server), pygame (client), pytest, existing `safety_filter` + `CharacterLoader` + `mario_response` metadata pattern.

**Branch:** `feat/tadc-censorship` (already created; spec at `docs/superpowers/specs/2026-06-18-tadc-censorship-design.md`).

## File Structure

- **Create** `server/tadc_censor.py` — pure censor logic (detect, block display, strip TTS). One responsibility.
- **Create** `tests/test_tadc_censor.py` — unit tests for the censor module.
- **Modify** `shared/character_loader.py` — add `self.franchise` parsed from `identity.franchise`.
- **Modify** `server/main.py` — enable censor at character load; apply censor after `analyze_text`; add `censor` param to `send_response`.
- **Modify** `client/sound_effects.py` — register a `"censor"` sound (wav if present, synth beep fallback).
- **Modify** `client/main.py` — on `censor` metadata, play SFX + set `_censor_active`; clear it when speaking ends.
- **Modify** `client/mario_display.py` — init `_censor_active`, load censor-bar PNG, blit it over the sprite mouth while speaking.
- **Add assets** `assets/sfx/censor.wav` (sourced) and `client/assets/censor_bar.png` (sourced); both have code fallbacks.
- **Modify** `characters/jax/character.yaml` + `characters/pomni/character.yaml` — add `identity.franchise: digital_circus`.

---

### Task 1: `server/tadc_censor.py` censor module (pure, TDD)

**Files:**
- Create: `server/tadc_censor.py`
- Test: `tests/test_tadc_censor.py`

> Note: match the import style used in `tests/test_safety_toggle.py` (it imports `safety_filter` with `server/` on `sys.path`). Use the same path setup so `from tadc_censor import ...` resolves.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_tadc_censor.py
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))
import tadc_censor


def test_clean_text_unchanged():
    r = tadc_censor.censor("hello there friend")
    assert r.display == "hello there friend"
    assert r.tts == "hello there friend"
    assert r.count == 0


def test_single_swear_blocked_in_display_and_removed_from_tts():
    r = tadc_censor.censor("oh fuck this")
    assert r.count == 1
    assert "████" in r.display
    assert "fuck" not in r.display.lower()
    assert "fuck" not in r.tts.lower()


def test_multiple_swears_counted():
    r = tadc_censor.censor("shit, that is fucking great")
    assert r.count == 2
    assert r.display.count("████") == 2


def test_compound_word_blocked_whole():
    r = tadc_censor.censor("that is bullshit")
    assert r.count == 1
    assert r.display == "that is ████"


def test_case_insensitive():
    assert tadc_censor.censor("FUCK").count == 1


def test_empty_text():
    r = tadc_censor.censor("")
    assert r.count == 0 and r.display == "" and r.tts == ""


def test_enabled_gate_defaults_off_and_toggles():
    tadc_censor.set_enabled(False)
    assert tadc_censor.is_enabled() is False
    tadc_censor.set_enabled(True)
    assert tadc_censor.is_enabled() is True
    tadc_censor.set_enabled(False)  # reset for other tests
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `venv/Scripts/python.exe -m pytest tests/test_tadc_censor.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tadc_censor'`.

- [ ] **Step 3: Write the module**

```python
# server/tadc_censor.py
"""TADC-style swear censor for Digital Circus characters.

Pure and dependency-light. Detects profanity in a character's OWN output and
returns (a) a display string with each swear replaced by a block (████) for the
speech bubble and (b) a TTS string with each swear removed so synthesis never
voices it. Gated per character via set_enabled() — only on when the active
character's franchise is 'digital_circus'.

Slurs are NOT handled here: safety_filter keeps hard-blocking those to **** on an
independent tier, regardless of this module.
"""
import re
from dataclasses import dataclass

from safety_filter import _normalize_unicode  # reuse homoglyph/zero-width normalizer (DRY)

# Profanity to bleep — the swear subset of safety_filter.CONTENT_PATTERNS plus
# common compounds. \b...\b word boundaries make ordering irrelevant for
# compounds ('shit' won't match inside 'bullshit'), but we still list compounds
# so they're caught as single blocks.
_SWEARS = [
    "motherfucker", "motherfuckin", "bullshit", "asshole", "dumbass", "jackass",
    "dipshit", "dickhead", "fucker", "fuckin", "fucking", "fuck", "shit",
    "bitch", "bastard", "dammit", "damn", "dick", "cock", "pussy", "ass",
    "piss", "crap",
]
_SWEAR_RE = re.compile(r"\b(?:" + "|".join(_SWEARS) + r")\b", re.IGNORECASE)

_BLOCK = "████"  # U+2588 FULL BLOCK ×4 — the bubble censor mark

_ENABLED = False
_CHARACTER_NAME = "assistant"
_CHARACTER_DISPLAY_NAME = "Assistant"


@dataclass
class CensorResult:
    display: str  # swears -> ████ (speech bubble)
    tts: str      # swears removed (audio never voices them)
    count: int    # number of swears found


def set_enabled(enabled: bool):
    global _ENABLED
    _ENABLED = bool(enabled)


def is_enabled() -> bool:
    return _ENABLED


def set_character(name: str, display_name: str):
    global _CHARACTER_NAME, _CHARACTER_DISPLAY_NAME
    if name:
        _CHARACTER_NAME = name
    if display_name:
        _CHARACTER_DISPLAY_NAME = display_name


def censor(text: str) -> CensorResult:
    """Block swears for display, strip them from TTS. Pure; never raises."""
    if not text:
        return CensorResult(display=text or "", tts=text or "", count=0)
    norm = _normalize_unicode(text)
    count = len(_SWEAR_RE.findall(norm))
    if not count:
        return CensorResult(display=text, tts=text, count=0)
    display = _SWEAR_RE.sub(_BLOCK, norm)
    # Remove from audio; ', ' keeps a natural pause. _preclean_tts_text downstream
    # collapses any resulting double commas.
    tts = _SWEAR_RE.sub(", ", norm)
    return CensorResult(display=display, tts=tts, count=count)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `venv/Scripts/python.exe -m pytest tests/test_tadc_censor.py -v`
Expected: PASS (7 passed).

- [ ] **Step 5: Commit**

```bash
git add server/tadc_censor.py tests/test_tadc_censor.py
git commit -m "feat(tadc-censor): pure swear censor module + tests"
```

---

### Task 2: `franchise` field on `CharacterLoader`

**Files:**
- Modify: `shared/character_loader.py:51` (after `self.display_name`)
- Test: `tests/test_tadc_censor.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_tadc_censor.py`:

```python
def test_character_loader_exposes_franchise(tmp_path):
    import yaml as _yaml
    from shared.character_loader import CharacterLoader
    cdir = tmp_path / "characters" / "testc"
    cdir.mkdir(parents=True)
    (cdir / "character.yaml").write_text(_yaml.dump({
        "identity": {"name": "Testc", "display_name": "Testc", "franchise": "Digital_Circus"},
    }), encoding="utf-8")
    c = CharacterLoader(str(tmp_path / "characters"), "testc")
    assert c.franchise == "digital_circus"   # normalized lower/stripped


def test_character_loader_franchise_defaults_empty(tmp_path):
    import yaml as _yaml
    from shared.character_loader import CharacterLoader
    cdir = tmp_path / "characters" / "plainc"
    cdir.mkdir(parents=True)
    (cdir / "character.yaml").write_text(_yaml.dump({
        "identity": {"name": "Plainc", "display_name": "Plainc"},
    }), encoding="utf-8")
    c = CharacterLoader(str(tmp_path / "characters"), "plainc")
    assert c.franchise == ""
```

> If `CharacterLoader.__init__` requires more than `identity` (e.g. a real sprite dir), check `tests/` for an existing CharacterLoader fixture and mirror its minimal yaml. Read `shared/character_loader.py:15-130` first to confirm the constructor signature and required keys.

- [ ] **Step 2: Run tests to verify they fail**

Run: `venv/Scripts/python.exe -m pytest tests/test_tadc_censor.py -k franchise -v`
Expected: FAIL — `AttributeError: 'CharacterLoader' object has no attribute 'franchise'`.

- [ ] **Step 3: Add the field**

In `shared/character_loader.py`, immediately after line 51
(`self.display_name: str = identity.get("display_name", self.name)`), add:

```python
        # Franchise group (e.g. "digital_circus") — drives franchise-wide
        # behaviors like TADC swear censoring. Normalized lower/stripped.
        self.franchise: str = (identity.get("franchise") or "").strip().lower()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `venv/Scripts/python.exe -m pytest tests/test_tadc_censor.py -k franchise -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add shared/character_loader.py tests/test_tadc_censor.py
git commit -m "feat(tadc-censor): CharacterLoader.franchise from identity.franchise"
```

---

### Task 3: Server wiring (enable at load, censor pipeline, send_response flag)

**Files:**
- Modify: `server/main.py` — import; char-load (732, 2472); censor hook (~4955); `send_response` (6149); sends (5066, 5126)

- [ ] **Step 1: Import the module**

Near the other server imports at the top of `server/main.py` (where `safety_filter`/`filter_response` are imported), add:

```python
import tadc_censor
```

- [ ] **Step 2: Enable/disable at character load (both load sites)**

In `server/main.py` immediately AFTER line 732
(`safety_filter.set_safety_config(_character.safety_enabled, _character.safety_block_slurs)`), add:

```python
    tadc_censor.set_character(_character.name, _character.display_name)
    tadc_censor.set_enabled(_character.franchise == "digital_circus")
    logger.info(f"[TADC] swear censor {'ON' if tadc_censor.is_enabled() else 'OFF'} "
                f"(franchise={_character.franchise or 'none'})")
```

Add the SAME three lines after the hot-swap site at line 2472
(`safety_filter.set_safety_config(_character.safety_enabled, _character.safety_block_slurs)`).

- [ ] **Step 3: Apply censor after `analyze_text` (main response path)**

In `server/main.py`, locate line 4956 (`logger.info(f"Mario says: '{analyzed['tts_text']}' ...")`).
IMMEDIATELY BEFORE that log line, insert:

```python
    censored = False
    if tadc_censor.is_enabled():
        _d = tadc_censor.censor(analyzed.get("display_text", ""))
        _t = tadc_censor.censor(analyzed.get("tts_text", ""))
        analyzed["display_text"] = _d.display
        analyzed["tts_text"] = _t.tts
        if analyzed.get("full_text"):
            analyzed["full_text"] = tadc_censor.censor(analyzed["full_text"]).display
        censored = (_d.count + _t.count) > 0
        if censored:
            logger.info(f"[TADC] censored {_d.count} swear(s) in response")
```

- [ ] **Step 4: Add `censor` param to `send_response`**

In `server/main.py`, change the `send_response` signature (line 6149-6155) to add a
`censor` keyword, and emit the flag. Specifically add `censor: bool = False,` to the
params, and AFTER the `if particle_effect:` block (line 6183-6184) add:

```python
    if censor:
        msg["censor"] = True
```

- [ ] **Step 5: Pass `censor=censored` on the two main-path sends**

In `server/main.py`, the streaming first-chunk send at line 5066-5070 — add `censor=censored,`
to its kwargs. The non-streaming send at line 5126-5129 — add `censor=censored,` to its kwargs.
(Leave the remaining `audio_chunk` sends at ~5090 untouched — the bar is already active and
the bleep plays once.)

- [ ] **Step 6: Integration test — censored flag rides the message**

Add to `tests/test_tadc_censor.py` a focused test of the message-shape contract (no full
server boot — test the helper logic directly):

```python
def test_pipeline_contract_blocks_and_flags():
    import tadc_censor as tc
    tc.set_enabled(True)
    analyzed = {"display_text": "you little shit", "tts_text": "you little shit", "full_text": "you little shit"}
    d = tc.censor(analyzed["display_text"]); t = tc.censor(analyzed["tts_text"])
    analyzed["display_text"], analyzed["tts_text"] = d.display, t.tts
    censored = (d.count + t.count) > 0
    assert censored is True
    assert "████" in analyzed["display_text"]
    assert "shit" not in analyzed["tts_text"].lower()
    tc.set_enabled(False)
```

- [ ] **Step 7: Run tests + import check**

Run: `venv/Scripts/python.exe -m pytest tests/test_tadc_censor.py -v`
Expected: PASS (all).
Run: `venv/Scripts/python.exe -c "import sys; sys.path.insert(0,'server'); import ast; ast.parse(open('server/main.py').read()); print('main.py parses')"`
Expected: `main.py parses`.

- [ ] **Step 8: Commit**

```bash
git add server/main.py tests/test_tadc_censor.py
git commit -m "feat(tadc-censor): wire censor into response pipeline + send_response flag"
```

---

### Task 4: Client `censor` sound effect

**Files:**
- Modify: `client/sound_effects.py` — register `"censor"` in the sound generation step (after line 252, end of `_generate_sounds`)

- [ ] **Step 1: Read the surrounding code**

Read `client/sound_effects.py:240-290` to confirm the end of the sound-generation method, the
`_make_tone` helper signature, and the `play()` method. (`play()` already no-ops gracefully on an
unknown name — line ~288.)

- [ ] **Step 2: Register the censor sound (wav if present, synth beep fallback)**

At the END of the sound-generation method (after line 252, before it returns), add:

```python
        # Censor bleep for TADC swear-censoring. Prefer a real wav if present,
        # else a short synth beep so the feature is never silent.
        import os as _os
        _censor_wav = _os.path.join(_os.path.dirname(_os.path.dirname(__file__)), "assets", "sfx", "censor.wav")
        try:
            if _os.path.exists(_censor_wav):
                import pygame.mixer as _mx
                self._sounds["censor"] = _mx.Sound(_censor_wav)
            else:
                self._sounds["censor"] = self._make_tone(1000, 0.25, volume=0.4, wave_type="square")
        except Exception as _e:
            logger.warning(f"[DEBUG_SFX] censor sound init failed: {_e}")
```

> `_make_tone(frequency, duration, volume=..., wave_type=...)` is the confirmed helper used by the neighboring synthesized sounds (e.g. `self._make_tone(4000, 0.2, volume=0.3, wave_type="sine")`). Confirm exact param names in Step 1 and match them.

- [ ] **Step 3: Smoke test the registration**

Run: `venv/Scripts/python.exe -c "import ast; ast.parse(open('client/sound_effects.py').read()); print('ok')"`
Expected: `ok`.
(Full pygame audio can't run headless in CI; live verification is in Task 7.)

- [ ] **Step 4: Commit**

```bash
git add client/sound_effects.py
git commit -m "feat(tadc-censor): register client 'censor' SFX (wav + synth fallback)"
```

---

### Task 5: Client mouth-bar overlay + `_censor_active` lifecycle

**Files:**
- Modify: `client/mario_display.py:299` (init flag), `__init__`/`init` (load bar PNG), after sprite blit `:2474` (draw overlay)
- Modify: `client/main.py:324-345` (`_on_mario_text`), `client/main.py:462` (`_clear_speaking_state`)

- [ ] **Step 1: Initialize the flag + load the bar PNG once**

In `client/mario_display.py`, immediately after line 298 (`self._speaking = False`) add:

```python
        self._censor_active = False
```

In the display `__init__` (near where other assets load; if unsure, add right after the
`self._censor_active = False` line and guard with `hasattr`), load the bar once:

```python
        # TADC censor bar (sourced PNG). None -> draw a black rect fallback.
        import os as _os
        _bar = _os.path.join(_os.path.dirname(__file__), "assets", "censor_bar.png")
        try:
            self._censor_bar = pygame.image.load(_bar).convert_alpha() if _os.path.exists(_bar) else None
        except Exception:
            self._censor_bar = None
```

> `convert_alpha()` requires a display surface to exist. If `__init__` runs before
> `pygame.display.set_mode`, defer the load to the first draw (lazy-load guarded by
> `hasattr(self, "_censor_bar")`). Read `client/mario_display.py:280-310` and the display-init
> sequence to choose the right spot.

- [ ] **Step 2: Draw the bar over the mouth after the sprite blit**

> **Deviation from spec (intentional, YAGNI):** the spec's per-character `visuals.mouth_censor`
> override is deferred. v1 uses one fixed mouth height (`0.40`) for all ADC chars — adjust that
> constant per character as a fast-follow after seeing it live on Jax vs Pomni (Task 7, Step 3).

In `client/mario_display.py`, immediately AFTER line 2474 (`self._screen.blit(display_sprite, (cx, cy))`),
add:

```python
        # TADC mouth censor bar — only while actively speaking a censored line.
        if getattr(self, "_censor_active", False) and self._speaking and display_sprite:
            sw, sh = display_sprite.get_width(), display_sprite.get_height()
            bar_w = int(sw * 0.45)
            bar_h = max(8, int(sh * 0.07))
            bx = cx + sw // 2 - bar_w // 2
            by = cy + int(sh * 0.40)          # ~mouth height (tunable)
            bar = getattr(self, "_censor_bar", None)
            if bar:
                scaled = pygame.transform.smoothscale(bar, (bar_w, int(bar_w * bar.get_height() / bar.get_width())))
                self._screen.blit(scaled, (bx, cy + int(sh * 0.40) - scaled.get_height() // 2))
            else:
                pygame.draw.rect(self._screen, (0, 0, 0), (bx, by, bar_w, bar_h), border_radius=4)
```

- [ ] **Step 3: Set `_censor_active` on the censor metadata**

In `client/main.py` `_on_mario_text`, inside the `if metadata:` block (after the `sound_effect`
handling at lines 324-327), add:

```python
            if metadata.get("censor"):
                self.sfx.play("censor")
                self.display._censor_active = True
```

- [ ] **Step 4: Clear `_censor_active` when speaking ends**

In `client/main.py` `_clear_speaking_state` (line 460-463), after `self.display._speaking = False`
(line 462) add:

```python
        self.display._censor_active = False
```

- [ ] **Step 5: Syntax check**

Run: `venv/Scripts/python.exe -c "import ast; [ast.parse(open(f).read()) for f in ('client/mario_display.py','client/main.py')]; print('ok')"`
Expected: `ok`.

- [ ] **Step 6: Commit**

```bash
git add client/mario_display.py client/main.py
git commit -m "feat(tadc-censor): client mouth-bar overlay + censor SFX trigger"
```

---

### Task 6: Source the assets (bleep wav + censor-bar PNG)

**Files:**
- Add: `assets/sfx/censor.wav`, `client/assets/censor_bar.png`

- [ ] **Step 1: Source the censor bleep**

Try to download the TADC censor sound via yt-dlp (a short isolated clip), then trim to ~250ms:

```bash
venv/Scripts/python.exe -c "from character_creator import voice_finder; print([ (h['duration'],h['title'],h['url']) for h in voice_finder.search('amazing digital circus censor beep sound effect', 6) ])"
```

Pick a short hit, download with `voice_finder.download_full`, and cut the bleep with ffmpeg to
`assets/sfx/censor.wav` (mono). If no clean isolated clip exists, SKIP — the synth fallback from
Task 4 already covers it. `log()`/note which path was used.

- [ ] **Step 2: Source the censor-bar PNG**

Find a transparent TADC-style black censor bar PNG (web search/download) and save to
`client/assets/censor_bar.png`. If none is found, SKIP — the drawn-rect fallback from Task 5
covers it. Verify it's a valid transparent PNG:

```bash
venv/Scripts/python.exe -c "from PIL import Image; im=Image.open('client/assets/censor_bar.png'); print(im.mode, im.size)"
```
Expected: `RGBA (w, h)`.

- [ ] **Step 3: Commit whatever landed**

```bash
git add assets/sfx/censor.wav client/assets/censor_bar.png   # add only the files that exist
git commit -m "assets(tadc-censor): censor bleep + bar (sourced)"
```

---

### Task 7: Enable on Jax + Pomni + live verification

**Files:**
- Modify: `characters/jax/character.yaml`, `characters/pomni/character.yaml` (add `identity.franchise`)

- [ ] **Step 1: Add the franchise flag**

In `characters/jax/character.yaml` under `identity:` add `franchise: digital_circus`.
In `characters/pomni/character.yaml` under `identity:` add `franchise: digital_circus`.

Verify both parse:
```bash
venv/Scripts/python.exe -c "import yaml; [print(p, yaml.safe_load(open(p))['identity'].get('franchise')) for p in ('characters/jax/character.yaml','characters/pomni/character.yaml')]"
```
Expected: each prints `... digital_circus`.

- [ ] **Step 2: Full test suite (no regressions)**

Run: `venv/Scripts/python.exe -m pytest tests/test_tadc_censor.py tests/test_safety_toggle.py -v`
Expected: PASS.

- [ ] **Step 3: Live verification (per `.claude/rules/testing.md` — MANDATORY)**

Start the server with Pomni active, send a line engineered to elicit a mild swear (or use
`POST /admin/simulate_text` with a response that contains one), and confirm in the CLIENT logs:
- `mario says:` shows `████` where the swear was (bubble censored),
- the spoken audio OMITS the word (`_play_wav: playing` … `_play_wav: done`), and the word is not voiced,
- `[DEBUG_SFX] play: censor` fires (bleep), and the mouth bar appears while `_speaking` and clears after.
Repeat for Jax (different mouth height) and confirm a NON-ADC character (e.g. Mario) is unaffected
(no `[TADC]` log, no censor flag).

- [ ] **Step 4: Commit**

```bash
git add characters/jax/character.yaml characters/pomni/character.yaml
git commit -m "feat(tadc-censor): enable censor on Jax + Pomni (franchise flag)"
```

---

## Final Review

After all tasks: dispatch a final code review over the branch diff, then use
`superpowers:finishing-a-development-branch` to wrap up (merge `feat/tadc-censorship` to master
or open a PR, per the user's preference).
