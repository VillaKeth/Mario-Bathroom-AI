# Mario AI Party Bot - TODO

## Recently Added
- [ ] Manual test: visit milestone callouts at 2/5/10/15+ visits during live party
- [ ] Manual test: Jacob birthday greeting variants with real accomplishment references
- [ ] Manual test: returning guest greetings reference last conversation topic
- [ ] Manual test: verify _connection_status red overlay appears when server unreachable
- [ ] Manual test: verify Ollama health tracking logs after 3 failed pings
- [ ] Manual test: verify emergency silence WAV plays when all TTS engines fail
- [ ] Manual test: F11 fullscreen toggle on 4K display
- [ ] Manual test: F3 chat history sidebar with long conversations
- [ ] Manual test: F12 panic mode kills all audio
- [ ] Manual test: Lisa Webb memorial triggers at 45 minutes
- [ ] Manual test: Webcam person detection with multiple guests
- [ ] Configure alert_webhook_url for production deployment
- [ ] Add Tailscale setup instructions for party day networking
- [ ] Create v3.0 GitHub Release with changelog

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
