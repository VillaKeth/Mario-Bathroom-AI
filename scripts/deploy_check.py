#!/usr/bin/env python3
"""
Pre-deployment validation script for Mario AI v2.0.
Run this before the party to verify everything is ready.

Usage:
    python scripts/deploy_check.py [--server URL]
"""

import argparse
import json
import subprocess
import shutil
import sys
import os
import importlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

PASS = "✅"
FAIL = "❌"
WARN = "⚠️"

results = []

def check(name, passed, detail="", warn=False):
    status = PASS if passed else (WARN if warn else FAIL)
    results.append((status, name, detail))
    print(f"  {status} {name}" + (f" — {detail}" if detail else ""))
    return passed


def check_system():
    print("\n🖥️  SYSTEM CHECKS")
    print("=" * 50)

    check("Python 3.10+", sys.version_info >= (3, 10),
          f"Found {sys.version_info.major}.{sys.version_info.minor}")

    check("Ollama installed", shutil.which("ollama") is not None,
          "Required for LLM")

    try:
        result = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=10)
        models = result.stdout.lower()
        check("70B quality model", "70b" in models or "llama3.1" in models,
              "llama3.1:70b-instruct-q4_K_M", warn=True)
        check("Fast model (Mixtral)", "mixtral" in models or "llama3" in models,
              "mixtral:8x7b or llama3", warn=True)
    except Exception as e:
        check("Ollama models", False, str(e))

    try:
        import torch
        has_cuda = torch.cuda.is_available()
        if has_cuda:
            gpu_name = torch.cuda.get_device_name(0)
            props = torch.cuda.get_device_properties(0)
            vram_gb = getattr(props, 'total_memory', getattr(props, 'total_mem', 0)) / (1024**3)
            check("CUDA GPU", True, f"{gpu_name} ({vram_gb:.1f} GB)")
            check("VRAM >= 12GB", vram_gb >= 12,
                  f"{vram_gb:.1f} GB" + (" (24GB recommended)" if vram_gb < 24 else ""))
        else:
            check("CUDA GPU", False, "No CUDA GPU found — will be very slow")
    except ImportError:
        check("PyTorch", False, "pip install torch", warn=True)


def check_dependencies():
    print("\n📦 DEPENDENCY CHECKS")
    print("=" * 50)

    required = [
        ("fastapi", "FastAPI server"),
        ("uvicorn", "ASGI server"),
        ("websockets", "WebSocket support"),
        ("edge_tts", "Edge TTS fallback"),
        ("numpy", "Audio processing"),
    ]

    optional = [
        ("fish_speech", "Fish Speech TTS (primary)"),
        ("resemblyzer", "Speaker identification"),
        ("faster_whisper", "Speech-to-text"),
    ]

    for mod, desc in required:
        try:
            importlib.import_module(mod)
            check(desc, True, mod)
        except ImportError:
            check(desc, False, f"pip install {mod}")

    for mod, desc in optional:
        try:
            importlib.import_module(mod)
            check(desc, True, mod)
        except ImportError:
            check(desc, False, f"pip install {mod}", warn=True)


def check_config():
    print("\n⚙️  CONFIG CHECKS")
    print("=" * 50)

    config_path = os.path.join(os.path.dirname(__file__), '..', 'config.json')
    if not os.path.exists(config_path):
        check("config.json exists", False, "Missing config file!")
        return

    with open(config_path) as f:
        config = json.load(f)

    server = config.get("server", {})

    check("config.json exists", True)
    check("Host is 0.0.0.0", server.get("host") == "0.0.0.0",
          f"Currently: {server.get('host')}")
    check("Port configured", server.get("port", 8765) == 8765,
          f"Port: {server.get('port', 8765)}")

    bday = server.get("birthday_person_name", "")
    check("Birthday person set", bool(bday),
          f"Name: {bday}" if bday else "Set in config.json → server.birthday_person_name",
          warn=True)

    webhook = config.get("alert_webhook_url", "")
    check("Alert webhook set", bool(webhook),
          "Discord/Slack alerts enabled" if webhook else "No alerts configured",
          warn=True)


def check_modules():
    print("\n🧩 MODULE CHECKS")
    print("=" * 50)

    modules = [
        ("server.llm_router", "LLM Router (dual model)"),
        ("server.tts_router", "TTS Router (5-level fallback)"),
        ("server.night_progression", "Night Progression (4 phases)"),
        ("server.watchdog", "Watchdog (auto-restart)"),
        ("server.canary", "Canary (pre-party self-test)"),
        ("server.hot_reload", "Hot Reload (live config)"),
        ("server.birthday_vip", "Birthday VIP"),
        ("server.sound_events", "Sound Effects"),
        ("server.catchphrase_mirror", "Catchphrase Mirror"),
        ("server.audio_distress", "Vomit Detection"),
        ("server.party_report", "Party Report Card"),
        ("server.dashboard", "Health Dashboard"),
    ]

    for mod, desc in modules:
        try:
            importlib.import_module(mod)
            check(desc, True)
        except Exception as e:
            check(desc, False, str(e)[:60])


def check_assets():
    print("\n🎨 ASSET CHECKS")
    print("=" * 50)

    base = os.path.join(os.path.dirname(__file__), '..')

    sprite_dirs = ["assets", "mario_assets", "assets_boutique"]
    found_sprites = False
    for d in sprite_dirs:
        path = os.path.join(base, d)
        if os.path.isdir(path) and os.listdir(path):
            found_sprites = True
            break
    check("Mario sprites", found_sprites,
          "Found in assets directory" if found_sprites else "No sprite assets found")

    ref_audio = os.path.join(base, "mario_ref_audio")
    has_ref = os.path.isdir(ref_audio) and any(
        f.endswith(('.wav', '.mp3')) for f in os.listdir(ref_audio)
    ) if os.path.isdir(ref_audio) else False
    check("Voice reference audio", has_ref,
          "mario_ref_audio/ has audio files" if has_ref else "No reference audio",
          warn=True)

    sfx_dir = os.path.join(base, "assets", "sfx")
    has_sfx = os.path.isdir(sfx_dir) and bool(os.listdir(sfx_dir))
    check("Sound effects", has_sfx,
          "assets/sfx/ has files" if has_sfx else "No SFX files (optional)",
          warn=True)


def check_server_health(server_url):
    print("\n🏥 SERVER HEALTH CHECK")
    print("=" * 50)

    import urllib.request
    import urllib.error

    health_url = server_url.replace("ws://", "http://").replace("/ws", "") + "/health"
    try:
        req = urllib.request.Request(health_url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            check("Server responding", True, health_url)
            check("Server healthy", data.get("status") == "healthy",
                  f"Status: {data.get('status')}")
            check("LLM available", data.get("llm_status") != "error",
                  f"LLM: {data.get('llm_status', 'unknown')}")
            check("TTS available", data.get("tts_status") != "error",
                  f"TTS: {data.get('tts_status', 'unknown')}")
            if "gpu_vram_used_pct" in data:
                vram_pct = data["gpu_vram_used_pct"]
                check("GPU VRAM OK", vram_pct < 95,
                      f"VRAM: {vram_pct}% used")
    except urllib.error.URLError:
        check("Server responding", False,
              f"Cannot reach {health_url} — is the server running?", warn=True)
    except Exception as e:
        check("Server responding", False, str(e)[:60], warn=True)


def print_summary():
    print("\n" + "=" * 50)
    print("📊 DEPLOYMENT READINESS SUMMARY")
    print("=" * 50)

    passes = sum(1 for s, _, _ in results if s == PASS)
    warns = sum(1 for s, _, _ in results if s == WARN)
    fails = sum(1 for s, _, _ in results if s == FAIL)
    total = len(results)

    print(f"\n  {PASS} Passed: {passes}/{total}")
    if warns:
        print(f"  {WARN} Warnings: {warns}")
    if fails:
        print(f"  {FAIL} Failed: {fails}")

    if fails == 0:
        print(f"\n  🎉 READY FOR THE PARTY! Let's-a go!")
    elif fails <= 2:
        print(f"\n  ⚠️  Almost ready — fix {fails} issue(s) above.")
    else:
        print(f"\n  🚨 NOT READY — fix {fails} critical issues above.")

    return fails


def main():
    parser = argparse.ArgumentParser(description="Mario AI v2.0 Deployment Checker")
    parser.add_argument("--server", default="ws://localhost:8765/ws",
                        help="Server WebSocket URL (default: ws://localhost:8765/ws)")
    parser.add_argument("--skip-server", action="store_true",
                        help="Skip live server health check")
    args = parser.parse_args()

    print("🍄 Mario AI v2.0 — Pre-Deployment Check")
    print("=" * 50)

    check_system()
    check_dependencies()
    check_config()
    check_modules()
    check_assets()

    if not args.skip_server:
        check_server_health(args.server)

    fails = print_summary()
    sys.exit(1 if fails > 0 else 0)


if __name__ == "__main__":
    main()
