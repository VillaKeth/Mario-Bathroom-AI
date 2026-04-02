# Memorial Overhaul + Party Polish — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the Lisa Webb memorial into a grand 5-phase tribute with photo, SFX, particles, and music; fix F11 fullscreen; inject Jacob VIP context into prompts.

**Architecture:** Server orchestrates 5 memorial phases via websocket events with calculated sleep delays between each. Client renders phase-specific overlays (photo, particles, text) and plays MP3 music via `pygame.mixer.music`. Both server and client maintain independent `memorial_active` flags for bullet-proof idle suppression. VIP context is injected into LLM system prompt when speaker matches a VIP profile.

**Tech Stack:** Python, pygame (display + mixer.music), sounddevice (TTS WAV), NumPy (SFX generation), FastAPI/websockets (server), GPT-SoVITS (TTS)

**Spec:** `docs/superpowers/specs/2026-04-02-memorial-party-polish-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `scripts/generate_sfx.py` | CREATE | One-time script to generate chime + clink WAV files |
| `client/assets/sfx/memorial_chime.wav` | CREATE (generated) | Soft bell chime for moment of silence |
| `client/assets/sfx/memorial_clink.wav` | CREATE (generated) | Glass clink for toast |
| `client/audio_playback.py` | MODIFY | Add `play_memorial_music()` and `stop_memorial_music()` via pygame.mixer.music |
| `client/mario_display.py` | MODIFY | Rewrite `_draw_memorial()` and `show_memorial()` for 5-phase overlay with photo, particles, text |
| `client/main.py` | MODIFY | Add `_memorial_active` flag, suppress idle text in `_on_mario_text()`, handle music phase |
| `server/main.py` | MODIFY | Rewrite `trigger_memorial()` to orchestrate 5 phases with sleep delays, extend flag lifetime |
| `server/idle_behavior.py` | MODIFY | Update memorial text strings for 5 phases |
| `server/mario_prompt.py` | MODIFY | Add VIP context injection in `build_context()` |
| `client/mario_display.py` | MODIFY | Wrap `_toggle_fullscreen()` in try/except, add RESIZABLE flag |

---

## Task 1: Generate Memorial SFX WAV Files

**Files:**
- Create: `scripts/generate_sfx.py`
- Create: `client/assets/sfx/memorial_chime.wav` (generated output)
- Create: `client/assets/sfx/memorial_clink.wav` (generated output)

- [ ] **Step 1: Create `scripts/generate_sfx.py`**

```python
"""Generate memorial SFX WAV files using NumPy synthesis."""
import numpy as np
import wave
import os

SAMPLE_RATE = 44100

def write_wav(path, audio_float, sample_rate=SAMPLE_RATE):
    """Write float32 audio [-1,1] to 16-bit WAV."""
    audio_int = (audio_float * 32767).astype(np.int16)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with wave.open(path, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(audio_int.tobytes())
    print(f"Wrote {path} ({len(audio_int)} samples, {len(audio_int)/sample_rate:.2f}s)")

def generate_chime(path):
    """Gentle bell chime: 880Hz + 1320Hz with exponential decay."""
    duration = 1.5
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False)
    tone = 0.5 * np.sin(2 * np.pi * 880 * t) + 0.3 * np.sin(2 * np.pi * 1320 * t)
    envelope = np.exp(-t / 0.4)
    audio = tone * envelope * 0.6
    write_wav(path, audio.astype(np.float32))

def generate_clink(path):
    """Glass clink: high-freq burst with fast decay."""
    duration = 0.6
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False)
    tone = 0.4 * np.sin(2 * np.pi * 2500 * t) + 0.3 * np.sin(2 * np.pi * 4000 * t) + 0.2 * np.sin(2 * np.pi * 6000 * t)
    envelope = np.exp(-t / 0.08)
    audio = tone * envelope * 0.7
    write_wav(path, audio.astype(np.float32))

if __name__ == "__main__":
    base = os.path.join(os.path.dirname(__file__), "..", "client", "assets", "sfx")
    generate_chime(os.path.join(base, "memorial_chime.wav"))
    generate_clink(os.path.join(base, "memorial_clink.wav"))
    print("Done! SFX files generated.")
```

- [ ] **Step 2: Run the script to generate WAV files**

Run: `cd C:\Users\Vketh\Desktop\Mario_AI && python scripts/generate_sfx.py`
Expected: Two WAV files created in `client/assets/sfx/`

- [ ] **Step 3: Verify files exist and are valid**

Run: `python -c "import wave; w=wave.open('client/assets/sfx/memorial_chime.wav'); print(f'chime: {w.getnframes()/w.getframerate():.2f}s'); w=wave.open('client/assets/sfx/memorial_clink.wav'); print(f'clink: {w.getnframes()/w.getframerate():.2f}s')"`
Expected: `chime: 1.50s` and `clink: 0.60s`

- [ ] **Step 4: Commit**

```bash
git add scripts/generate_sfx.py client/assets/sfx/
git commit -m "feat: generate memorial SFX (chime + clink WAV files)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 2: Add Memorial Music Support to AudioPlayback

**Files:**
- Modify: `client/audio_playback.py` (add `play_memorial_music()`, `stop_memorial_music()`, `is_music_playing`)

- [ ] **Step 1: Add pygame.mixer.music methods to AudioPlayback**

At the top of `client/audio_playback.py`, add `import pygame` after the existing imports.

Add these methods to the `AudioPlayback` class after the existing `is_playing` property (after line 76):

```python
    # ── Memorial music (MP3 via pygame.mixer.music) ──────────────
    def play_memorial_music(self, path: str, loops: int = 1):
        """Play an MP3 file using pygame.mixer.music.
        
        Args:
            path: Path to the MP3 file.
            loops: Number of extra repeats (0=play once, 1=play twice, etc.)
        """
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            pygame.mixer.music.load(path)
            pygame.mixer.music.set_volume(0.5)  # Lower than TTS so it's background
            pygame.mixer.music.play(loops=loops)
            if DEBUG_PLAYBACK:
                logger.info(f"[DEBUG_PLAYBACK] Memorial music started: {path} (loops={loops})")
        except Exception as e:
            logger.error(f"[DEBUG_PLAYBACK] Memorial music error: {e}")

    def stop_memorial_music(self, fadeout_ms: int = 3000):
        """Fade out and stop memorial music."""
        try:
            if pygame.mixer.music.get_busy():
                pygame.mixer.music.fadeout(fadeout_ms)
                if DEBUG_PLAYBACK:
                    logger.info(f"[DEBUG_PLAYBACK] Memorial music fading out ({fadeout_ms}ms)")
        except Exception as e:
            logger.error(f"[DEBUG_PLAYBACK] Memorial music stop error: {e}")

    @property
    def is_music_playing(self) -> bool:
        """Check if memorial music is currently playing."""
        try:
            return pygame.mixer.music.get_busy()
        except Exception:
            return False
```

- [ ] **Step 2: Verify no import errors**

Run: `cd C:\Users\Vketh\Desktop\Mario_AI && python -c "from client.audio_playback import AudioPlayback; a = AudioPlayback(); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add client/audio_playback.py
git commit -m "feat: add memorial music support (pygame.mixer.music MP3 playback)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 3: Rewrite Memorial Display Overlay (5-Phase Rendering)

**Files:**
- Modify: `client/mario_display.py:1784-1841` (rewrite `show_memorial()` and `_draw_memorial()`)

This task replaces the existing 2-phase memorial overlay with a 5-phase grand tribute.

- [ ] **Step 1: Add memorial photo loading**

Near the top of `mario_display.py`, inside the `__init__` method after the existing memorial attribute block (line 277, before `def _load_sprites` at line 279), add photo loading:

```python
        # ── Memorial photo ──
        self._memorial_photo = None
        try:
            photo_path = os.path.join(os.path.dirname(__file__), "assets", "images", "lisa_webb.jpg")
            if os.path.exists(photo_path):
                raw = pygame.image.load(photo_path)
                # Scale to ~300px height, maintain aspect ratio
                scale = 300 / raw.get_height()
                new_w = int(raw.get_width() * scale)
                self._memorial_photo = pygame.transform.smoothscale(raw, (new_w, 300))
                if DEBUG_DISPLAY:
                    logger.info(f"[DEBUG_DISPLAY] Memorial photo loaded: {new_w}x300")
        except Exception as e:
            logger.warning(f"[DEBUG_DISPLAY] Failed to load memorial photo: {e}")
```

- [ ] **Step 2: Add memorial particle system**

Add a simple particle class and list. First, add `self._memorial_particles = []` to the existing memorial attributes block in `__init__` (after line 277):

```python
        self._memorial_particles = []  # Floating golden light particles
```

Then add these methods above the `show_memorial` method (around line 1780). Note: uses existing `random` import (line 7):

```python
    def _init_memorial_particles(self):
        """Initialize floating memorial particles (golden light dots)."""
        self._memorial_particles = []
        w, h = WINDOW_WIDTH, WINDOW_HEIGHT
        for _ in range(25):
            self._memorial_particles.append({
                "x": random.randint(0, w),
                "y": random.randint(0, h),
                "speed": random.uniform(0.3, 1.2),
                "alpha": random.randint(80, 200),
                "size": random.randint(2, 5),
                "drift": random.uniform(-0.3, 0.3),
            })

    def _update_memorial_particles(self):
        """Update particle positions — drift upward, wrap around."""
        for p in self._memorial_particles:
            p["y"] -= p["speed"]
            p["x"] += p["drift"]
            p["alpha"] = max(60, min(220, p["alpha"] + random.randint(-5, 5)))
            if p["y"] < -10:
                p["y"] = WINDOW_HEIGHT + 10
                p["x"] = random.randint(0, WINDOW_WIDTH)

    def _draw_memorial_particles(self, surface):
        """Draw golden light particles on a surface."""
        for p in self._memorial_particles:
            color = (255, 215, 100, p["alpha"])  # Gold with variable alpha
            particle_surf = pygame.Surface((p["size"] * 2, p["size"] * 2), pygame.SRCALPHA)
            pygame.draw.circle(particle_surf, color, (p["size"], p["size"]), p["size"])
            surface.blit(particle_surf, (int(p["x"]), int(p["y"])))
```

- [ ] **Step 3: Rewrite `show_memorial()` (replace lines 1784-1793)**

Replace the existing `show_memorial` method with:

```python
    def show_memorial(self, name, phase, text, duration=15):
        """Show memorial overlay — handles all 5 phases."""
        self._memorial_active = True
        self._memorial_phase = phase
        self._memorial_name = name
        self._memorial_text = text
        self._memorial_start = time.time()
        self._memorial_duration = duration
        if phase in ("silence", "music"):
            self._init_memorial_particles()
        if DEBUG_DISPLAY:
            logger.info(f"[DEBUG_DISPLAY] Memorial overlay: phase={phase} name={name} duration={duration}")
```

- [ ] **Step 4: Rewrite `_draw_memorial()` (replace lines 1795-1841)**

Replace the entire `_draw_memorial` method with the 5-phase renderer:

```python
    def _draw_memorial(self, surface):
        """Draw memorial overlay — grand 5-phase tribute."""
        try:
            w, h = surface.get_size()
            elapsed = time.time() - self._memorial_start
            phase = self._memorial_phase

            # ── Phase 1: Announcement (dim screen) ──
            if phase == "announcement":
                overlay = pygame.Surface((w, h), pygame.SRCALPHA)
                alpha = min(150, int(elapsed * 30))  # Gradual dim
                overlay.fill((0, 0, 0, alpha))
                surface.blit(overlay, (0, 0))

            # ── Phase 2: Moment of Silence (photo, particles, glow) ──
            elif phase == "silence":
                overlay = pygame.Surface((w, h), pygame.SRCALPHA)
                overlay.fill((0, 0, 0, 200))
                surface.blit(overlay, (0, 0))

                self._update_memorial_particles()
                self._draw_memorial_particles(surface)

                # Photo with golden glow
                if self._memorial_photo:
                    photo_rect = self._memorial_photo.get_rect(center=(w // 2, h // 2 - 20))
                    # Golden glow behind photo
                    glow_surf = pygame.Surface((photo_rect.width + 20, photo_rect.height + 20), pygame.SRCALPHA)
                    glow_surf.fill((255, 200, 50, 60))
                    glow_rect = glow_surf.get_rect(center=(w // 2, h // 2 - 20))
                    surface.blit(glow_surf, glow_rect)
                    surface.blit(self._memorial_photo, photo_rect)

                # Text above photo
                font_large = pygame.font.SysFont("arial", 32, bold=True)
                font_name = pygame.font.SysFont("arial", 36, bold=True)
                font_dates = pygame.font.SysFont("arial", 20)

                title = "In Loving Memory"
                title_surf = font_large.render(title, True, (255, 255, 255))
                # Drop shadow
                shadow_surf = font_large.render(title, True, (0, 0, 0))
                surface.blit(shadow_surf, shadow_surf.get_rect(center=(w // 2 + 2, h // 2 - 182)))
                surface.blit(title_surf, title_surf.get_rect(center=(w // 2, h // 2 - 180)))

                # Name below photo
                name_surf = font_name.render(self._memorial_name, True, (255, 215, 0))
                name_shadow = font_name.render(self._memorial_name, True, (0, 0, 0))
                photo_bottom = h // 2 + 140
                surface.blit(name_shadow, name_shadow.get_rect(center=(w // 2 + 2, photo_bottom + 2)))
                surface.blit(name_surf, name_surf.get_rect(center=(w // 2, photo_bottom)))

                # Dates
                dates_text = "August 17, 1968 – March 23, 2023"
                dates_surf = font_dates.render(dates_text, True, (200, 200, 200))
                surface.blit(dates_surf, dates_surf.get_rect(center=(w // 2, photo_bottom + 40)))

            # ── Phase 3: Toast/Shot (warm amber overlay) ──
            elif phase == "toast":
                overlay = pygame.Surface((w, h), pygame.SRCALPHA)
                overlay.fill((60, 30, 0, 180))
                surface.blit(overlay, (0, 0))

                font_toast = pygame.font.SysFont("arial", 34, bold=True)
                toast_text = f"To {self._memorial_name}!"
                toast_surf = font_toast.render(toast_text, True, (255, 215, 0))
                surface.blit(toast_surf, toast_surf.get_rect(center=(w // 2, h // 2)))

                emoji_font = pygame.font.SysFont("arial", 28)
                emoji_surf = emoji_font.render("Raise your glass!", True, (255, 255, 255))
                surface.blit(emoji_surf, emoji_surf.get_rect(center=(w // 2, h // 2 - 50)))

            # ── Phase 4: Memorial Music (photo + particles + "In Loving Memory") ──
            elif phase == "music":
                overlay = pygame.Surface((w, h), pygame.SRCALPHA)
                overlay.fill((0, 0, 0, 210))
                surface.blit(overlay, (0, 0))

                self._update_memorial_particles()
                self._draw_memorial_particles(surface)

                if self._memorial_photo:
                    photo_rect = self._memorial_photo.get_rect(center=(w // 2, h // 2 - 20))
                    glow_surf = pygame.Surface((photo_rect.width + 20, photo_rect.height + 20), pygame.SRCALPHA)
                    glow_surf.fill((255, 200, 50, 40))
                    glow_rect = glow_surf.get_rect(center=(w // 2, h // 2 - 20))
                    surface.blit(glow_surf, glow_rect)
                    surface.blit(self._memorial_photo, photo_rect)

                font_mem = pygame.font.SysFont("arial", 28, bold=True)
                mem_surf = font_mem.render("In Loving Memory", True, (255, 255, 255))
                surface.blit(mem_surf, mem_surf.get_rect(center=(w // 2, h // 2 - 190)))

                font_name = pygame.font.SysFont("arial", 30, bold=True)
                name_surf = font_name.render(self._memorial_name, True, (255, 215, 0))
                surface.blit(name_surf, name_surf.get_rect(center=(w // 2, h // 2 + 170)))

            # ── Phase 5: Fade Out ──
            elif phase == "fadeout":
                fade_duration = 3.0
                if elapsed < fade_duration:
                    alpha = int(200 * (1.0 - elapsed / fade_duration))
                    overlay = pygame.Surface((w, h), pygame.SRCALPHA)
                    overlay.fill((0, 0, 0, max(0, alpha)))
                    surface.blit(overlay, (0, 0))
                else:
                    self._memorial_active = False

        except Exception as e:
            logger.debug(f"Memorial draw error: {e}")
```

- [ ] **Step 5: Verify display module imports**

Run: `cd C:\Users\Vketh\Desktop\Mario_AI && python -c "from client.mario_display import MarioDisplay; print('OK')"`
Expected: `OK` (no import errors)

- [ ] **Step 6: Commit all display changes (Steps 1-4)**

```bash
git add client/mario_display.py
git commit -m "feat: 5-phase memorial overlay (photo, particles, text, fadeout)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 4: Client Memorial Suppression + Music Phase Handling

**Files:**
- Modify: `client/main.py:211-218` (add memorial gate in `_on_mario_text()`)
- Modify: `client/main.py:376-385` (enhance `_on_memorial_event()` for music phase)

- [ ] **Step 1: Add `_memorial_active` flag to client MarioApp `__init__`**

Find the `__init__` method of `MarioApp` class in `client/main.py`. Add after other flag initializations:

```python
        self._memorial_active = False  # Suppresses idle text during memorial
```

- [ ] **Step 2: Add memorial gate to `_on_mario_text()` (line 211)**

Add at the very top of `_on_mario_text()`, before any existing code:

```python
        # Suppress idle text bubbles during memorial ceremony
        if self._memorial_active:
            if DEBUG_CLIENT:
                logger.info("[DEBUG_CLIENT] Suppressed idle text during memorial")
            return
```

- [ ] **Step 3: Enhance `_on_memorial_event()` for 5-phase handling (replace lines 376-385)**

Replace the existing `_on_memorial_event` method:

```python
    def _on_memorial_event(self, data: dict):
        """Called when server sends memorial event — handles all 5 phases."""
        phase = data.get("phase", "silence")
        name = data.get("name", "")
        text = data.get("text", "")
        duration = data.get("duration", 15)
        if DEBUG_CLIENT:
            logger.info(f"[DEBUG_CLIENT] Memorial event: phase={phase} name={name}")

        # Set memorial active on first phase, clear after fadeout
        if phase == "announcement":
            self._memorial_active = True
        elif phase == "fadeout":
            # Clear flag 3s after fadeout starts (animation duration)
            def _clear_flag():
                import time
                time.sleep(duration + 3)
                self._memorial_active = False
                if DEBUG_CLIENT:
                    logger.info("[DEBUG_CLIENT] Memorial flag cleared after fadeout")
            threading.Thread(target=_clear_flag, daemon=True).start()

        # Start/stop memorial music
        if phase == "music":
            music_path = os.path.join(os.path.dirname(__file__), "assets", "music", "lisa_webb_memorial.mp3")
            if os.path.exists(music_path):
                self.audio.play_memorial_music(music_path, loops=1)  # Play twice
            else:
                logger.warning(f"[DEBUG_CLIENT] Memorial music not found: {music_path}")
        elif phase == "fadeout":
            self.audio.stop_memorial_music(fadeout_ms=3000)

        # Route to display
        if self.display:
            self.display.show_memorial(name, phase, text, duration)

        # Play SFX for specific phases
        sfx_dir = os.path.join(os.path.dirname(__file__), "assets", "sfx")
        if phase == "silence":
            chime_path = os.path.join(sfx_dir, "memorial_chime.wav")
            if os.path.exists(chime_path):
                try:
                    import wave
                    with open(chime_path, "rb") as f:
                        self.audio.play(f.read())
                except Exception as e:
                    logger.warning(f"[DEBUG_CLIENT] Chime SFX error: {e}")
        elif phase == "toast":
            clink_path = os.path.join(sfx_dir, "memorial_clink.wav")
            if os.path.exists(clink_path):
                try:
                    with open(clink_path, "rb") as f:
                        self.audio.play(f.read())
                except Exception as e:
                    logger.warning(f"[DEBUG_CLIENT] Clink SFX error: {e}")
```

- [ ] **Step 4: Add missing imports at top of `client/main.py` if not present**

Ensure `import threading` and `import os` are in the imports section.

- [ ] **Step 5: Verify no import/syntax errors**

Run: `cd C:\Users\Vketh\Desktop\Mario_AI && python -c "from client.main import MarioApp; print('OK')"`
Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add client/main.py
git commit -m "feat: client memorial suppression + music/SFX phase handling

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 5: Server 5-Phase Memorial Orchestration

**Files:**
- Modify: `server/main.py:1192-1280` (rewrite `trigger_memorial()` for 5 phases)
- Modify: `server/idle_behavior.py:1078-1100` (update memorial text)

This is the largest task — replacing the 2-phase server memorial with a 5-phase orchestrated ceremony.

- [ ] **Step 1: Update memorial text in `server/idle_behavior.py`**

The existing inline memorial text in `check_memorial_event()` (lines 1081-1102) uses f-strings with `memorial['person']` interpolation. These stay for the auto-trigger path. The new module-level constants (added in Step 3 below) are used by the server's 5-phase manual trigger path.

- [ ] **Step 2: Rewrite `trigger_memorial()` in `server/main.py`**

Replace the existing `trigger_memorial()` function (lines 1192-1284) with the new 5-phase orchestrator. Note: `asyncio` (line 15) and `time` (line 23) are already imported in `server/main.py`. The new function:

1. Sets `memorial_active = True` at start
2. Synthesizes TTS for Phase 1, sends event + audio, sleeps for audio duration
3. Synthesizes TTS for Phase 2, sends event + audio, sleeps for audio duration + 5s silence
4. Synthesizes TTS for Phase 3, sends event + audio, sleeps for audio duration
5. Sends music phase event (no TTS), sleeps for 225s
6. Synthesizes TTS for Phase 5, sends event + audio, sleeps for audio duration + 15s buffer
7. Clears `memorial_active = False`

```python
async def trigger_memorial(request_body: dict = {}):
    """Trigger 5-phase Lisa Webb memorial ceremony."""
    global _active_ws
    if not _active_ws:
        return {"status": "error", "message": "No client connected"}

    if state_current.get("memorial_active"):
        return {"status": "error", "message": "Memorial already in progress"}

    state_current["memorial_active"] = True
    state_current["memorial_triggered_at"] = time.time()
    logger.info("[MEMORIAL] Starting 5-phase memorial ceremony")

    async def _run_memorial():
        try:
            ws = _active_ws
            if not ws:
                return

            phases = [
                ("announcement", idle_behavior.MEMORIAL_ANNOUNCEMENT, 2),
                ("silence", idle_behavior.MEMORIAL_SILENCE, 5),
                ("toast", idle_behavior.MEMORIAL_TOAST, 2),
                ("music", None, 0),
                ("fadeout", idle_behavior.MEMORIAL_FADEOUT, 0),
            ]

            for phase_name, text, extra_delay in phases:
                if not _active_ws:
                    logger.warning("[MEMORIAL] Client disconnected, aborting")
                    break

                event = {
                    "type": "memorial_event",
                    "phase": phase_name,
                    "name": "Lisa Webb",
                }

                if phase_name == "silence":
                    event["born"] = "August 17, 1968"
                    event["died"] = "March 23, 2023"

                audio_bytes = None
                audio_duration = 0

                if text:
                    # Synthesize TTS
                    loop = asyncio.get_event_loop()
                    try:
                        audio_bytes = await loop.run_in_executor(
                            _tts_executor, lambda t=text: tts.synthesize_user(t)
                        )
                        if audio_bytes:
                            # Calculate duration: 16-bit mono 24kHz = 48000 bytes/sec
                            audio_duration = len(audio_bytes) / 48000
                            logger.info(f"[MEMORIAL] phase={phase_name} audio={len(audio_bytes)}B duration={audio_duration:.1f}s")
                    except Exception as e:
                        logger.error(f"[MEMORIAL] TTS error for {phase_name}: {e}")

                # Send event + audio
                try:
                    event["text"] = text or ""
                    event["duration"] = int(audio_duration + extra_delay + 2)
                    await ws.send_json(event)
                    if audio_bytes:
                        await ws.send_bytes(audio_bytes)
                except Exception as e:
                    logger.error(f"[MEMORIAL] Send error for {phase_name}: {e}")
                    break

                # Wait for phase to complete
                if phase_name == "music":
                    logger.info("[MEMORIAL] Music phase — sleeping 225s")
                    await asyncio.sleep(225)
                elif audio_duration > 0:
                    await asyncio.sleep(audio_duration + extra_delay)
                else:
                    await asyncio.sleep(extra_delay + 2)

            # Buffer after fadeout — keep memorial_active for 15 more seconds
            logger.info("[MEMORIAL] Fadeout sent, waiting 15s buffer before clearing flag")
            await asyncio.sleep(15)

        except Exception as e:
            logger.error(f"[MEMORIAL] Ceremony error: {e}")
        finally:
            state_current["memorial_active"] = False
            logger.info("[MEMORIAL] Memorial ceremony complete, flag cleared")

    asyncio.create_task(_run_memorial())
    return {"status": "ok", "message": "Memorial triggered"}
```

- [ ] **Step 3: Add module-level memorial text constants to `server/idle_behavior.py`**

The existing memorial text is inline in `check_memorial_event()` (lines 1081-1102) as f-strings. Add new module-level constants at the top of the file (after imports, before the class definition). These will be used by the server's 5-phase orchestrator:

```python
# ── Memorial text constants (no ellipsis — convention) ──────────────
MEMORIAL_ANNOUNCEMENT = (
    "*Mario removes his hat and holds it to his chest* "
    "Hey everyone, can I have your attention for just a moment? "
    "Tonight we are celebrating Jacob's birthday, but I want us to take "
    "a special moment to honor someone very important to this family."
)

MEMORIAL_SILENCE = (
    "Lisa Webb was Jacob's beloved aunt. "
    "She was born on August 17th, 1968, and she passed away on March 23rd, 2023. "
    "She meant the world to this family, and her light touched everyone who knew her. "
    "Let us take a moment of silence in her memory."
)

MEMORIAL_TOAST = (
    "*puts hat back on with a warm smile* "
    "Alright everyone, Aunt Lisa would not want us to be sad! "
    "She would want us to CELEBRATE! So right now, everybody grab a drink! "
    "We are taking a shot for Aunt Lisa! "
    "To Lisa Webb, the kind of person who made every room brighter! "
    "Ready? One, two, three, CHEERS! Wahoo!"
)

MEMORIAL_FADEOUT = (
    "That was beautiful, everyone. Lisa would be so proud. "
    "Now, let us keep this party going for Jacob! "
    "Wahoo! Let's-a go!"
)
```

The existing inline text in `check_memorial_event()` (lines 1081-1102) can remain as-is for the auto-trigger path, or optionally be updated to reference these constants.

In `server/main.py`, `idle_behavior` is imported as: `from idle_behavior import IdleBehavior` and instantiated as `idle_behavior = IdleBehavior()`. Since the constants are module-level, access them in `main.py` by adding this import near the top:

```python
from idle_behavior import MEMORIAL_ANNOUNCEMENT, MEMORIAL_SILENCE, MEMORIAL_TOAST, MEMORIAL_FADEOUT
```

- [ ] **Step 4: Verify server starts without errors**

Run: `cd C:\Users\Vketh\Desktop\Mario_AI && python -c "import server.main; print('OK')"` (or run the server briefly)
Expected: No import errors

- [ ] **Step 5: Commit**

```bash
git add server/main.py server/idle_behavior.py
git commit -m "feat: 5-phase memorial ceremony (server orchestration)

- announcement → silence → toast → music (225s) → fadeout
- Server keeps memorial_active for full duration + 15s buffer
- TTS duration calculated from WAV size for accurate phase timing

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 6: Fullscreen Fix (F11)

**Files:**
- Modify: `client/mario_display.py:340` (add RESIZABLE flag)
- Modify: `client/mario_display.py:857-885` (wrap in try/except)

- [ ] **Step 1: Add RESIZABLE flag to initial display mode (line 340)**

Change:
```python
self._screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
```
To:
```python
self._screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.RESIZABLE)
```

- [ ] **Step 2: Wrap `_toggle_fullscreen()` in try/except (lines 857-885)**

Wrap the entire body of `_toggle_fullscreen()` in a try/except block:

```python
    def _toggle_fullscreen(self):
        """Toggle between fullscreen and windowed mode with native resolution scaling."""
        try:
            self._fullscreen = not self._fullscreen
            if self._fullscreen:
                info = pygame.display.Info()
                self._screen = pygame.display.set_mode(
                    (info.current_w, info.current_h), pygame.FULLSCREEN | pygame.SCALED
                )
                scale = min(info.current_w / WINDOW_WIDTH, info.current_h / WINDOW_HEIGHT)
                self._render_w = int(WINDOW_WIDTH * scale)
                self._render_h = int(WINDOW_HEIGHT * scale)
                self._fs_scale = scale
                self._display_scale = scale
                self._native_width = info.current_w
                self._native_height = info.current_h
                if DEBUG_DISPLAY:
                    logger.info(f"[DEBUG_DISPLAY] Fullscreen ON: {info.current_w}x{info.current_h}, scale={scale:.2f}")
            else:
                self._screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.RESIZABLE)
                self._render_buffer = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT))
                self._render_w = WINDOW_WIDTH
                self._render_h = WINDOW_HEIGHT
                self._fs_scale = 1.0
                self._display_scale = 1.0
                self._native_width = WINDOW_WIDTH
                self._native_height = WINDOW_HEIGHT
                if DEBUG_DISPLAY:
                    logger.info("[DEBUG_DISPLAY] Fullscreen OFF: windowed 800x600")
        except Exception as e:
            logger.error(f"[DEBUG_DISPLAY] Fullscreen toggle failed: {e}")
            # Revert to safe windowed mode
            try:
                self._fullscreen = False
                self._screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.RESIZABLE)
            except Exception:
                pass
```

Key changes: added `| pygame.SCALED` to fullscreen mode, `pygame.RESIZABLE` to windowed fallback, full try/except with safe fallback.

- [ ] **Step 3: Commit**

```bash
git add client/mario_display.py
git commit -m "fix: F11 fullscreen with SCALED flag, error handling, RESIZABLE window

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 7: Jacob VIP Context Injection

**Files:**
- Modify: `server/mario_prompt.py:170+` (add VIP injection in `build_context()`)

- [ ] **Step 1: Add VIP profile loader function**

Near the top of `server/mario_prompt.py` (after existing imports on lines 6-7), add the missing imports:

```python
import os
import json as _json

_VIP_PROFILES_DIR = os.path.join(os.path.dirname(__file__), "data", "vip_profiles")
_vip_cache = {}

def _load_vip_profile(speaker_name: str) -> dict | None:
    """Load VIP profile if speaker matches any VIP aliases."""
    if not speaker_name:
        return None
    name_lower = speaker_name.lower()

    # Check cache first
    if name_lower in _vip_cache:
        return _vip_cache[name_lower]

    # Scan VIP profiles
    if not os.path.isdir(_VIP_PROFILES_DIR):
        return None
    for fname in os.listdir(_VIP_PROFILES_DIR):
        if not fname.endswith(".json"):
            continue
        try:
            fpath = os.path.join(_VIP_PROFILES_DIR, fname)
            with open(fpath, "r", encoding="utf-8") as f:
                profile = _json.load(f)
            aliases = [a.lower() for a in profile.get("aliases", [])]
            aliases.append(profile.get("name", "").lower())
            if any(alias in name_lower or name_lower in alias for alias in aliases if alias):
                _vip_cache[name_lower] = profile
                return profile
        except Exception:
            continue
    _vip_cache[name_lower] = None
    return None
```

- [ ] **Step 2: Inject VIP context in `build_context()` (after line 185)**

Find the `build_context()` function. After the night progression injection block (around line 185-200), add:

```python
    # Inject VIP guest context if speaker matches a VIP profile
    vip = _load_vip_profile(speaker_name)
    if vip:
        vip_lines = [f"\n[VIP GUEST CONTEXT]\nYou are talking to {vip.get('name', speaker_name)}!"]
        if vip.get("title"):
            vip_lines.append(f"Title: {vip['title']}")
        if vip.get("interests"):
            vip_lines.append(f"Interests: {', '.join(vip['interests'][:8])}")
        if vip.get("fun_facts"):
            vip_lines.append(f"Fun facts: {'; '.join(vip['fun_facts'][:5])}")
        if vip.get("relationships"):
            rels = vip["relationships"]
            rel_strs = [f"{k}: {v}" for k, v in rels.items()]
            vip_lines.append(f"Relationships: {', '.join(rel_strs[:5])}")
        vip_lines.append("Use this context to make conversation personal and meaningful. Reference these details naturally, not all at once.")
        vip_context = "\n".join(vip_lines)
        messages.append({"role": "system", "content": vip_context})
```

- [ ] **Step 3: Verify import works**

Run: `cd C:\Users\Vketh\Desktop\Mario_AI && python -c "from server.mario_prompt import build_context; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add server/mario_prompt.py
git commit -m "feat: Jacob VIP context injection into LLM prompts

Mario now knows who Jacob is when he's speaking — interests,
relationships, fun facts from VIP profile.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 8: Integration Test — Full Memorial Flow

**Files:**
- No new files — this is a manual verification task

- [ ] **Step 1: Start the server**

Run: `cd C:\Users\Vketh\Desktop\Mario_AI && python -m server.main`
Expected: Server starts on port 8765

- [ ] **Step 2: Start the client**

Run (new terminal): `cd C:\Users\Vketh\Desktop\Mario_AI && python client/main.py`
Expected: Pygame window opens, connects to server, 74 poses loaded

- [ ] **Step 3: Trigger memorial via admin API**

Run: `curl -X POST http://localhost:8765/admin/trigger_memorial -H "Content-Type: application/json" -d "{}"`
Expected: `{"status": "ok", "message": "Memorial triggered"}`

- [ ] **Step 4: Verify all 5 phases visually**

Watch the pygame window and server logs:
1. Phase 1 (announcement): Screen dims, Mario speaks announcement
2. Phase 2 (silence): Photo appears with golden glow, particles float, chime SFX, Mario speaks
3. Phase 3 (toast): Warm amber overlay, clink SFX, Mario speaks toast
4. Phase 4 (music): Photo + particles + "In Loving Memory", music box plays
5. Phase 5 (fadeout): Overlay dissolves, Mario speaks, normal mode resumes

- [ ] **Step 5: Verify idle suppression**

During the entire memorial, NO idle text bubbles should appear on screen. Check server logs for `[IDLE] Suppressed idle send — memorial active` messages.

- [ ] **Step 6: Verify F11 fullscreen**

Press F11 during normal operation. Verify it enters fullscreen without errors. Press F11 again to exit.

- [ ] **Step 7: Commit final integration verification**

```bash
git add -A
git commit -m "test: verified memorial flow + fullscreen + VIP injection

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
git push
```

---

## Task Dependencies

```
Task 1 (SFX generation) ──────────────────────┐
Task 2 (Audio music support) ─────────────────┤
Task 3 (Display overlay rewrite) ─────────────┤
Task 5 (Server orchestration) ────────────────┼──► Task 8 (Integration test)
Task 4 (Client suppression + music handling) ──┤
Task 6 (Fullscreen fix) ──────────────────────┤
Task 7 (VIP context injection) ───────────────┘
```

Tasks 1-7 are **independent** and can be executed in parallel. Task 8 depends on ALL of them.
