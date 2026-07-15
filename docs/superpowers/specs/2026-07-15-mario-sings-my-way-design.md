# Design: Mario Sings "My Way"

**Date:** 2026-07-15
**Status:** Approved (design), pending implementation plan
**Scope:** Give Mario a real singing performance of "My Way" — an actual AI voice-conversion cover in his voice, triggered on command at the party.

---

## 1. Goal & Non-Goals

**Goal:** On a command like "sing my way," Mario plays a pre-rendered cover of "My Way" that *actually sings the melody* in his (Charles Martinet RVC) voice, with a speech bubble, on the party speakers.

**Non-goals (v1, deliberately cut):**
- True karaoke-synced, word-by-word lyric timing.
- Spontaneous/idle singing without being asked.
- A multi-song browser/library UI.
- Any live (real-time) singing synthesis.

All of the above are easy follow-ons on the same registry; none are needed for the party centerpiece.

---

## 2. Why the current system can't already do this

- Today "songs" are **lyric text strings** pushed through GPT-SoVITS, which is **speech synthesis** — Mario *recites* lyrics, he does not carry a melody.
- Real singing requires a **melody source** (a vocal performance) plus **timbre conversion** to Mario's voice. That is exactly what RVC ("AI cover") does, and the RVC stack is already in the repo.

---

## 3. Key architectural decision: two independent halves

The system splits into two halves that do not touch at runtime:

- **Half A — Production (offline, run once):** a script converts a source recording into `my_way.wav` in Mario's voice.
- **Half B — Runtime (party):** server loads that WAV and plays it on trigger via the existing audio delivery path.

**Why:** the party-critical path becomes "play a file" (trivial, reliable), while all the fiddly, re-runnable AI work lives in an offline tool that can be iterated until it sounds right. No model inference happens on the party hot path.

---

## 4. Chosen integration approach

**"Performed songs" asset + registry** (selected over two alternatives).

Rejected alternatives:
- *Shoehorn into the karaoke game* — that game is interactive text back-and-forth and its pool is character-YAML populated; a 3-minute audio file muddies it.
- *Server-side `pygame.mixer` playback (like SFX)* — bypasses the client speech bubble, won't reach a remote/tunnel client, and isn't volume-managed alongside TTS.

The registry approach generalizes for free: any character, any song, drop-in.

---

## 5. Half A — Production pipeline

**Deliverable:** `scripts/make_song_cover.py` (generic, reusable for any future song).

**Pipeline:**
```
source.mp3   --> demucs (isolate vocal stem)        --> vocals.wav
vocals.wav   --> rvc_python RVCInference (Mario)     --> raw_mario.wav
raw_mario.wav--> peak-normalize -3dB (tts._normalize_audio) --> my_way.wav
```

**Reused infra (already in repo):**
- **demucs** (present in the voice-pipeline env) for vocal isolation.
- **`rvc_python.infer.RVCInference`** — the same class `server/tts.py` loads at startup (`load_model` / `set_params` / `infer_file(in, out)`).
- Martinet RVC weights: `mario_models_new/SuperMario_TITAN/SuperMario-TITAN_e500_s13000.pth` (or the Switch-Era model) + matching `.index`.
- `tts._normalize_audio()` for the final -3dB peak normalization (consistent party volume).

**Critical parameter change vs. the speech path:**
- Speech uses `f0_up_key=12` (a full octave up) — that would **destroy the melody**. Singing starts at **`f0_up_key=0`** (preserve melody/key).
- `f0_method="rmvpe"` (quality pitch tracking).
- `protect ≈ 0.25` and `index_rate ≈ 0.5–0.66` as starting points — the speech values (`0.15` / `0.95`) are too aggressive and smear sung pitch.

**Timbre caveat (why this is offline + re-runnable):** "My Way" is low baritone; Mario is bright and high. Expect to A/B a few *positive* semitone values (or choose a higher-pitched cover as the source recording) to sound Mario-ish without shifting the song into an ugly key. The script is a CLI so it can be re-run with different params until it sings right.

**CLI shape:**
```
python scripts/make_song_cover.py --in source.mp3 --char mario --id my_way \
    --title "My Way" --f0-up-key 0 --protect 0.25 --index-rate 0.6
```

---

## 6. Half A — Song asset format

Per-character asset directory, following the existing `characters/<char>/{sfx,voice}/` convention.

- `characters/mario/songs/my_way.wav` — the rendered cover (kept **local**, not committed to the repo).
- `characters/mario/songs/my_way.json`:

```json
{
  "id": "my_way",
  "title": "My Way",
  "triggers": ["sing my way", "my way", "sing frank", "do it your way"],
  "wav": "my_way.wav",
  "lyric_pages": [
    "And now, the end is near ♪",
    "And so I face the final curtain ♪"
  ],
  "credits": "AI cover — private party use only, not for distribution"
}
```

---

## 7. Half B — Runtime module

**Deliverable:** `server/performed_songs.py` — character-agnostic, follows the `set_character(name, display_name)` + `_CHARACTER_NAME` / `_CHARACTER_DISPLAY_NAME` convention.

- Loads `characters/<char>/songs/*.json` (+ validates the referenced `.wav` exists) at startup.
- **Pool defaults empty** and is populated only from the active character's assets — so a missing song file never leaks Mario data into another character (same rule as `game_handlers.py` content pools).
- `match(text) -> song_id | None` — word-count-guarded phrase match, mirroring the existing karaoke keyword detection at `command_handlers.py:1256`.
- `get(song_id) -> {wav_bytes, lyric_pages, title}`.

---

## 8. Half B — Trigger & delivery

**Trigger:** `command_handlers` checks `performed_songs.match(text)` (guarded by low word count). On a hit it returns a **bypass-TTS signal** (a small dict/marker distinct from a normal string reply), so the pre-rendered audio is not run through TTS synthesis.

**Delivery:** `main.py`, on that signal, loads the song and sends it down the **existing** path:
1. `send_json({"type": "mario_response", "text": <title / first lyric page>, "has_audio": True, "emotion": ...})`
2. `send_bytes(wav_bytes)`

This is the same contract every audio response already uses — no new client message type required for basic playback.

**Bubble / lyrics (v1):** a title bubble ("🎤 Mario sings *My Way* ♪") plus optional lyric pages driven by the **existing audio-gated bubble paging**. Sync is loose (page-level), not word-precise — YAGNI on true karaoke timing.

**Performance guard:** set `state_current["_performing_song"] = True` for the song's duration and clear it when done. While set, the **idle loop and greeting flows are suppressed** (reuse existing idle-safety gates) so Mario doesn't talk over his own song.

**Interruption:** a "stop" / "okay stop Mario" phrase sends the existing `clear_audio` message and clears the performance guard.

---

## 9. Error handling & edge cases

- **Missing WAV/JSON:** registry skips the entry at load and logs; `match()` simply won't fire — no crash, no partial playback.
- **Non-Mario character:** no song assets → empty pool → trigger never matches → no wrong-character leak.
- **Trigger during another response/game:** treat like any other command — the existing response gating applies; the performance guard prevents idle overlap.
- **Client disconnect mid-song:** same as any audio send failure today; guard is cleared on the send exception so the server doesn't get stuck "performing."

---

## 10. Testing (per `.claude/rules/testing.md`)

**Unit tests (`tests/`):**
- Registry load: valid JSON loads; missing `.wav` is skipped; empty dir → empty pool.
- `match()`: known trigger phrases hit; unrelated text and over-long messages miss.
- Non-Mario character: pool empty, `match()` returns `None`.

**Live audio verification (mandatory — not just logs):**
- Trigger "sing my way" → confirm client log shows **`_play_wav: playing <bytes>`** AND **`_play_wav: done`**.
- Speech bubble text matches the performance; no wrong-character references.
- Idle/greeting suppressed while `_performing_song` is set.
- "stop" mid-song cuts audio (`clear_audio`) and clears the guard.

---

## 11. Copyright

"My Way" (lyrics Paul Anka; melody Claude François / Jacques Revaux) is under copyright. Use is limited to a **private house party** with **no distribution**. The rendered WAV is kept **local** and is **not committed** to the repository (add `characters/*/songs/*.wav` to the ignore rules or simply never `git add` it).

---

## 12. Deliverables summary

| # | Deliverable | Type |
|---|-------------|------|
| 1 | `scripts/make_song_cover.py` | New — offline production CLI (generic) |
| 2 | `characters/mario/songs/my_way.json` | New — song asset metadata |
| 3 | `characters/mario/songs/my_way.wav` | Generated — local only, not committed |
| 4 | `server/performed_songs.py` | New — runtime registry + matcher |
| 5 | `command_handlers.py` trigger hook | Edit — detect + return bypass-TTS signal |
| 6 | `main.py` delivery hook | Edit — load WAV, send via mario_response + send_bytes, manage guard |
| 7 | `tests/test_performed_songs.py` | New — unit tests |
