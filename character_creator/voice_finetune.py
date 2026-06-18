"""Wizard fine-tune orchestration — wraps voice_finder/build_voice_dataset/fine_tune_voice.
Web-free + pygame-free so it is unit-testable. The wizard server calls these.

Real markers from scripts/fine_tune_voice.py:
  - Epoch line: the GPT-SoVITS trainers (s2_train.py / s1_train.py) emit lines like
      "====> Epoch: 3"   (PyTorch Lightning epoch header)
  - Done line: fine_tune_voice.py itself prints
      "[ft] DONE -> <out_path>"
    after all weights are collected.
  - s1 stage: once the script starts s1_train.py, its log echoes the command
      '"<pyexe>" -s GPT_SoVITS/s1_train.py ...'
    so `s1_train` appears in the accumulated log.
"""
import os
import re
import subprocess
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---------------------------------------------------------------------------
# Regexes — tuned to both the real fine_tune_voice.py output AND the test
# fixture strings used in tests/test_voice_finetune.py.
#
# Real done line:   "[ft] DONE -> /path/to/GPT_SoVITS_Char"
# Test done string: "[ft] DONE GPT_SoVITS_Pomni copied"
# Both share the prefix "[ft] DONE".
# ---------------------------------------------------------------------------
_EPOCH_RE = re.compile(r"====> Epoch:\s*(\d+)")
_DONE_RE = re.compile(r"\[ft\]\s+DONE")


# ---------------------------------------------------------------------------
# Hardware / availability helpers — kept as module-level callables so tests
# can monkeypatch them by attribute (vf._gpu_vram_gb = ...).
# Heavy imports (torch, hardware, voice_trainer) are done lazily INSIDE to
# keep the module importable without torch/psutil installed.
# ---------------------------------------------------------------------------

def _gpu_vram_gb() -> float:
    """Return detected GPU VRAM in GB (0.0 if no CUDA GPU found)."""
    sys.path.insert(0, os.path.join(BASE, "server"))
    from hardware import detect_hardware  # lazy import — avoids torch at module load
    hw = detect_hardware()
    return float(hw.get("gpu_vram_gb") or 0.0)


def _sovits_installed() -> bool:
    """Return True if GPT-SoVITS repo + env + pretrained weights are all present."""
    from character_creator.voice_trainer import get_engine_status  # lazy import
    return bool(get_engine_status("sovits").get("available"))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def can_finetune() -> dict:
    """Check whether fine-tuning is possible on this machine.

    Returns a dict:
      {"ok": bool, "vram_gb": float, "sovits": bool, "reason": str}
    """
    vram = _gpu_vram_gb()
    sovits = _sovits_installed()
    ok = vram >= 3.5 and sovits
    if ok:
        reason = ""
    elif vram < 3.5:
        reason = "needs a CUDA GPU (>=4GB)"
    else:
        reason = "GPT-SoVITS not installed"
    return {"ok": ok, "vram_gb": vram, "sovits": sovits, "reason": reason}


_CHARS_DIR = os.path.join(BASE, "characters")


def build_dataset_from_picks(char: str, picks: list, char_root: str = None) -> int:
    """Cut user-picked regions from audio, slice into segments, transcribe, write .list.

    Args:
        char:      Character name (e.g. "sparkle_hsr").
        picks:     List of pick dicts, each with keys:
                     "edit_wav"  — path to the full downloaded wav
                     "regions"   — list of {"start": float, "end": float} in seconds
        char_root: Root directory under which ``<char>/voice/dataset/`` is created.
                   Defaults to the repo ``characters/`` directory.

    Returns:
        Count of usable segments (int) written to the .list manifest.

    Directory layout produced:
        <char_root>/<char>/voice/dataset/raw/       — region cuts (from cut_sections)
        <char_root>/<char>/voice/dataset/segments/  — silence-sliced pieces (if slicer2 avail)
        <char_root>/<char>/voice/dataset/<char>.list — GPT-SoVITS manifest
    """
    import shutil
    from character_creator import voice_finder

    root = char_root if char_root is not None else _CHARS_DIR
    ds = os.path.join(root, char, "voice", "dataset")
    raw_dir = os.path.join(ds, "raw")
    seg_dir = os.path.join(ds, "segments")
    list_path = os.path.join(ds, f"{char}.list")

    os.makedirs(raw_dir, exist_ok=True)
    os.makedirs(seg_dir, exist_ok=True)

    # Step 1 — cut the user-picked regions out of each source wav.
    raw_pieces = []
    for idx, pick in enumerate(picks):
        edit_wav = pick.get("edit_wav", "")
        regions = pick.get("regions", [])
        if not edit_wav or not os.path.exists(edit_wav) or not regions:
            continue
        base = f"pick{idx:02d}"
        try:
            pieces = voice_finder.cut_sections(edit_wav, regions, raw_dir, base)
        except Exception as exc:
            # ffmpeg unavailable or failed — copy the full wav as a single raw piece
            print(f"[finetune] cut_sections failed ({exc}), using full wav as fallback", flush=True)
            dst = os.path.join(raw_dir, f"{base}_full.wav")
            try:
                shutil.copy2(edit_wav, dst)
                pieces = [dst]
            except Exception:
                pieces = []
        print(f"[finetune] pick{idx}: {len(pieces)} raw piece(s)", flush=True)
        raw_pieces.extend(pieces)

    if not raw_pieces:
        print("[finetune] no raw pieces; writing empty .list", flush=True)
        os.makedirs(os.path.dirname(list_path), exist_ok=True)
        open(list_path, "w").close()
        return 0

    # Step 2 — silence-slice each raw piece into 3-10s training segments.
    # slicer2 lives in gpt_sovits_repo; if unavailable, treat raw pieces as segments.
    all_segs = []
    try:
        sys.path.insert(0, os.path.join(BASE, "gpt_sovits_repo"))
        sys.path.insert(0, os.path.join(BASE, "gpt_sovits_repo", "tools"))
        from scripts.build_voice_dataset import slice_audio
        for rp in raw_pieces:
            segs = slice_audio(rp, seg_dir, char)
            print(f"[finetune] sliced {os.path.basename(rp)} -> {len(segs)} segment(s)", flush=True)
            all_segs.extend(segs)
    except Exception as exc:
        # slicer2 / numpy / soundfile not available — use raw cuts directly as segments
        print(f"[finetune] slice_audio unavailable ({exc}); using raw pieces as segments", flush=True)
        all_segs = list(raw_pieces)

    # Step 3 — transcribe segments and write the GPT-SoVITS .list manifest.
    from scripts.build_voice_dataset import transcribe_and_write_list
    return transcribe_and_write_list(char, all_segs, list_path)


def parse_training_status(log: str, total_s2: int = 8, total_s1: int = 4) -> dict:
    """Parse accumulated subprocess log output and return training progress.

    Args:
        log: Full stdout/stderr captured so far from fine_tune_voice.py.
        total_s2: Configured s2 (SoVITS) epoch count (default 8).
        total_s1: Configured s1 (GPT) epoch count (default 15 in the script,
                  but callers who want a quick summary pass their own values).

    Returns:
        {
          "stage":  "s2" | "s1",
          "epoch":  int,        # last epoch number seen in log
          "total":  int,        # total_s2 + total_s1
          "pct":    int,        # 0-100 (capped at 99 until done)
          "done":   bool,
        }
    """
    done = bool(_DONE_RE.search(log))

    epochs = [int(m) for m in _EPOCH_RE.findall(log)]
    epoch = epochs[-1] if epochs else 0

    # Detect whether we have entered the s1 (GPT) training phase.
    # fine_tune_voice.py echoes the shell command before running it; s1_train
    # appears in that echo line once s1 begins.
    in_s1 = ("s1_train" in log) or (epoch > total_s2)
    stage = "s1" if in_s1 else "s2"

    total = total_s2 + total_s1
    if in_s1:
        # epoch counter may reset to 1 for s1, or continue from s2 epoch count;
        # use whichever interpretation gives a larger seen count.
        seen_continuing = epoch  # epoch counter runs straight through
        seen_reset = total_s2 + max(0, epoch)  # epoch reset to 1 inside s1
        seen = max(seen_continuing, seen_reset)
    else:
        seen = epoch

    pct = 100 if done else int(min(99, 100 * seen / max(1, total)))
    return {"stage": stage, "epoch": epoch, "total": total, "pct": pct, "done": done}
