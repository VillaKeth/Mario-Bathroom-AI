"""Generate content pools for Reze character."""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from character_creator.content_generator import generate_all_content

CHAR_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "characters", "reze")

async def main():
    print(f"Generating content for Reze in: {CHAR_DIR}")
    print("This will take 5-10 minutes with Ollama on 4GB VRAM...")
    print("-" * 50)
    
    count = 0
    async for event in generate_all_content(
        name="Reze",
        description="Reze is the Bomb Devil hybrid from Chainsaw Man. She appears as a sweet, kind cafe worker who befriends Denji, but is actually a trained Soviet assassin. She is playful, flirty, and manipulative, yet genuinely develops feelings.",
        personality="Playful, flirty, and mysterious with a hint of danger. Sweet on the surface with dark humor underneath. Teasing tone, asks personal questions, occasional dark humor.",
        char_dir=CHAR_DIR,
        categories=["idle", "games", "extras"]
    ):
        if event.get("type") == "pool_done":
            count += 1
            pool = event.get("data", {}).get("current_pool", "?")
            pct = event.get("data", {}).get("percent", 0)
            print(f"  [{count}/39] {pool} done ({pct}%)")
        elif event.get("type") == "error":
            print(f"  ERROR: {event.get('data', {}).get('errors', [])}")
        elif event.get("type") == "complete":
            print(f"\n{'='*50}")
            print(f"DONE! {event.get('data', {}).get('completed_pools', 0)} pools generated.")
            break
    
    print("\nReze content generation complete!")

if __name__ == "__main__":
    asyncio.run(main())
