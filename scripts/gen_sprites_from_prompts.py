"""Generate a character's sprites from its sprite_prompts.txt via the WIZARD's
image backends (HuggingFace/Pollinations flux, Gemini, local SD) — NOT ChatGPT.

Why this exists: the wizard's generate_all_poses() uses the canonical pose plan,
so it can't target characters whose sprite paths are custom (mario, rudi). This
driver reads the character's sprite_prompts.txt (which already lists each custom
path + a full self-contained prompt) and routes each through the same backend
router that drew Reze — flux has no IP filter, so it draws copyrighted characters
(Mario, Reze, ...) that ChatGPT refuses.

Reuses character_creator.sprite_generator for backend routing + rembg cutout, so
no new generation/cutout logic. Resumable (skips sprites already on disk).

Usage:
  venv/Scripts/python.exe scripts/gen_sprites_from_prompts.py mario
  venv/Scripts/python.exe scripts/gen_sprites_from_prompts.py mario --backend huggingface --force
"""
import argparse
import asyncio
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from character_creator import sprite_generator as sg  # noqa: E402

# Same block format mcp_chatgpt/batch_sprites.py parses: [NN] <relpath> + prompt.
_BLOCK = re.compile(r"\[(\d+)\]\s+(\S+)\s*\n-+\n(.+?)(?=\n\[\d+\]|\Z)", re.S)


def parse_blocks(path: str):
    """Return [(relpath, full_prompt), ...] — relpath like 'sprites/<path>.png'."""
    text = open(path, encoding="utf-8").read()
    return [(m.group(2).strip(), m.group(3).strip()) for m in _BLOCK.finditer(text)]


async def run(char: str, backend: str, force: bool, delay: float, ref: str = "") -> None:
    cdir = os.path.join(BASE, "characters", char)
    sheet = os.path.join(cdir, "sprite_prompts.txt")
    if not os.path.isfile(sheet):
        print(f"no sprite_prompts.txt for {char} — run the wizard or "
              f"character_creator.sprite_generator.write_sprite_prompts_file first")
        return
    blocks = parse_blocks(sheet)
    cfg = sg.load_sprite_config()
    if backend:
        cfg = {**cfg, "backend": backend}     # pin the lead backend (e.g. huggingface = free flux)
    # Reference image (gemini multimodal): base64 it into cfg so _generate_gemini_image
    # sends it inline, and prefix every prompt to copy the reference's exact colors.
    ref_prefix = ""
    if ref:
        import base64
        with open(ref, "rb") as f:
            cfg["_ref_image_b64"] = base64.b64encode(f.read()).decode()
        ref_prefix = ("Use the attached reference image as the EXACT same character — copy her "
                      "colors, hat, eyes, outfit and design precisely, do not recolor her. "
                      "Keep that identical character and only change the pose/expression to: ")
        print(f"REF: {ref} loaded ({len(cfg['_ref_image_b64'])//1024}KB b64) — color-locked to reference", flush=True)
    print(f"GEN {char}: {len(blocks)} sprites, backend order: {sg._backend_order(cfg)}", flush=True)

    done = skip = fail = 0
    for rel, prompt in blocks:
        out = os.path.join(cdir, rel)
        if not force and os.path.exists(out) and os.path.getsize(out) > 2000:
            print(f"SKIP {rel} (exists)", flush=True)
            skip += 1
            continue
        os.makedirs(os.path.dirname(out), exist_ok=True)
        img = used = None
        for b in sg._backend_order(cfg):
            img = await sg._run_backend(b, ref_prefix + prompt, cfg, portrait=True)
            if img:
                used = b
                break
        if not img:
            print(f"FAIL {rel} (all backends)", flush=True)
            fail += 1
            continue
        sg._try_remove_background(img, out)     # isnet + alpha matting cutout
        print(f"DONE {rel} via {used} ({len(img):,} bytes)", flush=True)
        done += 1
        if delay:
            await asyncio.sleep(delay)

    print(f"\nSUMMARY {char}: done={done} skip={skip} fail={fail}", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("character")
    ap.add_argument("--backend", default="", help="pin lead backend (huggingface/pollinations/gemini/...)")
    ap.add_argument("--force", action="store_true", help="regenerate even if the sprite exists")
    ap.add_argument("--delay", type=float, default=3.0, help="seconds between sprites")
    ap.add_argument("--ref", default="", help="reference image path; gemini multimodal color-lock")
    a = ap.parse_args()
    asyncio.run(run(a.character, a.backend, a.force, a.delay, a.ref))
