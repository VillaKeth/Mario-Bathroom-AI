# Adaptive Response Length & Continuous Conversation — Design

**Date:** 2026-06-30
**Status:** Approved (design), pre-implementation
**Baseline tag:** `v4.1`

## Problem

Rudi's replies are deliberately short (party-line throughput + TTS latency), but
that hurts three situations a guest runs into:

1. **Guides / deep questions** ("how do I beat the ender dragon?") get a useless
   one-liner instead of a real walkthrough.
2. **Back-and-forth conversation** dies — he answers and dead-ends, and doesn't
   always drive it forward.
3. **Message floods starve him** — every new `text_input` cancels the in-progress
   response (`main.py:6476`), so an impatient guest who fires several quick
   messages makes Rudi *more* silent: he never finishes a reply.

Shortness is enforced in three places today:
- `LLM_NUM_PREDICT` token cap (~120–150 on dev, hardware-resolved) — `llm.py:39`,
  applied in the Ollama payload `llm.py:193`.
- 500-char hard truncation in `filter_response()` — `safety_filter.py:196` (the
  function already takes a `cap` param; `main.py:5332` already calls it with
  `cap=False` for the chat-backlog copy).
- Prompt brevity rules ("under 15 words, punchy") — `mario_prompt.py:94`.

## Goal

Let Rudi go long **when intent calls for it**, auto-detected, while staying punchy
by default — and stop floods from starving his output. Speaking long answers is
**full + interruptible** (existing self-interrupt cuts him off when a new guest
engages). No extra LLM call for the decision.

## Non-goals

- No change to the TTS engines or the bubble renderer (sentence-streaming +
  pagination already handle long output).
- Not touching the screen-coach feature (separate spec).
- No persistent "long mode" toggle — it's per-response, decided each turn.

---

## Component A1 — Adaptive length (intent-detected)

**Decision:** a cheap heuristic classifier, no extra model call.

- Add a `detect_length_intent(text)` helper (in `mario_prompt.py` or alongside
  `_infer_response_type` in `main.py`). Returns `"long"` when the message matches
  guide/explain intent: `how do i`, `how do you`, `guide`, `walk me through`,
  `step by step`, `explain`, `strategy`, `best way`, `tips for`, `teach me`,
  `build`, `tell me everything`, `breakdown` — gated so a short "explain?" alone
  doesn't trip it (require the message be a real question/request, length > N).
- When intent is `"long"`, for **that response only**:
  - pass a per-call `num_predict` override (~512) into `llm.generate_response`
    (thread a new optional arg; default stays `LLM_NUM_PREDICT`).
  - call `filter_response(raw, cap=False)` (or a higher cap ~2000) instead of the
    500 cap — the `cap` param already exists.
  - append a context note that relaxes brevity: *"This question deserves a
    thorough, in-character answer — give real detail and structure, don't rush
    it."*
- Output: spoken in full, interruptible. Sentence-streaming (`main.py:5483`)
  already emits the first sentence's audio fast, so latency-to-first-word is
  unchanged.
- Everything else stays on the current short defaults.

**Alternative considered:** ask the LLM to self-decide length — rejected (extra
latency on an already-slow box, and the heuristic is reliable for these phrasings).

## Component A2 — Engagement (drive the conversation)

**Decision:** prompt/behavior-level, reuse existing hooks.

- In an active back-and-forth (conversation history depth ≥ a small threshold),
  raise the rate at which Rudi ends on a hook/follow-up via the existing
  `maybe_add_question` / `maybe_challenge` (`mario_prompt.py`).
- Throttle so it is not every line (track last-N turns; skip if he just asked
  one). Keep it character-appropriate (Rudi teases, doesn't interview).

## Component A3 — Burst handling (stop starving him)

**Decision:** debounce + batch (answer the batch as a whole).

Current: `text_input` immediately cancels `_current_response_task` and clears
audio (`main.py:6464–6494`).

New policy:
- On a `text_input`, start a short **debounce window (~1.2s)**. Additional
  messages that arrive in the window are collected, not each-cancelling.
- When the window closes, fold the collected messages into **one** user turn —
  e.g. join as `"<m1> <m2> <m3>"` with a system hint that the guest sent several
  quick messages — and run **one** response.
- Only **hard-interrupt an already-speaking reply** when a new message arrives
  *after audio has started* AND looks like a deliberate redirect (non-trivial
  length / new question), not for every keystroke-message.
- Edge cases: window resets on each new message up to a max cap (~3s) so a
  continuous typer still eventually gets an answer; a single message past the
  window behaves exactly as today (no added latency for the common case beyond
  the 1.2s debounce — tune this).

**Alternative considered:** FIFO queue answered sequentially — rejected: with a
slow LLM the queue piles up and he falls behind; batching collapses the burst
into one timely answer.

---

## Data flow (text path)

```
text_input ──▶ debounce/batch (A3) ──▶ _generate_and_send_response
                                          │
                                          ├─ detect_length_intent (A1) ─▶ long? set num_predict, cap=False, relax-prompt note
                                          ├─ build_context (+A2 engagement nudge)
                                          ├─ llm.generate_response(ctx, text, model, num_predict?)
                                          ├─ filter_response(raw, cap=<intent>)
                                          └─ analyze_text ▶ sentence-stream TTS ▶ send (interruptible)
```

## Testing

- **A1 unit:** `detect_length_intent` — guide phrasings → `long`; greetings,
  roasts, short banter → not long; false-positive guards ("explain?" alone).
- **A1 integration:** a long-intent prompt yields `num_predict` override + uncapped
  filter; a normal prompt is unchanged (still ≤500, ≤default tokens).
- **A2:** engagement throttle — follow-up appears in conversation, not on
  consecutive turns, not on one-off party lines.
- **A3:** burst of N messages within the window → exactly ONE response covering
  them; a lone message → single response (no regression); a redirect mid-speech
  → interrupt still fires.
- Manual: confirm long answers stream first audio quickly and are interruptible;
  confirm a flood no longer leaves Rudi silent.

## Rollout / safety

- Baseline `v4.1` tagged before this work.
- A3 changes the interrupt flow — the riskiest piece; land it behind a small
  config flag (`burst_debounce_ms`, 0 = old behavior) so it can be disabled live
  via hot-reload if it misbehaves at the party.
