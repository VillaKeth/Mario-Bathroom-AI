# Mario AI Party Bot — Project Context

## What This Is
An interactive Mario AI bathroom party bot. At a real house party, a Raspberry Pi/laptop runs Mario in the bathroom — he greets guests, plays games, tells jokes, sings, and comforts sick people. Designed for 8+ hour continuous operation.

## How to Run
```bash
# Setup (first time only):
setup.bat           # Windows
./setup.sh          # Mac/Linux

# Start server:
start_server.bat    # Windows
./start_server.sh   # Mac/Linux

# Then open: http://localhost:8765/chat
```

**Important**: The start scripts activate the `venv/` virtual environment automatically.
All Python dependencies (including PyTorch) are installed by setup.bat/sh into this venv.

---

## Architecture Overview

### Core Server
| File | Role |
|------|------|
| `server/main.py` | Central server: WebSocket event routing, LLM pipeline, greeting/exit flows, idle loop, TTS synthesis |
| `server/llm_router.py` | Dual-model LLM routing (creative + fast models via Ollama) |
| `server/mario_prompt.py` | Mario personality: context building, discovery hints, engagement scoring, guest typing |
| `server/command_handlers.py` | Command routing (games, compliments, motivation, name parsing), keyword triggers with word count guards, 30+ handler categories, 13 pop culture easter eggs |
| `server/game_handlers.py` | 16 party games with 492+ question/prompt items (trivia, karaoke, RPS, truth_or_dare, riddles, word_chain, hangman, hot_takes, would_you_rather, never_have_i_ever, simon_says, 20_questions, name_that_character, story_builder, rapid_fire, bathroom_dares) |

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
| `server/emotions.py` | Emotion detection, keyword-based inference fallback (26 emotions), mood tracking |
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
| `client/main.py` | Pygame client entry point, keyboard/admin command routing, health polling |
| `client/mario_display.py` | Display renderer (4K, 1-0 game triggers, F1 help, F3 chat history, F4 health overlay, F5 party mode, F6 leaderboard, F7 bg cycle, F8 bg auto-cycle, F11 fullscreen, F12 panic, adaptive typewriter, Ctrl+V paste) |
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

### Idle Message System (3-Layer Anti-Leak)
- **Post-response cooldown**: 15s after response, 10s safety net in `_idle_send_if_safe()`
- **Post-input cooldown**: 8s after user message, 5s safety net
- **Conversation-aware spacing**: 15-25s during active chat, 3-8s during silence
- Startup greeting is suppressed if user sends a message before TTS finishes

### Admin Endpoints
- `POST /admin/simulate_text` — send text through active WS connection (testing)
- `POST /admin/force_stop_game` — emergency game cancellation
- `GET /admin/game_stats` — game pool sizes, recent games, active game
- `GET /api/health` — server health, emotion, cache stats, timing
- `GET /leaderboard` — party leaderboard with categories and fun stats
- `GET /admin/party_summary` — comprehensive party state snapshot (requires restart to activate)
- `POST /admin/set_emotion` — force emotion change
- `POST /admin/announce` — broadcast announcement to client

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

### MANDATORY: Audio Verification During Live Testing
**See `.claude/rules/testing.md` for full rules.**
- ALWAYS verify audio playback when testing the running app — don't just read logs
- Check `_play_wav: playing` AND `_play_wav: done` in client logs
- Verify spoken text matches speech bubble content (check `mario says:` lines)
- For non-Mario characters: confirm ZERO Mario references in both text AND audio
- A test is NOT complete until audio has been confirmed playing and finishing

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
- **No ellipsis (`...`) in hardcoded strings** that go to TTS — use commas or periods
- Any server module with user-visible text should expose `set_character(name, display_name)` plus `_CHARACTER_NAME`/`_CHARACTER_DISPLAY_NAME` fallbacks so startup can swap characters cleanly.
- Generic/shared content must stay character-agnostic; deeply character-specific command flavor currently lives in `command_handlers.py` with runtime name substitution until it is moved into per-character YAML.
- `server/game_handlers.py` content pools must default to empty and be populated only from character YAML so missing game files never leak Mario data into other characters.

## Pygame Client UI
- **Two-strip header layout**: Zone 1 (Y=0-28) = title bar, Zone 2 (Y=28-50) = info strip
- **Speech bubble** starts at Y=58, stays visible while `_speaking` is True (timer only starts after audio ends)
- **Quick triggers**: Number keys 1-8 launch canned game/joke/song/dance prompts when not in keyboard mode
- **Admin controls**: Keyboard mode accepts slash commands like `/announce`, `/emotion`, `/memorial`, `/health`, `/leaderboard`, `/stats`, `/games`, `/stopgame`, `/reload`, `/reset`, `/pause`, `/sovits`
- **Health overlay**: F4 toggles cached `/api/health` details below the banner
- **Leaderboard overlay**: F6 toggles party leaderboard (auto-hides after 15s)
- **Panic button**: Secret triple-tap F12 within 2 seconds (hidden from hint bar — only owner knows)
- All header elements consolidated in `_draw_party_banner()` — no individual element drawing in `_draw()`

## Hardware Profiles

### Development Machine (Dev)
- **GPU**: Quadro P1000 (4GB VRAM) — detects as "low" tier
- **RAM**: 32GB
- **CPU**: 24-core
- **LLM**: Ollama running llama3 8B (fits in 4GB VRAM)
- **TTS**: GPT-SoVITS V2 subprocess (separate venv: `gpt_sovits_env`)
- **GPU detection**: nvidia-smi fallback (torch not installed in server venv)

### Party Deployment Machine (Threadripper) — NEVER FORGET THESE SPECS
- **CPU**: AMD Threadripper Pro 3995WX (64 cores / 128 threads)
- **RAM**: 256 GB DDR4 3200MHz
- **GPU**: EVGA RTX 3090 Ti FTW3 (24GB VRAM)
- **Hardware tier**: Will auto-detect as **ULTRA**
- **LLM**: gemma3:27b (quality, ~16GB) + llama3.1:8b (fast, ~5GB) — both fit in 24GB with room for TTS
- **LLM dual-model**: Models swap via Ollama keep_alive; never both loaded simultaneously
- **Note**: 70B Q4 (~39GB) does NOT fit in 24GB — would need partial CPU offloading. Possible but slower.
- **TTS workers**: 8 (auto-detected by hardware.py for ultra tier)
- **Context window**: 8192 tokens (ultra tier default)
- **Owner**: Friend of VillaKeth (NOT Jacob — Jacob is the birthday boy)

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

## Character System & Sprites

### Available Characters
| Character | Style | Sprites |
|-----------|-------|---------|
| `mario` | Classic Mario 3D figurine | ✅ Full set |
| `rudi` | Orange red panda, pink hoodie | ✅ 39/40 sprites |
| `sonic` | Modern 3D blue hedgehog | 🔄 In progress |
| `ani` | Pastel pink/lavender AI | ✅ Full set |
| 34× HSR chars | Anime 3D style | ⬜ Not started |

### Honkai Star Rail Characters (34 total)
stelle, march7th, danheng, himeko, welt, kafka, silverwolf, seele, blade_hsr, jingyuan, bronya_hsr, clara, fuxuan, jingliu, topaz_hsr, ruanmei, drratio, blackswan, sparkle_hsr, acheron, aventurine, robin_hsr, firefly, sunday, theherta, luocha, argenti, huohuo, gallagher, boothill, yunli, feixiao, lingsha, jiaoqiu

### Sprite Generation
- **Script:** `client/generate_character_poses.py` — generates AI sprites via Pollinations.ai + rembg
- **Batch:** `batch_generate_hsr.py` — automated batch generation with progress tracking
- **Setup:** `setup_hsr_characters.py` — creates character directories + YAML configs
- **API:** Pollinations.ai (free, rate-limited ~40-50 images before 402 errors)
- **Rate limit recovery:** 8 retries with 20s×attempt exponential backoff
- **Each sprite:** ~2-3 minutes with rate limiting, ~40 sprites per character
- **`model=flux` parameter MUST NOT be used** — causes HTTP 402
"Peach" → "Peech"
"Princess" → "the princess"
"Luigi" → "Looigi"
"Yoshi" → "Yoh shee"
"Daisy" → "Dayzee"
```
Year-to-words: `2024` → `twenty twenty four` (2000-2099 range).
GPT-SoVITS subprocess must be restarted for pronunciation changes to take effect.

## Audio Normalization
All TTS output (GPT-SoVITS and Edge+RVC paths) is peak-normalized to -3dB via `_normalize_audio()` in `server/tts.py`. Ensures consistent volume regardless of source engine.

## TTS Pre-Clean Pipeline
`_preclean_tts_text()` in `server/tts.py` sanitizes ALL text BEFORE cache key generation or any TTS engine:
- `...` / `…` / `..` → `, ` (natural pause)
- Smart quotes removed, em/en dashes → commas, asterisks stripped
- Artifact cleanup: leading commas, double commas, comma-after-punctuation, trailing commas
- Empty text after cleaning → `_EMERGENCY_SILENCE` (inline WAV)

## TTS Cache System
- **Disk cache**: `server/data/tts_cache/` — `.wav` + `.key` file pairs (MD5 hash filenames)
- **In-memory cache**: `SizeLimitedCache` (500MB / 2000 entries, LRU eviction)
- **Cache key format**: `{EDGE_VOICE}:{cleaned_text}:{rate}:{pitch}`
- **Precache at startup**: `precache_phrases()` pre-generates 51 common phrases
- **Cache scripts**: `scripts/perfect_cache.py`, `scripts/perfect_cache_v2.py`

### ⚠️ CRITICAL: TTS Cache Update Convention
**Any change to TTS text preprocessing MUST also update the cache:**
1. After changing `_preclean_tts_text()` or TTS pipeline logic, run `tts.purge_stale_cache()` to remove entries whose cache keys no longer match post-cleaning
2. After changing pronunciation in `gpt_sovits_server.py`, delete affected cache entries (they have the old pronunciation baked in)
3. After changing hardcoded phrases in `mario_prompt.py` or `llm.py`, the old cached audio becomes orphaned — run purge to clean
4. `tts.clear_all_cache()` nukes everything (in-memory + optionally disk) — use when unsure
5. **NEVER skip this step** — stale cache = bad audio at the party

## TTS Prompt Guidance
`MARIO_SYSTEM_PROMPT` includes TTS RULES section:
- Keep sentences under 15 words
- Avoid ALL CAPS (sounds robotic in TTS)
- No ellipsis or em-dashes (causes pauses)
- Spell out numbers (TTS reads digits oddly)
- No written sound effects (e.g., don't write "Wahoo!")

## Test Count
**636 tests** across 17 test files (as of v3.11).

## Character Creator Wizard — Design Principles

The wizard at `http://localhost:8766` is the PRIMARY way users create characters. It must be:

1. **Complete end-to-end** — When the wizard finishes, the character is 100% ready to run. No manual steps.
2. **Sprites generated as part of the process** — NOT optional or separate. The wizard generates all sprites.
3. **Content pools generated as part of the process** — Idle messages, game pools, extras are ALL generated. NOT skippable by default.
4. **Start Server must work** — The button updates config.json AND tells the user exactly how to launch (or auto-launches).
5. **Zero coding knowledge required** — A non-technical person should be able to clone the repo, run the wizard, and have a working AI character. No config files, no terminal commands, no code editing.
6. **Think "local character.ai"** — Mix and match photos, voices, models, backgrounds. One-stop-shop.

### The Flow
```
Clone repo → run setup.bat → wizard opens → fill in character details → 
sprites generate → content pools generate → click Start → character is LIVE
```

### What Must Happen Before "Character Created" Screen
- ✅ character.yaml written
- ✅ System prompt + all prompts generated
- ✅ Sprites generated (placeholder immediately, AI sprites in background)
- ✅ Content pools generated (idle, games, extras) via Ollama/API
- ✅ Voice configured and ready
- ✅ config.json updated to point to new character

## Remaining Work
See `TODO.md` for full task tracking.
