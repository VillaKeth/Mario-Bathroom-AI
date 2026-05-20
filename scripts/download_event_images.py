#!/usr/bin/env python3
"""Download real images for all party events from the web (Bing Image Search).
Similar to download_event_music.py but for images instead of audio.
Searches for iconic/recognizable images and saves as 800x450 PNGs.
"""

import json
import os
import sys
import time
import shutil
import tempfile
import requests
from pathlib import Path
from io import BytesIO

try:
    from PIL import Image
except ImportError:
    print("ERROR: Pillow required. pip install Pillow")
    sys.exit(1)

try:
    from icrawler.builtin import BingImageCrawler
except ImportError:
    print("ERROR: icrawler required. pip install icrawler")
    sys.exit(1)

ROOT = Path(__file__).resolve().parent.parent
EVENTS_JSON = ROOT / "server" / "data" / "shot_events.json"
OUTPUT_DIR = ROOT / "client" / "assets" / "event_images"
TARGET_SIZE = (800, 450)

# Curated search terms for each event - designed to find THE iconic image
SEARCH_TERMS = {
    # Gaming
    "mario_kart": "Mario Kart 8 Deluxe rainbow road screenshot",
    "smash_bros": "Super Smash Bros Ultimate character roster",
    "zelda": "Legend of Zelda Tears of the Kingdom",
    "pokemon": "Pokemon Pikachu iconic",
    "minecraft": "Minecraft landscape screenshot",
    "fortnite": "Fortnite battle royale poster",
    "among_us": "Among Us impostor emergency meeting",
    "gta": "GTA V Grand Theft Auto promo art",
    "call_of_duty": "Call of Duty Modern Warfare poster",
    "league": "League of Legends champions splash art",
    "rocket_league": "Rocket League aerial goal explosion",
    "animal_crossing": "Animal Crossing New Horizons island",
    "elden_ring": "Elden Ring Erdtree landscape",
    "dark_souls": "Dark Souls bonfire knight",
    "undertale": "Undertale characters Sans",
    "deltarune": "Deltarune Kris Ralsei Susie",

    # Movies/TV
    "star_wars": "Star Wars lightsaber duel",
    "marvel": "Marvel Avengers assembled poster",
    "breaking_bad": "Breaking Bad Heisenberg Walter White",
    "the_office": "The Office Michael Scott",
    "lord_of_rings": "Lord of the Rings fellowship poster",
    "harry_potter": "Harry Potter Hogwarts castle",
    "john_wick": "John Wick Keanu Reeves poster",
    "spongebob": "SpongeBob SquarePants excited",
    "shrek": "Shrek movie poster",
    "batman": "Batman dark knight poster",
    "fast_furious": "Fast and Furious cars poster",
    "stranger_things": "Stranger Things poster",
    "game_of_thrones": "Game of Thrones Iron Throne",
    "pirates_caribbean": "Pirates Caribbean Jack Sparrow poster",
    "jurassic_park": "Jurassic Park T-Rex poster",

    # Memes/Internet
    "rick_roll": "Rick Astley Never Gonna Give You Up music video",
    "sigma": "sigma male grindset meme",
    "based": "based chad meme",
    "ohio": "only in Ohio meme",
    "skibidi": "skibidi toilet meme",
    "no_cap": "no cap fr meme",
    "ratio": "ratio twitter meme W L",
    "yeet": "yeet meme throw",
    "vibe_check": "vibe check meme",
    "ok_boomer": "ok boomer meme",

    # Party Games
    "waterfall": "waterfall drinking game cards",
    "never_have_i": "never have i ever party game",
    "kings_cup": "kings cup drinking game cards",
    "flip_cup": "flip cup party game college",
    "beer_pong": "beer pong table cups party",
    "thunderstruck": "ACDC Thunderstruck concert",
    "shotgun": "shotgun a beer party",
    "power_hour": "power hour shot glasses party",
    "chug": "chugging beer contest",
    "double_shot": "double shot liquor glasses bar",
    "truth_or_dare": "truth or dare party game",
    "spin_bottle": "spin the bottle game",
    "categories": "drinking game categories party",
    "most_likely": "most likely to game friends pointing",
    "last_man": "last man standing drinking",

    # Music Artists
    "sabrina_carpenter": "Sabrina Carpenter Espresso performance",
    "kanye": "Kanye West My Beautiful Dark Twisted Fantasy album cover",
    "eminem": "Eminem Slim Shady performance concert",
    "weeknd": "The Weeknd Blinding Lights neon",
    "travis_scott": "Travis Scott Astroworld concert stage",
    "doja_cat": "Doja Cat performance concert",
    "bad_bunny": "Bad Bunny concert reggaeton",
    "beyonce": "Beyonce Renaissance concert",
    "kendrick": "Kendrick Lamar concert performance",

    # Random Fun
    "bathroom_break": "bathroom break sign funny",
    "pizza_time": "pizza party delivery celebration",
    "midnight": "midnight clock celebration party",
    "first_shot": "cheers first drink party shot",
    "last_shot": "last call bar closing time neon",
    "birthday_wish": "birthday cake candles celebration",
    "group_photo": "group photo friends selfie party",
    "dance_battle": "dance battle party breakdance",
    "karaoke": "karaoke night singing microphone neon",
    "couples": "couples party love dance",
    "singles": "singles party mingle fun",
    "designated_driver": "designated driver hero car keys",
    "best_friend": "best friends party hug",
    "throwback": "throwback retro 90s nostalgia party",
    "roast": "comedy roast battle microphone",

    # Sports
    "touchdown": "touchdown celebration NFL football",
    "slam_dunk": "slam dunk NBA basketball",
    "goal": "soccer goal celebration",
    "knockout": "knockout boxing punch",
    "world_cup": "FIFA World Cup trophy",
    "super_bowl": "Super Bowl halftime show",
    "home_run": "home run baseball swing",
    "hole_in_one": "hole in one golf celebration",
    "checkmate": "checkmate chess pieces king",
    "strike_bowling": "bowling strike pins",

    # Holidays
    "new_years": "New Years Eve fireworks celebration",
    "halloween": "Halloween party costume spooky",
    "christmas": "Christmas party lights celebration",
    "st_patricks": "St Patricks Day green beer shamrock",
    "valentines": "Valentines Day hearts romantic",
    "oktoberfest": "Oktoberfest beer festival",
    "graduation": "graduation cap throw celebration",

    # Quirky
    "mystery_shot": "mystery cocktail drink neon bar",
    "hot_take": "hot take spicy fire meme",
    "plot_twist": "plot twist surprise gasp",
    "angel_shotgun": "The Cab Angel With a Shotgun band",
    "tokyo_ghoul": "Tokyo Ghoul Ken Kaneki mask",
}


def download_and_resize(event_name: str, search_term: str, output_path: Path) -> bool:
    """Use icrawler to search Bing, download best image, resize to target."""
    tmp_dir = tempfile.mkdtemp(prefix=f"evt_{event_name}_")
    try:
        crawler = BingImageCrawler(
            storage={"root_dir": tmp_dir},
            log_level=50,  # suppress logs
        )
        crawler.crawl(
            keyword=search_term,
            max_num=5,
            min_size=(400, 200),
        )

        # Find downloaded images and pick the best one
        downloaded = sorted(Path(tmp_dir).glob("*.*"))
        if not downloaded:
            print(f"  ✗ No images found")
            return False

        for img_file in downloaded:
            try:
                img = Image.open(img_file)
                img = img.convert("RGB")

                # Skip tiny images
                if img.width < 200 or img.height < 100:
                    continue

                # Resize maintaining aspect ratio, then center-crop to exact size
                img_ratio = img.width / img.height
                target_ratio = TARGET_SIZE[0] / TARGET_SIZE[1]

                if img_ratio > target_ratio:
                    new_height = TARGET_SIZE[1]
                    new_width = int(new_height * img_ratio)
                else:
                    new_width = TARGET_SIZE[0]
                    new_height = int(new_width / img_ratio)

                img = img.resize((new_width, new_height), Image.LANCZOS)

                left = (new_width - TARGET_SIZE[0]) // 2
                top = (new_height - TARGET_SIZE[1]) // 2
                img = img.crop((left, top, left + TARGET_SIZE[0], top + TARGET_SIZE[1]))

                img.save(output_path, "PNG", optimize=True)
                size_kb = output_path.stat().st_size // 1024
                print(f"  ✓ Saved ({size_kb}KB)")
                return True

            except Exception:
                continue

        print(f"  ✗ All downloaded images failed to process")
        return False

    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Load events JSON
    with open(EVENTS_JSON) as f:
        data = json.load(f)
    events = data.get("events", data) if isinstance(data, dict) else data

    # Find events that need images
    event_names = [e["name"] for e in events if e["name"] in SEARCH_TERMS]

    # Check which already exist (skip if --force not passed)
    force = "--force" in sys.argv
    if not force:
        existing = {p.stem for p in OUTPUT_DIR.glob("*.png")}
        event_names = [n for n in event_names if n not in existing]

    if not event_names:
        print("All events already have images. Use --force to re-download.")
        return

    print(f"Events to download: {len(event_names)}")
    successes = 0
    failures = []

    for i, name in enumerate(event_names, 1):
        search_term = SEARCH_TERMS[name]
        output_path = OUTPUT_DIR / f"{name}.png"
        print(f"[{i}/{len(event_names)}] {name}: searching \"{search_term}\"...")

        ok = download_and_resize(name, search_term, output_path)
        if ok:
            successes += 1
        else:
            failures.append(name)

        # Small delay between searches
        time.sleep(1)

    # Update shot_events.json with image paths
    print(f"\nUpdating shot_events.json with image paths...")
    updated = 0
    for event in events:
        img_path = OUTPUT_DIR / f"{event['name']}.png"
        if img_path.exists():
            rel_path = f"assets/event_images/{event['name']}.png"
            if event.get("image_file") != rel_path:
                event["image_file"] = rel_path
                updated += 1

    with open(EVENTS_JSON, "w") as f:
        if isinstance(data, dict):
            json.dump(data, f, indent=2)
        else:
            json.dump(events, f, indent=2)

    print(f"\n=== RESULTS ===")
    print(f"Downloaded: {successes}/{len(event_names)}")
    print(f"Failed: {len(failures)}")
    if failures:
        print(f"Failed events: {', '.join(failures)}")
    print(f"JSON updated: {updated} events got image_file paths")


if __name__ == "__main__":
    main()
