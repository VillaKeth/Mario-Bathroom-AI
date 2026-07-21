# Close the Gaps Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** TADC group mode live with the full cast on one screen, vomit comfort proven with real audio, token-level streaming, voice barge-in, lip-flap.

**Architecture:** Additive everywhere — group/stage features only activate in group mode; streaming/barge-in/lip-flap behind flags. Single-character path untouched. Spec: `docs/superpowers/specs/2026-07-21-close-the-gaps-design.md`.

**Tech Stack:** Python, pygame, Ollama, GPT-SoVITS/Edge TTS, resemblyzer, PANNs, websockets, pytest.

## Global Constraints

- Never `git add` config.json (gitignored, holds live admin_api_key); copy into worktree for live tests, delete after.
- `git add` specific files only; Qdrant `.lock` files must never be committed.
- Commit trailer: `Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>`
- No ellipsis in TTS-bound strings; TTS preprocessing changes require cache purge.
- Live tests follow `.claude/rules/testing.md`: `_play_wav: playing` AND `done`, bubble text matches speech, no cross-character leaks.
- Dev-box live runs use desktop-commander `start_process` (bg-process reaper kills tracked Bash background tasks).
- Server modules exist as both bare and `server.*` module instances — mutate via `__package__` idiom, never assume one copy.

---

## Task 1: Group mode live boot + fallout fixes

- [x] Copy main-checkout config.json into worktree; set `"mode": "group"`. NEVER commit it.
- [x] Add `mode`/`group` keys to `config.example.json` (committable template).
- [x] Boot server + client (desktop-commander), watch startup for `_load_group` result.
- [x] Drive via debug MCP / `/admin/simulate_text`: "hey who are you two?", "Jax, tell me a joke", "Pomni how are you?", generic question (director pick), rapid double-send (interrupt during group turn).
- [x] Verify per testing rules: each line spoken in the RIGHT voice (Pomni SoVITS vs Jax voice), `_play_wav` pairs, transcript accumulates, censor active.
- [x] Fix whatever breaks; each fix its own commit with a test where feasible.
- [x] Restore config (`mode: single`) until Phase 1 completes.

## Task 2: Client speaker camera-cut

**Files:** Modify `client/ws_client.py` (surface `speaker` on response messages), `client/main.py` + `client/mario_display.py` (per-character sprite cache + swap on speaker change). Test: `tests/test_speaker_cut.py` (pure: sprite-cache keying + speaker→set selection).

- [x] Server: include `speaker_id` (character id, not just display name) in group-turn `mario_response` payloads (`server/main.py` group send path).
- [x] Client: `_sprite_sets: dict[str, dict]` lazy-loaded per character id from `characters/<id>/sprites`; on message with `speaker_id` != current → swap active set + banner name for that utterance.
- [x] Unit tests for cache/selection logic; live re-run of Task 1 script confirming the sprite cuts to the talker.
- [x] Commit.

## Task 3: Stage mode — full roster on screen

**Files:** Modify `server/main.py` (send `group_roster` at WS accept when group loaded), `client/ws_client.py` (handle it), `client/mario_display.py` (stage layout + draw), `client/main.py` (hotkey toggle). Test: `tests/test_stage_layout.py` (slot rect math, active-speaker scaling, missing-sprite fallback).

- [x] Server: `{"type": "group_roster", "members": [{"id", "display_name"}, ...]}` on connect.
- [x] Layout: N horizontal slots in sprite zone; active speaker full scale/brightness + bubble name tag; others 0.8 scale, 55% brightness, `listening` pose (fallback neutral → placeholder). Pure function `stage_slots(n, zone_rect) -> [Rect]`.
- [x] Toggle: default stage ON in group mode; hotkey (first free F-key — audit F-key map before picking) flips camera-cut ↔ stage; `config_live.group_stage` overrides.
- [x] Unit tests for layout math; live: screenshot with both (later seven) members visible, speaker highlighted.
- [x] Commit.

## Task 4: Cast scaffolds (Ragatha, Kinger, Gangle, Zooble, Caine)

- [x] Generate via wizard generator scripts: character.yaml (franchise `digital_circus`), prompts, pools (Ollama), distinct Edge voice each (pick at implementation; no two share a voice).
- [x] Append five roster entries to `groups/tadc.yaml`.
- [x] Leak test each per testing rules (no Mario refs, censor active).
- [x] Commit per character or as one cast commit (yaml + pools only; sprites separate).

## Task 5: Cast sprites

- [ ] Pollinations paid flux via `generate_character_poses.py` (~40/char; ledger check before + after; NO `model=flux` URL param on free tier — paid path only).
- [ ] rembg cutouts; verify via composite-over-magenta (raw PNG eyeballing lies).
- [ ] Provenance logged per existing `*_run.log` convention.
- [ ] Placeholder sprites immediately so stage mode renders all seven before AI sprites land.
- [ ] Commit sprites per character.

## Task 6: Vomit comfort real-audio E2E — DONE (82c5dd2, 080ec3a)

- [x] Real freesound retch WAVs (8 clips, untracked in main-checkout tests/); streamed over binary WS like a mic (inject_audio MCP is STT-only — cannot reach PANNs, documented). Harness: scratchpad vomit_e2e_real.py — tiles the clip's loudest 3s window (sustained retching) + trailing near-silence frames (server only flushes its 96000B buffer on frame arrival).
- [x] Chain confirmed live: PANNs Grunt 0.74/Groan 0.35 → `[AUDIO_DISTRESS] Confirmed distress (tracker): conf=0.65, frames=2` → sick latch → comfort lines + SoVITS audio delivered over WS.
- [x] Tuned from evidence: coherence window now keyed on chunk CAPTURE time (`DistressTracker.update(now=)`) — wall-clock coherence could never see 2 frames in 5s on a slow box where chunks process 15-20s apart. Thresholds unchanged. +3 unit tests (TestCaptureTimeCoherence). Also `ws_ping_timeout` 90s — CPU-pegged pipeline dropped live sockets at uvicorn's 20s default.
- [x] Text paths live-verified: sick latch ("I think I'm gonna throw up" → comfort pool), friend-sick ("my friend is throwing up" → helper line), recovery-clear in same session ("ok I feel better now" → welcome-back pool; required adding the plain "feel better"/"better now" keyword family — TestSickRecovery). Mood expiry = existing auto-recover (main.py ~4849), code-inspected. New primary connection resets mood by design.
- [x] Committed: 82c5dd2 (capture-time + ping + E2E enablers), 080ec3a (recovery keywords).

## Task 7: Token-streaming LLM→TTS

**Files:** Modify `server/llm.py`/`llm_router.py` (streaming generate), `server/main.py` (sentence-boundary feeder into existing chunk pipeline). Test: `tests/test_token_stream_split.py` (boundary splitter over token deltas; flag off = unchanged path).

- [ ] `llm_token_streaming` flag (default on).
- [ ] Stream tokens; emit sentence when boundary + ≥12 chars; per-sentence preclean/censor/safety; submit to existing per-sentence TTS executor + `audio_chunk` sends. Stream error mid-reply → sent sentences stand, remainder → fallback, `was_partial`.
- [ ] Unit tests: splitter (abbreviations, numbers, emoji, no-boundary short replies), flag-off passthrough.
- [ ] Live: measure first-audio latency vs baseline on dev box; log both.
- [ ] Commit.

## Task 8: Voice barge-in

**Files:** Modify `client/main.py` (`_audio_stream_loop` gate), `server/main.py` (mid-playback audio = interrupt). Test: `tests/test_barge_gate.py` (RMS gate: rolling floor, margin, sustain).

- [x] Client: during playback compute mic RMS; forward only after exceeding rolling echo floor × margin for ≥800ms sustained (`voice_barge_in` flag + tunables in config_live).
- [x] Server: audio arriving while a response is playing → cancel + `clear_audio` + process as new input (reuse existing interrupt path).
- [x] Unit tests for the gate; live: talk over Mario mid-sentence → he stops and answers.
- [x] Commit.

## Task 9: Lip-flap

**Files:** Modify `client/audio_playback.py` (expose playback RMS envelope), `client/mario_display.py` (pose cycle). Test: `tests/test_lip_flap.py` (pose selection from envelope values, 8 Hz cap, silence → listening).

- [x] Envelope tap on the playing buffer; display swaps `talking`/`talking_excited` by level, ≤8 Hz; silence → `listening`; characters missing speech poses → current behavior.
- [x] Unit tests; live visual check both in single and stage mode.
- [x] Commit.

## Task 10: Merge

- [x] Full suite vs master-baseline worktree diff (expect the known ~28 config-env failures + 2 collection errors; zero NEW failures).
- [x] Purge TTS cache if any TTS-bound text changed.
- [x] Merge `feature/close-the-gaps` → master (--no-ff), push origin. Update TODO.md + memory.
