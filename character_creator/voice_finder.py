"""Voice clip finder — searches YouTube via yt-dlp and downloads clips."""
import subprocess
import json
import os
import logging
import tempfile

logger = logging.getLogger(__name__)

def is_available() -> bool:
    try:
        subprocess.run(["yt-dlp", "--version"], capture_output=True, timeout=5)
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False

def search(query: str, max_results: int = 5) -> list[dict]:
    if not is_available():
        return []
    try:
        result = subprocess.run(
            ["yt-dlp", f"ytsearch{max_results}:{query}",
             "--dump-json", "--no-download", "--flat-playlist"],
            capture_output=True, text=True, timeout=30
        )
        clips = []
        for line in result.stdout.strip().split("\n"):
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                clips.append({
                    "id": data.get("id", ""),
                    "title": data.get("title", ""),
                    "duration": data.get("duration", 0),
                    "url": data.get("webpage_url", f"https://youtube.com/watch?v={data.get('id', '')}"),
                })
            except json.JSONDecodeError:
                continue
        return clips
    except Exception as e:
        logger.error(f"Voice search failed: {e}")
        return []

def download_clip(url: str, output_dir: str, max_duration: int = 30) -> str | None:
    if not is_available():
        return None
    output_path = os.path.join(output_dir, "reference_audio.wav")
    try:
        subprocess.run([
            "yt-dlp", url,
            "-x", "--audio-format", "wav",
            "--postprocessor-args", f"-t {max_duration}",
            "-o", output_path,
        ], capture_output=True, timeout=120, check=True)
        if os.path.exists(output_path):
            return output_path
    except Exception as e:
        logger.error(f"Voice download failed: {e}")
    return None
