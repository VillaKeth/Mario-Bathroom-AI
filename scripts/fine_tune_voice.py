"""Headless GPT-SoVITS v2 fine-tune for a character.

Replicates the GPT-SoVITS WebUI training flow (feature extraction 1a/1b/1c -> s2
SoVITS train -> s1 GPT train) without the Gradio UI, then copies the resulting
weights into mario_models_new/GPT_SoVITS_<Char>/ where tts._resolve_sovits_models
auto-discovers them.

Prereqs: scripts/build_voice_dataset.py already produced
    characters/<char>/voice/dataset/<char>.list

Run (uses the GPT-SoVITS venv which has torch+cuda):
    gpt_sovits_env/Scripts/python.exe scripts/fine_tune_voice.py jax

Tuned for a 4GB GPU: fp32 (P1000 lacks fast fp16), batch_size 1, few epochs.
Override via env: FT_S2_EPOCHS, FT_S1_EPOCHS, FT_BATCH, FT_IS_HALF, FT_GPU.
"""
import json
import os
import shutil
import subprocess
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.join(BASE, "gpt_sovits_repo")
PYEXE = sys.executable  # must be gpt_sovits_env python

VERSION = "v2"
IS_HALF = os.environ.get("FT_IS_HALF", "False")  # P1000: fp32
GPU = os.environ.get("FT_GPU", "0")
S2_EPOCHS = int(os.environ.get("FT_S2_EPOCHS", "8"))
S1_EPOCHS = int(os.environ.get("FT_S1_EPOCHS", "15"))
BATCH = int(os.environ.get("FT_BATCH", "2"))  # halved to 1 under fp32
SAVE_EVERY = int(os.environ.get("FT_SAVE_EVERY", "4"))

BERT = "GPT_SoVITS/pretrained_models/chinese-roberta-wwm-ext-large"
CNHUBERT = "GPT_SoVITS/pretrained_models/chinese-hubert-base"
S2G = "GPT_SoVITS/pretrained_models/gsv-v2final-pretrained/s2G2333k.pth"
S2D = "GPT_SoVITS/pretrained_models/gsv-v2final-pretrained/s2D2333k.pth"
S1 = "GPT_SoVITS/pretrained_models/gsv-v2final-pretrained/s1bert25hz-5kh-longer-epoch=12-step=369668.ckpt"


def run(cmd, env):
    print(f"\n$ {cmd}", flush=True)
    full = dict(os.environ)
    full.update(env)
    full["PYTHONIOENCODING"] = "utf-8"
    # The prepare/train scripts do bare `from text...`, `from module...`,
    # `from tools...` — those packages live under GPT_SoVITS/, so it (and the
    # repo root) must be importable.
    pp = os.pathsep.join([os.path.join(REPO, "GPT_SoVITS"), REPO])
    full["PYTHONPATH"] = pp + (os.pathsep + full["PYTHONPATH"] if full.get("PYTHONPATH") else "")
    p = subprocess.run(cmd, shell=True, cwd=REPO, env=full)
    if p.returncode != 0:
        raise SystemExit(f"[ft] stage failed (exit {p.returncode}): {cmd}")


def main():
    char = sys.argv[1] if len(sys.argv) > 1 else "jax"
    exp = char  # exp_name
    list_path = os.path.join(BASE, "characters", char, "voice", "dataset", f"{char}.list")
    if not os.path.exists(list_path):
        raise SystemExit(f"[ft] dataset list missing: {list_path} — run build_voice_dataset.py first")
    opt_dir = f"logs/{exp}"  # relative to REPO
    os.makedirs(os.path.join(REPO, opt_dir), exist_ok=True)
    # The webui creates these checkpoint dirs before training; s2_train/s1_train
    # save into them via shutil.move and crash if they don't exist.
    for d in (f"logs/{exp}/logs_s2_{VERSION}", f"logs/{exp}/logs_s1",
              f"logs/{exp}/logs_s1_{VERSION}", "SoVITS_weights_v2", "GPT_weights_v2", "TEMP"):
        os.makedirs(os.path.join(REPO, d), exist_ok=True)
    base_env = {"is_half": IS_HALF}

    print(f"[ft] {char}: v2 fine-tune | half={IS_HALF} batch={BATCH} "
          f"s2_epochs={S2_EPOCHS} s1_epochs={S1_EPOCHS} gpu={GPU}", flush=True)

    # ---- 1a: text/BERT features ----
    run(f'"{PYEXE}" -s GPT_SoVITS/prepare_datasets/1-get-text.py', {
        **base_env, "inp_text": list_path, "inp_wav_dir": "", "exp_name": exp,
        "opt_dir": opt_dir, "bert_pretrained_dir": BERT,
        "i_part": "0", "all_parts": "1", "_CUDA_VISIBLE_DEVICES": GPU, "version": VERSION,
    })
    # merge part file
    part = os.path.join(REPO, opt_dir, "2-name2text-0.txt")
    final = os.path.join(REPO, opt_dir, "2-name2text.txt")
    if os.path.exists(part):
        shutil.move(part, final)

    # ---- 1b: HuBERT + wav32k ----
    run(f'"{PYEXE}" -s GPT_SoVITS/prepare_datasets/2-get-hubert-wav32k.py', {
        **base_env, "inp_text": list_path, "inp_wav_dir": "", "exp_name": exp,
        "opt_dir": opt_dir, "cnhubert_base_dir": CNHUBERT,
        "i_part": "0", "all_parts": "1", "_CUDA_VISIBLE_DEVICES": GPU,
    })

    # ---- 1c: semantic tokens ----
    run(f'"{PYEXE}" -s GPT_SoVITS/prepare_datasets/3-get-semantic.py', {
        **base_env, "inp_text": list_path, "exp_name": exp, "opt_dir": opt_dir,
        "pretrained_s2G": S2G, "s2config_path": "GPT_SoVITS/configs/s2.json",
        "i_part": "0", "all_parts": "1", "_CUDA_VISIBLE_DEVICES": GPU,
    })
    sem_part = os.path.join(REPO, opt_dir, "6-name2semantic-0.tsv")
    sem_final = os.path.join(REPO, opt_dir, "6-name2semantic.tsv")
    if os.path.exists(sem_part):
        with open(sem_part, encoding="utf8") as f:
            body = f.read().strip("\n")
        with open(sem_final, "w", encoding="utf8") as f:
            f.write("item_name\tsemantic_audio\n" + body + "\n")
        os.remove(sem_part)

    half = IS_HALF.lower() == "true"
    s2_batch = BATCH if half else max(1, BATCH // 2)

    # ---- s2: SoVITS train ----
    with open(os.path.join(REPO, "GPT_SoVITS/configs/s2.json")) as f:
        s2 = json.load(f)
    s2["train"]["fp16_run"] = half
    s2["train"]["batch_size"] = s2_batch
    s2["train"]["epochs"] = S2_EPOCHS
    s2["train"]["pretrained_s2G"] = S2G
    s2["train"]["pretrained_s2D"] = S2D
    s2["train"]["if_save_latest"] = True
    s2["train"]["if_save_every_weights"] = True
    s2["train"]["save_every_epoch"] = SAVE_EVERY
    s2["train"]["gpu_numbers"] = GPU
    s2["train"]["text_low_lr_rate"] = 0.4
    s2["model"]["version"] = VERSION
    s2["data"]["exp_dir"] = s2["s2_ckpt_dir"] = opt_dir
    s2["save_weight_dir"] = "SoVITS_weights_v2"
    s2["name"] = exp
    s2["version"] = VERSION
    os.makedirs(os.path.join(REPO, "TEMP"), exist_ok=True)
    tmp_s2 = os.path.join(REPO, "TEMP", "tmp_s2.json")
    with open(tmp_s2, "w") as f:
        json.dump(s2, f)
    run(f'"{PYEXE}" -s GPT_SoVITS/s2_train.py --config "TEMP/tmp_s2.json"', base_env)

    # ---- s1: GPT train ----
    import yaml
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

    # ---- collect weights ----
    out = os.path.join(BASE, "mario_models_new", f"GPT_SoVITS_{char.capitalize()}")
    os.makedirs(out, exist_ok=True)

    def newest(folder, ext):
        d = os.path.join(REPO, folder)
        if not os.path.isdir(d):
            return None
        cands = [os.path.join(d, f) for f in os.listdir(d)
                 if f.endswith(ext) and (exp.lower() in f.lower())]
        return max(cands, key=os.path.getmtime) if cands else None

    g = newest("SoVITS_weights_v2", ".pth")
    a = newest("GPT_weights_v2", ".ckpt")
    print(f"[ft] sovits weight: {g}\n[ft] gpt weight: {a}", flush=True)
    if g:
        shutil.copy(g, os.path.join(out, os.path.basename(g)))
    if a:
        shutil.copy(a, os.path.join(out, os.path.basename(a)))
    # bundle a clean 3-10s reference for inference
    ref = os.path.join(BASE, "characters", char, "voice", "reference_audio.wav")
    if os.path.exists(ref):
        shutil.copy(ref, os.path.join(out, f"{char}_ref.wav"))
    print(f"[ft] DONE -> {out}\n[ft] contents: {os.listdir(out)}", flush=True)


if __name__ == "__main__":
    main()
