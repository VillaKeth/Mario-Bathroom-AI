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

1. **The brain is real.** Three pathways from the literature fire in simulation, and each goes silent when the wiring is shuffled (§3.3; the 42-neuron grooming readout keeps a trace under 1 Hz):
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
| refractory | 2.2 ms (22 steps); none for Poisson-stimulated neurons |
| synaptic delay | 1.8 ms (18 steps) |
| dt | 0.1 ms |
| weight per synapse | 0.275 mV × **gain** × sign |
| Poisson stimulus kick | 250 × 0.275 mV = 68.75 mV (suprathreshold: a stimulated neuron fires at the requested rate) |

The engine runs the model **as Shiu's Brian2 code (`model.py`) runs it**:

- **Dynamics:** `du/dt = (g − u)/τm` and `dg/dt = −g/τs`, with `u = v − v_rest`. This system is linear, so each step uses the exact update: `u ← u·e^(−dt/τm) + g·c` and `g ← g·e^(−dt/τs)`, where `c = τs/(τs−τm)·(e^(−dt/τs) − e^(−dt/τm))`.
- **Schedule, per step (Brian2's order):**
  1. integrate every neuron that is not refractory;
  2. test the threshold;
  3. deliver this step's synaptic input (`g += w`) and Poisson kicks (`v += 68.75 mV`);
  4. reset every neuron that spiked: `v = v_rest` **and `g = 0`** (Shiu's `eq_rst`).

  Input and kicks that land on a neuron's spike step are erased by its reset.
- **Refractory:** Brian2's `timestep(t − lastspike) ≥ timestep(rfc)`, so a neuron can fire again 22 steps after it fired. While refractory, integration pauses, but input still accumulates in `g` and kicks still reach `v`. Shiu sets `rfc = 0` for every Poisson-stimulated neuron, so a stimulated neuron can fire every other step, and fires at the requested rate (150 Hz in: 147–148 Hz measured across the sugar and antenna populations).
- **Spikes:** a spike from neuron j adds `data[e]·w` to target `g` 18 steps later, using an 18-slot ring buffer of target vectors.
- **Speed:** only neurons that spiked propagate, so cost scales with activity.
- **Proof:** the parallel engine matches a plain per-step reference simulator written in Brian2's order bit for bit, counts, `u` and `g` alike, on a random 400-neuron net with 40 stimulated neurons (`test_block_kernel_matches_shiu_brian2_reference`).

*Changed in the final review.* The first build departed from Shiu in four ways: no `g` reset on a spike, Poisson kicks dropped while refractory, a minimum inter-spike interval of 23 steps instead of 22, and a 22-step refractory period for stimulated neurons, so a 150 Hz stimulus delivered about 112 Hz. The gain, the ignition findings and every calibrated number rested on those departures. The engine was rebuilt to the schedule above, and every number in this spec was measured again on it.

### 3.2 Why a gain, and how it was chosen (re-measured in the final review)

At Shiu's 0.275 mV (gain 1.0) with every MaleCNS edge, one stimulus sets off network-wide activity. Sugar at 150 Hz drives about 800 k spikes per 500 ms window from rest (≈ 1.6 M per simulated second, ~10 Hz averaged over all 166,700 neurons), against 23 k at the chosen gain, and antenna drive no longer grooms reliably (aDN 24–55 Hz, depending on seed). Shiu's model ran on FlyWire, a different reconstruction with different synapse detection and no VNC, so its weight does not transfer 1:1.

We swept one global gain on the synaptic weight. Every run used a 500 ms window from rest, 150 Hz stimulation (bilateral; loom on the right side only), seeds 1/2/3, and target-shuffled wiring as the control (`calibration.json`, `gain_sweep`):

| gain | sugar → MN9 (Hz) | loom → giant fiber | JO-C/E → aDN | sugar + bitter → MN9 | shuffled aDN | spikes, sugar window | spikes, quiet window after antenna drive |
|---|---|---|---|---|---|---|---|
| 0.40 | 7 / 6 / 7 | 261–264 | 41 | 0 | 0.1 | 9 k | 9 k |
| 0.50 | 50 / 48 / 52 | 274–279 | 63 | 0 | 0.1–0.2 | 12 k | 17 k |
| 0.55 | 60 / 58 / 58 | 279–284 | 72 | 0 | 0.1–0.2 | 16 k | 23 k |
| 0.60 | 76 / 73 / 74 | 279–284 | 81–83 | 0 | 0.1–0.2 | 20 k | 30–54 k |
| 0.62 | 80 / 82 / 80 | 280–288 | 84–87 | 0 | 0.2–0.3 | 21 k | 61 k |
| 0.63 | 85 / 86 / 87 | 281–284 | 82–89 | 0 | 0.2–0.3 | 22 k | 570 k |
| **0.65** | **92 / 91 / 86** | **278–286** | **84–88** | **0** | **0.2–0.3** | **23 k** | **586 k** |
| 0.70 | 101 / 97 / 102 | 276–283 | 78–96 | 0–1 | 0.3–0.4 | 27–39 k | 659 k |
| 0.80 | 106 / 99 / 102 | 244–259 | 70–104 | 0–3 | 0.3–0.6 | 102–545 k | 693–773 k |
| 1.00 | 134 / 148 / 144 | 204–205 | 24–55 | 12–14 | 0.6–0.7 | 800 k | 975 k |

With shuffled wiring, MN9 and the giant fiber stay at exactly 0 at every gain, 1.0 included.

**We choose gain = 0.65**, i.e. ≈ 0.179 mV per synapse:

- It is the lowest swept gain at which every §3.3 line passes with margin on all three seeds. At 0.62, MN9 sits on the 80 Hz feeding line.
- One food word, as the party delivers it (sugar 150 Hz plus chat sound, `ears` 50 Hz), feeds on 8 of 8 seeds at 0.65, against 7 of 8 at 0.63 and 6 of 8 at 0.62.
- Above it, feeding gains little while grooming turns erratic from seed to seed (0.7–0.8), and at 0.8 a single sugar window can recruit half a million spikes.

Two caveats:

- This is **a single scalar fitted on these pathways**. They are therefore a calibration check, not an independent prediction. The spec says so, and so does the calibration report.
- The independent evidence is the shuffled control. MN9 and the giant fiber stay at 0 with shuffled wiring. The 42 aDN neurons pick up a trace: 0.1–0.7 Hz, a few spikes per window from 335 JO-C/E neurons firing at 150 Hz. That is more than 100× below the real response at every gain up to 0.8. Activity is carried by the specific wiring, not by the amount of input.

The gain lives in `brain.gain`, and `scripts/brain_calibrate.py --sweep` re-derives the table.

*Changed in the final review:* the first build chose 0.5, on the engine that departed from Shiu (§3.1). On the faithful engine, 0.5 drives MN9 to only ~50 Hz, under the feeding line. The carry-over column is §3.7.

### 3.3 Validation (pre-registered, becomes tests)

These use the real connectome at the configured gain. The tests are skipped when the cache is absent.

| Stimulus (bilateral unless noted, 150 Hz, 500 ms) | Must happen | Must not happen |
|---|---|---|
| sugar GRNs | MN9 mean ≥ 80 Hz | giant fiber ≥ 50 Hz |
| sugar, target-shuffled wiring | — | MN9 > 0 |
| LC4 + LPLC2, right side | giant fiber mean ≥ 50 Hz | — |
| LC4 + LPLC2, target-shuffled | — | giant fiber > 0 |
| JO-C/E | aDN (DNg12) mean ≥ 30 Hz | giant fiber ≥ 50 Hz |
| JO-C/E, target-shuffled | — | aDN ≥ 1 Hz |
| sugar + bitter together | MN9 ≤ 50% of sugar alone | — |

*Changed in the final review:* the shuffled JO-C/E line was "aDN > 0". On the faithful engine, 335 JO-C/E neurons firing at the full 150 Hz leak a few random spikes into the 42 aDN neurons through shuffled wiring, 0.1–0.7 Hz at every gain swept (§3.2). That is at least 30× below the GROOM threshold and far below the real response, so the line is now < 1 Hz. The two-neuron readouts (MN9, giant fiber) keep the strict zero.

**Measured at gain 0.65 (`characters/fly/brain/calibration.json`, seeds 1/2/3).** All pass:

| Case | Target | Real | Shuffled |
|---|---|---|---|
| sugar → MN9 | ≥ 80 Hz | **92 / 91 / 86 Hz** | 0 Hz |
| LC4 + LPLC2 (right) → giant fiber | ≥ 50 Hz | **279 / 286 / 278 Hz** | 0 Hz |
| JO-C/E → aDN | ≥ 30 Hz | **87.6 / 84.3 / 86.4 Hz** | 0.3 / 0.2 / 0.3 Hz |
| sugar + bitter → MN9 | ≤ 50% of sugar alone | **0 / 0 / 0 Hz** vs 92 / 91 / 86 Hz | — |

The giant fiber stays at 0 in the sugar and JO-C/E runs. The LB1 bitter GRNs read 0 Hz in the loom and JO-C/E runs, and in self-sustaining windows (§3.7). The first build's 46–49 Hz of "central bitter" came from its engine departures.

### 3.4 Populations

Populations are resolved by the annotation `type` column and live in `server/brain/malecns_populations.yaml`, which describes the dataset, not the character. Any population that resolves to zero neurons is a startup error: the brain refuses to load, and the fly goes brainless (§6.4).

| Name | Types | n (both sides) | Role |
|---|---|---|---|
| `sugar` | LB3a, LB3b, LB3c, LB3d | 77 | taste: sweet (see below) |
| `bitter` | LB1a–LB1e | 57 (the probe note said 56; the resolver counts 57) | taste: bitter (**inferred**, see below) |
| `ears` | JO-A\*, JO-B\* | 138 | sound (Johnston's organ, hearing) |
| `antenna` | JO-C\*, JO-E\* | 335 | antenna deflection: wind, touch |
| `loom` | LC4, LPLC2 | 311 | looming (visual projection) |
| `feed` | MN9 | 2 | proboscis extension motor neuron |
| `groom` | DNg12_a–h (aDN) | 42 | antennal grooming command |
| `escape` | DNp01 | 2 | giant fiber (takeoff) |
| `startle` | DNp02, DNp04, DNp06, DNp11 | 8 | other looming-escape DNs |
| `walk` | DNp09, DNg100, DNa01, DNa02 | 8 | walking and steering DNs |
| `backup` | MDN | 4 | moonwalker (backward walking) |

**How sugar and bitter were identified.** MaleCNS does not label GRN taste modality: `receptorType` only has putative ppk23, ppk25 and IR52b. We used two methods:

- **Sugar:** LB3a–d are the labellar GRN types whose top downstream partners are the sugar-pathway neurons named in Shiu 2022: Usnea, Phantom, Clavicle, Quasimodo, Zorro, Specter and G2N-1. These names are carried in the MaleCNS `synonyms` column. Measured from the edge table.
- **Bitter:** we used Shiu's own functional test. Each non-sugar GRN group was co-stimulated with sugar, 150 Hz each, at gain 0.65 on the faithful engine:

  | group | MN9, seeds 1/2/3 |
  |---|---|
  | sugar alone | 92 / 91 / 86 Hz |
  | + LB1a–e (57 neurons) | **0 / 0 / 0 Hz** |
  | + LB2a–d (18) | 95 / 96 / 96 Hz |
  | + LB4a–b (12) | 92 / 98 / 102 Hz |
  | + taste pegs (PEG, 18) | 87 / 87 / 83 Hz |

  LB1a–e is therefore the aversive group. The first build's engine gave the same verdict (249 → 42 Hz, the other groups unchanged). This is a model inference, not ground truth, and the spec and panel say so.

### 3.5 Performance design

The probe was serial numba and took **~6 s wall per 500 ms** in busy windows (~600 k spikes) and ~1.2 s when quiet. The engine does three things to cut that:

1. **Parallel integrate:** a `prange` over neuron chunks. Spikes land in per-chunk slices and are then compacted.
2. **Parallel propagate:** partitioned by *target* range. Each thread walks every spiker's target-sorted out-edges, but binary-searches to its own range, so there are no write races and no atomics.
3. **Skip quiet neurons:** `u = g = 0` with no pending input.

- **Target:** ≤ 1.5 s wall per 500 ms busy window on the dev box. If we miss it, `brain.window_ms` shrinks to 300 ms. Behaviors appear well inside 300 ms in the probe runs.
- **Threads:** `brain.threads` (0 = numba default).
- **Startup:** JIT compile uses `cache=True` and runs a warm-up at worker start.

**As built.** The engine steps in **18-step delay blocks**. A spike takes 18 steps to land, so within a block no neuron can affect another: integration runs 18 steps per neuron chunk in parallel. The block's spikes are then gathered and propagated once. The result is exact, not an approximation (§3.1, proof test).

- A neuron with a refractory period fires at most once per block. A Poisson-stimulated neuron has none (§3.1) and can fire up to 9 times, so each chunk's spike buffer is sized by the stimulated neurons it holds.
- Integration is branch-free over every neuron: the update is computed for all and then selected, so numba vectorizes it. That beat design item 3 (skipping quiet neurons).
- The inner loops are separate `@njit` helpers over zero-based slice views, which is what lets numba vectorize them.

**Measured** (dev box, 24 threads, 500 ms windows, gain 0.65; `calibration.json` timing, median of seeds 1–3, plus probe runs):

| Window | Spikes | Wall |
|---|---|---|
| quiet, no input | 0 | 0.23 s |
| sugar 150 Hz → FEED | 23 k | 0.26 s |
| antenna 150 Hz → GROOM | 198 k | 0.41 s |
| bitter 150 Hz → REJECT, ending in the self-sustaining state (§3.7) | 492 k, ~13.5 k neurons active | 0.61–0.63 s |
| idle noise, busy window (§4.5) | 115–440 k | 0.32–0.57 s |

Every window is well inside the 1.5 s target, so `window_ms` stays at 500. (The first build's engine took 1.2–1.6 s for its busiest windows.) The worker is ready about 50 s after spawn (cache load plus JIT warm-up).

### 3.6 Process boundary

The brain runs in its own subprocess, `python -m server.brain.worker`, speaking JSON lines on stdin/stdout, like `gpt_sovits_server.py`. That keeps 400 MB of arrays and numba threads out of the asyncio server, and a crash only costs the fly its brain.

Messages from the worker:

- On start (stdout only carries protocol lines; logs go to stderr):
  - `{"status":"loading","stage":"fetch|build|load|jit","progress":0.4}` (any number of these)
  - then `{"status":"ready","neurons":166700,"connections":25582938,"synapses":124177617,"populations":{"sugar":77,…},"gain":0.65}`

Requests and replies:

- **run:**
  - request: `{"cmd":"run","id":7,"ms":500,"seed":123,"stim":[{"pop":"sugar","rate":150,"side":"both"}],"noise":{"frac":0.0,"rate":0},"reset":true}`
  - reply: `{"status":"ok","id":7,"rates":{pop:hz},"bins":{pop:[10 floats]},"spikes":N,"active":M,"sim_ms":500,"wall_ms":812}`
  - `rates` and `bins` cover every named population, plus `total` and `active`.
- **reset** (`{"cmd":"reset"}`), **ping** (`{"cmd":"ping"}` → `{"status":"pong"}`), **quit** (`{"cmd":"quit"}`).
- **errors:** `{"status":"error","id":7,"error":"…"}`.

**Changed during implementation: each window starts from rest.** The design carried brain state (v, g, refractory, ring) between windows, so that a fly that just escaped would still be aroused. At the calibrated gain, the state carried out of an insult or a strong puff of air keeps ~0.6 M spikes per window going with no input and never decays (§3.7), so every later reaction would start from that state instead of from a resting fly. So a `run` request with `"reset": true` returns the engine to rest first, making each reaction a trial from rest, as in Shiu 2024. The fly sends `reset: not brain.persist`, and `brain.persist` defaults to `false`. Setting `persist: true` restores the original carry-over.

On the server side, `server/brain/client.py` runs blocking I/O in a thread and gives each request a 10 s timeout. After a crash it restarts, with a 30 s cooldown. It sends `{"cmd":"quit"}` itself, avoiding the `command`/`cmd` mismatch in the SoVITS client. It exposes `async run(stim, ms, seed, noise, reset=False) -> BrainWindow | None`, where `None` means brainless.

### 3.7 Self-sustaining activity (re-measured in the final review)

Single 500 ms windows from rest behave as in §3.2–3.3. Across windows, though, the network at gain 0.65 has a second, **self-sustaining state** (drive one window from rest, then run quiet windows with no input and no reset):

- **Strong drive tips it in.**
  - After an insult (bitter 100 Hz), about 12,900 neurons keep firing at ~0.6 M spikes per 500 ms with no input at all, and the activity does not decay.
  - A puff of air (antenna 100 Hz) does the same on some seeds, and leaves ~75 k spikes per window on others.
  - A threat (loom 150 Hz) leaves a smaller persistent state: ~50 k spikes per window, ~3,700 neurons.
  - Chat, food, affection and an arrival settle to a few dozen or a few hundred neurons.
- **Sparse noise tips it in too.** With idle noise at `frac` 0.002 and 5 Hz, about 1 window in 10 from rest reaches it (2 of 20 in calibration, 4 of 40 in a longer probe). Denser noise does so more often (§4.5).
- **Every useful gain has it.** Carry-over jumps between gains 0.62 and 0.63, from 61 k to 570 k spikes per quiet window (§3.2). Every gain at which one food word reliably feeds is above the jump.
- **It drives no behavior.** In self-sustaining windows MN9 reads 13–18 Hz and aDN 2–4 Hz, and the giant fiber and the bitter GRNs read 0. The result is NOTHING.

*Corrected in the final review:* the first build reported "ignition" at gain 0.5, self-sustaining at ~1.7 M spikes per window, with GNG016 driving the LB1 bitter GRNs to ~46 Hz during it. Both numbers came from its engine departures (§3.1). On the faithful engine the self-sustaining state is about a third of that size, and the bitter GRNs stay silent in it.

**What was done:**

1. Each window starts from rest (§3.6), as in Shiu 2024.
2. REJECT keys on the bitter taste *delivered* this window (§4.2). The faithful engine no longer fakes bitter, so correctness no longer needs this. It stays anyway: a taste is what was delivered, and the rule keeps any central drive of the GRN terminals from ever reading as one.

With both, every calibration sense line classifies as intended (§4.1), and every window ends within 0.65 s on the dev box.

**What was not done, and is the user's call:** a biologically grounded fix, such as spike-frequency adaptation or short-term synaptic depression, that would let state carry across windows, so that a fly that just escaped stays aroused. Each of these changes the model away from Shiu's plain LIF, and should be validated against §3.3 again.

---

## 4. Piece 1: the fly character

### 4.1 Senses: event → stimulus (deterministic)

`server/brain/senses.py` turns an event into a list of `(population, rate_hz, side)`. The lexicons are character data, in `characters/fly/brain/senses.yaml`, so they can be edited without code. The rules:

| Event | Stimulus |
|---|---|
| any chat text (it is sound) | `ears` 50 Hz; 120 Hz if shouted (ALL CAPS word or `!!`) |
| food/sweet words (sugar, candy, cake, fruit, banana, beer, wine, juice, soda, honey, pizza…) | `sugar` **150–200 Hz** by match count (calibrated at gain 0.65: MN9 ~90 Hz at 150 Hz, ~98 Hz at 200 Hz; one food word with chat sound feeds on 8 of 8 seeds) |
| affection/praise words (love, cute, good, nice, beautiful, best, sweet…) | `sugar` **60–100 Hz** (a faint taste: below MN9 drive, so "cute" alone gives NOTHING) |
| gross/insult words (gross, disgusting, hate, ugly, stupid, shut up, poison, bleach…) and profanity | `bitter` 100–200 Hz |
| threat words (swat, squash, smash, kill, spray, raid, zapper, swatter, newspaper, slipper) | `loom` 150–200 Hz, one side (random) |
| air/touch words (blow, wind, fan, dust, wash, clean, dirty, tickle, soap, hair) | `antenna` 100–150 Hz |
| person arrives (face greeting / presence) | `loom` 80 Hz, one side (something big approaching) |
| retching detected (`audio_distress`) | `sugar` 150 Hz. Flies are drawn to vomit; that is what a fly does. `senses.yaml` can flip it. |
| idle tick | no stimulus; background noise (§4.5) |

- **No emotion fallback:** valence comes only from the lexicons. The keyword inference in `server/emotions.py` (`_infer_emotion_from_text`) is Mario-flavored ("wahoo", "mama mia") and is not reused.
- **Combining:** when several senses fire, all stimuli run together in one window. The brain arbitrates; for example, sugar plus bitter gives MN9 suppression (§3.4).
- **Affection cap (final review):** every text is also sound, so affection always arrives with `ears`. At 120 Hz plus chat sound, MN9 crossed the feeding line on 4 of 8 seeds. At 100 Hz it peaks at 77 Hz, with chat sound or shouting (0 of 8). The top rate is therefore 100 Hz.
- **Measured** (`calibration.json` senses, gain 0.65), every line as intended:
  - "hello there", "HEY WHAT IS UP!!", "you're so cute" → NOTHING;
  - "have some candy" → FEED 0.37; "cake and beer and candy" → FEED 0.40;
  - "you are disgusting", "ew gross you stupid bug" → REJECT 1.00;
  - "I'm gonna swat you", "get the fly swatter" → ESCAPE 1.00;
  - "blow on it", "so much dust in here" → GROOM 0.96.

### 4.2 Behavior: readout → one behavior

`server/brain/behavior.py` reads mean rate per neuron in each readout population over the window. Rules are applied in priority order, and the first one that matches wins:

| Behavior | Rule (defaults in `brain.behavior`, re-derived by calibration) | Emotion | Pose |
|---|---|---|---|
| ESCAPE | `escape` ≥ 50 Hz | scared | movement/escape |
| REJECT | bitter **taste delivered this window** ≥ 20 Hz **and** `feed` < FEED threshold: tasted bitter, did not extend the proboscis. (Changed during implementation: the first build's engine drove the LB1 terminals centrally, §3.7, so the measured rate could not stand for taste. The faithful engine does not, and the rule stays because a taste is what was delivered. `classify(rates, thresholds, stim)` falls back to the measured rate only when called without a stimulus map.) | disgusted | negative/reject |
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
  - **Where:** the fly bypasses the TTS router entirely (see §5.4). `server/brain/voice.py` calls Edge directly and applies the effect configured under `brain.voice` (`carrier_hz`, `mix`, `bed`).
  - **Cache:** the TTS cache stores pre-effect audio, so a later effect change never poisons the cache (see memory note: voice-side changes are invisible to `purge_stale_cache`).
- **ESCAPE:** a procedural takeoff buzz. It lasts 0.5 s, sweeps 180→230 Hz, and is amplitude-modulated. It is generated in numpy, with no TTS.
- **NOTHING:** no audio.
- **Flag for the user:** this is Edge-based. The user has said "never Edge" for *Mario's numbers*. It does not apply here, since the fly has no trained voice and the ring mod dominates the timbre. It is flagged anyway.

### 4.5 Idle: spontaneous behavior

- **Noise window:** on each idle-loop tick (existing cadence and gates), the fly runs one window with **no stimulus** and **background noise**: independent Poisson input to a random `noise.frac` of all sensory neurons at `noise.rate` Hz.
- **Output:** whatever behavior emerges is shown. Silent behaviors (GROOM, NOTHING) change pose and panel only; FEED and WALK can speak their lexicon words (lexicon only; idle never calls the LLM).
- **Calibration:** `scripts/brain_calibrate.py` reports what fraction of noise windows produce each behavior. It sets `noise.frac` and `noise.rate` so that roughly 20–40% of idle windows produce *some* behavior, which leaves the fly alive but not frantic.
- **Measured: the 20–40% target is not reachable.** At gain 0.65, across `frac` 0.001–0.05 × `rate` 5–20 Hz (20 windows each, from rest), all 360 windows gave NOTHING. Denser noise does not produce behavior. It only tips more windows into the self-sustaining state of §3.7 ("busy": over 100 k spikes), and even there the readouts stay under their thresholds:
  - 0.002 × 5 Hz: 2 of 20 windows busy;
  - 0.005 × 5 Hz: 9 of 20;
  - 0.02 × 10 Hz: 20 of 20.
- **Chosen:** `noise: {frac: 0.002, rate: 5}`, kept from the first build. It gives a median of 92 spikes per window, with about 1 window in 10 busy (at most 0.57 s wall). 0.001 × 5 Hz gives 0 of 20 busy, but the fly is just as still.
- **Live:** in the first build's live test, 12 idle windows over 150 s were all NOTHING, with no speech. The re-test after the final review is in §10.
- **So the idle fly is still.** Its panel shows live noise activity; its pose does not change. This is true to the animal (§8) but short of the design's "alive" target. Livelier idle probably needs the §3.7 fix, or an idle stimulus (e.g. faint `ears` from room noise), rather than more noise.
- **No other idle content:** no Mario idle content, loneliness tiers, gossip, DJ lines, scheduled lines or memorial events run for the fly (§5.3).

### 4.6 Brain panel (pygame client, primary display)

`_draw_brain_panel()` in `client/mario_display.py` follows the pattern of `_draw_health_overlay`. It is on by default for brain characters and toggled with **B** outside typing mode (every F-key is already taken; F9/F10 are volume).

- **Header:** "MaleCNS v1.0 · 166,700 neurons · 25.6 M connections".
- **Sensory rows:** SWEET, BITTER, EARS, ANTENNA, LOOM.
- **Motor rows:** FEED, GROOM, ESCAPE, WALK, BACK.
- **Row contents:** a rate bar (log-scaled to 400 Hz) and a 10-bin sparkline over the window.
- **Status lines:** the behavior (e.g. "→ FEEDING"), then "spikes 368,532 · active 10,508 · 0.5 s fly-time".
- **Credit footer (CC BY):** "Connectome: MaleCNS v1.0, Janelia FlyEM et al., CC BY 4.0 · LIF after Shiu et al. 2024 · bitter taste group inferred".
- **As built:** the layout is measured from the display font (`_brain_panel_layout`). The header is split into three lines, and the stats add real time next to fly-time ("0.5s fly-time · 1.58s real"). The panel sits below the floating emotion badge and is drawn under the speech bubble, so the fly's words stay readable. The plan's fixed offsets clipped the header and ran labels into the bars at the client's real font; the live test caught it.

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
  # cache_dir: <path>  # optional; default is the per-user cache (§2)
  auto_fetch: true
  gain: 0.65
  window_ms: 500
  threads: 0
  persist: false       # each window starts from rest (§3.6, §3.7)
  behavior: {escape_hz: 50, feed_hz: 80, bitter_hz: 20, groom_hz: 30, walk_hz: 20}
  noise: {frac: 0.002, rate: 5}      # idle; from calibration.json "idle" (§4.5)
  words: {llm: true, max_words: 6, timeout_s: 3}
  voice: {carrier_hz: 200, mix: 0.55, bed: 0.06}   # wing-buzz ring mod (§4.4)
```

`shared/character_loader.py` gains `self.brain = self._config.get("brain") or {}`. Every other character has no `brain:` block and is unaffected.

---

## 5. Server integration

### 5.1 Lifecycle

- **Startup:** in `lifespan` (`server/main.py` ~856–936), if `char_loader.brain.enabled` is set, `FlyBrain` is built and the worker starts in the background. Startup never waits for the brain.
- **Character switch:** `admin_switch_character` (~3285–3376) starts or stops the worker to match the new character.
- **Canary:** not extended. `GET /api/brain` (§5.5) reports readiness, and a canary check would duplicate it.

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
5. Synthesize with `FlyVoice` (Edge direct + ring mod, §5.4), or the takeoff buzz for ESCAPE.
6. Send `brain_state`, then `send_response` with `pose_hint`, emotion and `is_idle=False`.

There is no chat history, memory write or gossip update; `party_stats` visit counting is kept. When the brain is `None` (brainless), the fly gives NOTHING: no words, the idle pose, and a panel showing "brain loading" or "brain offline".

*As built:* `_generate_and_send_response` turned out to have no visit counting to keep, so the fly does none. The per-message transcript line (`mario.conversation`) is still written by the text dispatcher. That is a log file, not memory.

### 5.3 Other outbound surfaces (leak gating)

For a brain character, these paths are suppressed or replaced:

- **Idle loop:** content selection is replaced with the brain idle window (§4.5). Announcements from `/admin/announce` stay, because they are admin-authored.
- **Replaced by the brain window:** face greetings and exit flows go through `_generate_and_send_response`, so the §5.2 branch covers them with `source` → a looming event.
- **Suppressed:** startup greeting text (replaced by one noise window), sick/distress comfort lines (retching becomes a sense event instead), performed songs, DJ lines, memorial events, catchphrase mirror, and trivia/vision idle.
  - *As built:* the startup greeting is dropped at the chokepoint below. On connect the client gets a `brain_state` panel, and the idle loop's first tick runs the first noise window.
  - *As built:* the admin endpoints `/admin/trigger_memorial` and `/admin/trigger_event/{name}` refuse for a brain character, because both send scripted audio raw, past the chokepoint.
  - *As built:* the retch reaction keeps the comfort path's 20 s cooldown and fall-through.

**Mechanism: one chokepoint, not thirty patches.** `server/main.py` has 30+ `send_response(...)` call sites: greetings, goodbyes, wash reminders, celebrations, error and timeout texts, songs and idle pools. Rather than gate each one, `send_response` gains a keyword `_brain_ok=False`. When the active character's config has `brain.enabled`, any send without `_brain_ok=True` is dropped and logged as `[BRAIN] suppressed non-brain send`.

- **Keyed on config, not health:** a brain character whose worker failed still cannot leak.
- **The brain path** (`_brain_respond`, the brain idle tick, admin announcements spoken by the fly) passes `_brain_ok=True`.
- **Raw senders:** three places build a raw `{"type": "mario_response"}` without `send_response` (the idle no-TTS branch, the LLM block, and the text-input error path). The first two are unreachable for a brain character, because of the §5.2 early return and the idle branch. The third gets the same check.
- **Retching:** audio distress for a brain character becomes a `retch` sense event (§4.1) instead of comfort lines.

### 5.4 Fly voice path (bypasses the TTS router)

The fly does **not** go through `tts.synthesize` or the TTS router. There are two reasons, both found while planning:

1. `config.json` has `server.tts_mode: sovits`, which is global. `tts.synthesize` would send the fly to GPT-SoVITS base weights, zero-shot cloning whatever reference clip is loaded, which is another character's voice.
2. The router's last resort is `pre_recorded`, which holds Mario clips.

Instead, `FlyVoice` calls `tts._synthesize_edge(text)`. That uses the Edge voice/rate/pitch that `tts.set_voice_config` already set from the fly's `voice:` block, and never applies RVC to a non-Mario character. `FlyVoice` then applies the ring mod, and keeps its own small in-memory LRU of dry clips (the fly's vocabulary is tiny). If Edge fails (no network), the fly buzzes instead of speaking. There is no fallback that could leak another voice. The ESCAPE buzz bypasses TTS too.

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
    - a stimulated neuron fires at the requested rate, with no refractory period;
    - chain firing with the 1.8 ms delay;
    - inhibition blocks;
    - a driven neuron fires again exactly 22 steps after it fired;
    - a spike resets the synaptic drive;
    - one event matches the closed-form solution;
    - silence stays silent;
    - determinism per seed;
    - parallel propagation = serial.
  - Engine against a per-step reference simulator in Brian2's order on a random 400-neuron net: bit-identical counts, `u` and `g`, serial and parallel (added in the final review; 9 of the 15 engine tests fail on the first build's engine).
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
  - *Measured at the end of implementation:* 38 failed / 1768 passed / 3 skipped, with the failing set identical to the baseline (0 new, 0 fixed). The +94 passing are the brain tests.
  - *Command:* `pytest tests/ --ignore=tests/convert_and_test.py --ignore=tests/test_mcp_chatgpt_browser.py`. A bare `pytest` also collects `server/test_gpt_sovits.py`, a script that exits at import.
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
| Busy windows are too slow | Parallel engine (§3.5), with fallback to a 300 ms window. *Measured:* the busiest window takes 0.63 s, well inside the target (§3.5). |
| Idle is too quiet (a fly mostly does nothing) | Noise calibration target (§4.5). Stillness is acceptable, and is true to the animal. *Measured:* this risk landed. Idle is all NOTHING (§4.5). |
| Carried state never settles (found during implementation) | Reset per window (§3.6, §3.7); REJECT keyed on the delivered taste. A biological fix is open. |
| The engine departs from the model it credits (found in the final review) | Rebuilt to Brian2's schedule and pinned bit for bit against a reference simulator (§3.1). Every number was re-measured. |
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

## 10. Live test (measured 2026-09-25, dev box)

The setup was `config.json` → `fly`, then a fresh server and client launched from the worktree with the venv python. `/api/brain` reported `ready` about 50 s after the worker spawned. Each prompt went through `/admin/simulate_text`. Evidence comes from `/api/brain` `last` and `logs/2026-09-25/client.log`.

| Prompt | Stimulus | Behavior | Words | Audio (bytes) | `_play_wav` | Window |
|---|---|---|---|---|---|---|
| "Hey who are you?" | ears 50 | NOTHING | none | none | n/a | 4.3 k spikes, 0.27 s |
| "Do you know Mario?" | ears 50 | NOTHING | none | none | n/a | 4.0 k, 0.27 s |
| "Tell me a fun fact!" | ears 50 | NOTHING | none | none | n/a | 4.1 k, 0.27 s |
| "What's your favorite game?" | ears 50 | NOTHING | none | none | n/a | 4.1 k, 0.27 s |
| "have some candy" (×2) | ears 50 + sugar 150 | FEED (MN9 246–249 Hz) | "yum. more. more." / "eat eat eat. more." | 159,020 / 119,852 | playing → done | 338 k, 0.62 s / 1.10 M (ignited), 1.19 s |
| "you're disgusting" | ears 50 + bitter 100 | REJECT (MN9 30 Hz) | "no no no. bitter." | 100,268 | playing → done | 727 k, 0.88 s |
| "I'm gonna swat you" (×2) | ears 50 + loom 150 (L) | ESCAPE (giant fiber 239 Hz) | none (buzz) | 24,044 | playing → done | 1.24 M, 1.29 s / 1.58 s |
| "blow on it" | ears 50 + antenna 100 | GROOM (aDN 263 Hz) | "dust. clean. clean." | 164,780 | playing → done | 1.21 M, 1.26 s |

- **Leak test:** zero "Mario" in any spoken or displayed fly line. The four leak prompts produce NOTHING (sound alone), which is the fly's honest answer to a question.
- **Idle, 150 s:** 12 windows, all NOTHING, no speech, and a pose update reached the client for each window (§4.5).
- **Latency:** text in → audio out took 4.95 s for "have some candy". Of that, the brain window was 1.19 s, the LLM words about 3 s (llama3 8B on the P1000, at the edge of the 3 s words timeout), and Edge plus ring mod 0.74 s.
- **Screenshot:** the ESCAPE pose, with the panel showing all 11 rows, "-> ESCAPE", "spikes 1,234,973 · active 19,583", "0.5s fly-time · 1.58s real", and the full CC BY credit.
- **Observed, not fixed:**
  - The pygame client shows its own local "Server connected! Here we go!" bubble on connect. It is client chrome shared by every character; it contains no Mario text.
  - ESCAPE sends an empty text with the buzz; the client draws no bubble for it.
