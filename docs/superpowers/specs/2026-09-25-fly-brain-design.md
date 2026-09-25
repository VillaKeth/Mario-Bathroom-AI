# Fly Brain: a Character Run by a Real Connectome (Design)

**Date:** 2026-09-25
**Scope:** Pieces 0 and 1 of the fly-brain idea. Piece 0 is a whole-CNS spiking simulation of the male fruit fly connectome. Piece 1 is a new party character, `fly`, whose behavior comes from that simulation.
**Status:** The user approved the design direction in conversation ("what if the fly is just everything", "just like whatever the fly does man"). They asked for spec, plan and implementation on a worktree, to be reviewed on return. **Do not merge.**
**Branch:** `feature/fly-brain` (worktree `.claude/worktrees/fly-brain`)
**Later, separate specs:** piece 2 is pure mode (no words at all). Piece 3 is the fly playing a custom platformer.

---

## 1. What we are building

Party events become sensory input to a simulated fly brain. A sweet word is sugar on the proboscis. Shouting is sound on the antennae. "I'm gonna swat you" is a looming shadow. The simulation runs about half a second of fly-time. The character then does whatever the fly's motor and descending neurons did: it feeds, rejects, grooms, escapes, walks, or does nothing.

The screen shows the fly in the matching pose, next to a live brain panel with the neuron groups that fired. The fly says at most six words, grounded in what fired, and says nothing at all when it escaped or nothing happened.

There is no invented persona. Personality is whatever falls out of the wiring. That is the user's ask ("just like whatever the fly does man").

### 1.1 Success criteria

1. **The brain is real.** Three pathways from the literature fire in simulation, and each goes silent when the wiring is shuffled (§3.3):
   - sugar → MN9 feeding (Shiu 2024)
   - looming → giant-fiber escape (von Reyn 2014, Ache 2019)
   - antennal JO-C/E → aDN grooming (Hampel 2015)

   Tests pin all three.
2. **The character runs end to end:**
   - a chat message produces a brain window, then a behavior, then pose, emotion and words;
   - audio plays, with `_play_wav: playing` and then `done`;
   - the brain panel updates.
3. **No Mario leaks.** The fly passes the testing.md leak test. Its words come from a closed vocabulary, so a leak is impossible by construction on the reply path. The remaining surfaces (idle, greetings, songs, sick lines) are gated.
4. **The party machine can run it.** A 500 ms window completes in ≤ 1.5 s wall on the dev box (24 cores), and the server never stalls, because the brain runs in a subprocess.
5. **Attribution.** The MaleCNS CC BY 4.0 credit is visible on screen and in the docs.

### 1.2 Non-goals (this spec)

- Pure no-words mode (piece 2) and the platformer (piece 3).
- Plasticity or learning, body biomechanics, and pixel-level vision. Camera events map to looming *rates*, not a simulated retina.
- Group mode with the fly in a roster. The fly is a solo character.
- Memory, gossip, and name learning. A fly has no language, so none of the memory writes happen for the fly.

---

## 2. Data: MaleCNS v1.0

The source is the MaleCNS v1.0 flat connectome from Janelia FlyEM, University of Cambridge, MRC LMB and Google Research (Cell, 2026). Licence: **CC BY 4.0**. It covers brain, optic lobes and ventral nerve cord in one volume, so the same network includes walking and grooming motor neurons. That is why it beats FlyWire (brain only) for "the fly is everything".

| File (`…/flyem-male-cns/v1.0/connectome-data/flat-connectome/`) | Size | Rows |
|---|---|---|
| `body-annotations-male-cns-v1.0-minconf-0.5.feather` | 14.5 MB | 211,577 |
| `body-neurotransmitters-male-cns-v1.0.feather` | 43.3 MB | 1,835,518 |
| `connectome-weights-male-cns-v1.0-minconf-0.5.feather` | 1.05 GB | 151,856,684 |

- **Location:** `~/.cache/mario_ai/connectome/malecns_v1/`, outside every checkout so git never sees a gigabyte. It is configurable.
- **Reading:** feather needs `pyarrow`. polars cannot read the dictionary columns ("The dictionary key must fit in a `usize`").
- **Node policy** (same as DOOMFLY): keep every body with an assigned `superclass` whose `status` is not `Glia`. That gives **166,700 neurons**.
- **Edge policy:** keep every edge between retained nodes, with no synapse threshold. That gives **25,582,938 connections** and **124,177,617 synapses**. Both counts match DOOMFLY exactly.
- **Sign:** the first non-`unclear` value of `consensus_nt`, then `celltype_predicted_nt`, then `predicted_nt`.
  - Inhibitory (−1): GABA, glutamate, histamine. Glutamate is inhibitory via GluCl in the fly CNS, as in Shiu 2024. Histamine is inhibitory via HisCl.
  - Excitatory (+1): acetylcholine, dopamine, serotonin, octopamine, and unknown.
  - Result: 35.8% of neurons are inhibitory.
- **Cache format:** a single `net_v1.npz`, loaded in about 1 s:
  - CSC by presynaptic neuron: `indptr` int64, `indices` int32 (postsynaptic), `data` float32 (signed synapse count). Out-edges are sorted by target.
  - Node metadata: `body_ids`, `types`, `side`, `superclass`, `synonyms`.
  - Built in about 25 s from the feathers.
- **Fetch:** `server/brain/connectome.py` downloads with resume and a size check, then builds the cache. When `brain.auto_fetch` is true (default), the brain subprocess does this on first start and the fly runs brainless until it finishes (§6.4). `scripts/fetch_connectome.py` does the same from the command line.

---

## 3. Piece 0: the brain engine

### 3.1 Model

Leaky integrate-and-fire, with the parameters of Shiu et al. 2024 (*Nature* 634:210):

| | |
|---|---|
| resting = reset potential | −52 mV |
| threshold | −45 mV |
| membrane τ | 20 ms |
| synaptic τ | 5 ms |
| refractory | 2.2 ms (22 steps) |
| synaptic delay | 1.8 ms (18 steps) |
| dt | 0.1 ms |
| weight per synapse | 0.275 mV × **gain** × sign |
| Poisson stimulus kick | 250 × 0.275 mV (suprathreshold: a stimulated neuron fires ≈ at the requested rate) |

- **Dynamics:** `du/dt = (g − u)/τm` and `dg/dt = −g/τs`, with `u = v − v_rest`. This system is linear, so each step uses the exact update: `u ← u·e^(−dt/τm) + g·c` and `g ← g·e^(−dt/τs)`, where `c = τs/(τs−τm)·(e^(−dt/τs) − e^(−dt/τm))`.
- **Refractory:** while refractory, integration pauses, but incoming events still accumulate in `g` (Brian2 `unless refractory` semantics).
- **Spikes:** a spike from neuron j adds `data[e]·w` to target `g` 18 steps later, using an 18-slot ring buffer of target vectors.
- **Speed:** only neurons that spiked propagate, so cost scales with activity.

### 3.2 Why a gain, and how it was chosen (measured 2026-09-25)

At Shiu's 0.275 mV with every MaleCNS edge, the network is **supercritical**. One stimulus ignites the whole CNS: 4.7 M spikes per simulated second, 28 Hz average across all 166,700 neurons, MN9 saturated at 426 Hz. Target-shuffled wiring ignites too, with 24 M spikes. Shiu's model ran on FlyWire, a different reconstruction with different synapse detection and no VNC, so its weight does not transfer 1:1.

We swept one global gain on the synaptic weight. All runs used 500 ms windows, right-side stimulation at 150 Hz, and target-shuffled wiring as the control:

| gain | sugar → MN9 | loom → giant fiber | JO-C/E → aDN | shuffled (all) |
|---|---|---|---|---|
| 0.25 | 0 Hz | — | — | silent |
| 0.35 | 34 Hz | 425 Hz | 0 | silent |
| 0.42 | 229 Hz | 424 Hz | 0 | silent |
| **0.50** | **249 Hz** | **309 Hz** | **236 Hz** | **silent** |
| 1.00 | 426 Hz (runaway) | — | — | ignites |

**We choose gain = 0.5**, i.e. 0.1375 mV per synapse. It is the lowest tested gain at which all three pathways fire, and it leaves margin below runaway. Two caveats:

- This is **a single scalar fitted on these three pathways**. They are therefore a calibration check, not an independent prediction. The spec says so, and so does the calibration report.
- The independent evidence is the shuffled control, which is silent at every gain ≤ 0.5. Activity is carried by the specific wiring, not by the amount of input.

The gain lives in `brain.gain`, and `scripts/brain_calibrate.py` re-derives the table.

### 3.3 Validation (pre-registered, becomes tests)

These use the real connectome at the configured gain. The tests are skipped when the cache is absent.

| Stimulus (bilateral unless noted, 150 Hz, 500 ms) | Must happen | Must not happen |
|---|---|---|
| sugar GRNs | MN9 mean ≥ 80 Hz | giant fiber ≥ 50 Hz |
| sugar, target-shuffled wiring | — | MN9 > 0 |
| LC4 + LPLC2, right side | giant fiber mean ≥ 50 Hz | — |
| LC4 + LPLC2, target-shuffled | — | giant fiber > 0 |
| JO-C/E | aDN (DNg12) mean ≥ 30 Hz | giant fiber ≥ 50 Hz |
| JO-C/E, target-shuffled | — | aDN > 0 |
| sugar + bitter together | MN9 ≤ 50% of sugar alone | — |

The bilateral runs are re-measured when the tests are written. The probe used the right side only.

### 3.4 Populations

Populations are resolved by the annotation `type` column and live in `server/brain/malecns_populations.yaml`, which describes the dataset, not the character. Any population that resolves to zero neurons is a startup error: the brain refuses to load, and the fly goes brainless (§6.4).

| Name | Types | n (both sides) | Role |
|---|---|---|---|
| `sugar` | LB3a, LB3b, LB3c, LB3d | 77 | taste: sweet (see below) |
| `bitter` | LB1a–LB1e | 56 | taste: bitter (**inferred**, see below) |
| `ears` | JO-A\*, JO-B\* | ~150 (exact count pinned in calibration.json) | sound (Johnston's organ, hearing) |
| `antenna` | JO-C\*, JO-E\* | ~330 (exact count pinned in calibration.json) | antenna deflection: wind, touch |
| `loom` | LC4, LPLC2 | 311 | looming (visual projection) |
| `feed` | MN9 | 2 | proboscis extension motor neuron |
| `groom` | DNg12_a–h (aDN) | 42 | antennal grooming command |
| `escape` | DNp01 | 2 | giant fiber (takeoff) |
| `startle` | DNp02, DNp04, DNp06, DNp11 | 8 | other looming-escape DNs |
| `walk` | DNp09, DNg100, DNa01, DNa02 | 8 | walking and steering DNs |
| `backup` | MDN | 4 | moonwalker (backward walking) |

**How sugar and bitter were identified.** MaleCNS does not label GRN taste modality: `receptorType` only has putative ppk23, ppk25 and IR52b. We used two methods:

- **Sugar:** LB3a–d are the labellar GRN types whose top downstream partners are the sugar-pathway neurons named in Shiu 2022: Usnea, Phantom, Clavicle, Quasimodo, Zorro, Specter and G2N-1. These names are carried in the MaleCNS `synonyms` column. Measured from the edge table.
- **Bitter:** we used Shiu's own functional test. Each non-sugar GRN group was co-stimulated with sugar:

  | group | MN9, seeds 1/2/3 |
  |---|---|
  | sugar alone | 249 / 250 / 246 Hz |
  | + LB1a–e | **42 / 43 / 41 Hz** |
  | + LB2, LB4, taste pegs | unchanged, 244–255 Hz |

  LB1a–e is therefore the aversive group. This is a model inference, not ground truth, and the spec and panel say so.

### 3.5 Performance design

The probe was serial numba and took **~6 s wall per 500 ms** in busy windows (~600 k spikes) and ~1.2 s when quiet. The engine does three things to cut that:

1. **Parallel integrate:** a `prange` over neuron chunks. Spikes land in per-chunk slices and are then compacted.
2. **Parallel propagate:** partitioned by *target* range. Each thread walks every spiker's target-sorted out-edges, but binary-searches to its own range, so there are no write races and no atomics.
3. **Skip quiet neurons:** `u = g = 0` with no pending input.

- **Target:** ≤ 1.5 s wall per 500 ms busy window on the dev box. If we miss it, `brain.window_ms` shrinks to 300 ms. Behaviors appear well inside 300 ms in the probe runs.
- **Threads:** `brain.threads` (0 = numba default).
- **Startup:** JIT compile uses `cache=True` and runs a warm-up at worker start.

### 3.6 Process boundary

The brain runs in its own subprocess, `python -m server.brain.worker`, speaking JSON lines on stdin/stdout, like `gpt_sovits_server.py`. That keeps 400 MB of arrays and numba threads out of the asyncio server, and a crash only costs the fly its brain.

Messages from the worker:

- On start (stdout only carries protocol lines; logs go to stderr):
  - `{"status":"loading","stage":"fetch|build|load|jit","progress":0.4}` (any number of these)
  - then `{"status":"ready","neurons":166700,"connections":25582938,"synapses":124177617,"populations":{"sugar":77,…},"gain":0.5}`

Requests and replies:

- **run:**
  - request: `{"cmd":"run","id":7,"ms":500,"seed":123,"stim":[{"pop":"sugar","rate":150,"side":"both"}],"noise":{"frac":0.0,"rate":0}}`
  - reply: `{"status":"ok","id":7,"rates":{pop:hz},"bins":{pop:[10 floats]},"spikes":N,"active":M,"sim_ms":500,"wall_ms":812}`
  - `rates` and `bins` cover every named population, plus `total` and `active`.
- **reset** (`{"cmd":"reset"}`), **ping** (`{"cmd":"ping"}` → `{"status":"pong"}`), **quit** (`{"cmd":"quit"}`).
- **errors:** `{"status":"error","id":7,"error":"…"}`.

Brain state (v, g, refractory, ring) **persists between windows**, so a fly that just escaped is still aroused for the next window. `reset` returns it to rest.

On the server side, `server/brain/client.py` runs blocking I/O in a thread and gives each request a 10 s timeout. After a crash it restarts, with a 30 s cooldown. It sends `{"cmd":"quit"}` itself, avoiding the `command`/`cmd` mismatch in the SoVITS client. It exposes `async run(stim, ms, seed, noise) -> BrainWindow | None`, where `None` means brainless.

---

## 4. Piece 1: the fly character

### 4.1 Senses: event → stimulus (deterministic)

`server/brain/senses.py` turns an event into a list of `(population, rate_hz, side)`. The lexicons are character data, in `characters/fly/brain/senses.yaml`, so they can be edited without code. The rules:

| Event | Stimulus |
|---|---|
| any chat text (it is sound) | `ears` 50 Hz; 120 Hz if shouted (ALL CAPS word or `!!`) |
| food/sweet words (sugar, candy, cake, fruit, banana, beer, wine, juice, soda, honey, pizza…) | `sugar` 100–200 Hz by match count |
| affection/praise words (love, cute, good, nice, beautiful, best, sweet…) | `sugar` 60–120 Hz |
| gross/insult words (gross, disgusting, hate, ugly, stupid, shut up, poison, bleach…) and profanity | `bitter` 100–200 Hz |
| threat words (swat, squash, smash, kill, spray, raid, zapper, swatter, newspaper, slipper) | `loom` 150–200 Hz, one side (random) |
| air/touch words (blow, wind, fan, dust, wash, clean, dirty, tickle, soap, hair) | `antenna` 100–150 Hz |
| person arrives (face greeting / presence) | `loom` 80 Hz, one side (something big approaching) |
| retching detected (`audio_distress`) | `sugar` 150 Hz. Flies are drawn to vomit; that is what a fly does. `senses.yaml` can flip it. |
| idle tick | no stimulus; background noise (§4.5) |

- **Emotion fallback:** if no lexicon matched but the existing keyword emotion inference in `server/emotions.py` returns a clearly valenced emotion, positive adds `sugar` 60 Hz and negative adds `bitter` 60 Hz.
- **Combining:** when several senses fire, all stimuli run together in one window. The brain arbitrates; for example, sugar plus bitter gives MN9 suppression (§3.4).

### 4.2 Behavior: readout → one behavior

`server/brain/behavior.py` reads mean rate per neuron in each readout population over the window. Rules are applied in priority order, and the first one that matches wins:

| Behavior | Rule (defaults in `brain.behavior`, re-derived by calibration) | Emotion | Pose |
|---|---|---|---|
| ESCAPE | `escape` ≥ 50 Hz | scared | movement/escape |
| REJECT | `bitter` ≥ 20 Hz **and** `feed` < FEED threshold: tasted bitter, did not extend the proboscis | disgusted | negative/reject |
| FEED | `feed` ≥ 80 Hz | happy | positive/feeding |
| GROOM | `groom` ≥ 30 Hz | neutral | reactions/grooming |
| WALK | `walk` or `backup` ≥ 20 Hz; direction is `back` if `backup` > `walk` | curious | movement/walking |
| NOTHING | otherwise | neutral | neutral/idle |

- **Intensity:** `clamp(rate / threshold / 3, 0, 1)`. It sets how many words (§4.3) and how loud the buzz is.
- **Emotion names:** these are checked against `server/emotions.py` when implemented, and replaced with the nearest valid emotion if a name is absent. The client falls back unknown emotions to "happy", which would be wrong for REJECT.

### 4.3 Words: 0–6, grounded

`server/brain/words.py`:

1. **ESCAPE or NOTHING:** no words, as approved. ESCAPE gets a takeoff buzz instead (§4.4).
2. **Deterministic lexicon (always available):** each behavior and sense has short phrases, and intensity picks the length.
   - FEED: "sweet." / "food. more." / "sweet sweet sweet."
   - REJECT: "bitter." / "no. bad."
   - GROOM: "clean." / "rub rub."
   - WALK: "walk." / "back. back."
3. **LLM rephrase (`brain.words.llm`, default on):** the local Ollama fast model gets:
   - the behavior;
   - the populations that fired, with rates;
   - a **closed vocabulary** of about 90 fly words (senses, body parts, food, motion, yes/no, you/me).

   It must answer with at most 6 words from that vocabulary. A validator lowercases the answer, strips it to words, and rejects it if any word is outside the vocabulary or the answer is longer than 6 words. On rejection or a 3 s timeout, the lexicon answer is used.

Because every reply is drawn from a closed vocabulary, the reply path cannot leak another character's text.

### 4.4 Voice

- **Speech:** the fly's `voice:` block uses Edge TTS. The voice, rate and pitch are chosen for a small, fast, high voice.
- **Effect:** a **wing-buzz ring modulation**, a ~200 Hz carrier (Drosophila wingbeat) mixed with the dry signal, plus a faint buzz bed, applied to the synthesized WAV.
  - **Where:** after TTS routing, as a per-character effect (`voice.effect: wing_buzz`).
  - **Cache:** the TTS cache stores pre-effect audio, so a later effect change never poisons the cache (see memory note: voice-side changes are invisible to `purge_stale_cache`).
- **ESCAPE:** a procedural takeoff buzz. It lasts 0.5 s, sweeps 180→230 Hz, and is amplitude-modulated. It is generated in numpy, with no TTS.
- **NOTHING:** no audio.
- **Flag for the user:** this is Edge-based. The user has said "never Edge" for *Mario's numbers*. It does not apply here, since the fly has no trained voice and the ring mod dominates the timbre. It is flagged anyway.

### 4.5 Idle: spontaneous behavior

- **Noise window:** on each idle-loop tick (existing cadence and gates), the fly runs one window with **no stimulus** and **background noise**: independent Poisson input to a random `noise.frac` of all sensory neurons at `noise.rate` Hz.
- **Output:** whatever behavior emerges is shown. Silent behaviors (GROOM, NOTHING) change pose and panel only; FEED and WALK can speak their lexicon words (lexicon only; idle never calls the LLM).
- **Calibration:** `scripts/brain_calibrate.py` reports what fraction of noise windows produce each behavior. It sets `noise.frac` and `noise.rate` so that roughly 20–40% of idle windows produce *some* behavior, which leaves the fly alive but not frantic.
- **No other idle content:** no Mario idle content, loneliness tiers, gossip, DJ lines, scheduled lines or memorial events run for the fly (§5.3).

### 4.6 Brain panel (pygame client, primary display)

`_draw_brain_panel()` in `client/mario_display.py` follows the pattern of `_draw_health_overlay`. It is on by default for brain characters and toggled with **F9**.

- **Header:** "MaleCNS v1.0 · 166,700 neurons · 25.6 M connections".
- **Sensory rows:** SWEET, BITTER, EARS, ANTENNA, LOOM.
- **Motor rows:** FEED, GROOM, ESCAPE, WALK, BACK.
- **Row contents:** a rate bar (log-scaled to 400 Hz) and a 10-bin sparkline over the window.
- **Status lines:** the behavior (e.g. "→ FEEDING"), then "spikes 368,532 · active 10,508 · 0.5 s fly-time".
- **Credit footer (CC BY):** "Connectome: MaleCNS v1.0, Janelia FlyEM et al., CC BY 4.0 · LIF after Shiu et al. 2024 · bitter taste group inferred".

Data transport: a new WS message `{"type":"brain_state", …}` is sent after every window, for replies and idle alike. It carries `behavior`, `rates`, `bins`, `spikes`, `active`, `window_ms`, `pose_hint` and `emotion`. The client routes it to `display.set_brain_state()` and, when `pose_hint` is present, to `set_pose_hint` and `set_emotion`. Silent behaviors therefore still change the sprite, with no speech bubble.

### 4.7 Sprites

The fly has 7 poses: `neutral/idle`, `speech/talking`, `positive/feeding` (proboscis on a sugar drop), `negative/reject` (proboscis retracted, turned away), `reactions/grooming` (front legs rubbing the head), `movement/escape` (takeoff, wings blurred), and `movement/walking`.

- **Style:** an anatomically faithful *Drosophila melanogaster* (red eyes, tan thorax, banded abdomen, clear wings) as a glossy 3D collectible figurine on a plain white background, to suit rembg.
- **Pipeline:** the existing ChatGPT-browser batch (`mcp_chatgpt/batch_sprites.py`, free accounts, resumable) with a rembg cut. It is slow but free, and there is a week. **No paid Pollinations spend** (memory: the user was upset by unintended spend).
- **Placement:** sprites go in `characters/fly/sprites/<category>/<pose>.png`, verified by corner-alpha or by compositing, not by eyeballing.
- **Sprite maps:** `state_sprite_map.talking` must be non-empty, because a missing key crashes the client. A missing sprite falls back to `neutral/idle`.

### 4.8 Character files

```
characters/fly/
  character.yaml          identity, voice (edge + effect), visuals, brain
  brain/senses.yaml       lexicons + rates (§4.1)
  brain/words.yaml        lexicon phrases + closed vocabulary (§4.3)
  brain/calibration.json  output of scripts/brain_calibrate.py (committed, small)
  sprite_prompts.txt      7 poses
  sprites/...
```

```yaml
brain:
  enabled: true
  dataset: malecns_v1
  cache_dir: ~/.cache/mario_ai/connectome/malecns_v1
  auto_fetch: true
  gain: 0.5
  window_ms: 500
  threads: 0
  behavior: {escape_hz: 50, feed_hz: 80, bitter_hz: 20, groom_hz: 30, walk_hz: 20}
  noise: {frac: 0.02, rate: 10}      # idle; re-derived by calibration
  words: {llm: true, max_words: 6, timeout_s: 3}
```

`shared/character_loader.py` gains `self.brain = self._config.get("brain") or {}`. Every other character has no `brain:` block and is unaffected.

---

## 5. Server integration

### 5.1 Lifecycle

- **Startup:** in `lifespan` (`server/main.py` ~856–936), if `char_loader.brain.enabled` is set, `FlyBrain` is built and the worker starts in the background. Startup never waits for the brain.
- **Character switch:** `admin_switch_character` (~3285–3376) starts or stops the worker to match the new character.
- **Canary:** `server/canary.py` gains a brain check, only when the active character has a brain. It fails if the brain is not ready within its budget.

### 5.2 Reply path

The branch goes at the **top** of `_generate_and_send_response`, before `check_input` and command handling:

```python
if _brain_character_active():
    return await _brain_respond(ws, text, source, start_time)
```

This one early return keeps the Mario path untouched. The fly ignores jokes, games, trivia and the safety redirect: profanity is simply bitter to it, and its output vocabulary is closed. `_brain_respond` does the following:

1. Map senses.
2. `await brain.run(...)`.
3. Classify the behavior.
4. Pick words.
5. Synthesize via the existing TTS, then apply the effect.
6. Send `brain_state`, then `send_response` with `pose_hint`, emotion and `is_idle=False`.

There is no chat history, memory write or gossip update; `party_stats` visit counting is kept. When the brain is `None` (brainless), the fly gives NOTHING: no words, the idle pose, and a panel showing "brain loading" or "brain offline".

### 5.3 Other outbound surfaces (leak gating)

For a brain character, these paths are suppressed or replaced:

- **Idle loop:** content selection is replaced with the brain idle window (§4.5). Announcements from `/admin/announce` stay, because they are admin-authored.
- **Replaced by the brain window:** face greetings and exit flows go through `_generate_and_send_response`, so the §5.2 branch covers them with `source` → a looming event.
- **Suppressed:** startup greeting text (replaced by one noise window), sick/distress comfort lines (retching becomes a sense event instead), performed songs, DJ lines, memorial events, catchphrase mirror, and trivia/vision idle.

The plan's leak audit greps every `send_response(` / `mario_response` sender in `server/main.py` and records the gate for each.

### 5.4 TTS effect hook

`voice.effect` is read at character load. The effect is applied to the return value of the TTS router (`tts_router.py` ~92–100), keyed on the active character, so the cache keeps storing dry audio. This happens only when an effect is configured. The ESCAPE buzz bypasses TTS.

### 5.5 Debug endpoint

`GET /api/brain` returns worker status (loading, ready or offline), dataset counts, and the last window: stimulus, behavior, rates and wall time. It is used by live testing and the mario-debug MCP.

---

## 6. Errors and degradation

1. **Connectome missing, auto_fetch on:** the worker downloads and builds, emitting `loading` progress, and the panel shows "fetching connectome 40%". This happens on first run only.
2. **Download fails or auto_fetch off:** the worker exits with an error line. The fly is brainless, and a log line names `python scripts/fetch_connectome.py`.
3. **Worker crash or timeout (10 s):** that window returns `None`, so NOTHING. The client restarts the worker, with a 30 s cooldown.
4. **Brainless fly:** idle pose, no words, panel status. It never raises into the reply path.
5. **numba missing:** the worker fails to import and the fly is brainless. numba and pyarrow are declared in `server/requirements.txt` (versions from the venv: numba 0.65.1, pyarrow 25.0.1).

---

## 7. Testing

- **Unit, fast, synthetic:**
  - Engine on 2–5-neuron nets:
    - Poisson rate ≈ requested;
    - chain firing with the 1.8 ms delay;
    - inhibition blocks;
    - refractory caps the rate;
    - one event matches the closed-form solution;
    - silence stays silent;
    - determinism per seed;
    - parallel propagation = serial.
  - Connectome build on tiny synthetic feathers: node policy, NT sign precedence, edge filter, CSC ordering.
  - Population resolver.
  - Senses, behavior and words, including the validator and a fake LLM that returns out-of-vocab or overlong answers.
  - Voice: ring-mod output is valid WAV of the same length; the buzz is valid WAV.
  - Worker protocol, against a fake worker script.
  - Brain client: timeout, restart cooldown, quit.
  - Character loader `brain` field.
  - The main.py branch, with a fake FlyBrain: routing, and no LLM call.
  - brain_state client plumbing.
- **Integration, real connectome:** the §3.3 table. Skipped when the cache is absent. These are the "brain is real" tests.
- **Full suite:** diffed against the worktree baseline. That baseline is 38 failed / 1674 passed / 3 skipped on 66f49a2, with pre-existing failures in latency, safety and pygame-control tests; the failing set is saved in the session scratchpad.
- **Live (testing.md):**
  - config → fly, restarting both server and client;
  - the leak prompts: "Hey who are you?", "Do you know Mario?", "Tell me a fun fact!", "What's your favorite game?", then 2+ minutes idle;
  - sense probes: "have some candy", "you're disgusting", "I'm gonna swat you", "blow on it";
  - for each: `mario says:` text, audio bytes, `_play_wav: playing` and `done`, zero Mario references, the brain panel visible in a screenshot, and `/api/brain` behavior as expected.

## 8. Risks

| Risk | Mitigation |
|---|---|
| The gain is a fit, not a law | Stated plainly (§3.2). The shuffled control is the independent check, and the calibration script is reproducible. |
| Bitter identity is inferred | Stated on the panel and in the docs, and pinned by test. It is easy to swap in `malecns_populations.yaml`. |
| Busy windows are too slow | Parallel engine (§3.5), with fallback to a 300 ms window. |
| Idle is too quiet (a fly mostly does nothing) | Noise calibration target (§4.5). Stillness is acceptable, and is true to the animal. |
| Other outbound paths leak Mario text | The §5.3 audit plus the live leak test. |
| The 1.05 GB download on the party box | auto_fetch runs on first start, with progress on the panel. The build also runs in `scripts/fetch_connectome.py` ahead of the party. |
| Free sprite accounts rate-limited | Resumable batch over a week. Missing sprites fall back to `neutral/idle` and never crash. |

## 9. Credits

- **Connectome:** MaleCNS v1.0, Janelia FlyEM with the University of Cambridge, MRC LMB and Google Research, CC BY 4.0. This project preprocesses it into a signed weight matrix. Required attribution: panel footer, `characters/fly/README.md`, and this spec.
- **Model:** Shiu, P.K. et al. "A Drosophila computational brain model reveals sensorimotor processing." *Nature* 634, 210–219 (2024).
- **Pathways:**
  - Hampel et al. 2015 (JO-C/E → aDN grooming);
  - von Reyn et al. 2014 and Ache et al. 2019 (looming → giant fiber);
  - Bidaye et al. 2014 (MDN).
- **Reference implementations (MIT, read, not vendored):** flypoke (FlyWire LIF) and DOOMFLY (MaleCNS node policy).
