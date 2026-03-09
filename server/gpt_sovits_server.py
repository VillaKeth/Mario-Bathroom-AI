"""
GPT-SoVITS TTS Server — runs as a subprocess in the gpt_sovits_env venv.
Communicates via stdin/stdout JSON protocol for low-latency integration with main TTS pipeline.

Usage: gpt_sovits_env\Scripts\python.exe server\gpt_sovits_server.py
Protocol: 
  stdin  → JSON line: {"text": "Hello!", "ref_audio": "path.wav", "prompt_text": "ref text", "speed": 1.0}
  stdout → JSON line: {"status": "ok", "audio_path": "output.wav", "duration": 2.5, "elapsed": 1.3}
           or {"status": "error", "error": "message"}
  Special: {"cmd": "ping"} → {"status": "pong"}
           {"cmd": "quit"} → graceful shutdown
"""
import os
import sys
import json
import time
import tempfile
import numpy as np

DEBUG_SOVITS = True

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_DIR = os.path.join(BASE_DIR, "gpt_sovits_repo")
GPT_SOVITS_DIR = os.path.join(REPO_DIR, "GPT_SoVITS")
sys.path.insert(0, REPO_DIR)
sys.path.insert(0, GPT_SOVITS_DIR)

MODEL_DIR = os.path.join(BASE_DIR, "mario_models_new", "GPT_SoVITS_Mario")
SOVITS_PATH = os.path.join(MODEL_DIR, "Mario_e15_s255.pth")
GPT_PATH = os.path.join(MODEL_DIR, "Mario-e20.ckpt")
DEFAULT_REF_AUDIO = os.path.join(MODEL_DIR, "mario_ref.wav")
OUTPUT_DIR = os.path.join(BASE_DIR, "server", "tts_cache")


def init_pipeline():
    """Initialize GPT-SoVITS pipeline — loads models onto GPU."""
    import yaml
    from TTS_infer_pack.TTS import TTS, TTS_Config

    config_path = os.path.join(MODEL_DIR, "tts_infer.yaml")
    config = {
        "custom": {
            "bert_base_path": os.path.join(GPT_SOVITS_DIR, "pretrained_models", "chinese-roberta-wwm-ext-large"),
            "cnhuhbert_base_path": os.path.join(GPT_SOVITS_DIR, "pretrained_models", "chinese-hubert-base"),
            "device": "cuda",
            "is_half": False,
            "t2s_weights_path": GPT_PATH,
            "version": "v2",
            "vits_weights_path": SOVITS_PATH,
        }
    }
    with open(config_path, "w") as f:
        yaml.dump(config, f)

    tts_config = TTS_Config(config_path)
    pipeline = TTS(tts_config)
    return pipeline


def synthesize(pipeline, text, ref_audio=None, prompt_text=None, speed=1.0):
    """Generate audio from text using GPT-SoVITS pipeline."""
    import soundfile as sf

    if ref_audio is None:
        ref_audio = DEFAULT_REF_AUDIO
    if prompt_text is None:
        prompt_text = "It's a me Mario"

    # Clean text for better GPT-SoVITS synthesis
    # Remove hyphens in Mario-speak (e.g., "It's-a" → "It'sa") to avoid phoneme confusion
    clean_text = text.replace("-a ", "a ").replace("-A ", "a ")
    
    req = {
        "text": clean_text,
        "text_lang": "en",
        "ref_audio_path": ref_audio,
        "prompt_text": prompt_text,
        "prompt_lang": "en",
        "text_split_method": "cut0",  # No splitting — short phrases stay intact, avoids garbled transitions
        "speed_factor": speed,
    }

    chunks = []
    sr = 32000
    for sr_chunk, audio_chunk in pipeline.run(req):
        sr = sr_chunk
        chunks.append(audio_chunk)

    if not chunks:
        raise RuntimeError("GPT-SoVITS produced no audio chunks")

    full_audio = np.concatenate(chunks)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUT_DIR, f"sovits_{int(time.time()*1000)}.wav")
    sf.write(output_path, full_audio, sr)

    duration = len(full_audio) / sr
    return output_path, duration


def main():
    """Main server loop — reads JSON commands from stdin, writes responses to stdout."""
    if DEBUG_SOVITS:
        print(json.dumps({"status": "loading", "msg": "Initializing GPT-SoVITS pipeline..."}), flush=True)

    pipeline = init_pipeline()

    print(json.dumps({"status": "ready", "msg": "GPT-SoVITS pipeline ready"}), flush=True)

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            req = json.loads(line)
        except json.JSONDecodeError as e:
            print(json.dumps({"status": "error", "error": f"Invalid JSON: {e}"}), flush=True)
            continue

        cmd = req.get("cmd")
        if cmd == "ping":
            print(json.dumps({"status": "pong"}), flush=True)
            continue
        if cmd == "quit":
            print(json.dumps({"status": "goodbye"}), flush=True)
            break

        text = req.get("text")
        if not text:
            print(json.dumps({"status": "error", "error": "Missing 'text' field"}), flush=True)
            continue

        t0 = time.time()
        try:
            output_path, duration = synthesize(
                pipeline,
                text=text,
                ref_audio=req.get("ref_audio"),
                prompt_text=req.get("prompt_text"),
                speed=req.get("speed", 1.0),
            )
            elapsed = time.time() - t0
            print(json.dumps({
                "status": "ok",
                "audio_path": output_path,
                "duration": round(duration, 3),
                "elapsed": round(elapsed, 3),
            }), flush=True)
        except Exception as e:
            elapsed = time.time() - t0
            print(json.dumps({
                "status": "error",
                "error": f"{type(e).__name__}: {e}",
                "elapsed": round(elapsed, 3),
            }), flush=True)


if __name__ == "__main__":
    main()
