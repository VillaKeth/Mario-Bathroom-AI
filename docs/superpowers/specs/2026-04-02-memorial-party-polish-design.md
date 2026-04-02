# Memorial Overhaul + Party Polish — Design Spec

**Date:** 2026-04-02
**Status:** Approved (brainstorming complete)

---

## Overview

Two sub-projects to improve the Mario AI Party Bot:
- **Sub-Project A: Memorial Overhaul** — Transform the Lisa Webb memorial from a basic 2-phase text event into a grand, emotional 5-phase tribute with photo, SFX, music, and visual effects.
- **Sub-Project B: Party Polish** — Fix F11 fullscreen, inject Jacob VIP context into prompts.

---

## Sub-Project A: Memorial Overhaul

### Current State

- Memorial triggers via `/admin/trigger_memorial` or auto (45min+Jacob / 90min)
- Two phases: silence (15s + TTS) → toast (TTS)
- **Bugs:** Idle text bubbles leak during memorial; `memorial_active` only lasts ~15s
- No photo, no music, no visual effects, no SFX

### Target State

A 5-phase grand memorial spanning ~5 minutes with full idle suppression.

### Phase Timeline

| # | Phase | Duration | Audio | Visual |
|---|-------|----------|-------|--------|
| 1 | Announcement | ~10s | Mario TTS: "Hey everyone, can I have your attention..." | Screen dims gradually |
| 2 | Moment of Silence | ~20s | Mario TTS: "Lisa Webb was Jacob's aunt..." + soft chime SFX | Photo fade-in, glow, particles, name/dates text |
| 3 | Toast/Shot | ~15s | Mario TTS: "Raise a glass! To Lisa!" + glass clink SFX | Overlay shifts warm gold/amber |
| 4 | Memorial Music | ~222s | `lisa_webb_memorial.mp3` plays twice (111s × 2) | Photo stays, floating particles, "In Loving Memory" |
| 5 | Fade Out | ~10s | Mario TTS: "That was beautiful. Let's keep this party going!" | Overlay dissolves, normal mode resumes |

**Total duration:** ~4.6 minutes

**Note on phase durations:** Durations in the table are *inclusive* of TTS playback. E.g., Phase 1 "~10s" means the TTS audio itself is ~8s plus ~2s of pre/post pause. Server calculates exact duration from generated WAV size before sleeping.

### Server Changes

#### `server/main.py`

1. **Extend `memorial_active` flag**: Set `True` at start, clear only after Phase 5 completes (~5 min)
2. **Phase event protocol**: Send `memorial_event` websocket messages for each phase:
   ```json
   {"type": "memorial_event", "phase": "announcement", "name": "Lisa Webb", "audio": "<base64>"}
   {"type": "memorial_event", "phase": "silence", "name": "Lisa Webb", "born": "August 17, 1968", "died": "March 23, 2023", "audio": "<base64>"}
   {"type": "memorial_event", "phase": "toast", "name": "Lisa Webb", "audio": "<base64>"}
   {"type": "memorial_event", "phase": "music", "name": "Lisa Webb"}
   {"type": "memorial_event", "phase": "fadeout", "name": "Lisa Webb", "audio": "<base64>"}
   ```
3. **Timing control — server-driven with calculated delays**:
   - Server generates TTS audio for each phase, then calculates duration from WAV size: `duration_s = len(wav_bytes) / (sample_rate * channels * bytes_per_sample)` (16-bit mono 24kHz → `len / 48000`).
   - After sending each phase event + audio, server sleeps for the calculated audio duration before advancing to the next phase.
   - **Phase 4 (music)**: Server sends `{"phase": "music"}` then sleeps a fixed `225s` (111.6s × 2 + 2s buffer). No client-to-server acknowledgment needed — the server simply waits the known music duration.
   - **Phase 5 buffer**: After sending the fadeout event, server keeps `memorial_active = True` for an additional 15 seconds to cover client fadeout animation (3s) + fadeout TTS audio (~10s) + safety margin.
4. **Idle suppression**: `_idle_send_if_safe()` gate already checks `memorial_active` — extending flag duration to cover the full 5-min ceremony fixes the leak. Flag is only cleared after Phase 5 + 15s buffer.

#### `server/idle_behavior.py`

- Update memorial text for Phase 1 (announcement), Phase 2 (silence), Phase 3 (toast), Phase 5 (fadeout)
- Remove ellipsis from all memorial text (existing convention)
- Make text very clear and explicit about what's happening

### Client Changes

#### `client/main.py`

1. **Add `_memorial_active` flag**: Set on first memorial event, clear 3 seconds after fadeout animation completes. This client-side flag acts as a **secondary safety net** — even if server idle messages slip through due to timing, client will drop them.
2. **Suppress idle text during memorial**: Add check in `_on_mario_text()`:
   ```python
   def _on_mario_text(self, data):
       if self._memorial_active:
           return  # suppress idle text during memorial
       # ... existing logic
   ```
3. **Handle each phase**: Route `memorial_event` messages to display with phase-specific data
4. **Music fallback**: If `lisa_webb_memorial.mp3` is missing, skip Phase 4 (log warning), jump to Phase 5 after a 5-second pause

#### `client/mario_display.py`

1. **Memorial overlay phases**:
   - Phase 1 (announcement): Screen dims to 60% opacity black overlay
   - Phase 2 (silence): Full memorial overlay — Lisa's photo centered with soft golden glow, name/dates text, particle effects (floating light dots)
   - Phase 3 (toast): Warm gold/amber overlay tint, toast text
   - Phase 4 (music): Maintain photo + particles + "In Loving Memory" text
   - Phase 5 (fadeout): Alpha decreases over 3 seconds, overlay dissolves

2. **Photo rendering**: Load `client/assets/images/lisa_webb.jpg`, scale to ~300px height, center on screen with soft border/glow effect

3. **Particle effects**: Simple floating light particles (20-30) that drift upward slowly — gold/white color, variable alpha

4. **Text rendering**: Anti-aliased white text with subtle drop shadow:
   - "In Loving Memory" (large, centered above photo)
   - "Lisa Webb" (large, centered below photo)
   - "August 17, 1968 – March 23, 2023" (smaller, below name)

#### `client/audio_playback.py`

1. **Add `pygame.mixer.music` support**: For MP3 playback (memorial music)
   - `play_memorial_music(path, loops=1)` — plays MP3 file, `loops=1` means play twice
   - `stop_memorial_music(fadeout_ms=3000)` — fade out and stop
2. **Keep existing `sounddevice` for TTS WAV** — no changes to normal audio path

### New Assets

| File | Size | Purpose |
|------|------|---------|
| `client/assets/images/lisa_webb.jpg` | 38 KB | Lisa Webb obituary photo (170×220) |
| `client/assets/music/lisa_webb_memorial.mp3` | 1.69 MB | Mario World Music Box (111.6s) |

### SFX

- **Chime** (Phase 2): Synthesize using NumPy — 880Hz + 1320Hz sine waves mixed, exponential decay envelope (τ=0.3s), total ~1.2s, 44100Hz 16-bit mono WAV
- **Glass clink** (Phase 3): Synthesize using NumPy — 2500Hz + 4000Hz sine burst, very fast exponential decay (τ=0.08s), total ~0.5s, 44100Hz 16-bit mono WAV
- Save as `client/assets/sfx/memorial_chime.wav` and `client/assets/sfx/memorial_clink.wav`
- Generated by a one-time script `scripts/generate_sfx.py` — committed as WAV files, script kept for reproducibility

---

## Sub-Project B: Party Polish

### B1: Fullscreen Fix (F11)

**Current state:** `_toggle_fullscreen()` at `mario_display.py:857-887` — no error handling, no RESIZABLE flag on init.

**Fix:**
1. Add `pygame.RESIZABLE` to initial `pygame.display.set_mode()` call (line 340)
2. Wrap fullscreen toggle in try/except:
   ```python
   def _toggle_fullscreen(self):
       try:
           if self._is_fullscreen:
               self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.RESIZABLE)
           else:
               self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN | pygame.SCALED)
           self._is_fullscreen = not self._is_fullscreen
       except Exception as e:
           print(f"[WARN] Fullscreen toggle failed: {e}")
   ```
3. Update all drawing code to use `self.screen.get_size()` instead of hardcoded `WINDOW_WIDTH/WINDOW_HEIGHT` for key layout functions. Specifically update:
   - `_draw_background()` — scale background to current screen size
   - `_draw_mario()` — position Mario relative to screen bottom-center
   - `_draw_text_bubble()` — position bubble relative to screen width/height
   - `_draw_header()` — stretch header strips to full screen width
   - `_draw_memorial()` — center photo/text to current screen dimensions
   - Other functions can use hardcoded sizes as they are relative to the above

### B2: Jacob VIP Context Injection

**Current state:** `mario_prompt.py:build_context()` doesn't inject VIP profile data. Jacob is just treated as any guest.

**Fix:**
1. In `build_context()`, check if current speaker matches a VIP profile
2. If match found, load `server/data/vip_profiles/jacob_hoppenstedt.json` (confirmed existing, contains `interests`, `fun_facts`, `relationships`, `memorial` fields) and inject into system prompt:
   ```
   [VIP GUEST CONTEXT]
   You are talking to Jacob Hoppenstedt, the birthday boy!
   Key facts: {interests, relationships, fun facts from profile}
   Use this to make conversation personal and meaningful.
   ```
3. This makes Mario able to reference Jacob's interests, family, achievements naturally
4. **Schema**: VIP profile JSON has: `name`, `aliases[]`, `interests[]`, `fun_facts[]`, `relationships{}`, `memorial{}` — all string/array fields

---

## Testing Plan

### Memorial Testing
1. Trigger via `/admin/trigger_memorial` and verify all 5 phases fire in sequence
2. Verify idle text suppression (no bubbles during any phase, including Phase 5 fadeout)
3. Verify music plays twice and fades out
4. Verify photo displays correctly (or graceful degradation if missing)
5. Verify particle effects render without frame drops — **monitor FPS during Phase 2-4, ensure >30 FPS**
6. Verify normal operation resumes after fadeout + 15s server buffer
7. Verify memorial cannot be triggered twice (one-shot flags)

### Fullscreen Testing
1. Press F11 — verify enters fullscreen without error
2. Press F11 again — verify returns to windowed
3. Resize window — verify content scales

### Jacob VIP Testing
1. Set speaker name to "Jacob" and verify VIP context appears in prompt
2. Ask Mario "what do you know about me" as Jacob — verify personal details
3. Verify non-VIP speakers don't get VIP context

---

## Dependencies

- `pygame.mixer.music` — already available in pygame (no new deps)
- NumPy — already installed (for SFX generation)
- No external downloads needed — all assets already in repo

---

## Risk Mitigations

- **Photo quality**: 170×220 is small but sufficient for overlay display at ~300px with bilinear scaling
- **Music timing**: `pygame.mixer.music.get_busy()` polling ensures we know when music finishes
- **Frame rate**: Particle effects limited to 20-30 particles, simple alpha blending — won't impact FPS
- **Fallback**: If photo fails to load, memorial still works without it (text + music only)
