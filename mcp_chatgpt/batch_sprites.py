"""Batch-generate character sprites via ChatGPT (browser MCP) + rembg cutout.

Reads characters/<char>/sprite_prompts.txt, generates each `[NN] <relpath>`
block whose index >= --start, and saves the background-removed (transparent)
sprite to characters/<char>/<relpath>. Existing sprites are skipped.

Generation runs in THIS (mcp_chatgpt) venv via the browser session; the rembg
cutout runs in the MAIN repo venv (which has rembg) through a subprocess, so no
extra dependency is added here.

IMPORTANT: the default browser profile must be FREE — i.e. the in-editor MCP
server must not be running (restart/close it first), otherwise Chrome reports
the profile is already in use.

Run:
  mcp_chatgpt/venv/Scripts/python.exe mcp_chatgpt/batch_sprites.py --character rudi --start 5
"""
import argparse
import asyncio
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:           # allow running as a plain script file
    sys.path.insert(0, str(ROOT))

from mcp_chatgpt.browser import get_session  # noqa: E402 (after sys.path setup)

MAIN_PY = ROOT / "venv" / "Scripts" / "python.exe"

# Suppress GPT's habit of stamping text/letters onto the character or clothing.
PROMPT_PREFIX = (
    "Generate an image of the following (produce the image directly, no questions). "
    "Do NOT put any text, letters, words, watermark or signage anywhere in the image:\n\n"
)

# Runs in the MAIN venv (has rembg). Cuts background -> transparent RGBA PNG.
CUT_SNIPPET = (
    "import sys\n"
    "from pathlib import Path\n"
    "from PIL import Image\n"
    "from rembg import remove\n"
    "src, dst = Path(sys.argv[1]), Path(sys.argv[2])\n"
    "dst.parent.mkdir(parents=True, exist_ok=True)\n"
    "dst.write_bytes(remove(src.read_bytes()))\n"
    "Image.open(dst).convert('RGBA').save(dst)\n"
    "print('CUT_OK', dst)\n"
)

_BLOCK = re.compile(r"\[(\d+)\]\s+(\S+)\s*\n-+\n(.+?)(?=\n\[\d+\]|\Z)", re.S)


def parse_prompts(path: Path):
    """Return [(index, relpath, prompt_text), ...] from a sprite_prompts.txt."""
    text = path.read_text(encoding="utf-8")
    out = []
    for m in _BLOCK.finditer(text):
        out.append((int(m.group(1)), m.group(2).strip(), m.group(3).strip()))
    return out


def cut(src: str, dst: Path) -> bool:
    cp = subprocess.run([str(MAIN_PY), "-c", CUT_SNIPPET, src, str(dst)],
                        capture_output=True, text=True)
    if cp.returncode != 0 or not dst.exists():
        print(f"     cut error: {cp.stderr.strip()[:200]}", flush=True)
        return False
    return True


async def run(character: str, start: int, force: bool, account: str) -> None:
    char_dir = ROOT / "characters" / character
    entries = parse_prompts(char_dir / "sprite_prompts.txt")
    session = get_session()
    done, skipped, failed = [], [], []

    for idx, rel, prompt in entries:
        if idx < start:
            continue
        dst = char_dir / rel
        if dst.exists() and dst.stat().st_size > 1000 and not force:
            print(f"SKIP [{idx:02d}] {rel} (exists)", flush=True)
            skipped.append(rel)
            continue

        print(f"GEN  [{idx:02d}] {rel}", flush=True)
        try:
            r = await session.new_thread(PROMPT_PREFIX + prompt, account=account)
        except Exception as e:  # noqa: BLE001 - log and keep going
            print(f"FAIL [{idx:02d}] gen error: {e}", flush=True)
            failed.append(rel)
            continue

        imgs = r.get("response", {}).get("images", [])
        if not imgs:
            txt = r.get("response", {}).get("text", "")[:80]
            print(f"FAIL [{idx:02d}] no image (limit/timeout?) text={txt!r}", flush=True)
            failed.append(rel)
            continue

        if cut(imgs[0], dst):
            print(f"DONE [{idx:02d}] {rel}", flush=True)
            done.append(rel)
        else:
            failed.append(rel)

    print(f"\nSUMMARY done={len(done)} skipped={len(skipped)} failed={len(failed)}", flush=True)
    if failed:
        print("FAILED:", failed, flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--character", default="rudi")
    ap.add_argument("--start", type=int, default=1)
    ap.add_argument("--force", action="store_true", help="regenerate even if the sprite exists")
    ap.add_argument("--account", default="default", help="logged-in account profile to use")
    a = ap.parse_args()
    asyncio.run(run(a.character, a.start, a.force, a.account))
