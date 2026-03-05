# History — Mario AI Design Decisions

## 2026-03-04 — Initial Architecture
- **Decision**: Client-server architecture (MacBook client + friend's GPU PC as server)
- **Reason**: 2015 MacBook can't run AI models locally. All heavy processing offloaded to GPU server via WebSocket.
- **Tech choices**:
  - faster-whisper for STT (best open-source, GPU accelerated)
  - Ollama + llama3 for LLM (free, easy setup, good quality)
  - Piper TTS for voice synthesis (fast, local, free)
  - resemblyzer for speaker ID (simple voice embeddings)
  - Pygame for Mario display (lightweight, works on old MacBook)
  - OpenCV for presence detection (background subtraction)

## 2026-03-04 — Mario Personality Design
- Mario knows he's in a bathroom at a party
- Short responses (1-3 sentences) — people aren't having long conversations
- Lighthearted bathroom humor, nothing crude
- Remembers past visitors and references previous conversations
- Pitch-shifted Piper TTS for Mario-like voice quality

## 2026-03-04 — Switched TTS from Piper to Edge-TTS
- **Reason**: Piper's piper-phonemize dependency has no Windows/Python 3.11 wheel
- **Solution**: edge-tts (Microsoft's free, no-API-key TTS). Must use >=7.2.7 (older versions 403)
- Pitch shifting done post-synthesis via scipy resampling (+3 semitones)

## 2026-03-04 — Neuro-sama Feature Parity
- Added emotion/mood system (10 states), party stats, content safety, idle behavior, sound effects
- Emotions affect TTS rate/pitch and Mario sprite animations (eyes, mouth, particles)
- Idle system makes Mario hum/joke/sing when nobody's talking
- Safety filter blocks inappropriate content with Mario-style redirects

## 2026-03-04 — Bug Fixes (TTS + Speaker ID)
- **TTS bug**: `synthesize()` accepted `rate`/`pitch` params but never passed them to `_synthesize_async()` — caused `NameError`. Fixed by threading params through all wrapper functions.
- **Speaker ID bug**: resemblyzer uses deprecated `np.bool`. Fixed with monkey-patch before import. Silence audio causes divide-by-zero warnings in resemblyzer (harmless — gracefully returns "too short").
- **E2E test**: All 5 steps pass (greeting, enter, audio, exit, health check)

## 2026-03-04 — Pixel Art Sprite System
- **Decision**: Replaced MS Paint-style shape drawing with proper NES-style pixel art sprites
- **Implementation**: Sprites defined as 16×23 pixel grids with NES color palette, rendered at 8× scale (128×184px)
- **Frames**: 8 sprite frames — idle, talk, talk2, walk1, walk2, wave, jump, think
- **Generator**: `client/generate_sprites.py` creates all PNGs from pixel data
- **Customizable**: Users can swap in their own PNGs in `client/assets/mario/` with matching filenames
- **Display**: `mario_display.py` loads PNGs at init, switches frames based on state (talking → talk/talk2 alternation, greeting → wave, thinking → think)

## 2026-03-04 — Visual Overhaul & Sprite Fixes
- **Sprite anatomy fixes**: Relaxed eyes (kk pupils), clear mustache/mouth separation with nose shadow, arms extend from body not head (wave/jump/think)
- **4 new reaction sprites**: laugh, surprise, sleep, dance (12 total frames now)
- **Bathroom background**: Tiled walls, reflective mirror with shine, sink with faucet, toilet with tank/handle/seat, toilet paper roll, darker floor tiles
- **Walk transitions**: Ease-in-out walk-in from left on enter, walk-out to right on exit, uses walk1/walk2 sprites
- **Speech bubble styles**: Normal (white rounded), shout (spiky yellow/red for ! or CAPS), question (blue tint for ?), whisper (gray with dot trail for parens/asterisks)
- **Typewriter effect**: Characters appear one-by-one in speech bubble with blinking cursor
- **Keyboard input**: TAB toggles text input mode — type messages to Mario without microphone
- **Party mode**: F5 toggles disco ball with rotating light beams, falling confetti particles with gravity, color-cycling background overlay
- **Emotion→sprite mapping**: excited→dance, surprised→surprise, sleepy→sleep, laughing→laugh
- **Server text_input handler**: Keyboard-typed text goes through same pipeline as voice (safety→LLM→TTS→response)

## 2026-03-05 — Boutique Sprite Iterations (10-pass manual rebuild)
- Added `client/generate_boutique_sprites.py` to generate 10 deliberate full sprite-set iterations.
- Output folder is `assets_boutique/` with `iteration_01...iteration_10`, each containing all 12 Mario sprites plus `style_notes.txt`.
- Every iteration rebuilds core facial/costume rows: hat silhouette, overalls, mustache, and large blue eyes.
- Added `assets_boutique/index.html` and `assets_boutique/manifest.txt` for quick review and selection.

## 2026-03-05 — Fresh From-Scratch Sprite Batch
- Added `client/generate_boutique_fresh.py` to generate a completely new 10-iteration set without reusing prior sprite grids.
- Output folder is `assets_boutique_fresh/` with `iteration_01...iteration_10`, each containing 12 state sprites plus `style_notes.txt`.
- Sprite construction is procedural (shape-based): hat, face, large blue eyes, mustache, overalls, limbs, and per-state poses (walk/wave/jump/think/laugh/surprise/sleep/dance).
- Added `assets_boutique_fresh/index.html` and `assets_boutique_fresh/manifest.txt` for quick side-by-side review.

## 2026-03-05 — Reference Link Compliance Gate
- Added `client/audit_reference_links.py` to parse a link list and block sources without explicit permissive license markers.
- Audited `C:\Users\Vketh\Desktop\Here are all the links from the 2D.txt` and produced `assets_boutique_fresh/link_license_report.txt`.
- Current audit result: `approved=0`, `blocked=32`, `skipped=1`; no provided links were safe for direct ingestion under compliance rules.
