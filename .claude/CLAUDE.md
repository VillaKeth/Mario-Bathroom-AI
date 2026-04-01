# Mario AI Party Bot — Project Context

## What This Is
An interactive Mario AI bathroom party bot. At a real house party, a Raspberry Pi/laptop runs Mario in the bathroom — he greets guests, plays games, tells jokes, sings, and comforts sick people. Designed for 8+ hour continuous operation.

## Architecture
```
── Server Core ──
server/main.py            — FastAPI + WebSocket server (port 8765)
server/command_handlers.py — All command routing, games, sick detection
server/mario_prompt.py    — Phase prompts, guest typing, system prompt assembly

── Voice & Audio ──
server/tts.py             — GPT-SoVITS + Edge TTS + RVC voice pipeline
server/tts_router.py      — 5-level TTS fallback chain
server/fish_speech_tts.py — Fish Speech integration (ready, deferred for VRAM)
server/stt.py             — Whisper-based speech-to-text
server/audio_distress.py  — PANNs Cnn14 model for retching/distress audio detection

── LLM ──
server/llm_router.py      — Dual-model routing (fast vs quality)
server/hardware.py        — GPU detection, 5 hardware tiers (LOW→ULTRA)

── Memory & Knowledge ──
server/memory.py          — SQLite memory (facts, conversations, people) + dual-write to Qdrant
server/memory_semantic.py — Qdrant vector DB wrapper (fastembed all-MiniLM-L6-v2, 384-dim)
server/vip_knowledge.py   — VIP profile loader (JSON profiles → Qdrant injection)
server/face_memory.py     — SQLite face encoding storage + Euclidean matching

── Party Features ──
server/party_stats.py     — Leaderboard, visitor tracking, party analytics
server/party_gossip.py    — Cross-visitor social dynamics
server/idle_behavior.py   — Idle behavior, autonomous actions, timed events
server/night_progression.py — 4-phase party progression over 8 hours
server/catchphrase_mirror.py — Detects and mirrors guest catchphrases
server/birthday_vip.py    — Birthday person detection + enhanced interactions

── Reliability ──
server/watchdog.py        — Health monitoring + tier degradation
server/dashboard.py       — Real-time stats dashboard
server/canary.py          — Pre-party smoke tests (10 checks)
server/hot_reload.py      — LiveConfig for runtime tuning via config_live.json

── Client ──
client/mario_client.py    — Pygame desktop client with 74 AI poses
client/mario_display.py   — Display renderer (4K, F3 chat history, F11 fullscreen)
client/person_detector.py — YOLO v8n person detection + face_recognition encoding
web/mario_chat.html       — Browser chat interface at /chat endpoint
```

### Memory System (Hybrid SQLite + Qdrant)
- **SQLite** (`server/data/memory.db`): Source of truth for structured data (people, conversations, facts)
- **Qdrant** (`server/data/qdrant_memories/`): Semantic vector search over all memories
- **fastembed** (all-MiniLM-L6-v2): 384-dim embeddings, CPU-only, zero VRAM impact
- **Dual-write**: every save_fact/save_conversation writes to both SQLite and Qdrant
- **Memory cap**: 50 items injected into LLM context (ULTRA hardware budget)
- **VIP profiles**: JSON files in `server/data/vip_profiles/` — deep biographical data for special guests
- **Backfill**: first startup auto-migrates existing SQLite data into Qdrant

## How to Run
```bash
cd server && python main.py    # Starts on http://localhost:8765
# Browser: http://localhost:8765/chat
# Desktop: python client/mario_client.py
```

## Webcam / Face Detection Pipeline
Fully local face recognition — no cloud, no stored images.

### Data Flow
```
PresenceDetector (exclusive cv2.VideoCapture)
  → frames passed to PersonDetector (client/person_detector.py)
    → YOLO v8n detects person bounding boxes
    → face_recognition encodes faces (128-dim vectors)
      → encodings sent via WebSocket to server
        → FaceMemory (server/face_memory.py) matches via Euclidean distance
          → detected_guest wired into greeting logic in main.py
```

### Key Details
- **Storage**: SQLite only — 128-dim numerical vectors. No images ever stored.
- **Matching**: Euclidean distance with early-exit at >95% confidence.
- **Privacy**: Camera faces the door only. Raw frames never leave the client.
- **Config keys**: `enable_person_detection`, `yolo_model`, `face_match_tolerance`, `person_detection_frame_skip`

## Phase Prompts System
`server/mario_prompt.py` drives Mario's personality evolution throughout the party.

### Party Phases (PHASE_PROMPTS dict)
| Phase | Description |
|-------|-------------|
| WARM_UP | Friendly, welcoming energy for early arrivals |
| PARTY_MODE | Peak energy, jokes, games, maximum engagement |
| UNHINGED | Late-night chaos — wildcard responses, roasts |
| WIND_DOWN | Mellow, reflective, "great party" energy |

### Guest Typing
- `_infer_guest_type()` analyzes message patterns → classifies as **shy / curious / energetic / storyteller / balanced**
- `GUEST_TYPE_HINTS` dict provides per-type prompt adjustments (e.g., shy guests get gentler prompts)
- Phase + guest type are injected into the LLM system prompt in `main.py`

## LLM Router
`server/llm_router.py` — Dual-model routing system.
- **Fast model**: Used for quick, simple responses (greetings, short answers)
- **Quality model**: Used for complex queries, games, emotional moments
- Automatic routing based on query complexity analysis
- 37 dedicated tests passing

## TTS Router
`server/tts_router.py` — 5-level fallback chain for voice synthesis:
1. GPT-SoVITS V2 (primary, highest quality)
2. Edge TTS + RVC (instant, good quality)
3. Edge TTS raw (no RVC, still decent)
4. Fish Speech (ready in `server/fish_speech_tts.py`, deferred — needs >4GB VRAM)
5. Silent fallback (text-only, no audio)

## ULTRA Hardware Tier
`server/hardware.py` defines 5 tiers (LOW → MEDIUM → HIGH → VERY_HIGH → ULTRA). ULTRA is tuned for Threadripper Pro / high-end setups:

| Setting | ULTRA Value |
|---------|-------------|
| tts_concurrency | 6 |
| gpu_idle | 0.3s |
| cache | 1000 MB |
| bg_tasks | 80 |
| llm_predict | 250 tokens |
| history | 150 messages |
| LLM keepalive | 60 minutes |

- 16 additional precache phrases preloaded in `tts.py` at startup

## Client UI Upgrades
`client/mario_display.py` renderer features:

### Keyboard Shortcuts
| Key | Action |
|-----|--------|
| F3 | Chat history sidebar (scrollable, overlay with transparency) |
| F11 | Fullscreen toggle with 4K support |

### Rendering Optimizations
- **Adaptive typewriter speed**: <50 chars → slow, <200 chars → medium, else → fast
- **Font caching**: Avoids per-frame `SysFont` creation (major perf win)
- **Cached fonts**: Sidebar uses pre-rendered font objects

## Reliability Layer

### Watchdog (`server/watchdog.py`)
Health monitoring with automatic tier degradation:
- **full** → all systems operational
- **degraded** → non-critical features disabled
- **minimal** → only core chat + TTS running

### Dashboard (`server/dashboard.py`)
Real-time stats dashboard for monitoring party health.

### Canary (`server/canary.py`)
Pre-party smoke tests — 10 checks run before the party starts:
- LLM connectivity, TTS pipeline, WebSocket health, memory DB, etc.

### Hot Reload (`server/hot_reload.py`)
LiveConfig system — edit `config_live.json` at runtime to tune:
- Personality parameters, idle timing, energy levels
- No server restart required

## Party Features

### Catchphrase Mirror (`server/catchphrase_mirror.py`)
Detects guest catchphrases through repetition analysis and mirrors them back in Mario's voice for comedic effect.

### Birthday VIP (`server/birthday_vip.py`)
Special handling for birthday guests:
- Auto-detection from VIP profiles or explicit mention
- Enhanced interactions, birthday-specific jokes and songs

### Night Progression (`server/night_progression.py`)
4 phases over 8 hours with smooth transitions:
- 15-minute crossfade between phases
- Guest energy caps per phase (prevents over-hype during wind-down)
- `banned_topics` per phase (e.g., no sad topics during PARTY_MODE)
- 22 dedicated tests passing

### Sound Effects System
- 6 WAV files for party events
- `SoundEventManager` handles playback, queuing, and volume control

## Key Technical Details

### Response Pipeline
1. User sends text via WebSocket → `command_handlers.py` checks for games/commands
2. If no command match → LLM (Ollama llama3 8B) generates response with VIP fact injection
3. Response → TTS (GPT-SoVITS primary, Edge TTS + RVC fallback) → audio sent back
4. Cached responses are instant (0.0s), LLM responses 3-15s
5. Thinking filler ("Let me think!") sent while LLM generates (is_thinking_filler flag)

### Games (12 total)
RPS, Simon Says, 20 Questions, Truth or Dare, Trivia, Riddle, Word Chain, Hangman, Hot Takes, Would You Rather, Never Have I Ever, Karaoke. All have game state management, timeouts (180s), and clean switching between games.

### Sick Care System (4 detection layers)
1. **Text keywords** in command_handlers.py — instant comfort response
2. **Friend-sick detection** — "my friend is throwing up" → helpful advice (NOT first-person flow)
3. **Recovery detection** — "feeling better" → clears sick mood with funny response
4. **Audio distress** via PANNs model — retching/groaning sounds → comfort
5. **Proactive check-ins** — 30s silence while sick → Mario checks on you (then every 90s)

**Tone**: Deadpan humor + genuine care. NOT corny. Example: "If anyone asks, you were fixing your hair. Our secret."

### Idle System
- Fires messages at 30-135s intervals when no user input
- 207+ idle mumbles (party-specific, time-aware, DJ announcements)
- Known issue: some messages over-repeat (e.g., "Afternoon break!")

### TTS Voice
- GPT-SoVITS V2 with Charles Martinet RVC models
- 1600+ cached audio clips in server/data/tts_cache
- 397 ralph loop rounds, final quality 97-100%
- Hybrid mode: Edge+RVC for instant, GPT-SoVITS for background quality

### Conversation Quality
- Dynamic temperature (humor→0.95, questions→0.75)
- Nickname evolution (stranger→acquaintance→buddy→bestie)
- Running gag detection, emotional mirroring, question-back system
- 40-message conversation history with momentum injection

## Testing Status (as of 2026-04-01)
- **Core tests**: 144+ passing (unit + integration)
- **E2E Browser Test**: 40/45 passed (53+ min session, 107 audio clips)
- **Stress Test**: 52/52 passed, 8-hour endurance verified
- **LLM Router**: 37/37 tests pass
- **Night Progression**: 22/22 tests pass
- **Memory Semantic**: 19/19 tests pass (Qdrant layer)
- **VIP Knowledge**: 12+ tests pass (profile loading, fuzzy matching, facts)
- **Edge Cases**: 18 crash vector tests in `test_edge_cases.py`
- **Webcam Pipeline**: 12 tests (`test_face_memory.py` + `test_person_detector.py`)
- **All features working**: games, chat, idle, emotions, sick care, recovery, friend-sick, face detection
- **Known minor issues**: idle message variety, trivia not interactive Q&A

## Coding Conventions
- `print()` for logging (NOT `logger` — command_handlers has no logger import)
- WebSocket message type must be `"mario_response"` (not `"response"`)
- Game state in `state_current["_active_game"]` dict
- Sick mood tracked in `state_current["_detected_mood"]`
- Debug flags: `DEBUG_AUTH`, `DEBUG_API`, etc. (default True for new features)
- Always use `general-to-specific` naming: `pointBase`, `pointNext`, etc.

## Config
- `config.json` at repo root — LLM model, TTS settings, timeouts, face detection settings
- `config_live.json` — Runtime-editable personality tuning (hot-reloaded by `server/hot_reload.py`)
- Hot-reload via `/config/reload` endpoint (full config) or LiveConfig (personality only)
- LLM keepalive: 30min keep_alive + 4min ping (60min on ULTRA tier)
- Face detection keys: `enable_person_detection`, `yolo_model`, `face_match_tolerance`, `person_detection_frame_skip`

## Remaining Work
See `TODO.md` for full task tracking. Key remaining:
- Create reusable stress test skill
- Idle message variety improvement
- Consider LLM upgrade from llama3 8B to larger model (needs bigger GPU)
- Sprite system overhaul
- Fish Speech TTS — code ready, needs GPU with >4GB VRAM

## Hardware Profile
- **GPU**: Quadro P1000 (4GB VRAM) — detects as "low" tier
- **RAM**: 32GB
- **CPU**: 24-core
- **LLM**: Ollama running llama3 8B (fits in 4GB VRAM)
- **TTS**: GPT-SoVITS V2 subprocess (separate venv: `gpt_sovits_env`)
- **GPU detection**: nvidia-smi fallback (torch not installed in server venv)
- Fish Speech deferred — needs ~3GB VRAM, can't fit alongside llama3 + SoVITS

## VIP Knowledge System
VIP profiles provide deep biographical context for special guests.

### Adding a New VIP
1. Create JSON file: `server/data/vip_profiles/<name>.json`
2. Profile loads automatically at server startup via `load_all_vip_profiles()`
3. Memories injected into Qdrant with negative person_id (deterministic hash)

### JSON Profile Schema
```json
{
  "name": "Full Name",
  "aliases": ["Nickname1", "Nick2"],
  "hometown": "City, State",
  "age": 25,
  "birthday": "Month Day, Year",
  "education": { "university": "...", "degree": "...", "graduation_year": 2023 },
  "titles": ["Birthday VIP"],
  "family": { "dad": "Name", "mom": "Name" },
  "projects": [{ "name": "...", "description": "...", "tech_stack": ["..."] }],
  "skills": ["Python", "..."],
  "personality_notes": ["Loves X", "..."],
  "mario_conversation_hooks": ["Ask about X!", "Mention Y!"],
  "memorial": {
    "person": "Memorial Person Name",
    "relationship": "aunt",
    "born": "1960", "passed": "2025",
    "note": "Take a moment of silence"
  },
  "memories": ["Fact 1", "Fact 2", "..."]
}
```

### Memorial Events
- Fires at 45 minutes into the party (configurable in `idle_behavior.py`)
- Two phases: moment of silence → everyone take a shot
- Triggered by `check_memorial_event()` in idle loop

## TTS Pronunciation Guide
Add pronunciation fixes in `server/gpt_sovits_server.py` → `clean_text_for_tts()`:
```python
# Existing fixes:
"Bowser" → "the bad guy"
"Goomba" → "bad mushroom"
"Koopa" → "Cooper"
"Hoppenstedt" → "Hoppenstead"
```
**Note:** GPT-SoVITS subprocess must be restarted for changes to take effect.

## Recent Bug Fixes (2026-03-31 → 2026-04-01)
- **LLM 404**: Fixed hardcoded `llama3:8b` → `llama3` in hardware.py
- **TTS recursion**: Fixed monkey-patch closure bug in tts.py
- **Health endpoint**: Fixed `NightProgression.current_phase` → `get_time_phase()`
- **Response truncation**: Removed `\n\n` and `[` stop sequences, raised 120→300 char cap
- **Token limits**: Bumped llm_num_predict (low: 25→120, med: 30→120, high: 40→150)
- **GPU detection**: Added nvidia-smi fallback for systems without torch
- **VIP bypass**: "know anything about me" now falls through to VIP-aware LLM pipeline
- **Idle guard**: Text input path gets post-response guard (matches audio path)
