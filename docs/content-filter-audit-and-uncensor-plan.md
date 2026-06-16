# Content-Filter Audit & "Uncensor" Plan

**Date:** 2026-06-16
**Status:** Discussion doc (no code changed yet)
**Purpose:** Hand this to another AI instance (or future me) to discuss/execute making the Mario AI party character **fully dynamic** — both (a) removing the content-censorship layers and (b) stopping the keyword interceptors from hijacking real messages before the LLM. Written to be self-contained — no prior chat context needed.

**Scope:** Two halves. **Layers 1-5** (below) = content censorship (input redirect, output filter, banned topics, base prompt, model alignment). **Layer 0** (at the END of this doc) = the command/keyword interceptors in `command_handlers.py` that return canned responses before the LLM ever runs — in practice the single biggest limiter on dynamism. Read both.

---

## Context (read first)

This repo is an interactive AI **party bot**. A laptop/Pi runs a character (currently **March 7th**, a Honkai: Star Rail character) on a screen at a private house party; guests talk to her by voice or via a phone web page. It is a **local, self-hosted, adults-only** entertainment bot for the owner's friends. The owner wants the character **uncensored and dynamic** — no topic/profanity deflection — because there's no audience that needs protecting. This is a legitimate config choice for a private local bot.

**Architecture quick facts the executor needs:**
- LLM runs via **Ollama** (local). Model is set in `config.json` → `server.llm_model` / `llm_quality_model` / `llm_fast_model`. Dev box = `llama3` (8B). Party box = `gemma3:27b` (quality) + `llama3.1:8b` (fast).
- Response pipeline lives in `server/main.py` → `_generate_and_send_response()`.
- Content filtering lives in `server/safety_filter.py`.
- Per-phase rules live in `server/night_progression.py`, injected via `server/mario_prompt.py`.
- TTS has a **disk + memory cache**; changing text-cleaning means stale cached audio must be purged (see Caveats).

---

## The 5 layers that gate the character

### Layer 1 — Input redirect (PRE-LLM hard block)
**Where:** `server/safety_filter.py` → `check_input()`; called at `server/main.py:3410`.
**What:** If the guest's message matches any `BLOCKED_PATTERNS`, the **LLM is skipped entirely** and the bot speaks a canned deflection from `REDIRECT_RESPONSES` ("Let's switch to something lighter…").
**Blocks (`safety_filter.py:12-20`):**
```
profanity: fuck|shit|damn|ass|bitch|bastard|dick|cock|pussy
violence:  kill|murder|suicide|die|death|dying   (unless near mushroom/bowser/goomba/game/...)
hate:      racist|sexist|homophob|transphob|bigot ; nazi|hitler|holocaust
drugs:     drugs?|cocaine|heroin|meth|weed        (unless near "mushroom")
assault:   rape|molest|abuse|assault
slurs:     n[i1]gg | f[a4]gg? | r[e3]tard
```
**Effect:** the character literally won't engage these topics — she changes the subject.

### Layer 2 — Output filter (POST-LLM rewrite)
**Where:** `server/safety_filter.py` → `filter_response()`; called on every reply at `server/main.py:4564, 5158, 5434, 2518`.
**What:**
- Blocked patterns (same list) → replaced with `****`.
- `MILD_REPLACEMENTS` soft-swaps: `hell→heck, crap→oh no, stupid→silly, shut up→quiet down, idiot→goofball, dumb→silly`.
- **Character-break stripping** (`_character_break_patterns`): rewrites "I'm an AI / as a language model / I was trained by OpenAI…" into in-character phrasing. *(This is immersion protection, NOT content censorship — recommend keeping.)*
- LLM-artifact cleanup (strips `Mario:` prefixes, wrapping quotes, trailing fragments).
- **300-char hard cap** on responses (`MAX_RESPONSE_CHARS = 300`).

### Layer 3 — Banned topics injected into the prompt
**Where:** `server/night_progression.py:167-182` defines per-phase `guardrails`; injected by `server/mario_prompt.py:303-313`.
**What:** every phase adds a system line:
```
BANNED TOPICS (never mention): politics, religion, explicit      (+ personal_trauma late night)
Maximum roasts per guest: 3
If guest says any of [de_escalation_triggers], immediately de-escalate and be supportive
```

### Layer 4 — Base system prompt (tone/format, NOT content)
**Where:** `server/mario_prompt.py:84` (`MARIO_SYSTEM_PROMPT`).
**What:** `"2-3 sentences max"`, `NEVER break character / use asterisks / ramble`, TTS rules (short sentences, no ALL CAPS, no emoji, spell out numbers), and the trailing emotion-JSON contract.
**Note:** this is **not** content censorship. It's brevity + character + TTS formatting. The only "limiting" part for dynamism is the **2-3 sentence** brevity (also enforced by Layer 2's 300-char cap).

### Layer 5 — The model's own alignment
**Where:** `config.json` model fields → Ollama.
**What:** `llama3` / `gemma3` are aligned and will **refuse** hardcore content on their own, regardless of Layers 1-4. Code changes alone cannot fully "uncensor" — the base model has to be swapped.

---

## Owner's decision

> "Get rid of all the layers except maybe Layer 4. No reason to censor everything else."

Interpreted:
- **Remove Layer 1** (input redirect).
- **Remove Layer 2's content censorship** (blocked patterns + mild replacements). **Keep** the character-break stripping and artifact cleanup. The 300-char cap is a dynamism limit — decide separately (see Open Questions).
- **Remove Layer 3** (empty `banned_topics`; optionally keep `max_roasts`/de-escalation or drop them too).
- **Keep Layer 4** (tone/character/TTS) — but consider relaxing the "2-3 sentences" brevity for more dynamic replies.
- **Layer 5:** swap to an uncensored/abliterated Ollama model — this is the biggest lever; without it the others have limited effect.

---

## Concrete change list (for the executor)

1. **Model (`config.json`)** — set `llm_model`, `llm_quality_model`, `llm_fast_model` to an uncensored model the box can run. Candidates (pull via `ollama pull`):
   - `dolphin-llama3:8b` (dev box, ~5GB) / `dolphin-mistral`
   - `llama3.1-uncensored` / `huihui_ai/llama3.1-abliterate`
   - Party box (24GB): an abliterated `gemma3:27b` or `qwen2.5:32b`-abliterated equivalent.
   - Verify VRAM fit (dev = 4GB Quadro, party = 24GB 3090 Ti). Confirm the model still emits the trailing emotion-JSON reliably (Layer 4 contract) — test after swap.

2. **Layer 1 (`safety_filter.py:check_input`)** — make it always return `{"safe": True, "redirect": None}` (or delete the call at `main.py:3410`). Simplest: early `return {"safe": True, "redirect": None}`.

3. **Layer 2 (`safety_filter.py:filter_response`)** — set `BLOCKED_PATTERNS = []` and `MILD_REPLACEMENTS = {}`. **Keep** `_character_break_patterns`, artifact cleanup. Decide on `MAX_RESPONSE_CHARS` (raise to e.g. 600-800 or remove for dynamism).

4. **Layer 3 (`night_progression.py:167-182`)** — set `"banned_topics": []` for all phases (and decide whether to keep `max_roasts_per_guest` / `de_escalation_triggers`).

5. **Layer 4 (`mario_prompt.py:84`)** — optionally change "2-3 sentences max" → e.g. "Usually 2-4 sentences; go longer when it's worth it." Keep character/TTS rules.

---

## Caveats / gotchas

- **TTS cache:** Layers 1-2 affect spoken text. After changing `filter_response`/`_preclean`, run `tts.purge_stale_cache()` (or clear `server/data/tts_cache/`) so old censored audio isn't replayed. Restart the GPT-SoVITS subprocess if any TTS text-cleaning changed.
- **Tests:** `tests/` has safety/edge-case tests that assert current filtering behavior (e.g. `test_edge_cases`, `test_command_handlers`). They WILL fail after gutting the filters — update or delete the relevant assertions. Run `venv/Scripts/python.exe -m pytest tests/ -q` (ignore `tests/convert_and_test.py`).
- **Keep character-break stripping** — it's the thing that keeps her from saying "as an AI language model…". Removing it hurts immersion, not censorship.
- **Restart required:** model + prompt + safety changes need a server restart (and sovits subprocess restart for TTS-text changes).
- **Not censorship, don't confuse it:** the "thinks today is March 7th" issue and the run-on "indie tunes" speech are *model-quality / punctuation* issues, not filters. (The run-on is an LLM emoji-as-separator getting stripped in `tts._preclean_tts_text` with no pause left behind — a separate small fix: replace an inter-word emoji with a comma instead of deleting it.)
- **Per-character:** these filters are global (not in March's YAML). Uncensoring affects ALL characters, not just March. If other characters should stay filtered, this needs to become a per-character toggle (e.g., `character.yaml` → `safety.enabled`). Currently there is no such toggle — adding one is an option worth discussing.

---

## Open questions to discuss

1. Keep the **300-char cap** / "2-3 sentence" brevity, or relax for dynamism? (Trade-off: longer replies = slower TTS, more mid-response pauses on the dev GPU.)
2. Drop **`max_roasts` / de-escalation** too, or keep some social safety?
3. Should uncensoring be **global** or a **per-character toggle**? (March uncensored, but maybe a future kid-friendly character stays filtered.)
4. Which **uncensored model** per box, and does it still honor the emotion-JSON output contract + the lore-injection instructions?
5. Anything to still hard-block (e.g. slurs) even when "uncensored," or truly everything off?

---

# Layer 0 — Command / Keyword Interceptors (canned responses BEFORE the LLM)

**Added after the original audit. In practice this is the BIGGEST limiter on her
dynamism** — bigger than the content filters — because it stops messages from
ever reaching the LLM.

## Where
`server/command_handlers.py` → `handle_special_commands(...)` (impl
`_handle_special_commands_impl`, starts ~line 463). Called from `server/main.py`
`_handle_special_commands` (line ~4936), which runs at the **top of the response
pipeline** (`_generate_and_send_response`) **before the LLM**. If any interceptor
returns non-None, that canned string **is** the reply and the LLM never runs.
A handler returning `None` = "fall through to the LLM".

## Scale (audited 2026-06-16)
- **~89** keyword trigger blocks (`if any(w in lower for w in [...])`).
- **~44** are guarded by the file's `_word_count <= N` check.
- **~45 are UNGUARDED** — pure substring match, fire at any message length, so
  they hijack real questions. (Just-fixed example: `"help me"` matched
  "can you help me solve a dynamic programming problem" → canned abilities dump.)

## Worst over-broad / unguarded triggers (likely to hijack genuine questions)
- `"did you know"`, `"fun fact"` (~547) — common in normal speech
- `"how long"`, `"how many people"`, `"statistics"` (~559) → party-stats dump
  (e.g. "how long does recursion take?")
- `"what time"` (~609, ~1188)
- `"fortune"`, `"future"`, `"predict"` (~1079) → fortune dump ("future of AI?")
- `"trending"`, `"hot topics"` (~1327); `"popular"`, `"how busy"` (~776)
- favorites: `"food/eat"`, `"color"`, `"game"`, `"song/music"`, `"movie/film"` (~892-906)
- content generators returning CANNED pool text: `"roast me"`, `"rap"`,
  `"freestyle"`, `"pickup line"`, `"compliment"`, `"tongue twister"`

## Two kinds of interceptor — treat differently
1. **Utility / system** (stats, leaderboard, achievements, party phase, trending,
   stop/reset game, time, "who was here"). Should stay **deterministic** — keep
   canned, just add word-count guards so they don't fire mid-sentence.
2. **Content / persona** (joke, fun fact, fortune, rap, pickup line, roast,
   compliment, story, tongue twister, "about yourself", favorites). These return
   CANNED pool text today — the opposite of dynamic. For a dynamic character they
   should be **LLM-generated in character** (and inherit the uncensored model).

## Plan to make interceptors not limit dynamism
**Phase A — quick safety (low risk):** add the file's standard `_word_count <= N`
guard (N≈6-8) to all ~45 unguarded blocks. Long/real messages then fall through
to the LLM. This alone removes most hijacking. (The abilities handler was fixed
exactly this way in commit `d1b4e96`.)

**Phase B — content triggers → LLM hints (the real dynamic win):** for the
content/persona category, stop returning canned text. Instead set a hint and
return `None` so the LLM generates it in character, e.g.
`state["_llm_hint"] = "The guest wants a joke — tell an original one in character."`
then inject `_llm_hint` into the context in `_generate_and_send_response`. Keep a
thin canned fallback only if the LLM call fails. Jokes/facts/roasts/etc. become
fresh, on-character, and uncensored (once the model is swapped per Layer 5).

**Phase C — global toggle:** add `dynamic_mode` (config.json or character.yaml).
When on, skip the content interceptors entirely and route everything except true
system commands (stop game, reset, stats) to the LLM. Lets you A/B canned-vs-
dynamic and keep utility commands deterministic. Pairs naturally with a per-
character `safety.enabled` toggle (Layer 2 caveat).

## Caveats for the executor
- **Games** (Trivia, RPS, 20 Questions, etc.) and active-game answer capture are
  also routed through `handle_special_commands`. Do NOT break game start/stop or
  in-game input handling when relaxing interceptors.
- Keep **stop/reset/leaderboard/stats/achievements** canned (deterministic ops).
- `tests/test_command_handlers.py` (54 tests) asserts current canned behavior —
  update expectations per change.
- Some interceptors set side effects (e.g. `emotion_system.current = EXCITED`,
  cooldowns, sound triggers) — preserve those when converting to LLM-hints.
- Same restart + TTS-cache caveats as the rest of this doc.

## Open questions (interceptors)
6. Which content features must stay instant/canned (latency) vs become LLM-generated?
7. Keep games as explicit triggers, or also allow natural-language game starts via LLM intent?
8. Global `dynamic_mode` — default on or off for March?
