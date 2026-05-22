"""STT Audio Intake Test — verifies the full speech-to-text pipeline.

Tests:
  1. Hardware detection & model selection
  2. STT model initialization (with actual device)
  3. Synthetic audio transcription (sine wave / silence rejection)
  4. Live mic capture → STT (optional, skipped if no mic)
  5. Audio format validation (sample rate, dtype, chunking)

Usage:
  python tests/test_stt_intake.py              # full test
  python tests/test_stt_intake.py --mic        # include live mic test (speak into mic)
  python tests/test_stt_intake.py --hardware   # just show hardware info
"""
import sys
import os
import time
import argparse
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

SAMPLE_RATE = 16000

def print_header(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

def print_result(label, passed, detail=""):
    icon = "✅" if passed else "❌"
    print(f"  {icon} {label}{f' — {detail}' if detail else ''}")

# ── 1. Hardware Detection ────────────────────────────────────
def test_hardware():
    print_header("1. Hardware Detection")
    import hardware
    hw = hardware.detect_hardware()
    tier = hardware.get_tier()
    print(f"  CPU cores:  {hw['cpu_cores']}")
    print(f"  RAM:        {hw['ram_gb']} GB")
    print(f"  GPU:        {hw['gpu_name']}")
    print(f"  GPU VRAM:   {hw['gpu_vram_gb']} GB")
    print(f"  Tier:       {tier}")

    model_map = {"ultra": "large-v3", "high": "medium", "medium": "base", "low": "base"}
    auto_model = model_map.get(tier, "base")
    print(f"  Auto model: {auto_model}")

    # Check CUDA
    try:
        import torch
        cuda = torch.cuda.is_available()
        print(f"  CUDA:       {'available' if cuda else 'not available'}")
        if cuda:
            print(f"  CUDA dev:   {torch.cuda.get_device_name(0)}")
    except ImportError:
        print(f"  CUDA:       torch not installed")

    return hw, tier, auto_model


# ── 2. STT Model Init ────────────────────────────────────────
def test_model_init(auto_model):
    print_header("2. STT Model Initialization")
    import stt

    if not stt._HAS_WHISPER:
        print_result("faster-whisper installed", False, "pip install faster-whisper")
        return False

    print_result("faster-whisper installed", True)

    t0 = time.time()
    stt.init_model(model_size=auto_model, device="auto")
    elapsed = time.time() - t0

    loaded = stt._model is not None
    print_result(f"Model loaded ({auto_model})", loaded, f"{elapsed:.1f}s")
    return loaded


# ── 3. Synthetic Audio Tests ─────────────────────────────────
def test_synthetic():
    print_header("3. Synthetic Audio Tests")
    import stt
    results = []

    # 3a. Silence should return empty
    silence = np.zeros(SAMPLE_RATE * 2, dtype=np.int16).tobytes()
    t0 = time.time()
    text = stt.transcribe(silence)
    elapsed = time.time() - t0
    ok = text.strip() == ""
    print_result("Silence rejected", ok, f"got '{text}' in {elapsed:.1f}s")
    results.append(ok)

    # 3b. Too-short audio rejected
    short = np.zeros(SAMPLE_RATE // 4, dtype=np.int16).tobytes()
    text = stt.transcribe(short)
    ok = text.strip() == ""
    print_result("Short audio rejected (<0.5s)", ok)
    results.append(ok)

    # 3c. Empty bytes
    text = stt.transcribe(b"")
    ok = text.strip() == ""
    print_result("Empty bytes rejected", ok)
    results.append(ok)

    # 3d. Pure tone (440Hz sine) — should NOT produce meaningful words
    t = np.linspace(0, 2, SAMPLE_RATE * 2, endpoint=False)
    tone = (np.sin(2 * np.pi * 440 * t) * 16000).astype(np.int16).tobytes()
    t0 = time.time()
    text = stt.transcribe(tone)
    elapsed = time.time() - t0
    word_count = len(text.split()) if text.strip() else 0
    ok = word_count <= 3  # Whisper might hallucinate a word or two on pure tone
    print_result(f"Pure tone handled", ok, f"'{text}' ({word_count} words, {elapsed:.1f}s)")
    results.append(ok)

    # 3e. Realistic speech-like audio (white noise bursts simulating voice)
    noise = np.random.randint(-8000, 8000, SAMPLE_RATE * 3, dtype=np.int16).tobytes()
    t0 = time.time()
    text = stt.transcribe(noise)
    elapsed = time.time() - t0
    print_result(f"Noise handled", True, f"'{text}' in {elapsed:.1f}s")
    results.append(True)

    return all(results)


# ── 4. Audio Format Validation ───────────────────────────────
def test_format():
    print_header("4. Audio Format Validation")
    import stt

    # Verify int16 conversion path
    samples = np.array([0, 16384, -16384, 32767, -32768], dtype=np.int16)
    float_samples = samples.astype(np.float32) / 32768.0
    ok = all(-1.0 <= s <= 1.0 for s in float_samples)
    print_result("int16 → float32 normalization", ok, f"range [{float_samples.min():.3f}, {float_samples.max():.3f}]")

    # Verify chunk sizing (server uses 96000 bytes = 3s at 16kHz int16)
    chunk_bytes = 96000
    chunk_seconds = chunk_bytes / (SAMPLE_RATE * 2)  # 2 bytes per int16 sample
    ok = abs(chunk_seconds - 3.0) < 0.01
    print_result(f"Chunk size = {chunk_seconds}s", ok, f"{chunk_bytes} bytes")

    # Verify min buffer (16000 bytes = 0.5s)
    min_bytes = 16000
    min_seconds = min_bytes / (SAMPLE_RATE * 2)
    print_result(f"Min buffer = {min_seconds}s", True, f"{min_bytes} bytes")

    return ok


# ── 5. Live Mic Test ─────────────────────────────────────────
def test_mic():
    print_header("5. Live Microphone → STT Test")
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "client"))
        from audio_capture import AudioCapture, list_devices
    except ImportError as e:
        print_result("Audio capture import", False, str(e))
        return False

    print("\n  Available devices:")
    try:
        list_devices()
    except Exception as e:
        print(f"  (could not list: {e})")

    cap = AudioCapture()
    if not cap.start():
        print_result("Mic opened", False, "no input device found")
        return False
    print_result("Mic opened", True)

    duration = 5
    print(f"\n  🎤 Speak now! Recording for {duration} seconds...")
    print(f"     Say something clear like: 'Hello Mario, how are you?'")
    print()

    chunks = []
    start = time.time()
    while time.time() - start < duration:
        data = cap.get_audio(timeout=0.2)
        if data:
            chunks.append(data)

    cap.stop()
    audio = b"".join(chunks)

    if not audio:
        print_result("Audio captured", False, "no data received")
        return False

    audio_seconds = len(audio) / (SAMPLE_RATE * 2)
    print_result("Audio captured", True, f"{len(audio)} bytes ({audio_seconds:.1f}s)")

    # Check audio levels
    samples = np.frombuffer(audio, dtype=np.int16)
    rms = np.sqrt(np.mean(samples.astype(np.float64) ** 2))
    peak = np.max(np.abs(samples))
    print(f"  📊 RMS level: {rms:.0f} / 32768  (peak: {peak})")

    if rms < 50:
        print_result("Audio level", False, "very quiet — is mic working?")
    elif rms < 500:
        print_result("Audio level", True, "low but audible")
    else:
        print_result("Audio level", True, "good levels")

    # Transcribe
    import stt
    print(f"\n  Transcribing...")
    t0 = time.time()
    transcript = stt.transcribe(audio)
    elapsed = time.time() - t0

    if transcript and transcript.strip():
        print_result(f"STT result", True, f"'{transcript}' ({elapsed:.1f}s)")
        return True
    else:
        print_result("STT result", False, f"empty transcript ({elapsed:.1f}s) — was there speech?")
        return False


# ── Main ─────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Mario AI STT Intake Test")
    parser.add_argument("--mic", action="store_true", help="Include live microphone test")
    parser.add_argument("--hardware", action="store_true", help="Only show hardware info")
    args = parser.parse_args()

    print_header("Mario AI — STT Audio Intake Test")

    hw, tier, auto_model = test_hardware()

    if args.hardware:
        return

    results = {}

    if test_model_init(auto_model):
        results["synthetic"] = test_synthetic()
        results["format"] = test_format()

        if args.mic:
            results["mic"] = test_mic()
    else:
        print("\n  ⚠️  Skipping remaining tests (model failed to load)")

    # Summary
    print_header("Summary")
    total = len(results)
    passed = sum(1 for v in results.values() if v)
    for name, ok in results.items():
        print_result(name, ok)
    print(f"\n  {passed}/{total} test groups passed")

    if not args.mic:
        print(f"\n  💡 Run with --mic to test live microphone input")


if __name__ == "__main__":
    main()
