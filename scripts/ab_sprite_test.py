"""A/B a sprite prompt across image backends (local SD vs Pollinations).

Renders the SAME prompt through each requested backend and writes
model_comparison/sprite_ab_<backend>.png so you can eyeball quality.

Usage:
    venv/Scripts/python.exe scripts/ab_sprite_test.py "a purple cartoon rabbit ..." [a1111,pollinations]

Notes:
- a1111 = the local SD server (scripts/local_sd_server.py) on :7860.
- pollinations = free sana first, then budget-capped paid flux (see
  sprite_config.json pollinations_budget + .secrets ledger).
"""
import asyncio
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from character_creator import sprite_generator as sg  # noqa: E402

OUT = os.path.join(BASE, "model_comparison")


async def main():
    prompt = sys.argv[1] if len(sys.argv) > 1 else (
        "a tall lanky purple cartoon rabbit, mischievous grin, full body, "
        "3d rendered figurine style, clean studio background")
    backends = (sys.argv[2] if len(sys.argv) > 2 else "a1111,pollinations").split(",")
    os.makedirs(OUT, exist_ok=True)
    cfg = sg.load_sprite_config()

    for b in backends:
        b = b.strip()
        img = None
        if b == "a1111":
            img = await sg._generate_a1111(prompt, cfg.get("a1111_url", "http://localhost:7860"))
        elif b == "pollinations":
            img = await sg._generate_pollinations(prompt)
        elif b == "comfyui":
            img = await sg._generate_comfyui(prompt, cfg.get("comfyui_url", "http://localhost:8188"))
        else:
            print(f"[ab] unknown backend: {b}")
            continue
        if img:
            p = os.path.join(OUT, f"sprite_ab_{b}.png")
            with open(p, "wb") as f:
                f.write(img)
            print(f"[ab] {b}: OK {len(img):,}b -> {p}")
        else:
            print(f"[ab] {b}: FAILED")


if __name__ == "__main__":
    asyncio.run(main())
