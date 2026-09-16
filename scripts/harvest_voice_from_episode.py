"""Harvest single-speaker training audio for a character from a long recording.

Given a podcast/interview URL, produce only the slices where the TARGET speaker
is talking alone -- no co-host, no callers, no guests, no sponsor reads -- ready
to append to characters/<char>/voice/dataset/.

Why each stage exists (all four were needed on a real episode):

  1. Slice          Same silence-slicer the training pipeline uses, so segments
                    come out the shape GPT-SoVITS wants (3-10s).
  2. Score          Cosine against a voiceprint built from the character's
                    EXISTING verified segments.
  3. Recalibrate    A centroid from a different recording partly measures codec
                    and channel, not voice -- on a 64kbps mp3 every score sagged
                    and the distribution had no clean split. Reseeding from the
                    episode's own top slices makes it channel-matched and the
                    distribution goes bimodal.
  4. Transcribe     The speaker metric cannot tell a sponsor read from speech,
                    and ad copy is usually over a music bed. Promo markers drop
                    it. Ads often score HIGH because it is genuinely the host
                    reading them.
  5. Window floor   The one that matters most on call-in shows. A slice spanning
                    a handover contains two voices; the averaged embedding still
                    scores high. Scoring each window and taking the MINIMUM
                    exposes the intruder.
  6. Dedupe         Skip anything already in the character's dataset, so the same
                    episode can be re-harvested without duplicating segments.

Usage:
    venv/Scripts/python.exe scripts/harvest_voice_from_episode.py charlie_kirk \\
        https://omny.fm/shows/the-charlie-kirk-show/ask-charlie-anything-215-... \\
        --tag aca215

Output: <out>/<tag>/*.wav plus <tag>_manifest.json (wav + transcript + scores).
Nothing is written into the real dataset; merging is a separate, deliberate step.
"""
import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import warnings

import numpy as np

warnings.simplefilter("ignore")
if not hasattr(np, "bool") or type(np.bool) is not type:
    np.bool = bool

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "gpt_sovits_repo"))
sys.path.insert(0, os.path.join(BASE, "gpt_sovits_repo", "tools"))

# Promo markers. Deliberately broad: losing a little good audio costs far less
# than training the clone on ad-read cadence over a music bed. The second group
# exists because sponsor copy often names no URL at all -- a supplement and a
# gold-IRA read both survived the first version of this pattern.
AD_PAT = re.compile(
    r"\.com|\.org|\bdot com\b|promo code|coupon|discount|sponsor|brought to you by"
    r"|visit |call now|call \d|text \w+ to|\b1[-\s]?8\d\d\b|offer|free shipping"
    r"|limited time|terms and conditions|go to |sign up at|subscribe"
    r"|gold ira|precious metal|bullion|supplement|mattress|\bVPN\b|hair loss"
    r"|weight loss|life insurance|mortgage rate|retirement account"
    r"|use (my|our) (code|link)|listeners get|percent off|our sponsor|sponsored by",
    re.I)

DEDUPE_NGRAM = 6
DEDUPE_FRAC = 0.25


def ngrams(s, n=DEDUPE_NGRAM):
    w = s.split()
    return set(" ".join(w[i:i + n]) for i in range(max(0, len(w) - n + 1)))


def log(msg):
    print(msg, flush=True)


def cos(a, b):
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def wav_dur(p):
    import wave
    try:
        with wave.open(p) as w:
            return w.getnframes() / float(w.getframerate())
    except Exception:
        return 0.0


def norm_text(t):
    return re.sub(r"[^a-z0-9 ]", "", (t or "").lower()).strip()


def download(url, dest):
    """Fetch audio as mono 32k wav -- what the training pipeline decodes to anyway."""
    if os.path.isfile(dest) and os.path.getsize(dest) > 100000:
        log(f"[1/6] reusing existing download: {dest}")
        return dest
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    base, _ = os.path.splitext(dest)
    log(f"[1/6] downloading {url}")
    subprocess.run(
        [sys.executable, "-m", "yt_dlp", url, "-x", "--audio-format", "wav",
         "--postprocessor-args", "ffmpeg:-ac 1 -ar 32000",
         "-o", base + ".%(ext)s", "--force-overwrites", "--no-playlist"],
        check=True, capture_output=True, timeout=1800)
    if not os.path.isfile(dest):
        raise SystemExit(f"download produced no file at {dest}")
    return dest


def build_reference_centroid(enc, char):
    """Voiceprint from the character's existing verified segments."""
    d = os.path.join(BASE, "characters", char, "voice", "dataset", "segments")
    files = sorted(glob.glob(os.path.join(d, "*.wav")))
    if len(files) < 10:
        raise SystemExit(f"need >=10 existing segments in {d} to build a voiceprint "
                         f"(found {len(files)})")
    from resemblyzer import preprocess_wav
    embs, texts = [], []
    for f in files:
        try:
            embs.append(enc.embed_utterance(preprocess_wav(f)))
        except Exception:
            pass
    log(f"[2/6] voiceprint from {len(embs)} existing segments")
    # existing transcripts, for dedupe
    lst = os.path.join(BASE, "characters", char, "voice", "dataset", f"{char}.list")
    if os.path.isfile(lst):
        for line in open(lst, encoding="utf-8"):
            parts = line.strip().split("|")
            if len(parts) >= 4:
                texts.append(norm_text(parts[3]))
    # Exact-string dedupe is far too weak: re-harvesting an episode the dataset
    # was originally cropped from produces the SAME speech on different slice
    # boundaries, so the transcripts differ by a word or two and every duplicate
    # sails through. Measured on one episode: exact match caught 7, shared
    # 6-grams caught 30. Overlap is scored against a pooled n-gram set instead.
    pool = set()
    for t in texts:
        if t:
            pool |= ngrams(t)
    return np.array(embs).mean(axis=0), pool


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("char")
    ap.add_argument("url")
    ap.add_argument("--tag", required=True, help="short label, e.g. aca215")
    ap.add_argument("--out", default=None, help="staging root (default: voice_harvest/)")
    ap.add_argument("--threshold", type=float, default=0.90,
                    help="pass-2 mean score floor")
    ap.add_argument("--wfloor", type=float, default=0.80,
                    help="per-window minimum; catches two-speaker slices")
    ap.add_argument("--seed-n", type=int, default=60)
    ap.add_argument("--whisper", default="small")
    args = ap.parse_args()

    out_root = args.out or os.path.join(BASE, "voice_harvest")
    work = os.path.join(out_root, "_work", args.tag)
    slices_dir = os.path.join(work, "slices")
    final_dir = os.path.join(out_root, args.tag)
    os.makedirs(work, exist_ok=True)

    from resemblyzer import VoiceEncoder, preprocess_wav
    enc = VoiceEncoder()

    src = download(args.url, os.path.join(work, "source.wav"))
    total_src = wav_dur(src)
    log(f"      source: {total_src/60:.1f} min")

    ref_centroid, existing_texts = build_reference_centroid(enc, args.char)

    if not glob.glob(os.path.join(slices_dir, "*.wav")):
        os.makedirs(slices_dir, exist_ok=True)
        from scripts.build_voice_dataset import slice_audio
        log("[3/6] slicing")
        slice_audio(src, slices_dir, args.char)
    files = sorted(glob.glob(os.path.join(slices_dir, "*.wav")))
    log(f"      {len(files)} slices")

    log("[4/6] embedding + scoring")
    embs, meta = {}, {}
    for i, f in enumerate(files):
        if i and i % 100 == 0:
            log(f"      {i}/{len(files)}")
        try:
            wav = preprocess_wav(f)
            if len(wav) < 16000 * 1.2:
                continue
            n = os.path.basename(f)
            embs[n] = enc.embed_utterance(wav)
            meta[n] = {"dur": wav_dur(f)}
        except Exception:
            pass

    p1 = sorted(((n, cos(e, ref_centroid)) for n, e in embs.items()), key=lambda x: -x[1])
    seed = np.array([embs[n] for n, _ in p1[:args.seed_n]])
    centroid = seed.mean(axis=0)
    log(f"      channel-matched centroid from top {len(seed)} slices "
        f"(pass-1 floor {p1[min(args.seed_n, len(p1)) - 1][1]:.3f})")

    scored = [{"file": n, "score": cos(e, centroid), **meta[n]} for n, e in embs.items()]
    scored.sort(key=lambda r: -r["score"])
    cand = [r for r in scored if r["score"] >= args.threshold]
    log(f"      {len(cand)} slices >= {args.threshold} "
        f"({sum(r['dur'] for r in cand)/60:.1f} min)")

    log(f"[5/6] transcribing {len(cand)} candidates (whisper {args.whisper})")
    from faster_whisper import WhisperModel
    model = WhisperModel(args.whisper, device="cpu", compute_type="int8")
    kept = []
    drop = {"ad": 0, "short": 0, "dupe": 0, "window": 0}
    for i, r in enumerate(cand):
        if i and i % 40 == 0:
            log(f"      {i}/{len(cand)}")
        p = os.path.join(slices_dir, r["file"])
        segs, _ = model.transcribe(p, language="en", beam_size=5)
        text = " ".join(s.text for s in segs).strip()
        if len(text.split()) < 3:
            drop["short"] += 1
            continue
        if AD_PAT.search(text):
            drop["ad"] += 1
            continue
        g = ngrams(norm_text(text))
        if g and len(g & existing_texts) / len(g) > DEDUPE_FRAC:
            drop["dupe"] += 1
            continue
        kept.append({**r, "text": text})
    del model

    log(f"[6/6] window check on {len(kept)} slices (second-speaker detection)")
    final = []
    for i, r in enumerate(kept):
        if i and i % 40 == 0:
            log(f"      {i}/{len(kept)}")
        try:
            wav = preprocess_wav(os.path.join(slices_dir, r["file"]))
            _, partials, _ = enc.embed_utterance(wav, return_partials=True)
            if partials is None or not len(partials):
                continue
            w = [cos(p, centroid) for p in partials]
            wmin = float(np.min(w))
        except Exception:
            continue
        if wmin < args.wfloor:
            drop["window"] += 1
            continue
        final.append({**r, "wmin": wmin})

    final.sort(key=lambda r: r["file"])
    shutil.rmtree(final_dir, ignore_errors=True)
    os.makedirs(final_dir, exist_ok=True)
    man = []
    for i, r in enumerate(final):
        dst = os.path.join(final_dir, f"{args.tag}_{i:04d}.wav")
        shutil.copy2(os.path.join(slices_dir, r["file"]), dst)
        man.append({"wav": os.path.basename(dst), "text": r["text"],
                    "score": round(r["score"], 4), "wmin": round(r["wmin"], 4),
                    "dur": round(r["dur"], 2)})
    json.dump({"tag": args.tag, "url": args.url, "char": args.char,
               "source_minutes": round(total_src / 60, 2),
               "threshold": args.threshold, "wfloor": args.wfloor,
               "dropped": drop, "segments": man},
              open(os.path.join(out_root, f"{args.tag}_manifest.json"), "w",
                   encoding="utf-8"), indent=1, ensure_ascii=False)

    secs = sum(r["dur"] for r in final)
    numy = [r for r in final if re.search(
        r"\b\d|\b(one|two|three|four|five|six|seven|eight|nine|ten|hundred|thousand|"
        r"million|billion|trillion)\b", r["text"], re.I)]
    log("")
    log("=" * 68)
    log(f"{args.tag}: {len(final)} segments, {secs/60:.1f} min kept "
        f"from {total_src/60:.1f} min  ({secs/max(1.0, total_src)*100:.0f}% yield)")
    log(f"  dropped -> ad {drop['ad']}, dupe {drop['dupe']}, "
        f"two-speaker {drop['window']}, too-short {drop['short']}")
    log(f"  with numbers/counting: {len(numy)} ({sum(r['dur'] for r in numy)/60:.1f} min)")
    log(f"  -> {final_dir}")
    log("=" * 68)


if __name__ == "__main__":
    main()
