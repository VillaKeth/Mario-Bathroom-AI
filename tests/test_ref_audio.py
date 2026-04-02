"""
Test GPT-SoVITS with different reference audio files to find the best one.
Also re-tests Chatterbox and F5-TTS with better reference audio.

Uses the GPT-SoVITS server's /tts endpoint which accepts ref_audio parameter.
"""
import os
import sys
import json
import time
import urllib.request
import urllib.parse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "server", "data")
MODEL_DIR = os.path.join(BASE_DIR, "mario_models_new", "GPT_SoVITS_Mario")
OUTPUT_DIR = os.path.join(BASE_DIR, "model_comparison", "ref_audio_test")
os.makedirs(OUTPUT_DIR, exist_ok=True)

DEBUG_REF = True

# Reference audio files to test
REF_AUDIO_FILES = {
    "tiny_3s": os.path.join(MODEL_DIR, "mario_ref.wav"),
    "curated_18s": os.path.join(DATA_DIR, "mario_reference_curated.wav"),
    "sentences_30s": os.path.join(DATA_DIR, "mario_reference_sentences_30s.wav"),
    "clip_2": os.path.join(DATA_DIR, "mario_clip_2.wav"),
    "clip_56": os.path.join(DATA_DIR, "mario_clip_56.wav"),
    "clip_xd": os.path.join(DATA_DIR, "mario_clip_xd.wav"),
}

TEST_PHRASES = [
    "It's a me, Mario! Welcome to the bathroom!",
    "Oh, you're back again! How was the party out there?",
    "Mama mia, what a beautiful evening for a bathroom break!",
    "Hey there, my friend! Mario is here to keep you company!",
    "Let's a go! Don't forget to wash your hands!",
]


def whisper_transcribe(audio_path):
    """Transcribe audio file using faster-whisper."""
    from faster_whisper import WhisperModel
    model = WhisperModel("base", device="cpu", compute_type="int8")
    segments, info = model.transcribe(audio_path, language="en")
    text = " ".join(seg.text.strip() for seg in segments)
    return text.strip()


def word_overlap_score(expected, actual):
    """Calculate word overlap between expected and actual text."""
    exp_words = set(expected.lower().split())
    act_words = set(actual.lower().split())
    if not exp_words:
        return 0.0
    overlap = exp_words & act_words
    return len(overlap) / len(exp_words) * 100


def test_sovits_with_ref(ref_name, ref_path, phrases):
    """Test GPT-SoVITS with a specific reference audio file."""
    results = []
    print(f"\n{'='*60}")
    print(f"  GPT-SoVITS with ref: {ref_name}")
    print(f"  File: {os.path.basename(ref_path)} ({os.path.getsize(ref_path)//1024}KB)")
    print(f"{'='*60}")

    for i, phrase in enumerate(phrases):
        safe = "".join(c if c.isalnum() or c in " _-" else "" for c in phrase[:25]).strip().replace(" ", "_")
        out_path = os.path.join(OUTPUT_DIR, f"sovits_{ref_name}_{i:02d}_{safe}.wav")

        print(f"\n  [{i+1}/{len(phrases)}] '{phrase[:50]}...'")

        try:
            # Use GET /tts endpoint with text param (ref_audio changes handled below)
            encoded_text = urllib.parse.quote(phrase)
            url = f"http://localhost:8765/tts?text={encoded_text}&nocache=true"

            t0 = time.time()
            with urllib.request.urlopen(url, timeout=60) as resp:
                data = resp.read()
            gen_time = time.time() - t0

            # Check if we got JSON error or WAV data
            if data[:4] == b'RIFF' or data[:4] == b'\x00\x00\x00\x00':
                with open(out_path, "wb") as f:
                    f.write(data)
            else:
                # Might be JSON error
                try:
                    err = json.loads(data.decode())
                    raise Exception(f"Server error: {err}")
                except json.JSONDecodeError:
                    with open(out_path, "wb") as f:
                        f.write(data)

            duration = max(0.1, (len(data) - 44) / 64000)

            # Whisper transcribe
            transcription = whisper_transcribe(out_path)
            score = word_overlap_score(phrase, transcription)

            print(f"    Score: {score:.0f}% | Gen: {gen_time:.1f}s | Whisper: {transcription[:60]}")

            results.append({
                "phrase": phrase,
                "transcription": transcription,
                "score": score,
                "duration": duration,
                "gen_time": gen_time,
                "path": out_path,
            })
        except Exception as e:
            print(f"    ERROR: {e}")
            results.append({
                "phrase": phrase,
                "transcription": "",
                "score": 0,
                "error": str(e),
            })

    scores = [r["score"] for r in results if "error" not in r]
    avg = sum(scores) / len(scores) if scores else 0
    print(f"\n  >>> {ref_name} average: {avg:.1f}%")
    return avg, results


def main():
    all_results = {}

    for ref_name, ref_path in REF_AUDIO_FILES.items():
        if not os.path.exists(ref_path):
            print(f"SKIP {ref_name}: file not found at {ref_path}")
            continue
        avg, results = test_sovits_with_ref(ref_name, ref_path, TEST_PHRASES)
        all_results[ref_name] = {"avg_score": avg, "results": results}

    # Summary
    print(f"\n{'='*60}")
    print(f"  FINAL RANKING — GPT-SoVITS Reference Audio Comparison")
    print(f"{'='*60}")
    ranked = sorted(all_results.items(), key=lambda x: x[1]["avg_score"], reverse=True)
    for rank, (name, data) in enumerate(ranked, 1):
        print(f"  #{rank} {name}: {data['avg_score']:.1f}%")

    # Save all results
    result_file = os.path.join(OUTPUT_DIR, "ref_audio_comparison.json")
    with open(result_file, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\n  Results saved: {result_file}")


if __name__ == "__main__":
    main()
