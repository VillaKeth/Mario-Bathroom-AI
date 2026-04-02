# History — Mario AI Design Decisions

## 2026-04-02 — v3.7-v3.8 Social Intelligence Sprint (overnight, 5:45-6:45 AM)
- **Goal**: Make gossip system create real social dynamics between guests
- **Changes (v3.7)**:
  - Alliance detection: guests who agree on topics form friendships (not just rivalries)
  - Trending topics: when 3+ guests mention same topic, Mario surfaces it as party hot news
  - Party recap for newcomers: exciting FOMO teaser combining trending, rivalries, alliances, drama
  - Return visit intelligence: gossip-based dossier for returning guests
  - Command discovery tests: 7 new tests
- **Changes (v3.8)**:
  - Idle gossip recap: when alone, Mario reflects on party social dynamics out loud
  - Fixed idle gossip wiring: `if not action` condition was unreachable
  - 619 total tests (was 582 at v3.6)
- **Rationale**: The gossip system had good data collection but only rivalries, no friendships or trends. Alliances + trending create a rich social web. The recap gives newcomers FOMO context. Return visit intel makes Mario genuinely remember each guest's social standing.

## 2026-04-02 — v3.6 Conversation Quality (overnight, 4:50-5:45 AM)
- **Goal**: Fix conversation amnesia, add emotional depth, help guests discover features
- **Changes**:
  - Conversation summarization: zero-latency extractive summarizer preserves old context
  - Idle loneliness arc: 3-tier mood progression when Mario is alone (24 unique messages)
  - Command discovery hints: 15 natural feature suggestions during conversation
  - 582 total tests
- **Rationale**: With RECENT_RAW_MESSAGES=8, older context was silently dropped. Summary preserves topics + proper nouns. Loneliness arc makes Mario feel alive when alone. Discovery hints teach guests about 40+ features without being pushy.

## 2026-04-02 — v3.4 Robustness Sprint (overnight session)
- **Goal**: Make Mario bulletproof for Jacob's birthday party on Threadripper Pro
- **Changes**:
  - Concurrent game guard — blocks starting new game while one active
  - Per-guest game rotation — prevents cross-guest game history pollution
  - Night progression persistence across server restarts
  - 11 IndexError guards on game data pool access
  - Idle/text race condition fix — _handle_text_input now sets _user_request_active
  - _idle_send_if_safe() helper — rechecks guard before sending idle messages
  - Greeting outer timeout (60s) with emergency fallback
  - Reconnect state reset — clears speaker identity on WebSocket reconnect
  - Extracted _do_greeting() async helper (~180 lines)
  - 21 coverage gap tests (gossip pruning, idle behavior)
  - 14 edge case tests (night progression, concurrent game guard)
  - Total: 538 tests passing
- **Rationale**: Party runs 6+ hours on friend's Threadripper. Every edge case matters when 50+ guests cycle through. Race conditions, stale state, and game pool exhaustion are all real risks at scale.

## 2026-04-01 — Party Resilience: Error Recovery & Health Tracking
- **Goal**: Mario should NEVER go silent during a party
- **Changes**:
  - Silent `except: pass` blocks in keepalive/maintenance now log at DEBUG level
  - Ollama health tracking: 3 consecutive failed pings marks it unhealthy with ERROR log
  - LLM fallback responses now log WARNING for diagnostics
  - Emergency silence WAV fallback in tts_router when ALL TTS engines fail (1.5s silent PCM)
  - Client displays red connection status overlay via `set_connection_status()` method
- **Rationale**: During a party, silent failures are the worst — they look like crashes. Logging + emergency fallbacks ensure the bot always responds, even if degraded.

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

## 2026-03-06 — Game Logic Extraction Refactor
- **Decision**: Extracted all interactive game code from `server/main.py` into `server/game_handlers.py`
- **Reason**: main.py grew to ~1880 lines; game content data (lists, dicts) and game logic accounted for ~387 lines and was logically independent of the server WebSocket/LLM/TTS machinery
- **API**: Two functions — `start_game(game_name, state, config, emotion_sys)` and `handle_game_input(lower, state, emotion_sys)`. State dict passed by reference so mutations propagate to main.py's `state_current`.
- **Games moved**: Simon Says, 20 Questions, Truth or Dare, Riddles, Word Chain, Karaoke, Rapid Fire Quiz
- **Data moved**: SIMON_ACTIONS, TWENTY_Q_THINGS, RIDDLES, STARTER_WORDS, KARAOKE_SONGS, RAPID_FIRE_QUESTIONS, TRUTH_QUESTIONS, DARES
- **Result**: main.py reduced to ~1495 lines; game_handlers.py is 421 lines

## 2026-03-XX — Extracted command handlers into command_handlers.py
- **Decision**: Move `_handle_special_commands` logic and all its inline content data from main.py into server/command_handlers.py
- **Reason**: main.py still ~1760 lines; the special command handler contained ~600 lines of content data (easter eggs, secrets, dares, nicknames, fortunes, roasts, etc.) and branching logic that was independent of WebSocket/LLM/TTS infrastructure
- **API**: One function — `handle_special_commands(transcript, state, game_config, emotion_system, idle_behavior, party_stats, memory_module)`. Synchronous (no async). Wrapper in main.py remains async for callers.
- **Data moved**: EASTER_EGGS, SECRETS, DARES, NICKNAMES, FORTUNES, MOOD_RESPONSES, TWISTERS, STORIES, PICKUP_LINES, BATHROOM_TIPS, RAPS, MOTIVATIONS, CONFESSIONS, ROASTS
- **Result**: main.py reduced to ~1150 lines; command_handlers.py is 683 lines

## 2026-03-12 — Data-Driven Pronunciation Fixes Break 78% Ceiling
- **Decision**: Replace character names with words the model CAN say, instead of phonetic spellings
- **Reason**: 220-round ralph loop + 30-variant phonetic A/B testing proved GPT-SoVITS literally cannot pronounce any variant of "Bowser" (Bowzur, Bowzah, Bowzer, Browser, Bao-zer — ALL produce gibberish). Same for Goomba/Koopa.
- **Key insight**: The model was fine-tuned on Mario audio which has strong game-word priors. It HALLUCINATES "Bowser" and other game words even when they're not in the input. But it cannot PRODUCE these words on command.
- **Solution**: Semantic substitution instead of phonetic:
  - Bowser → "the bad guy" (+12.9% on Bowser phrases: 62.4% → 75.3%)
  - Goomba → "bad mushroom" (+13.1%: 66.1% → 79.2%)
  - Koopa → "Cooper" (pronounceable real word)
  - Toad → "Todd" (natural tendency, +0.5%)
  - "quoted" → "noted" (avoids garbled "It's beach" outputs)
- **Also fixed**: Conflicting double-replacements (Bowser→Bowzur then bowser→Bowzer were overwriting each other)
- **Result**: R231 hit 79.4% acceptable (28G+22O/63) — first time ever breaking the 78% ceiling
- **Prior best**: 78.1% (R67) out of 220 rounds; avg was 65.3%

## 2026-03-16 — Neuro-sama Party Overhaul: Guest Interaction & Chaos
- **Decision**: Major personality overhaul to make Mario more like Neuro-sama — chaotic, gossipy, emotionally volatile, socially dynamic
- **Reason**: User wanted Mario to interact with party guests, reference previous visitors, create social dynamics, and be more unpredictable/entertaining
- **Key changes**:
  1. **System prompt rewrite**: Mario is now chaotic, opinionated, gossipy, dramatically emotional, self-aware about being a bathroom guardian. Strong takes on everything, mood swings, teasing, genuine curiosity.
  2. **Party Gossip System** (`server/party_gossip.py`): New module that tracks interesting things each guest says/does, then feeds gossip about previous visitors into LLM context for new visitors. Creates cross-visitor social dynamics.
     - `analyze_for_gossip()`: Detects gossip-worthy content (opinions, claims, preferences, reactions) via keyword matching
     - `get_gossip_for_guest()`: Returns formatted gossip hints about OTHER guests, filtered to not gossip about the current speaker
     - `get_comparison_hint()`: Detects when current guest mentions same topics as previous guests
     - `assign_title()`: Gives each guest a fun title ("The Magnificent Bathroom Visitor", "Defender of Hand Soap")
     - `add_dramatic_moment()` / `get_party_narrative_hint()`: Running party storyline
  3. **Chaos System**: 8% chance per response of random chaos hint — existential crises, sudden topic shifts, pretending Luigi is behind them, forgetting identity momentarily
  4. **Enhanced idle**: 20 new chaotic idle mumbles — arguing with mirror, conspiracy theories about coins, existential plumber crises, Luigi apologies
  5. **Gossip in greetings**: 50% chance to gossip about previous visitors when greeting new ones; 30% chance to use guest's fun title
  6. **Gossip in idle**: 20% chance of gossip-based idle when alone (reminiscing about guests)
  7. **Enhanced greeting prompts**: All 16 prompts rewritten for maximum drama, chaos, and guest interaction energy
- **Architecture**: PartyGossip is in-memory (resets on server restart) — party-scoped by design, no persistence needed

## 2026-03-16 — Ralph Loop Round 2: Robustness & Polish
- **Decision**: Deep codebase analysis followed by targeted improvements across 4 files
- **Key changes**:
  1. **Idle loop auto-recovery**: Error counter now resets after 5min cooldown instead of accumulating forever. Circuit breaker at 10 consecutive errors pauses idle until next visitor.
  2. **LLM timeout fallback**: Wrapped LLM call in `asyncio.wait_for`. On timeout, returns funny canned responses ("My brain went on vacation!") instead of dead silence. Sets emotion to CONFUSED.
  3. **Gossip memory management**: Capped gossip log at 500 entries with 4-hour time decay. Prevents unbounded memory growth during long parties.
  4. **Speech-derived titles**: Guests get personalized titles based on detected speech traits (foodie → "Grand Chef of Flavor Town", gamer → "Boss Battle Survivor"). 12 trait categories with 3-4 titles each.
  5. **Title evolution**: Titles update as guest reveals more personality traits during conversation.
  6. **5 new gossip categories**: food, gaming, fear, dream, embarrassing — richer cross-visitor references.
  7. **Emotion-based particle fallback**: If no keyword triggers particles, emotion state provides fallback (EXCITED→stars, LOVING→hearts, FRUSTRATED→fire).
  8. **Cheer-up system**: If guest is negative (worried/frustrated/bored) for 2+ minutes, Mario actively tries to cheer them up with specific strategies per emotion.
  9. **Prompt injection hardening**: Strict whitelist (alphanumeric + space/hyphen/apostrophe), 20 char cap on names, more blocked injection words, control char stripping.
  10. **Expanded chaos hints**: 16 total (from 8) — mind reading, countdowns, phone calls from Peach, hand-washing concerns, third-person speech.
- **Bug prevention**: Smooth emotion transitions tracked via `_previous_emotion` and `_transition_start` for future interpolation.
