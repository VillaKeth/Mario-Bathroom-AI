"""One-shot: regenerate Jax's idle + game + extras pools directly (no wizard UI).

Bypasses the rate-limited Chrome wizard. Uses the same content_generator the
wizard calls, pointed at the local Ollama backend (llama3:latest).
"""
import asyncio
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from character_creator.content_generator import generate_all_content  # noqa: E402

CHAR_DIR = os.path.join(BASE, "characters", "jax")
NAME = "Jax"
DESCRIPTION = (
    "Jax from The Amazing Digital Circus. A sarcastic, cocky purple/lavender "
    "cartoon rabbit trapped in a digital circus world. Mischievous troublemaker "
    "who loves chaos, pranks, and snarky one-liners."
)
PERSONALITY = (
    "Sarcastic, cocky, mischievous, effortlessly cool, perpetually bored, witty, "
    "loves chaos and pranks, snarky insults with a hidden flicker of self-awareness "
    "about the absurdity of his digital prison. Never references Mario."
)


async def main():
    cats = sys.argv[1:] or ["idle", "games", "extras"]
    print(f"[gen] categories={cats} dir={CHAR_DIR}", flush=True)
    async for ev in generate_all_content(
        name=NAME, description=DESCRIPTION, personality=PERSONALITY,
        char_dir=CHAR_DIR, categories=cats,
    ):
        t = ev.get("type")
        if t == "start":
            print(f"[gen] start backend={ev.get('backend')} total={ev['data'].get('total_pools')}", flush=True)
        elif t == "pool_done":
            d = ev["data"]
            print(f"[gen] {ev.get('category')}/{ev.get('pool')} done "
                  f"({d.get('completed_pools')}/{d.get('total_pools')})", flush=True)
        elif t == "complete":
            print("[gen] COMPLETE", flush=True)
            errs = ev.get("data", {}).get("errors") or []
            if errs:
                print(f"[gen] errors: {errs}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
