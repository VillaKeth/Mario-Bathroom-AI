# Unbounded Responses, Ramble Mode & Audio-Gated Bubble Pages — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The character is never length-amputated, occasionally gets explicit permission to ramble, and long replies reveal in the speech bubble exactly in sync with the audio actually being spoken (page flips gated on real playback).

**Architecture:** Server-side, the 500-char truncation becomes a high live-config ceiling and `num_predict` rises per hardware tier; a probabilistic "ramble hint" is injected into the LLM context. The existing sentence-streaming TTS pipeline is reworked to split the *display* text into sentences (pairing each with its TTS-cleaned input via `analyze_text`) and to attach each sentence's display text to its audio chunk (`chunk_text`). Client-side, each audio chunk's `on_start` callback (existing mechanism) advances a new span-limited typewriter to the end of that sentence, paced to the clip's real duration; the existing bubble pagination reads the typewriter position unchanged, so pages flip exactly with speech.

**Tech Stack:** Python 3 (FastAPI/WebSocket server, Pygame client), pytest, Ollama LLM, GPT-SoVITS/Edge TTS.

**Spec:** `docs/superpowers/specs/2026-07-07-unbounded-yap-audio-gated-pages-design.md`

## Global Constraints

- Branch: work happens on `feat/admin-live-control` (spec already committed there). Before EVERY commit run `git branch --show-current` and confirm it prints `feat/admin-live-control` (multiple Claude sessions share this worktree).
- `git add <specific files>` only — NEVER `git add -A` (Qdrant `.lock` files must not be committed). NEVER add `config.json` or `config_live.json` (untracked secret / concurrently edited by another session — this plan does not touch either file; new config keys work purely via `live_config.get(key, default)` code defaults).
- Commit trailer (both lines, every commit):
  `Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>`
  `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`
- No ellipsis (`...`) in any hardcoded string that can reach TTS; use commas or periods.
- WebSocket response type stays `"mario_response"`.
- Run tests with: `venv\Scripts\python -m pytest tests\<file> -v` from the repo root (Windows; the venv has all deps including pygame).
- Character-agnostic text only in shared modules (no "Mario" in new user-visible strings).
- New-feature debug logging follows each file's existing pattern (`logger` in server modules and client modules — they all have loggers).

---

### Task 1: Response ceiling — `filter_response` gains `cap_chars`, main.py drops the 500/2000 split

**Files:**
- Modify: `server/safety_filter.py:140-206` (`filter_response`)
- Modify: `server/main.py:5550-5559` (filter call site)
- Test: `tests/test_response_ceiling.py` (new)

**Interfaces:**
- Produces: `filter_response(text: str, cap: bool = True, cap_chars: int = 4000) -> str`. `cap=False` still skips the length cap entirely (chat-backlog full text). All existing callers that pass only `(text)` or `(text, cap=...)` keep working — the default ceiling just rises from 500 to 4000.
- Produces: main.py reads `live_config.get("response_char_ceiling", 4000)` each response (hot-reloadable).

- [ ] **Step 1: Write the failing test**

Create `tests/test_response_ceiling.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))
from safety_filter import filter_response


def test_long_response_no_longer_cut_at_500():
    # 60 sentences x ~25 chars = ~1500 chars — was amputated at 500 before.
    text = " ".join(f"This is sentence number {i}." for i in range(60))
    out = filter_response(text, cap=True)
    assert len(out) > 1000, f"still amputated: {len(out)} chars"


def test_ceiling_cuts_at_sentence_boundary():
    text = " ".join(f"This is sentence number {i}." for i in range(300))  # ~8000 chars
    out = filter_response(text, cap=True, cap_chars=4000)
    assert len(out) <= 4000
    assert out.endswith((".", "!", "?")), f"bad tail: ...{out[-20:]!r}"


def test_custom_low_ceiling_respected():
    text = " ".join(f"Sentence number {i} here." for i in range(40))
    out = filter_response(text, cap=True, cap_chars=300)
    assert len(out) <= 300


def test_cap_false_never_cuts():
    text = " ".join(f"This is sentence number {i}." for i in range(300))
    out = filter_response(text, cap=False)
    assert len(out) > 6000


def test_short_response_unchanged():
    text = "Wahoo, what a great party!"
    assert filter_response(text, cap=True) == text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv\Scripts\python -m pytest tests\test_response_ceiling.py -v`
Expected: `test_long_response_no_longer_cut_at_500` FAILS (output cut to ≤500); `test_ceiling_cuts_at_sentence_boundary` and `test_custom_low_ceiling_respected` FAIL with `TypeError: filter_response() got an unexpected keyword argument 'cap_chars'`. The other two pass already.

- [ ] **Step 3: Implement `cap_chars`**

In `server/safety_filter.py`, change the signature and docstring (line 140):

```python
def filter_response(text: str, cap: bool = True, cap_chars: int = 4000) -> str:
    """Filter the response for inappropriate content and LLM artifacts.

    cap=True (default) enforces the cap_chars ceiling on the spoken/displayed
    text — a runaway-protection limit, not a style choice (the prompt handles
    pacing). cap=False skips only the length cap (all cleaning/filtering still
    applies), yielding the full 'what she meant to say' text for the chat
    backlog.
    """
```

And replace the cap block (lines 189-201):

```python
    # Enforce the maximum response length ceiling — runaway protection only.
    # Skipped when cap=False so callers can capture the full untruncated reply.
    MAX_RESPONSE_CHARS = max(200, int(cap_chars))
    if cap and len(text) > MAX_RESPONSE_CHARS:
        # Try to cut at a sentence boundary
        truncated = text[:MAX_RESPONSE_CHARS]
        last_punct = max(truncated.rfind('.'), truncated.rfind('!'), truncated.rfind('?'))
        if last_punct > MAX_RESPONSE_CHARS // 2:
            text = truncated[:last_punct + 1]
        else:
            text = truncated.rstrip() + "."
        logger.warning(f"[DEBUG_SAFETY] Response hit char ceiling — truncated from {len(original)} to {len(text)} chars")
```

(The old `if DEBUG_SAFETY: logger.info(...)` inside the cap block is replaced by the unconditional `logger.warning` — ceiling hits should always be visible.)

- [ ] **Step 4: Simplify the main.py call site**

In `server/main.py` replace lines 5550-5559:

```python
    _raw_response = response_text
    _is_long = bool(locals().get("_long"))
    _to_filter = _raw_response
    if _is_long:
        _char_cap = int(live_config.get("long_char_cap", 2000))
        if len(_to_filter) > _char_cap:
            _to_filter = _to_filter[:_char_cap]
    response_text = filter_response(_to_filter, cap=not _is_long)
    # Uncapped clean version for the chat backlog ("what she meant to say").
    _full_clean = filter_response(_raw_response, cap=False)
```

with:

```python
    _raw_response = response_text
    # Single high ceiling (runaway protection) — the character is never
    # style-truncated; the prompt handles pacing. Hot-reloadable live.
    _ceiling = int(live_config.get("response_char_ceiling", 4000))
    response_text = filter_response(_raw_response, cap=True, cap_chars=_ceiling)
    # Uncapped clean version for the chat backlog ("what she meant to say").
    _full_clean = filter_response(_raw_response, cap=False)
```

- [ ] **Step 5: Run the new tests plus neighbors**

Run: `venv\Scripts\python -m pytest tests\test_response_ceiling.py tests\test_safety_toggle.py tests\test_tadc_censor.py tests\test_adaptive_length.py -v`
Expected: all PASS. If a pre-existing test asserts the 500 cap or `long_char_cap`, update that assertion to the new default (4000) — the behavior change is the point of this task. (Note: the suite has ~24 pre-existing failures unrelated to this branch; only judge the files listed here.)

- [ ] **Step 6: Commit**

```bash
git branch --show-current   # must print: feat/admin-live-control
git add server/safety_filter.py server/main.py tests/test_response_ceiling.py
git commit -m "feat(length): replace 500-char amputation with live-config ceiling (default 4000)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>
Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: Raise `num_predict` per hardware tier; unify long budget at 1024

**Files:**
- Modify: `server/hardware.py:102-157` (`_TIER_DEFAULTS`)
- Modify: `server/main.py:5440` (`long_num_predict` default)

**Interfaces:**
- Produces: tier defaults `llm_num_predict` — ultra `700`, high `400`, medium `300`, low `250`.
- Produces: `_long_np` default becomes `1024` (Task 3 rewrites this same line again to include the ramble hint — that is expected; this task just establishes the new numbers so it can be reviewed/reverted independently).

- [ ] **Step 1: Edit the tier table**

In `server/hardware.py` change each tier's `llm_num_predict`:
- line 109 (`"ultra"`): `"llm_num_predict": 250,` → `"llm_num_predict": 700,`
- line 123 (`"high"`): `"llm_num_predict": 150,` → `"llm_num_predict": 400,`
- line 137 (`"medium"`): `"llm_num_predict": 120,` → `"llm_num_predict": 300,`
- line 151 (`"low"`): `"llm_num_predict": 150,` → `"llm_num_predict": 250,`

(No latency cost for short replies — the model stops at end-of-turn; `num_predict` is only the allowed maximum.)

- [ ] **Step 2: Bump the long budget default**

In `server/main.py` line 5440:

```python
        _long_np = int(live_config.get("long_num_predict", 512)) if _long else None
```

becomes:

```python
        _long_np = int(live_config.get("long_num_predict", 1024)) if _long else None
```

- [ ] **Step 3: Sanity-run the adaptive-length tests**

Run: `venv\Scripts\python -m pytest tests\test_adaptive_length.py -v`
Expected: all PASS (the num_predict test passes an explicit 512 override — unaffected).

- [ ] **Step 4: Commit**

```bash
git branch --show-current   # must print: feat/admin-live-control
git add server/hardware.py server/main.py
git commit -m "feat(length): raise num_predict tiers (ultra 700) and long budget to 1024

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>
Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: Ramble mode — `maybe_ramble_hint()` + prompt permission + main.py injection

**Files:**
- Modify: `server/mario_prompt.py:84-97` (base prompt), `server/mario_prompt.py:140-144` (character builder), new function near `get_rhythm_hint` (~line 1658)
- Modify: `server/main.py:5437-5445` (length-intent block)
- Test: `tests/test_ramble_hint.py` (new)

**Interfaces:**
- Consumes: `live_config.get("ramble_chance", 0.12)` (main.py already imports `live_config`).
- Produces: `mario_prompt.RAMBLE_HINT: str` and `mario_prompt.maybe_ramble_hint(chance: float = 0.12) -> str` (returns `RAMBLE_HINT` or `""`).

- [ ] **Step 1: Write the failing test**

Create `tests/test_ramble_hint.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))
import mario_prompt


def test_chance_one_always_fires():
    for _ in range(5):
        assert mario_prompt.maybe_ramble_hint(1.0) == mario_prompt.RAMBLE_HINT


def test_chance_zero_never_fires():
    for _ in range(50):
        assert mario_prompt.maybe_ramble_hint(0.0) == ""


def test_invalid_chance_is_safe():
    assert mario_prompt.maybe_ramble_hint(None) == ""
    assert mario_prompt.maybe_ramble_hint("nope") == ""


def test_hint_is_tts_safe_and_character_agnostic():
    assert "..." not in mario_prompt.RAMBLE_HINT
    assert "Mario" not in mario_prompt.RAMBLE_HINT


def test_base_prompt_no_longer_bans_rambling():
    # The old prompt said "NEVER: ... Ramble. ..." — that contradicts ramble mode.
    never_line = [l for l in mario_prompt.MARIO_SYSTEM_PROMPT.splitlines()
                  if l.startswith("NEVER:")][0]
    assert "Ramble" not in never_line
    assert "2-3 sentences max" not in mario_prompt.MARIO_SYSTEM_PROMPT


def test_character_prompt_grants_long_permission():
    prompt = mario_prompt._character_system_prompt()
    assert "screen handles long replies" in prompt
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv\Scripts\python -m pytest tests\test_ramble_hint.py -v`
Expected: FAIL — `AttributeError: module 'mario_prompt' has no attribute 'maybe_ramble_hint'`, and the two prompt assertions fail.

- [ ] **Step 3: Implement**

3a. In `server/mario_prompt.py` line 84, change the base prompt's first line and the NEVER line (line 92):

```python
MARIO_SYSTEM_PROMPT = """You are a friendly AI character. Usually 2-3 sentences.
```

```python
NEVER: Break character. Use asterisks. Repeat yourself.
```

(Only those two lines change; the rest of the triple-quoted block stays byte-identical, including the TTS line and the JSON-emotion footer.)

3b. In `_character_system_prompt()` line 144, extend the closing sentence:

```python
               "Always speak and answer as this character. Usually 2 to 4 sentences; go longer when the moment is worth it. "
               "When a story, an explanation, or something you love comes up, you may go long, the screen handles long replies.")
```

3c. Add near `get_rhythm_hint` (below `reset_rhythm`, ~line 1673):

```python
# Ramble mode — occasionally grant explicit permission to filibuster.
RAMBLE_HINT = ("If this topic sparks something in you, RAMBLE. Stories, tangents, hot takes, "
               "things you are weirdly passionate about. Go long, the screen handles it.")

def maybe_ramble_hint(chance: float = 0.12) -> str:
    """Roll the ramble dice: return RAMBLE_HINT with the given probability.

    chance comes from live_config ("ramble_chance"), so 0 disables it live."""
    try:
        chance = float(chance)
    except (TypeError, ValueError):
        return ""
    if chance > 0 and random.random() < chance:
        return RAMBLE_HINT
    return ""
```

3d. In `server/main.py`, replace lines 5437-5445 (the length-intent block):

```python
        # Detect length intent and set token budget for this turn
        _length_intent = mario_prompt.detect_length_intent(text)
        _long = (_length_intent == "long")
        if _long:
            ctx.append({"role": "system", "content":
                "This question deserves a thorough, in-character answer — give real "
                "detail and clear structure, do not rush it or cut it short."})
            logger.info(f"[LENGTH] long-intent detected for: '{text[:60]}'")
        # Ramble mode: occasionally grant explicit permission to filibuster
        # (skipped when long-intent already fired — redundant then).
        _ramble_hint = "" if _long else mario_prompt.maybe_ramble_hint(
            live_config.get("ramble_chance", 0.12))
        if _ramble_hint:
            ctx.append({"role": "system", "content": _ramble_hint})
            logger.info("[LENGTH] ramble hint fired — filibuster permission granted")
        # Long-form token budget applies to both explicit long intent and rambles.
        _long_np = int(live_config.get("long_num_predict", 1024)) if (_long or _ramble_hint) else None
```

(Note the `_long_np` line moves BELOW the ramble roll — it now depends on `_ramble_hint`. The two later uses of `_long_np` at main.py:5462 and :5497 are unchanged.)

- [ ] **Step 4: Run tests**

Run: `venv\Scripts\python -m pytest tests\test_ramble_hint.py tests\test_adaptive_length.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git branch --show-current   # must print: feat/admin-live-control
git add server/mario_prompt.py server/main.py tests/test_ramble_hint.py
git commit -m "feat(ramble): probabilistic filibuster permission + prompt no longer bans rambling

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>
Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: Server streaming — display-sentence chunks with `chunk_text`

**Files:**
- Modify: `server/tts.py` (add `split_display_sentences` + `build_stream_chunks` next to `split_into_sentences`, ~line 1684)
- Modify: `server/main.py:5711-5766` (streaming block), `server/main.py:6891-6941` (`send_response`)
- Test: `tests/test_stream_chunks.py` (new)

**Interfaces:**
- Produces: `tts.split_display_sentences(text: str) -> list[str]` — same split/merge rules as `split_into_sentences` but NO preclean (sentences stay verbatim substrings of the display text, so the client can `find` them).
- Produces: `tts.build_stream_chunks(display_text: str) -> list[dict]` — each `{"display": str, "tts": str}`; sentences whose TTS input is empty (emoji-only etc.) are merged into the next chunk's `display` so no bubble text is orphaned.
- Produces: wire format — chunk 0 `mario_response` gains `chunk_text` (sentence 0's display text); each `audio_chunk` JSON gains `chunk_text` (that sentence's display text). Task 5/6 consume `chunk_text`.
- Consumes: `pose_analyzer.analyze_text(sentence)["tts_text"]` (existing) for per-sentence TTS input — zero transform drift with the non-streamed path.

- [ ] **Step 1: Write the failing test**

Create `tests/test_stream_chunks.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))
import tts


def test_display_sentences_are_verbatim_substrings():
    text = "First sentence here! Second one follows. And a third, with a comma?"
    sents = tts.split_display_sentences(text)
    assert len(sents) == 3
    cursor = 0
    for s in sents:
        idx = text.find(s, cursor)
        assert idx >= 0, f"sentence not found verbatim: {s!r}"
        cursor = idx + len(s)


def test_display_split_does_not_preclean():
    # split_into_sentences precleans "..." into ", " — the display splitter must NOT.
    text = "Wait for it... here it comes! Another sentence right here."
    joined = " ".join(tts.split_display_sentences(text))
    assert "..." in joined


def test_short_fragments_merge():
    text = "Yes! No! Okay fine, party people. And here is a second proper sentence for the test."
    sents = tts.split_display_sentences(text)
    assert len(sents) == 2
    assert sents[0].startswith("Yes! No!")  # shorts merged forward, not standalone
    assert all(len(s) >= 15 for s in sents)


def test_build_stream_chunks_pairs_display_and_tts():
    text = "The party is amazing tonight everyone! Let me tell you a longer story about it."
    chunks = tts.build_stream_chunks(text)
    assert len(chunks) == 2
    for c in chunks:
        assert c["display"].strip() and c["tts"].strip()


def test_emoji_only_sentence_merges_into_next_display():
    # The emoji run is ≥15 chars so it survives the short-chunk merge as its own
    # sentence, then cleans to empty TTS — exercising the carry-merge path.
    text = "Here is the first real sentence of all! " + "🎉" * 20 + "! And here is the second real one."
    chunks = tts.build_stream_chunks(text)
    # No chunk may have empty tts; all display text must survive, in order.
    assert all(c["tts"].strip() for c in chunks)
    combined = " ".join(c["display"] for c in chunks)
    assert "first real sentence" in combined and "second real one" in combined


def test_single_sentence_yields_single_chunk():
    chunks = tts.build_stream_chunks("Just one single sentence for the bubble tonight.")
    assert len(chunks) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv\Scripts\python -m pytest tests\test_stream_chunks.py -v`
Expected: FAIL with `AttributeError: module 'tts' has no attribute 'split_display_sentences'`.

- [ ] **Step 3: Implement the helpers in `server/tts.py`**

Add directly below `split_into_sentences` (after line 1683):

```python
def split_display_sentences(text: str) -> list[str]:
    """Split DISPLAY text into sentence chunks — same boundaries and short-chunk
    merging as split_into_sentences, but with NO preclean, so every chunk stays
    a verbatim substring of the display text. The client locates each chunk in
    the bubble text to gate the typewriter to real audio playback.
    """
    import re
    if not text or not text.strip():
        return []
    chunks = re.split(r'(?<=[.!?])\s+', text.strip())
    merged = []
    buffer = ""
    for chunk in chunks:
        buffer += (" " if buffer else "") + chunk
        if len(buffer) >= 15:
            merged.append(buffer)
            buffer = ""
    if buffer:
        if merged:
            merged[-1] += " " + buffer
        else:
            merged.append(buffer)
    return merged


def build_stream_chunks(display_text: str) -> list[dict]:
    """Pair each display sentence with its TTS input for sentence streaming.

    Returns [{"display": <verbatim display sentence(s)>, "tts": <cleaned tts text>}].
    Uses pose_analyzer.analyze_text per sentence — the exact transform the
    non-streamed path applies to the whole reply — so spoken text never drifts
    from the bubble. Sentences that clean to nothing (emoji-only) have their
    display text merged into the NEXT chunk so the bubble still reveals them.
    """
    from pose_analyzer import analyze_text as _analyze
    chunks = []
    carry = ""
    for sent in split_display_sentences(display_text):
        disp = (carry + " " + sent).strip() if carry else sent
        tts_in = _analyze(sent)["tts_text"].strip()
        if not tts_in:
            carry = disp
            continue
        chunks.append({"display": disp, "tts": tts_in})
        carry = ""
    if carry:
        if chunks:
            chunks[-1]["display"] = (chunks[-1]["display"] + " " + carry).strip()
        else:
            # Nothing speakable at all — one chunk with empty tts; caller falls
            # back to the non-streamed path.
            chunks.append({"display": carry, "tts": ""})
    return chunks
```

- [ ] **Step 4: Run the unit tests**

Run: `venv\Scripts\python -m pytest tests\test_stream_chunks.py -v`
Expected: all PASS.

- [ ] **Step 5: Rewire the streaming block in `server/main.py`**

Replace lines 5711-5732 (from the `# Sentence streaming:` comment through the chunk-0 `send_response(...)` call):

```python
    # Sentence streaming: split the DISPLAY text into sentences, send the first
    # chunk (text + its sentence) immediately, synthesize the rest in background
    # while the client plays chunk 0. Each chunk carries its display sentence
    # (chunk_text) so the client can gate the bubble typewriter to real audio.
    if TTS_STREAMING_ENABLED:
        stream_chunks = tts.build_stream_chunks(analyzed["display_text"])
        if len(stream_chunks) >= 2 and len(stream_chunks[0]["tts"]) >= 12:
            try:
                total_chunks = len(stream_chunks)
                if DEBUG_STREAM:
                    logger.info(f"[DEBUG_STREAM] Streaming {total_chunks} sentences for: \"{tts_text[:80]}...\"")

                # Synthesize first sentence immediately
                first_audio = await loop.run_in_executor(
                    _tts_executor, lambda: tts.synthesize_user(
                        stream_chunks[0]["tts"], rate=voice_params.get("rate"), pitch=voice_params.get("pitch")))
                if first_audio and len(first_audio) > 44:
                    # Send full text + metadata with first audio chunk
                    await send_response(ws, analyzed["display_text"], first_audio,
                        sound=game_sound, emotion=response_emotion or emotion_system.current,
                        pose_hint=analyzed["pose_hint"], response_time=time.time() - start_time,
                        particle_effect=particle, full_text=analyzed.get("full_text"),
                        censor=censored,
                        chunk_index=0, total_chunks=total_chunks, is_last=(total_chunks == 1),
                        chunk_text=stream_chunks[0]["display"])
                    streamed = True
```

Then replace the remaining-sentences part (old lines 5735-5766) with:

```python
                    # Pre-synthesize remaining sentences in parallel for speed
                    remaining = [(i, c) for i, c in enumerate(stream_chunks[1:], start=1)]
                    if remaining:
                        synth_tasks = [
                            loop.run_in_executor(
                                _tts_executor, lambda s=c["tts"]: tts.synthesize_user(
                                    s, rate=voice_params.get("rate"), pitch=voice_params.get("pitch")))
                            for _, c in remaining
                        ]
                        synth_results = await asyncio.gather(*synth_tasks, return_exceptions=True)
                        for (i, chunk), chunk_audio in zip(remaining, synth_results):
                            if isinstance(chunk_audio, Exception):
                                logger.error(f"[DEBUG_STREAM] Sentence {i+1}/{total_chunks} failed: {chunk_audio}")
                                continue
                            if chunk_audio and len(chunk_audio) > 44:
                                is_last = (i == total_chunks - 1)
                                try:
                                    await ws.send_json({
                                        "type": "audio_chunk",
                                        "chunk_index": i,
                                        "total_chunks": total_chunks,
                                        "is_last": is_last,
                                        "chunk_text": chunk["display"],
                                    })
                                    await ws.send_bytes(chunk_audio)
                                except Exception as send_err:
                                    logger.warning(f"[DEBUG_STREAM] WebSocket send failed on chunk {i+1}/{total_chunks}: {send_err}")
                                    break
                                if DEBUG_STREAM:
                                    logger.info(f"[DEBUG_STREAM] Sent chunk {i+1}/{total_chunks} ({len(chunk_audio)} bytes, is_last={is_last})")
                            else:
                                if DEBUG_STREAM:
                                    logger.warning(f"[DEBUG_STREAM] Sentence {i+1}/{total_chunks} produced empty audio, skipping")
```

(Everything around it — the `else` fall-through at 5767, the `except` at 5770, and the `if not streamed:` full-synthesis fallback — stays unchanged. The fallback still synthesizes `tts_text`, which is the whole-reply transform of the same display text.)

- [ ] **Step 6: Add `chunk_text` to `send_response`**

In `server/main.py:6891`, add the parameter after `censor: bool = False,`:

```python
async def send_response(ws: WebSocket, text: str, audio: bytes = None,
                        sound: str = None, emotion: str = None, energy: float = None,
                        pose_hint: str = None, response_time: float = None,
                        particle_effect: str = None,
                        chunk_index: int = None, total_chunks: int = None,
                        is_last: bool = None, is_idle: bool = False,
                        full_text: str = None, censor: bool = False,
                        speaker: str = None, chunk_text: str = None):
```

And in the message-build section (next to the existing `if speaker:` block at 6935):

```python
    if chunk_text is not None:
        msg["chunk_text"] = chunk_text
```

- [ ] **Step 7: Import check + server boots**

Run: `venv\Scripts\python -c "import sys; sys.path.insert(0, 'server'); import tts; print(len(tts.build_stream_chunks('One full sentence here tonight! And a second one follows right after.')))"`
Expected: `2`

Run: `venv\Scripts\python -m pytest tests\test_stream_chunks.py tests\test_tts_abbrev.py -v`
Expected: all PASS.

- [ ] **Step 8: Commit**

```bash
git branch --show-current   # must print: feat/admin-live-control
git add server/tts.py server/main.py tests/test_stream_chunks.py
git commit -m "feat(stream): chunks carry their display sentence (chunk_text) for audio-gated bubbles

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>
Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: Client display — span-limited typewriter (`prepare_span_stream` / `resolve_span_target` / `set_typewriter_span`)

**Files:**
- Modify: `client/mario_display.py:245-248` (init vars), `:885-903` (`set_mario_text` reset), `:911-930` (methods area — add new methods below `sync_typewriter_to_audio`), `:1167-1178` (`_update_typewriter`)
- Test: `tests/test_span_typewriter.py` (new)

**Interfaces:**
- Produces (on `MarioDisplay`):
  - `prepare_span_stream() -> None` — holds the typewriter at 0 until the first span arrives (called when a streamed reply's text lands, before its audio starts).
  - `resolve_span_target(sentence: str) -> int` — locates the (emoji-stripped) sentence in `_typewriter_text` starting from the previous span's end; returns the char index just past it. On a find miss, falls back to advancing by the needle length. Advances the internal search cursor either way.
  - `set_typewriter_span(target_char: int, duration_s: float) -> None` — paces the typewriter from its current position to `target_char` over the clip duration (finishing ~0.3s early), then holds. Monotonic: a lower target than the current one never rewinds text.
- State: `_typewriter_span_target: int|None` (None = no span limit → legacy behavior), `_span_search_pos: int`, `_span_stale_frames: int`.
- Stale release: if the typewriter has been held at a span target for >240 frames (~8s at 30fps) while `_speaking` with text remaining, the span limit is released and the adaptive fallback speed resumes (stream died without `is_last` — bubble must not hang forever).
- Consumes: existing `_typewriter_text`, `_typewriter_pos`, `_typewriter_speed`, `_typewriter_audio_synced`, `_EMOJI_RE`, `_speaking` — pagination (`_draw_speech_bubble`) is NOT touched; it keeps reading `_typewriter_pos`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_span_typewriter.py` — the display methods are exercised unbound against a plain stub object, so no pygame window or font loading is needed (module import of `mario_display` is safe headless):

```python
import sys, os, types
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "client"))
from mario_display import MarioDisplay


def make_stub(text):
    d = types.SimpleNamespace()
    d._typewriter_text = text
    d._typewriter_pos = 0
    d._typewriter_speed = 2
    d._typewriter_audio_synced = False
    d._typewriter_span_target = None
    d._span_search_pos = 0
    d._span_stale_frames = 0
    d._speaking = True
    d.current_text = ""
    d._get_typewriter_speed = lambda n: 2  # fallback speed used after stale release
    return d


TEXT = "First sentence right here! Second sentence follows now. Third one ends it all."


def test_prepare_span_stream_holds_at_zero():
    d = make_stub(TEXT)
    MarioDisplay.prepare_span_stream(d)
    for _ in range(30):
        MarioDisplay._update_typewriter(d)
    assert int(d._typewriter_pos) == 0


def test_resolve_span_target_sequential():
    d = make_stub(TEXT)
    MarioDisplay.prepare_span_stream(d)
    t1 = MarioDisplay.resolve_span_target(d, "First sentence right here!")
    t2 = MarioDisplay.resolve_span_target(d, "Second sentence follows now.")
    assert t1 == len("First sentence right here!")
    assert t2 > t1
    assert TEXT[:t2].endswith("Second sentence follows now.")


def test_resolve_span_target_duplicate_sentences_advance():
    text = "Go go go, party people! Go go go, party people! The end of it all."
    d = make_stub(text)
    MarioDisplay.prepare_span_stream(d)
    t1 = MarioDisplay.resolve_span_target(d, "Go go go, party people!")
    t2 = MarioDisplay.resolve_span_target(d, "Go go go, party people!")
    assert t2 > t1


def test_resolve_span_target_miss_falls_back():
    d = make_stub(TEXT)
    MarioDisplay.prepare_span_stream(d)
    t = MarioDisplay.resolve_span_target(d, "totally different words that are absent")
    assert 0 < t <= len(TEXT)


def test_span_paces_and_holds():
    d = make_stub(TEXT)
    MarioDisplay.prepare_span_stream(d)
    target = MarioDisplay.resolve_span_target(d, "First sentence right here!")
    MarioDisplay.set_typewriter_span(d, target, 2.0)
    for _ in range(100):  # ~3.3s of frames — past the 2s clip, below the 8s stale release
        MarioDisplay._update_typewriter(d)
    assert int(d._typewriter_pos) == target  # held exactly at the span end


def test_span_is_monotonic():
    d = make_stub(TEXT)
    MarioDisplay.prepare_span_stream(d)
    MarioDisplay.set_typewriter_span(d, 40, 0.5)
    for _ in range(120):
        MarioDisplay._update_typewriter(d)
    pos_before = d._typewriter_pos
    MarioDisplay.set_typewriter_span(d, 10, 1.0)  # lower target must not rewind
    MarioDisplay._update_typewriter(d)
    assert d._typewriter_pos >= pos_before


def test_stale_span_releases_after_8s():
    d = make_stub(TEXT)
    MarioDisplay.prepare_span_stream(d)
    target = MarioDisplay.resolve_span_target(d, "First sentence right here!")
    MarioDisplay.set_typewriter_span(d, target, 0.5)
    for _ in range(1000):  # reach target, then sit stale well past 240 frames
        MarioDisplay._update_typewriter(d)
    assert d._typewriter_span_target is None          # limit released
    assert d._typewriter_pos > target                 # fallback speed resumed
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv\Scripts\python -m pytest tests\test_span_typewriter.py -v`
Expected: FAIL — `AttributeError: type object 'MarioDisplay' has no attribute 'prepare_span_stream'`.

- [ ] **Step 3: Implement in `client/mario_display.py`**

3a. Init vars — after line 248 (`self._typewriter_audio_synced = False  # ...`):

```python
        self._typewriter_span_target = None  # char limit for audio-gated reveal (None = no limit)
        self._span_search_pos = 0            # where the next chunk sentence search starts
        self._span_stale_frames = 0          # frames held at a span target with no new span
```

3b. `set_mario_text` reset — after line 903 (`self._page_transition_frame = 0`):

```python
        # Reset audio-gated span state (new utterance)
        self._typewriter_span_target = None
        self._span_search_pos = 0
        self._span_stale_frames = 0
```

3c. New methods, inserted directly after `sync_typewriter_to_audio` (after line 930):

```python
    def prepare_span_stream(self):
        """Hold the typewriter until the first audio span arrives.

        Called when a streamed reply's text lands (its chunk carries
        chunk_text). Without this the typewriter would run ahead at the
        default speed before chunk-0 audio starts playing."""
        self._typewriter_span_target = 0
        self._span_search_pos = 0
        self._span_stale_frames = 0
        self._typewriter_speed = 0.0
        self._typewriter_audio_synced = True

    def resolve_span_target(self, sentence: str) -> int:
        """Locate a chunk's display sentence in the bubble text; return the char
        index just past it. Searches forward from the previous span so repeated
        sentences resolve in order. Emoji are stripped exactly like
        set_mario_text strips them, so the needle matches the bubble text. On a
        miss (whitespace drift etc.) fall back to advancing by needle length."""
        text = self._typewriter_text or ""
        needle = _EMOJI_RE.sub("", sentence or "").strip()
        if not needle or not text:
            return int(self._typewriter_span_target or 0)
        start = max(0, int(self._span_search_pos))
        idx = text.find(needle, start)
        if idx < 0:
            idx = text.find(needle)
        end = (idx + len(needle)) if idx >= 0 else min(start + len(needle) + 1, len(text))
        self._span_search_pos = end
        return end

    def set_typewriter_span(self, target_char: int, duration_s: float):
        """Pace the typewriter to target_char over duration_s, then hold.

        Called from the audio queue's on_start callback the moment a chunk's
        clip begins playing — the bubble reveals exactly what is being said.
        Monotonic: a lower target never rewinds already-shown text."""
        text = self._typewriter_text or ""
        if not text:
            return
        target = max(0, min(int(target_char), len(text)))
        if self._typewriter_span_target is None or target > self._typewriter_span_target:
            self._typewriter_span_target = target
        self._span_stale_frames = 0
        remaining = self._typewriter_span_target - self._typewriter_pos
        if remaining <= 0:
            return
        # Finish revealing ~0.3s before the clip ends (same feel as full sync)
        frames = max(1, int(max(0.5, duration_s - 0.3) * 30))
        self._typewriter_speed = max(0.15, min(8.0, remaining / frames))
        self._typewriter_audio_synced = True
```

3d. Replace `_update_typewriter` (lines 1167-1178):

```python
    def _update_typewriter(self):
        """Advance typewriter text effect (span-limited when audio-gated)."""
        if not self._typewriter_text:
            return
        limit = len(self._typewriter_text)
        span = getattr(self, "_typewriter_span_target", None)
        if span is not None:
            limit = min(limit, int(span))
        if self._typewriter_pos < limit:
            if self._typewriter_audio_synced:
                speed = self._typewriter_speed
            else:
                speed = self._get_typewriter_speed(len(self._typewriter_text))
            self._typewriter_pos = min(self._typewriter_pos + speed, limit)
            self.current_text = self._typewriter_text[:int(self._typewriter_pos)]
        elif span is not None and limit < len(self._typewriter_text):
            # Held at a span with text remaining. If no new span arrives for
            # ~8s while still speaking, the stream died (no is_last) — release
            # the limit so the bubble never hangs forever.
            if getattr(self, "_speaking", False):
                self._span_stale_frames += 1
                if self._span_stale_frames > 240:
                    self._typewriter_span_target = None
                    self._typewriter_audio_synced = False
```

- [ ] **Step 4: Run tests**

Run: `venv\Scripts\python -m pytest tests\test_span_typewriter.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git branch --show-current   # must print: feat/admin-live-control
git add client/mario_display.py tests/test_span_typewriter.py
git commit -m "feat(client): span-limited typewriter — bubble reveal gated to audio spans

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>
Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 6: Client wiring — chunk handlers drive spans; stream-death failsafe

**Files:**
- Modify: `client/audio_playback.py` (add `wav_duration_s` module function near the top, after the imports/constants)
- Modify: `client/main.py:191` (init attrs), `:397-455` (`_on_mario_text`), `:457-474` (`_wait_for_audio_complete`), `:476-502` (`_on_mario_audio`), `:540-564` (`_on_audio_chunk`)
- Test: extend `tests/test_span_typewriter.py` (duration helper test)

**Interfaces:**
- Consumes: `chunk_text` on chunk-0 `mario_response` metadata and on `audio_chunk` meta (Task 4); `prepare_span_stream` / `resolve_span_target` / `set_typewriter_span` (Task 5); existing `audio_playback.play(wav_bytes, on_start=..., text=...)`.
- Produces: `audio_playback.wav_duration_s(wav_bytes: bytes) -> float` — real clip duration from the WAV header (fallback: `len/48000`).
- Produces: client state `self._pending_chunk0_text: str|None`, `self._stream_is_last_seen: bool`.
- Failsafe: the audio-wait thread now starts on EVERY chunk; after playback goes idle it waits 0.5s (when `is_last` was seen) or 4s (mid-stream gap) for more audio before clearing the speaking state — a stream that dies without `is_last` no longer wedges the bubble.

- [ ] **Step 1: Write the failing test for the duration helper**

Append to `tests/test_span_typewriter.py`:

```python
def test_wav_duration_from_header():
    import io, wave, struct
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "client"))
    import audio_playback
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(24000)
        wf.writeframes(struct.pack("<h", 0) * 24000)  # exactly 1.0s of silence
    dur = audio_playback.wav_duration_s(buf.getvalue())
    assert abs(dur - 1.0) < 0.02


def test_wav_duration_garbage_falls_back():
    import audio_playback
    dur = audio_playback.wav_duration_s(b"RIFFgarbage-not-a-real-wav" * 100)
    assert dur > 0
```

- [ ] **Step 2: Run to verify failure**

Run: `venv\Scripts\python -m pytest tests\test_span_typewriter.py -v -k wav_duration`
Expected: FAIL — `AttributeError: module 'audio_playback' has no attribute 'wav_duration_s'`.

- [ ] **Step 3: Implement `wav_duration_s` in `client/audio_playback.py`**

Add as a module-level function after the imports/logger setup (before the class):

```python
def wav_duration_s(wav_bytes: bytes) -> float:
    """Real duration of a WAV byte buffer from its header.

    Used to pace the bubble typewriter to each streamed clip. Falls back to
    the 24kHz/16-bit estimate used for echo cancellation when the header is
    unreadable."""
    try:
        with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
            rate = wf.getframerate() or 24000
            return max(0.3, wf.getnframes() / float(rate))
    except Exception:
        return max(0.5, len(wav_bytes or b"") / 48000)
```

(`wave` and `io` are already imported at the top of audio_playback.py — verify, add if missing.)

- [ ] **Step 4: Run the helper tests**

Run: `venv\Scripts\python -m pytest tests\test_span_typewriter.py -v -k wav_duration`
Expected: both PASS.

- [ ] **Step 5: Wire the client handlers in `client/main.py`**

5a. Init attrs — next to line 191 (`self._audio_wait_cancel = threading.Event()`):

```python
        self._pending_chunk0_text = None   # chunk-0 display sentence awaiting its audio
        self._stream_is_last_seen = True   # False while a chunked stream is still arriving
```

5b. In `_on_mario_text`, right after `self.display._speaking = True` (line 412), add:

```python
        # Audio-gated reveal: a streamed reply's chunk 0 carries its first
        # sentence (chunk_text). Hold the typewriter until that clip starts.
        _chunk_text = (metadata or {}).get("chunk_text")
        if _chunk_text is not None and (metadata or {}).get("chunk_index") == 0:
            self.display.prepare_span_stream()
            self._pending_chunk0_text = _chunk_text
            self._stream_is_last_seen = bool((metadata or {}).get("is_last"))
        else:
            self._pending_chunk0_text = None
            self._stream_is_last_seen = True
```

5c. In `_on_mario_audio`, replace the play/sync section (lines 483-498, from the `pending = getattr(...)` line through `self.display.sync_typewriter_to_audio(duration)`) with:

```python
        # If a countdown number is pending, reveal it exactly when this clip
        # starts playing — so the visual countdown is driven by the audio.
        pending = getattr(self, "_pending_countdown_number", None)
        _spoken = getattr(self.display, "_typewriter_text", "")
        _chunk0_text = getattr(self, "_pending_chunk0_text", None)
        duration = wav_duration_s(wav_bytes)
        if _chunk0_text is not None:
            # Streamed reply: pace the bubble to this clip only (audio-gated).
            self._pending_chunk0_text = None
            _target = self.display.resolve_span_target(_chunk0_text)
            self.audio_playback.play(
                wav_bytes,
                on_start=(lambda t=_target, d=duration: self.display.set_typewriter_span(t, d)),
                text=_chunk0_text)
        elif pending is not None:
            self._pending_countdown_number = None
            self.audio_playback.play(wav_bytes, on_start=(lambda n=pending: self.display.set_countdown(n)), text=_spoken)
        else:
            self.audio_playback.play(wav_bytes, text=_spoken)
        self.mirror.send_audio(wav_bytes)   # tee to remote viewers (no-op if inactive)
        # Track when playback finishes for echo cancellation
        self._last_play_end_time = time.time() + duration
        # Sync typewriter speed to audio duration (whole-text estimate) only
        # when this reply is NOT audio-gated per chunk.
        if _chunk0_text is None:
            self.display.sync_typewriter_to_audio(duration)
```

Add the import at the top of `client/main.py` next to the existing audio_playback import (the file already imports the `AudioPlayback` class from this module — extend or add the from-import):

```python
from audio_playback import wav_duration_s
```

(The old `duration = max(0.5, len(wav_bytes) / 48000)` line is replaced by the header-accurate helper; echo-cancellation behavior only gets more accurate.)

5d. In `_on_audio_chunk`, replace the body after the `is_last = chunk_meta.get(...)` / debug-log lines (lines 550-564) with:

```python
        _chunk_text = chunk_meta.get("chunk_text")
        duration = wav_duration_s(wav_bytes)
        if _chunk_text:
            # Audio-gated reveal: when this clip starts, pace the bubble to the
            # end of exactly this sentence.
            _target = self.display.resolve_span_target(_chunk_text)
            self.audio_playback.play(
                wav_bytes,
                on_start=(lambda t=_target, d=duration: self.display.set_typewriter_span(t, d)),
                text=_chunk_text)
        else:
            # Legacy server without chunk_text — old estimate behavior.
            self.audio_playback.play(wav_bytes, text=getattr(self.display, "_typewriter_text", ""))
            if chunk_idx == 0 and isinstance(total, int) and total > 0:
                self.display.sync_typewriter_to_audio(duration * total)
        self.mirror.send_audio(wav_bytes)   # tee streaming chunk to remote viewers
        # Keep speaking state active; extend echo cancellation window
        self._last_play_end_time = time.time() + duration
        if is_last:
            self._stream_is_last_seen = True
        # (Re)start the audio-wait watchdog on EVERY chunk — it clears the
        # speaking state after real playback ends, and failsafes a stream that
        # died without is_last (see _wait_for_audio_complete).
        self._audio_wait_cancel.set()
        self._audio_wait_thread = threading.Thread(target=self._wait_for_audio_complete, daemon=True)
        self._audio_wait_thread.start()
```

5e. Replace `_wait_for_audio_complete` (lines 457-474) with:

```python
    def _wait_for_audio_complete(self):
        """Wait for audio playback to finish, then clear the speech bubble.

        Streamed replies keep this thread alive across chunk gaps: after
        playback goes idle it waits 0.5s (last chunk seen) or up to 4s
        (mid-stream gap / stream died without is_last) for more audio before
        clearing — the bubble never wedges on a broken stream."""
        self._audio_wait_cancel.clear()

        # Wait for audio to start playing (up to 2s)
        for _ in range(20):
            if self.audio_playback.is_playing or self._audio_wait_cancel.is_set():
                break
            time.sleep(0.1)

        while not self._audio_wait_cancel.is_set():
            if self.audio_playback.is_playing:
                time.sleep(0.1)
                continue
            # Playback idle — grace window depends on whether the stream ended.
            grace = 0.5 if getattr(self, "_stream_is_last_seen", True) else 4.0
            idle_start = time.time()
            resumed = False
            while (time.time() - idle_start) < grace and not self._audio_wait_cancel.is_set():
                if self.audio_playback.is_playing:
                    resumed = True
                    break
                time.sleep(0.1)
            if resumed:
                continue
            if not self._audio_wait_cancel.is_set():
                self._clear_speaking_state()
            return
```

- [ ] **Step 6: Full client-side test pass + smoke import**

Run: `venv\Scripts\python -m pytest tests\test_span_typewriter.py tests\test_stream_chunks.py tests\test_response_ceiling.py tests\test_ramble_hint.py tests\test_adaptive_length.py -v`
Expected: all PASS.

Run: `venv\Scripts\python -c "import ast; ast.parse(open('client/main.py', encoding='utf-8').read()); ast.parse(open('client/mario_display.py', encoding='utf-8').read()); ast.parse(open('client/audio_playback.py', encoding='utf-8').read()); print('client syntax OK')"`
Expected: `client syntax OK`

- [ ] **Step 7: Commit**

```bash
git branch --show-current   # must print: feat/admin-live-control
git add client/main.py client/audio_playback.py tests/test_span_typewriter.py
git commit -m "feat(client): audio chunks drive bubble spans + stream-death watchdog

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>
Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 7: Live end-to-end verification (MANDATORY audio checklist) + docs

**Files:**
- Modify: `.claude/CLAUDE.md` (config docs: add `response_char_ceiling`, `ramble_chance`, `long_num_predict` to the Key Config Fields list — 3 lines)
- No code changes expected; fixes discovered here get their own commits.

**Interfaces:**
- Consumes: everything above, running live (server + client both restarted — a character/config change requires BOTH per project memory).

- [ ] **Step 1: Restart server AND client**

Kill any running instances, then start fresh (foreground per project convention — this dev box reaps detached background processes):
- `start_server.bat` in one terminal
- `venv\Scripts\python client\main.py` in another (or the usual client launcher)

Confirm startup logs show no import errors from `tts.py`, `main.py`, `mario_display.py`.

- [ ] **Step 2: Long-response live test (mario-debug MCP)**

Send via MCP `mario_send_text` (or `POST /admin/simulate_text`):
`"tell me the whole story of your greatest adventure ever, take your time and give me every detail"`
(long-intent phrasing → reliably triggers the long path).

Verify ALL of (per `.claude/rules/testing.md`):
- Server log: `[DEBUG_STREAM] Streaming N sentences` with N ≥ 4, chunks sent with `chunk_text`.
- Client log: `mario says:` line shows the full long text (NOT cut at 500 chars).
- Client log: one `_play_wav: playing` AND one `_play_wav: done` per chunk, in order.
- Screenshot (`mario_screenshot`) mid-reply: bubble shows only the portion spoken so far; a later screenshot shows a later page. No page appears before its audio.
- Spoken text matches bubble content; zero wrong-character references.
- Bubble clears within ~1s after the final chunk's `_play_wav: done`.

- [ ] **Step 3: Gating + interrupt live test**

While a second long reply is mid-stream (send the prompt again), send a new short message (`"wait, what?"`). Verify: audio stops (clear_audio), bubble resets, the new short reply plays normally, and no stale long-reply text reappears.

- [ ] **Step 4: Short-reply regression + idle check**

Send `"hey!"` — verify a normal short reply with instant audio and normal bubble behavior (estimate path if unstreamed). Let the client idle ~2 minutes — verify idle mumbles still display and speak normally (they don't use chunk_text; fallback path).

- [ ] **Step 5: Ceiling + ramble sanity (logs only)**

- Grep server log for `[LENGTH] ramble hint fired` across ~15 test messages — at ~12% it may or may not appear; absence is fine, presence must coincide with a longer-than-usual reply.
- Confirm NO `Response hit char ceiling` warnings during normal replies.

- [ ] **Step 6: Update CLAUDE.md config docs**

In `.claude/CLAUDE.md` under "### Key Config Fields" add:

```markdown
- `response_char_ceiling` (config_live, default 4000) — runaway-protection cap on spoken/displayed replies (was a hard 500 cut)
- `ramble_chance` (config_live, default 0.12) — probability a response gets filibuster permission
- `long_num_predict` (config_live, default 1024) — token budget for long-intent/ramble responses
```

- [ ] **Step 7: Final commit**

```bash
git branch --show-current   # must print: feat/admin-live-control
git add .claude/CLAUDE.md
git commit -m "docs: document response ceiling + ramble config keys

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>
Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```
