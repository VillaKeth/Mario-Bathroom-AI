"""Fish Speech (v1.5.1) zero-shot synthesis — runs INSIDE fish_speech_env.

Clones a voice from a reference clip (+ its transcript) with no training. Called
as a subprocess by scripts/voice_compare.py and the runtime. Mirrors the official
v1.5.1 tools/run_webui.py + tools/webui/inference.py usage. Uses the non-gated
fish-speech-1.5 checkpoint (firefly decoder).

Run with fish_speech_env python:
    fish_speech_env/Scripts/python.exe scripts/fish_synth.py \
        --ref ref.wav --ref-text "transcript" --text "hello" --out out.wav
"""
import argparse
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CKPT = os.path.join(BASE, "fish_speech_ckpts")
DECODER = os.path.join(CKPT, "firefly-gan-vq-fsq-8x1024-21hz-generator.pth")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", required=True)
    ap.add_argument("--ref-text", default="")
    ap.add_argument("--text", required=True)
    ap.add_argument("--out", required=True)
    # Expressiveness knobs. Higher temperature/top_p = more pitch + prosody
    # variance (less flat); repetition_penalty curbs droning. Defaults tuned for
    # a livelier delivery than the stock 0.7/0.7.
    ap.add_argument("--temperature", type=float, default=0.9)
    ap.add_argument("--top-p", type=float, default=0.85)
    ap.add_argument("--repetition-penalty", type=float, default=1.4)
    args = ap.parse_args()

    if not os.path.exists(DECODER):
        sys.exit(f"[fish] checkpoint missing: {DECODER}. Run scripts/setup_fish_speech.py")

    import torch
    from fish_speech.inference_engine import TTSInferenceEngine
    from fish_speech.models.text2semantic.inference import launch_thread_safe_queue
    from fish_speech.models.vqgan.inference import load_model as load_decoder_model
    from fish_speech.utils.schema import ServeTTSRequest, ServeReferenceAudio

    device = "cuda" if torch.cuda.is_available() else "cpu"
    precision = torch.half if device == "cuda" else torch.float32
    print(f"[fish] device={device}", file=sys.stderr)

    llama_queue = launch_thread_safe_queue(
        checkpoint_path=CKPT, device=device, precision=precision, compile=False)
    decoder = load_decoder_model(
        config_name="firefly_gan_vq", checkpoint_path=DECODER, device=device)
    engine = TTSInferenceEngine(
        llama_queue=llama_queue, decoder_model=decoder, compile=False, precision=precision)

    with open(args.ref, "rb") as f:
        ref_bytes = f.read()

    req = ServeTTSRequest(
        text=args.text,
        references=[ServeReferenceAudio(audio=ref_bytes, text=args.ref_text)],
        reference_id=None,
        max_new_tokens=1024, chunk_length=200,
        top_p=args.top_p, repetition_penalty=args.repetition_penalty,
        temperature=args.temperature, format="wav",
    )

    audio = None
    for result in engine.inference(req):
        if result.code == "final":
            audio = result.audio
            break
        if result.code == "error":
            sys.exit(f"[fish] inference error: {result.error}")
    if audio is None:
        sys.exit("[fish] no audio generated")

    sample_rate, data = audio
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    import soundfile as sf
    sf.write(args.out, data, sample_rate)
    print(args.out)


if __name__ == "__main__":
    main()
