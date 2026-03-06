"""Download Mario voice clips from open dataset and create reference audio."""
import os
import subprocess
import wave
import struct

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
OUTPUT = os.path.join(DATA_DIR, "mario_reference.wav")

# Best clips for voice cloning (longer sentences with clear Mario voice)
CLIPS = [
    "2",   # Hello everybody, it's a me, Mario.
    "10",  # So, starting today, I'm super duper excited.
    "6",   # Thank you very much for everyone who made this moment possible.
    "56",  # Well, you know how it is...
    "51",  # Well, you know what they say...
    "69",  # It really, at the end of the day, is all about the friends you make.
    "80",  # Well, you know Mario, I'm going with my traditional blue overalls
    "94",  # Welcome to my new game!
    "xd",  # Have you thought about, four sports!
]

BASE_URL = "https://raw.githubusercontent.com/eros71-dev/mario-voice-dataset/main/wavs"

os.makedirs(DATA_DIR, exist_ok=True)

# Download each clip
wav_files = []
for clip_id in CLIPS:
    local_path = os.path.join(DATA_DIR, f"mario_clip_{clip_id}.wav")
    if not os.path.exists(local_path) or os.path.getsize(local_path) < 1000:
        url = f"{BASE_URL}/{clip_id}.wav"
        print(f"Downloading clip {clip_id}...")
        subprocess.run(
            ["curl", "-L", "-o", local_path, url, "--connect-timeout", "15", "-s"],
            check=True,
        )
    size = os.path.getsize(local_path)
    if size > 1000:
        wav_files.append(local_path)
        print(f"  clip {clip_id}: {size} bytes")
    else:
        print(f"  clip {clip_id}: too small ({size}), skipping")

# Concatenate all WAV files into one reference
print(f"\nConcatenating {len(wav_files)} clips into reference audio...")

all_frames = b""
params = None

for wf_path in wav_files:
    try:
        with wave.open(wf_path, "rb") as wf:
            if params is None:
                params = wf.getparams()
            frames = wf.readframes(wf.getnframes())
            all_frames += frames
    except Exception as e:
        print(f"  Error reading {wf_path}: {e}")

if params and all_frames:
    with wave.open(OUTPUT, "wb") as out:
        out.setparams(params)
        out.writeframes(all_frames)
    size = os.path.getsize(OUTPUT)
    duration = len(all_frames) / (params.sampwidth * params.nchannels * params.framerate)
    print(f"\nReference audio saved: {OUTPUT}")
    print(f"  Size: {size} bytes")
    print(f"  Duration: {duration:.1f} seconds")
    print(f"  Sample rate: {params.framerate} Hz")
    print(f"  Channels: {params.nchannels}")
else:
    print("ERROR: No audio data to concatenate")
