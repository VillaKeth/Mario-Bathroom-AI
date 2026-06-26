"""Resume a killed GPT-SoVITS fine-tune at the s1 (GPT) stage only.

Use when s2 (SoVITS) already finished (logs/<char>/ has the 1a/1b/1c feature
artifacts + SoVITS_weights_v2/<char>_e*.pth exists) but s1 didn't complete.
Skips re-extraction + s2 (saves ~3 hr), runs just s1, then collects weights to
mario_models_new/GPT_SoVITS_<Char>/. Mirrors scripts/fine_tune_voice.py s1+collect.

Run detached so the harness can't reap it:
    Start-Process gpt_sovits_env\\Scripts\\python.exe -ArgumentList '-u','scripts/resume_finetune_s1.py','rudi'

Env overrides: FT_S1_EPOCHS, FT_BATCH, FT_SAVE_EVERY, FT_IS_HALF, FT_GPU.
"""
import os, shutil, subprocess, sys, yaml

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.join(BASE, "gpt_sovits_repo")
PYEXE = sys.executable  # must be the gpt_sovits_env python
CHAR_ROOT = os.path.join(BASE, "characters")

char = sys.argv[1] if len(sys.argv) > 1 else "rudi"
exp = char
VERSION = "v2"
IS_HALF = os.environ.get("FT_IS_HALF", "False")
GPU = os.environ.get("FT_GPU", "0")
S1_EPOCHS = int(os.environ.get("FT_S1_EPOCHS", "15"))
BATCH = int(os.environ.get("FT_BATCH", "2"))
SAVE_EVERY = int(os.environ.get("FT_SAVE_EVERY", "2"))  # frequent vs re-kill
S1 = "GPT_SoVITS/pretrained_models/gsv-v2final-pretrained/s1bert25hz-5kh-longer-epoch=12-step=369668.ckpt"
opt_dir = f"logs/{exp}"


def run(cmd, env):
    print(f"\n$ {cmd}", flush=True)
    full = dict(os.environ); full.update(env)
    full["PYTHONIOENCODING"] = "utf-8"
    pp = os.pathsep.join([os.path.join(REPO, "GPT_SoVITS"), REPO])
    full["PYTHONPATH"] = pp + (os.pathsep + full["PYTHONPATH"] if full.get("PYTHONPATH") else "")
    p = subprocess.run(cmd, shell=True, cwd=REPO, env=full)
    if p.returncode != 0:
        raise SystemExit(f"[resume] stage failed (exit {p.returncode}): {cmd}")


for need in ("2-name2text.txt", "6-name2semantic.tsv"):
    p = os.path.join(REPO, opt_dir, need)
    if not os.path.exists(p):
        raise SystemExit(f"[resume] missing {p} — features gone; run full fine_tune_voice.py instead")

half = IS_HALF.lower() == "true"
s2_batch = BATCH if half else max(1, BATCH // 2)
base_env = {"is_half": IS_HALF}
for d in (f"logs/{exp}/logs_s1_{VERSION}", "GPT_weights_v2", "TEMP"):
    os.makedirs(os.path.join(REPO, d), exist_ok=True)

print(f"[resume] {char}: s1 GPT-only | epochs={S1_EPOCHS} batch={s2_batch} save_every={SAVE_EVERY}", flush=True)

with open(os.path.join(REPO, "GPT_SoVITS/configs/s1longer-v2.yaml")) as f:
    s1 = yaml.safe_load(f)
s1["train"]["precision"] = "32" if not half else "16-mixed"
s1["train"]["batch_size"] = s2_batch
s1["train"]["epochs"] = S1_EPOCHS
s1["pretrained_s1"] = S1
s1["train"]["save_every_n_epoch"] = SAVE_EVERY
s1["train"]["if_save_every_weights"] = True
s1["train"]["if_save_latest"] = True
s1["train"]["if_dpo"] = False
s1["train"]["half_weights_save_dir"] = "GPT_weights_v2"
s1["train"]["exp_name"] = exp
s1["train_semantic_path"] = f"{opt_dir}/6-name2semantic.tsv"
s1["train_phoneme_path"] = f"{opt_dir}/2-name2text.txt"
s1["output_dir"] = f"{opt_dir}/logs_s1_{VERSION}"
tmp_s1 = os.path.join(REPO, "TEMP", "tmp_s1.yaml")
with open(tmp_s1, "w") as f:
    yaml.dump(s1, f, default_flow_style=False)
run(f'"{PYEXE}" -s GPT_SoVITS/s1_train.py --config_file "TEMP/tmp_s1.yaml"',
    {**base_env, "_CUDA_VISIBLE_DEVICES": GPU, "hz": "25hz"})

out = os.path.join(BASE, "mario_models_new", f"GPT_SoVITS_{char.capitalize()}")
os.makedirs(out, exist_ok=True)

def newest(folder, ext):
    d = os.path.join(REPO, folder)
    if not os.path.isdir(d):
        return None
    cands = [os.path.join(d, f) for f in os.listdir(d) if f.endswith(ext) and exp.lower() in f.lower()]
    return max(cands, key=os.path.getmtime) if cands else None

g = newest("SoVITS_weights_v2", ".pth")
a = newest("GPT_weights_v2", ".ckpt")
print(f"[resume] sovits weight: {g}\n[resume] gpt weight: {a}", flush=True)
if g:
    shutil.copy(g, os.path.join(out, os.path.basename(g)))
if a:
    shutil.copy(a, os.path.join(out, os.path.basename(a)))
ref = os.path.join(CHAR_ROOT, char, "voice", "reference_audio.wav")
if os.path.exists(ref):
    shutil.copy(ref, os.path.join(out, f"{char}_ref.wav"))
print(f"[resume] DONE -> {out}\n[resume] contents: {os.listdir(out)}", flush=True)
