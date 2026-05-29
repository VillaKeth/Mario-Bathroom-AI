"""Sprite generator — wraps SubNP pipeline for character pose generation."""
import os
import sys
import logging
import json

logger = logging.getLogger(__name__)

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))

# Canonical emotion sprites (25 unique paths)
EMOTION_SPRITES = {
    "happy": "positive/happy",
    "excited": "positive/excited",
    "laughing": "positive/laughing",
    "love": "positive/love",
    "proud": "positive/proud",
    "sad": "negative/sad",
    "angry": "negative/angry",
    "annoyed": "negative/annoyed",
    "nervous": "negative/nervous",
    "scared": "negative/scared",
    "embarrassed": "negative/embarrassed",
    "disgusted": "negative/disgusted",
    "grossed_out": "negative/grossed_out",
    "confused": "thinking/confused",
    "thinking": "thinking/thinking",
    "curious": "thinking/curious",
    "determined": "thinking/determined",
    "mischievous": "thinking/mischievous",
    "shocked": "thinking/shocked",
    "idea": "thinking/idea",
    "surprised": "thinking/surprised",
    "mind_blown": "reactions/mind_blown",
    "sassy": "reactions/sassy",
    "cringe": "reactions/cringe",
    "impressed": "reactions/impressed",
}

EMOTION_ALIASES = {
    "loving": "positive/love",
    "frustrated": "negative/annoyed",
    "worried": "negative/nervous",
    "solemn": "memorial/moment_of_silence",
    "celebratory": "party/celebrate",
    "bored": "sleep/yawning",
}

SPECIAL_EMOTIONS = {
    "sleepy": "sleep/sleepy",
    "neutral": "neutral/idle",
    "memorial": "memorial/moment_of_silence",
    "toast": "toast/raising_glass",
    "party": "party/celebrate",
    "birthday": "birthday/birthday",
}

# State sprites (9 states, 11 unique images including array variants)
STATE_SPRITES = {
    "idle": ["neutral/idle"],
    "talking": ["speech/talking", "speech/talking_excited"],
    "listening": ["speech/listening"],
    "greeting": ["greeting/wave"],
    "thinking": ["thinking/thinking"],
    "sleeping": ["sleep/sleeping"],
    "dancing": ["movement/dancing", "party/celebrate"],
    "entering": ["movement/entering"],
    "exiting": ["greeting/farewell"],
}

ALL_EMOTIONS = {**EMOTION_SPRITES, **SPECIAL_EMOTIONS}

POSE_PROMPTS = {
    "happy": "{char} with a warm genuine smile, arms open, welcoming happy pose",
    "excited": "{char} jumping with excitement, fist pumped, huge grin",
    "laughing": "{char} laughing hard, head thrown back, genuine amusement",
    "love": "{char} with heart eyes, hands clasped near face, love-struck expression",
    "proud": "{char} standing tall, hands on hips, chin up, supremely confident proud pose",
    "sad": "{char} looking down sadly, shoulders slumped, disappointed expression",
    "angry": "{char} with intense angry expression, fists clenched, leaning forward",
    "annoyed": "{char} with arms crossed, one eyebrow raised, clearly unimpressed look",
    "nervous": "{char} looking nervously to the side, hands fidgeting, uncertain expression",
    "scared": "{char} jumping back with wide eyes, arms up in surprise, startled and scared",
    "embarrassed": "{char} scratching back of head sheepishly, embarrassed half-smile",
    "disgusted": "{char} leaning away with disgusted face, hand up in stop gesture",
    "grossed_out": "{char} holding nose in disgust, leaning away, revolted face",
    "confused": "{char} with head tilted, confused expression, one eyebrow raised high",
    "thinking": "{char} looking upward thoughtfully, finger tapping chin, pondering",
    "curious": "{char} leaning forward with curiosity, eyes bright, interested expression",
    "determined": "{char} with intense focused eyes, determined expression, leaning forward",
    "mischievous": "{char} with a mischievous grin, fingers steepled, plotting look",
    "shocked": "{char} with mouth wide open in shock, eyes huge, absolutely stunned",
    "idea": "{char} with index finger raised, bright idea moment, excited eyes",
    "surprised": "{char} doing a dramatic double take, wide eyes, surprised",
    "mind_blown": "{char} with hands on sides of head, amazed shocked expression",
    "sassy": "{char} with hand on hip, head tilted, finger wagging, sassy attitude",
    "cringe": "{char} cringing hard, one eye closed, teeth gritted, looking away",
    "impressed": "{char} nodding approvingly, arms crossed, raised eyebrow, genuine respect",
    "sleepy": "{char} mid-yawn, hand covering mouth, half-closed eyes, sleepy",
    "neutral": "{char} standing relaxed, casual confident stance, neutral expression",
    "memorial": "{char} with head bowed, one hand over heart, solemn respectful pose",
    "toast": "{char} raising a glass high, confident smile, toasting",
    "party": "{char} raising both arms in celebration, huge grin, confetti around",
    "birthday": "{char} holding a birthday cake with candles, warm smile",
}

STATE_PROMPTS = {
    "idle": "{char} standing relaxed in a casual idle pose",
    "talking": "{char} gesturing with one hand while speaking, animated expression",
    "talking_excited": "{char} gesturing enthusiastically with both hands, excited while talking",
    "listening": "{char} with head slightly tilted, attentive listening pose",
    "wave": "{char} waving hello, big smile, welcoming gesture",
    "sleeping": "{char} curled up sleeping, peaceful expression",
    "dancing": "{char} doing a fun dance move, energetic and happy",
    "entering": "{char} walking in confidently, dramatic entrance",
    "farewell": "{char} waving goodbye, looking back with a smile",
}

ART_STYLE_SUFFIXES = {
    "3d_figurine": ", 3D rendered figurine style, clean gray studio background, full body shot, highly detailed, high quality, soft studio lighting",
    "anime": ", anime art style, cel-shaded, clean lines, vibrant colors, full body shot, studio background",
    "pixel_art": ", pixel art style, 16-bit, clean pixelated edges, retro game aesthetic, full body",
    "realistic": ", photorealistic 3D render, unreal engine style, detailed textures, studio lighting, full body",
    "cartoon": ", cartoon style, bold outlines, bright colors, expressive, full body shot, clean background",
}

def get_all_poses() -> dict:
    """Return the full pose matrix for the wizard UI."""
    unique_emotions = []
    seen_paths = set()
    for name, path in {**EMOTION_SPRITES, **SPECIAL_EMOTIONS}.items():
        if path not in seen_paths:
            seen_paths.add(path)
            unique_emotions.append({
                "name": name,
                "path": path,
                "category": path.split("/")[0],
                "prompt_template": POSE_PROMPTS.get(name, ""),
            })

    states = []
    for state_name, paths in STATE_SPRITES.items():
        states.append({
            "name": state_name,
            "paths": paths,
            "prompts": [STATE_PROMPTS.get(p.split("/")[-1], "") for p in paths],
        })

    return {"emotions": unique_emotions, "states": states}

import asyncio
import uuid
import httpx
from pathlib import Path

# Track background generation tasks
_generation_tasks = {}

def _is_valid_image(data: bytes) -> bool:
    """Check if bytes are a real image (PNG or JPEG magic bytes)."""
    return (data[:4] == b'\x89PNG' or data[:3] == b'\xff\xd8\xff' or
            data[:4] == b'RIFF' or data[:6] in (b'GIF87a', b'GIF89a'))


async def generate_single_pose(char_name: str, visual_description: str, art_style: str,
                                 pose_name: str, pose_prompt: str, output_dir: str) -> dict:
    """Generate a single sprite pose using Pollinations.ai (free, no auth required).

    Pollinations free tier: 1 concurrent request per IP, ~90s cooldown between requests.
    Retries up to 8 times; waits 90s on rate-limit (402) or small-file responses.
    """
    import urllib.parse
    style_suffix = ART_STYLE_SUFFIXES.get(art_style, ART_STYLE_SUFFIXES["3d_figurine"])
    full_prompt = pose_prompt.replace("{char}", visual_description) + style_suffix

    output_path = os.path.join(output_dir, f"{pose_name}.png")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    encoded = urllib.parse.quote(full_prompt)
    url = f"https://image.pollinations.ai/prompt/{encoded}?width=768&height=1024&nologo=true"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    for attempt in range(8):
        try:
            async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
                resp = await client.get(url, headers=headers)

                if resp.status_code == 402:
                    wait = 90
                    logger.warning(f"Pose '{pose_name}' rate-limited (402), waiting {wait}s...")
                    await asyncio.sleep(wait)
                    continue

                if resp.status_code != 200:
                    logger.warning(f"Pose '{pose_name}' attempt {attempt+1}: HTTP {resp.status_code}, waiting 20s")
                    await asyncio.sleep(20)
                    continue

                if not _is_valid_image(resp.content):
                    logger.warning(f"Pose '{pose_name}' attempt {attempt+1}: not a valid image ({len(resp.content)} bytes), waiting 20s")
                    await asyncio.sleep(20)
                    continue

                if len(resp.content) < 5000:
                    logger.warning(f"Pose '{pose_name}' attempt {attempt+1}: too small ({len(resp.content)} bytes), waiting 20s")
                    await asyncio.sleep(20)
                    continue

                with open(output_path, "wb") as f:
                    f.write(resp.content)

                # Try background removal with rembg
                try:
                    from rembg import remove
                    from PIL import Image
                    import io
                    input_img = Image.open(io.BytesIO(resp.content))
                    output_img = remove(input_img)
                    output_img.save(output_path)
                except (ImportError, SystemExit):
                    pass  # rembg not installed, keep raw image
                except Exception as e:
                    logger.warning(f"Background removal failed for {pose_name}: {e}")

                logger.info(f"Pose '{pose_name}' done ({len(resp.content):,} bytes)")
                return {"pose": pose_name, "status": "done", "path": output_path}

        except Exception as e:
            logger.warning(f"Pose '{pose_name}' attempt {attempt+1} error: {e}, waiting 20s")
            await asyncio.sleep(20)

    logger.error(f"Sprite generation failed for {pose_name} after 8 attempts")
    return {"pose": pose_name, "status": "failed", "error": "All attempts failed"}

async def generate_all_poses(task_id: str, char_name: str, visual_description: str,
                               art_style: str, output_dir: str):
    """Generate all sprite poses as a background task."""
    all_poses = {}
    for name, prompt in POSE_PROMPTS.items():
        category = EMOTION_SPRITES.get(name, SPECIAL_EMOTIONS.get(name, name))
        all_poses[name] = {"prompt": prompt, "category": category}
    for name, prompt in STATE_PROMPTS.items():
        all_poses[f"state_{name}"] = {"prompt": prompt, "category": f"states/{name}"}
    
    total = len(all_poses)
    completed = 0
    results = []
    
    _generation_tasks[task_id] = {
        "status": "running", "total": total, "completed": 0,
        "current": "", "results": results, "char_name": char_name,
    }
    
    for idx, (pose_name, info) in enumerate(all_poses.items()):
        _generation_tasks[task_id]["current"] = pose_name
        result = await generate_single_pose(char_name, visual_description, art_style,
                                              pose_name, info["prompt"], output_dir)
        results.append(result)
        completed += 1
        _generation_tasks[task_id]["completed"] = completed

        # Pollinations free tier requires ~90s between requests
        if idx < total - 1:
            logger.info(f"Sprite {completed}/{total} done, waiting 90s for rate limit...")
            await asyncio.sleep(90)
    
    _generation_tasks[task_id]["status"] = "completed"

def get_task_status(task_id: str) -> dict:
    return _generation_tasks.get(task_id, {"status": "not_found"})
