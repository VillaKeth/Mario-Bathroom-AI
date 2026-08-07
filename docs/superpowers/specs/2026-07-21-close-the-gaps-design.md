# Close the Gaps — Design Spec

**Date:** 2026-07-21
**Status:** Approved (user directive: "finish it and close the gaps")
**Branch:** `feature/close-the-gaps`
**Prior art:** `2026-06-22-tadc-group-engine-design.md` (engine shipped to master, never booted live; multi-sprite display + remaining cast were explicitly deferred to this spec).

## Goal

Finish the partially-built capabilities so they demonstrably work: TADC group mode live (with the full cast, all on screen at once when desired), throw-up comfort verified with real audio, streaming completed to token level, voice barge-in, and lip-flap.

## Audit baseline (2026-07-21, all verified against master `f4bd34b`)

| Area | State |
|---|---|
| Sentence-chunked TTS streaming | Shipped (`tts_streaming`); LLM still generates full text first |
| Self-interruption | Shipped for typed input; mic deaf during playback (`client/main.py:378`) |
| Voice ID | Shipped (resemblyzer + recognition_fusion); installed in venv |
| Vomit comfort | Fully wired (PANNs eager-load, weights on disk); zero real-audio E2E evidence |
| TADC group engine | Shipped on master, 31 unit tests; **never booted** (no group log lines anywhere) |
| Pomni/Jax | Complete (39 sprites each, trained SoVITS models, pools, censor) |
| Ragatha/Kinger/Gangle/Zooble/Caine | Missing entirely |
| Multi-char on screen | Missing; client ignores `speaker` field — group lines all render on the one configured sprite set |
| Lip-flap | Missing; `speech/{listening,talking,talking_excited}.png` exist per character |

## Scope (phases in execution order)

### Phase 1 — Group mode actually works on screen

1. **Live boot + fallout fixes.** Set `mode: "group"` in local config, run server+client on dev box, drive with debug MCP. Fix whatever breaks. Engine design says fail-safe to single mode — verify.
2. **Speaker camera-cut (v1 promise).** Server already sends `speaker` per line. Client learns to hot-swap the active sprite set + display name to the speaking character for the duration of that line. Reuses the existing `_pending_character_switch` machinery but per-response, cheap, no reload from disk after first load (cache per-character sprite dicts).
3. **Stage mode — everyone on screen at once.** New additive render path in `client/mario_display.py`:
   - `stage_mode` on when: group mode active AND (`config_live.group_stage: true` OR client hotkey toggle). Default ON in group mode — "presented on same screen at once if desired" — hotkey flips back to camera-cut.
   - Layout: roster in horizontal slots across the sprite zone. Active speaker: full scale, full brightness, speech bubble with name tag. Non-speakers: 0.8 scale, dimmed ~55%, `speech/listening.png` pose (fallback: neutral).
   - Server sends a `group_roster` info message at WS connect (ids + display names) so the client preloads every member's sprites once.
   - Audio stays sequential (one room speaker). Single-character mode: zero change.

### Phase 2 — Full TADC cast

4. **Scaffold Ragatha, Kinger, Gangle, Zooble, Caine** with the wizard's generator scripts: `character.yaml` (franchise `digital_circus` so `tadc_censor` gates apply), system prompts, content pools via Ollama, distinct Edge voices per character (SoVITS fine-tunes later only if voice datasets appear). Append all five to `groups/tadc.yaml` roster.
5. **Sprites:** 39-40 per character via the existing `generate_character_poses.py` pipeline on paid Pollinations flux (~$0.07/character, ledger-tracked in `.secrets/`); TADC designs are well known to flux. rembg cutouts verified by composite (not raw-PNG eyeballing).
6. **Director scaling:** cap of 2 speakers/turn stays; least-recent fallback keeps a 7-member roster from starving anyone. Verify director prompt lists the full roster and still returns valid picks with llama3.

### Phase 3 — Comfort verified

7. **Real-audio vomit E2E:** inject genuine retching audio (CC0 sample) through the debug MCP inject-audio path; confirm detection → comfort line → TTS → playback. Tune the gate from evidence — options if it misses: single-frame trigger at high combined confidence, or widen the 5s window to cover the 3s-chunk cadence. Also verify all three text paths and recovery-clear.

### Phase 4 — Latency + liveliness

8. **Token-streaming LLM→TTS:** stream Ollama tokens; on each completed sentence (≥12 chars) run the per-sentence preclean/censor and submit to the existing chunk pipeline (`audio_chunk` client path unchanged). First audio starts after the FIRST sentence generates, not the whole reply. Safety filter runs per-sentence; the full-text pass stays for logging/telemetry. Gated by new `llm_token_streaming` flag (default on; off = today's behavior).
9. **Voice barge-in:** during playback the client keeps capturing; forwards mic audio only when RMS exceeds a rolling echo floor by a margin for ≥800ms sustained (config-tunable, conservative default). Server treats mid-playback audio arrivals as interrupts → existing cancel + `clear_audio` path. Flag `voice_barge_in` (default on dev, prove before party).
10. **Lip-flap:** while audio plays, cycle `talking`/`talking_excited` by playback RMS envelope (~8 Hz swap cap); silent → `listening`. Client-only, works for every character that has the speech poses.

## Out of scope

- SoVITS fine-tunes for the five new cast voices (Edge voices first; upgrade path exists via `GPT_SoVITS_<Name>` auto-resolution in `tts.py`).
- Overlapping/simultaneous audio for multiple speakers.
- Acoustic echo cancellation (true AEC) — energy-gate barge-in only.
- Fine-tuned personality LLM (explicitly declined).

## Error handling

- Stage mode with a missing member sprite set → that slot renders the placeholder sprite, logged, never crashes the draw loop.
- `group_roster` missing (old server) → client stays in single-sprite mode.
- Token-streaming: LLM stream error mid-reply → whatever sentences already went out stay; remainder falls back to the canned-fallback path; `was_partial` marked.
- Barge-in false-positive storm → flag off via config_live hot reload, no restart.

## Testing

- Unit: stage layout math (slot rects, active scaling), roster message handling, sentence-boundary splitter on token stream, barge-in RMS gate, lip-flap pose selection — all pure, no pygame/audio needed.
- Live (debug MCP + logs, per `.claude/rules/testing.md` audio verification rules): group turn with camera-cut, stage mode screenshot with 7 on screen, vomit inject E2E, token-streaming first-audio timing, voice interrupt mid-speech. Every live test confirms `_play_wav: playing` AND `_play_wav: done`.
