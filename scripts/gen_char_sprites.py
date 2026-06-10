"""Generate ALL sprites for a character using the wizard's own pipeline.

Drives character_creator.sprite_generator.generate_all_poses, which auto-detects
the local SD server (A1111-compatible API on :7860) and removes backgrounds via
rembg. 100% local/offline.

Run: venv/Scripts/python.exe scripts/gen_char_sprites.py <char_name>
"""
import asyncio
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

import yaml  # noqa: E402
from character_creator.sprite_generator import (  # noqa: E402
    generate_all_poses, expected_sprite_count, find_missing_sprites, _generation_tasks,
)


async def main():
    char = sys.argv[1] if len(sys.argv) > 1 else "jax"
    char_dir = os.path.join(BASE, "characters", char)
    yml = yaml.safe_load(open(os.path.join(char_dir, "character.yaml"), encoding="utf-8"))
    visuals = yml.get("visuals", {})
    desc = visuals.get("visual_description", "")
    art = visuals.get("art_style", "3d_figurine")
    out = os.path.join(char_dir, "sprites")
    total = expected_sprite_count()
    print(f"[sprites] {char}: {total} poses, art_style={art}", flush=True)

    task_id = f"gen_{char}"
    gen = asyncio.create_task(generate_all_poses(task_id, char, desc, art, out))

    # Progress watcher
    while not gen.done():
        await asyncio.sleep(15)
        t = _generation_tasks.get(task_id, {})
        print(f"[sprites] {t.get('completed',0)}/{t.get('total',total)} "
              f"(current: {t.get('current_pose') or t.get('current','')})", flush=True)
    await gen

    missing = find_missing_sprites(out)
    done = total - len(missing)
    print(f"[sprites] DONE {done}/{total}", flush=True)
    if missing:
        print(f"[sprites] MISSING: {[m['sprite_path'] for m in missing]}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
