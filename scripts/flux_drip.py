"""Hourly Pollinations flux drip — spend the use-it-or-lose-it pollen grant.

The account regenerates ~0.01 pollen/hour and it does NOT accumulate, so an
hourly task spends it on the highest-value sprite work available: upgrading
character sprites from local-SD quality to flux quality, one small batch at a
time (default 5 images ~= 0.00875 pollen).

Queue: every character listed in DRIP_CHARACTERS gets its full sprite plan
queued (hero poses first). Progress persists in .secrets/flux_drip_state.json
so each run picks up where the last left off. Images get rembg background
removal (RGBA) exactly like the wizard pipeline.

Safety:
- hard per-run image cap (--max, default 5)
- global ledger budget still applies (sprite_config.json pollinations_budget)
- HTTP 402 (insufficient pollen) aborts the run quietly; next hour retries

Run hourly via Task Scheduler (see setup in repo docs) or manually:
    venv/Scripts/python.exe scripts/flux_drip.py [--max 5] [--dry-run]
"""
import argparse
import asyncio
import io
import json
import os
import sys
import urllib.parse
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from character_creator import sprite_generator as sg  # noqa: E402

STATE_PATH = os.path.join(BASE, ".secrets", "flux_drip_state.json")
LOG_PATH = os.path.join(BASE, "flux_drip.log")

# Characters whose sprites get flux upgrades, in priority order.
# Local-SD sprites are TEMPORARY placeholders only — flux output is the quality
# source of record; the drip replaces every local-SD sprite, Jax first.
DRIP_CHARACTERS = ["jax", "reze"]

# Poses most visible at the party — upgraded first.
HERO_POSES = [
    "greeting/wave", "positive/happy", "speech/talking", "positive/excited",
    "neutral/idle", "speech/listening", "positive/laughing", "thinking/thinking",
]


def log(msg):
    line = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} {msg}"
    print(line, flush=True)
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def load_state():
    try:
        with open(STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"done": []}


def save_state(state):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=1)


def build_queue(state):
    """All (char, sprite_path, prompt) not yet flux-upgraded, hero poses first."""
    import yaml
    done = set(state.get("done", []))
    queue = []
    for char in DRIP_CHARACTERS:
        ypath = os.path.join(BASE, "characters", char, "character.yaml")
        if not os.path.exists(ypath):
            continue
        y = yaml.safe_load(open(ypath, encoding="utf-8"))
        desc = (y.get("visuals") or {}).get("visual_description", "")
        art = (y.get("visuals") or {}).get("art_style", "3d_figurine")
        if not desc:
            continue
        style = sg.ART_STYLE_SUFFIXES.get(art, sg.ART_STYLE_SUFFIXES["3d_figurine"])
        plan = sg._generation_pose_plan()
        plan.sort(key=lambda i: (i["sprite_path"] not in HERO_POSES,
                                 HERO_POSES.index(i["sprite_path"]) if i["sprite_path"] in HERO_POSES else 0))
        for info in plan:
            key = f"{char}/{info['sprite_path']}"
            if key in done:
                continue
            prompt = info["prompt"].replace("{char}", desc) + style + sg.FRAMING_SUFFIX
            queue.append((char, info["sprite_path"], prompt, key))
    return queue


def detect_cropped(char: str, threshold: float = 0.985) -> list[str]:
    """Return sprite keys whose subject runs off the top OR bottom edge — the
    'missing body part' sprites. Used to re-queue only the worst poses."""
    from PIL import Image
    import numpy as np
    bad = []
    sdir = os.path.join(BASE, "characters", char, "sprites")
    if not os.path.isdir(sdir):
        return bad
    for info in sg._generation_pose_plan():
        p = os.path.join(sdir, f"{info['sprite_path']}.png")
        if not os.path.isfile(p):
            continue
        try:
            im = Image.open(p)
            if im.mode != "RGBA":
                continue
            a = np.array(im.split()[3])
            h = a.shape[0]
            top_cut = (a[0] > 10).mean() > 0.02      # opaque pixels on top row
            bot_cut = (a[h - 1] > 10).mean() > 0.02  # opaque pixels on bottom row
            if top_cut or bot_cut:
                bad.append(f"{char}/{info['sprite_path']}")
        except Exception:
            continue
    return bad


async def gen_flux(prompt: str, token: str) -> bytes | None:
    import httpx
    url = ("https://gen.pollinations.ai/image/" + urllib.parse.quote(prompt)
           + f"?model={sg._POLLINATIONS_PAID_MODEL}&width=768&height=1024")
    headers = {"Authorization": f"Bearer {token}", "User-Agent": "Mozilla/5.0"}
    async with httpx.AsyncClient(timeout=180, follow_redirects=True) as c:
        r = await c.get(url, headers=headers)
    if r.status_code == 200 and sg._is_valid_image(r.content) and len(r.content) > 5000:
        return r.content
    if r.status_code == 402:
        raise InsufficientPollen(r.text[:120])
    log(f"flux HTTP {r.status_code} ({len(r.content)}b)")
    return None


class InsufficientPollen(Exception):
    pass


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=5, help="max images this run")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--redo-cropped", action="store_true",
                    help="re-queue sprites whose subject runs off the top/bottom edge")
    args = ap.parse_args()

    token = sg._load_pollinations_token()
    if not token:
        log("no token — aborting")
        return

    state = load_state()

    if args.redo_cropped:
        cropped = []
        for char in DRIP_CHARACTERS:
            cropped += detect_cropped(char)
        before = len(state.get("done", []))
        state["done"] = [k for k in state.get("done", []) if k not in set(cropped)]
        save_state(state)
        log(f"redo-cropped: {len(cropped)} cropped sprite(s) re-queued "
            f"(done {before} -> {len(state['done'])})")
        for k in cropped:
            log(f"  redo: {k}")

    queue = build_queue(state)
    log(f"drip start: queue={len(queue)} max={args.max} "
        f"ledger={sg._pollinations_spent():.4f}/{sg._pollinations_budget():.4f}")
    if args.dry_run:
        for char, sp, _, _ in queue[:10]:
            log(f"  next: {char}/{sp}")
        return

    done_count = 0
    for char, sprite_path, prompt, key in queue:
        if done_count >= args.max:
            break
        if sg._pollinations_spent() + sg._POLLINATIONS_PAID_COST > sg._pollinations_budget():
            log("ledger budget reached — stopping")
            break
        try:
            img = await gen_flux(prompt, token)
        except InsufficientPollen as e:
            log(f"out of pollen this hour — stopping ({e})")
            break
        if not img:
            continue
        out = os.path.join(BASE, "characters", char, "sprites", f"{sprite_path}.png")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        sg._try_remove_background(img, out)
        sg._record_pollinations_spend(sg._POLLINATIONS_PAID_COST)
        state["done"].append(key)
        save_state(state)
        done_count += 1
        log(f"upgraded {key} ({len(img):,}b) | spent {sg._pollinations_spent():.4f}")

    log(f"drip end: upgraded {done_count} sprite(s)")


if __name__ == "__main__":
    asyncio.run(main())
