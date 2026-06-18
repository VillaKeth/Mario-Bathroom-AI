# Wizard Fine-Tune Voice (default) — Design

**Date:** 2026-06-18
**Status:** Approved (design), pending implementation plan

## Goal

Make a **GPT-SoVITS fine-tuned voice the wizard's default** — a faithful,
character-accurate voice — instead of the current quick zero-shot clone. The
wizard lets the user search YouTube for the character's voice, **multi-select
videos and multiple regions within each video** via an in-browser waveform
editor, then builds a training dataset from those regions and runs the fine-tune,
blocking until the real voice is ready. Machines without a capable GPU fall back
to the instant zero-shot/Edge voice with a clear note, so the wizard still
completes everywhere.

Guiding principle (user's words): *"cheap, fast, good — pick two; we're not
taking fast."* Faithfulness over speed.

## Background (what already exists — reuse it)

- **`character_creator/server.py`**:
  - `POST /api/voice/search` (~135) — YouTube search via `voice_finder.search`.
  - `POST /api/voice/download` (~149) + `POST /api/voice/download_multi` (~164) — clip download.
  - `GET /api/hardware` (~41) — `hardware.detect_hardware()` → `gpu_vram_gb`, tier.
  - `POST` calls `prepare_voice_artifacts` (~507) — current zero-shot path.
- **`character_creator/voice_finder.py`**: `search`, `download_full(url, out)`,
  `cut_sections(in_wav, [{start,end}], out_dir, base)`, `concat_wavs(pieces, out, max_duration)`.
- **`scripts/build_voice_dataset.py`**: slices a wav → 3-10s segments → Whisper
  transcribes → writes `characters/<char>/voice/dataset/<char>.list`. Reads
  `characters/<char>/voice/dataset/raw/*.wav`.
- **`scripts/fine_tune_voice.py`**: headless GPT-SoVITS v2 fine-tune (1a/1b/1c →
  s2 → s1), env `FT_S2_EPOCHS`/`FT_S1_EPOCHS`; weights → `gpt_sovits_repo/{SoVITS_weights_v2,GPT_weights_v2}`
  then discoverable model dir. Emits per-epoch `INFO:<char>:====> Epoch: N`.
- **`server/hardware.py`**: `detect_hardware()` (torch.cuda or nvidia-smi), `gpu_vram_gb`.
- **`character_creator/static/wizard.js`**: Step 2 = Voice (~209); edge-voice
  select, rate/pitch, validation at `case 2` (~365).
- **No waveform lib vendored yet** (only `wizard.js`, `sprites.js` in `static/`).

## Decisions (from the user)

1. **No/weak GPU → fall back to zero-shot/Edge** with a clear note. Wizard still completes.
2. **Blocking**: the wizard waits for training; the character is not "ready" until the faithful voice is done.
3. **Dataset = auto-search + user multi-select**, with an **in-browser audio editor**; the user can select **multiple regions per video** and across multiple videos.

## Architecture / Flow

```
Wizard Step 2 (Voice):
  GPU check (GET /api/hardware)
    ├─ no capable GPU → "fine-tune needs a GPU; using a quick voice" → zero-shot/Edge (existing path) → done
    └─ GPU present (default path):
        1. user types/accepts search query → POST /api/voice/search → results
        2. user picks videos; each opens the WAVEFORM EDITOR:
             - download that video's audio (POST /api/voice/download_full_for_edit)
             - wavesurfer.js + regions: user drags MULTIPLE regions (start,end) to keep
        3. user submits all selections: { picks: [{url, regions:[{start,end},...]}, ...] }
             → POST /api/voice/build_dataset:
                  for each pick: download_full → cut_sections(regions) → collect pieces
                  copy/normalize pieces into characters/<char>/voice/dataset/raw/
                  run build_voice_dataset → <char>.list
             → POST /api/voice/train (or part of build_dataset):
                  run fine_tune_voice (s2=8/s1=4) as a tracked background job
                  BLOCKING SCREEN: "Training a faithful voice — ~1-2 hr, keep this open" + epoch progress bar
                  poll GET /api/voice/train_status → {stage, epoch, total_epochs, pct, done, error}
             → on done: set character.yaml voice → trained model (finetuned_model + preferred_engine sovits)
```

## Components

### 1. Frontend — audio editor + voice step (`character_creator/static/`)
- **Vendor `wavesurfer.js` + regions plugin** (single local file under `static/vendor/`, no CDN at runtime).
- New `voice_editor.js` (or a section in `wizard.js`): for a selected video, render the
  waveform, let the user add/drag/delete **multiple regions**, list them (start–end,
  duration), and collect `[{start,end}]`. A small play-region button per region.
- Voice step UI: search box + results (title, duration, "add" button), a tray of
  selected videos each showing its region count + an "edit" button (opens the editor),
  a running "total selected audio" readout (warn if < ~60s — thin dataset).
- Training screen: big banner + indeterminate→epoch progress bar, polls `train_status`.
  Cannot advance/finish until `done`.
- No-GPU branch: hide the fine-tune UI, show the existing edge/zero-shot controls + the note.

### 2. Backend endpoints (`character_creator/server.py`)
- `POST /api/voice/download_full_for_edit` — `voice_finder.download_full(url, draft/edit/<id>.wav)`;
  returns a static URL the editor can load into wavesurfer. (Cache by video id.)
- `POST /api/voice/build_dataset` — body `{char, picks:[{url, regions:[{start,end}]}]}`:
  for each pick `cut_sections` the regions (reuse the already-downloaded edit wav),
  write pieces into `characters/<char>/voice/dataset/raw/`, then run
  `scripts/build_voice_dataset` logic → `<char>.list`. Returns segment/duration stats.
- `POST /api/voice/train` — start `fine_tune_voice` for `<char>` as a background job
  (env `FT_S2_EPOCHS=8 FT_S1_EPOCHS=4`); returns a job id.
- `GET /api/voice/train_status?char=` — parse the job log for the latest
  `====> Epoch: N` and the s2/s1 stage → `{stage, epoch, total, pct, done, error}`.
  On `done`: patch `character.yaml` voice block (`preferred_engine: sovits`,
  `finetuned_model: GPT_SoVITS_<Char> (...)`).
- `GET /api/voice/can_finetune` — `hardware.detect_hardware()`; capable if a CUDA GPU
  with ≥ ~4 GB VRAM AND the sovits env/weights are installed (reuse
  `voice_trainer.get_engine_status('sovits')`). Drives the wizard's GPU branch.

### 3. Backend orchestration (reuse, thin wrappers)
- A small `character_creator/voice_finetune.py`: `build_dataset_from_picks(char, picks)`,
  `start_training(char)`, `training_status(char)` — wrapping `voice_finder`,
  `build_voice_dataset`, `fine_tune_voice` so `server.py` stays thin and the logic is
  unit-testable without the web layer.

### 4. Wizard build flow (`character_creator/character_builder.py`)
- Today `build_character` writes the character then `prepare_voice_artifacts` (zero-shot).
- New: when the fine-tune path is used, the trained model is already wired by
  `train_status`'s on-done patch; `character_builder` should NOT overwrite it with the
  zero-shot engine. The fine-tune happens in the wizard step BEFORE the final "create"
  (blocking), so by build time the voice yaml is already trained-model. No-GPU path keeps
  the existing zero-shot wiring.

## Data flow

```
search → user picks videos + regions → download_full (per video, cached)
  → cut_sections(regions) → raw/*.wav → build_voice_dataset → <char>.list
  → fine_tune_voice (blocking, progress) → GPT_SoVITS_<Char> weights
  → character.yaml: preferred_engine=sovits, finetuned_model=GPT_SoVITS_<Char>
No-GPU: skip all above → prepare_voice_artifacts (zero-shot/edge) + note
```

## Edge cases

- **No GPU / no sovits env** → fall back to zero-shot/Edge + note; wizard completes.
- **Thin dataset** (user selected < ~60s) → warn before training; allow proceed (their call).
- **Training crash / OOM** → `train_status` surfaces `error`; wizard shows it + offers
  retry or fall-back-to-zero-shot.
- **User closes the tab mid-training** → training is a detached background job; on
  reopen, `train_status` resumes reporting (job keyed by char). (Blocking = the UI waits,
  but the job survives a refresh.)
- **No transcribable speech in a region** (music only) → `build_voice_dataset`'s Whisper
  drops empty segments; if the whole dataset is empty, surface an error pre-train.

## Testing

- **Unit** (`tests/test_voice_finetune.py`): `build_dataset_from_picks` cuts the right
  regions and writes a `<char>.list` with the expected segment count (use a short fixture
  wav + fake regions; mock Whisper). `training_status` parses epoch/stage from sample log
  lines. `can_finetune` returns False when no CUDA / no sovits env (monkeypatch hardware).
- **Integration**: `/api/voice/build_dataset` end-to-end on a tiny fixture (no real train).
  `/api/voice/can_finetune` reflects hardware.
- **Manual**: full wizard run on the GPU box — search, multi-region edit, train with live
  progress, character ends on the trained voice; and a no-GPU run falls back cleanly.
  Audio verification per `.claude/rules/testing.md` (the trained voice actually plays).

## Future (not in scope)

- Live region preview synthesized from the partial checkpoint.
- Resumable training UI (pause/continue) — currently blocking, job survives refresh.
- Per-character epoch tuning in the UI (advanced).
