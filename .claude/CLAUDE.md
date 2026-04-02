# Mario AI Party Bot — Project Context

## What This Is
An interactive Mario AI bathroom party bot. At a real house party, a Raspberry Pi/laptop runs Mario in the bathroom — he greets guests, plays games, tells jokes, sings, and comforts sick people. Designed for 8+ hour continuous operation.

## How to Run
```bash
cd server && python main.py    # Starts on ws://localhost:8765
python client/main.py          # Pygame desktop client
```

---

## Architecture Overview

### Core Server
| File | Role |
|------|------|
| `server/main.py` | Central server: WebSocket event routing, LLM pipeline, greeting/exit flows, idle loop, TTS synthesis |
| `server/llm_router.py` | Dual-model LLM routing (creative + fast models via Ollama) |
| `server/mario_prompt.py` | Mario personality: context building, discovery hints, engagement scoring, guest typing |
| `server/command_handlers.py` | Slash commands (`/games`, `/leaderboard`, `/report`, etc.) + sick detection |
| `server/game_handlers.py` | 10+ party games (trivia, karaoke, RPS, truth_or_dare, riddles, word_chain, hangman, hot_takes, would_you_rather, never_have_i_ever, simon_says, 20_questions) |

### Memory & Knowledge
| File | Role |
|------|------|
| `server/memory.py` | Dual-write memory: SQLite (persistence) + Qdrant (vector search) |
| `server/memory_semantic.py` | Qdrant vector search for semantic memory retrieval (fastembed all-MiniLM-L6-v2, 384-dim) |
| `server/vip_knowledge.py` | VIP guest profiles (Jacob Hoppenstedt birthday boy, etc.) — injected via Qdrant semantic search, NOT hardcoded |
| `server/face_memory.py` | SQLite face encoding storage + Euclidean matching (128-dim vectors) |

### Party Systems
| File | Role |
|------|------|
| `server/party_gossip.py` | Cross-visitor gossip: rivalries, alliances, trending topics, party recaps, return visit intel, gossip seed questions, speech trait analysis, dramatic moments, guest titles |
| `server/party_stats.py` | Visit tracking, engagement metrics, milestone detection |
| `server/night_progression.py` | 4-phase party arc: `early_night` → `peak_party` → `late_night` → `after_hours` |
| `server/idle_behavior.py` | Idle behaviors: mumbles, songs, jokes, loneliness arc (3 tiers), gossip recap, memorial events |
| `server/birthday_vip.py` | Birthday person detection + enhanced interactions |
| `server/catchphrase_mirror.py` | Detects and mirrors guest catchphrases via repetition analysis |
| `server/emotions.py` | Emotion detection and tracking |
| `server/safety_filter.py` | Character-break safety filter — prevents Mario from breaking character |

### TTS / Voice
| File | Role |
|------|------|
| `server/tts_router.py` | TTS routing: GPT-SoVITS → Fish Speech → Edge TTS → emergency silence (4-tier fallback) |
| `server/tts.py` | GPT-SoVITS + Edge TTS + RVC voice pipeline, precaching |
| `server/fish_speech_tts.py` | Fish Speech TTS wrapper (library not yet available, graceful fallback) |
| `server/gpt_sovits_server.py` | GPT-SoVITS subprocess management + pronunciation fixes |
| `server/stt.py` | Whisper-based speech-to-text |
| `server/audio_distress.py` | PANNs Cnn14 model for retching/distress audio detection |
| `server/sound_events.py` | SFX playback, queuing, and volume control |

### Infrastructure & Reliability
| File | Role |
|------|------|
| `server/watchdog.py` | Process monitoring and auto-restart (full → degraded → minimal) |
| `server/canary.py` | Pre-party smoke test (LLM, TTS, WebSocket, memory DB, etc.) |
| `server/hot_reload.py` | Config hot reload without restart via `config_live.json` |
| `server/hardware.py` | GPU detection, 5 hardware tiers (LOW → MEDIUM → HIGH → VERY_HIGH → ULTRA) |
| `server/dashboard.py` | Real-time stats dashboard: health badges, GPU temp, cache stats, alerts |
| `server/party_report.py` | Post-party analytics report generation |

### Client
| File | Role |
|------|------|
| `client/main.py` | Pygame client entry point |
| `client/mario_display.py` | Display renderer (4K, F3 chat history, F11 fullscreen, adaptive typewriter) |
| `client/ws_client.py` | WebSocket client connection handler |
| `client/person_detector.py` | YOLO v8n person detection + face_recognition encoding |
| `client/presence.py` | Webcam presence detection (exclusive cv2.VideoCapture) |
| `client/audio_capture.py` | Microphone input capture |
| `client/audio_playback.py` | Audio playback management |
| `client/sound_effects.py` | Client-side SFX |

---

## Key Architectural Patterns

### Memory: Dual-Write (SQLite + Qdrant)
- **SQLite** (`server/data/memory.db`): Source of truth for structured data (people, conversations, facts)
- **Qdrant** (`server/data/qdrant_memories/`): Semantic vector search over all memories
- **fastembed** (all-MiniLM-L6-v2): 384-dim embeddings, CPU-only, zero VRAM impact
- Every `save_fact`/`save_conversation` writes to both SQLite and Qdrant
- First startup auto-migrates existing SQLite data into Qdrant (backfill)
- Memory cap: 50 items injected into LLM context

### TTS: 4-Tier Fallback Chain
1. **GPT-SoVITS V2** — primary, highest quality (Charles Martinet RVC models)
2. **Fish Speech** — wrapper ready in `fish_speech_tts.py`, graceful fallback if unavailable
3. **Edge TTS** — instant fallback (with or without RVC post-processing)
4. **Emergency silence** — never returns None, always produces valid output

### LLM: Dual-Model Routing
- **Fast model**: Quick responses (greetings, short answers)
- **Quality model**: Complex queries, games, emotional moments
- Automatic routing based on query complexity analysis via `llm_router.py`

### Gossip System
- Tracks rivalries, alliances, trending topics across ALL visitors
- Speech trait analysis and dramatic moment detection
- Guest titles assigned dynamically
- Party recaps for newcomers (FOMO teasers)
- Return visit intel (gossip-based dossier for returning guests)
- Gossip seed questions injected at 20% probability when gossip < 10 entries

### Night Progression
- 4 phases: `early_night` → `peak_party` → `late_night` → `after_hours`
- 15-minute crossfade between phases
- Adjusts Mario's personality: gossip aggression, chaos level, energy
- Guest energy caps per phase (prevents over-hype during wind-down)
- `banned_topics` per phase (e.g., no sad topics during PARTY_MODE)
- `party_start_time` persisted in SQLite (survives restarts)

### VIP Knowledge
- JSON profiles in `server/data/vip_profiles/<name>.json`
- Loaded at startup via `load_all_vip_profiles()` → injected into Qdrant
- Memories injected with negative `person_id` (deterministic hash)
- **NOT hardcoded responses** — surfaced via semantic search during conversation

### Response Pipeline
1. User sends text via WebSocket → `command_handlers.py` checks for games/commands
2. If no command match → LLM generates response with VIP fact injection + gossip context
3. Response → TTS (fallback chain) → audio sent back via WebSocket
4. Thinking filler ("Let me think!") sent while LLM generates (`is_thinking_filler` flag)

---

## Config
- **`config.json`** — LLM model, TTS settings, timeouts, face detection, `birthday_person_name`, party metadata
- **`config_live.json`** — Runtime-editable personality tuning (hot-reloaded by `server/hot_reload.py`)
- Hot-reload via `/config/reload` endpoint (full config) or LiveConfig (personality only)

### Key Config Fields
- `birthday_person_name` — VIP birthday guest name
- `models` — LLM model configuration for Ollama
- TTS settings — engine preferences, cache paths
- Party metadata — location, theme, expected guest count

## Port
- **WebSocket server**: `ws://localhost:8765` (default)

---

## Testing
- **624 tests** across **37 test files** in `tests/`
- Test files cover: command_handlers, game_handlers, idle_behavior, llm_router, memory_semantic, night_progression, party_gossip, party_modules, vip_knowledge, edge_cases, tts_router, watchdog, canary, hot_reload, face_memory, person_detector, fish_speech, and more
- E2E browser test, 8-hour stress test, integration tests all verified

---

## Git Workflow
- **Always use `git add <specific files>`** (not `git add -A`) — Qdrant `.lock` files in `server/data/qdrant_memories/` must not be committed
- Commit trailers: `Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>`

## Coding Conventions
- `print()` for logging (NOT `logger` — command_handlers has no logger import)
- WebSocket message type must be `"mario_response"` (not `"response"`)
- Game state in `state_current["_active_game"]` dict
- Sick mood tracked in `state_current["_detected_mood"]`
- Debug flags: `DEBUG_AUTH`, `DEBUG_API`, etc. (default True for new features)
- General-to-specific naming: `pointBase`, `pointNext`, `configDefault`, etc.

## Hardware Profile
- **GPU**: Quadro P1000 (4GB VRAM) — detects as "low" tier
- **RAM**: 32GB
- **CPU**: 24-core
- **LLM**: Ollama running llama3 8B (fits in 4GB VRAM)
- **TTS**: GPT-SoVITS V2 subprocess (separate venv: `gpt_sovits_env`)
- **GPU detection**: nvidia-smi fallback (torch not installed in server venv)

---

## VIP Profile Schema
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

## TTS Pronunciation Guide
Add fixes in `server/gpt_sovits_server.py` → `clean_text_for_tts()`:
```python
"Bowser" → "the bad guy"
"Goomba" → "bad mushroom"
"Koopa" → "Cooper"
"Hoppenstedt" → "Hoppenstead"
```
GPT-SoVITS subprocess must be restarted for pronunciation changes to take effect.

## Remaining Work
See `TODO.md` for full task tracking.
