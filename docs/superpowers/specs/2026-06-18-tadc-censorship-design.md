# TADC Censorship Feature — Design

**Date:** 2026-06-18
**Status:** Approved (design), pending implementation plan

## Goal

Digital Circus characters can't swear. When an ADC character's spoken line contains
profanity, that word is censored TADC-style:
- replaced with a censor block (`████`) in the speech bubble,
- **omitted from the spoken audio** (TTS never voices it),
- a sourced **TADC censor-bar PNG overlays the sprite's mouth** while speaking,
- the sourced **TADC bleep SFX** plays once.

Robust across ALL Digital Circus characters (Jax, Pomni, and any future ADC
character) via a single franchise flag. Zero behavior change for every other
character (Mario, HSR cast, etc.).

## Background (existing code this builds on)

- **`server/safety_filter.py`** — `filter_response(text)` already detects profanity
  (`CONTENT_PATTERNS`: `fuck|shit|damn|ass|bitch|bastard|dick|cock|pussy`, plus
  violence/hate/etc.) and redacts to `****` when `_SAFETY_ENABLED`. Slurs are an
  **independent hard-block tier** (`SLUR_PATTERNS`, gated by `_BLOCK_SLURS`) that
  stays on even when general safety is off. `set_safety_config(enabled, block_slurs)`
  is called at startup from `character.yaml`. `_normalize_unicode()` defeats
  homoglyph/fullwidth/zero-width bypass tricks.
- **Response pipeline** (`server/main.py`) already separates **display text** from
  **spoken text**: synthesis uses `analyzed["tts_text"]` while the bubble shows
  `response_text` (from `filter_response`). Main user-response path is ~lines
  4902–5033. `filter_response` is also applied in the greeting path (~2799) and
  other spoken paths (~3214, 5556, 5832).
- **`mario_response` ws message** (`send_response`, ~6149) already carries
  client-visual metadata fields the client reads: `sound_effect`, `emotion`,
  `particle_effect`, `pose_hint`, `is_thinking_filler`. Adding one more flag is the
  established pattern.
- **Client** (`client/main.py _on_mario_text`, `client/sound_effects.py`,
  `client/mario_display.py`): metadata drives SFX (`sfx.play(name)`) and visuals.
  Sprite is a flat PNG blitted at `(cx, cy)` (~line 2474); `_speaking` flag is True
  while talking. **No per-sprite mouth coordinates exist.**
- **No `franchise`/group field** exists in `character.yaml` today. ADC chars are
  only identifiable by description text.

## Chosen Approach: Server censors + metadata flag + client overlay

Rejected alternatives:
- **Client-side detection** — duplicates profanity logic on the client, desyncs
  text/audio, puts censorship policy in the wrong layer.
- **Inline per-word sentinel markers** for exact word-level bar/bleep timing — needs
  TTS word timestamps to truly sync to the mouth; over-engineered for now. Recorded
  as future work.

## Components

### 1. Franchise flag (config)

- Add to `characters/jax/character.yaml` and `characters/pomni/character.yaml`:
  ```yaml
  identity:
    franchise: digital_circus
  ```
- At character load, `main.py` reads `identity.franchise`. If `== "digital_circus"`,
  call `tadc_censor.set_enabled(True)`; otherwise `set_enabled(False)`. Mirrors how
  `safety_filter.set_safety_config` is wired at startup. Default OFF.
- Optional per-character mouth-bar placement (see Client):
  ```yaml
  visuals:
    mouth_censor: { x_frac: 0.5, y_frac: 0.40, w_frac: 0.45 }
  ```

### 2. `server/tadc_censor.py` (new module, single responsibility)

- Module-level `_ENABLED` flag + `set_enabled(bool)` / `is_enabled()`.
- `set_character(name, display_name)` for parity with other modules (logging only).
- Profanity set = the swear subset of `safety_filter.CONTENT_PATTERNS`
  (`fuck, shit, damn, ass, bitch, bastard, dick, cock, pussy` + common variants
  `fuckin`, `bullshit`, `asshole`, `dickhead`, etc.). Compiled with word boundaries,
  case-insensitive.
- `censor(text: str) -> CensorResult` where `CensorResult` has:
  - `display: str` — each swear replaced with `████` (U+2588 × 4) for the bubble.
  - `tts: str` — each swear removed and replaced with `", "` (a brief pause) so
    synthesis never voices it and the sentence still flows.
  - `count: int` — number of swears found.
- Input is Unicode-normalized via `safety_filter._normalize_unicode` before matching
  (shared helper; do not duplicate) — this catches homoglyph/fullwidth/zero-width
  variants. Because the censored text is the character's OWN LLM output, swears are
  normally-spelled words, so literal word matching is sufficient; digit/symbol
  leetspeak (`sh1t`, `f*ck`, `a$$`) is explicitly out of scope (future robustness).
- Slurs are NOT handled here — they remain on `safety_filter`'s hard-block `****`
  tier (serious, not a comedy bleep).
- Pure function, fully unit-testable, no I/O, no pygame, no network.

### 3. Pipeline integration (`server/main.py`)

- Add a small helper applied right after `analyze` and BEFORE `tts.synthesize` in the
  spoken-output paths (audio must omit the swear, so censoring must precede
  synthesis):
  ```python
  if tadc_censor.is_enabled():
      r = tadc_censor.censor(response_text)
      t = tadc_censor.censor(analyzed["tts_text"])
      response_text = r.display
      analyzed["tts_text"] = t.tts
      censored = r.count > 0 or t.count > 0
  ```
- Primary integration: the main user-response path (~4902–5033).
- Robustness: route the greeting path (~2799) and idle path through the same helper
  so any ADC spoken line is covered. (Canned/idle text rarely swears, but the helper
  is cheap and keeps it uniform.)
- `send_response` gains a `censor: bool = False` param; when True it adds
  `"censor": true` to the `mario_response` JSON. Dedicated flag — does NOT reuse
  `sound_effect` (so a censored line can still carry its normal SFX).

### 4. Client

- **`client/main.py _on_mario_text`**: if `metadata.get("censor")`:
  - `self.sfx.play("censor")` (one bleep), and
  - `self.display._censor_active = True`.
  - `_censor_active` is reset to `False` wherever `_speaking` is cleared
    (`_clear_speaking_state`, ~main.py:462), so the bar lives exactly as long as the
    spoken line.
- **`client/sound_effects.py`**: register `"censor"` → load `assets/sfx/censor.wav`
  (or `client/assets/sfx/censor.wav`). If the file is absent, `play("censor")` is a
  graceful no-op (existing behavior for missing sounds).
- **`client/mario_display.py`**: while `_censor_active and _speaking`, blit the
  censor-bar PNG (`assets/censor_bar.png`, loaded once, alpha-preserved) over the
  sprite's mouth. Position computed relative to the sprite blit rect `(cx, cy, w, h)`:
  ```
  bar_w = w * mouth.w_frac
  bar_cx = cx + w * mouth.x_frac
  bar_cy = cy + h * mouth.y_frac
  ```
  Defaults `x_frac=0.5, y_frac=0.40, w_frac=0.45`; per-character override from
  `visuals.mouth_censor`. Bar PNG scaled to `bar_w` preserving aspect. If the PNG is
  missing, fall back to a filled black rounded rect of the same rect (feature still
  works visually).

### 5. Assets (sourced online)

- `assets/sfx/censor.wav` — the real TADC censor bleep. Source via `yt-dlp`/web; if no
  clean isolated clip is found, generate a short synth beep (~150ms, ~1kHz) as a
  committed fallback so the feature is never silent.
- `assets/censor_bar.png` — the TADC black censor bar as a transparent PNG. Source
  online; fallback is the drawn black rounded rect (no commit needed for the
  fallback).

## Data flow

```
LLM raw text
  → filter_response()            (slur hard-block ****, char-break cleanup, length cap)
  → analyze()                    (produces tts_text, pose_hint, emotion, ...)
  → [ADC char only] tadc_censor.censor() on display + tts_text
       display:  swear → ████
       tts_text: swear → ", "    (audio omits it)
       censored = count > 0
  → tts.synthesize(tts_text)     (no swear in audio)
  → send_response(text=display, audio=..., censor=censored)
       mario_response { ..., "censor": true }
Client:
  censor==true → sfx.play("censor")  +  _censor_active=True
  draw loop: while speaking → blit censor bar over sprite mouth
  speaking ends → _censor_active=False (bar gone)
```

## Edge cases

- **Multiple swears in one line** → still one bleep; bar held for the whole spoken
  line (per-response, not per-word). Per-word timing is future work.
- **Asset missing** → bleep is a no-op; bar falls back to a drawn black rect; text is
  still censored. Feature degrades, never crashes.
- **Non-ADC character** → `is_enabled()` False, pipeline helper skipped, no metadata,
  identical behavior to today.
- **Slurs** → unchanged: `safety_filter` hard-blocks them to `****` before
  `tadc_censor` runs; they never reach the comedy bleep.
- **Streaming sentences** (`chunk_index`/`total_chunks`) → censor each chunk
  independently; any chunk with `count>0` sets `censor:true` for that chunk.

## Testing

- **Unit** `tests/test_tadc_censor.py`:
  - profanity → `display` has `████`, `tts` omits the word, `count` correct.
  - clean text → unchanged, `count==0`.
  - unicode homoglyph / fullwidth variants caught via the shared `_normalize_unicode`
    (e.g. fullwidth `ｆｕｃｋ`); digit/symbol leetspeak is out of scope.
  - slurs are NOT bleeped here (left for safety_filter's `****`).
  - `is_enabled()` gates behavior; disabled → passthrough.
- **Integration**: ADC char response containing a swear → `mario_response.censor ==
  true` and censored `text`; non-ADC char with the same text → no `censor` flag,
  unchanged.
- **Manual / live (per `.claude/rules/testing.md`)**: confirm the bleep is audible,
  the bar appears over the mouth while speaking and disappears when done, and the
  spoken audio omits the word. Verify on BOTH Jax and Pomni (different mouth heights).

## Future work (not in this scope)

- Per-word bar/bleep timing via inline censor markers + TTS word timestamps.
- A shared `franchise` taxonomy reused for other franchise-wide behaviors.
