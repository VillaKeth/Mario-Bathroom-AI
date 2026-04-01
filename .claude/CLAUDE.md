# Mario AI Party Bot — Project Context

## What This Is
An interactive Mario AI bathroom party bot. At a real house party, a Raspberry Pi/laptop runs Mario in the bathroom — he greets guests, plays games, tells jokes, sings, and comforts sick people. Designed for 8+ hour continuous operation.

## Architecture
```
server/main.py          — FastAPI + WebSocket server (port 8765)
server/command_handlers.py — All command routing, games, sick detection
server/tts.py           — GPT-SoVITS + Edge TTS + RVC voice pipeline
server/stt.py           — Whisper-based speech-to-text
server/audio_distress.py — PANNs Cnn14 model for retching/distress audio detection
server/party_stats.py   — Leaderboard, visitor tracking, party analytics
server/party_gossip.py  — Cross-visitor social dynamics
server/memory.py        — SQLite memory (facts, conversations, people) + dual-write to Qdrant
server/memory_semantic.py — Qdrant vector DB wrapper (fastembed all-MiniLM-L6-v2, 384-dim)
server/vip_knowledge.py — VIP profile loader (JSON profiles → Qdrant injection)
server/idle_behavior.py — Idle behavior, autonomous actions, timed events
web/mario_chat.html     — Browser chat interface at /chat endpoint
client/                 — Pygame desktop client with 74 AI poses
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

## Key Technical Details

### Response Pipeline
1. User sends text via WebSocket → `command_handlers.py` checks for games/commands
2. If no command match → LLM (Ollama qwen2:1.5b) generates response
3. Response → TTS (GPT-SoVITS primary, Edge TTS fallback) → audio sent back
4. Cached responses are instant (0.0s), LLM responses 3-15s

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

## Testing Status (as of 2026-03-27)
- **E2E Browser Test**: 40/45 passed (53+ min session, 107 audio clips)
- **Stress Test**: 52/52 passed, 8-hour endurance verified
- **All features working**: games, chat, idle, emotions, sick care, recovery, friend-sick
- **Known minor issues**: idle message variety, trivia not interactive Q&A

## Coding Conventions
- `print()` for logging (NOT `logger` — command_handlers has no logger import)
- WebSocket message type must be `"mario_response"` (not `"response"`)
- Game state in `state_current["_active_game"]` dict
- Sick mood tracked in `state_current["_detected_mood"]`
- Debug flags: `DEBUG_AUTH`, `DEBUG_API`, etc. (default True for new features)
- Always use `general-to-specific` naming: `pointBase`, `pointNext`, etc.

## Config
- `config.json` at repo root — LLM model, TTS settings, timeouts
- Hot-reload via `/config/reload` endpoint
- LLM keepalive: 30min keep_alive + 4min ping

## Remaining Work
See `TODO.md` for full task tracking. Key remaining:
- Create reusable stress test skill
- Idle message variety improvement
- Consider LLM upgrade from qwen2:1.5b to 7B+
- Sprite system overhaul
