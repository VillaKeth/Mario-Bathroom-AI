"""
F5-TTS adapter — test script for Mario voice cloning.
Uses diffusion-based zero-shot voice cloning from a reference WAV file.

Usage: f5tts_env\Scripts\python.exe test_f5tts.py
"""
import os
import sys
import time
import argparse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REF_AUDIO = os.path.join(BASE_DIR, "mario_models_new", "GPT_SoVITS_Mario", "mario_ref.wav")
OUTPUT_DIR = os.path.join(BASE_DIR, "model_comparison")

DEBUG_F5 = True

# Reference text that matches the mario_ref.wav content
# This helps F5-TTS understand the speaker's style
REF_TEXT = "It's a me Mario! Wahoo! Let's a go!"


def synthesize_f5tts(text, ref_audio=None, ref_text=None, output_path=None):
    """Synthesize speech using F5-TTS with Mario reference audio."""
    if ref_audio is None:
        ref_audio = REF_AUDIO
    if ref_text is None:
        ref_text = REF_TEXT
    if output_path is None:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        safe_name = "".join(c if c.isalnum() or c in " _-" else "" for c in text[:40]).strip().replace(" ", "_")
        output_path = os.path.join(OUTPUT_DIR, f"f5_{safe_name}.wav")

    if DEBUG_F5:
        print(f"[DEBUG_F5] synthesize_f5tts: START text='{text[:60]}...'")

    from f5_tts.api import F5TTS

    t0 = time.time()
    model = F5TTS()
    t_load = time.time() - t0
    if DEBUG_F5:
        print(f"[DEBUG_F5] synthesize_f5tts: model loaded in {t_load:.1f}s")

    t0 = time.time()
    wav, sr, _ = model.infer(
        ref_file=ref_audio,
        ref_text=ref_text,
        gen_text=text,
        file_wave=output_path,
    )
    t_gen = time.time() - t0
    if DEBUG_F5:
        print(f"[DEBUG_F5] synthesize_f5tts: generated in {t_gen:.1f}s")

    # Calculate duration
    if wav is not None:
        duration = len(wav) / sr if hasattr(wav, '__len__') else 0
    else:
        # Read from file
        import soundfile as sf
        data, sr2 = sf.read(output_path)
        duration = len(data) / sr2

    if DEBUG_F5:
        print(f"[DEBUG_F5] synthesize_f5tts: saved {output_path} ({duration:.1f}s audio)")

    # Free VRAM
    del model
    import torch
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    import gc
    gc.collect()

    return output_path, duration, t_gen


def main():
    parser = argparse.ArgumentParser(description="F5-TTS Mario TTS test")
    parser.add_argument("--text", default="It's a me, Mario! Welcome to the bathroom, my friend!")
    parser.add_argument("--ref", default=REF_AUDIO)
    parser.add_argument("--ref-text", default=REF_TEXT)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    print(f"=== F5-TTS Test ===")
    print(f"Text: {args.text}")
    print(f"Ref:  {args.ref}")

    path, dur, elapsed = synthesize_f5tts(args.text, args.ref, args.ref_text, args.output)
    print(f"\nResult: {path}")
    print(f"Audio duration: {dur:.1f}s")
    print(f"Generation time: {elapsed:.1f}s")
    print(f"Real-time factor: {dur/elapsed:.2f}x" if elapsed > 0 else "")


if __name__ == "__main__":
    main()
