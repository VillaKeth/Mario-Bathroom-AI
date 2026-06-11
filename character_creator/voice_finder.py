"""Voice clip finder — searches YouTube via yt-dlp and downloads clips.

Invokes yt-dlp through the current interpreter (`python -m yt_dlp`) so it works
without yt-dlp being on PATH — a non-technical user just needs the dependency
installed (setup.bat does this), no shell/PATH setup required.
"""
import subprocess
import json
import os
import sys
import logging

logger = logging.getLogger(__name__)

_YTDLP = [sys.executable, "-m", "yt_dlp"]


def is_available() -> bool:
    try:
        r = subprocess.run(_YTDLP + ["--version"], capture_output=True, timeout=15)
        return r.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def search(query: str, max_results: int = 5) -> list[dict]:
    if not is_available():
        return []
    try:
        result = subprocess.run(
            _YTDLP + [f"ytsearch{max_results}:{query}",
                      "--dump-json", "--no-download", "--flat-playlist"],
            capture_output=True, text=True, timeout=60
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


def download_full(url: str, out_path: str) -> str | None:
    """Download a video's FULL audio track as wav (for timestamp-section cutting)."""
    if not is_available():
        return None
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    base, _ = os.path.splitext(out_path)
    try:
        subprocess.run(
            _YTDLP + [
                url,
                "-x", "--audio-format", "wav",
                "-o", base + ".%(ext)s",
                "--force-overwrites", "--no-playlist",
            ],
            capture_output=True, timeout=600, check=True,
        )
        wav = base + ".wav"
        if os.path.exists(wav) and os.path.getsize(wav) > 2000:
            return wav
    except Exception as e:
        logger.error(f"Full audio download failed: {e}")
    return None


def cut_sections(in_wav: str, sections: list[dict], out_dir: str, base: str) -> list[str]:
    """Cut [{start, end}] (seconds) out of a wav via ffmpeg. Returns piece paths."""
    os.makedirs(out_dir, exist_ok=True)
    pieces = []
    for j, sec in enumerate(sections):
        try:
            start = float(sec.get("start", 0))
            end = float(sec.get("end", 0))
        except (TypeError, ValueError):
            continue
        if end <= start:
            continue
        out_path = os.path.join(out_dir, f"{base}_s{j:02d}.wav")
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-i", in_wav, "-ss", str(start), "-to", str(end),
                 "-ac", "1", out_path],
                capture_output=True, timeout=120, check=True,
            )
            if os.path.exists(out_path) and os.path.getsize(out_path) > 2000:
                pieces.append(out_path)
        except Exception as e:
            logger.error(f"Section cut {start}-{end} failed: {e}")
    return pieces


def concat_wavs(pieces: list[str], out_path: str, max_duration: float = 25.0) -> str | None:
    """Concatenate wavs into one reference clip, capped at max_duration seconds."""
    if not pieces:
        return None
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    list_file = out_path + ".txt"
    with open(list_file, "w", encoding="utf-8") as f:
        for p in pieces:
            f.write(f"file '{os.path.abspath(p)}'\n")
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_file,
             "-t", str(max_duration), "-ac", "1", out_path],
            capture_output=True, timeout=120, check=True,
        )
        if os.path.exists(out_path) and os.path.getsize(out_path) > 2000:
            return out_path
    except Exception as e:
        logger.error(f"Reference concat failed: {e}")
    finally:
        try:
            os.remove(list_file)
        except OSError:
            pass
    return None


def download_clip(url: str, output_dir: str, max_duration: int = 30) -> str | None:
    if not is_available():
        return None
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "reference_audio.wav")
    try:
        subprocess.run(
            _YTDLP + [
                url,
                "-x", "--audio-format", "wav",
                # Trim to the first max_duration seconds for a clean short reference.
                "--postprocessor-args", f"ffmpeg:-t {max_duration}",
                "-o", output_path,
                "--force-overwrites", "--no-playlist",
            ],
            capture_output=True, timeout=180, check=True,
        )
        if os.path.exists(output_path) and os.path.getsize(output_path) > 2000:
            return output_path
    except Exception as e:
        logger.error(f"Voice download failed: {e}")
    return None
