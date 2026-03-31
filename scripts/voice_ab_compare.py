#!/usr/bin/env python3
"""Voice A/B Comparison — synthesize test phrases with every TTS engine side-by-side.

Usage:
    python scripts/voice_ab_compare.py "Its-a me, Mario!" "Wahoo!" "Mama mia!"

Saves WAV files to output/voice_comparison/ and prints a timing table.
"""

import argparse
import os
import sys
import time

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "server"))

DEBUG_VOICE_AB = True

# Default phrases if none provided
DEFAULT_PHRASES = [
    "Its-a me, Mario!",
    "Wahoo!",
    "Mama mia!",
    "Let's-a go!",
    "Here we go!",
]


def _discover_engines() -> list:
    """Discover available TTS engines without requiring a running server."""
    engines = []

    # Edge TTS (pip install edge-tts)
    try:
        import edge_tts  # noqa: F401
        engines.append({
            "name": "edge_tts",
            "synthesize": _synth_edge_tts,
        })
        if DEBUG_VOICE_AB:
            print("  ✓ edge_tts available")
    except ImportError:
        if DEBUG_VOICE_AB:
            print("  ✗ edge_tts not installed")

    # Fish Speech (local server)
    try:
        import requests
        r = requests.get("http://localhost:8080/v1/health", timeout=2)
        if r.status_code == 200:
            engines.append({
                "name": "fish_speech",
                "synthesize": _synth_fish_speech,
            })
            if DEBUG_VOICE_AB:
                print("  ✓ fish_speech available")
        else:
            if DEBUG_VOICE_AB:
                print("  ✗ fish_speech server not responding")
    except Exception:
        if DEBUG_VOICE_AB:
            print("  ✗ fish_speech not reachable")

    # pyttsx3 (offline fallback)
    try:
        import pyttsx3  # noqa: F401
        engines.append({
            "name": "pyttsx3",
            "synthesize": _synth_pyttsx3,
        })
        if DEBUG_VOICE_AB:
            print("  ✓ pyttsx3 available")
    except ImportError:
        if DEBUG_VOICE_AB:
            print("  ✗ pyttsx3 not installed")

    # gTTS (pip install gTTS)
    try:
        from gtts import gTTS  # noqa: F401
        engines.append({
            "name": "gtts",
            "synthesize": _synth_gtts,
        })
        if DEBUG_VOICE_AB:
            print("  ✓ gtts available")
    except ImportError:
        if DEBUG_VOICE_AB:
            print("  ✗ gtts not installed")

    return engines


def _synth_edge_tts(text: str, output_path: str) -> float:
    """Synthesize with Edge TTS. Returns duration in seconds."""
    import asyncio
    import edge_tts

    async def _run():
        communicate = edge_tts.Communicate(text, "en-US-GuyNeural")
        await communicate.save(output_path)

    start = time.perf_counter()
    asyncio.run(_run())
    return time.perf_counter() - start


def _synth_fish_speech(text: str, output_path: str) -> float:
    """Synthesize with Fish Speech API. Returns duration in seconds."""
    import requests

    start = time.perf_counter()
    resp = requests.post(
        "http://localhost:8080/v1/tts",
        json={"text": text},
        timeout=30,
    )
    if resp.status_code == 200:
        with open(output_path, "wb") as f:
            f.write(resp.content)
    else:
        raise RuntimeError(f"Fish Speech returned {resp.status_code}")
    return time.perf_counter() - start


def _synth_pyttsx3(text: str, output_path: str) -> float:
    """Synthesize with pyttsx3. Returns duration in seconds."""
    import pyttsx3

    start = time.perf_counter()
    engine = pyttsx3.init()
    engine.save_to_file(text, output_path)
    engine.runAndWait()
    return time.perf_counter() - start


def _synth_gtts(text: str, output_path: str) -> float:
    """Synthesize with gTTS. Returns duration in seconds (saves as mp3)."""
    from gtts import gTTS

    mp3_path = output_path.replace(".wav", ".mp3")
    start = time.perf_counter()
    tts = gTTS(text=text, lang="en")
    tts.save(mp3_path)
    elapsed = time.perf_counter() - start
    # Rename to expected path for consistency
    if mp3_path != output_path:
        os.rename(mp3_path, output_path)
    return elapsed


def _sanitize_filename(text: str) -> str:
    """Make text safe for filenames."""
    safe = "".join(c if c.isalnum() or c in " -_" else "" for c in text)
    return safe.strip().replace(" ", "_")[:40]


def run_comparison(phrases: list[str]):
    """Run A/B comparison across all available engines."""
    print("\n🎙️  Mario AI — Voice A/B Comparison")
    print("=" * 60)

    print("\nDiscovering TTS engines...")
    engines = _discover_engines()

    if not engines:
        print("\n❌ No TTS engines available. Install at least one:")
        print("   pip install edge-tts")
        print("   pip install pyttsx3")
        print("   pip install gTTS")
        sys.exit(1)

    print(f"\n✅ {len(engines)} engine(s) available: {', '.join(e['name'] for e in engines)}")

    # Create output directory
    output_dir = os.path.join(PROJECT_ROOT, "output", "voice_comparison")
    os.makedirs(output_dir, exist_ok=True)
    print(f"📁 Output: {output_dir}\n")

    # Results table
    results = []  # [(phrase, engine, time_s, filepath, error)]

    for phrase in phrases:
        phrase_slug = _sanitize_filename(phrase)
        print(f"📝 \"{phrase}\"")

        for engine in engines:
            filename = f"{phrase_slug}__{engine['name']}.wav"
            filepath = os.path.join(output_dir, filename)

            try:
                elapsed = engine["synthesize"](phrase, filepath)
                file_size = os.path.getsize(filepath) if os.path.exists(filepath) else 0
                results.append((phrase, engine["name"], elapsed, filepath, None, file_size))
                print(f"   ✓ {engine['name']:15s}  {elapsed:.3f}s  ({file_size // 1024}KB)")
            except Exception as e:
                results.append((phrase, engine["name"], 0, filepath, str(e), 0))
                print(f"   ✗ {engine['name']:15s}  FAILED: {e}")

        print()

    # Print summary table
    print("\n" + "=" * 60)
    print("📊 TIMING COMPARISON")
    print("=" * 60)
    print(f"{'Phrase':<30s} {'Engine':<15s} {'Time':>8s} {'Size':>8s} {'Status':<8s}")
    print("-" * 71)

    for phrase, engine, elapsed, filepath, error, size in results:
        short = phrase[:28] + ".." if len(phrase) > 30 else phrase
        status = "✓ OK" if not error else "✗ FAIL"
        size_str = f"{size // 1024}KB" if size > 0 else "-"
        time_str = f"{elapsed:.3f}s" if not error else "-"
        print(f"{short:<30s} {engine:<15s} {time_str:>8s} {size_str:>8s} {status:<8s}")

    # Compute averages per engine
    print("\n" + "-" * 71)
    print("AVERAGES:")
    engine_times = {}
    for _, engine, elapsed, _, error, _ in results:
        if not error:
            engine_times.setdefault(engine, []).append(elapsed)

    for engine, times in engine_times.items():
        avg = sum(times) / len(times)
        print(f"  {engine:<15s}  avg {avg:.3f}s  ({len(times)} successful)")

    total_files = sum(1 for r in results if not r[4])
    print(f"\n✅ {total_files} files saved to {output_dir}")


def main():
    parser = argparse.ArgumentParser(
        description="Compare TTS engines side-by-side with test phrases"
    )
    parser.add_argument(
        "phrases",
        nargs="*",
        default=DEFAULT_PHRASES,
        help="Test phrases to synthesize (default: built-in Mario phrases)",
    )
    args = parser.parse_args()
    run_comparison(args.phrases)


if __name__ == "__main__":
    main()
