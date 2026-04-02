"""
Direct GPT-SoVITS reference audio comparison — bypasses the server, uses subprocess directly.
Tests multiple reference audio files (all within 3-10s range) against the same 5 phrases.
"""
import os
import sys
import json
import time
import subprocess
import shutil

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "server", "data")
MODEL_DIR = os.path.join(BASE_DIR, "mario_models_new", "GPT_SoVITS_Mario")
OUTPUT_DIR = os.path.join(BASE_DIR, "model_comparison", "ref_audio_test")
SOVITS_PYTHON = os.path.join(BASE_DIR, "gpt_sovits_env", "Scripts", "python.exe")
SOVITS_SERVER = os.path.join(BASE_DIR, "server", "gpt_sovits_server.py")

os.makedirs(OUTPUT_DIR, exist_ok=True)

# Only clips within GPT-SoVITS 3-10s range, with prompt_text matching clip content
REF_AUDIO_FILES = {
    "mario_ref_5s": {
        "path": os.path.join(MODEL_DIR, "mario_ref.wav"),
        "prompt_text": "It's a me Mario",
    },
    "clip_2_3s": {
        "path": os.path.join(DATA_DIR, "mario_clip_2.wav"),
        "prompt_text": "Here we go",
    },
    "clip_10_4s": {
        "path": os.path.join(DATA_DIR, "mario_clip_10.wav"),
        "prompt_text": "Let's a go",
    },
    "clip_51_4s": {
        "path": os.path.join(DATA_DIR, "mario_clip_51.wav"),
        "prompt_text": "Yahoo",
    },
    "clip_6_4s": {
        "path": os.path.join(DATA_DIR, "mario_clip_6.wav"),
        "prompt_text": "Oh yeah",
    },
    "clip_80_4s": {
        "path": os.path.join(DATA_DIR, "mario_clip_80.wav"),
        "prompt_text": "Thank you so much",
    },
    "clip_69_5s": {
        "path": os.path.join(DATA_DIR, "mario_clip_69.wav"),
        "prompt_text": "Welcome, welcome",
    },
    "clip_56_7s": {
        "path": os.path.join(DATA_DIR, "mario_clip_56.wav"),
        "prompt_text": "Mama mia, here we go again",
    },
    "clip_xd_8s": {
        "path": os.path.join(DATA_DIR, "mario_clip_xd.wav"),
        "prompt_text": "Oh boy, oh boy",
    },
}

TEST_PHRASES = [
    "It's a me, Mario! Welcome to the bathroom!",
    "Oh, you're back again! How was the party out there?",
    "Mama mia, what a beautiful evening for a bathroom break!",
    "Hey there, my friend! Mario is here to keep you company!",
    "Let's a go! Don't forget to wash your hands!",
]

# Lazy-load Whisper model once
_whisper_model = None

def whisper_transcribe(audio_path):
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel
        _whisper_model = WhisperModel("base", device="cpu", compute_type="int8")
    segments, info = _whisper_model.transcribe(audio_path, language="en")
    return " ".join(seg.text.strip() for seg in segments).strip()


def word_overlap_score(expected, actual):
    exp_words = set(expected.lower().split())
    act_words = set(actual.lower().split())
    if not exp_words:
        return 0.0
    return len(exp_words & act_words) / len(exp_words) * 100


def start_sovits_subprocess():
    """Start GPT-SoVITS subprocess, consume initial status messages, wait for ready."""
    proc = subprocess.Popen(
        [SOVITS_PYTHON, "-u", SOVITS_SERVER],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        cwd=BASE_DIR,
    )
    
    # Read initial status lines (loading, ready) that the subprocess emits on startup
    print("  Waiting for GPT-SoVITS model to load...")
    for _ in range(60):  # Wait up to 2 minutes
        line = proc.stdout.readline().decode().strip()
        if not line:
            time.sleep(1)
            continue
        try:
            msg = json.loads(line)
            print(f"  [{msg.get('status', '?')}] {msg.get('msg', '')}")
            if msg.get("status") == "ready":
                # Model loaded! Verify with ping
                proc.stdin.write((json.dumps({"cmd": "ping"}) + "\n").encode())
                proc.stdin.flush()
                pong = proc.stdout.readline().decode().strip()
                pong_data = json.loads(pong)
                if pong_data.get("status") == "pong":
                    print("  GPT-SoVITS subprocess ready and verified!")
                    return proc
        except json.JSONDecodeError:
            print(f"  (non-JSON output: {line[:80]})")
        time.sleep(1)
    
    raise Exception("GPT-SoVITS subprocess failed to start within 2 minutes")


def synthesize_via_subprocess(proc, text, ref_audio, prompt_text, output_path):
    """Send synthesis request to subprocess and get result."""
    cmd = json.dumps({
        "text": text,
        "ref_audio": ref_audio,
        "prompt_text": prompt_text,
        "speed": 1.0,
    }) + "\n"
    
    t0 = time.time()
    proc.stdin.write(cmd.encode())
    proc.stdin.flush()
    line = proc.stdout.readline().decode().strip()
    gen_time = time.time() - t0
    
    resp = json.loads(line)
    if resp.get("status") == "ok":
        src = resp["audio_path"]
        shutil.copy2(src, output_path)
        return output_path, resp.get("duration", 0), gen_time
    else:
        raise Exception(f"Synthesis error: {resp.get('error', 'unknown')}")


def test_ref_audio(ref_name, ref_info, proc):
    """Test a specific reference audio file."""
    ref_path = ref_info["path"]
    prompt_text = ref_info["prompt_text"]
    results = []
    print(f"\n{'='*60}")
    print(f"  REF: {ref_name} ({os.path.getsize(ref_path)//1024}KB) prompt='{prompt_text}'")
    print(f"{'='*60}")
    
    for i, phrase in enumerate(TEST_PHRASES):
        safe = "".join(c if c.isalnum() or c in " _-" else "" for c in phrase[:25]).strip().replace(" ", "_")
        out_path = os.path.join(OUTPUT_DIR, f"sovits_{ref_name}_{i:02d}_{safe}.wav")
        
        try:
            path, duration, gen_time = synthesize_via_subprocess(proc, phrase, ref_path, prompt_text, out_path)
            transcription = whisper_transcribe(path)
            score = word_overlap_score(phrase, transcription)
            
            print(f"  [{i+1}/{len(TEST_PHRASES)}] {score:5.0f}% | {gen_time:4.1f}s | {transcription[:55]}")
            results.append({"phrase": phrase, "transcription": transcription, "score": score,
                          "duration": duration, "gen_time": gen_time, "path": out_path})
        except Exception as e:
            print(f"  [{i+1}/{len(TEST_PHRASES)}] ERROR: {e}")
            results.append({"phrase": phrase, "score": 0, "error": str(e)})
    
    scores = [r["score"] for r in results if "error" not in r]
    avg = sum(scores) / len(scores) if scores else 0
    print(f"  >>> Average: {avg:.1f}%")
    return avg, results


def main():
    print("Starting GPT-SoVITS subprocess...")
    proc = start_sovits_subprocess()
    
    all_results = {}
    
    try:
        for ref_name, ref_info in REF_AUDIO_FILES.items():
            if not os.path.exists(ref_info["path"]):
                print(f"SKIP {ref_name}: not found")
                continue
            avg, results = test_ref_audio(ref_name, ref_info, proc)
            all_results[ref_name] = {"avg_score": avg, "results": results}
    finally:
        # Cleanup
        proc.stdin.write(json.dumps({"cmd": "quit"}).encode() + b"\n")
        proc.stdin.flush()
        time.sleep(2)
        proc.kill()
    
    # Final ranking
    print(f"\n{'='*60}")
    print(f"  FINAL RANKING — GPT-SoVITS Reference Audio Comparison")
    print(f"{'='*60}")
    ranked = sorted(all_results.items(), key=lambda x: x[1]["avg_score"], reverse=True)
    for rank, (name, data) in enumerate(ranked, 1):
        bar = "█" * int(data["avg_score"] / 5)
        print(f"  #{rank} {name:20s} {data['avg_score']:5.1f}% {bar}")
    
    # Save
    with open(os.path.join(OUTPUT_DIR, "ref_audio_comparison.json"), "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\n  Results saved to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
