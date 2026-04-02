"""
ElevenLabs Mario Voice Cloning & Testing
1. Clones Mario's voice from our reference audio
2. Tests with the same 5 phrases used for GPT-SoVITS comparison
3. Saves audio + Whisper verification scores
"""
import os
import sys
import json
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "model_comparison", "elevenlabs_test")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Load API key
with open(os.path.join(BASE_DIR, "config.json")) as f:
    API_KEY = os.environ.get("ELEVENLABS_API_KEY") or json.load(f).get("elevenlabs_api_key", "")

from elevenlabs.client import ElevenLabs
from elevenlabs import VoiceSettings

client = ElevenLabs(api_key=API_KEY)

# Reference audio files for voice cloning (use multiple for better quality)
REF_FILES = [
    os.path.join(BASE_DIR, "mario_models_new", "GPT_SoVITS_Mario", "mario_ref.wav"),
    os.path.join(BASE_DIR, "server", "data", "mario_clip_2.wav"),
    os.path.join(BASE_DIR, "server", "data", "mario_clip_51.wav"),
    os.path.join(BASE_DIR, "server", "data", "mario_clip_56.wav"),
    os.path.join(BASE_DIR, "server", "data", "mario_clip_80.wav"),
]

TEST_PHRASES = [
    "It's a me, Mario! Welcome to the bathroom!",
    "Oh, you're back again! How was the party out there?",
    "Mama mia, what a beautiful evening for a bathroom break!",
    "Hey there, my friend! Mario is here to keep you company!",
    "Let's a go! Don't forget to wash your hands!",
]

_whisper_model = None

def whisper_transcribe(audio_path):
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel
        _whisper_model = WhisperModel("base", device="cpu", compute_type="int8")
    segments, _ = _whisper_model.transcribe(audio_path, language="en")
    return " ".join(seg.text.strip() for seg in segments).strip()


def word_overlap_score(expected, actual):
    exp_words = set(expected.lower().split())
    act_words = set(actual.lower().split())
    if not exp_words:
        return 0.0
    return len(exp_words & act_words) / len(exp_words) * 100


def clone_mario_voice():
    """Try to clone or find Mario voice. Falls back to energetic premade voice."""
    print("Setting up ElevenLabs voice...")
    
    # Check existing voices first
    voices = client.voices.get_all()
    for v in voices.voices:
        if "mario" in v.name.lower():
            print(f"  Found existing Mario voice: {v.name} (ID: {v.voice_id})")
            return v.voice_id, v.name
    
    # Try voice cloning (requires paid plan)
    existing_refs = [f for f in REF_FILES if os.path.exists(f)]
    try:
        voice = client.voices.ivc.create(
            name="Mario AI",
            description="Super Mario character voice",
            files=[open(f, "rb") for f in existing_refs],
        )
        print(f"  Voice cloned! ID: {voice.voice_id}")
        return voice.voice_id, "Mario AI (cloned)"
    except Exception as e:
        if "paid_plan_required" in str(e) or "payment_required" in str(e):
            print(f"  Voice cloning requires paid plan — using premade voice for benchmark")
            # Use "Liam - Energetic" as closest personality match
            return "TX3LPaxmHKxFdv7VOQHJ", "Liam (premade, benchmark only)"
        raise


def test_elevenlabs(voice_id):
    """Test ElevenLabs TTS with the cloned Mario voice."""
    results = []
    
    print(f"\n{'='*60}")
    print(f"  ElevenLabs TTS — Voice ID: {voice_id}")
    print(f"{'='*60}")
    
    for i, phrase in enumerate(TEST_PHRASES):
        safe = "".join(c if c.isalnum() or c in " _-" else "" for c in phrase[:25]).strip().replace(" ", "_")
        out_path = os.path.join(OUTPUT_DIR, f"elevenlabs_{i:02d}_{safe}.wav")
        
        try:
            t0 = time.time()
            audio_iter = client.text_to_speech.convert(
                voice_id=voice_id,
                text=phrase,
                model_id="eleven_turbo_v2_5",
                output_format="wav_22050",
                voice_settings=VoiceSettings(
                    stability=0.5,
                    similarity_boost=0.85,
                    style=0.3,
                    use_speaker_boost=True,
                ),
            )
            
            # Collect audio bytes from iterator
            audio_bytes = b"".join(audio_iter)
            gen_time = time.time() - t0
            
            with open(out_path, "wb") as f:
                f.write(audio_bytes)
            
            # Transcribe and score
            transcription = whisper_transcribe(out_path)
            score = word_overlap_score(phrase, transcription)
            
            print(f"  [{i+1}/{len(TEST_PHRASES)}] {score:5.0f}% | {gen_time:4.1f}s | {transcription[:55]}")
            results.append({
                "phrase": phrase, "transcription": transcription, "score": score,
                "gen_time": gen_time, "path": out_path, "size_kb": len(audio_bytes) // 1024,
            })
        except Exception as e:
            print(f"  [{i+1}/{len(TEST_PHRASES)}] ERROR: {e}")
            results.append({"phrase": phrase, "score": 0, "error": str(e)})
    
    scores = [r["score"] for r in results if "error" not in r]
    avg = sum(scores) / len(scores) if scores else 0
    gen_times = [r["gen_time"] for r in results if "error" not in r]
    avg_time = sum(gen_times) / len(gen_times) if gen_times else 0
    
    print(f"\n  >>> Average Score: {avg:.1f}%")
    print(f"  >>> Average Gen Time: {avg_time:.1f}s")
    
    return avg, avg_time, results


def main():
    # Step 1: Get voice
    voice_id, voice_name = clone_mario_voice()
    print(f"  Using voice: {voice_name}")
    
    # Step 2: Test
    avg_score, avg_time, results = test_elevenlabs(voice_id)
    
    # Save results
    output = {
        "voice_id": voice_id,
        "voice_name": voice_name,
        "avg_score": avg_score,
        "avg_gen_time": avg_time,
        "results": results,
    }
    with open(os.path.join(OUTPUT_DIR, "elevenlabs_results.json"), "w") as f:
        json.dump(output, f, indent=2)
    
    # Summary comparison
    print(f"\n{'='*60}")
    print(f"  MODEL COMPARISON SUMMARY")
    print(f"{'='*60}")
    print(f"  GPT-SoVITS (fine-tuned):  71.1% avg | ~3s/phrase | ✅ Sounds like Mario")
    print(f"  ElevenLabs (cloned):      {avg_score:.1f}% avg | {avg_time:.1f}s/phrase | ? Listen to compare")
    print(f"  Chatterbox (zero-shot):   87.9% avg | ~74s/phrase | ❌ Generic voice")
    print(f"  F5-TTS (zero-shot):       87.0% avg | ~43s/phrase | ❌ Generic voice")
    print(f"\n  Audio saved to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
