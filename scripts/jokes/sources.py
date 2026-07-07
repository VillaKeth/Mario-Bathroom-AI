import hashlib, json
from pathlib import Path


def candidate_id(text: str) -> str:
    return hashlib.sha1(text.strip().lower().encode("utf-8")).hexdigest()[:12]


def write_candidate(fp, text: str, source: str, seen: set) -> bool:
    text = (text or "").strip()
    if not text:
        return False
    cid = candidate_id(text)
    if cid in seen:
        return False
    seen.add(cid)
    fp.write(json.dumps({"id": cid, "text": text, "source": source}) + "\n")
    return True


def merge_jsonl(paths, out_path) -> int:
    """Merge multiple candidate files into one deduped candidates.jsonl.

    Each entry in `paths` is either:
    - a `.jsonl` file with one JSON object per line (needs a "text" field; "source"
      is preserved if present, otherwise falls back to the file's stem), or
    - a `.txt` file where each non-empty line is treated as a joke, with "source"
      derived from the filename stem.

    Dedup is by `candidate_id` (via `write_candidate`) across ALL input files
    combined. Returns the number of candidates written to `out_path`.
    """
    seen = set()
    count = 0
    with open(out_path, "w", encoding="utf-8") as out_fp:
        for raw_path in paths:
            path = Path(raw_path)
            stem_source = path.stem
            if path.suffix.lower() == ".txt":
                with open(path, "r", encoding="utf-8") as in_fp:
                    for line in in_fp:
                        text = line.strip()
                        if not text:
                            continue
                        if write_candidate(out_fp, text, stem_source, seen):
                            count += 1
            else:
                with open(path, "r", encoding="utf-8") as in_fp:
                    for line in in_fp:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            record = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        text = record.get("text", "")
                        source = record.get("source") or stem_source
                        if write_candidate(out_fp, text, source, seen):
                            count += 1
    return count
