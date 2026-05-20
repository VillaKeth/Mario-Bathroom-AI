#!/usr/bin/env python3
"""
Add music files to shot events automatically.

Scans client/assets/event_music/ for MP3 files, matches them to events
by filename, and updates shot_events.json with the music_file path and
music phase.

Usage:
    python scripts/add_music_to_events.py
"""

import json
import os
import sys

EVENTS_JSON = os.path.join(os.path.dirname(__file__), "..", "server", "data", "shot_events.json")
MUSIC_DIR = os.path.join(os.path.dirname(__file__), "..", "client", "assets", "event_music")


def main():
    if not os.path.isdir(MUSIC_DIR):
        print(f"Music directory not found: {MUSIC_DIR}")
        print("Create it and add MP3 files named after events (e.g., mario_kart.mp3)")
        sys.exit(1)

    with open(EVENTS_JSON, "r") as f:
        data = json.load(f)

    events = data["events"]
    event_map = {e["name"]: e for e in events}

    mp3_files = [f for f in os.listdir(MUSIC_DIR) if f.lower().endswith(".mp3")]
    if not mp3_files:
        print("No MP3 files found in", MUSIC_DIR)
        sys.exit(0)

    updated = 0
    skipped = []
    not_found = []

    for mp3 in sorted(mp3_files):
        event_name = os.path.splitext(mp3)[0]
        if event_name not in event_map:
            not_found.append(mp3)
            continue

        event = event_map[event_name]
        music_path = f"client/assets/event_music/{mp3}"

        if event.get("music_file") == music_path and "music" in event.get("phases", []):
            skipped.append(event_name)
            continue

        event["music_file"] = music_path

        phases = event.get("phases", [])
        if "music" not in phases:
            # Insert music after countdown, before toast
            if "countdown" in phases:
                idx = phases.index("countdown") + 1
                phases.insert(idx, "music")
            elif "toast" in phases:
                idx = phases.index("toast")
                phases.insert(idx, "music")
            else:
                phases.append("music")
            event["phases"] = phases

        updated += 1
        print(f"  ✓ {event_name} → {music_path}")

    with open(EVENTS_JSON, "w") as f:
        json.dump(data, f, indent=2)

    print(f"\nResults:")
    print(f"  Updated: {updated}")
    print(f"  Already set: {len(skipped)}")
    if not_found:
        print(f"  No matching event: {', '.join(not_found)}")
    print(f"\nTotal events with music: {sum(1 for e in events if e.get('music_file'))}/{len(events)}")


if __name__ == "__main__":
    main()
