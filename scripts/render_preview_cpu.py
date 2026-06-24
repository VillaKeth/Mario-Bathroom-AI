"""One-off CPU render of a specific (s2,s1) checkpoint pair — for an early voice
preview WHILE a GPU fine-tune is still running (CPU render = no VRAM contention).

Run (GPT-SoVITS venv):
    gpt_sovits_env/Scripts/python.exe scripts/render_preview_cpu.py <char> <s2.pth> <s1.ckpt> <out.wav> ["line"]
"""
import os
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.join(BASE, "gpt_sovits_repo")
OUT = os.path.join(BASE, "model_comparison")

char = sys.argv[1]
s2 = os.path.join(REPO, "SoVITS_weights_v2", sys.argv[2])
s1 = os.path.join(REPO, "GPT_weights_v2", sys.argv[3])
outp = os.path.join(OUT, sys.argv[4])
line = sys.argv[5] if len(sys.argv) > 5 else (
    "This is a dream, and I should just play along until I wake up, right?")

ref = os.path.join(BASE, "characters", char, "voice", "reference_audio.wav")
rtxt = os.path.join(BASE, "characters", char, "voice", "reference_text.txt")
ref_text = open(rtxt, encoding="utf-8").read().strip() if os.path.exists(rtxt) else ""

print(f"[preview] CPU render | s2={os.path.basename(s2)} s1={os.path.basename(s1)}", flush=True)
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "GPT_SoVITS"))
os.environ.setdefault("PYTHONPATH", os.pathsep.join([os.path.join(REPO, "GPT_SoVITS"), REPO]))
os.chdir(REPO)
from GPT_SoVITS.TTS_infer_pack.TTS import TTS, TTS_Config  # noqa: E402
import soundfile as sf  # noqa: E402

cfg = TTS_Config(os.path.join(REPO, "GPT_SoVITS/configs/tts_infer.yaml"))
cfg.device = "cpu"
cfg.is_half = False
tts = TTS(cfg)
tts.init_t2s_weights(s1)
tts.init_vits_weights(s2)
gen = tts.run({
    "text": line, "text_lang": "en",
    "ref_audio_path": ref, "prompt_text": ref_text, "prompt_lang": "en",
    "top_k": 5, "top_p": 1, "temperature": 1,
    "text_split_method": "cut0", "speed_factor": 1.0,
    "return_fragment": False, "fragment_interval": 0.3,
})
for sr, audio in gen:
    sf.write(outp, audio, sr)
    print(f"[preview] wrote {outp} ({len(audio)/sr:.1f}s)", flush=True)
    break
print("[preview] DONE", flush=True)
