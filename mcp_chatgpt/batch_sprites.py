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
from mcp_chatgpt.parsing import parse_reset_seconds  # noqa: E402 (after sys.path setup)
from mcp_chatgpt.rotation import AccountPool  # noqa: E402 (after sys.path setup)

MAIN_PY = ROOT / "venv" / "Scripts" / "python.exe"

# Suppress GPT's habit of stamping text/letters onto the character or clothing.
PROMPT_PREFIX = (
    "Generate an image of the following (produce the image directly, no questions). "
    "Do NOT put any text, letters, words, watermark or signage anywhere in the image:\n\n"
)

# Prepended (after PROMPT_PREFIX) when a --ref reference image is attached, so the
# model treats the uploaded picture as the exact character to match (image-to-image).
REF_PREAMBLE = (
    "Use the attached image ONLY as a reference for the character's APPEARANCE - copy her face, "
    "hairstyle, hair length, hair color, eye color, outfit design and colors from it exactly. But do "
    "NOT copy the reference's pose, camera angle, background, lighting, glowing light, sparks, "
    "ribbons, sashes or any props from it. Draw this same character in a brand-new different pose on "
    "a plain empty background, as described next: "
)

# Runs in the MAIN venv (has rembg). Cuts background -> transparent RGBA PNG.
CUT_SNIPPET = (
    "import sys, io\n"
    "from pathlib import Path\n"
    "from PIL import Image\n"
    "from rembg import remove, new_session\n"
    "src, dst = Path(sys.argv[1]), Path(sys.argv[2])\n"
    "dst.parent.mkdir(parents=True, exist_ok=True)\n"
    # isnet-general-use + alpha matting keeps thin/pale parts (white gloves,
    # sleeves) that the default u2net erases — matches character_creator's cut.
    "sess = new_session('isnet-general-use')\n"
    "out = remove(Image.open(io.BytesIO(src.read_bytes())), session=sess,\n"
    "             alpha_matting=True, alpha_matting_foreground_threshold=240,\n"
    "             alpha_matting_background_threshold=10, alpha_matting_erode_size=10)\n"
    "out.convert('RGBA').save(dst)\n"
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


# A profile-LAUNCH failure (profile already open in another session) is
# infrastructure-fatal — retrying just burns the queue, so we stop the run.
# NOTE: a closed/stale page is NOT here — that's recoverable (reopened below).
_FATAL_GEN_ERR = ("launch_persistent_context", "existing browser", "ProfileInUse")


async def _generate_once(session, prompt: str, account: str, thread_id, ref_image: str = ""):
    """One sprite attempt, up to 3 retries for stochastic guardrail blocks.

    Uses ONE persistent chat per account: the first call opens the thread, every
    later call sends into that SAME conversation (keeps history to 1 chat/account
    and 1 reused tab/account — no per-sprite open/close churn). The thread stays
    open for reuse and is torn down only by session.close() at the end.

    Returns (image_path|None, status, message, thread_id); status in
    {ok, cap, refused, fatal, notloggedin}. Scans assistant text AND the page
    notice, so a cap banner is caught even when it isn't part of the reply."""
    msg = ""
    pre = REF_PREAMBLE if ref_image else ""
    for attempt in range(1, 3):     # 2 tries on this account, then rotate (caller)
        try:
            if thread_id is None:
                r = await session.new_thread(PROMPT_PREFIX + pre + prompt, account=account,
                                             image_path=ref_image)
                thread_id = r.get("thread_id")
            else:
                r = await session.send(thread_id, PROMPT_PREFIX + pre + prompt, account=account,
                                       image_path=ref_image)
        except Exception as e:  # noqa: BLE001
            msg = f"gen error: {e}"
            low = msg.lower()
            if "not logged in" in low:
                return None, "notloggedin", msg, thread_id
            if any(s in msg for s in _FATAL_GEN_ERR):
                return None, "fatal", msg, thread_id
            # Network/HTTP error reaching chatgpt.com (e.g. ERR_HTTP_RESPONSE_CODE_
            # FAILURE = the site bounced us, often Cloudflare/bot-throttle after too
            # many rapid opens). Surface a distinct status so the caller BACKS OFF on
            # the SAME account instead of instantly rotating through every account
            # (which is the rapid-fire hammering that causes the throttle).
            if any(s in low for s in ("net::", "err_http", "err_connection",
                                      "err_timed_out", "err_network", "err_aborted",
                                      "err_name_not_resolved")):
                return None, "neterror", msg, thread_id
            # Recoverable browser instability (stale/closed page, wedged context,
            # failed target creation): relaunch the account's context + drop the
            # thread so the next attempt reopens fresh. NOT a guardrail refusal.
            if any(s in low for s in ("has been closed", "target page", "crash",
                                      "createtarget", "new_page", "protocol error",
                                      "connection closed", "browser has been closed")):
                try:
                    await session.reset_account(account)
                except Exception:  # noqa: BLE001
                    pass
                thread_id = None
            continue
        resp = r.get("response", {})
        imgs = resp.get("images", [])
        msg = ((resp.get("text") or "") + "\n" + (resp.get("notice") or "")).strip()
        if imgs:
            return imgs[0], "ok", msg, thread_id
        if any(m.lower() in msg.lower() for m in session.site.usage_limit_markers):
            return None, "cap", msg, thread_id
        print(f"     retry attempt {attempt} blocked: {msg[:60]!r}", flush=True)
    return None, "refused", msg, thread_id


async def run(provider: str, character: str, start: int, force: bool, regen: bool, accounts: list,
              delay: float, cap_fallback: float, max_cap_waits: int, ref: str = "",
              prompts: str = "sprite_prompts.txt") -> None:
    char_dir = ROOT / "characters" / character
    # A --prompts file (e.g. an alternate outfit's "outfits/tuxedo/prompts.txt")
    # isolates a campaign: the manifest lives next to it, so an outfit grind
    # never touches the default set's .regen_done.txt. Default resolves to the
    # legacy char_dir/sprite_prompts.txt + char_dir/.regen_done.txt.
    prompts_path = char_dir / prompts
    entries = parse_prompts(prompts_path)
    # Manifest of sprites already FRESHLY regenerated this campaign, so a re-run
    # after a cap resumes instead of redoing finished ones.
    manifest = prompts_path.parent / ".regen_done.txt"
    done_set = set(manifest.read_text().split()) if manifest.exists() else set()
    session = get_session(provider)
    pool = AccountPool(accounts)
    threads: dict = {}          # account -> persistent thread_id (one chat each)
    print(f"PROVIDER {provider} | ACCOUNTS rotating: {', '.join(pool.accounts)}", flush=True)
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
            wait_rounds = 0
            refusal_clears = 0      # times we've re-tried the refused (stochastic) set
            net_retries = 0         # consecutive network/HTTP errors on this sprite
            refused_here = set()    # accounts that guardrail-refused THIS sprite
            while True:
                acct = pool.pick(exclude=refused_here)
                if acct is None:
                    # A refused account that's actually AVAILABLE (not capped) means
                    # we'd otherwise wait hours for a slow account while a fast one
                    # sits idle. Guardrail refusals are stochastic — clear them and
                    # retry (bounded) rather than stalling for the next reset.
                    if (refused_here and refusal_clears < 3
                            and any(pool.is_available(a) for a in refused_here)):
                        refusal_clears += 1
                        print(f"RETRY [{idx:02d}] refused account still free — clearing "
                              f"refusals, retry {refusal_clears}/3", flush=True)
                        refused_here.clear()
                        continue
                    # Nothing pickable: either every account refused this sprite,
                    # or the only un-refused ones are capped.
                    if len(refused_here) >= len(pool.accounts):
                        print(f"FAIL [{idx:02d}] {rel} (refused by all "
                              f"{len(pool.accounts)} accounts)", flush=True)
                        failed.append(rel)
                        break
                    # Some accounts haven't refused but are capped — wait soonest.
                    wait_rounds += 1
                    if wait_rounds > max_cap_waits:
                        print(f"STOP [{idx:02d}] all accounts capped {wait_rounds}x — "
                              "ending run. Re-run --regen later to resume.", flush=True)
                        failed.append(rel)
                        capped_out = True
                        break
                    secs = int(max(5, min(pool.seconds_until_any(exclude=refused_here), 93600)))
                    print(f"WAITALL [{idx:02d}] accounts capped — "
                          f"sleeping {secs}s for soonest reset", flush=True)
                    # Don't hold 5 browsers open through a multi-hour idle: Chrome
                    # closes idle tabs/contexts and we'd resume on a dead page. Tear
                    # the session down (frees the windows too); thread uuids persist
                    # and reopen by URL on the next send.
                    if secs > 120:
                        await session.close()
                    await asyncio.sleep(secs)
                    continue

                img, status, msg, tid = await _generate_once(
                    session, prompt, acct, threads.get(acct), ref_image=ref)
                threads[acct] = tid     # remember this account's persistent chat
                if status == "fatal":
                    print(f"STOP [{idx:02d}] fatal browser error on '{acct}' — ending run "
                          f"(is the profile open elsewhere?):\n{msg[:300]}", flush=True)
                    failed.append(rel)
                    capped_out = True   # reuse the break-out-of-everything flag
                    break
                if status == "notloggedin":
                    # Park it far out so pick() skips it for the rest of the run
                    # (doesn't affect the all-capped wait, which uses the soonest).
                    print(f"DROP [{idx:02d}] '{acct}' not logged in — dropping from rotation. "
                          f"Re-login: python -m mcp_chatgpt._login_oneshot {acct}", flush=True)
                    pool.mark_capped(acct, 10**9)
                    continue
                if status == "neterror":
                    # chatgpt.com bounced us (HTTP/Cloudflare). Do NOT rotate to the
                    # next account — that rapid-fire blast is what causes the throttle.
                    # Back off on the SAME account (growing cooldown), fresh browser.
                    net_retries += 1
                    if net_retries > 8:
                        print(f"STOP [{idx:02d}] persistent network errors x{net_retries} "
                              f"(IP throttled?) — ending run; re-run later.", flush=True)
                        failed.append(rel)
                        capped_out = True
                        break
                    backoff = int(min(30 * net_retries, 240))
                    print(f"NET  [{idx:02d}] '{acct}' chatgpt.com HTTP error — cooling "
                          f"{backoff}s on SAME account (no rotate). {msg[:70]!r}", flush=True)
                    try:
                        await session.reset_account(acct)     # fresh browser, shed bad CF state
                    except Exception:  # noqa: BLE001
                        pass
                    threads.pop(acct, None)
                    await asyncio.sleep(backoff)
                    continue        # sticky pick returns the SAME account → retry it
                if status == "ok":
                    if cut(img, dst):
                        print(f"DONE [{idx:02d}] {rel} (via {acct})", flush=True)
                        done.append(rel)
                        done_set.add(rel)
                        manifest.write_text("\n".join(sorted(done_set)))
                    else:
                        print(f"FAIL [{idx:02d}] {rel} (cut)", flush=True)
                        failed.append(rel)
                    break
                if status == "cap":
                    parsed = parse_reset_seconds(msg)
                    src = "page timer" if parsed is not None else "fallback"
                    # The reset is whatever THIS response reports (varies: minutes,
                    # hours, "5 hours and 51 minutes", a clock countdown) — parsed
                    # dynamically, never assumed. +60s buffer to wake just AFTER the
                    # reset. Clamp only as an absurdity guard (5s..26h) so a parser
                    # misfire can't truncate a real long reset NOR sleep forever.
                    secs = (parsed + 60) if parsed is not None else cap_fallback
                    secs = int(max(5, min(secs, 93600)))
                    pool.mark_capped(acct, secs)
                    print(f"CAP  [{idx:02d}] '{acct}' capped {secs}s ({src}); rotating. "
                          f"Msg: {msg[:160]!r}", flush=True)
                    continue
                # Guardrail/refusal on this account — rotate to a fresh one instead
                # of burning the same account's quota. If EVERY account refuses, the
                # pick(exclude=...) above runs out and fails the sprite.
                print(f"REFUSE [{idx:02d}] '{acct}' refused; rotating. text={msg[:80]!r}",
                      flush=True)
                refused_here.add(acct)
                continue

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
    ap.add_argument("--provider", default="chatgpt",
                    help="browser provider: chatgpt | grok | gemini")
    ap.add_argument("--character", default="rudi")
    ap.add_argument("--start", type=int, default=1)
    ap.add_argument("--force", action="store_true", help="(re)generate every sprite, ignore manifest + existing")
    ap.add_argument("--regen", action="store_true",
                    help="overwrite existing sprites, but skip ones already regenerated (resumable)")
    ap.add_argument("--account", default="default", help="single logged-in account (back-compat)")
    ap.add_argument("--accounts", default="",
                    help="comma-separated accounts to rotate through, e.g. 'default,work'. "
                         "Caps rotate to the next; only ALL-capped waits.")
    ap.add_argument("--delay", type=float, default=0.0,
                    help="seconds to wait before EACH generation (pacing; e.g. 900 = 15 min)")
    ap.add_argument("--cap-fallback", type=float, default=900.0,
                    help="seconds to wait on a cap when the page shows no parseable timer")
    ap.add_argument("--max-cap-waits", type=int, default=8,
                    help="give up a sprite after this many all-accounts-capped waits")
    ap.add_argument("--ref", default="",
                    help="reference image path; attach for image-to-image (chatgpt) on every send")
    ap.add_argument("--prompts", default="sprite_prompts.txt",
                    help="prompts file relative to characters/<char>/ (e.g. "
                         "'outfits/tuxedo/prompts.txt'); its folder holds the "
                         "campaign's own .regen_done.txt manifest")
    a = ap.parse_args()
    accounts = [s.strip() for s in a.accounts.split(",") if s.strip()] or [a.account]
    asyncio.run(run(a.provider, a.character, a.start, a.force, a.regen, accounts, a.delay,
                    a.cap_fallback, a.max_cap_waits, ref=a.ref, prompts=a.prompts))
