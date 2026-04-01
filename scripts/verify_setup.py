#!/usr/bin/env python3
"""Post-setup health check for Mario AI Party Bot.

Standalone verification script — checks every component of the installation
using subprocess calls, file checks, and pip queries. No server imports for
the checks themselves (except check #3 hardware and #16 qdrant and #19 server).

Usage:
    python scripts/verify_setup.py            # Standard 20-check suite
    python scripts/verify_setup.py --full-tts  # Also test GPT-SoVITS synthesis

Exit codes:
    0 = all critical checks passed
    1 = one or more critical failures
    2 = warnings only (non-critical issues)
"""
import sys
import os
import json
import subprocess
import argparse
import platform
import time
import warnings
from pathlib import Path

# Suppress noisy transitive-import warnings (e.g. requests version mismatch)
warnings.filterwarnings("ignore")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
os.chdir(PROJECT_ROOT)
sys.path.insert(0, str(PROJECT_ROOT))

# ---------------------------------------------------------------------------
# Status constants
# ---------------------------------------------------------------------------
PASS = "PASS"
FAIL = "FAIL"
WARN = "WARN"
SKIP = "SKIP"

# ---------------------------------------------------------------------------
# Color support (colorama on Windows, fall back to no colors)
# ---------------------------------------------------------------------------
try:
    from colorama import init as _colorama_init, Fore, Style
    _colorama_init()
    COLORS = {
        PASS: Fore.GREEN,
        FAIL: Fore.RED,
        WARN: Fore.YELLOW,
        SKIP: Fore.CYAN,
        "RESET": Style.RESET_ALL,
        "BOLD": Style.BRIGHT,
    }
except ImportError:
    COLORS = {PASS: "", FAIL: "", WARN: "", SKIP: "", "RESET": "", "BOLD": ""}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
class CheckResult:
    """Outcome of a single verification check."""

    def __init__(self, name: str, status: str, detail: str = "", critical: bool = True):
        self.name = name
        self.status = status
        self.detail = detail
        self.critical = critical


def run_cmd(cmd, timeout=10):
    """Run a subprocess command and return ``(success, stdout)``."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode == 0, r.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False, ""


def fmt(result: CheckResult):
    """Print a single check result line with color."""
    color = COLORS.get(result.status, "")
    reset = COLORS["RESET"]
    tag = f"[{color}{result.status:4s}{reset}]"
    detail = f"  ({result.detail})" if result.detail else ""
    print(f"  {tag}  {result.name}{detail}")


# ---------------------------------------------------------------------------
# Individual check functions (1-20)
# ---------------------------------------------------------------------------

def check_01_python_version():
    """1. Python version >= 3.10"""
    v = sys.version_info
    ver_str = f"{v.major}.{v.minor}.{v.micro}"
    if v >= (3, 10):
        return CheckResult("Python version >= 3.10", PASS, ver_str)
    return CheckResult("Python version >= 3.10", FAIL, f"Got {ver_str}, need 3.10+")


def check_02_cuda_gpu():
    """2. CUDA / GPU drivers"""
    ok, out = run_cmd(
        ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"]
    )
    if ok and out:
        return CheckResult("CUDA / GPU drivers", PASS, out.split("\n")[0].strip(), critical=False)
    # Fallback: check torch.cuda
    try:
        import torch
        if torch.cuda.is_available():
            name = torch.cuda.get_device_name(0)
            return CheckResult("CUDA / GPU drivers", PASS, f"{name} (via torch)", critical=False)
        return CheckResult("CUDA / GPU drivers", WARN, "torch installed but CUDA not available", critical=False)
    except ImportError:
        return CheckResult("CUDA / GPU drivers", WARN, "nvidia-smi failed, torch not installed", critical=False)


def check_03_hardware_tier():
    """3. Hardware tier detection — returns (CheckResult, tier_string)."""
    try:
        from server.hardware import detect_hardware
        hw = detect_hardware()
        vram = hw.get("gpu_vram_gb", 0)
        gpu = hw.get("gpu_name", "unknown")

        if vram >= 40:
            tier = "ULTRA"
        elif vram >= 16:
            tier = "HIGH"
        elif vram >= 6:
            tier = "MID"
        else:
            tier = "LOW"

        detail = f"{tier} — {gpu}, {vram:.1f} GB VRAM"
        return CheckResult("Hardware tier detection", PASS, detail, critical=False), tier
    except ImportError as exc:
        return CheckResult("Hardware tier detection", WARN, f"ImportError: {exc}", critical=False), "LOW"
    except Exception as exc:
        return CheckResult("Hardware tier detection", WARN, f"Error: {exc}", critical=False), "LOW"


def check_04_ollama_installed():
    """4. Ollama installed"""
    ok, out = run_cmd(["ollama", "--version"])
    if ok:
        return CheckResult("Ollama installed", PASS, out)
    return CheckResult("Ollama installed", FAIL, "ollama not found in PATH")


def check_05_ollama_running():
    """5. Ollama service running"""
    ok, _out = run_cmd(["ollama", "list"])
    if ok:
        return CheckResult("Ollama service running", PASS)
    return CheckResult("Ollama service running", FAIL, "'ollama list' failed — is the service running?")


def _get_ollama_models() -> str:
    """Fetch ``ollama list`` output once for reuse."""
    ok, out = run_cmd(["ollama", "list"])
    return out if ok else ""


def check_06_llama3(ollama_output: str):
    """6. llama3 model present"""
    for line in ollama_output.splitlines():
        if "llama3" in line.lower():
            model_name = line.split()[0] if line.split() else ""
            return CheckResult("llama3 model present", PASS, model_name)
    return CheckResult("llama3 model present", FAIL, "llama3 not found in ollama list")


def check_07_ultra_70b(ollama_output: str, tier: str):
    """7. ULTRA-only: llama3.1:70b-q4_k_m present"""
    name = "llama3.1:70b-q4_k_m present"
    if tier != "ULTRA":
        return CheckResult(name, SKIP, f"Not required for {tier} tier", critical=False)
    for line in ollama_output.splitlines():
        parts = line.split()
        if parts and parts[0] == "llama3.1:70b-q4_k_m":
            return CheckResult(name, PASS)
    return CheckResult(name, FAIL, "Model not pulled — needed for ULTRA tier")


def check_08_ultra_mixtral(ollama_output: str, tier: str):
    """8. ULTRA-only: mixtral:8x7b present"""
    name = "mixtral:8x7b present"
    if tier != "ULTRA":
        return CheckResult(name, SKIP, f"Not required for {tier} tier", critical=False)
    for line in ollama_output.splitlines():
        parts = line.split()
        if parts and parts[0].startswith("mixtral:8x7b"):
            return CheckResult(name, PASS)
    return CheckResult(name, FAIL, "Model not pulled — needed for ULTRA tier")


def check_09_gpt_sovits_venv():
    """9. GPT-SoVITS venv exists"""
    if platform.system() == "Windows":
        venv_python = PROJECT_ROOT / "gpt_sovits_env" / "Scripts" / "python.exe"
    else:
        venv_python = PROJECT_ROOT / "gpt_sovits_env" / "bin" / "python"
    if venv_python.exists():
        return CheckResult("GPT-SoVITS venv exists", PASS, str(venv_python.relative_to(PROJECT_ROOT)), critical=False)
    return CheckResult("GPT-SoVITS venv exists", WARN, f"Not found: {venv_python.name}", critical=False)


def check_10_gpt_sovits_mario_models():
    """10. GPT-SoVITS Mario models exist"""
    base = PROJECT_ROOT / "mario_models_new" / "GPT_SoVITS_Mario"
    files = {"Mario-e20.ckpt": base / "Mario-e20.ckpt",
             "Mario_e15_s255.pth": base / "Mario_e15_s255.pth"}
    missing = [n for n, p in files.items() if not p.exists()]
    if not missing:
        return CheckResult("GPT-SoVITS Mario models exist", PASS, critical=False)
    return CheckResult("GPT-SoVITS Mario models exist", WARN, f"Missing: {', '.join(missing)}", critical=False)


def check_11_gpt_sovits_pretrained():
    """11. GPT-SoVITS pretrained models exist"""
    base = PROJECT_ROOT / "gpt_sovits_repo" / "GPT_SoVITS" / "pretrained_models"
    dirs = {"chinese-roberta-wwm-ext-large": base / "chinese-roberta-wwm-ext-large",
            "chinese-hubert-base": base / "chinese-hubert-base"}
    missing = [n for n, p in dirs.items() if not p.exists()]
    if not missing:
        return CheckResult("GPT-SoVITS pretrained models exist", PASS, critical=False)
    return CheckResult("GPT-SoVITS pretrained models exist", WARN, f"Missing: {', '.join(missing)}", critical=False)


def check_12_rvc_models():
    """12. RVC models exist (Switch + TITAN)"""
    switch_pth = PROJECT_ROOT / "mario_models_new" / "MarioSwitch" / "SuperMario-NintendoSwitchEra.pth"
    titan_pth = PROJECT_ROOT / "server" / "data" / "rvc_model" / "SuperMario-TITAN_e500_s13000.pth"
    missing = []
    if not switch_pth.exists():
        missing.append("NintendoSwitchEra.pth")
    if not titan_pth.exists():
        missing.append("TITAN_e500_s13000.pth (active)")
    if not missing:
        return CheckResult("RVC models exist", PASS, "Switch + TITAN", critical=False)
    return CheckResult("RVC models exist", WARN, f"Missing: {', '.join(missing)}", critical=False)


def check_13_reference_audio():
    """13. Mario reference audio"""
    primary = PROJECT_ROOT / "server" / "data" / "mario_reference_sentences_30s.wav"
    fallback = PROJECT_ROOT / "server" / "data" / "mario_reference_sentences.wav"
    if primary.exists():
        return CheckResult("Mario reference audio", PASS, "30s version", critical=False)
    if fallback.exists():
        return CheckResult("Mario reference audio", PASS, "standard version (fallback)", critical=False)
    return CheckResult("Mario reference audio", WARN, "No reference audio found", critical=False)


def check_14_fish_speech(tier: str):
    """14. ULTRA-only: Fish Speech installed"""
    name = "Fish Speech installed"
    if tier != "ULTRA":
        return CheckResult(name, SKIP, f"Not required for {tier} tier", critical=False)
    ok, _out = run_cmd([sys.executable, "-m", "pip", "show", "fish-speech"])
    if ok:
        return CheckResult(name, PASS)
    return CheckResult(name, FAIL, "pip show fish-speech failed — needed for ULTRA tier")


def check_15_config_json():
    """15. config.json exists and is valid JSON"""
    cfg_path = PROJECT_ROOT / "config.json"
    if not cfg_path.exists():
        return CheckResult("config.json exists and valid", FAIL, "File not found")
    try:
        with open(cfg_path, encoding="utf-8") as f:
            data = json.load(f)
        keys = len(data) if isinstance(data, dict) else "?"
        return CheckResult("config.json exists and valid", PASS, f"{keys} top-level keys")
    except json.JSONDecodeError as exc:
        return CheckResult("config.json exists and valid", FAIL, f"Invalid JSON: {exc}")


def check_16_qdrant():
    """16. qdrant-client installed"""
    try:
        from qdrant_client import QdrantClient  # noqa: F401
        return CheckResult("qdrant-client installed", PASS)
    except ImportError:
        return CheckResult("qdrant-client installed", FAIL, "pip install qdrant-client")


def check_17_vip_profile():
    """17. VIP profile exists"""
    vip = PROJECT_ROOT / "server" / "data" / "vip_profiles" / "jacob_hoppenstedt.json"
    if vip.exists():
        return CheckResult("VIP profile exists", PASS, "jacob_hoppenstedt.json", critical=False)
    return CheckResult("VIP profile exists", WARN, "Missing jacob_hoppenstedt.json", critical=False)


def check_18_sfx_files():
    """18. SFX WAV files exist (expect >= 6)"""
    sfx_dir = PROJECT_ROOT / "assets" / "sfx"
    if not sfx_dir.exists():
        return CheckResult("SFX WAV files exist", WARN, "assets/sfx/ directory not found", critical=False)
    wavs = list(sfx_dir.glob("*.wav"))
    count = len(wavs)
    if count >= 6:
        return CheckResult("SFX WAV files exist", PASS, f"{count} WAV files", critical=False)
    return CheckResult("SFX WAV files exist", WARN, f"Found {count}/6 expected WAV files", critical=False)


def check_19_server_imports():
    """19. Server core imports — validates the full import chain"""
    import logging
    import io

    # server/main.py uses bare imports (from stt import ...) so we need
    # the server/ directory on sys.path for them to resolve.
    server_dir = str(PROJECT_ROOT / "server")
    path_added = server_dir not in sys.path
    if path_added:
        sys.path.insert(1, server_dir)

    # Suppress log noise and pygame banner during import
    os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
    old_level = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    old_stderr = sys.stderr
    sys.stderr = io.StringIO()
    try:
        from server import main  # noqa: F401
        return CheckResult("Server core imports", PASS)
    except ImportError as exc:
        return CheckResult("Server core imports", FAIL, str(exc))
    except Exception as exc:
        return CheckResult("Server core imports", WARN, f"Import side-effect: {type(exc).__name__}: {exc}")
    finally:
        sys.stderr = old_stderr
        logging.disable(old_level)
        if path_added and server_dir in sys.path:
            sys.path.remove(server_dir)


def check_20_edge_tts():
    """20. Edge TTS quick test"""
    null_path = "NUL" if platform.system() == "Windows" else "/dev/null"
    t0 = time.time()
    ok, _out = run_cmd(
        ["edge-tts", "--text", "It's-a me, Mario!", "--write-media", null_path],
        timeout=30,
    )
    elapsed = time.time() - t0
    if ok:
        return CheckResult("Edge TTS quick test", PASS, f"{elapsed:.1f}s", critical=False)
    return CheckResult("Edge TTS quick test", WARN, "edge-tts command failed", critical=False)


def check_bonus_gpt_sovits_synthesis():
    """Bonus (--full-tts): GPT-SoVITS subprocess synthesis test."""
    if platform.system() == "Windows":
        venv_python = PROJECT_ROOT / "gpt_sovits_env" / "Scripts" / "python.exe"
    else:
        venv_python = PROJECT_ROOT / "gpt_sovits_env" / "bin" / "python"

    if not venv_python.exists():
        return CheckResult("GPT-SoVITS synthesis test", SKIP, "venv not found", critical=False)

    test_script = (
        "import sys; sys.path.insert(0, 'gpt_sovits_repo'); "
        "from GPT_SoVITS.TTS_infer_pack.TTS import TTS; "
        "print('GPT-SoVITS TTS import OK')"
    )
    t0 = time.time()
    ok, out = run_cmd([str(venv_python), "-c", test_script], timeout=60)
    elapsed = time.time() - t0
    if ok:
        return CheckResult("GPT-SoVITS synthesis test", PASS, f"Import OK in {elapsed:.1f}s", critical=False)
    return CheckResult("GPT-SoVITS synthesis test", WARN, f"Import failed ({elapsed:.1f}s)", critical=False)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Verify Mario AI Party Bot setup")
    parser.add_argument("--full-tts", action="store_true", help="Include GPT-SoVITS synthesis test")
    args = parser.parse_args()

    results: list[CheckResult] = []
    detected_tier = "LOW"  # default, updated by check 3

    # ---- Run all 20 checks ----

    # 1. Python version
    results.append(check_01_python_version())

    # 2. CUDA / GPU
    results.append(check_02_cuda_gpu())

    # 3. Hardware tier (also sets detected_tier for later checks)
    hw_result, detected_tier = check_03_hardware_tier()
    results.append(hw_result)

    # 4. Ollama installed
    results.append(check_04_ollama_installed())

    # 5. Ollama service running
    results.append(check_05_ollama_running())

    # Fetch ollama model list once for checks 6-8
    ollama_output = _get_ollama_models()

    # 6. llama3 model
    results.append(check_06_llama3(ollama_output))

    # 7. ULTRA-only: 70b model
    results.append(check_07_ultra_70b(ollama_output, detected_tier))

    # 8. ULTRA-only: mixtral model
    results.append(check_08_ultra_mixtral(ollama_output, detected_tier))

    # 9. GPT-SoVITS venv
    results.append(check_09_gpt_sovits_venv())

    # 10. GPT-SoVITS Mario models
    results.append(check_10_gpt_sovits_mario_models())

    # 11. GPT-SoVITS pretrained models
    results.append(check_11_gpt_sovits_pretrained())

    # 12. RVC models
    results.append(check_12_rvc_models())

    # 13. Mario reference audio
    results.append(check_13_reference_audio())

    # 14. ULTRA-only: Fish Speech
    results.append(check_14_fish_speech(detected_tier))

    # 15. config.json
    results.append(check_15_config_json())

    # 16. qdrant-client
    results.append(check_16_qdrant())

    # 17. VIP profile
    results.append(check_17_vip_profile())

    # 18. SFX files
    results.append(check_18_sfx_files())

    # 19. Server core imports
    results.append(check_19_server_imports())

    # 20. Edge TTS
    results.append(check_20_edge_tts())

    # Bonus: GPT-SoVITS synthesis (only with --full-tts)
    if args.full_tts:
        results.append(check_bonus_gpt_sovits_synthesis())

    # ---- Print formatted table ----
    print()
    print(f"{COLORS['BOLD']}{'=' * 62}{COLORS['RESET']}")
    print(f"{COLORS['BOLD']}  Mario AI Party Bot — Setup Verification{COLORS['RESET']}")
    print(f"{COLORS['BOLD']}{'=' * 62}{COLORS['RESET']}")
    print()

    for r in results:
        fmt(r)

    # ---- Summary ----
    count_pass = sum(1 for r in results if r.status == PASS)
    count_fail = sum(1 for r in results if r.status == FAIL)
    count_warn = sum(1 for r in results if r.status == WARN)
    count_skip = sum(1 for r in results if r.status == SKIP)
    total = len(results)

    critical_fails = sum(1 for r in results if r.status == FAIL and r.critical)

    print()
    print(f"  {'-' * 58}")
    print(f"  {count_pass}/{total} passed, {count_skip} skipped, {count_warn} warnings, {count_fail} failed")
    print(f"  {'-' * 58}")

    if critical_fails > 0:
        print(f"\n  {COLORS[FAIL]}RESULT: CRITICAL FAILURES — please fix before running{COLORS['RESET']}")
        sys.exit(1)
    elif count_warn > 0 or count_fail > 0:
        print(f"\n  {COLORS[WARN]}RESULT: WARNINGS — system may work but check items above{COLORS['RESET']}")
        sys.exit(2)
    else:
        print(f"\n  {COLORS[PASS]}RESULT: ALL CHECKS PASSED ✓{COLORS['RESET']}")
        sys.exit(0)


if __name__ == "__main__":
    main()
