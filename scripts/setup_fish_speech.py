"""One-time Fish Speech setup (online). After this, cloning runs offline.

Creates fish_speech_env, installs fish-speech from the official repo, and
downloads the model checkpoint. voice_trainer.detect_available_engines() flips
Fish Speech to 'ready' automatically once fish_speech_env/ and fish_speech_ckpts/
both exist.

Run: venv/Scripts/python.exe scripts/setup_fish_speech.py
"""
import os
import subprocess
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV = os.path.join(BASE, "fish_speech_env")
REPO = os.path.join(BASE, "fish_speech_repo")
CKPT = os.path.join(BASE, "fish_speech_ckpts")
ENV_PY = os.path.join(ENV, "Scripts", "python.exe")

# Pinned to Fish Speech v1.5.1 + its non-gated fish-speech-1.5 checkpoint (firefly
# decoder). No HF token or license click required.
FISH_TAG = "v1.5.1"
HF_REPO = "fishaudio/fish-speech-1.5"


def run(cmd, **kw):
    print(f"\n$ {' '.join(cmd)}", flush=True)
    r = subprocess.run(cmd, cwd=BASE, **kw)
    if r.returncode != 0:
        print(f"[setup] command failed (exit {r.returncode})", flush=True)
    return r.returncode


def main():
    # 1) venv
    if not os.path.exists(ENV_PY):
        print("[setup] creating fish_speech_env ...", flush=True)
        run([sys.executable, "-m", "venv", ENV])
    else:
        print("[setup] fish_speech_env exists", flush=True)

    # 2) clone repo + pin to the v1.5.1 tag (matches the non-gated checkpoint)
    if not os.path.isdir(os.path.join(REPO, ".git")):
        print("[setup] cloning fish-speech repo ...", flush=True)
        run(["git", "clone", "https://github.com/fishaudio/fish-speech.git", REPO])
    else:
        print("[setup] fish_speech_repo exists", flush=True)
    run(["git", "-C", REPO, "fetch", "--tags"])
    run(["git", "-C", REPO, "checkout", FISH_TAG])

    # 3) install torch (match cu126) + the package
    run([ENV_PY, "-m", "pip", "install", "--upgrade", "pip"])
    run([ENV_PY, "-m", "pip", "install", "torch", "torchaudio",
         "--index-url", "https://download.pytorch.org/whl/cu126"])
    run([ENV_PY, "-m", "pip", "install", "huggingface_hub", "soundfile"])
    if os.path.isdir(REPO):
        run([ENV_PY, "-m", "pip", "install", "-e", REPO])

    # 3b) Pin a CUDA torch that's compatible with fish-speech v1.5.1. Its deps pull
    # in CPU torch, and the LATEST torchaudio dropped list_audio_backends() which
    # v1.5.1 calls — torch 2.6.0 (same as gpt_sovits_env) is the known-good build.
    run([ENV_PY, "-m", "pip", "install", "--force-reinstall", "torch==2.6.0", "torchaudio==2.6.0",
         "--index-url", "https://download.pytorch.org/whl/cu126"])

    # 4) download checkpoint (non-gated, no token needed)
    os.makedirs(CKPT, exist_ok=True)
    print(f"[setup] downloading {HF_REPO} checkpoint ...", flush=True)
    run([ENV_PY, "-c",
         f"from huggingface_hub import snapshot_download;"
         f"snapshot_download('{HF_REPO}', local_dir=r'{CKPT}')"])

    ok = os.path.exists(ENV_PY) and os.path.isdir(CKPT) and os.listdir(CKPT)
    print(f"\n[setup] {'SUCCESS' if ok else 'INCOMPLETE'} — env={os.path.exists(ENV_PY)} "
          f"ckpt_files={len(os.listdir(CKPT)) if os.path.isdir(CKPT) else 0}", flush=True)


if __name__ == "__main__":
    main()
