"""Generate Mario reference audio using FakeYou API (one-time setup).

This script generates a reference WAV file of Mario's voice that XTTS v2
uses for voice cloning. Only needs to run once.
"""

import requests
import uuid
import time
import os
import sys

# FakeYou Mario voice model tokens (Charles Martinet)
MARIO_TOKENS = [
    "TM:7wbtjphx8h8v",  # Mario (most popular)
    "TM:4e2xqpwqaggr",  # Mario (alternate)
]

# Reference text — a longer passage for better voice cloning quality
REFERENCE_TEXT = (
    "Hello everybody! It's-a me, Mario! Welcome to my world! "
    "I love jumping on goombas and eating mushrooms! "
    "Let's-a go on an adventure together! Wahoo! "
    "The princess might be in another castle, but that's okay! "
    "Every pipe leads somewhere amazing!"
)

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "data")
OUTPUT_PATH = os.path.join(OUTPUT_DIR, "mario_reference.wav")

API_BASE = "https://api.fakeyou.com"


def generate_reference():
    """Generate Mario reference audio via FakeYou API."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    if os.path.exists(OUTPUT_PATH) and os.path.getsize(OUTPUT_PATH) > 10000:
        print(f"Reference audio already exists at {OUTPUT_PATH}")
        print("Delete it and re-run to regenerate.")
        return True

    print("Generating Mario reference audio via FakeYou API...")
    print(f"Text: {REFERENCE_TEXT[:80]}...")

    for token in MARIO_TOKENS:
        print(f"\nTrying model token: {token}")
        try:
            # Submit TTS request
            payload = {
                "tts_model_token": token,
                "uuid_idempotency_token": str(uuid.uuid4()),
                "inference_text": REFERENCE_TEXT,
            }

            resp = requests.post(
                f"{API_BASE}/tts/inference",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30,
            )

            if resp.status_code != 200:
                print(f"  Request failed: HTTP {resp.status_code}")
                continue

            result = resp.json()
            if not result.get("success"):
                print(f"  API error: {result}")
                continue

            job_token = result.get("inference_job_token")
            if not job_token:
                print("  No job token returned")
                continue

            print(f"  Job submitted: {job_token}")
            print("  Waiting for generation (this may take 30-120 seconds)...")

            # Poll for completion
            for attempt in range(60):  # max 5 minutes
                time.sleep(5)
                status_resp = requests.get(
                    f"{API_BASE}/tts/job/{job_token}",
                    timeout=15,
                )

                if status_resp.status_code != 200:
                    print(f"  Poll failed: HTTP {status_resp.status_code}")
                    continue

                status_data = status_resp.json()
                state = status_data.get("state", {})
                status = state.get("status", "unknown")

                if status == "pending":
                    if attempt % 6 == 0:
                        print(f"  Still pending... ({attempt * 5}s)")
                    continue
                elif status == "started":
                    if attempt % 4 == 0:
                        print(f"  Processing... ({attempt * 5}s)")
                    continue
                elif status == "complete_success":
                    audio_path = state.get("maybe_public_bucket_wav_audio_path")
                    if not audio_path:
                        print("  No audio path in response")
                        break

                    # Download the audio
                    audio_url = f"https://cdn.fakeyou.com{audio_path}"
                    print(f"  Downloading from: {audio_url}")

                    audio_resp = requests.get(audio_url, timeout=30)
                    if audio_resp.status_code == 200:
                        with open(OUTPUT_PATH, "wb") as f:
                            f.write(audio_resp.content)
                        print(f"  Saved reference audio: {OUTPUT_PATH}")
                        print(f"  Size: {len(audio_resp.content)} bytes")
                        return True
                    else:
                        print(f"  Download failed: HTTP {audio_resp.status_code}")
                        break

                elif status in ("complete_failure", "dead", "attempt_failed"):
                    print(f"  Generation failed: {status}")
                    break
                else:
                    print(f"  Unknown status: {status}")

            print(f"  Timed out or failed with token {token}")

        except Exception as e:
            print(f"  Error: {e}")
            continue

    print("\nAll model tokens failed. You can manually provide a Mario WAV file at:")
    print(f"  {OUTPUT_PATH}")
    print("Use any 5-15 second clip of Mario speaking.")
    return False


if __name__ == "__main__":
    success = generate_reference()
    sys.exit(0 if success else 1)
