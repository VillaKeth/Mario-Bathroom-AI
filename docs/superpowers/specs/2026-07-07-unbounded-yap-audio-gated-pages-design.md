# Unbounded Responses, Ramble Mode & Audio-Gated Bubble Pages — Design

**Date:** 2026-07-07
**Status:** Approved (design), pre-implementation
**Builds on:** `2026-06-30-adaptive-response-length-design.md` (Component A1 — the
`_long` intent path). This spec supersedes A1's cap mechanics (500/2000 split →
single high ceiling) and upgrades the bubble sync that spec declared a non-goal.

## Problem

1. **The character can't choose to go long.** Length relief exists only when the
   *guest's* phrasing trips the long-intent regex (`_LONG_INTENT_RE`). If Rudi
   wants to tell a story unprompted, three layers amputate him:
   - `num_predict` token cap (ultra 250, dev 120–150) — cuts mid-sentence
     (`hardware.py:109–151`, applied `llm.py:194`)
   - 500-char hard truncation in `filter_response()` (`safety_filter.py:191`)
   - prompt brevity rules ("2-3 sentences max") (`mario_prompt.py:84,144`)
2. **No sanctioned rambling.** The user wants the character to be able to yap /
   filibuster about things it cares about when the situation invites it. Nothing
   in the prompt or hint system ever grants that.
3. **Bubble pages drift from speech.** Long responses already paginate
   (`mario_display.py:2859`) and audio already streams per sentence
   (`main.py:5711`), but the typewriter that drives page flips is paced by an
   *estimate* (first-chunk duration × chunk count, `client/main.py:557–559`).
   Uneven sentence lengths make page N appear before or after it is actually
   spoken. Desired behavior: text appears in bubble-sized parts, the next part
   appears only as it is actually being said, gated until everything on screen
   has been spoken.

## Goal

- Whatever the character generates is **never amputated** (safety ceiling only).
- Prompt keeps party pacing ("usually 2-3 sentences") but grants standing
  permission to go long, plus an occasional injected **ramble hint** that
  actively invites a filibuster.
- Bubble pages advance **exactly in sync with real audio playback** — each
  sentence's text is revealed while that sentence's audio clip plays, holds
  during gaps, flips pages only when speech crosses the page boundary.
- Guest input still interrupts a monologue (existing interrupt/debounce flow —
  untouched).

## Non-goals

- No changes to TTS engines, voices, or the fallback chain.
- No manual page controls (no scroll/skip buttons) — pages remain speech-driven.
- No persistent "long mode" — per-response, decided by prompt + dice each turn.
- Idle mumbles, games, web `/chat`, and mirror viewers keep their current paths.

---

## Component 1 — Length policy (server)

- **`hardware.py`:** raise `llm_num_predict` per tier — ultra → **700**,
  high → **400**, medium → **300**, low → **250**. (The tier table has four
  tiers, not five. Token cap stops being the amputator;
  the model still stops naturally on short replies, so no latency cost for the
  common case.)
- **`safety_filter.py`:** replace the `MAX_RESPONSE_CHARS = 500` constant with a
  `cap_chars` parameter. `main.py` passes
  `int(live_config.get("response_char_ceiling", 4000))` — hot-reloadable,
  runaway protection only. Keep the truncate-at-last-punctuation behavior for
  ceiling hits; log a warning when it fires.
- **`_long` path:** keep intent detection for its prompt hint ("this deserves a
  thorough answer"). Its `num_predict` becomes
  `max(base, live_config long_num_predict)`; bump the `long_num_predict` code
  default 512 → **1024**. Remove `long_char_cap` reads — superseded by the
  single ceiling.
- **Prompts (`mario_prompt.py`):**
  - line 84 base prompt: "2-3 sentences max" → "usually 2-3 sentences".
  - line 92 NEVER list: **remove "Ramble."** — it directly contradicts ramble
    mode (found during planning).
  - line 144 character builder: append standing permission — "When a story, an
    explanation, or something you love comes up, you may go long, the screen
    handles long replies."
- Per-message pacing hints (rhythm "keep it SHORT", engagement hints) stay —
  they steer, never cut.

## Component 1b — Ramble mode (new)

- **`maybe_ramble_hint()`** in `mario_prompt.py`, called from the normal-chat
  LLM path only (not games, not idle):
  - Fires with probability `live_config.get("ramble_chance", 0.12)`.
  - Mutually exclusive with the rhythm "keep it SHORT" hint and skipped when
    `_long` already fired (redundant).
  - Injected system hint: *"If this topic sparks something in you — RAMBLE.
    Stories, tangents, hot takes, things you're weirdly passionate about. Go
    long; the screen handles it."*
- When the ramble hint fires, the response is treated as `_long` for
  `num_predict` purposes (gets the 1024 budget).
- **Optional (nice-to-have, not blocking):** scale `ramble_chance` by night
  phase — late_night/after_hours multiply it (yappier as the party winds down).

## Component 2 — Streaming spans (server, `main.py:5711` block)

Today the streamer splits `tts_text` into sentences; the client displays
`display_text`. And the client *mutates* the display text on arrival
(`set_mario_text` strips emoji via `_EMOJI_RE`), so server-computed char
offsets would drift on any emoji-bearing reply. **Revised during planning:
chunks carry their display sentence text, not offsets** — the client resolves
each sentence against its own post-transform bubble text.

1. Split **`display_text`** into sentences with a new offset-safe splitter
   (`tts.split_display_sentences` — same boundary regex and <15-char merge as
   `split_into_sentences`, but NO preclean, so every sentence stays a verbatim
   substring of the display text).
2. Pair each display sentence with its TTS input via
   `pose_analyzer.analyze_text(sentence)["tts_text"]` — the exact transform the
   non-streamed path applies to the whole reply, so zero transform drift
   (`tts.build_stream_chunks`). Sentences that clean to empty (emoji-only) get
   their display text merged into the next chunk so no bubble text is orphaned.
   TTS cache keys are generated after `_preclean_tts_text()` as before; content
   chunked differently simply re-synthesizes (no stale-audio risk).
3. Wire format:
   - Chunk 0 (`mario_response` via `send_response`): new optional field
     **`chunk_text`** — sentence 0's display text.
   - Later chunks (`audio_chunk` JSON): add **`chunk_text`** likewise.
   - `is_last` semantics unchanged. Old clients ignore the extra key —
     backward compatible; a client receiving no `chunk_text` falls back
     (below).
4. Client resolution: strip emoji from the needle exactly like
   `set_mario_text`, then `find` forward from the previous span's end (repeated
   sentences resolve in order); on a miss, advance by needle length. Graceful
   by construction.

## Component 3 — Audio-gated typewriter (client)

New display method **`set_typewriter_span(target_char, duration_s)`**
(`mario_display.py`):

- Paces `_typewriter_pos` from its current position to `target_char` over
  `duration_s`, then **holds** — never reveals past the current span target.
- Existing pagination logic reads `_typewriter_pos` and is untouched: pages flip
  exactly when *spoken* text crosses the page boundary; during playback-queue
  gaps the text holds, which is precisely the requested gating.

Wiring (`client/main.py`):

- `_on_mario_text` sees chunk-0 `chunk_text` in metadata → calls
  `prepare_span_stream()` (holds the typewriter at 0 until audio starts) and
  stores the sentence as pending.
- `_on_mario_audio` (chunk-0 audio): if a pending sentence exists, resolve it
  (`resolve_span_target` — emoji-stripped `find` in the bubble text, forward
  from the last span) and attach an `on_start` callback (mechanism already
  exists — countdown reveal uses it) that calls
  `set_typewriter_span(target, clip_duration)` instead of the full-text
  estimate sync. Clip duration read from the WAV header
  (`audio_playback.wav_duration_s`), not the byte-length estimate.
- `_on_audio_chunk`: resolve `chunk_meta["chunk_text"]`, queue audio with
  `on_start = set_typewriter_span(target, chunk_duration)`.
- **Fallback:** no `chunk_text` present (non-streamed path, idle lines, old
  server) → current estimate-based `sync_typewriter_to_audio` unchanged.
- **Skipped chunk** (server-side TTS failure skips a sentence): the next
  chunk's span paces from the current position through the skipped text —
  smooth catch-up, no snapping.
- **Interrupt/reset:** `set_mario_text` and `_on_clear_audio` clear the span
  target (they already reset typewriter position and pages).

## Component 4 — Edge cases

- **WS drops mid-stream (no `is_last` ever arrives):** two cheap guards close
  this pre-existing hole. (1) The audio-wait watchdog thread now (re)starts on
  EVERY chunk: after playback goes idle it waits 0.5s (last chunk seen) or up
  to 4s (mid-stream gap) for more audio before clearing the speaking state.
  (2) In the display, a span held for >240 frames (~8s) while `_speaking` with
  text remaining releases the span limit so the rest of the text reveals at
  the fallback speed — the bubble never wedges.
- **Ceiling hit (4000 chars):** truncate at punctuation + warning log.
- **Idle mumbles / games / web chat / mirror:** untouched paths; mirror
  transcript already receives full text.

## Component 5 — Config

- New live keys (hot-reload via `live_config.get(key, default)` **code
  defaults** — `config_live.json` itself is NOT edited by this work; it is
  concurrently edited by another session and the keys are optional):
  `response_char_ceiling` (4000), `ramble_chance` (0.12). `long_num_predict`
  code default bumped to 1024; `long_char_cap` retired.
- Admin live-control page (branch `feat/admin-live-control`) may later expose
  `ramble_chance` as a slider — follow-up, not in scope.

## Data flow

```
LLM reply (num_predict: base 700 / ramble+long 1024)
  └─ filter_response(cap_chars=response_char_ceiling)      ← never 500-cut
      └─ display_text ── build_stream_chunks: [(display sentence, tts input)]
          ├─ chunk 0: send_response(text=display_text, chunk_text=s0) + audio0
          ├─ chunk i: audio_chunk{chunk_text=si} + audio_i
          └─ client: target_i = resolve_span_target(si)
                     on_start(clip_i) → set_typewriter_span(target_i, dur_i)
                       └─ _typewriter_pos drives existing pagination
                           → page flips exactly with speech, holds in gaps
```

## Testing

- **Unit (server):** `split_display_sentences` (verbatim substrings, no
  preclean, short-fragment merge); `build_stream_chunks` (display/tts pairing,
  emoji-only carry-merge, single-sentence case); ceiling behavior (under/over,
  punctuation cut, cap=False uncut); `maybe_ramble_hint` probability +
  invalid-input safety; prompt no longer bans rambling.
- **Unit (client):** `set_typewriter_span` pacing, hold-at-target, monotonic
  (never backward); `resolve_span_target` sequential + duplicate sentences +
  miss fallback; `prepare_span_stream` holds at zero; stale-span release;
  `wav_duration_s` header parse + garbage fallback.
- **Schema:** chunk-0 `mario_response` and `audio_chunk` carry `chunk_text`;
  absent on non-streamed sends.
- **Update:** any existing test asserting the 500-char cap or `long_char_cap`.
- **Live test (per `.claude/rules/testing.md` — mandatory audio verification):**
  ask for a long story → verify every chunk plays (`_play_wav: playing` …
  `done` per clip), pages flip in sync with actual speech, no page appears
  before its audio, spoken text matches bubble text, and a mid-monologue guest
  message still interrupts cleanly.

## Rollout / safety

- All new behavior degrades gracefully: missing `chunk_text` → estimate sync;
  `ramble_chance: 0` disables rambling live; `response_char_ceiling` can be
  lowered live if the party needs shorter replies (hot-reload, no restart).
- TTS cache: keys still generated after `_preclean_tts_text()`. Sentences that
  chunk differently than before simply cache-miss and re-synthesize — no
  stale-audio risk. Optional tidy-up after landing: `tts.purge_stale_cache()`
  to drop orphaned entries.
