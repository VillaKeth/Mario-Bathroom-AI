"""Test GPT-SoVITS inference with pre-trained Mario model using official repo code."""
import os
import sys
import time
import numpy as np

# Add the official GPT-SoVITS repo to path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_DIR = os.path.join(BASE_DIR, "gpt_sovits_repo")
GPT_SOVITS_DIR = os.path.join(REPO_DIR, "GPT_SoVITS")
sys.path.insert(0, REPO_DIR)
sys.path.insert(0, GPT_SOVITS_DIR)

# Paths
MODEL_DIR = os.path.join(BASE_DIR, "mario_models_new", "GPT_SoVITS_Mario")
SOVITS_PATH = os.path.join(MODEL_DIR, "Mario_e15_s255.pth")
GPT_PATH = os.path.join(MODEL_DIR, "Mario-e20.ckpt")
REF_AUDIO = os.path.join(MODEL_DIR, "mario_ref.wav")
OUTPUT_DIR = os.path.join(BASE_DIR, "voice_tests")

print(f"[DEBUG] SoVITS model: {os.path.exists(SOVITS_PATH)}")
print(f"[DEBUG] GPT model: {os.path.exists(GPT_PATH)}")
print(f"[DEBUG] Ref audio: {os.path.exists(REF_AUDIO)}")

# Create config for the official TTS_infer_pack
import yaml

config_path = os.path.join(MODEL_DIR, "tts_infer.yaml")
config = {
    "custom": {
        "bert_base_path": os.path.join(REPO_DIR, "GPT_SoVITS", "pretrained_models", "chinese-roberta-wwm-ext-large"),
        "cnhuhbert_base_path": os.path.join(REPO_DIR, "GPT_SoVITS", "pretrained_models", "chinese-hubert-base"),
        "device": "cuda",
        "is_half": False,
        "t2s_weights_path": GPT_PATH,
        "version": "v2",
        "vits_weights_path": SOVITS_PATH,
    }
}

with open(config_path, "w") as f:
    yaml.dump(config, f)
print(f"[DEBUG] Config written to {config_path}")

# Try importing the official TTS infer pack
try:
    from TTS_infer_pack.TTS import TTS, TTS_Config
    print("[DEBUG] Official TTS_infer_pack imported OK")
except ImportError as e:
    print(f"[ERROR] Import failed: {e}")
    sys.exit(1)

# Initialize
print("[DEBUG] Creating TTS config...")
tts_config = TTS_Config(config_path)
print("[DEBUG] Creating TTS pipeline...")
tts_pipeline = TTS(tts_config)
print("[DEBUG] TTS pipeline ready!")

# Test phrases
phrases = [
    "It's-a me, Mario! Welcome to the bathroom!",
    "Mama mia! You've been in here a long time!",
    "Let's-a go! Have a great time at the party!",
]

os.makedirs(OUTPUT_DIR, exist_ok=True)
import soundfile as sf

for i, phrase in enumerate(phrases):
    print(f"\n[DEBUG] Generating phrase {i+1}: {phrase}")
    t0 = time.time()
    
    try:
        # Clean text: remove Mario-speak hyphens that confuse phonemes
        clean = phrase.replace("-a ", "a ").replace("-A ", "a ")
        req = {
            "text": clean,
            "text_lang": "en",
            "ref_audio_path": REF_AUDIO,
            "prompt_text": "It's a me Mario",
            "prompt_lang": "en",
            "text_split_method": "cut0",  # No splitting — keeps phrase intact
            "speed_factor": 1.0,
        }
        
        # The official TTS.run returns a generator of (sr, audio_chunk) tuples
        chunks = []
        sr = 32000
        for result in tts_pipeline.run(req):
            sr_chunk, audio_chunk = result
            sr = sr_chunk
            chunks.append(audio_chunk)
        
        if chunks:
            full_audio = np.concatenate(chunks)
            output_path = os.path.join(OUTPUT_DIR, f"GPT_SOVITS_mario_{i+1}.wav")
            sf.write(output_path, full_audio, sr)
            elapsed = time.time() - t0
            size = os.path.getsize(output_path)
            print(f"[DEBUG] Done in {elapsed:.1f}s, size={size} bytes, duration={len(full_audio)/sr:.1f}s")
        
    except Exception as e:
        elapsed = time.time() - t0
        print(f"[ERROR] Failed after {elapsed:.1f}s: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

print("\n[DEBUG] All done!")
