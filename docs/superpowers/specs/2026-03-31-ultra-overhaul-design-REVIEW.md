# Design Spec Review: ULTRA Overhaul
**Reviewed**: 2026-03-31
**Spec**: `2026-03-31-ultra-overhaul-design.md`
**Verdict**: ⚠️ **ISSUES FOUND** — 2 critical, 4 major, 6 minor

---

## 🔴 CRITICAL ISSUES (must fix before implementation)

### C1. VRAM Budget Is Impossible — Section 2 vs Reality

The spec claims 70B-Q5_K_M fits the RTX 3090 Ti with "2GB headroom." This is false
when accounting for other GPU consumers already in the codebase:

| Component        | VRAM     | Source                        |
|------------------|----------|-------------------------------|
| Llama 3.1 70B    | ~22 GB   | Spec §2                      |
| RVC v2 (Mario)   | ~1-2 GB  | server/tts.py (always loaded) |
| Whisper large-v3 | ~1 GB    | server/stt.py (ULTRA tier)    |
| Fish Speech v2.2 | ~1-2 GB  | Spec §1 (new)                |
| **Total**        | **25-27 GB** | **Exceeds 24 GB**         |

**Consequences**:
- GPT-SoVITS (3-5 GB) cannot coexist with 70B LLM at all. The current
  subprocess-kill-after-batch architecture was designed for a 4.7 GB LLM leaving
  ~19 GB free. With 22 GB for the LLM, there's ~0 GB left.
- The A/B comparison (§1) between Fish Speech and GPT-SoVITS is physically
  impossible while 70B is loaded — both need GPU and there's no VRAM left.
- Even Fish Speech alone + 70B + RVC + Whisper = ~26 GB → OOM crash.

**Fix options (pick one)**:
1. **Use Q4_K_M quantization** (~18 GB) instead of Q5_K_M (~22 GB). Saves ~4 GB.
   Quality loss is marginal. This is the simplest fix.
2. **Run Whisper on CPU** (int8). Frees ~1 GB. Adds ~1s STT latency. Combine with Q4.
3. **Dynamic model swapping**: Unload 70B from Ollama before TTS regen, reload after.
   Complex, adds 30-60s latency per swap. Not viable for real-time party.
4. **Use Mixtral 8x7B as primary** (~26 GB at Q4, but with expert offloading fits in
   ~13-16 GB). Lower quality than 70B but fits the VRAM budget.
5. **Drop GPT-SoVITS entirely**, use Fish Speech only (no A/B comparison).

**Recommendation**: Option 1 + 2 + 5. Use Q4_K_M (~18 GB), Whisper on CPU, Fish Speech
as sole new TTS engine. Keep GPT-SoVITS as subprocess-kill architecture for offline
comparison only (not live A/B). Update VRAM budget table in spec.

---

### C2. No Feature Priority / Cut List — Entire Spec

The spec defines 14 sections of new work with zero prioritization. If time runs out
(likely — this is 4 days of work), the implementer has no guidance on what to cut.

**Fix**: Add a MoSCoW priority table:

| Priority | Feature | Justification |
|----------|---------|---------------|
| **Must** | §2 LLM 70B upgrade | Core quality improvement |
| **Must** | §3 Night progression | Core party experience |
| **Must** | §4 Reliability layer | 8-hour uptime requirement |
| **Must** | §1 Fish Speech (single engine, not A/B) | Voice quality |
| **Must** | §5 Pygame hardening | Crash prevention |
| **Should** | §12 Pre-party canary | Risk reduction |
| **Should** | §13 Hot reload | Mid-party adjustability |
| **Should** | §6 Vomit enhancements | Incremental improvement |
| **Should** | §9 Birthday VIP | Party personalization |
| **Could** | §11 Sound effects | Polish |
| **Could** | §10 Catchphrase mirroring | Nice-to-have |
| **Could** | §14 Guest count scaling | Already partially in §3 |
| **Could** | §8 Party report card | Post-party, not urgent |
| **Won't** | §7 Image gen hooks | Explicitly deferred |

---

## 🟡 MAJOR ISSUES (should fix, will cause implementation friction)

### M1. Fallback Chain Ordering Is Backwards — Section 1

The spec defines:
```
Winner → Loser → XTTS v2 → Edge TTS + RVC → Pre-recorded clips
```

XTTS v2 has **10-60s latency** (per codebase comments). Edge TTS has **~1s latency**.
Putting XTTS before Edge means a fallback scenario adds a 10-60s delay before reaching
the fast path. The current codebase correctly orders Edge before XTTS.

**Fix**: Swap order to `Winner → Loser → Edge TTS + RVC → XTTS v2 → Pre-recorded clips`.

---

### M2. No API Contracts for 6 New Endpoints — Sections 1, 4, 8, 12, 13

The spec introduces these endpoints with no request/response schema:

| Endpoint | Section | Missing |
|----------|---------|---------|
| `/api/voice-compare` | §1 | Request params, response format, audio encoding |
| `/dashboard` | §4 | Is this a new page or consolidation of existing 4 pages? |
| `/report` | §8 | Response format, how superlatives are calculated |
| `/api/canary` | §12 | Response JSON schema, pass/fail thresholds |
| `/api/reload` | §13 | Auth mechanism, request body, what "simple key" means |
| Phone webhook | §4 | Webhook format (Pushover? Slack? ntfy? Custom?) |

**Fix**: Add OpenAPI-style endpoint definitions or at minimum request/response examples.

---

### M3. Phase 3 "UNHINGED" Has No Content Safety Rails — Section 3

Phase 3 sets `chaos=extreme, gossip_aggression=extreme` with behaviors like:
- "Manufactured drama" between guests
- Obsession lock on random topics
- Fourth wall breaks

At a 21+ party with alcohol, extreme gossip aggression could:
- Generate genuinely hurtful content about guests
- Manufacture "drama" that guests take seriously
- Cross lines that embarrass the birthday person

**Fix**: Add content guardrails:
- Roast severity caps (even at 8/10, define what 8/10 means)
- Banned topics list (appearance, relationships, employment)
- "Drama" must be clearly absurd/Mario-themed, not realistic
- Emergency phrase detection: if guest says "stop" or "that's not funny" → immediately de-escalate

---

### M4. Section 3 and Section 14 Are the Same Feature Split Across Two Sections

Section 3 defines night progression with guest count awareness. Section 14 defines
guest count scaling with the same formula. This causes:
- Ambiguity about which section is the source of truth
- `effective_phase = min(time_phase, guest_energy_phase)` appears in both
- An implementer might build them separately and have conflicts

**Fix**: Merge §14 into §3. One section owns the formula and phase logic.

---

## 🟢 MINOR ISSUES (fix if time permits)

### m1. Section 12 Duplicates Section 4 Canary — Sections 4, 12
Both sections describe the pre-party canary test. §4 lists it as a subsection with 7
features tested. §12 expands it to 10 tests. Consolidate into one location.

### m2. "Obsession Lock" Mechanics Undefined — Section 3
Phase 3 says Mario "picks ONE random topic per visit, won't let it go" but doesn't
specify: How is the topic selected? For how long? What prevents it from being
annoying rather than funny? Does it reset on next visit?

**Fix**: Define: topic = random pick from guest's conversation_topics, duration = 3
exchanges or 2 minutes (whichever first), resets on new visit.

### m3. `config_live.json` Not Documented — Section 13
Hot reload reads from `config_live.json` but this file isn't in the current codebase.
How does it relate to `config.json`? Is it a subset? Does it override? What's the
initial state? The implementer needs to know the schema.

### m4. Pre-recorded Catchphrase Sourcing — Section 1
"Source high-quality Mario clips" for catchphrases but doesn't specify the source.
Game audio rips have copyright implications. Needs clarification: are these being
recorded via TTS and hand-picked? Extracted from specific games? Generated?

### m5. Audio Channel Allocation — Section 11
Sound effects need a "separate audio channel from TTS" but the current pygame mixer
may not have multiple channels allocated. The client's `audio_playback.py` needs to
be checked for channel management. This is an implementation detail but could block.

### m6. Smoke Test Coverage Gap — Section 12
The canary tests don't cover: night progression phase transitions, guest count
scaling, hot reload, sound effects playback, birthday VIP mode, or catchphrase
mirroring. If those features are implemented, the canary should test them.

---

## ✅ WHAT'S GOOD

- **Fallback chain philosophy** is excellent (never-silent principle)
- **Phase design** (§3) is creative and well-thought-out for the party arc
- **Reliability layer** (§4) is comprehensive — watchdog, auto-recovery, degradation tiers
- **Image gen hooks** (§7) correctly deferred — good scope management
- **Existing test infrastructure** (ralph loop, 40/45 e2e) provides a solid safety net
- **Hardware auto-detection** already built gives clean upgrade path
- **Birthday VIP** (§9) and **Party Report** (§8) add real party value
- **Tag `v1.0-pre-superpowers`** as rollback point is smart

---

## VERDICT

### ⚠️ ISSUES FOUND

**Do not begin implementation until C1 (VRAM budget) is resolved.** The 70B model
physically cannot coexist with the planned TTS stack on 24 GB VRAM. Starting
implementation without resolving this will waste days of work that must be redone.

**Add priority ordering (C2)** before starting. With 4 days to Friday, at least 3-4
features will likely be cut. The team needs to know which ones in advance.

**Resolve M1-M4** in a spec revision. These won't block day-1 work but will cause
rework and confusion by day 2-3.

**Minor issues** can be resolved during implementation.

### Recommended Next Step
1. Fix C1: Write VRAM budget table, pick quantization strategy
2. Fix C2: Add MoSCoW priority list
3. Fix M1: Swap fallback chain order
4. Fix M3: Add Phase 3 content guardrails
5. Merge M4: Consolidate §3 and §14
6. Begin implementation in priority order
