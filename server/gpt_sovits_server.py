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
    """Initialize GPT-SoVITS pipeline — loads models onto GPU.
    
    Redirects stdout to stderr during loading to keep stdout clean for JSON protocol.
    """
    import yaml
    from io import StringIO

    # Redirect stdout during model loading (libraries print to stdout)
    _real_stdout = sys.stdout
    sys.stdout = sys.stderr
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

    # Restore stdout for JSON protocol
    sys.stdout = _real_stdout
    return pipeline


def synthesize(pipeline, text, ref_audio=None, prompt_text=None, speed=1.0):
    """Generate audio from text using GPT-SoVITS pipeline."""
    import soundfile as sf

    if ref_audio is None:
        ref_audio = DEFAULT_REF_AUDIO
    if prompt_text is None:
        prompt_text = "It's a me Mario"

    # Clean text for better GPT-SoVITS synthesis
    import re as _re
    clean_text = text

    # Collapse repeated characters that cause letter-by-letter pronunciation
    # "YAAAAYYYY" → "YAAY", "BAAAAAALLS" → "BAALLS", "AHHHAARRRRRGGGGHHH" → "AHHAARRGGHH"
    clean_text = _re.sub(r'(.)\1{2,}', r'\1\1', clean_text)

    # Normalize ALL CAPS to lowercase (GPT-SoVITS spells out capital letters)
    # Preserve first-letter caps for natural sentence flow
    def _normalize_caps(m):
        word = m.group(0)
        return word[0] + word[1:].lower()
    # Match any word with 2+ consecutive uppercase letters
    clean_text = _re.sub(r'\b[A-Z][A-Z]+\b', _normalize_caps, clean_text)
    # Also handle single ALL-CAP words at sentence start
    clean_text = _re.sub(r'(?<=[.!?]\s)[A-Z]{2,}\b', _normalize_caps, clean_text)

    # Remove ALL hyphens — GPT-SoVITS either reads "-" as "minus" or produces silence
    # Step 1: "word-word" → "word word" (compound words keep space)
    clean_text = _re.sub(r'(?<=\w)-(?=\w)', ' ', clean_text)
    # Step 2: " - " freestanding hyphens → comma pause
    clean_text = _re.sub(r'\s+-+\s+', ', ', clean_text)
    # Step 3: Remove ALL remaining hyphens (leading, trailing, multiple dashes)
    clean_text = _re.sub(r'-+', '', clean_text)

    # Remove special characters that cause garbled output
    clean_text = _re.sub(r'[♪♫🎵🎶🎤🎸🎹🎺🎻🎷🥁🎭🎪]', '', clean_text)  # Music/performance emojis
    clean_text = _re.sub(r'[\U0001F600-\U0001F64F]', '', clean_text)  # Emoticons
    clean_text = _re.sub(r'[\U0001F300-\U0001F5FF]', '', clean_text)  # Misc symbols
    clean_text = _re.sub(r'[\U0001F680-\U0001F6FF]', '', clean_text)  # Transport/map
    clean_text = _re.sub(r'[\U0001F900-\U0001F9FF]', '', clean_text)  # Supplemental symbols
    clean_text = _re.sub(r'[\u2600-\u26FF]', '', clean_text)  # Misc symbols (★, ☆, etc.)
    clean_text = _re.sub(r'[\u2700-\u27BF]', '', clean_text)  # Dingbats (✓, ✗, etc.)
    clean_text = _re.sub(r'[\u2190-\u21FF]', '', clean_text)  # Arrows
    clean_text = _re.sub(r'[\u2500-\u257F]', '', clean_text)  # Box drawing
    clean_text = clean_text.replace('*', '')  # Asterisks (action markers)
    clean_text = clean_text.replace('~', '')  # Tildes
    clean_text = clean_text.replace('#', '')  # Hash symbols
    clean_text = clean_text.replace('@', ' at ')  # @ sign → spoken form
    clean_text = clean_text.replace('&', ' and ')  # Ampersand → spoken form
    clean_text = clean_text.replace('+', ' plus ')  # Plus sign → spoken form
    clean_text = clean_text.replace('=', ' equals ')  # Equals → spoken form
    clean_text = clean_text.replace('<', '').replace('>', '')  # Angle brackets
    clean_text = clean_text.replace('{', '').replace('}', '')  # Curly braces
    clean_text = clean_text.replace('[', '').replace(']', '')  # Square brackets
    clean_text = clean_text.replace('(', ', ').replace(')', ', ')  # Parentheses → pauses
    clean_text = clean_text.replace('/', ' ')  # Slashes → space
    clean_text = clean_text.replace('\\', ' ')  # Backslashes → space
    clean_text = clean_text.replace('_', ' ')  # Underscores → space
    clean_text = clean_text.replace('…', '...')  # Normalize ellipsis
    clean_text = clean_text.replace('"', '"').replace('"', '"')  # Smart quotes → straight
    clean_text = clean_text.replace(''', "'").replace(''', "'")  # Smart apostrophes
    clean_text = clean_text.replace('"', '')  # Remove remaining quotes (TTS reads them)
    clean_text = clean_text.replace('—', ', ').replace('–', ', ')  # Em/en dashes → comma
    # Remove excessive punctuation ("?!?!" → "?!")
    clean_text = _re.sub(r'([!?])\1+', r'\1', clean_text)
    clean_text = _re.sub(r'[!?]{3,}', '?!', clean_text)
    # Remove excessive dots ("....." → "...")
    clean_text = _re.sub(r'\.{4,}', '...', clean_text)
    # Clean up multiple commas/spaces from substitutions
    clean_text = _re.sub(r',\s*,', ',', clean_text)
    clean_text = _re.sub(r'\s+', ' ', clean_text).strip()

    if DEBUG_SOVITS:
        if clean_text != text:
            print(f"[sovits] ORIGINAL: '{text[:100]}'", file=sys.stderr)
        print(f"[sovits] clean_text: '{clean_text[:100]}'", file=sys.stderr)

    req = {
        "text": clean_text,
        "text_lang": "en",
        "ref_audio_path": ref_audio,
        "prompt_text": prompt_text,
        "prompt_lang": "en",
        "text_split_method": "cut5",
        "speed_factor": speed,
    }

    # Suppress stdout during inference (GPT-SoVITS prints progress bars)
    _real_stdout = sys.stdout
    sys.stdout = sys.stderr
    try:
        chunks = []
        sr = 32000
        for sr_chunk, audio_chunk in pipeline.run(req):
            sr = sr_chunk
            chunks.append(audio_chunk)
    finally:
        sys.stdout = _real_stdout

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

    while True:
        line = sys.stdin.readline()
        if not line:
            break  # stdin closed
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
            err_msg = f"{type(e).__name__}: {e}"
            # Log to stderr for debugging
            print(f"[sovits-subprocess] ERROR: {err_msg}", file=sys.stderr, flush=True)
            print(json.dumps({
                "status": "error",
                "error": err_msg,
                "elapsed": round(elapsed, 3),
            }), flush=True)


if __name__ == "__main__":
    main()
