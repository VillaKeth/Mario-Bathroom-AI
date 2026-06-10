"""A/B voice comparison for a character.

Renders the SAME line through every available engine (GPT-SoVITS zero-shot,
Fish Speech zero-shot, Edge TTS fallback) using the character's modular voice
config, so you can listen and pick the best. Fully offline except Edge.

Usage:
    venv/Scripts/python.exe scripts/voice_compare.py --character power \
        --text "Hey, welcome to the party!"

Outputs WAVs to model_comparison/<character>_<engine>.wav and prints a summary.
"""
import argparse
import asyncio
import concurrent.futures
import json
import os
import shutil
import subprocess
import sys
import threading
import time

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(BASE, "model_comparison")
SOVITS_V2_BASE = os.path.join(BASE, "gpt_sovits_repo", "GPT_SoVITS", "pretrained_models",
                              "gsv-v2final-pretrained")


def load_voice_config(character: str) -> dict:
    import yaml
    yaml_path = os.path.join(BASE, "characters", character, "character.yaml")
    if not os.path.exists(yaml_path):
        sys.exit(f"character.yaml not found for '{character}' at {yaml_path}")
    with open(yaml_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    voice = cfg.get("voice", {})
    char_dir = os.path.join(BASE, "characters", character)
    ref = voice.get("reference_audio")
    if ref and not os.path.isabs(ref):
        ref = os.path.join(char_dir, ref)
    return {
        "reference_audio": ref,
        "prompt_text": voice.get("prompt_text", ""),
        "prompt_lang": voice.get("prompt_lang", "en"),
        "edge_voice": voice.get("edge_voice", "en-US-GuyNeural"),
        "rate": voice.get("rate", "+0%"),
        "pitch": voice.get("pitch", "+0Hz"),
        "engines": voice.get("engines", []),
    }


def _resolve_sovits_models(character: str):
    """Fine-tune dir for the character wins; else v2 base weights (zero-shot)."""
    ft = os.path.join(BASE, "mario_models_new", f"GPT_SoVITS_{character.capitalize()}")
    if os.path.isdir(ft):
        ck = [f for f in os.listdir(ft) if f.endswith(".ckpt")]
        pt = [f for f in os.listdir(ft) if f.endswith(".pth")]
        if ck and pt:
            return os.path.join(ft, ck[0]), os.path.join(ft, pt[0]), True
    return (os.path.join(SOVITS_V2_BASE, "s1bert25hz-5kh-longer-epoch=12-step=369668.ckpt"),
            os.path.join(SOVITS_V2_BASE, "s2G2333k.pth"), False)


def render_sovits(character: str, vc: dict, text: str) -> dict:
    py = os.path.join(BASE, "gpt_sovits_env", "Scripts", "python.exe")
    server = os.path.join(BASE, "server", "gpt_sovits_server.py")
    if not os.path.exists(py):
        return {"engine": "sovits", "ok": False, "error": "gpt_sovits_env missing"}
    gpt_path, sovits_path, is_ft = _resolve_sovits_models(character)
    if not os.path.exists(sovits_path):
        return {"engine": "sovits", "ok": False, "error": "v2 base weights missing"}

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["SOVITS_GPT_PATH"] = gpt_path
    env["SOVITS_SOVITS_PATH"] = sovits_path
    env["SOVITS_CHARACTER"] = character
    if vc.get("reference_audio") and os.path.exists(vc["reference_audio"]):
        env["SOVITS_REF_AUDIO"] = vc["reference_audio"]
    if vc.get("prompt_text"):
        env["SOVITS_PROMPT_TEXT"] = vc["prompt_text"]
    if vc.get("prompt_lang"):
        env["SOVITS_PROMPT_LANG"] = vc["prompt_lang"]

    p = subprocess.Popen([py, server], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, cwd=BASE, text=True, bufsize=1, env=env,
                         encoding="utf-8", errors="ignore")

    def _drain():
        try:
            for _ in p.stderr:
                pass
        except Exception:
            pass
    threading.Thread(target=_drain, daemon=True).start()

    t0 = time.time()
    ready = False
    deadline = time.time() + 180
    while time.time() < deadline:
        line = p.stdout.readline()
        if not line:
            break
        try:
            msg = json.loads(line.strip())
        except json.JSONDecodeError:
            continue
        if msg.get("status") == "ready":
            ready = True
            break
    if not ready:
        p.kill()
        return {"engine": "sovits", "ok": False, "error": "subprocess never ready"}

    try:
        p.stdin.write(json.dumps({"text": text}) + "\n")
        p.stdin.flush()
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            line = pool.submit(lambda: p.stdout.readline()).result(timeout=120)
        resp = json.loads(line.strip())
    except Exception as e:
        p.kill()
        return {"engine": "sovits", "ok": False, "error": str(e)}

    if resp.get("status") != "ok":
        p.kill()
        return {"engine": "sovits", "ok": False, "error": resp.get("error")}
    dst = os.path.join(OUT_DIR, f"{character}_sovits.wav")
    shutil.copy(resp["audio_path"], dst)
    p.kill()
    return {"engine": "sovits", "ok": True, "path": dst,
            "model": "fine-tune" if is_ft else "v2-base-zeroshot",
            "elapsed": round(time.time() - t0, 1)}


def render_edge(character: str, vc: dict, text: str) -> dict:
    import edge_tts
    dst = os.path.join(OUT_DIR, f"{character}_edge.mp3")

    async def _run():
        comm = edge_tts.Communicate(text, vc["edge_voice"], rate=vc["rate"], pitch=vc["pitch"])
        with open(dst, "wb") as f:
            async for chunk in comm.stream():
                if chunk["type"] == "audio":
                    f.write(chunk["data"])
    t0 = time.time()
    try:
        asyncio.run(_run())
    except Exception as e:
        return {"engine": "edge", "ok": False, "error": str(e)}
    return {"engine": "edge", "ok": True, "path": dst, "voice": vc["edge_voice"],
            "elapsed": round(time.time() - t0, 1)}


def render_fish(character: str, vc: dict, text: str) -> dict:
    fish_env = os.path.join(BASE, "fish_speech_env")
    fish_script = os.path.join(BASE, "scripts", "fish_synth.py")
    if not os.path.isdir(fish_env) or not os.path.exists(fish_script):
        return {"engine": "fish_speech", "ok": False, "error": "Fish Speech not installed"}
    if not (vc.get("reference_audio") and os.path.exists(vc["reference_audio"])):
        return {"engine": "fish_speech", "ok": False, "error": "no reference audio"}
    py = os.path.join(fish_env, "Scripts", "python.exe")
    dst = os.path.join(OUT_DIR, f"{character}_fish.wav")
    t0 = time.time()
    try:
        r = subprocess.run(
            [py, fish_script, "--ref", vc["reference_audio"], "--ref-text", vc.get("prompt_text", ""),
             "--text", text, "--out", dst],
            cwd=BASE, capture_output=True, text=True, timeout=300)
        if r.returncode != 0 or not os.path.exists(dst):
            return {"engine": "fish_speech", "ok": False, "error": (r.stderr or "")[-300:]}
    except Exception as e:
        return {"engine": "fish_speech", "ok": False, "error": str(e)}
    return {"engine": "fish_speech", "ok": True, "path": dst, "elapsed": round(time.time() - t0, 1)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--character", required=True)
    ap.add_argument("--text", default="Hey there, welcome to the party! So great to see you.")
    ap.add_argument("--engines", default="sovits,fish_speech,edge",
                    help="comma list of engines to compare")
    args = ap.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    vc = load_voice_config(args.character)
    print(f"=== Voice compare: {args.character} ===")
    print(f"text: {args.text}")
    print(f"ref:  {vc['reference_audio']} (exists={bool(vc['reference_audio']) and os.path.exists(vc['reference_audio'] or '')})")
    print(f"prompt_text: {vc['prompt_text'][:80]!r}")
    print("-" * 60)

    runners = {"sovits": render_sovits, "fish_speech": render_fish, "edge": render_edge}
    results = []
    for eng in [e.strip() for e in args.engines.split(",") if e.strip()]:
        fn = runners.get(eng)
        if not fn:
            continue
        print(f"[{eng}] rendering...", flush=True)
        res = fn(args.character, vc, args.text)
        results.append(res)
        if res["ok"]:
            print(f"[{eng}] OK -> {res['path']}  ({res.get('elapsed','?')}s, {res.get('model', res.get('voice',''))})")
        else:
            print(f"[{eng}] skipped/failed: {res['error']}")

    print("-" * 60)
    ok = [r for r in results if r["ok"]]
    print(f"{len(ok)}/{len(results)} engines rendered. Listen and compare:")
    for r in ok:
        print(f"  {r['engine']:12s} {r['path']}")


if __name__ == "__main__":
    main()
