# Mario AI Party Bot - TODO

## v3.12 TTS Cache + UI Fixes (Current)
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

## Idle Message Variety Fix
- [x] Randomize idle category selection (random.randint instead of modulo rotation)
- [x] Increase global dedup window from 15 → 50 messages
- [x] Lower pool reset threshold from 90% → 60% for earlier item re-entry
- [x] De-hardcode birthday person name from PHASE_PROMPTS in mario_prompt.py
