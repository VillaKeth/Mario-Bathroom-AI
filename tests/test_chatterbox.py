"""
Chatterbox Turbo TTS adapter — test script for Mario voice cloning.
Uses zero-shot voice cloning from a reference WAV file.

Usage: chatterbox_env\Scripts\python.exe test_chatterbox.py
"""
import os
import sys
import time
import argparse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REF_AUDIO = os.path.join(BASE_DIR, "mario_models_new", "GPT_SoVITS_Mario", "mario_ref.wav")
OUTPUT_DIR = os.path.join(BASE_DIR, "model_comparison")

DEBUG_CB = True

def synthesize_chatterbox(text, ref_audio=None, output_path=None, exaggeration=0.5, cfg_weight=0.5):
    """Synthesize speech using Chatterbox Turbo with Mario reference audio."""
    if ref_audio is None:
        ref_audio = REF_AUDIO
    if output_path is None:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        safe_name = "".join(c if c.isalnum() or c in " _-" else "" for c in text[:40]).strip().replace(" ", "_")
        output_path = os.path.join(OUTPUT_DIR, f"cb_{safe_name}.wav")

    if DEBUG_CB:
        print(f"[DEBUG_CB] synthesize_chatterbox: START text='{text[:60]}...'")

    import torch
    import torchaudio
    from chatterbox.tts import ChatterboxTTS

    device = "cuda" if torch.cuda.is_available() else "cpu"
    if DEBUG_CB:
        print(f"[DEBUG_CB] synthesize_chatterbox: device={device}")

    t0 = time.time()
    model = ChatterboxTTS.from_pretrained(device=device)
    t_load = time.time() - t0
    if DEBUG_CB:
        print(f"[DEBUG_CB] synthesize_chatterbox: model loaded in {t_load:.1f}s")

    t0 = time.time()
    wav = model.generate(
        text=text,
        audio_prompt_path=ref_audio,
        exaggeration=exaggeration,
        cfg_weight=cfg_weight,
    )
    t_gen = time.time() - t0
    if DEBUG_CB:
        print(f"[DEBUG_CB] synthesize_chatterbox: generated in {t_gen:.1f}s")

    torchaudio.save(output_path, wav, model.sr)
    duration = wav.shape[-1] / model.sr
    if DEBUG_CB:
        print(f"[DEBUG_CB] synthesize_chatterbox: saved {output_path} ({duration:.1f}s audio)")

    # Free VRAM
    del model
    del wav
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    import gc
    gc.collect()

    return output_path, duration, t_gen


def main():
    parser = argparse.ArgumentParser(description="Chatterbox Mario TTS test")
    parser.add_argument("--text", default="It's a me, Mario! Welcome to the bathroom, my friend!")
    parser.add_argument("--ref", default=REF_AUDIO)
    parser.add_argument("--output", default=None)
    parser.add_argument("--exaggeration", type=float, default=0.5)
    parser.add_argument("--cfg", type=float, default=0.5)
    args = parser.parse_args()

    print(f"=== Chatterbox Turbo TTS Test ===")
    print(f"Text: {args.text}")
    print(f"Ref:  {args.ref}")

    path, dur, elapsed = synthesize_chatterbox(
        args.text, args.ref, args.output,
        exaggeration=args.exaggeration, cfg_weight=args.cfg
    )
    print(f"\nResult: {path}")
    print(f"Audio duration: {dur:.1f}s")
    print(f"Generation time: {elapsed:.1f}s")
    print(f"Real-time factor: {dur/elapsed:.2f}x" if elapsed > 0 else "")


if __name__ == "__main__":
    main()
