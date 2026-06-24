# TADC Group Engine — Design Spec

**Date:** 2026-06-22
**Status:** Approved (design), pending implementation plan
**Branch:** `feat/tadc-group`
**Goal:** Let a guest hold a group conversation with multiple "The Amazing Digital Circus" characters at once — a director-orchestrated ensemble where characters are aware of each other, take turns, and can banter, running on the existing single-sprite display to start.

## Locked decisions (from brainstorming)

1. **Model strategy = both, made configurable.** Each character may declare its own `model:`; a group definition sets a `shared_model`. No override → that character uses the shared model (one-brain mode). Every character overridden → separate-brains mode. Some overridden → hybrid. One config shape supports all three; the engine is model-agnostic and just passes `model=` per call.
2. **Interaction = director-orchestrated.** A "ringmaster" picks who speaks each turn — usually 1 character, sometimes 2 for a quick back-and-forth; can cue cross-talk.
3. **Director implementation = hybrid.** Explicit address ("Jax, …") routes instantly with no LLM; otherwise a fast-model director call selects the responder(s).
4. **v1 cast = engine-first with existing Pomni + Jax.** The "ringmaster" is the **director logic itself**, not a required character — its turn-transition narration may *optionally* be surfaced as a Caine voice later, but v1 requires only Pomni + Jax. Generating the rest of the cast is a separate content task.

## Scope

**In scope (this spec):** the group orchestration engine — director, multi-character session state, configurable per-character models, turn-taking, sequential multi-voice synthesis, driving the *existing* single-sprite display by spotlighting the current speaker. Additive group mode that does not touch the single-character path.

**Deferred (own specs):** multi-character-on-screen rendering (a stage with several sprites); generating the rest of the TADC cast (Ragatha, Zooble, Kinger, Gangle, Bubble) — sprites, voices, prompts; richer autonomous idle banter.

## Architecture

```
guest text ──> GroupOrchestrator.handle(text)
                 │
                 ├─ Director.plan_turn(text, transcript, roster) ──> TurnPlan{speakers, addressed, banter}
                 │
                 └─ for each speaker in plan (sequential):
                       build speaker system prompt + shared transcript
                       LLM.generate(ctx, model = speaker.model or shared_model)
                       safety_filter.filter_response(...)
                       TTS.synthesize in speaker's voice
                       swap active sprite/name -> speaker  (existing display)
                       play audio (single room speaker = sequential)
                       append "<speaker>: <line>" to shared transcript
```

| Unit | Responsibility | New/Modify |
|------|----------------|-----------|
| `server/group_orchestrator.py` | Owns the group turn: roster, shared transcript, calls director, runs per-speaker generate→filter→TTS→display→play | New |
| `server/group_director.py` | `plan_turn(text, transcript, roster) -> TurnPlan`; hybrid (address fast-path + fast-model pick); pure + mockable | New |
| `groups/tadc.yaml` | Group definition: `shared_model`, `director_model`, roster `[{id, model?}]`, turn policy | New |
| `shared/character_loader.py` | Add optional `model` field read from `character.yaml` | Modify |
| `server/main.py` | Group-mode branch in dispatch; load group at startup when configured; sprite/voice swap per speaker reuses existing `set_character`/`set_voice_config` | Modify |
| `config.json` | `mode: "single"｜"group"` + `group: "tadc"` selector | Modify |

### Director (hybrid)

`plan_turn(guest_text, transcript, roster)`:
1. **Address fast-path** — if the text names a roster member ("Jax", "hey Caine"), return `{speakers:[that], addressed:that}` with no LLM call.
2. **Fast-model pick** — otherwise call the `director_model` with a compact prompt (cast list + last few transcript lines + guest text) that returns a small JSON `{speakers:[...], banter:bool}`. Validated against the roster; falls back to a relevance/round-robin rule if the model returns garbage.
3. Cap speakers at 2 per turn (latency + single audio output).

### Model serving ("both" in one shape)

- `character.yaml` may set `model: <ollama-model>`. `groups/tadc.yaml` sets `shared_model` (default brain) + `director_model` (fast).
- Engine resolves each speaker's model as `character.model or group.shared_model`.
- Concurrency handled by Ollama: set `OLLAMA_MAX_LOADED_MODELS` ≥ distinct-model count and `keep_alive` so loaded models stay warm. A startup **VRAM budget check** logs a loud warning if the sum of distinct model sizes + TTS headroom would exceed the GPU (party box: 24 GB).
- All-shared roster = 1 model loaded (cheap). Per-character models = N loaded (separate brains). Same code path.

### Mode toggle (additive)

`config.json` gains `mode` (`"single"` default, or `"group"`) and `group` (e.g. `"tadc"`). In `single` mode nothing changes — the existing single-character dispatch runs untouched. In `group` mode, dispatch routes to `GroupOrchestrator`. The single-character code is never removed.

### Display v1 (reuse current single sprite)

No rendering rework. Each spoken line swaps the active sprite + name to the speaker (the existing per-character `set_character` + sprite/voice swap used by `/admin/switch_character`), then plays. The screen "cuts" between speakers like a show camera. True multi-sprite stage is the deferred display spec.

### Voice

Sequential — one room speaker means one clip at a time. Each line synthesizes in the speaker's voice (existing `tts.set_voice_config` per character), queued in turn order through the existing playback queue.

## Data flow (shared awareness)

All characters read **one shared transcript** (a bounded deque of `"<name>: <line>"`), so each speaker's prompt includes what the others just said — that is what makes them feel like a group rather than parallel solo bots. Per-character persona/voice/sprite stay distinct; the conversation context is shared.

## Error handling

- Director model returns invalid/empty plan → rule-based fallback (addressed name, else least-recent speaker).
- A speaker's LLM or TTS fails → skip that speaker, log, continue the turn (never blocks the whole group).
- Model not loaded / Ollama busy → the generate call's existing timeout + fallback applies; the engine surfaces a short in-character "…" rather than hanging.
- Group definition missing/invalid at startup → fall back to `single` mode with a loud warning (fail safe, never crash the party).

## Testing (TDD)

- **Director (pure):** address fast-path picks the named character; fast-model plan is validated against roster; garbage plan → rule fallback; speaker cap = 2.
- **Roster/transcript (pure):** add/snapshot, bounded length, `"<name>: <line>"` formatting.
- **Model resolution (pure):** `character.model or shared_model`; all-shared vs per-character vs hybrid.
- **Speaker prompt assembly (pure):** includes the shared transcript + the speaker's own persona.
- **Live (debug MCP):** a 2-character (Pomni + Jax) session end-to-end on the existing display — `mario_send_text` → both characters take turns, `mario_audio_out` shows each line in the right voice, `mario_screenshot`/`mario_state` show the sprite spotlighting the speaker.

## Files

**New:** `server/group_orchestrator.py`, `server/group_director.py`, `groups/tadc.yaml`, `tests/test_group_director.py`, `tests/test_group_state.py`, `tests/test_group_model_resolution.py`.

**Modify:** `shared/character_loader.py` (read `model`), `server/main.py` (group-mode dispatch + startup load + per-speaker swap), `config.json` (`mode` + `group`).

## Out of scope (explicit)

- Multi-sprite simultaneous rendering (deferred display spec).
- Generating Ragatha/Zooble/Kinger/Gangle/Bubble assets (deferred content task).
- Concurrent (overlapping) audio for multiple speakers — single room output stays sequential.
- Changing the single-character experience in any way.
