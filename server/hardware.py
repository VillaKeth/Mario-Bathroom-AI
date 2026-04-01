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
    "ultra": {
        "tts_workers": 8,
        "tts_concurrency": 4,
        "gpu_idle_threshold": 0.5,
        "precache_pause_seconds": 0.5,
        "max_background_tasks": 50,
        "max_cache_memory": 500,
        "llm_num_predict": 80,
        "llm_num_ctx": 8192,
        "conversation_history_limit": 100,
        "llm_quality_model": "llama3.1:70b-q4_k_m",
        "llm_fast_model": "mixtral:8x7b",
        "stt_device": "cpu",
    },
    "high": {
        "tts_workers": 4,
        "tts_concurrency": 2,
        "gpu_idle_threshold": 1.0,
        "precache_pause_seconds": 1.0,
        "max_background_tasks": 25,
        "max_cache_memory": 300,
        "llm_num_predict": 40,
        "llm_num_ctx": 4096,
        "conversation_history_limit": 60,
        "llm_quality_model": "llama3:8b",
        "llm_fast_model": "llama3:8b",
        "stt_device": "cpu",
    },
    "medium": {
        "tts_workers": 2,
        "tts_concurrency": 1,
        "gpu_idle_threshold": 2.0,
        "precache_pause_seconds": 1.5,
        "max_background_tasks": 15,
        "max_cache_memory": 200,
        "llm_num_predict": 30,
        "llm_num_ctx": 2048,
        "conversation_history_limit": 40,
        "llm_quality_model": "llama3:8b",
        "llm_fast_model": "llama3:8b",
        "stt_device": "cpu",
    },
    "low": {
        "tts_workers": 1,
        "tts_concurrency": 1,
        "gpu_idle_threshold": 3.0,
        "precache_pause_seconds": 2.0,
        "max_background_tasks": 10,
        "max_cache_memory": 100,
        "llm_num_predict": 25,
        "llm_num_ctx": 2048,
        "conversation_history_limit": 28,
        "llm_quality_model": "llama3:8b",
        "llm_fast_model": "llama3:8b",
        "stt_device": "cpu",
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
