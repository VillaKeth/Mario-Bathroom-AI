# Mario AI — Task Tracking

## ✅ Completed
- [x] Server project setup (FastAPI WebSocket)
- [x] Client project setup (Pygame display)
- [x] Speech-to-text pipeline (faster-whisper, cuda→cpu fallback)
- [x] Text-to-speech pipeline (edge-tts with Mario pitch shift)
- [x] Basic conversation loop (mic → STT → LLM → TTS → speaker)
- [x] Mario personality system prompt
- [x] Memory system (SQLite: people, conversations, facts)
- [x] Speaker identification (resemblyzer voice embeddings)
- [x] Memory retrieval for context
- [x] Presence detection (OpenCV webcam motion)
- [x] Animated Mario sprite with speech bubbles
- [x] Event reactions (enter/exit greetings)
- [x] Deploy scripts (bat + sh for both client and server)
- [x] Emotion/mood system (10 states, affects voice + animations)
- [x] Party stats tracker (visits, durations, records, fun facts)
- [x] Content safety filter (blocks inappropriate content, Mario-style redirects)
- [x] Idle behavior system (mumbles, jokes, trivia, songs, time comments)
- [x] Sound effects generator (coin, powerup, pipe, jump, star, greeting, goodbye)
- [x] TTS emotion-based voice modulation (rate + pitch from emotion)
- [x] Client sound effects integration
- [x] Emotion-based Mario animations (eyes, mouth, particles)
- [x] Particle effects system (stars, sparkles per emotion)
- [x] Server tested and starts cleanly
- [x] Configuration file (config.json for server IP, port, models, client settings)
- [x] Latency masking ("thinking" state sent to client before processing)
- [x] Name learning flow (voice registration on "my name is X")
- [x] Fixed TTS rate/pitch variable scoping bug
- [x] Fixed resemblyzer numpy.bool deprecation crash
- [x] Full end-to-end WebSocket test — ALL 5 STEPS PASS
- [x] Pixel art Mario sprites (8 frames: idle, talk, talk2, walk1, walk2, wave, jump, think)
- [x] Sprite-based display rendering (replaces basic shape drawing)
- [x] Sprite generator script (client/generate_sprites.py)
- [x] HD sprite upgrade (auto-outlines, drop shadows, shading, 10× scale → 200×270px)

## 🔲 Remaining
- [ ] Test with multiple speakers switching rapidly
- [ ] Tune speaker ID threshold for party noise levels
- [ ] Add volume control / gain adjustment for noisy environments
- [ ] Test latency over WiFi vs ethernet to server
- [ ] Consider adding a physical "flush" button trigger for fun
- [ ] Package into installable app for easy deployment
- [ ] Test full client (with mic/webcam) on MacBook

