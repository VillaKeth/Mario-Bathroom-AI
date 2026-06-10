"""Download GPT-SoVITS v2 base pretrained models for modular zero-shot cloning.

One-time online setup. Once present, per-character voice cloning runs fully offline.
Pulls the two v2 base weights into gpt_sovits_repo/GPT_SoVITS/pretrained_models/.
"""
import os
from huggingface_hub import hf_hub_download

REPO = "lj1995/GPT-SoVITS"
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEST = os.path.join(BASE_DIR, "gpt_sovits_repo", "GPT_SoVITS", "pretrained_models")

FILES = [
    "gsv-v2final-pretrained/s2G2333k.pth",
    "gsv-v2final-pretrained/s2D2333k.pth",
    "gsv-v2final-pretrained/s1bert25hz-5kh-longer-epoch=12-step=369668.ckpt",
]

os.makedirs(DEST, exist_ok=True)
for f in FILES:
    print(f"[download] {f} ...", flush=True)
    try:
        p = hf_hub_download(repo_id=REPO, filename=f, local_dir=DEST)
        print(f"[download] OK -> {p}", flush=True)
    except Exception as e:
        print(f"[download] FAILED {f}: {e}", flush=True)
print("[download] done", flush=True)
