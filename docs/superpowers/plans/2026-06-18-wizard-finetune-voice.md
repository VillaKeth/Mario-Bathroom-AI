# Wizard Fine-Tune Voice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make a GPT-SoVITS fine-tuned voice the wizard default — YouTube search → multi-select videos + multiple regions each via an in-browser waveform editor → build dataset → blocking fine-tune with progress → trained voice; no-GPU falls back to zero-shot/Edge.

**Architecture:** Thin web endpoints over a new `character_creator/voice_finetune.py` that wraps the existing `voice_finder` / `build_voice_dataset` / `fine_tune_voice`. Frontend adds a vendored wavesurfer.js region editor + a blocking training screen. Backend is fully unit-testable; frontend + full train are manual/visual.

**Tech Stack:** Python (FastAPI in `character_creator/server.py`), vanilla JS wizard, wavesurfer.js, GPT-SoVITS (`gpt_sovits_env`), faster-whisper.

**Spec:** `docs/superpowers/specs/2026-06-18-wizard-finetune-voice-design.md`

---

## File Structure

- **Create** `character_creator/voice_finetune.py` — orchestration (dataset-from-picks, start/poll training, can-finetune). One clear responsibility, no web/pygame deps.
- **Create** `tests/test_voice_finetune.py` — unit tests for the module.
- **Modify** `character_creator/server.py` — 4 endpoints (download_full_for_edit, build_dataset, train, train_status) + can_finetune.
- **Modify** `character_creator/static/wizard.js` — voice step: search/multi-select, open editor, GPU branch, blocking train screen.
- **Create** `character_creator/static/voice_editor.js` — wavesurfer region editor (multi-region per video).
- **Add** `character_creator/static/vendor/wavesurfer.min.js` (+ regions plugin) — vendored, no runtime CDN.
- **Modify** `character_creator/character_builder.py` — don't overwrite the trained voice when the fine-tune path ran.

---

### Task 1: `voice_finetune.py` — can_finetune + status parsing (TDD)

**Files:** Create `character_creator/voice_finetune.py`, `tests/test_voice_finetune.py`

- [ ] **Step 1: Failing tests**

```python
# tests/test_voice_finetune.py
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from character_creator import voice_finetune as vf


def test_parse_status_reads_epoch_and_stage():
    log = "INFO:pomni:start training\nINFO:pomni:====> Epoch: 3\nsome s2 line\n"
    st = vf.parse_training_status(log, total_s2=8, total_s1=4)
    assert st["stage"] in ("s2", "s1")
    assert st["epoch"] == 3
    assert 0 <= st["pct"] <= 100
    assert st["done"] is False


def test_parse_status_done_on_marker():
    log = "INFO:pomni:====> Epoch: 4\n[ft] DONE GPT_SoVITS_Pomni copied\n"
    st = vf.parse_training_status(log, total_s2=8, total_s1=4)
    assert st["done"] is True


def test_can_finetune_false_without_cuda(monkeypatch):
    monkeypatch.setattr(vf, "_gpu_vram_gb", lambda: 0.0)
    monkeypatch.setattr(vf, "_sovits_installed", lambda: True)
    assert vf.can_finetune()["ok"] is False


def test_can_finetune_true_with_gpu_and_env(monkeypatch):
    monkeypatch.setattr(vf, "_gpu_vram_gb", lambda: 6.0)
    monkeypatch.setattr(vf, "_sovits_installed", lambda: True)
    assert vf.can_finetune()["ok"] is True
```

- [ ] **Step 2: Run → fail** `venv/Scripts/python.exe -m pytest tests/test_voice_finetune.py -v` (ModuleNotFound).

- [ ] **Step 3: Implement** `character_creator/voice_finetune.py`:

```python
"""Wizard fine-tune orchestration — wraps voice_finder/build_voice_dataset/fine_tune_voice.
Web-free + pygame-free so it is unit-testable. The wizard server calls these."""
import os, re, subprocess, sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Markers the fine-tune emits (see scripts/fine_tune_voice.py).
_EPOCH_RE = re.compile(r"====> Epoch:\s*(\d+)")
_DONE_RE = re.compile(r"\[ft\]\s+DONE|copied into|GPT_SoVITS_\w+/")


def _gpu_vram_gb() -> float:
    sys.path.insert(0, os.path.join(BASE, "server"))
    import hardware
    return float(hardware.detect_hardware().get("gpu_vram_gb") or 0.0)


def _sovits_installed() -> bool:
    from character_creator.voice_trainer import get_engine_status
    return bool(get_engine_status("sovits").get("available"))


def can_finetune() -> dict:
    vram = _gpu_vram_gb()
    ok = vram >= 3.5 and _sovits_installed()
    return {"ok": ok, "vram_gb": vram, "sovits": _sovits_installed(),
            "reason": "" if ok else ("needs a CUDA GPU (>=4GB)" if vram < 3.5
                                       else "GPT-SoVITS not installed")}


def parse_training_status(log: str, total_s2: int = 8, total_s1: int = 4) -> dict:
    done = bool(_DONE_RE.search(log))
    epochs = [int(m) for m in _EPOCH_RE.findall(log)]
    epoch = epochs[-1] if epochs else 0
    # s2 runs first (total_s2 epochs), then s1 (total_s1). Rough overall pct.
    in_s1 = log.count("s1_train") > 0 or epoch > total_s2
    stage = "s1" if in_s1 else "s2"
    total = total_s2 + total_s1
    seen = (epoch if not in_s1 else total_s2 + max(0, epoch - total_s2))
    pct = 100 if done else int(min(99, 100 * seen / max(1, total)))
    return {"stage": stage, "epoch": epoch, "total": total, "pct": pct, "done": done}
```

> Adjust `_DONE_RE` / the s1 detection to the ACTUAL strings `scripts/fine_tune_voice.py` prints at completion and at the s1 stage — read that script first and match its real markers.

- [ ] **Step 4: Run → pass.** Commit `git add character_creator/voice_finetune.py tests/test_voice_finetune.py && git commit`.

---

### Task 2: `build_dataset_from_picks` (TDD)

**Files:** Modify `character_creator/voice_finetune.py`, `tests/test_voice_finetune.py`

- [ ] **Step 1: Failing test** — with a short fixture wav + regions, asserts pieces are cut and a `<char>.list` is produced (mock Whisper to return fixed text).

```python
def test_build_dataset_from_picks_cuts_regions(tmp_path, monkeypatch):
    # fixture: a 6s sine wav; one pick with two regions
    import wave, struct, math
    wavp = tmp_path / "edit_v1.wav"
    with wave.open(str(wavp), "w") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(32000)
        for i in range(32000*6):
            w.writeframes(struct.pack("<h", int(8000*math.sin(i/20))))
    monkeypatch.setattr("character_creator.voice_transcribe.transcribe_file",
                        lambda p, **k: {"text": "hello there", "language": "en"})
    n = vf.build_dataset_from_picks("testc", [{"edit_wav": str(wavp),
        "regions": [{"start": 0.5, "end": 3.0}, {"start": 3.5, "end": 5.5}]}],
        char_root=str(tmp_path))
    assert n >= 1
    assert (tmp_path / "testc" / "voice" / "dataset" / "testc.list").exists()
```

- [ ] **Step 2: Run → fail.**

- [ ] **Step 3: Implement** `build_dataset_from_picks(char, picks, char_root=...)`: for each pick, `voice_finder.cut_sections(edit_wav, regions, raw_dir, base)` into `characters/<char>/voice/dataset/raw/`, then run the slicing+transcribe logic from `scripts/build_voice_dataset.py` (import its functions; do NOT duplicate) to write `<char>.list`. Return usable-segment count.

> Read `scripts/build_voice_dataset.py` and import its `slice_audio`/transcribe loop rather than re-implementing. If it's only a `__main__` script, refactor its core into an importable function first (small, in-scope).

- [ ] **Step 4: Run → pass. Commit.**

---

### Task 3: Training job control (start/status, background)

**Files:** Modify `character_creator/voice_finetune.py` (+ test the status file logic)

- [ ] `start_training(char)` — spawn `gpt_sovits_env/Scripts/python.exe scripts/fine_tune_voice.py <char>` with `FT_S2_EPOCHS=8 FT_S1_EPOCHS=4`, detached, log → `characters/<char>/voice/finetune.log`. Idempotent (no double-start if already running). Returns `{started, log}`.
- [ ] `training_status(char)` — read the log, call `parse_training_status`. On `done`, patch `character.yaml` voice (`preferred_engine: sovits`, `finetuned_model: GPT_SoVITS_<Char> (s2=e8, s1=e4)`).
- [ ] Test the on-done yaml patch with a fake "done" log + a temp char dir.
- [ ] Commit.

---

### Task 4: Backend endpoints (`character_creator/server.py`)

**Files:** Modify `character_creator/server.py`

- [ ] `GET /api/voice/can_finetune` → `voice_finetune.can_finetune()`.
- [ ] `POST /api/voice/download_full_for_edit` `{url}` → `voice_finder.download_full` into a per-id edit cache under the draft voice dir; return a static-served URL + the cached path id.
- [ ] `POST /api/voice/build_dataset` `{char, picks:[{edit_id|edit_wav, regions:[...]}]}` → `voice_finetune.build_dataset_from_picks`; return `{segments, seconds}`.
- [ ] `POST /api/voice/train` `{char}` → `voice_finetune.start_training`.
- [ ] `GET /api/voice/train_status?char=` → `voice_finetune.training_status`.
- [ ] Manual smoke: `can_finetune` + a tiny `build_dataset` on a fixture (no real train). Commit.

---

### Task 5: Frontend — wavesurfer region editor

**Files:** Add `static/vendor/wavesurfer.min.js` (+ regions), Create `static/voice_editor.js`

- [ ] Vendor wavesurfer.js + regions plugin locally (download the minified files into `static/vendor/`).
- [ ] `voice_editor.js`: given an audio URL, render the waveform; add/drag/delete **multiple regions**; list them with start–end + duration + a play-region button; expose `getRegions() -> [{start,end}]`.
- [ ] Manual: load a sample wav, create 2 regions, confirm `getRegions()` returns them. Commit.

---

### Task 6: Frontend — voice step flow + GPU branch + blocking train screen

**Files:** Modify `static/wizard.js` (Step 2 Voice, ~209; validation `case 2`, ~365)

- [ ] On entering Step 2: `GET /api/voice/can_finetune`. If `!ok` → show the existing edge/zero-shot controls + a note ("fine-tune needs a GPU — using a quick voice"); skip the rest.
- [ ] If `ok` (default): search box → `POST /api/voice/search` → results; "add" a video → `download_full_for_edit` → open `voice_editor` modal; persist each video's regions; show a tray (videos + region counts + total seconds, warn < ~60s).
- [ ] "Build & Train" → `build_dataset` then `train`; switch to a **blocking training screen**: banner "Training a faithful voice — ~1–2 hr, keep this open", progress bar polling `train_status` every ~10s; block Finish until `done`. On `error`, show it + offer "use quick voice instead" (zero-shot fallback).
- [ ] Manual (GPU box): full flow. Commit.

---

### Task 7: Build flow guard + end-to-end

**Files:** Modify `character_creator/character_builder.py`

- [ ] Ensure `build_character` does NOT re-run `prepare_voice_artifacts` (overwriting the trained voice) when the fine-tune path already wired the trained model. Gate on the voice block already having `finetuned_model`.
- [ ] Full manual run on the GPU box (search → multi-region edit → train w/ progress → character on trained voice) AND a no-GPU run (clean zero-shot fallback). Audio verification per `.claude/rules/testing.md`.
- [ ] Final review + `superpowers:finishing-a-development-branch`.

---

## Self-Review

- **Spec coverage:** search/multi-select (T4/T6), multi-region editor (T5), dataset-from-regions (T2), blocking train + progress (T3/T6), no-GPU fallback (T1/T6), trained-voice wiring (T3/T7). Covered.
- **Placeholders:** none — code shown for the testable core; frontend tasks are inherently manual but have concrete steps + endpoints.
- **Type consistency:** `can_finetune()->{ok,...}`, `parse_training_status()->{stage,epoch,total,pct,done}`, `build_dataset_from_picks()->int`, region shape `{start,end}` consistent across tasks.
