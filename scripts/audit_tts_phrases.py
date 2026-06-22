"""Audit TTS pronunciation of a list of phrases: synthesize each via the live
server, transcribe with Whisper, print what was 'heard' so gross garbling shows.

Run (server UP): venv/Scripts/python.exe scripts/audit_tts_phrases.py
"""
import os
import sys
import time
import tempfile
import urllib.request
import urllib.parse

SERVER_URL = "http://localhost:8765"

PHRASES = [
    # -a suffix (Mario signature)
    "It's-a me, Mario!",
    "Let's-a go, my friend!",
    "That's-a so funny!",
    "I'm-a the king of this party!",
    "What's-a your name?",
    "You're-a doing great!",
    "Time to wash-a your hands!",
    "This-a is the best party ever!",
    "The water is-a cold!",
    "You like-a the music?",
    # double-apostrophe content bug
    "I''m-a ready to play!",
    "That''s-a great idea!",
    # 'cause
    "I'm happy 'cause it's a party!",
    "Just 'cause I said so!",
    "'cause you're awesome!",
    # hyphens
    "Grab a power-up!",
    "You're the first-place winner!",
    "It's a warp-pipe!",
    "Super-duper job!",
]


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

    print(f"\nAuditing {len(PHRASES)} phrases (phrase  ->  heard):\n", flush=True)
    for p in PHRASES:
        try:
            wav = urllib.request.urlopen(
                f"{SERVER_URL}/tts?nocache=1&text={urllib.parse.quote(p)}", timeout=90).read()
        except Exception as e:
            print(f"  GEN ERROR '{p}': {e}", flush=True); continue
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(wav); tmp = f.name
        try:
            segs, _ = model.transcribe(tmp, language="en", beam_size=5)
            heard = " ".join(s.text.strip() for s in segs).strip()
        except Exception as e:
            heard = f"TRANSCRIBE_ERROR: {e}"
        finally:
            os.unlink(tmp)
        print(f"  {p:40s} -> {heard!r}", flush=True)
        time.sleep(0.3)

    try:
        urllib.request.urlopen(f"{SERVER_URL}/precache?pause=false", timeout=5)
    except Exception:
        pass
    print("\nDONE.", flush=True)


if __name__ == "__main__":
    main()
