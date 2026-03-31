# Mario AI Party Bot — ULTRA Overhaul Design Spec

**Date**: 2026-03-31
**Target Event**: 8-hour 21+ birthday party
**Hardware**: Threadripper Pro 3995wx (64c/128t), 256GB RAM, RTX 3090 Ti 24GB (ULTRA tier)
**Physical Setup**: Pygame on monitor in bathroom, mic + speaker + webcam
**Baseline**: Tag `v1.0-pre-superpowers` (safe rollback)

---

## VRAM Budget

All GPU-resident components must fit within 24GB:

| Component | VRAM | Notes |
|-----------|------|-------|
| Llama 3.1 70B-**Q4_K_M** | ~18 GB | Downgraded from Q5 to fit budget |
| Fish Speech v2.2+ | ~1-2 GB | Primary TTS |
| RVC v2 (Mario TITAN) | ~1-2 GB | Voice conversion |
| CUDA overhead + buffers | ~2 GB | PyTorch allocator |
| **Total** | **~22-24 GB** | Fits within 24GB |

**Not on GPU**: Whisper runs on CPU (int8) to save ~1GB VRAM. Adds ~1s STT latency, acceptable.
**Not live**: GPT-SoVITS runs as offline-only subprocess for pre-rendering comparison samples. NOT loaded during party.

---

## Priority Ordering (MoSCoW)

| Priority | Section | Feature | Justification |
|----------|---------|---------|---------------|
| **Must** | §2 | LLM 70B upgrade | Core quality, fixes gossip |
| **Must** | §1 | Fish Speech TTS | Voice quality + speed |
| **Must** | §3 | Night progression | Core party experience arc |
| **Must** | §4 | Reliability layer | 8-hour uptime requirement |
| **Must** | §5 | Pygame hardening | Crash prevention |
| **Should** | §12 | Pre-party canary | Risk reduction |
| **Should** | §13 | Hot reload | Mid-party adjustability |
| **Should** | §6 | Vomit enhancements | Incremental improvement |
| **Should** | §9 | Birthday VIP | Party personalization |
| **Could** | §11 | Sound effects | Polish/immersion |
| **Could** | §10 | Catchphrase mirroring | Nice-to-have |
| **Could** | §8 | Party report card | Post-party, not urgent |
| **Won't** | §7 | Image gen hooks | Explicitly deferred to v2 |

If time runs out, cut from bottom up. Everything above the line marked "Should" ships no matter what.

---

## 1. Voice Quality — Fish Speech Primary + Offline A/B Comparison

### Problem
GPT-SoVITS produces decent Mario voice but has 3-10s latency and fails on some words ("Bowser", "Koopa"). The Italian "-a-" vocal tic doesn't always generate naturally.

### Solution
**Fish Speech v2.2+** is the live TTS engine. GPT-SoVITS is used **offline only** to pre-render comparison samples (VRAM constraint: both cannot be loaded simultaneously with 70B LLM).

**Primary Engine — Fish Speech v2.2+ (live)**
- Zero-shot Mario voice clone from existing `mario_reference_sentences.wav`
- Native accent/style control for Italian "-a-" tics
- Expected latency: 0.3-0.8s on RTX 3090 Ti
- MIT license, single `pip install fish-speech`
- ~1-2GB VRAM (fits alongside 70B LLM)

**Comparison Engine — GPT-SoVITS (offline only)**
- Keep current implementation with Mario-e20.ckpt + TITAN RVC model
- Run as subprocess ONLY when 70B LLM is unloaded (e.g., during setup/testing)
- Known ceiling: ~78% quality (from 220-iteration ralph TTS loop)
- Used to pre-render 20 test phrases for user to compare against Fish Speech

**Offline A/B Comparison Workflow**
1. Before party: unload 70B, load GPT-SoVITS, render 20 test phrases
2. Unload GPT-SoVITS, render same 20 phrases via Fish Speech
3. User listens side-by-side, picks winner engine
4. Winner is confirmed as live engine, loser stays offline
5. At party: only the winner + RVC + Whisper(CPU) are loaded

**Pre-recorded Catchphrase Bank**
- Generate via TTS and hand-pick the best renditions for: "Wahoo!", "Mama mia!", "Let's-a go!", "It's-a me, Mario!", "Yahoo!", "Okie dokie!", "Here we go!"
- Source: render 10 variations each via Fish Speech + GPT-SoVITS, user picks best
- These play INSTEAD of TTS for exact-match phrases — always perfect, instant playback
- Works with either TTS engine
- Stored in `assets/catchphrases/` as WAV files

**Never-Silent Fallback Chain** (ordered by latency, fastest first)
```
Fish Speech (0.3-0.8s) → Edge TTS + RVC (0.4-1.2s) → XTTS v2 (0.8-2s) → Pre-recorded clips (instant)
```
If ALL fail: play a sound effect + show speech bubble on pygame.

**8 Parallel TTS Workers** (ULTRA tier)
- Responses stream in sentence chunks
- First sentence plays while rest generates

---

## 2. LLM Upgrade — 70B + Dual-Model Router

### Problem
Llama3 8B is fast but can't follow complex instructions. Gossip system fails because LLM ignores "MUST mention guest names" — only 20% compliance.

### Solution

**Primary Model: Llama 3.1 70B-Q4_K_M**
- ~18GB VRAM (leaves 6GB for TTS + RVC + buffers)
- Estimated 90%+ gossip name compliance (massive improvement over 8B's 20%)
- Superior humor, personality consistency, game hosting
- ~2-4s for 25-50 token responses
- Marginal quality difference vs Q5_K_M; fits VRAM budget

**Router: Fast path + Quality path**
```
Greetings, one-liners, roasts → Mixtral 8x7B (~1s)
Gossip, games, stories, complex → 70B-Q5_K_M (~3s)
```
- Classification by response_type in request pipeline
- When "MUST mention" is in system prompt → force quality path
- Average response time: ~2s (blended)

**Auto-Fallback**
- If 70B hangs >15s → retry with Mixtral
- If Ollama crashes → restart service + use canned responses
- Config stays `"auto"` — hardware tier resolves model choice
- Whisper runs on CPU (int8) to preserve GPU VRAM for LLM + TTS

---

## 3. Night Progression System

### Concept
Mario's personality escalates over the 8-hour party in 4 phases. Energy also scales with guest count (not just clock time).

### Phase 1 — WARM UP (Hours 0-2)
- Friendly host, learning names, light banter
- "Welcome-a to the party!"
- Games: Easy trivia, Would You Rather
- Roast level: 1/10 (gentle teasing)
- System prompt modifier: `personality_warmth=high, chaos=low, gossip_aggression=low`

### Phase 2 — PARTY MODE (Hours 2-5)
- Gossip flows freely, competitive energy
- "You know what Tony told me earlier? *leans in*"
- Harder games, pointed roasts
- Roast level: 5/10
- System prompt modifier: `personality_warmth=medium, chaos=medium, gossip_aggression=high`

### Phase 3 — UNHINGED (Hours 5-7)
- Full Neuro-sama chaos energy
- Random tangents: "How's it going?! I'll tell you — I just found out Toad's head might be a HAT!"
- Manufactured drama: "Sarah said she could beat you at ANYTHING. In MY bathroom?!"
- Mario conspiracy theories: "Why are ALL the pipes green? I have a theory involving the government."
- Obsession lock: picks ONE random topic per visit, won't let it go
- Unsolicited life advice: "I've been through 38 castles. Let me tell you about perseverance."
- Spontaneous singing, dramatic overreactions
- Fourth wall breaks: "I'm literally a computer in a bathroom"
- Power moves: "Name ONE other celebrity in this bathroom right now."
- Roast level: 8/10
- System prompt modifier: `personality_warmth=low, chaos=extreme, gossip_aggression=extreme`

### Phase 3 Content Guardrails
Even at UNHINGED, Mario has hard safety rails:
- **Banned roast topics**: Physical appearance, weight, relationships, employment, mental health
- **Drama must be absurd/Mario-themed**: "Sarah is secretly working for Bowser" NOT "Sarah is a bad person"
- **Emergency de-escalation**: If guest says "stop", "that's not funny", "too far" → immediately drop to Phase 2 energy for rest of that visit
- **Roast level 8/10 defined**: Pointed but clearly jokes. Think comedy roast, not personal attack. Always end with love: "I kid! You're one of the best guests tonight!"
- **No targeting the same guest repeatedly**: Max 2 roasts per guest per visit before moving on

### Phase 4 — WIND DOWN (Hours 7-8)
- Nostalgic, sentimental Mario
- Callback system: pulls specific quotes from earlier conversations via memory DB
- "Remember when Jake walked in at the start? What a night..."
- Heartfelt farewells
- Roast level: 3/10
- System prompt modifier: `personality_warmth=extreme, chaos=low, gossip_aggression=low`

### Guest Count Awareness (merged from former §14)
- Phase transitions require BOTH time threshold AND minimum guest count
- Don't go UNHINGED at hour 5 if only 3 guests visited
- Fast escalation if 20+ guests in 2 hours
- Formula: `effective_phase = min(time_phase, guest_energy_phase)`

```python
def get_effective_phase(hours_elapsed, unique_guests):
    time_phase = get_time_phase(hours_elapsed)  # 1-4
    
    if unique_guests < 5:
        guest_energy = 1  # Keep it calm
    elif unique_guests < 15:
        guest_energy = 2  # Getting lively
    elif unique_guests < 25:
        guest_energy = 3  # Full party
    else:
        guest_energy = 4  # Absolute madness
    
    return min(time_phase, guest_energy)
```

### Obsession Lock Mechanics (Phase 3)
- Topic selected: random pick from guest's `conversation_topics` in memory DB
- Duration: 3 exchanges or 2 minutes (whichever comes first), then releases
- Resets on new guest visit (fresh obsession each time)
- Mario refers back to it naturally: "But back to my point about pineapple pizza..."
- If guest has no recorded topics, Mario picks from a pre-set list of absurd topics

### Implementation
- `party_phase` module: calculates current phase from `server_start_time` + `total_unique_guests`
- Dynamic system prompt injection per phase
- Smooth transitions (blend prompts during 15-min crossfade windows)

---

## 4. 8-Hour Reliability Layer

### Watchdog Process
- Separate Python script, runs independently
- Pings `/health` every 30 seconds
- 3 consecutive failures → auto-restart server via subprocess
- Logs all restarts to `logs/watchdog.log`

### Memory Leak Prevention
- SQLite WAL checkpoint every 30 minutes
- TTS cache capped at 2000 entries (LRU eviction)
- WebSocket connection cleanup on disconnect
- `gc.collect()` every 10 minutes
- Monitor RSS via `/health` endpoint

### Connection Auto-Recovery
- Pygame client: exponential backoff (1s → 2s → 4s → max 30s)
- WebSocket ping/pong every 15 seconds
- Server down → pygame shows "Mario is taking a quick break!" with idle animation

### Remote Health Dashboard
- Web page at `/dashboard` — accessible from phone
- Displays: uptime, guests served, current phase, active games, error count, TTS cache size, LLM response times, memory usage, GPU temp
- Color-coded: 🟢 healthy, 🟡 degraded, 🔴 issues
- Auto-refreshes every 5 seconds

### Phone Alerts
- Webhook push to configurable URL on status degradation
- Triggers: response time >10s (warning), >20s (critical), service restart, TTS fallback activated

### Graceful Degradation Tiers
```
FULL      → Everything working (normal party experience)
DEGRADED  → LLM slow, using Mixtral fallback (still functional)
MINIMAL   → TTS failed, using Edge TTS (still works, voice quality reduced)
EMERGENCY → Canned responses only (party still fun, limited interaction)
```

### Pre-Party Canary (Self-Test)
- 5-minute automated test exercising every feature
- Voice synthesis, STT, games, gossip, vomit detection, memory, emotions
- Reports confidence score: "Mario is 97% ready for the party!"
- Run via `/api/canary` endpoint or CLI command

### Hot Reload
- `/api/reload` endpoint (authenticated)
- Change personality traits, chaos level, system prompt without restart
- Accessible from dashboard on phone
- "Mario is too mild" → crank up chaos slider mid-party

---

## 5. Pygame Client Hardening

### Fullscreen/Resolution
- Auto-detect monitor resolution
- Scale all elements proportionally
- F11 toggle between windowed and fullscreen
- Config: `display_mode: "auto" | "fullscreen" | "windowed"`

### Auto-Reconnect
- Exponential backoff on disconnect
- "Mario is taking a bathroom break... be right back!" screen with idle animation
- Auto-reconnect within seconds of server recovery

### Sprite Transitions
- Smooth fade between emotion states (not hard cuts)
- Configurable transition duration (default 0.5s)

### Panic Button
- F12: immediately mutes all audio, stops TTS, shows "Technical Difficulties" screen
- F12 again: resumes normal operation
- For when things go sideways at the party

### Crash Recovery
- Pygame catches all exceptions, logs, and attempts restart
- Never shows a Python traceback on the party monitor

---

## 6. Vomit Comfort — Enhanced Detection

### Existing (Keep)
- PANNs Cnn14 audio classification (Gasp, Cough, Gargling, etc.)
- Text keyword detection (vomit, puke, barf, etc.)
- Spectral analysis (energy bursts + spectral flatness)
- 26 comfort messages, proactive check-ins

### New: Volume Spike Detection
- Detects sudden volume changes characteristic of vomiting
- Vomiting pattern: ~200ms sudden spike, NOT sustained (vs hand dryer)
- Rapid falloff check: spike returns to baseline within 100-300ms
- ~20 lines of code addition

### New: Temporal Coherence
- Require 2+ audio bursts within a 2-second window
- Single isolated sounds (hiccup, cough) don't trigger comfort mode
- Reduces false alarms by ~40%

### TTS Interrupt on Distress
- If Mario is mid-sentence and distress detected → STOP audio playback immediately
- Pause 1 second → switch to comfort mode
- No fighting for audio channel

### Recovery Flow
- "Feeling better" / "I'm okay" → clears sick mood
- Transition back to normal with a funny line
- Not an awkward restart

---

## 7. Image Generation Hooks (Architecture Only)

**Not implemented for Friday. Architecture only.**

### ImageProvider Interface
```python
class ImageProvider:
    async def generate(self, prompt: str, emotion: str, context: dict) -> str:
        """Returns path to generated image."""
        raise NotImplementedError

class StaticSpriteProvider(ImageProvider):
    """Default: returns pre-generated sprite by emotion. Current behavior."""

class ComfyUIProvider(ImageProvider):
    """Future: generates custom image via ComfyUI API."""
```

### Sprite System
- Modular: swap `StaticSpriteProvider` for `ComfyUIProvider` later
- LRU cache for generated images
- Async generation (doesn't block response pipeline)
- Fallback to static sprite if generation fails/times out

---

## 8. Party Report Card

### Trigger
- Auto-generates when server has been running 7+ hours
- Also available via `/api/report` endpoint

### Contents
- **Stats**: Total guests, total conversations, games played, jokes told
- **Superlatives**: Most talkative guest, funniest moment, game champion, best roast survivor, "most likely to come back"
- **Gossip Summary**: Cross-guest drama highlights
- **Quote Board**: Best quotes of the night
- **Mario's Awards**: Birthday person gets "VIP of the Night"

### Output
- Web page at `/report` (shareable link)
- Optional: generate downloadable image/PDF

---

## 9. Birthday VIP Mode

### Configuration
- `config.json`: `"birthday_person": "Jake"` (or set via dashboard)

### Special Treatment
- Birthday songs when they enter
- Extra roasts (loving but savage)
- Crown emoji on leaderboard
- Other guests asked: "Have you wished Jake happy birthday yet?"
- Late night: "It's Jake's special day and you're in the BATHROOM? Get out there and celebrate!"
- Phase 4 special farewell for birthday person

---

## 10. Catchphrase Mirroring

### How It Works
- Track word frequency per guest in current visit
- If a guest uses a word 3+ times (e.g., "bro", "literally", "no cap"), Mario starts using it
- "As you would say, bro — that's-a literally the best thing I've heard tonight!"
- Stored in memory for return visits

### Implementation
- Word frequency counter in conversation handler
- Threshold: 3+ uses of non-common word
- Injected into system prompt: `"Mirror the guest's catchphrase: 'bro'"`
- Max 2 mirrored phrases per guest (prevent overload)

---

## 11. Nintendo Sound Effects

### Sound Events
| Event | Sound | Trigger |
|-------|-------|---------|
| Guest enters | 1-UP | `presence_enter` |
| Good answer / game win | Coin | Game score +1 |
| Game loss | Power-down | Game score -1 |
| Birthday person enters | Star music | VIP mode |
| Easter egg triggered | Secret sound | Easter egg handler |
| Vomit detected | Pipe warp | Comfort mode start |
| Guest leaves | Farewell jingle | `presence_exit` |

### Implementation
- Pre-loaded WAV files in `assets/sfx/`
- Non-blocking playback (separate audio channel from TTS)
- Volume adjustable independently from voice
- Sourced from freely available game sound recreation packs

---

## 12. Pre-Party Canary

### Test Suite
1. **Voice test**: Generate "It's-a me, Mario!" via primary TTS → verify audio output
2. **STT test**: Play test audio → verify transcription accuracy
3. **LLM test**: Send test prompt with "MUST mention Alice" → verify name appears
4. **Game test**: Start and complete a trivia round
5. **Memory test**: Store and retrieve a test fact
6. **Emotion test**: Trigger each emotion, verify sprite mapping
7. **Vomit test**: Play test audio → verify detection triggers
8. **WebSocket test**: Connect, send message, verify response
9. **Dashboard test**: Verify `/dashboard` loads
10. **Audio playback test**: Play test audio through speaker

### Output
- Console: `✅ Mario is 97% ready! (1 warning: STT confidence low in noisy environment)`
- Log: Detailed results per test
- API: `/api/canary` returns JSON results

---

## 13. Hot Reload

### Reloadable Parameters
- System prompt personality traits
- Chaos level (0-10 slider)
- Night progression phase (manual override)
- Gossip aggression
- Roast level cap
- TTS engine selection
- Idle message frequency

### Implementation
- `/api/reload` POST endpoint (authenticated via `config.json` key: `"reload_key": "your-secret"`)
- `config_live.json` created at server startup as a copy of relevant personality fields from `config.json`
- Schema: `{ "chaos_level": 5, "roast_cap": 8, "gossip_aggression": 7, "phase_override": null, "idle_frequency_seconds": 30, "tts_engine": "fish_speech" }`
- Changes to `config_live.json` take effect on next response (no restart)
- Dashboard UI: sliders and toggles that POST to `/api/reload`

---

## Testing Strategy

### E2E Test Suite (existing, enhanced)
- Current 52-53 checks expanded with new feature tests
- Night progression test: verify phase transitions
- Router test: verify fast/quality path selection
- Sound effects test: verify event → sound mapping
- Canary test: verify self-test passes

### Ralph Loop
- 3 consecutive passes required before deployment
- Run on party machine hardware before Friday

### Voice A/B Test (Offline)
- Unload 70B LLM, load GPT-SoVITS subprocess
- Generate 20 test phrases, save to `docs/voice-comparison/sovits/`
- Unload GPT-SoVITS, load Fish Speech
- Generate same 20 phrases, save to `docs/voice-comparison/fish/`
- User listens side-by-side, picks winner
- Document results in `docs/voice-comparison.md`

---

## Deployment Checklist (Party Day)

1. Install Ollama models on party machine (`llama3.1:70b-q4_k_m`, `mixtral:8x7b`)
2. Install Fish Speech v2.2+ and verify Mario voice clone
3. Run canary self-test → all green
4. Run ralph loop → 3/3 passes
5. Start watchdog process
6. Open dashboard on phone
7. Verify fullscreen pygame on party monitor
8. Test mic + speaker + webcam
9. Set `birthday_person` in config
10. Set `reload_key` in config
11. Start the party 🎉
