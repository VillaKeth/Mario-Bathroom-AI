"""Check all event music files exist."""
import json
import os

d = json.load(open("server/data/shot_events.json"))
missing = []
for e in d["events"]:
    mf = e.get("music_file", "")
    if mf:
        path = mf if os.path.isabs(mf) else os.path.join(".", mf)
        if not os.path.exists(path):
            missing.append(f"{e['name']}: {mf}")
if missing:
    print(f"{len(missing)} missing music files:")
    for m in missing:
        print(f"  {m}")
else:
    print("All music files present!")
