# Mario AI Party Bot - TODO

## Critical LLM Fixes — DONE ✅
- [x] Fix ImportError in llm.py that silently discarded ALL LLM responses
- [x] Fix Easter egg interception: only trigger on short messages (≤5 words)
- [x] Fix substring matching: "embarrassing" no longer matches "sing" command
- [x] Slim system prompt from ~2700 to ~960 chars (save 435 tokens)
- [x] Add system message trimming (keep first 5 secondary hints)
- [x] Increase LLM timeout 30s→45s, router fallback 15s→25s
- [x] Relax repeat detection 70%→80%, reduce buffer 20→10
- [x] Add always-on LLM context logging

## LLM Response Quality Fixes — DONE ✅
- [x] Fix plumber-specific humor intercepting "Tell me a joke about plumbing" (word count guard)
- [x] Add `was_fallback` flag to LLM return to prevent canned responses polluting history
- [x] Fix conversation history: don't store non-LLM interactions (canned/special commands)
- [x] Remove orphaned user messages from history when response was non-LLM
- [x] Add random seed to Ollama API for response diversity
- [x] Embed user question into CTX 00 (main system prompt) for maximum attention weight
- [x] Add randomized approach hints for diverse response styles
- [x] Reduce _MAX_SYS_HINTS from 5→3 to reduce competing instructions
- [x] Reduce RECENT_RAW_MESSAGES from 8→4 to prevent pattern-copying
- [x] Improve on-topic rate: achieved 20/20 on-topic, 20/20 unique in stress test
- [x] Add word count guards to ALL game triggers (trivia≤4, dare≤5, RPS≤5, hot takes≤4, etc.)
- [x] Reduce Easter egg threshold from ≤5 to ≤3 words
- [x] Add mood handler word guard ≤6 words
- [x] Fix trivia routing: remove \btrivia\b from fun fact handler
- [x] Test all response quality with 20-prompt stress test: PERFECT 20/20
- [x] Test all 13 games: PERFECT 13/13 start correctly
- [x] Fix name detection false positive: "it is pasta" no longer triggers name learning (≤8 word guard)
- [x] Fix hangman trigger: "Tell me about hangman" now goes to LLM (≤3 word guard)
- [x] Add word count guards to ALL remaining game triggers (simon≤4, 20Q≤4, riddle≤4, etc.)
- [x] Fix idle message race: set _user_request_active immediately in text_input handler
- [x] Add keyword-based emotion inference fallback for 8B model (no more all-neutral)
- [x] Test full game playthroughs: trivia, RPS, riddle, hangman, word chain, simon says all complete
- [x] Test sentiment mood meter: emotions now vary (curious, loving, confused, etc.)
- [x] Fix greeting collision: first prompt after connect sometimes gets greeting response
- [x] Fix remaining idle message leakage (3-layer cooldown system: post-response 8s, post-input 5s, conversation-aware spacing 15-25s)
- [x] Add POST /admin/simulate_text endpoint for testing through Pygame client
- [x] Add [EMOTION_CHANGE] debug logging in mario_display.py
- [x] Fix name parser false positive: "I'm feeling" no longer triggers name="Feeling" (expanded stop words)
- [x] Verify emotion transitions in Pygame client: 6+ transitions across 5 emotions confirmed
- [x] Verify zero idle leaks during active conversation (was 2-4 per 20 prompts)

## Current Focus
- [x] Quick greeting handlers for "hi", "hey", "yo" etc. (instant response, no LLM wait)
- [x] Quick laugh handlers for "lol", "haha" etc.
- [x] Relaxed word count guards: joke/secret/story handlers now ≤7 words (was ≤5)
- [x] Verified idle messages fire during silence (~30s intervals)
- [x] Verified 19+ emotion transitions in Pygame client on Desktop 2
- [x] Verified zero idle leaks during rapid conversation (8 messages, 0 leaks)
- [x] Added thank you, yes/no, goodbye, stop game response handlers
- [x] Expanded greeting set (sup dude, hey bro, hi there, etc.)
- [x] Dare handler catches "can I get a dare" (word count ≤7)
- [x] Fix idle rapid-fire leak: 3-8s alone sleep → 8-15s, added 25s min interval between idle msgs
- [x] Verified idle intervals: 20s, 58s, 29s gaps (was 4-6s before fix)
- [x] Confirmed TTS uses RVC on ALL paths (Edge TTS fallback still gets voice conversion)
- [x] Confirmed 33 Edge TTS fallbacks were all during precache startup (not user-facing)
- [x] Run extended stress tests (10-msg batch) — verified routing, interruption, and responses
- [x] Test multi-sentence and very long user messages — LLM handles correctly with streaming
- [x] Fix simulate_text endpoint missing self-interruption (now cancels old task like real WS input)
- [x] Verified self-interruption: rapid-fire messages properly cancel stale LLM responses
- [x] Add "what games" / "list games" / "which games" handler (instant game list instead of LLM)
- [x] Test idle suppression during memorial events — zero idle messages during ceremony
- [x] Improve LLM empathetic response quality (sad messages get greeting responses)
- [x] Verify idle messages don't get cut off mid-sentence
- [x] Add LLM response staleness detection (discard if game started during inference)
- [x] Fix name parsing for "im" without apostrophe (e.g., "hey im jake" now learns name)
- [x] Fix truth-or-dare routing to correct game (was starting bathroom_dare)
- [x] Extend laugh handler with regex for extended patterns (hahahaha, looool, emoji)
- [ ] Add party soundtrack/ambient noise integration
- [ ] Add voice command for volume control
- [ ] Implement guest rotation tracking (who hasn't spoken recently)

## Installation Overhaul (Post-Party Fix) — VERIFIED ✅
- [x] Add torchaudio to server/requirements.txt (was missing, caused server crash)
- [x] Make face_recognition and ultralytics optional in client/requirements.txt
- [x] Fix start_server.bat to activate venv before running
- [x] Fix start_server.sh to activate venv before running
- [x] Fix start_client.bat to activate venv before running
- [x] Fix start_client.sh to activate venv before running
- [x] Fix setup.bat to install PyTorch with CUDA properly (separate step before requirements.txt)
- [x] Fix setup.sh to install PyTorch with CUDA properly
- [x] Make tts.py handle missing torch/torchaudio gracefully (fallback to edge-tts)
- [x] Make speaker_id.py handle missing resemblyzer gracefully
- [x] Make stt.py handle missing faster-whisper gracefully (text chat still works)
- [x] Rewrite README.md for dead-simple fresh-computer setup
- [x] Add psutil and colorama to server requirements for better hardware detection and colored output
- [x] Fix 'from server.X' import errors in main.py and party_report.py (5 broken imports)
- [x] Test full fresh install flow: created fresh venv, installed all deps, server booted successfully
- [x] Verified all 27 server module imports pass in fresh venv
- [x] Fix _detect_particle_effect NameError (was _detect_keyword_particles)
- [x] FULL END-TO-END FRESH INSTALL TEST PASSED: venv deleted → recreated → all deps installed → server boots → Mario responds with audio

## Web Chat Removal & Pygame Migration
- [x] Delete web/ directory (mario_chat.html, dashboard.html, party_host.html, report.html, leaderboard.html, sfx_preview.html, tts_cache_preview.html, tts_test.html)
- [x] Remove HTML-serving routes from server (main.py /chat, /tts_test, /tts_cache_preview, /leaderboard_page; dashboard.py /dashboard, /party-host, /report)
- [x] Add game quick-trigger keys 1-8 to pygame client (Trivia, RPS, T or D, Simon, 20Q, Joke, Song, Dance)
- [x] Add admin slash commands to pygame client (/announce, /emotion, /memorial, /stopgame, /reload, /reset, /pause, /sovits, /health, /help)
- [x] Add server health overlay (F4) to pygame client
- [x] Update keyboard hints in display to show new controls
- [x] Update README to remove all browser chat references, add pygame controls docs
- [x] Fix admin commands: /announce and /emotion now send JSON body (was query params), /reload hits /api/reload (was /config/reload)
- [x] Fix /health display using correct API field names (uptime_seconds, tts, llm, memory_mb)

## Pose Image Regeneration
- [x] Audit all 122 Mario poses for quality issues (buff hulk, grey hat, amiibo pedestals, artifacts)
- [x] Find working image generation API (SubNP is dead → switched to Pollinations.ai)
- [x] Update regenerate_poses.py with Pollinations.ai backend + --worst-only/--category/--dry-run flags
- [x] Regenerate 15 worst-quality poses (action/dabbing, movement/sliding, negative/angry, negative/furious, negative/scared, negative/disgusted, neutral/idle, positive/happy, positive/love, powerup/mega_mario, powerup/mini_mario, sleep/sleeping, sleep/yawning, thinking/confused, thinking/dizzy)
- [x] Visually verify all 15 regenerated poses look correct (clean backgrounds, correct Mario colors)
- [ ] Full regeneration of all 122 poses running (with rate-limit backoff)
- [x] Add memorial/honor pose to regeneration (was skipped, now included)

## Shot Event System (Config-Driven)
- [x] Move hardcoded shot events from Python to JSON config (server/data/shot_events.json)
- [x] Update shot_events.py to load events from JSON at startup
- [x] Create docs/EVENTS.md with template, field reference, and examples
- [x] Add /event <name> and /events admin commands to pygame client
- [x] Update /memorial command to accept optional event name
- [x] Add rate-limit backoff (HTTP 402) to regenerate_poses.py
- [x] Test shot event end-to-end with pygame client connected
- [x] Test shot event end-to-end: deltarune triggered, all phases ran, 0 errors, reset works
- [x] Fix event text overlay: add show_memorial() call so Mario's speech text appears on screen during events
- [x] Fix countdown pronunciation: simplify "TEN-a!" to "Ten!" for cleaner TTS output
- [x] Fix countdown parser: use flexible lowercase matching for new format
- [x] Fix idle lines during events: all send_response calls in idle loop now use _idle_send_if_safe
- [x] Fix idle race condition: set memorial_active BEFORE creating asyncio task (not inside task)
- [x] Auto-detect MP3 duration from file using mutagen (deltarune 90→185s, birthday 30→186s)
- [x] Make music phase tone-aware: fun="Take a Shot!", celebratory="Cheers!", solemn="In Loving Memory"
- [x] Increase announcement/toast phase delays from 2s to proportional (words/2.5 + 2s, min 5s)
- [x] E2E test: deltarune event — all 6 phases, 0 errors, 185s music duration correct
- [x] E2E test: birthday_boy event — all 7 phases (incl silence), 0 errors, 186s music correct
- [x] Fix double subtitles: remove captions.set_text from regular speech and events (speech bubble + overlay handle display)
- [x] Fix memorial_active flag stuck forever: add recovery phase flag clear (was only on 'fadeout' phase which doesn't exist)
- [x] E2E test: lisa_webb_memorial event — all 7 phases, 0 suppressed idle lines, flag cleared 18s after recovery, idle resumed normally
- [x] Add 100 fun party events (103 total) across 7 categories: Gaming, Movies/TV, Memes, Party Games, Music Artists, Random Fun, Sports, Holidays, Quirky
- [x] E2E batch test: 8 events (rick_roll, among_us, taylor_swift, waterfall, touchdown, shrek, mystery_shot, star_wars) — all completed, 0 errors, all flags cleared
- [x] Stress test: 100/103 events fired sequentially, 0 errors, 100/100 flags cleared, 32 idle lines suppressed (client safety net)
- [x] Edge case tests: re-trigger already-fired (correctly rejected), nonexistent event (not_found), concurrent triggers (second blocked)
- [x] Server stability: 0 errors, 0 idle errors after 100 events, memory stable at 943MB, GPU 54°C
- [x] Regenerate ALL 122 Mario poses via Pollinations.ai — 122/122 succeeded, 0 failures
- [x] Full overnight verification complete — ALL SYSTEMS PERFECT
- [x] Swap Drake → removed (Kendrick already exists), Taylor Swift → Sabrina Carpenter
- [x] Create docs/MUSIC_GUIDE.md with recommended songs for all 102 events
- [x] Create scripts/add_music_to_events.py for auto-wiring MP3s to events
- [x] Add MP3 music files for all 99 events without music
- [x] Downloaded 99/99 MP3 music files for all events via yt-dlp
- [x] Wired all 102 events with music phases and file paths via add_music_to_events.py
- [x] Swap Kanye "Stronger" → "Dark Fantasy" (Can We Get Much Higher / MBDTF)
- [x] Add "Angel With a Shotgun" event (The Cab)
- [x] Add "Tokyo Ghoul - Unravel" event (solemn tone, Ken Kaneki themed with custom pose)
- [x] Fix countdown overlay not clearing when music phase starts (bug: "1" stuck on screen)
- [x] All 104 events now have music + correct phase transitions
- [x] Fix event display: proper titles per event (not generic "In Loving Memory"), no Lisa Webb photo fallback, subtitles in music phase
- [x] Generate topical images for all 100 events via Pollinations.ai (800x450 themed PNGs, 0 failures)
- [x] Auto-update shot_events.json with image_file paths for all 100 events
- [x] Commit and push all 100 event images + updated JSON (commit be28ef0)
- [x] Replace all AI-generated event images with real web-sourced images from Bing
- [x] Created download_event_images.py (icrawler + BingImageCrawler) and retry_images.py
- [x] 102/104 events now have real images (2 person-specific events keep custom photos)
- [x] Commit and push real images (commit 734e3b2)
- [x] Fix 33 wrong Bing images via Pollinations.ai (Bing word-matching was broken for multi-word queries)
- [x] Visual audit: all 102 event images verified correct (deltarune kept as user-preferred AI version)
- [x] Clean up temp scripts and gallery files
- [x] Commit fixed images (commit ef372b8)
- [x] Fix deltarune event image to correct pixel sprites (commit e3bec8c)
- [x] User gallery review complete — vibe_check keeping cosmic hand, all other images approved
- [x] Clean up temp comparison/gallery HTML files

## v3.15 Guest Intelligence — RELEASED ✅ (48 tests, 8/8 tasks)
- [x] Task 1: GuestProfile Data Model + Manager (23 tests passing)
- [x] Task 2: Face Recognition Integration — Event routing + GuestProfileManager wiring (10 routing tests)
- [x] Task 3: Voice Recognition Integration — Voice ID → GuestProfile wiring at 2 identify_speaker call sites
- [x] Task 4: Per-Guest Mood Recording — Record emotion + energy after every LLM response with trend calculation (8 mood tests)
- [x] Task 5: LLM Guest Context Injection — Mario knows guest name, ID method, visit count, mood trend, topics discussed, and who else is in the bathroom
- [x] Task 6: Client Multi-Face Event Batching — Implemented batching of faces from client to server
- [x] Task 7: Group Greetings + Debounce — Mario greets multiple recognized faces by name with 60-second cooldown to prevent spam
- [x] Task 8: Integration Tests + Final Verification + Release (48 tests total, v3.15 tag released)
- [ ] Task 10: Persistent Guest Memory

## v3.14 Ultra Party Upgrade — RELEASED ✅ (85 tests, 14/14 tasks)
- [x] Sub-A: Memorial v2 — voice trigger, 10-sec countdown, music loop fix, warm recovery
- [x] 6 shot event wiring bugs fixed (finally block, .upper(), Ctrl+Shift+L, typo, loops, circular import)
- [x] Sub-A: Secret skip combo (Ctrl+Shift+L) for memorial
- [x] Sub-A: Flush idle text queue when memorial starts
- [x] Sub-B: Speech bubble auto-shrink font (14-28px) with word wrap
- [x] Sub-B: Closed captions bar at bottom of screen
- [x] Sub-B: Speech bubble stays visible until TTS audio finishes
- [x] Sub-B: Hot-swappable bathroom backgrounds from assets/backgrounds/
- [x] Task 10: Person Detection Qdrant Collections — mario_faces (128-dim) and mario_voices (256-dim)
- [x] Person detection tests fixed — 9 tests pass with consistent Qdrant mocking
- [x] Task 11: Dynamic Guest Learning Flow — "Who are you?" flow, Mystery Guest fallback, Jacob VIP
- [x] Task 12: LLM Sentiment Integration — emotion/energy extraction (14 tests passing)
- [x] Sub-E: Fix WIND_DOWN stuck bug (reset party clock on fresh start)
- [x] Task 5: Shot Events System Framework (10 tests passing)
- [x] Task 6: Shot Event Configurations — Lisa Webb + Birthday Boy + Deltarune (19 tests passing)
- [x] Task 7: Shot Events WebSocket Integration — wired, REST endpoints, TTS precaching
- [x] Easter egg scheduler — fires 3-5x per night with 30-min minimum gap

## v3.14.1 Post-Review Fixes (In Progress)
- [x] Fix orphaned _detect_keyword_particles function body (missing def)
- [x] Remove random VIP face encoding (pollutes face recognition)
- [x] Move admin API key from URL query param to X-API-Key header
- [x] Fix EasterEggScheduler multi-fire race condition
- [x] Restrict CORS from wildcard to localhost/LAN IPs
- [x] Make DEBUG flags configurable via environment variables
- [x] Add thread safety to _recent_responses list in llm.py
- [x] Fix deadlock in FaceMemory.learn_guest() — Lock → RLock (already fixed: face_memory.py:36 uses RLock)
- [x] Fix NameError: _safe_ws_send undefined in guest learning flow (not present in codebase)
- [x] Fix NameError: memory_module → memory in leaderboard (command_handlers.py:855-872)
- [x] Fix unreachable Qdrant health check (dead code after return in main.py:1049-1111)

## v3.16 Party Day Release — RELEASED ✅ (768 tests passing)
- [x] Deltarune shot: character→person mapping (Kris=Roman, Ralsei=Elijah, Susie=Villa, Lancer=Jacob)
- [x] Add display_name + image_file fields to ShotEvent dataclass
- [x] Copy Deltarune pixel art to client/assets/images/
- [x] Route shot event text to closed captions (was missing)
- [x] Tone-adaptive overlay rendering (solemn/celebratory/fun)
- [x] Event-specific image display during announcement + toast phases
- [x] Word-wrap long text in shot event overlays
- [x] Regenerate all 122 Mario poses via SubNP API + rembg background removal
- [x] Fix 5 game handler IndexError crashes (would_you_rather, mario_trivia, name_that_character, wyr_mario, rapid_fire)
- [x] Hardened hot_takes + never_have_i_ever with same defensive patterns
- [x] Secret panic sequence (Up Up Down Down Left Right) — no visible hints
- [x] Fix leaderboard memory_module NameError
- [x] Fix unreachable Qdrant health check (removed 50 lines dead code)

## v3.15.1 UI Fixes
- [x] Fix UI element overlapping (info strip vs speech bubble, subtitle vs closed captions)
- [x] Dynamic banner positioning (_banner_bottom) for all HUD elements
- [x] Speech bubble auto-scales to available screen space
- [x] Fix relative imports in client (mario_display.py, presence.py)
- [x] Info strip overflow protection (left/right items won't collide)

## v3.16.1 Overlay + Sprite Fixes — RELEASED ✅
- [x] Fix sprite flickering: EMOTION_SPRITE_MAP converted from random lists to single deterministic strings
- [x] Fix STATE_SPRITE_MAP greeting from list to single string
- [x] Memorial overlay alpha set to 255 (fully opaque) for all phases — no UI bleed-through
- [x] Screenshot utility rewritten with DPI awareness + TOPMOST flag
- [x] Fix lisa_webb music path in shot_events.py
- [x] Verified all 6 event phases work: announcement→silence→countdown→toast→music→recovery
- [x] Fix ellipsis TTS bug: strip "..." from LLM responses, idle behavior, safety filter
- [x] TTS preclean: handle comma-before-punctuation artifacts (", !" → "!")
- [x] Fullscreen toggle (F11) verified: render buffer scaling + memorial overlay compatible

## v3.16.2 Final Audit Release — RELEASED ✅
- [x] CRITICAL: Fix reset_event race condition — block reset while event is actively running (prevents double-fire)
- [x] Fix toast_y Surface None guard — prevents potential crash during memorial toast phase
- [x] Regenerated 3D pose images (improved quality)
- [x] Added qdrant face/voice storage databases
- [x] Ignore qdrant .lock files in .gitignore

## Future / Not Yet Implemented
- [ ] Sub-C: Real-time face detection (YOLO v8 + face_recognition)
- [ ] Sub-C: Voice identification (Resemblyzer) per-utterance
- [ ] Sub-D: Per-guest mood persistence in Qdrant
- [ ] Stable Diffusion bathroom backgrounds (prompts written, need generation)
- [ ] Better bathroom background images (more realistic)

## v3.13 Memorial Overhaul + Party Polish
- [x] Generate memorial SFX (chime + clink WAV files)
- [x] Add memorial music support (pygame.mixer.music MP3 playback)
- [x] 5-phase memorial display overlay (announcement, silence, toast, music, fadeout) with photo, particles, golden glow
- [x] Client memorial suppression + music/SFX phase handling
- [x] Server 5-phase memorial orchestration with TTS timing
- [x] F11 fullscreen fix (SCALED + RESIZABLE + error handling)
- [x] Jacob VIP context injection into LLM prompts
- [ ] Integration test: trigger full memorial flow end-to-end
- [] Add pygame quick-trigger key coverage
- [] Verify admin slash command routing in client
- [] Check F4 health overlay rendering in pygame client
- [ ] Create release v3.13

## v3.12 TTS Cache + UI Fixes
- [x] Deep ellipsis pre-clean: _preclean_tts_text() in tts.py sanitizes ALL text before cache/TTS
- [x] Purge stale TTS cache: purge_stale_cache() deleted 1109 bad entries
- [x] Cache management: clear_all_cache() for full reset
- [x] Fixed all hardcoded ellipsis in mario_prompt.py (20+ strings) and llm.py (3 strings)
- [x] Fixed perfect_cache_v2.py .lower() cache key mismatch
- [x] Two-strip header layout (title bar Y=0-28, info strip Y=28-50)
- [x] Secret triple-tap F12 panic button (hidden from guests)
- [x] Speech bubble stays visible while audio still playing
- [x] Memorial interrupt priority (skips idle queue)
- [x] Updated CLAUDE.md with TTS cache convention and UI layout rules
- [ ] Test gemma3:27b quality on Threadripper before party
- [ ] Run canary smoke test on Threadripper
- [ ] Configure Tailscale for remote client access
- [ ] Fix 5 game handler IndexError crash bugs (would_you_rather, wyr_mario, name_that_character, mario_trivia, rapid_fire)
- [ ] Fix 13 client UI bugs from prior audit
- [ ] Add tests for _preclean_tts_text()
- [ ] Create release v3.12

## Speech Bubble Fix (Done)
- [x] Fix text overflowing speech bubbles — text was rendered outside spiky SHOUT bubble edges
- [x] Size bubble for full text (not partial typewriter) to prevent mid-message resizing
- [x] Use font.get_linesize() instead of magic number for proper line spacing
- [x] Add extra padding for SHOUT style spiky bubbles (35px vs 20px)
- [x] Make spike inner dips flush with rect boundary instead of 5px inside
- [x] Page-based auto-advance: long text splits into pages that advance with typewriter
- [x] Page indicator dots show current page position
- [x] Smooth fade transitions between pages
- [x] All text visible (no more "..." truncation)
- [x] Add pygame clip rect as safety net for text rendering

## Audio-Synced Typewriter (Done)
- [x] Calculate typewriter speed from audio WAV duration
- [x] Text finishes 0.3s before audio ends (natural feel)
- [x] Fallback to adaptive speed for non-audio messages
- [x] Handle streaming audio chunks (estimate total from first chunk)
- [x] Min clamp 0.15, max 8 chars/frame (readable range)

## Event Image Audit Round 5 (Done)
- [x] Audited all 100 event images
- [x] Found 12 bad images: pokemon, among_us, ohio, ok_boomer, rick_roll, mystery_shot, waterfall, kings_cup, fast_furious, rocket_league, sabrina_carpenter, smash_bros
- [x] Regenerated all 12 via Pollinations.ai
- [x] Verified all 12 regenerated images look correct

## Fullscreen Fix (Done)
- [x] Fix fullscreen scaling — pygame.display.Info() returned window size (800x600) not desktop resolution
- [x] Use get_desktop_sizes() for correct monitor resolution (1280x720)
- [x] Fullscreen now properly scales and centers content with letterboxing

## v3.11 TTS Quality + Audio Normalization (Done — 636 tests)
- [x] Audio normalization: peak normalize to -3dB for consistent volume
- [x] New character pronunciations (Peach, Luigi, Yoshi, Daisy)
- [x] Year-to-words conversion (2000-2099)
- [x] TTS prompt guidance rules in system prompt
- [x] Speech rate reduced +20% → +10%
- [x] 10 new TTS tests (normalization + preprocessing)
- [x] Fixed escape sequence deprecation warning
- [x] Updated CLAUDE.md with TTS improvements
- [x] Added purge_stale_cache() to tts.py — scans disk cache, deletes entries stale after _preclean_tts_text
- [x] Added clear_all_cache() to tts.py — clears in-memory + optional disk cache, resets stats
- [x] Purged 1109 stale disk cache entries via purge_stale_cache()
- [x] Fixed perfect_cache_v2.py .lower() mismatch in cache key generation
- [ ] Test gemma3:27b quality on Threadripper before party
- [ ] Run canary smoke test on Threadripper
- [ ] Configure Tailscale for remote client access

## v3.9 Gossip Seed Questions (Done)
- [x] Gossip seed questions — 10 fun party-starter questions to generate gossip material early
- [x] Wired into conversation context at 20% probability when gossip < 10 entries
- [x] No-repeat tracking per party session
- [x] 624 tests passing

## v3.8 Final Sprint (Done)
- [x] Idle gossip recap — Mario reflects on party gossip when alone (trending, rivalries, alliances, titles)
- [x] Fix idle gossip wiring — was unreachable due to condition that was always False
- [x] 619 tests passing

## v3.7 Social Intelligence Overhaul (Done)
- [x] Gossip alliances — guests who agree on topics form friendships alongside rivalries
- [x] Trending topics — 3+ guests mention same topic → surfaced as party hot news
- [x] Topic mention tracking across all guests for trend detection
- [x] Party recap for newcomers — exciting FOMO teaser combining all social dynamics
- [x] Return visit intelligence — gossip-based dossier for returning guests (highlights, traits, titles, relationships)
- [x] Command discovery tests — 7 tests for hint system
- [x] 613 tests passing

## v3.6 Conversation Quality & Emotional Depth (Done)
- [x] Conversation summarization — zero-latency rolling summary prevents context amnesia
- [x] Idle loneliness arc — 3-tier mood progression when alone (24 unique messages)
- [x] Command discovery hints — 15 natural feature suggestions during conversation
- [x] 582 tests passing

## v3.5 Content Expansion & Validation (Done)
- [x] Text input timeout (45s) + exception handling with fallback responses
- [x] Game content expansion (karaoke 5→20, truth 10→25, dares 10→20, stories 12→25)
- [x] Force-stop game admin endpoint + dashboard button
- [x] Game state validation (VALID_GAMES frozenset, input guards, check_game_timeout)
- [x] Dashboard alerts (WS status, GPU overtemp, error spikes, idle failures)
- [x] Idle loop executor restart on circuit breaker
- [x] Expanded Jacob aliases (JH, Hoppenstedt, birthday boy)
- [x] Simon actions 12→31, starter words 8→18, RPS reactions 10→15 each
- [x] WebSocket send lock tests + text input timeout tests
- [x] 561 tests passing
- [x] Birthday context always-on — injected into EVERY LLM call
- [x] Emotion sync wired — client processes emotion field from server
- [x] Party metadata in config — location, theme, expected guest count
- [x] Generic party guest profile — conversation hooks for unknown guests
- [x] Webcam exponential backoff recovery (never silently dies)
- [x] Camera status UI indicator (reconnecting/disconnected)
- [x] Token budget enforcement — trims context if > 80% of num_ctx
- [x] Qdrant health recovery — auto re-enables semantic search
- [x] TTS emergency silence fallback (never returns None)
- [x] Fix TTS tests for emergency silence behavior
- [x] 188 tests passing
- [x] Add comprehensive test suite for command_handlers.py (54 tests)
- [x] Add TestGreetingTimeout and TestReconnectStateReset tests (8 tests)
- [x] Add TestWsSendLock tests for _ws_send_lock concurrency guard (3 tests)
- [x] Add TestTextInputTimeout tests for text_input timeout/exception handling (4 tests)
- [ ] Manual test: Jacob birthday trivia mixed into Mario trivia rounds
- [ ] Manual test: birthday special questions award 2x bonus points
- [ ] Manual test: game leaderboard shows in /leaderboard endpoint
- [ ] Manual test: gossip idle behavior — verify Mario references real guest snippets when alone
- [ ] Manual test: party info banner displays name, duration timer, and guest count
- [ ] Manual test: connection status overlay no longer overlaps party banner
- [ ] Manual test: visit milestone callouts at 2/5/10/15+ visits during live party
- [ ] Manual test: Jacob birthday greeting variants with real accomplishment references
- [ ] Manual test: returning guest greetings reference last conversation topic
- [ ] Manual test: verify _connection_status red overlay appears when server unreachable
- [ ] Manual test: verify Ollama health tracking logs after 3 failed pings
- [ ] Manual test: verify emergency silence WAV plays when all TTS engines fail
- [ ] Manual test: F11 fullscreen toggle on 4K display
- [ ] Manual test: F3 chat history sidebar with long conversations
- [ ] Manual test: F12 panic mode kills all audio
- [x] Manual test: Lisa Webb memorial triggers at 45 minutes
- [ ] Manual test: admin-triggered Lisa Webb memorial via POST /admin/trigger_memorial
- [x] 5-phase memorial overlay (announcement, silence, toast, music, fadeout) with photo, particles, text
- [x] Client memorial suppression + music/SFX phase handling (_memorial_active flag, play_memorial_music, chime/clink SFX)
- [x] Server 5-phase memorial orchestration (announcement→silence→toast→music→fadeout with TTS + timing)
- [ ] Manual test: memorial overlay displays all 5 phases on client
- [ ] Manual test: Webcam person detection with multiple guests
- [ ] Configure alert_webhook_url for production deployment
- [ ] Add Tailscale setup instructions for party day networking
- [ ] Create v3.0 GitHub Release with changelog


## v3.4 Dashboard Enhancements
- [x] WebSocket connection status indicator (green/red dot) in stats bar
- [x] Alert banner for GPU overtemp, high error count, idle loop failures
- [x] dismissAlert() with 60s auto-reset of dismissed state
- [x] Server-side ws_connected and idle_errors added to /health endpoint
- [x] WebSocket send lock (_ws_send_lock) prevents concurrent sends from idle loop, user responses, admin endpoints
- [x] All 554 tests passing
- [x] Idle loop circuit breaker with TTS executor restart recovery
- [x] Integrated check_game_timeout from game_handlers into idle loop

## v3.3 Robustness & Testing (Done)
- [x] Fix 12 bare except-pass blocks → logged warnings/debug messages
- [x] Add 12 check_input() safety filter tests
- [x] Enhanced party host dashboard — health badges (LLM/TTS/STT), GPU temp, cache stats
- [x] Rapid re-entry detection ("back so soon?" greeting intelligence)
- [x] TTS retry resilience (2-attempt retry before text-only fallback)
- [x] Concurrent game guard (block starting new game while one active)
- [x] Per-guest game rotation tracking (no cross-guest pollution)
- [x] Night progression persistence across server restarts
- [x] 11 IndexError guards on game data pool access
- [x] 8 night progression edge case tests (boundary, restart, negative time, 12h party)
- [x] 6 concurrent game guard tests
- [x] 517 tests passing

## v3.2 Party UX (Done)
- [x] Smart game suggestions — mood/engagement-based game recommendations (30% after 3+ exchanges)
- [x] Expanded SFX map — 7 new events (correct, wrong, level_up, victory, challenge, milestone, gossip)
- [x] Exit quick feedback — 25% chance Mario asks for bathroom rating in farewell
- [ ] Manual test: verify game suggestions trigger after 3+ exchanges with different moods
- [ ] Manual test: verify new SFX events fire correctly (correct, wrong, level_up, victory, challenge, milestone, gossip)
- [ ] Manual test: verify exit rating prompt appears ~25% of the time for 3+ exchange visits

## Tests
- [x] Add comprehensive unit tests for idle_behavior.py (43 tests covering init, idle actions, content pools, unique selection, memorial, contextual behavior, reengagement, games, edge cases)

## Critical / Major
- [ ] CRITICAL: Resolve VRAM budget — 70B-Q5_K_M (22GB) + RVC + Whisper + Fish Speech exceeds 24GB RTX 3090 Ti
- [ ] CRITICAL: Add MoSCoW priority ordering to spec — no cut list if time runs out
- [ ] MAJOR: Fix TTS fallback chain ordering — XTTS v2 (10-60s) before Edge TTS (1s) is backwards
- [ ] MAJOR: Add API contracts for 6 new endpoints (voice-compare, dashboard, report, canary, reload, webhook)
- [ ] MAJOR: Add Phase 3 UNHINGED content safety guardrails
- [ ] MAJOR: Merge Section 14 (Guest Count Scaling) into Section 3 (Night Progression) — duplicated logic
- [ ] GPU contention: LLM + TTS share VRAM, may need orchestration
## Deployment & Setup
- [ ] Upload models-v2.1.zip to GitHub Release at https://github.com/VillaKeth/Mario-Bathroom-AI/releases/tag/v2.1
- [ ] On Linux/Mac: run `chmod +x setup.sh` before executing
- [ ] Set birthday_person_name in config.json
- [ ] Set alert_webhook_url in config.json
- [ ] Run `python scripts/verify_setup.py` on party machine (replaces deploy_check.py)
- [ ] Run watchdog standalone during party: python server/watchdog.py
- [ ] Pull and run Mixtral 8x7B model on server: ollama pull mixtral:8x7b
- [ ] Pull 70B-Q4_K_M model on server: ollama pull llama3.1:70b-q4_k_m
- [ ] Run canary against live server before party: python server/canary.py
- [ ] Package into installable app for easy deployment
- [ ] Task 8: Create GitHub Release v2.1 via web UI (API auth mismatch — SSH=VillaKeth, HTTPS token=VillaKWS)
- [ ] Task 8: Upload models-v2.1.zip to release (re-run package_models.py, then upload via web UI)

## Testing
- [x] Comprehensive test suite for game_handlers.py (60 tests covering 10 games + rotation + edge cases)
- [x] Add defensive empty-list guards to all game init functions (11 guards across 9 games + truth_or_dare handler)
- [x] Game state validation and timeout enforcement in handle_game_input + check_game_timeout
- [ ] Integration test with both models loaded simultaneously
- [ ] Test fullscreen (F11) and panic (F12) on party monitor
- [ ] Test Pygame client with reorganized repo
- [ ] Test end-to-end with live conversation
- [ ] Test with multiple speakers switching rapidly
- [ ] Test latency over WiFi vs ethernet to server
- [ ] Test full client (with mic/webcam) on MacBook
- [ ] Test XTTS-only voice quality with full-sentences reference (does it sound like Mario?)
- [ ] Run extended 6-hour endurance test with new file paths
- [ ] Run --hours 1 quick endurance test to validate
- [ ] Run --ralph overnight for continuous improvement
- [ ] Continue ralph loop iterations (R299+) for regression monitoring
- [ ] Smoke test: run client headless to verify no import/init crashes
- [ ] End-to-end party rehearsal test
- [ ] Final cache quality audit (listen to all 51 phrases)
- [ ] Overnight ralph loop endurance test
- [ ] Create reusable stress test skill for repeated testing
- [ ] Full end-to-end party simulation test
## TTS & Voice Quality
- [ ] Install fish-speech when available: pip install fish-speech
- [ ] Add catchphrase WAV files to assets/catchphrases/ directory
- [ ] Integration test with Fish Speech model loaded
- [ ] Implement XTTS streaming (inference_stream) for faster first-audio playback
- [ ] Fix remaining TTS problem phrases (6 BAD, 13 WEAK in round 10)
- [ ] Fix consistently BAD phrases: #31 Bowzer, #33 okey dokey, #39 bathroom fun
- [ ] Test Bowzer alternatives (Bawzer, Bowsur) for best pronunciation
- [ ] Edge TTS fallback for consistently garbled short phrases
- [ ] Chase 85%+ — may need hybrid TTS (GPT-SoVITS for good phrases, Edge for persistent failures)
- [ ] Implement retry in production server synthesize() for live conversations
- [ ] Work on accuracy for live random prompts
- [ ] Live LLM responses need Whisper verification too
- [ ] Try different Edge TTS base voices for better RVC result
- [ ] Tune RVC pitch further (try 6, 10, 12 semitones)
- [ ] Upgrade ElevenLabs to Starter plan ($5/mo) for Mario voice cloning
- [ ] ElevenLabs voice cloning (needs API key from user)
- [ ] Consider Kokoro (82M, ultra-fast) as real-time fallback
- [ ] Consider Edge TTS fallback for very short phrases (<4 words)
- [ ] Add request-level isolation to prevent TTS race conditions

## Content Expansion (Done)
- [x] Expanded MARIO_TRIVIA_QUESTIONS from 25 to 50 (Mario Kart, Paper Mario, Galaxy, Odyssey, Mario Party, DK arcade, Yoshi's Island, Luigi's Mansion)
- [x] Expanded RAPID_FIRE_QUESTIONS from 20 to 30
- [x] Expanded RIDDLES from 20 to 30
- [x] Expanded HOT_TAKES from 30 to 40
- [x] Expanded NHIE_PROMPTS from 30 to 40
- [x] All 260 tests passing after expansion
- [x] Expanded SIMON_ACTIONS from 12 to 31 (physical actions, Mario impressions, party-fun moves)
- [x] Expanded STARTER_WORDS from 8 to 18
- [x] Expanded RPS_WIN_REACTIONS from 10 to 15
- [x] Expanded RPS_LOSE_REACTIONS from 10 to 15
- [x] Expanded RPS_TIE_REACTIONS from 10 to 15
- [x] All 557 tests passing after expansion

## VIP Context Injection
- [x] Add VIP profile loader (_load_vip_profile) with alias matching and caching
- [x] Inject VIP guest context as system message in build_context() before memories
- [x] Verified Jacob VIP profile loads correctly from server/data/vip_profiles/

## Features & Enhancements
- [ ] Hand wash reminder on exit event
- [ ] Bathroom challenge mode (mini-games/trivia)
- [ ] Trivia not structured as interactive Q&A (just facts)
- [ ] Add LLM-based fuzzy answer judging for trivia (call ollama for borderline answers)
- [ ] Add gossip fuel tracking from Would You Rather choices
- [ ] Tune gossip frequency (currently 35% in conversation, 50% in greetings)
- [ ] Gossip test still LLM-dependent (llama3 ignores visitor list ~50% of time)
- [ ] Consider guest rivalry system (friendly competitions between visitors)
- [ ] Add per-user personality tagging (saves "likes puns", "is sarcastic")
- [ ] Upgrade LLM model from qwen2:1.5b to 7B+ for better personality depth
- [ ] Memory greeting name test LLM-dependent (~50% pass rate)
- [ ] Sprite system total overhaul with accurate AI-generated Mario sprites
- [ ] Add more walk/run pose variants for entrance animation
- [ ] Consider adding a physical "flush" button trigger for fun
- [ ] Tune speaker ID threshold for party noise levels
- [ ] Add volume control / gain adjustment for noisy environments
- [ ] Consider streaming TTS (start playing before full generation)
## Performance & Optimization
- [ ] Measure full end-to-end conversation latency
- [ ] Audio buffer timeout optimization (2.5s → 1.5s?)
- [ ] Optimize retry loop to stop re-testing OK phrases (wastes server time)

## Documentation & Cleanup
- [ ] MINOR: Consolidate Pre-Party Canary (duplicated in Section 4 and Section 12)
- [ ] MINOR: Define Phase 3 obsession lock mechanics (topic selection, duration, reset)
- [ ] MINOR: Document config_live.json schema and relationship to config.json
- [ ] MINOR: Clarify pre-recorded catchphrase audio sourcing (copyright concerns)
- [ ] MINOR: Verify pygame mixer channel allocation supports separate SFX channel
- [ ] MINOR: Expand canary smoke tests to cover new features
- [ ] Remove "Wahoo!", "Boom!" etc. from CACHED_PHRASES (they're now empty after cleaning)
- [ ] Clean up idle_behavior.py source phrases (remove sfx/filler at source level)

## Event Image Audit — COMPLETE ✅
- [x] Generated AI images for all 102 events via Pollinations.ai
- [x] Replaced AI images with real images from Bing (93/102 events)
- [x] Visual audit round 1: fixed star_wars, game_of_thrones, league, dark_souls
- [x] Visual audit round 2: fixed checkmate (EXPLICIT CONTENT!), beer_pong, categories, chug
- [x] Visual audit round 3: fixed 14 more bad images (couples, designated_driver, last_man, mario_kart, midnight, most_likely, new_years, oktoberfest, power_hour, shotgun, skibidi, spin_bottle, vibe_check, group_photo)
- [x] Visual audit round 4: fixed 12 more bad images (pokemon, among_us, ohio, ok_boomer, rick_roll, mystery_shot, waterfall, kings_cup, fast_furious, rocket_league, sabrina_carpenter, smash_bros)
- [x] ALL 104 event images verified correct and appropriate across 5 audit rounds
- [x] Cleaned up temp audit files (_regen_batch.py, _audit_gallery.html, _audit_script.py, _screenshot.png)

## Tests
- [x] Add TestVIPBypassFix class to test_edge_cases.py (5 tests)
- [x] Add TestStateAccessThreadSafety class to test_edge_cases.py (2 tests)
- [x] Add TestRapidReEntry class to test_party_modules.py (6 tests for get_seconds_since_last_exit)
- [x] Add TestGossipPruningAndComparison to test_party_gossip.py (11 tests for _prune_gossip, get_comparison_hint, _analyze_speech_traits)

## SFX Audio
- [x] Replace all 16 SFX WAV files with high-quality retro chiptune sounds (square waves, FM synthesis, ADSR envelopes, arpeggios, noise channels, 44100Hz 16-bit PCM)
- [x] Generate memorial_chime.wav (1.5s gentle bell, 880Hz+1320Hz) for moment of silence phase
- [x] Generate memorial_clink.wav (0.6s glass clink, 2500Hz+4000Hz+6000Hz) for toast phase

## TTS Source String Cleanup
- [x] Replace all hardcoded ellipsis (...) in TTS-spoken strings with commas/periods (15 edits across mario_prompt.py and llm.py)

## Session Fixes (2026-05-22)
- [x] MCP config migration (.vscode/mcp.json → .mcp.json)
- [x] STT device fix (cpu → auto)
- [x] STT model upgrade (base → small, 74% vs 48% recall)
- [x] Audio buffer timeout bug fix (empty→non-empty transition only)
- [x] Black bars fix when maximized (fill BG_COLOR, extend floor)
- [x] Shout bubble text overflow fix (max_text_width=380, dynamic bubble width)
- [x] Bubble height descender buffer (+4 pixels)
- [x] Typewriter cursor alignment fix
- [x] Keyboard input cursor alignment fix
- [x] Command cooldown bug fix (only reset on match, not every call)
- [x] Game routing order fix (specific games before generic "let's play")
- [x] Startup greeting async (non-blocking receive loop)
- [x] TTS workers increased to 2 for low tier
- [x] TTS user priority preemption (idle/precache yields to user TTS via _UserTTSPreempt)
- [x] Mood badge repositioned to top-left corner below banner
- [x] Shout bubble shadow now matches spiky polygon shape (no rectangular shadow)
- [x] Shout bubble inner dips pushed outward (+5px margin) to prevent text overlap
- [x] Emoji stripping in speech bubble (Pygame fonts can't render emojis)
- [x] Idle chatter deduplication (contextual idle uses _global_recent, main loop tracks last 10)
- [x] Self-interruption system (server cancels previous task on new input, sends clear_audio to client)
- [x] Client audio clear() method (drains queue + stops playback without killing worker thread)
- [x] Rate limiter bypass for urgent messages (always reset on new input)
- [x] Post-response sleep reduced from 5s to 1s (non-blocking task architecture)
- [x] Full 8/8 E2E test suite passing (vomit/voice/audio/interrupt)
- [x] Emotion badge fix: LLM response emotion passed directly to client (was using decayed system state)
- [x] Idle chatter emotion inference: badge matches idle text content (not stuck on neutral)
- [x] Idle chatter variety fix: contextual idle throttled to 20%, main 663-item pool used 80% of the time
- [x] Idle interval growth slowed (max 45s instead of 90s, +2s per action instead of +5s)
- [x] Idle pool dedup uses named pools for better per-category rotation

## Idle Message Variety Fix
- [x] Randomize idle category selection (random.randint instead of modulo rotation)
- [x] Increase global dedup window from 15 → 50 messages
- [x] Lower pool reset threshold from 90% → 60% for earlier item re-entry
- [x] De-hardcode birthday person name from PHASE_PROMPTS in mario_prompt.py

## Expanded Pose Generation (~48 new poses across 7 categories)
- [ ] Run generate_expanded_poses.py --category party (10 party poses)
- [ ] Run generate_expanded_poses.py --category memorial (5 memorial poses)
- [ ] Run generate_expanded_poses.py --category toast (5 toast poses)
- [ ] Run generate_expanded_poses.py --category bathroom (8 bathroom poses)
- [ ] Run generate_expanded_poses.py --category reactions (10 reaction poses)
- [ ] Run generate_expanded_poses.py --category birthday (5 birthday poses)
- [ ] Run generate_expanded_poses.py --category gaming (5 gaming poses)
- [ ] Review generated images and re-run any that look bad
- [ ] Verify transparent backgrounds look clean in mario_display
- [ ] Test new EMOTION_SPRITE_MAP list-based random selection in live display

- [x] Build interactive pose comparison gallery (pose_gallery.html) with emotion mapping, selection/rejection, flagging, localStorage persistence, and export

## Client UX Overhaul
- [x] Fix fullscreen scaling bug (removed SCALED flag that conflicted with render buffer)
- [x] Redesign speech bubbles (drop shadow, warm colors, inner highlights, better font)
- [x] Add bouncing dots thinking indicator (replaces "Hmm..." speech bubble)
- [x] Add floating emotion badge with pop animation (replaces tiny "Mood:" HUD text)
- [x] Cover all 37 emotions with emoji + color badge mappings
- [x] Clean up bottom status bar (removed debug [IDLE] labels, minimal design)
- [x] Push all UX overhaul commits to remote
- [ ] Persistent guest memory (remembers guests between sessions)
- [ ] Improve Mario's personality/conversation quality

## MCP Migration
- [x] Migrate .vscode/mcp.json to .mcp.json (servers -> mcpServers)
- [x] Remove stale chat.mcp.serverSampling references from .vscode/settings.json
- [x] Delete old .vscode/mcp.json file

## STT Improvements
- [x] Fix stt_device from 'cpu' to 'auto' in config.json (enables GPU when available)
- [x] Create comprehensive STT intake test (tests/test_stt_intake.py)
- [x] Upgraded STT model: base -> small (74% vs 48% recall, same speed)
- [x] Live mic test created (fails on RDP, works locally)`n- [x] TTS-STT roundtrip verify improved from 40% to 60% with small model`n- [x] Fixed all hardware tiers to use stt_device=auto instead of cpu

- [x] Fix audio buffer timeout bug (buf_age always ~0, short audio never processed)
- [x] Live E2E test passing 3/3 — audio → STT → LLM → TTS pipeline fully verified
- [x] Created live STT E2E test (tests/test_stt_live.py)
