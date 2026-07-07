"""Hardware auto-detection for optimal performance tuning.

Detects CPU, RAM, and GPU capabilities at startup and provides
performance-tier-based defaults. Config values of "auto" are resolved
to hardware-appropriate settings.
"""
import os
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Hardware detection
# ---------------------------------------------------------------------------

def detect_hardware() -> dict:
    """Return dict with cpu_cores, ram_gb, gpu_vram_gb, gpu_name."""
    info = {
        "cpu_cores": os.cpu_count() or 4,
        "ram_gb": 8,
        "gpu_vram_gb": 0,
        "gpu_name": "none",
    }

    # RAM
    try:
        import psutil
        info["ram_gb"] = round(psutil.virtual_memory().total / (1024**3))
    except ImportError:
        # Windows fallback without psutil
        try:
            import ctypes
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]
            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(stat)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
            info["ram_gb"] = round(stat.ullTotalPhys / (1024**3))
        except Exception:
            pass

    # GPU via torch
    try:
        import torch
        if torch.cuda.is_available():
            info["gpu_name"] = torch.cuda.get_device_name(0)
            info["gpu_vram_gb"] = round(
                torch.cuda.get_device_properties(0).total_memory / (1024**3)
            )
    except ImportError:
        # Fallback: nvidia-smi (no torch needed)
        try:
            import subprocess
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                parts = result.stdout.strip().split(",")
                if len(parts) >= 2:
                    info["gpu_name"] = parts[0].strip()
                    info["gpu_vram_gb"] = round(int(parts[1].strip()) / 1024)
        except Exception:
            pass

    return info


# ---------------------------------------------------------------------------
# Performance tiers
# ---------------------------------------------------------------------------

def _tier(hw: dict) -> str:
    v, r, c = hw["gpu_vram_gb"], hw["ram_gb"], hw["cpu_cores"]
    if v >= 20 and r >= 128 and c >= 32:
        return "ultra"
    if v >= 10 and r >= 32 and c >= 8:
        return "high"
    if v >= 6 and r >= 16:
        return "medium"
    return "low"


_TIER_DEFAULTS = {
    # Ultra tier: ≥20GB VRAM, ≥128GB RAM, ≥32 cores
    # VRAM budget (24GB card like 3090 Ti):
    #   Quality LLM ~8-10GB + GPT-SoVITS ~8GB + overhead ~2GB = ~20GB
    #   Fast LLM swaps in when quality unloads (Ollama keep_alive manages this)
    # NOTE: 70b models need partial CPU offloading (~39GB total).
    #   With Threadripper Pro 8-channel DDR4 (~200GB/s), offloading works at
    #   ~10-15 tok/s. To use 70b, set llm_quality_model in config.json manually.
    "ultra": {
        "tts_workers": 8,
        "tts_concurrency": 6,
        "gpu_idle_threshold": 0.3,
        "precache_pause_seconds": 0.5,
        "max_background_tasks": 80,
        "max_cache_memory": 1000,
        "llm_num_predict": 700,
        "llm_num_ctx": 8192,
        "conversation_history_limit": 150,
        "llm_quality_model": "gemma3:27b",
        "llm_fast_model": "llama3.1:8b",
        "stt_device": "auto",
    },
    "high": {
        "tts_workers": 4,
        "tts_concurrency": 2,
        "gpu_idle_threshold": 1.0,
        "precache_pause_seconds": 1.0,
        "max_background_tasks": 25,
        "max_cache_memory": 300,
        "llm_num_predict": 400,
        "llm_num_ctx": 4096,
        "conversation_history_limit": 60,
        "llm_quality_model": "llama3",
        "llm_fast_model": "llama3",
        "stt_device": "auto",
    },
    "medium": {
        "tts_workers": 2,
        "tts_concurrency": 1,
        "gpu_idle_threshold": 2.0,
        "precache_pause_seconds": 1.5,
        "max_background_tasks": 15,
        "max_cache_memory": 200,
        "llm_num_predict": 300,
        "llm_num_ctx": 4096,
        "conversation_history_limit": 40,
        "llm_quality_model": "llama3",
        "llm_fast_model": "llama3",
        "stt_device": "auto",
    },
    "low": {
        "tts_workers": 2,
        "tts_concurrency": 1,
        "gpu_idle_threshold": 3.0,
        "precache_pause_seconds": 2.0,
        "max_background_tasks": 10,
        "max_cache_memory": 100,
        "llm_num_predict": 250,
        "llm_num_ctx": 4096,
        "conversation_history_limit": 28,
        "llm_quality_model": "llama3",
        "llm_fast_model": "llama3",
        "stt_device": "auto",
    },
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_hw_cache: dict | None = None
_tier_cache: str | None = None


def get_hardware() -> dict:
    """Cached hardware info (detected once)."""
    global _hw_cache
    if _hw_cache is None:
        _hw_cache = detect_hardware()
        _tier_cache_update()
        logger.info(
            f"[HARDWARE] Detected: {_hw_cache['cpu_cores']} cores, "
            f"{_hw_cache['ram_gb']}GB RAM, "
            f"{_hw_cache['gpu_vram_gb']}GB VRAM ({_hw_cache['gpu_name']}) "
            f"→ tier={get_tier()}"
        )
    return _hw_cache


def _tier_cache_update():
    global _tier_cache
    _tier_cache = _tier(_hw_cache) if _hw_cache else "low"


def get_tier() -> str:
    """Return performance tier string: ultra/high/medium/low."""
    if _tier_cache is None:
        get_hardware()
    return _tier_cache


def resolve(setting_name: str, config_value=None):
    """Resolve a setting: use config_value if not 'auto'/None, else auto-detect.
    
    Usage:
        workers = hardware.resolve("tts_workers", server_config.get("tts_workers", "auto"))
    """
    if config_value is not None and config_value != "auto":
        return config_value
    tier = get_tier()
    return _TIER_DEFAULTS[tier].get(setting_name, config_value)


def log_resolved_settings(settings: dict):
    """Log all resolved performance settings at startup."""
    tier = get_tier()
    logger.info(f"[HARDWARE] Performance tier: {tier.upper()}")
    for k, v in settings.items():
        logger.info(f"[HARDWARE]   {k} = {v}")
