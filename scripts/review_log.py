"""Read back a day's Mario/Rudi logs. Files live at logs/<day>/<source>.log.

  python scripts/review_log.py                    # today's conversation
  python scripts/review_log.py --day 2026-07-01
  python scripts/review_log.py --source tts
  python scripts/review_log.py --grep goodbye --tail 50
"""
import argparse
import datetime
import json
import os
import sys


def _default_root():
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    try:
        with open(os.path.join(here, "config.json"), encoding="utf-8") as f:
            root = json.load(f).get("logging", {}).get("root_dir", "logs")
    except Exception:
        root = "logs"
    return os.path.join(here, root)


def resolve_log_path(root, day, source):
    day = day or datetime.datetime.now().strftime("%Y-%m-%d")
    return os.path.join(root, day, f"{source}.log")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Review Mario/Rudi day logs.")
    ap.add_argument("--root", default=None)
    ap.add_argument("--day", default=None)
    ap.add_argument("--source", default="conversation")
    ap.add_argument("--grep", default=None)
    ap.add_argument("--tail", type=int, default=None)
    args = ap.parse_args(argv)

    root = args.root or _default_root()
    path = resolve_log_path(root, args.day, args.source)
    if not os.path.exists(path):
        print(f"(no log at {path})", file=sys.stderr)
        return
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()
    if args.grep:
        lines = [ln for ln in lines if args.grep.lower() in ln.lower()]
    if args.tail is not None:
        lines = lines[-args.tail:] if args.tail > 0 else []
    print("".join(lines), end="")


if __name__ == "__main__":
    main()
