"""Voice training orchestration — detects engines, triggers training, tracks progress."""
import os
import sys
import logging
import subprocess
import shutil

logger = logging.getLogger(__name__)

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))

def detect_available_engines() -> list[dict]:
    engines = []
    
    # Fish Speech (priority 1, ~4GB VRAM)
    fish_available = False
    try:
        import fish_speech
        fish_available = True
    except ImportError:
        pass
    engines.append({
        "name": "fish_speech", "display_name": "Fish Speech",
        "priority": 1, "vram_required": 4,
        "available": fish_available,
        "needs_reference_audio": True,
        "status": "ready" if fish_available else "needs_setup",
        "description": "Best quality voice cloning. Needs reference audio."
    })
    
    # GPT-SoVITS (priority 2, ~8GB VRAM)
    sovits_path = os.path.join(PROJECT_ROOT, "gpt_sovits_repo")
    sovits_env = os.path.join(PROJECT_ROOT, "gpt_sovits_env")
    sovits_available = os.path.isdir(sovits_path) and os.path.isdir(sovits_env)
    engines.append({
        "name": "gpt_sovits", "display_name": "GPT-SoVITS",
        "priority": 2, "vram_required": 8,
        "available": sovits_available,
        "needs_reference_audio": True,
        "status": "ready" if sovits_available else "needs_setup",
        "description": "Trainable voice cloning. Needs training audio."
    })
    
    # Edge TTS + RVC (priority 3, ~2GB VRAM)
    rvc_available = False
    try:
        rvc_model_dir = os.path.join(PROJECT_ROOT, "server", "data", "rvc_model")
        rvc_available = os.path.isdir(rvc_model_dir)
    except Exception:
        pass
    engines.append({
        "name": "edge_rvc", "display_name": "Edge TTS + RVC",
        "priority": 3, "vram_required": 2,
        "available": rvc_available,
        "needs_reference_audio": True,
        "status": "ready" if rvc_available else "needs_setup",
        "description": "Voice conversion on top of Edge TTS base voice."
    })
    
    # Edge TTS (priority 4, 0 VRAM — always available)
    engines.append({
        "name": "edge", "display_name": "Edge TTS",
        "priority": 4, "vram_required": 0,
        "available": True,
        "needs_reference_audio": False,
        "status": "ready",
        "description": "Free Microsoft voices. Always available fallback."
    })
    
    return engines

def get_engine_status(engine_name: str) -> dict:
    engines = detect_available_engines()
    for e in engines:
        if e["name"] == engine_name:
            return e
    return {"name": engine_name, "available": False, "status": "unknown"}

def prepare_voice_artifacts(config: dict, char_dir: str) -> dict:
    """Prepare voice artifacts for a character based on chosen engine and audio."""
    engine = config.get("preferred_engine", "edge")
    voice_dir = os.path.join(char_dir, "voice")
    os.makedirs(voice_dir, exist_ok=True)
    ref_audio = os.path.join(voice_dir, "reference_audio.wav")
    
    result = {"engine": engine, "fallback_engine": "edge", "artifacts_ready": False,
              "errors": [], "training_status": "not_needed"}
    
    if engine == "edge":
        result["artifacts_ready"] = True
        return result
    
    if not os.path.exists(ref_audio):
        result["errors"].append(f"Reference audio required for {engine} but not found at {ref_audio}")
        result["engine"] = "edge"
        result["artifacts_ready"] = True
        return result
    
    if engine == "fish_speech":
        status = get_engine_status("fish_speech")
        if status["available"]:
            result["artifacts_ready"] = True
            result["training_status"] = "not_needed_zero_shot"
        else:
            result["errors"].append("Fish Speech not installed, falling back to Edge TTS")
            result["engine"] = "edge"
            result["artifacts_ready"] = True
    
    elif engine == "gpt_sovits":
        status = get_engine_status("gpt_sovits")
        if status["available"]:
            try:
                _trigger_sovits_training(ref_audio, char_dir)
                result["artifacts_ready"] = True
                result["training_status"] = "training_started"
            except Exception as e:
                result["errors"].append(f"GPT-SoVITS training failed: {e}. Falling back to Edge TTS.")
                result["engine"] = "edge"
                result["artifacts_ready"] = True
                result["training_status"] = "training_failed"
        else:
            result["errors"].append("GPT-SoVITS not installed, falling back to Edge TTS")
            result["engine"] = "edge"
            result["artifacts_ready"] = True
    
    elif engine == "edge_rvc":
        status = get_engine_status("edge_rvc")
        if status["available"]:
            result["artifacts_ready"] = True
            result["training_status"] = "not_needed_runtime_conversion"
        else:
            result["errors"].append("RVC not set up, falling back to Edge TTS")
            result["engine"] = "edge"
            result["artifacts_ready"] = True
    
    return result

def _trigger_sovits_training(ref_audio: str, char_dir: str):
    sovits_path = os.path.join(PROJECT_ROOT, "gpt_sovits_repo")
    if not os.path.isdir(sovits_path):
        raise FileNotFoundError("gpt_sovits_repo not found")
    marker = os.path.join(char_dir, "voice", ".training_requested")
    with open(marker, "w") as f:
        f.write(f"engine=gpt_sovits\naudio={ref_audio}\nstatus=pending\n")
    logger.info(f"GPT-SoVITS training requested for {char_dir}")
