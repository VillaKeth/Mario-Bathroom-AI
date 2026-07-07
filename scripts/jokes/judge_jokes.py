import argparse
import json
from pathlib import Path

import yaml


def _score(j): return j["funny"] * 2 + j["rudi_fit"]

def select_top(scored, n, long_cap=0.15):
    usable = [j for j in scored if j.get("tts_ok")]
    usable.sort(key=_score, reverse=True)
    out, longs, long_limit = [], 0, int(n * long_cap)
    for j in usable:
        is_long = len(j["text"]) > 200
        if is_long and longs >= long_limit:
            continue
        out.append(j["text"]); longs += is_long
        if len(out) >= n:
            break
    return out


def load_candidates(path) -> list:
    """Read a candidates/scored .jsonl file into a list of dicts."""
    candidates = []
    with open(path, "r", encoding="utf-8") as fp:
        for line in fp:
            line = line.strip()
            if not line:
                continue
            candidates.append(json.loads(line))
    return candidates


def write_curated(char_dir, jokes) -> None:
    """Write the final curated joke list to `<char_dir>/jokes/curated.yaml`."""
    jokes_dir = Path(char_dir) / "jokes"
    jokes_dir.mkdir(parents=True, exist_ok=True)
    out_path = jokes_dir / "curated.yaml"
    with open(out_path, "w", encoding="utf-8") as fp:
        yaml.safe_dump({"jokes": jokes}, fp, allow_unicode=True, sort_keys=False)


def main():
    """CLI stub: load already-scored candidates for a character, keep the top ones,
    and write them to curated.yaml. Judging (funny/rudi_fit/tts_ok fields) is done
    externally by other agents before this runs — each candidate dict is expected to
    already carry those fields.
    """
    parser = argparse.ArgumentParser(description="Select top-judged jokes into curated.yaml")
    parser.add_argument("--char", required=True, help="Character name, e.g. 'rudi'")
    parser.add_argument(
        "--candidates",
        default=None,
        help="Path to scored candidates .jsonl (defaults to characters/<char>/jokes/scored.jsonl)",
    )
    parser.add_argument("--n", type=int, default=1000, help="Max number of jokes to keep")
    args = parser.parse_args()

    char_dir = Path("characters") / args.char
    candidates_path = Path(args.candidates) if args.candidates else char_dir / "jokes" / "scored.jsonl"

    candidates = load_candidates(candidates_path)
    top = select_top(candidates, args.n)
    write_curated(char_dir, top)
    print(f"Wrote {len(top)} jokes to {char_dir / 'jokes' / 'curated.yaml'}")


if __name__ == "__main__":
    main()
