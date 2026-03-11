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


def _num_to_words(n):
    """Convert integer 0-999 to English words for TTS pronunciation."""
    ones = ['zero','one','two','three','four','five','six','seven','eight','nine',
            'ten','eleven','twelve','thirteen','fourteen','fifteen','sixteen',
            'seventeen','eighteen','nineteen']
    tens_w = ['','','twenty','thirty','forty','fifty','sixty','seventy','eighty','ninety']
    if not isinstance(n, int) or n < 0 or n > 999:
        return str(n)
    if n < 20:
        return ones[n]
    elif n < 100:
        return tens_w[n // 10] + ('' if n % 10 == 0 else ' ' + ones[n % 10])
    else:
        return ones[n // 100] + ' hundred' + ('' if n % 100 == 0 else ' ' + _num_to_words(n % 100))


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


def clean_text_for_tts(text):
    """Clean and normalize text for GPT-SoVITS synthesis."""
    import re as _re
    clean_text = text

    # Strip control characters (newlines, tabs, carriage returns cause garbled output)
    clean_text = clean_text.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')
    # Also strip literal escape sequences that might come from LLM output
    clean_text = clean_text.replace('\\n', ' ').replace('\\r', ' ').replace('\\t', ' ')

    # Remove stage directions / action markers like "(whispers)" "(laughs)" etc.
    clean_text = _re.sub(r'\([^)]*\)', '', clean_text)

    # Remove sound effects / onomatopoeia that GPT-SoVITS cannot pronounce
    _sfx_pattern = r'\b(?:wahoo+|whoosh|splish|splash|boom|boing|brr+|shh+|pfft+|mwah+|ka[\s\-]*ching|ching|whomp|swoosh|zing|thud|clang|bonk|woo+|tick[\s\-]*tock)\b'
    clean_text = _re.sub(_sfx_pattern, '', clean_text, flags=_re.IGNORECASE)

    # Normalize filler words to simple pronounceable forms (keep character, fix length)
    clean_text = _re.sub(r'\bhm+\b', 'Hmm', clean_text, flags=_re.IGNORECASE)
    clean_text = _re.sub(r'\bumm*\b', 'Um', clean_text, flags=_re.IGNORECASE)
    clean_text = _re.sub(r'\buhh*\b', 'Uh', clean_text, flags=_re.IGNORECASE)
    clean_text = _re.sub(r'\bahh+\b', 'Ah', clean_text, flags=_re.IGNORECASE)
    clean_text = _re.sub(r'\bohh+\b', 'Oh', clean_text, flags=_re.IGNORECASE)
    clean_text = _re.sub(r'\ber+m*\b', 'Um', clean_text, flags=_re.IGNORECASE)
    clean_text = _re.sub(r'\bmhm+\b', 'Mm hm', clean_text, flags=_re.IGNORECASE)

    # Strip leading punctuation/whitespace left after word removal
    clean_text = _re.sub(r'^[\s,!?.;:\-]+', '', clean_text)

    # Replace non-standard words with pronounceable alternatives
    # Bowser → Bowzer phonetic (original spelling garbles in short context)
    clean_text = _re.sub(r'\bbowser\b', 'Bowzer', clean_text, flags=_re.IGNORECASE)
    # Goomba → Gumba (simpler phonetic)
    clean_text = _re.sub(r'\bgoomba(s?)\b', r'Gumba\1', clean_text, flags=_re.IGNORECASE)
    clean_text = _re.sub(r'\bbitey\b', 'biting', clean_text, flags=_re.IGNORECASE)
    clean_text = _re.sub(r'\bokie\b', 'okey', clean_text, flags=_re.IGNORECASE)
    clean_text = _re.sub(r'\bdokie\b', 'dokey', clean_text, flags=_re.IGNORECASE)
    # "mine cart" → "minecart" (two words garbles as "my god")
    clean_text = _re.sub(r'\bmine\s+cart\b', 'minecart', clean_text, flags=_re.IGNORECASE)
    clean_text = _re.sub(r'\bnoo+\b', 'no', clean_text, flags=_re.IGNORECASE)
    clean_text = _re.sub(r'\byaa+y+\b', 'yay', clean_text, flags=_re.IGNORECASE)
    clean_text = _re.sub(r'\byay+\b', 'yay', clean_text, flags=_re.IGNORECASE)
    clean_text = _re.sub(r'\bsoo+\b', 'so', clean_text, flags=_re.IGNORECASE)
    clean_text = _re.sub(r'\bhee+lp\b', 'help', clean_text, flags=_re.IGNORECASE)
    clean_text = _re.sub(r'\byippee+\b', 'yippee', clean_text, flags=_re.IGNORECASE)
    # Number fractions: "10/10" → "10 out of 10"
    clean_text = _re.sub(r'(\d+)\s*/\s*(\d+)', r'\1 out of \2', clean_text)

    # Convert percentages to spoken form: "50%" → "fifty percent"
    def _pct_repl(m):
        try:
            n = int(m.group(1))
            return (_num_to_words(n) if 0 <= n <= 999 else m.group(1)) + ' percent'
        except ValueError:
            return m.group(0)
    clean_text = _re.sub(r'(\d+)%', _pct_repl, clean_text)

    # Convert standalone numbers (0-999) to words for better pronunciation
    def _num_repl(m):
        try:
            n = int(m.group(0))
            return _num_to_words(n) if 0 <= n <= 999 else m.group(0)
        except ValueError:
            return m.group(0)
    clean_text = _re.sub(r'\b\d{1,3}\b', _num_repl, clean_text)

    # Collapse repeated characters — vowels to 1, consonants to 2
    # "BAAAAAALLS" → "BALLS", "YAAAAY" → "YAY", "BRRRR" → "BRR"
    clean_text = _re.sub(r'([aeiouAEIOU])\1{2,}', r'\1', clean_text)
    clean_text = _re.sub(r'([^aeiouAEIOU\s\W])\1{2,}', r'\1\1', clean_text)

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

    # Interjection phonetics — must run AFTER hyphen removal & char collapse
    # "Ha He!" → "Hah hey!" (only for the "ha he" combo which is a Mario catchphrase)
    clean_text = _re.sub(r'\bha\s+he\b', 'hah hey', clean_text, flags=_re.IGNORECASE)
    # Don't convert "ha ha ha" to "hah hah hah" — the repeated 'hah' garbles
    # Instead just normalize trailing 'ha' before punctuation to 'hah'
    clean_text = _re.sub(r'\bha\b(?=[!.,?])', 'hah', clean_text, flags=_re.IGNORECASE)

    # Handle "da" interjections AFTER hyphen removal (da-da-daa → da da daa → removed)
    clean_text = _re.sub(r'\bdaa+\b', 'da', clean_text, flags=_re.IGNORECASE)
    clean_text = _re.sub(r'\bda(?:\s+da)+\b', '', clean_text, flags=_re.IGNORECASE)
    # Also remove standalone "da" at end of sentence (leftovers)
    clean_text = _re.sub(r'\bda\b\s*([!.,?])', r'\1', clean_text, flags=_re.IGNORECASE)

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
    clean_text = clean_text.replace('…', ', ')  # Smart ellipsis → comma pause
    clean_text = _re.sub(r'\.{2,}', ', ', clean_text)  # Multi-dots → comma pause (TTS garbles dots)
    clean_text = clean_text.replace('"', '"').replace('"', '"')  # Smart quotes → straight
    clean_text = clean_text.replace(''', "'").replace(''', "'")  # Smart apostrophes
    clean_text = clean_text.replace('"', '')  # Remove remaining quotes (TTS reads them)
    # Remove non-contraction single quotes: 'hello' → hello, but keep don't, it's
    clean_text = _re.sub(r"(?<![a-zA-Z])'|'(?![a-zA-Z])", '', clean_text)
    clean_text = clean_text.replace('—', ', ').replace('–', ', ')  # Em/en dashes → comma
    # Remove excessive punctuation ("?!?!" → "?!")
    clean_text = _re.sub(r'([!?])\1+', r'\1', clean_text)
    clean_text = _re.sub(r'[!?]{3,}', '?!', clean_text)
    # Remove any remaining multi-dots (safety net after earlier dot normalization)
    clean_text = _re.sub(r'\.{2,}', ', ', clean_text)
    # Convert mid-sentence periods to commas (prevents TTS sentence fragmentation)
    # "Line one. Line two. Line three." → "Line one, Line two, Line three."
    # Only convert periods followed by space+uppercase (sentence boundaries mid-text)
    # Keep final period
    clean_text = _re.sub(r'\.\s+(?=[A-Z])', ', ', clean_text)
    # Clean up multiple commas/spaces from substitutions
    clean_text = _re.sub(r',\s*,', ',', clean_text)
    # Strip leading/trailing punctuation left from removals
    clean_text = _re.sub(r'^[\s,!?.;:\-]+', '', clean_text)
    # Remove trailing orphan punctuation (e.g. ", !" left after content removal)
    clean_text = _re.sub(r',\s*[!?.]+\s*$', '', clean_text)
    clean_text = _re.sub(r'[\s,]+$', '', clean_text)
    clean_text = _re.sub(r'\s+', ' ', clean_text).strip()

    # Pad very short phrases — GPT-SoVITS garbles text with < 3 words
    _words = clean_text.split()
    if len(_words) >= 1 and len(_words) <= 2 and len(clean_text) < 20:
        # Use "Well, " for very short phrases (1-2 words)
        clean_text = "Well, " + clean_text[0].lower() + clean_text[1:]
        if DEBUG_SOVITS:
            print(f"[sovits] SHORT PHRASE PADDED: '{clean_text}'", file=sys.stderr)

    # Ensure first character is capitalized after all removals
    if clean_text and clean_text[0].islower():
        clean_text = clean_text[0].upper() + clean_text[1:]

    return clean_text


def synthesize(pipeline, text, ref_audio=None, prompt_text=None, speed=1.0):
    """Generate audio from text using GPT-SoVITS pipeline."""
    import soundfile as sf

    if ref_audio is None:
        ref_audio = DEFAULT_REF_AUDIO
    if prompt_text is None:
        prompt_text = "It's a me Mario"

    clean_text = clean_text_for_tts(text)

    # If text was entirely sound effects/filler, return a short silence file
    if not clean_text or len(clean_text.strip()) == 0:
        if DEBUG_SOVITS:
            print(f"[sovits] ORIGINAL: '{text[:100]}' → EMPTY after cleaning, returning silence", file=sys.stderr)
        silence = np.zeros(16000, dtype=np.float32)  # 0.5s silence at 32kHz
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        silence_path = os.path.join(OUTPUT_DIR, f"silence_{int(time.time()*1000)}.wav")
        sf.write(silence_path, silence, 32000)
        return silence_path, 0.5

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
    
    # Retry mechanism: short/garbled outputs tend to be very brief
    # Estimate minimum expected duration based on word count (~0.15s per word)
    _word_count = len(clean_text.split())
    _min_expected_duration = max(0.25, _word_count * 0.15)
    _best_audio = None
    _best_duration = 0
    _best_sr = 32000
    _max_attempts = 3
    
    for _attempt in range(_max_attempts):
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
            if _attempt < _max_attempts - 1:
                if DEBUG_SOVITS:
                    print(f"[sovits] RETRY {_attempt+1}: no audio chunks", file=sys.stderr)
                continue
            raise RuntimeError("GPT-SoVITS produced no audio chunks after retries")
        
        audio = np.concatenate(chunks)
        duration = len(audio) / sr
        
        if duration > _best_duration:
            _best_audio = audio
            _best_duration = duration
            _best_sr = sr
        
        if duration >= _min_expected_duration:
            break
        
        if DEBUG_SOVITS:
            print(f"[sovits] RETRY {_attempt+1}: audio too short ({duration:.2f}s < {_min_expected_duration:.2f}s)", file=sys.stderr)

    full_audio = _best_audio

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUT_DIR, f"sovits_{int(time.time()*1000)}.wav")
    sf.write(output_path, full_audio, _best_sr)

    duration = len(full_audio) / _best_sr
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
