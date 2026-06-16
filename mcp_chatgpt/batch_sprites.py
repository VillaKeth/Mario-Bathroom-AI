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

from mcp_chatgpt import selectors  # noqa: E402 (after sys.path setup)
from mcp_chatgpt.browser import get_session  # noqa: E402 (after sys.path setup)
from mcp_chatgpt.parsing import parse_reset_seconds  # noqa: E402 (after sys.path setup)

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


# A browser/profile-launch failure (e.g. the profile is already open in another
# session) is infrastructure-fatal — retrying just reopens tabs and burns the
# whole queue with the same error, so we stop the run instead.
_FATAL_GEN_ERR = ("launch_persistent_context", "existing browser",
                  "Target page", "has been closed", "ProfileInUse")


async def _generate_once(session, prompt: str, account: str):
    """One sprite attempt, up to 3 retries for stochastic guardrail blocks.
    Returns (image_path|None, status, message); status in {ok, cap, refused, fatal}.
    Scans assistant text AND the page notice, so a cap banner is caught even when
    it isn't part of the reply. Each opened thread/tab is closed before returning
    so tabs don't pile up across sprites and retries."""
    msg = ""
    for attempt in range(1, 4):
        try:
            r = await session.new_thread(PROMPT_PREFIX + prompt, account=account)
        except Exception as e:  # noqa: BLE001
            msg = f"gen error: {e}"
            if any(s in msg for s in _FATAL_GEN_ERR):
                return None, "fatal", msg
            continue
        tid = r.get("thread_id")
        try:
            resp = r.get("response", {})
            imgs = resp.get("images", [])
            msg = ((resp.get("text") or "") + "\n" + (resp.get("notice") or "")).strip()
            if imgs:
                return imgs[0], "ok", msg
            if any(m.lower() in msg.lower() for m in selectors.USAGE_LIMIT_MARKERS):
                return None, "cap", msg
            print(f"     retry attempt {attempt} blocked: {msg[:60]!r}", flush=True)
        finally:
            if tid:
                try:
                    await session.close_thread(tid)   # close the tab; no pileup
                except Exception:  # noqa: BLE001
                    pass
    return None, "refused", msg


async def run(character: str, start: int, force: bool, regen: bool, account: str,
              delay: float, cap_fallback: float, max_cap_waits: int) -> None:
    char_dir = ROOT / "characters" / character
    entries = parse_prompts(char_dir / "sprite_prompts.txt")
    # Manifest of sprites already FRESHLY regenerated this campaign, so a re-run
    # after a cap resumes instead of redoing finished ones.
    manifest = char_dir / ".regen_done.txt"
    done_set = set(manifest.read_text().split()) if manifest.exists() else set()
    session = get_session()
    done, skipped, failed = [], [], []
    capped_out = False

    try:
        for idx, rel, prompt in entries:
            if idx < start:
                continue
            dst = char_dir / rel
            # --regen: overwrite existing art, but skip ones already regenerated.
            # default: skip any sprite that already exists. --force ignores both.
            if not force:
                if regen and rel in done_set:
                    print(f"SKIP [{idx:02d}] {rel} (already regenerated)", flush=True)
                    skipped.append(rel)
                    continue
                if not regen and dst.exists() and dst.stat().st_size > 1000:
                    print(f"SKIP [{idx:02d}] {rel} (exists)", flush=True)
                    skipped.append(rel)
                    continue

            # Proactive pacing before each real generation (skips don't reach here).
            if delay:
                print(f"WAIT {int(delay)}s before [{idx:02d}] {rel}", flush=True)
                await asyncio.sleep(delay)

            print(f"GEN  [{idx:02d}] {rel}", flush=True)
            cap_waits = 0
            while True:
                img, status, msg = await _generate_once(session, prompt, account)
                if status == "fatal":
                    print(f"STOP [{idx:02d}] fatal browser error — ending run "
                          f"(is the profile open elsewhere?):\n{msg[:300]}", flush=True)
                    failed.append(rel)
                    capped_out = True   # reuse the break-out-of-everything flag
                    break
                if status == "ok":
                    if cut(img, dst):
                        print(f"DONE [{idx:02d}] {rel}", flush=True)
                        done.append(rel)
                        done_set.add(rel)
                        manifest.write_text("\n".join(sorted(done_set)))
                    else:
                        print(f"FAIL [{idx:02d}] {rel} (cut)", flush=True)
                        failed.append(rel)
                    break
                if status == "cap":
                    cap_waits += 1
                    parsed = parse_reset_seconds(msg)
                    src = "page timer" if parsed is not None else "fallback"
                    # The reset is whatever THIS response reports (varies: minutes,
                    # hours, "5 hours and 51 minutes", a clock countdown) — parsed
                    # dynamically, never assumed. +60s buffer to wake just AFTER the
                    # reset. Clamp only as an absurdity guard (30s..26h) so a parser
                    # misfire can't truncate a real long reset NOR sleep forever.
                    secs = (parsed + 60) if parsed is not None else cap_fallback
                    secs = int(max(30, min(secs, 93600)))
                    print(f"CAP  [{idx:02d}] image cap hit. Message:\n{msg[:400]}", flush=True)
                    if cap_waits > max_cap_waits:
                        print(f"STOP [{idx:02d}] capped {cap_waits}x — ending run. "
                              "Re-run --regen later to resume.", flush=True)
                        failed.append(rel)
                        capped_out = True
                        break
                    print(f"CAP  [{idx:02d}] waiting {secs}s ({src}) then retrying", flush=True)
                    await asyncio.sleep(secs)
                    continue
                # refused after retries
                print(f"FAIL [{idx:02d}] {rel} (refused) text={msg[:80]!r}", flush=True)
                failed.append(rel)
                break

            if capped_out:
                break
    finally:
        await session.close()

    print(f"\nSUMMARY done={len(done)} skipped={len(skipped)} failed={len(failed)} "
          f"regenerated_total={len(done_set)}", flush=True)
    if failed:
        print("FAILED:", failed, flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--character", default="rudi")
    ap.add_argument("--start", type=int, default=1)
    ap.add_argument("--force", action="store_true", help="(re)generate every sprite, ignore manifest + existing")
    ap.add_argument("--regen", action="store_true",
                    help="overwrite existing sprites, but skip ones already regenerated (resumable)")
    ap.add_argument("--account", default="default", help="logged-in account profile to use")
    ap.add_argument("--delay", type=float, default=0.0,
                    help="seconds to wait before EACH generation (pacing; e.g. 900 = 15 min)")
    ap.add_argument("--cap-fallback", type=float, default=900.0,
                    help="seconds to wait on a cap when the page shows no parseable timer")
    ap.add_argument("--max-cap-waits", type=int, default=8,
                    help="give up a run after this many cap-waits on one sprite")
    a = ap.parse_args()
    asyncio.run(run(a.character, a.start, a.force, a.regen, a.account, a.delay,
                    a.cap_fallback, a.max_cap_waits))
