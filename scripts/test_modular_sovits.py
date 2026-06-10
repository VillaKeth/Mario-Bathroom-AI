"""Prove GPT-SoVITS is modular: load the v2 BASE weights + an arbitrary reference
clip (no Mario fine-tune) and synthesize a line. This is the zero-shot path used
for every non-Mario character.
"""
import json
import os
import shutil
import subprocess
import sys
import threading
import time

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = os.path.join(BASE, "gpt_sovits_env", "Scripts", "python.exe")
SERVER = os.path.join(BASE, "server", "gpt_sovits_server.py")
BASE_DIR = os.path.join(BASE, "gpt_sovits_repo", "GPT_SoVITS", "pretrained_models", "gsv-v2final-pretrained")

env = os.environ.copy()
env["PYTHONUNBUFFERED"] = "1"
env["SOVITS_GPT_PATH"] = os.path.join(BASE_DIR, "s1bert25hz-5kh-longer-epoch=12-step=369668.ckpt")
env["SOVITS_SOVITS_PATH"] = os.path.join(BASE_DIR, "s2G2333k.pth")
env["SOVITS_REF_AUDIO"] = os.path.join(BASE, "mario_models_new", "GPT_SoVITS_Mario", "mario_ref.wav")
env["SOVITS_PROMPT_TEXT"] = "It's a me Mario"
env["SOVITS_PROMPT_LANG"] = "en"
env["SOVITS_CHARACTER"] = "testchar"  # NON-mario => Mario name fixes must NOT fire

print("[test] launching subprocess with v2 BASE models...", flush=True)
p = subprocess.Popen([PY, SERVER], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                     stderr=subprocess.PIPE, cwd=BASE, text=True, bufsize=1, env=env)

# Drain stderr in a thread so the pipe never fills and deadlocks the subprocess.
def _drain():
    try:
        for line in p.stderr:
            if "[sovits]" in line:
                print("[stderr] " + line.strip()[:160], flush=True)
    except Exception:
        pass
threading.Thread(target=_drain, daemon=True).start()

ready = False
deadline = time.time() + 180
while time.time() < deadline:
    line = p.stdout.readline()
    if not line:
        break
    line = line.strip()
    if not line:
        continue
    try:
        msg = json.loads(line)
    except json.JSONDecodeError:
        continue
    if msg.get("status") == "ready":
        ready = True
        break
    print(f"[test] {msg.get('status')}: {msg.get('msg','')}", flush=True)

if not ready:
    print("[test] FAILED: server never became ready", flush=True)
    err = p.stderr.read()[-2000:] if p.stderr else ""
    print("[test] stderr tail:\n" + err, flush=True)
    p.kill()
    sys.exit(1)

print("[test] ready. sending synthesis request...", flush=True)
p.stdin.write(json.dumps({"text": "Hello there, welcome to the party! This voice is fully modular."}) + "\n")
p.stdin.flush()

import concurrent.futures
with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
    try:
        line = pool.submit(lambda: p.stdout.readline()).result(timeout=120)
    except concurrent.futures.TimeoutError:
        print("[test] FAILED: synthesis timed out after 120s", flush=True)
        p.kill()
        sys.exit(1)
resp = json.loads(line.strip())
print("[test] response:", resp, flush=True)
if resp.get("status") == "ok":
    dst = os.path.join(BASE, "model_comparison", "modular_sovits_base_test.wav")
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy(resp["audio_path"], dst)
    print(f"[test] SUCCESS -> {dst} ({resp['duration']}s audio in {resp['elapsed']}s)", flush=True)
else:
    print("[test] SYNTH FAILED:", resp.get("error"), flush=True)

try:
    p.stdin.write(json.dumps({"command": "quit"}) + "\n"); p.stdin.flush()
except Exception:
    pass
p.kill()
