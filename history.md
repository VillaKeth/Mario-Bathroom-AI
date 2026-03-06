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

## 2026-03-05 — Wacky Remix Lab from Local mario_assets
- Added `client/generate_wacky_remixes.py` to apply 10 visual effects per source sheet (`neon_pop`, `rgb_ghost`, `sine_wave`, `pixel_crunch`, `hot_duotone`, `inverted_scanline`, `kaleido_mirror`, `solar_flare`, `edge_glow`, `gameboy_mutation`).
- Generated `assets_wacky_lab/` with remixes for 3 local source sheets from `mario_assets/`, plus `index.html`, `manifest.txt`, and preview image.
- This flow edits user-provided local assets directly (no external scraping), enabling fast experimentation with aggressive style remixes.

## 2026-03-05 — 3D Mario Assets: 100 Iterations × 24 Sources
- Created `client/generate_3d_mario_assets.py` — comprehensive image processing pipeline that:
  - Loads all 24 images from `mario_assets/` (including user's preferred `Mario_New_Super_Mario_Bros_U_Deluxe.webp` and `zap9gpu6vj9e1.png`)
  - Applies smart background removal (corner-sampling + tolerance), crops to content, fits to 400×500 target
  - Runs 100 unique visual effects per source: color shifts (sepia, ice, fire, golden, purple), hue rotations, art styles (oil paint, watercolor, comic, sketch, pop art), distortions (glitch, wave, swirl), pixelation levels (NES 8-bit, SNES 16-bit, N64), character swaps (Wario/Luigi/Waluigi colors), power-ups (star power, fire mario, ice mario, metal, shadow, ghost), backgrounds, outlines, and composited combos
  - Total output: 2,400 PNG images in `mario_3d_assets/` with interactive HTML gallery and manifest
- Bug fixes during development: PIL HSV conversion requires RGB intermediary + `putalpha()` needs PIL Image not numpy array; numpy glitch effect needed deterministic slice bounds

## 2026-03-05 — Expressive Mario Poses (Photoshopped)
- **What**: 47 unique photoshopped poses from NSMBU Deluxe Mario render — actual face/body manipulation, not just color filters
- **Script**: `client/generate_expressive_mario.py`
- **Output**: `mario_3d_assets/expressive/` with index.html gallery
- **Categories**: Speech & Communication (talking, waving, greeting, farewell, listening, singing), Positive Emotions (idle, happy, excited, laughing, love, proud, victorious), Negative Emotions (sad, crying, angry, furious, embarrassed, nervous, scared, tired), Thinking & Processing (thinking, confused, mischievous, determined, processing), Sleep & Rest (sleepy, sleeping), Movement & Action (jumping, dancing, eating), Power-Ups (star, fire flower, mega/mini mushroom)
- **Techniques**: Face region manipulation (eye closing/widening, mouth opening), body tilting/squashing/stretching, color tints per emotion, overlay elements (speech bubbles, thought clouds, Zzz, hearts, tears, anger veins, stars, sparkles, music notes, motion lines, sweat drops, question marks, exclamation marks, fire/ice effects)

## 2026-03-05 — Expressive Mario V2: Actual Body Manipulation
- **Why**: User criticized V1 poses — "you just tilted the PNG" — wanted ACTUAL arm/body part movement
- **What**: 74 unique poses with real body part segmentation and manipulation
- **Script**: `client/generate_expressive_mario_v2.py`
- **Output**: `mario_3d_assets/expressive_v2/` with index.html gallery
- **Key innovation**: `MarioBody` class segments Mario into manipulable parts using color masks:
  - Red mask (r>150, g<80, b<80): hat, shirt/sleeves
  - Blue mask (b>120, r<100, g<100): overalls
  - White mask (r>200, g>200, b>200): gloves, eye whites
  - Skin mask (r>180, g∈[130,200], b∈[80,160]): face, ears
  - Dark mask (r<60, g<60, b<60): mustache, outlines
  - Brown mask (r∈[100,180], g∈[40,110], b<80): shoes, hair
- **Arm extraction**: For each row, finds rightmost blue overalls pixel as body edge, classifies red/white pixels beyond as arm. Arm rotated around shoulder pivot and composited back.
- **Face painting**: `FacePainter` class draws different eye styles (closed, half, wide, angry, sad, wink, looking directions, heart, sparkle, spiral) and mouth styles (open, wide_open, smile, big_smile, frown, tongue_out, gritted, whistle) directly on face region
- **Categories (74 poses)**: Neutral (6), Greeting (7), Speech (8), Positive (9), Negative (10), Thinking (10), Sleep (3), Movement (9), Action (5), Power-Up (7)
- **Bug fix**: `np.random.choice()` fails with lists of tuples ("a must be 1-dimensional") — replaced with `random.choice()`
- **Analysis tool**: `client/analyze_mario.py` mapped precise body part coordinates on the 400×500 prepared image to inform segmentation regions

## 2026-03-05 — AI-Generated 3D Mario Poses (SubNP Magic Model)
- **Why**: V2 body manipulation still looked janky — user wanted proper AI-generated renders
- **What**: 74 AI-generated 3D figurine-style Mario poses using SubNP's free API
- **Script**: `client/generate_ai_poses.py`
- **Output**: `mario_3d_assets/ai_poses/` (10 subdirectories, 74 PNGs, interactive gallery)
- **API discovery**: Tested 5+ free APIs — Pollinations (HTTP 530/401), HuggingFace (deprecated/401), Together AI (401), Puter.js (login wall). Only **SubNP "magic" model** worked (no auth needed).
- **SubNP API**: `POST https://subnp.com/api/free/generate`, SSE streaming response, `magic` model (MagicStudio provider). Models tested: turbo/flux/flux-schnell all failed.
- **Prompt engineering**: All prompts include "3D rendered figurine style, clean gray studio background, full body shot, highly detailed, Nintendo official art quality, soft studio lighting" suffix for consistent results.
- **Reliability**: Connection drops after ~35-40 consecutive requests. Solved with 5s delay between requests, 5 retries with exponential backoff, and resume logic (skip files >1000 bytes).
- **Quality**: Excellent — correct Mario outfit (red cap with M, blue overalls, white gloves, brown shoes, mustache) with distinct expressive poses per emotion.
- **Limitation**: Gray studio backgrounds (not transparent) — will need background removal for Pygame overlay use.

## 2026-03-05 — XTTS v2 Mario Voice Cloning
- **Why**: Edge TTS (`en-US-GuyNeural` + pitch shift) sounded nothing like Mario — just a pitched-up American male voice
- **Solution**: Coqui XTTS v2 voice cloning with Charles Martinet reference audio
- **Reference audio**: 40.5s concatenated WAV from `eros71-dev/mario-voice-dataset` (MPL-2.0 license, ~100 clips from Nintendo press events). Key clips: "It's-a me Mario!", long sentences, enthusiastic delivery.
- **Compatibility fixes**:
  1. PyTorch 2.6+ changed `torch.load()` default to `weights_only=True` — monkey-patched to `False`
  2. torchaudio 2.x defaults to torchcodec backend which requires FFmpeg DLLs — replaced `torchaudio.load()` entirely with soundfile-based loader
  3. transformers 5.x removed `BeamSearchScorer` — downgraded to 4.44.2
- **Performance**: On Quadro P1000 (4GB VRAM), XTTS v2 achieves ~1.1-1.8x real-time factor (4.6s to generate 3.7s audio, 27.8s for 13.8s audio). Short sentences are near-real-time.
- **Architecture**: XTTS v2 is primary TTS, Edge TTS is automatic fallback. Model loads at server startup (~19s).
- **Packages**: TTS 0.22.0, transformers 4.44.2, numpy 1.26.4 (TTS requires <2)
- **Background removal**: Used `rembg` library (U²-Net AI model) to remove gray studio backgrounds from all 74 AI poses → transparent PNGs in `mario_3d_assets/ai_poses_transparent/`
- **Script**: `client/remove_backgrounds.py` — processes all 10 category subdirectories, skip-on-resume capability
- **Display update**: Rewrote `mario_display.py` sprite system to support AI poses:
  - `_load_ai_poses()` loads from category subdirectories, scales from 1024×1024 to 250×250 display size
  - `STATE_SPRITE_MAP` maps states (idle, talking, thinking, etc.) to AI pose paths
  - `EMOTION_SPRITE_MAP` expanded to 17 emotions (happy, excited, surprised, confused, annoyed, sleepy, mischievous, laughing, sad, angry, nervous, scared, love, proud, embarrassed, disgusted, determined)
  - `_get_ai_sprite_key()` / `_get_legacy_sprite_key()` dual-path approach: AI poses preferred, pixel art fallback
  - Talking alternates between `speech/talking` and `speech/talking_excited`; dancing alternates between `movement/dancing_1` and `movement/dancing_2`
- **Bug fix**: `--no-camera` flag set `self.presence = None` but `start()` and `stop()` didn't guard against None → `AttributeError`
- **End-to-end verified**: Server (STT + TTS + LLM + speaker ID) + Client (74 AI poses + WebSocket + audio playback) all working together
