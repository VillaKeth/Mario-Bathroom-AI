"""Merge harvested episode audio into a character's training dataset.

Takes the staged output of harvest_voice_from_episode.py (one or more tags) and
folds it into characters/<char>/voice/dataset/, then rewrites the GPT-SoVITS
.list manifest so it covers old and new segments together.

Dedupe runs across EVERYTHING at once -- existing dataset, and every harvest
against every other -- because separate episodes repeat the same sponsor
boilerplate and show-open patter, and re-harvesting an episode the dataset was
cropped from reproduces its own audio on different slice boundaries.

Dry run by default. Pass --apply to write, which first backs up the existing
.list and records exactly what was added.
"""
import argparse
import glob
import json
import os
import re
import shutil
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from scripts.harvest_voice_from_episode import (  # noqa: E402
    AD_PAT, DEDUPE_FRAC, ngrams, norm_text)


def log(m):
    print(m, flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("char")
    ap.add_argument("tags", nargs="+", help="harvest tags, e.g. aca215 aca214")
    ap.add_argument("--harvest-root", default=os.path.join(BASE, "voice_harvest"))
    ap.add_argument("--apply", action="store_true", help="actually write (default: dry run)")
    args = ap.parse_args()

    ds = os.path.join(BASE, "characters", args.char, "voice", "dataset")
    seg_dir = os.path.join(ds, "segments")
    list_path = os.path.join(ds, f"{args.char}.list")
    if not os.path.isdir(seg_dir):
        raise SystemExit(f"no dataset at {seg_dir}")

    # ---- existing ----
    existing = []
    if os.path.isfile(list_path):
        for line in open(list_path, encoding="utf-8"):
            p = line.rstrip("\n").split("|")
            if len(p) >= 4 and p[0].strip():
                existing.append({"wav": p[0], "text": p[3]})
    log(f"existing dataset: {len(existing)} segments")

    pool = set()
    for e in existing:
        pool |= ngrams(norm_text(e["text"]))

    # ---- harvests ----
    added, stats = [], {}
    for tag in args.tags:
        mpath = os.path.join(args.harvest_root, f"{tag}_manifest.json")
        if not os.path.isfile(mpath):
            log(f"  !! no manifest for {tag} ({mpath}) -- skipped")
            continue
        m = json.load(open(mpath, encoding="utf-8"))
        src_dir = os.path.join(args.harvest_root, tag)
        kept, drop_ad, drop_dupe, missing = 0, 0, 0, 0
        for s in m["segments"]:
            wav = os.path.join(src_dir, s["wav"])
            if not os.path.isfile(wav):
                missing += 1
                continue
            if AD_PAT.search(s["text"]):
                drop_ad += 1
                continue
            g = ngrams(norm_text(s["text"]))
            if g and len(g & pool) / len(g) > DEDUPE_FRAC:
                drop_dupe += 1
                continue
            pool |= g            # so later harvests dedupe against this one too
            added.append({"tag": tag, "src": wav, "text": s["text"], "dur": s["dur"]})
            kept += 1
        stats[tag] = {"kept": kept, "ad": drop_ad, "dupe": drop_dupe, "missing": missing,
                      "min": round(sum(a["dur"] for a in added if a["tag"] == tag) / 60, 1)}
        log(f"  {tag}: kept {kept} ({stats[tag]['min']} min), "
            f"dropped ad {drop_ad}, dupe {drop_dupe}"
            + (f", missing {missing}" if missing else ""))

    new_min = sum(a["dur"] for a in added) / 60
    log("")
    log("=" * 64)
    log(f"would add {len(added)} segments / {new_min:.1f} min")
    log(f"total after merge: {len(existing) + len(added)} segments")
    log("=" * 64)

    if not args.apply:
        log("dry run -- pass --apply to write")
        return

    shutil.copy2(list_path, list_path + ".bak")
    log(f"backed up {os.path.basename(list_path)} -> .bak")

    lines = [f"{e['wav']}|{args.char}|en|{e['text']}" for e in existing]
    for a in added:
        dst = os.path.join(seg_dir, os.path.basename(a["src"]))
        if not os.path.isfile(dst):
            shutil.copy2(a["src"], dst)
        text = re.sub(r"\s+", " ", a["text"]).replace("|", " ").strip()
        lines.append(f"{os.path.abspath(dst)}|{args.char}|en|{text}")

    with open(list_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    json.dump({"added": [{"tag": a["tag"], "wav": os.path.basename(a["src"]),
                          "dur": a["dur"]} for a in added], "stats": stats},
              open(os.path.join(ds, "merge_record.json"), "w", encoding="utf-8"),
              indent=1, ensure_ascii=False)

    # verify every path in the rewritten manifest resolves
    bad = 0
    for line in open(list_path, encoding="utf-8"):
        p = line.split("|")[0].strip()
        if p and not os.path.isfile(p):
            bad += 1
    log(f"wrote {len(lines)} manifest entries; unresolvable paths: {bad}")
    if bad:
        raise SystemExit("manifest has broken paths -- NOT safe to train")


if __name__ == "__main__":
    main()
