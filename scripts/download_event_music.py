#!/usr/bin/env python3
"""
Download music for all shot events from YouTube.

Uses yt-dlp to search YouTube and download the first result as MP3.
Downloads to client/assets/event_music/ with event-name filenames.
Then run scripts/add_music_to_events.py to wire them into events.

Usage:
    python scripts/download_event_music.py          # Download all missing
    python scripts/download_event_music.py rick_roll # Download specific event
    python scripts/download_event_music.py --list    # Show what would download

Requirements:
    pip install yt-dlp
    ffmpeg must be installed (for audio conversion)
"""

import json
import os
import subprocess
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.join(SCRIPT_DIR, "..")
EVENTS_JSON = os.path.join(ROOT_DIR, "server", "data", "shot_events.json")
MUSIC_DIR = os.path.join(ROOT_DIR, "client", "assets", "event_music")

# Search terms for each event — curated for best YouTube results
MUSIC_SEARCH = {
    # Gaming
    "mario_kart": "mario kart rainbow road theme",
    "smash_bros": "super smash bros ultimate main theme",
    "zelda": "legend of zelda main theme orchestral",
    "pokemon": "pokemon theme song original",
    "minecraft": "minecraft sweden c418",
    "fortnite": "fortnite og lobby music",
    "among_us": "among us drip theme song",
    "gta": "gta san andreas theme song",
    "call_of_duty": "modern warfare 2 theme hans zimmer",
    "league": "warriors imagine dragons league of legends",
    "rocket_league": "rocket league breathing underwater",
    "animal_crossing": "animal crossing new horizons main theme",
    "elden_ring": "elden ring main theme",
    "dark_souls": "dark souls gwyn lord of cinder theme",
    "undertale": "megalovania undertale",

    # Movies/TV
    "star_wars": "imperial march star wars",
    "marvel": "avengers theme song",
    "breaking_bad": "breaking bad main theme",
    "the_office": "the office theme song",
    "lord_of_rings": "concerning hobbits lord of the rings",
    "harry_potter": "hedwigs theme harry potter",
    "john_wick": "john wick theme song",
    "spongebob": "spongebob squarepants theme song",
    "shrek": "all star smash mouth",
    "batman": "dark knight theme hans zimmer",
    "fast_furious": "see you again wiz khalifa fast furious",
    "stranger_things": "stranger things main theme",
    "game_of_thrones": "game of thrones main theme",
    "pirates_caribbean": "hes a pirate pirates of the caribbean",
    "jurassic_park": "jurassic park theme john williams",

    # Memes
    "rick_roll": "never gonna give you up rick astley",
    "sigma": "drive forever sigma male remix",
    "based": "can you feel my heart bring me the horizon",
    "ohio": "only in ohio phonk remix",
    "skibidi": "skibidi toilet theme song",
    "no_cap": "no cap future lil uzi vert",
    "ratio": "megamind phonk remix",
    "yeet": "yeet sound effect bass boosted",
    "vibe_check": "buttercup jack stauber",
    "ok_boomer": "ok boomer song remix",

    # Party Games
    "waterfall": "waterfalls tlc",
    "never_have_i": "shots lmfao",
    "kings_cup": "we are the champions queen",
    "flip_cup": "timber pitbull kesha",
    "beer_pong": "red solo cup toby keith",
    "thunderstruck": "thunderstruck acdc",
    "shotgun": "shotgun george ezra",
    "power_hour": "levels avicii",
    "chug": "chug jug with you",
    "double_shot": "turn down for what dj snake lil jon",
    "truth_or_dare": "dare gorillaz",
    "spin_bottle": "kiss from a rose seal",
    "categories": "mr brightside the killers",
    "most_likely": "most girls hailee steinfeld",
    "last_man": "the final countdown europe",

    # Music Artists
    "sabrina_carpenter": "espresso sabrina carpenter",
    "kanye": "stronger kanye west",
    "eminem": "lose yourself eminem",
    "weeknd": "blinding lights the weeknd",
    "travis_scott": "sicko mode travis scott",
    "doja_cat": "say so doja cat",
    "bad_bunny": "titi me pregunto bad bunny",
    "beyonce": "crazy in love beyonce",
    "kendrick": "humble kendrick lamar",

    # Random Fun
    "bathroom_break": "toilet flush sound effect royalty free",
    "pizza_time": "pizza time spiderman 2 theme",
    "midnight": "midnight city m83",
    "first_shot": "first date blink 182",
    "last_shot": "closing time semisonic",
    "birthday_wish": "birthday katy perry",
    "group_photo": "photograph nickelback",
    "dance_battle": "everybody dance now c c music factory",
    "karaoke": "dont stop believin journey",
    "couples": "at last etta james",
    "singles": "single ladies beyonce",
    "designated_driver": "sober demi lovato",
    "best_friend": "lean on me bill withers",
    "throwback": "everybody backstreets back",
    "roast": "burn usher",

    # Sports
    "touchdown": "zombie nation kernkraft 400",
    "slam_dunk": "space jam theme song",
    "goal": "wavin flag knaan world cup",
    "knockout": "eye of the tiger survivor",
    "world_cup": "waka waka shakira",
    "super_bowl": "crazy train ozzy osbourne",
    "home_run": "centerfield john fogerty",
    "hole_in_one": "pga tour theme song golf",
    "checkmate": "one metallica chess",
    "strike_bowling": "the big lebowski bowling scene",

    # Holidays
    "new_years": "auld lang syne new years",
    "halloween": "thriller michael jackson",
    "christmas": "all i want for christmas mariah carey",
    "st_patricks": "irish drinking song dubliners",
    "valentines": "cant help falling in love elvis presley",
    "oktoberfest": "ein prosit oktoberfest",
    "graduation": "good riddance time of your life green day",

    # Quirky
    "mystery_shot": "x files theme song",
    "hot_take": "hot in herre nelly",
    "plot_twist": "roundabout yes jojo to be continued",
}


def download_one(event_name: str, search_query: str, max_duration: int = 300) -> bool:
    """Download a single song as MP3."""
    output_path = os.path.join(MUSIC_DIR, f"{event_name}.mp3")

    if os.path.exists(output_path):
        size_mb = os.path.getsize(output_path) / (1024 * 1024)
        if size_mb > 0.1:
            print(f"  ⏭ Already exists ({size_mb:.1f}MB)")
            return True

    cmd = [
        sys.executable, "-m", "yt_dlp",
        f"ytsearch1:{search_query}",
        "--extract-audio",
        "--audio-format", "mp3",
        "--audio-quality", "5",
        "--max-downloads", "1",
        "--match-filter", f"duration<{max_duration}",
        "--no-playlist",
        "--quiet",
        "--no-warnings",
        "-o", output_path,
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode == 0 and os.path.exists(output_path):
            size_mb = os.path.getsize(output_path) / (1024 * 1024)
            print(f"  ✓ Downloaded ({size_mb:.1f}MB)")
            return True
        else:
            # Try without duration filter
            cmd_retry = [c for c in cmd if not c.startswith("duration")]
            cmd_retry = [c for c in cmd if c != "--match-filter" and c != f"duration<{max_duration}"]
            result2 = subprocess.run(cmd_retry, capture_output=True, text=True, timeout=120)
            if result2.returncode == 0 and os.path.exists(output_path):
                size_mb = os.path.getsize(output_path) / (1024 * 1024)
                print(f"  ✓ Downloaded on retry ({size_mb:.1f}MB)")
                return True
            print(f"  ✗ Failed: {result.stderr[:200] if result.stderr else 'unknown error'}")
            return False
    except subprocess.TimeoutExpired:
        print(f"  ✗ Timeout")
        return False
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False


def main():
    os.makedirs(MUSIC_DIR, exist_ok=True)

    # Check yt-dlp
    try:
        subprocess.run([sys.executable, "-m", "yt_dlp", "--version"],
                      capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("ERROR: yt-dlp not installed. Run: pip install yt-dlp")
        sys.exit(1)

    # Check ffmpeg
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
    except FileNotFoundError:
        print("WARNING: ffmpeg not found. Audio conversion may fail.")
        print("Install: https://ffmpeg.org/download.html")

    # Parse args
    specific = None
    list_only = False
    if len(sys.argv) > 1:
        if sys.argv[1] == "--list":
            list_only = True
        else:
            specific = sys.argv[1:]

    # Filter events
    if specific:
        to_download = {k: v for k, v in MUSIC_SEARCH.items() if k in specific}
        if not to_download:
            print(f"Event(s) not found: {', '.join(specific)}")
            print(f"Available: {', '.join(sorted(MUSIC_SEARCH.keys()))}")
            sys.exit(1)
    else:
        to_download = MUSIC_SEARCH

    if list_only:
        existing = set(os.path.splitext(f)[0] for f in os.listdir(MUSIC_DIR) if f.endswith(".mp3"))
        for name, query in sorted(to_download.items()):
            status = "✓" if name in existing else " "
            print(f"  [{status}] {name:30s} → {query}")
        have = len(existing & set(to_download.keys()))
        print(f"\n{have}/{len(to_download)} already downloaded")
        return

    # Download
    total = len(to_download)
    success = 0
    failed = []

    print(f"=== Downloading music for {total} events ===\n")

    for i, (name, query) in enumerate(sorted(to_download.items()), 1):
        print(f"[{i}/{total}] {name} → \"{query}\"")
        if download_one(name, query):
            success += 1
        else:
            failed.append(name)

        if i < total:
            time.sleep(2)

    print(f"\n{'='*50}")
    print(f"Downloaded: {success}/{total}")
    if failed:
        print(f"Failed: {', '.join(failed)}")
    print(f"{'='*50}")

    if success > 0:
        print(f"\nNext step: python scripts/add_music_to_events.py")


if __name__ == "__main__":
    main()
