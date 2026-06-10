"""Voice setup — fully offline, LLM-free.

Zero-shot cloners (GPT-SoVITS v2 base, Fish Speech) clone a character's voice
directly from an uploaded reference clip plus that clip's transcript. The
transcript is produced locally by Whisper (see voice_transcribe.py), so the whole
pipeline runs with no cloud service and no LLM query. There is no per-character
training step. Edge TTS is always kept as a character-matched fallback.
"""
import os
import shutil
import logging

logger = logging.getLogger(__name__)

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))

# Filesystem locations that indicate an engine is installed on this machine.
SOVITS_REPO = os.path.join(PROJECT_ROOT, "gpt_sovits_repo")
SOVITS_ENV = os.path.join(PROJECT_ROOT, "gpt_sovits_env")
SOVITS_V2_BASE = os.path.join(
    SOVITS_REPO, "GPT_SoVITS", "pretrained_models", "gsv-v2final-pretrained", "s2G2333k.pth"
)
FISH_ENV = os.path.join(PROJECT_ROOT, "fish_speech_env")
# Fish Speech v1.5.1 uses the non-gated fish-speech-1.5 checkpoint (firefly
# decoder). Require the actual decoder weight so we never advertise Fish as ready
# when only a README/partial download landed.
FISH_CKPT_DIR = os.path.join(PROJECT_ROOT, "fish_speech_ckpts")
FISH_CODEC = os.path.join(FISH_CKPT_DIR, "firefly-gan-vq-fsq-8x1024-21hz-generator.pth")


def detect_available_engines() -> list[dict]:
    """Report which voice engines are usable on this machine right now."""
    engines = []

    sovits_available = (
        os.path.isdir(SOVITS_REPO)
        and os.path.isdir(SOVITS_ENV)
        and os.path.exists(SOVITS_V2_BASE)
    )
    engines.append({
        "name": "sovits", "display_name": "GPT-SoVITS", "priority": 1,
        "vram_required": 8, "available": sovits_available,
        "needs_reference_audio": True, "zero_shot": True,
        "status": "ready" if sovits_available else "needs_setup",
        "description": "Modular zero-shot voice cloning from a reference clip (v2 base).",
    })

    fish_available = os.path.isdir(FISH_ENV) and os.path.exists(FISH_CODEC)
    engines.append({
        "name": "fish_speech", "display_name": "Fish Speech", "priority": 2,
        "vram_required": 4, "available": fish_available,
        "needs_reference_audio": True, "zero_shot": True,
        "status": "ready" if fish_available else "needs_setup",
        "description": "Fast zero-shot voice cloning from a reference clip.",
    })

    engines.append({
        "name": "edge", "display_name": "Edge TTS", "priority": 3,
        "vram_required": 0, "available": True,
        "needs_reference_audio": False, "zero_shot": False,
        "status": "ready",
        "description": "Microsoft neural voices — character-matched fallback.",
    })

    return engines


def get_engine_status(engine_name: str) -> dict:
    for e in detect_available_engines():
        if e["name"] == engine_name:
            return e
    return {"name": engine_name, "available": False, "status": "unknown"}


# Map wizard/legacy engine names to the canonical runtime engine names.
_ENGINE_ALIAS = {
    "hybrid": "sovits",
    "sovits": "sovits",
    "gpt_sovits": "sovits",
    "fish": "fish_speech",
    "fish_speech": "fish_speech",
    "edge_rvc": "edge",
    "edge": "edge",
}


def _patch_character_voice_yaml(char_dir: str, updates: dict):
    """Merge keys into the character.yaml 'voice' block (preserving edge_voice/rate/pitch)."""
    import yaml
    yaml_path = os.path.join(char_dir, "character.yaml")
    if not os.path.exists(yaml_path):
        logger.warning(f"[voice] character.yaml not found at {yaml_path}; cannot record voice config")
        return
    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    voice = data.get("voice") or {}
    voice.update(updates)
    data["voice"] = voice
    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


def _trim_reference(voice_dir: str) -> bool:
    """Normalize the reference for the cloning engines' constraints.

    GPT-SoVITS hard-fails on references outside 3-10s, and quiet/whispered
    sections clone badly. If reference_audio.wav is longer than 10s:
      - keep the original as reference_full.wav
      - write reference_clean.wav (first 14s, mono 32k) for Fish Speech
      - overwrite reference_audio.wav with the LOUDEST contiguous 8s window
        (max-RMS scan), so the engines get clear, energetic speech.
    Returns True if a trim happened.
    """
    import subprocess
    ref = os.path.join(voice_dir, "reference_audio.wav")
    try:
        out = subprocess.run(
            ["ffmpeg", "-i", ref, "-ac", "1", "-ar", "32000", "-f", "f32le", "-"],
            capture_output=True, timeout=120)
        import numpy as np
        audio = np.frombuffer(out.stdout, dtype=np.float32)
        sr = 32000
        dur = len(audio) / sr
        if dur <= 10.0 or len(audio) == 0:
            return False
        full = os.path.join(voice_dir, "reference_full.wav")
        if not os.path.exists(full):
            shutil.copy(ref, full)
        subprocess.run(["ffmpeg", "-y", "-i", full, "-t", "14", "-ac", "1", "-ar", "32000",
                        os.path.join(voice_dir, "reference_clean.wav")],
                       capture_output=True, timeout=120)
        # loudest contiguous 8s window via cumulative energy
        win = min(8 * sr, len(audio) - 1)
        sq = audio.astype(np.float64) ** 2
        cum = np.concatenate(([0.0], np.cumsum(sq)))
        energy = cum[win:] - cum[:-win]
        start = int(np.argmax(energy)) / sr
        subprocess.run(["ffmpeg", "-y", "-ss", f"{start:.2f}", "-t", "8", "-i", full,
                        "-ac", "1", "-ar", "32000", ref], capture_output=True, timeout=120)
        return True
    except Exception as e:
        logger.warning(f"reference trim failed (using original): {e}")
        return False


def prepare_voice_artifacts(config: dict, char_dir: str) -> dict:
    """Offline, LLM-free voice setup for a freshly built character.

    If a reference clip is present, transcribe it locally and record modular
    per-character voice config so BOTH GPT-SoVITS and Fish Speech can clone it
    zero-shot (lets the user A/B them). Edge TTS stays as the fallback.
    """
    from character_creator import voice_transcribe

    voice_dir = os.path.join(char_dir, "voice")
    os.makedirs(voice_dir, exist_ok=True)
    ref_audio = os.path.join(voice_dir, "reference_audio.wav")
    rel_ref = "voice/reference_audio.wav"

    requested = config.get("preferred_engine", "edge")
    result = {
        "requested_engine": requested,
        "engine": "edge",
        "fallback_engine": "edge",
        "engines_ready": ["edge"],
        "reference_audio": None,
        "prompt_text": None,
        "transcription": "skipped",
        "artifacts_ready": True,
        "errors": [],
    }

    has_ref = os.path.exists(ref_audio) and os.path.getsize(ref_audio) > 1024

    # Default behavior: if the user didn't upload a clip, automatically pull one
    # from YouTube so a non-technical user gets a real character voice with zero
    # extra steps. Set config["auto_voice"] = False to opt out.
    if not has_ref and config.get("auto_voice", True):
        try:
            from character_creator import voice_finder
            if voice_finder.is_available():
                name = config.get("name", "").strip()
                query = (config.get("voice_search_query")
                         or (f"{name} voice lines" if name else "")).strip()
                if query:
                    hits = voice_finder.search(query, max_results=6)
                    # Prefer a short-to-medium clip (5s..240s) for a clean reference.
                    hits = sorted(
                        [h for h in hits if 5 <= (h.get("duration") or 0) <= 240] or hits,
                        key=lambda h: h.get("duration") or 9999,
                    )
                    for h in hits[:3]:
                        if voice_finder.download_clip(h["url"], voice_dir, max_duration=25):
                            result["voice_source"] = {
                                "type": "youtube", "title": h.get("title"), "url": h.get("url")}
                            break
        except Exception as e:  # never block creation on auto-pull
            result["errors"].append(f"Auto voice pull failed: {e}")
        has_ref = os.path.exists(ref_audio) and os.path.getsize(ref_audio) > 1024

    if not has_ref:
        if _ENGINE_ALIAS.get(requested, requested) != "edge":
            result["errors"].append(
                f"No reference clip uploaded; '{requested}' needs one. Using Edge TTS fallback."
            )
        _patch_character_voice_yaml(char_dir, {"preferred_engine": "edge", "engines": ["edge"]})
        return result

    result["reference_audio"] = rel_ref

    # Enforce engine constraints (SoVITS needs 3-10s; whispers clone badly).
    if _trim_reference(voice_dir):
        result["reference_trimmed"] = True

    # Local Whisper transcription — the offline, independent piece.
    tr = voice_transcribe.transcribe_file(ref_audio)
    prompt_text = tr.get("text", "")
    if prompt_text:
        with open(os.path.join(voice_dir, "reference_text.txt"), "w", encoding="utf-8") as f:
            f.write(prompt_text)
        result["prompt_text"] = prompt_text
        result["transcription"] = "ok"
    else:
        result["transcription"] = "failed"
        result["errors"].append(
            "Could not transcribe reference clip ("
            + (tr.get("error") or "empty result")
            + "). You can hand-edit voice/reference_text.txt to improve cloning."
        )

    # Which cloners are installed right now
    engines_ready = ["edge"]
    for name in ("sovits", "fish_speech"):
        st = get_engine_status(name)
        if st.get("available"):
            engines_ready.append(name)
        else:
            result["errors"].append(
                f"{st.get('display_name', name)} not installed yet — run its setup to enable it."
            )
    result["engines_ready"] = engines_ready

    # Choose the active engine: honor request if available, else best clone, else edge
    want = _ENGINE_ALIAS.get(requested, requested)
    if want in engines_ready and want != "edge":
        active = want
    elif "fish_speech" in engines_ready:
        # Fish Speech wins zero-shot A/B (cleaner, longer reference support)
        active = "fish_speech"
    elif "sovits" in engines_ready:
        active = "sovits"
    else:
        active = "edge"
    result["engine"] = active

    _patch_character_voice_yaml(char_dir, {
        "preferred_engine": active,
        "engines": engines_ready,
        "reference_audio": rel_ref,
        "prompt_text": prompt_text,
        "prompt_lang": tr.get("language") or "en",
    })
    return result
