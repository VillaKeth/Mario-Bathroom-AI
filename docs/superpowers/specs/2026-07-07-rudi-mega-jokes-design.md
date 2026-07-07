# Rudi Mega-Joke System — Design Spec

**Date:** 2026-07-07
**Status:** Design (pending user review → implementation plan)
**Character:** Rudi (generalizes to any character later)

## 1. Problem

Rudi's jokes are a **static pool of 20**, cycled by index (`idle_behavior.get_joke()` →
`_joke_index += 1`). At an 8-hour party he repeats within minutes. A *specific*
"joke about X" already routes to the LLM (`command_handlers.py:535`); only the
**generic** pool is thin. Goal: a large, genuinely-funny, on-voice joke system that
rarely repeats and stays fresh — woven into idle chatter.

## 2. Goals / Success Criteria

- **~1,000 curated jokes**, each vetted funny + in Rudi's voice.
- **Rarely repeats** in an 8-hour party (shuffle-bag, no-repeat-until-exhausted).
- **Fresh**: 10% of jokes are live-LLM "infinite" jokes, 90% instant cached.
- **Idle-first**: jokes are a first-class idle-chatter behavior, not just on-request.
- **Instant audio**: the 1,000 pool jokes are TTS-precached.
- **Non-goal (YAGNI):** 10k jokes (quality drops, party never uses them), per-guest
  joke personalization, real-time joke rating UI.

## 3. Rudi's Voice Profile (drives generation + judging)

Dry, witty, nerdy. Tech / programming / AI / internet-culture humor, meta jokes
(self-aware he's an AI in a bathroom), mild sass and edge, deadpan delivery.
Reference existing pool: *"I told a joke about UDP but I'm not sure you got it."* /
*"Why did the AI cross the road? It didn't. It was stuck in a bathroom."* Not:
knock-knock kiddie jokes, wholesome dad-joke-only, anything off-voice-sappy.

## 4. Architecture

Three decoupled units: **(A) build pipeline** (offline, produces the pool),
**(B) runtime selection** (serves jokes), **(C) idle integration** (when he tells them).

### 4A. Build Pipeline (offline, one-time; re-runnable)

```
6 sources → candidates.jsonl (~6000) → judge → scored.jsonl → top 1000 → curated.yaml → precache
```

**Sources (~1,000 each, source-tagged):**
| Source | Method |
|---|---|
| `claude` | Claude authors 1,000 in Rudi's voice (batched; may fan out via subagents/workflow) |
| `online` | ~1,000 collected from public joke sources/datasets/APIs (r/jokes-style, incl. long story-jokes) |
| `ollama` | Local batch-gen (llama3/hermes/qwen) in Rudi's voice |
| `gpt` | mcp_chatgpt browser, `--provider chatgpt`, ~50–100 jokes/prompt (TEXT — **not** image-capped) |
| `gemini` | mcp_chatgpt browser, `--provider gemini` |
| `grok` | mcp_chatgpt browser, `--provider grok` |

**Candidate format** — `characters/rudi/jokes/candidates.jsonl`, one per line:
`{"id": "<hash>", "text": "...", "source": "claude|online|ollama|gpt|gemini|grok"}`.
De-dupe by exact hash at write time; semantic de-dupe happens in the judge.

**Online jokes** default to a **light Rudi-voice rewrite** (reframe delivery to his
deadpan tech-nerd voice) when it improves the joke; kept verbatim when already perfect.
The rewrite is an LLM pass; the judge scores the rewritten form.

### 4B. Judge / Curation → best 1,000

A Claude LLM-judge scores every candidate:
- `funny` (1–10) — is it actually funny?
- `rudi_fit` (1–10) — does it match the voice profile (§3)?
- `tts_ok` (bool) — speakable: not too long for a bathroom bit, no unreadable formatting,
  no ASCII art. (Long story-jokes allowed but flagged; capped share in the final pool.)
- Semantic de-dupe: near-duplicate jokes collapse to the highest-scored one
  (embedding similarity via the existing fastembed/Qdrant stack).

**Selection:** rank by `funny*2 + rudi_fit`, keep top **1,000** that pass `tts_ok`,
with a cap of ~15% long story-jokes so the pool stays snappy. Output:
`characters/rudi/jokes/curated.yaml` (`jokes: [ ... ]`). Keep `scored.jsonl`
(full corpus + scores) so re-runs (e.g. when browser sources finish) re-judge without
re-generating.

### 4C. Storage

- `characters/rudi/jokes/curated.yaml` — the live 1,000-joke pool (git-committed).
- `characters/rudi/jokes/candidates.jsonl`, `scored.jsonl` — build artifacts
  (git-ignored; large, regenerable).
- Wiring: `character_loader.get_idle_messages()` (or a sibling loader) exposes the
  curated jokes to `idle_behavior` as the `jokes` pool. If `curated.yaml` exists it
  supersedes the small `idle/messages.yaml` `jokes:` block.

### 4D. Runtime Selection — 90/10 hybrid

`idle_behavior.get_joke()` rewritten:
- **90%** → next joke from a **shuffle-bag** over the 1,000 pool: shuffle once, draw
  without replacement, reshuffle when exhausted → no repeat until the whole pool is used.
  (Replaces the current `_joke_index` linear cycle.)
- **10%** → a **live-LLM joke**: prompt the LLM (Rudi system prompt + "tell one fresh,
  short, in-character joke") → returned uncached. On LLM error/timeout → fall back to the
  90% pool path (never fail to produce a joke).
- Roll is per-call `random.random() < 0.10` (config-tunable `joke_llm_chance`, default 0.10).

### 4E. Idle-Chatter Integration

Jokes become a first-class idle behavior in `idle_behavior.py`'s category rotation
(alongside mumbles/songs/etc.), so Rudi organically drops jokes during idle — routed
through the same `get_joke()` 90/10 split. Idle joke frequency respects existing
idle pacing/cooldowns and night-phase weighting (jokes lean up in later/UNHINGED phases,
which the code already does via `self._jokes * 3`).

### 4F. TTS Precache

Extend the startup precache (`tts.precache_phrases` / idle precache) to pre-synthesize
the 1,000 curated jokes over time (background, yields to user TTS) so a 90%-path joke
plays instantly. Live-LLM (10%) jokes are synthesized on demand (cache miss, acceptable
since rare). Per the TTS cache convention, precache uses the character's active voice.

## 5. Data Flow

1. **Build:** run generators → `candidates.jsonl`; run judge → `scored.jsonl` →
   write top-1000 → `curated.yaml`; kick precache.
2. **Load:** on server start, loader reads `curated.yaml` into the `jokes` pool.
3. **Serve:** idle loop or "tell me a joke" → `get_joke()` → 90% shuffle-bag / 10% LLM.

## 6. Error Handling

- **Empty/missing `curated.yaml`** → fall back to `idle/messages.yaml` `jokes:` (current 20).
- **Live-LLM failure** (10% path) → fall back to pool joke.
- **Generator source fails** (e.g. a browser provider down) → build proceeds with the other
  sources; pool just draws from fewer candidates. Build never blocks on one source.
- **Judge partial failure** → un-scored candidates are excluded, not fatal.

## 7. Testing

- `get_joke()`: shuffle-bag exhausts all 1,000 before repeating; 90/10 split holds over N
  draws (seeded RNG); LLM-path failure falls back to pool.
- Loader: `curated.yaml` supersedes `idle/messages.yaml`; missing file → graceful fallback.
- Judge: scoring + top-N selection + semantic-dedupe on a small fixture corpus.
- Idle integration: jokes appear in the idle rotation; frequency respects cooldowns.
- **Audio (mandatory):** verify a precached pool joke plays start→finish and a 10%
  live-LLM joke synthesizes + plays, both in Rudi's voice (per `.claude/rules/testing.md`).

## 8. Implementation Phases

1. **Runtime + loader** (4C/4D/4E): shuffle-bag, 90/10, idle integration, curated.yaml
   loader with fallback — works with the *current* 20 jokes immediately.
2. **Build pipeline** (4A/4B): generators + judge → produce `curated.yaml` (1,000).
   Claude + Ollama + online first; GPT/Gemini/Grok fold in and re-judge.
3. **Precache** (4F): pre-synthesize the pool.

Phase 1 ships value with no generation; Phases 2–3 fill + speed the pool.

## 9. Open Questions

- Online-joke licensing: public/user-submitted joke corpora only; personal-use party bot.
- `joke_llm_chance` lives in `config_live.json` (hot-reloadable) — confirm at plan time.
