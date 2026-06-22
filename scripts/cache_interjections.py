"""Cache curated GOOD takes of short interjections.

GPT-SoVITS garbles very short / non-lexical utterances ("Hmm", "Oh", "Well",
"So"). This generates each one many times via the LIVE server's /tts, transcribes
with Whisper, keeps the best-matching take, and writes it to the disk cache under
the SERVER'S real key so live synthesis becomes a cache hit with a clean clip.

Run (server must be UP):
    venv/Scripts/python.exe scripts/cache_interjections.py
"""
import os
import sys
import time
import wave
import hashlib
import tempfile
import urllib.request
import urllib.parse
from difflib import SequenceMatcher

SERVER_URL = "http://localhost:8765"
MAX_ATTEMPTS = 8
# Real Mario cache-key params (verified from existing server/data/tts_cache/*.key)
EDGE_VOICE = "en-US-JennyNeural"
RATE = "+15%"
PITCH = "+5Hz"
CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "server", "data", "tts_cache")

# Short interjections Mario uses as fillers/reactions (no trailing punctuation so
# the key text matches the server's light pre-clean).
INTERJECTIONS = [
    "Hmm", "Oh", "Oh no", "Oh yeah", "Oh boy", "Well", "So", "Ah", "Aha",
    "Wow", "Whoa", "Hey", "Yikes", "Aw", "Yeah", "Nope", "Uh oh", "Yay",
]


def clean(t):
    import re
    t = re.sub(r"[^a-z0-9\s]", "", t.lower().strip())
    return re.sub(r"\s+", " ", t).strip()


def wav_dur(b):
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(b); tmp = f.name
        with wave.open(tmp, "rb") as w:
            d = w.getnframes() / float(w.getframerate())
        os.unlink(tmp); return d
    except Exception:
        return 0.0


def save_to_cache(text, wav):
    os.makedirs(CACHE_DIR, exist_ok=True)
    key = f"{EDGE_VOICE}:{text.strip()}:{RATE}:{PITCH}"
    h = hashlib.md5(key.encode()).hexdigest()[:16]
    with open(os.path.join(CACHE_DIR, f"{h}.wav"), "wb") as f:
        f.write(wav)
    with open(os.path.join(CACHE_DIR, f"{h}.key"), "w", encoding="utf-8") as f:
        f.write(key)
    return h


def main():
    print("Loading Whisper (base, cpu)...", flush=True)
    from faster_whisper import WhisperModel
    model = WhisperModel("base", device="cpu", compute_type="int8")
    try:
        urllib.request.urlopen(f"{SERVER_URL}/health", timeout=10)
    except Exception as e:
        sys.exit(f"Server not reachable: {e}")
    try:
        urllib.request.urlopen(f"{SERVER_URL}/precache?pause=true", timeout=5)
    except Exception:
        pass

    print(f"Caching {len(INTERJECTIONS)} interjections (key {EDGE_VOICE}:..:{RATE}:{PITCH})\n", flush=True)
    for i, word in enumerate(INTERJECTIONS, 1):
        best_sim, best_wav, best_tx, best_d = -1.0, None, "", 0.0
        for a in range(1, MAX_ATTEMPTS + 1):
            try:
                wav = urllib.request.urlopen(
                    f"{SERVER_URL}/tts?nocache=1&text={urllib.parse.quote(word)}", timeout=90).read()
            except Exception as e:
                print(f"  {word}: gen error {e}", flush=True); time.sleep(2); continue
            d = wav_dur(wav)
            if d < 0.3 or d > 3.5:    # interjection sanity bounds
                continue
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                f.write(wav); tmp = f.name
            try:
                segs, _ = model.transcribe(tmp, language="en", beam_size=5)
                tx = " ".join(s.text.strip() for s in segs).strip()
            except Exception:
                tx = ""
            finally:
                os.unlink(tmp)
            sim = SequenceMatcher(None, clean(word), clean(tx)).ratio()
            if sim > best_sim:
                best_sim, best_wav, best_tx, best_d = sim, wav, tx, d
            if sim >= 0.9:
                break
            time.sleep(0.2)
        if best_wav:
            save_to_cache(word, best_wav)
            print(f"  {i:2d}. '{word}' -> cached [{best_sim:.0%} {best_d:.1f}s] heard='{best_tx}'", flush=True)
        else:
            print(f"  {i:2d}. '{word}' -> NO usable take", flush=True)

    try:
        urllib.request.urlopen(f"{SERVER_URL}/precache?pause=false", timeout=5)
    except Exception:
        pass
    print("\nDONE.", flush=True)


if __name__ == "__main__":
    main()
