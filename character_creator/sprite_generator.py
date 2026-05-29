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
import json
import httpx
from pathlib import Path

# Track background generation tasks
_generation_tasks = {}

# Global semaphore — Pollinations allows only 1 concurrent request per IP
_pollinations_lock = None

def _get_pollinations_lock():
    global _pollinations_lock
    if _pollinations_lock is None:
        _pollinations_lock = asyncio.Semaphore(1)
    return _pollinations_lock

_SPRITE_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "sprite_config.json")

def load_sprite_config() -> dict:
    try:
        with open(_SPRITE_CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"backend": "auto", "hf_token": "", "a1111_url": "http://localhost:7860", "comfyui_url": "http://localhost:8188"}

def save_sprite_config(cfg: dict):
    with open(_SPRITE_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)

def _is_valid_image(data: bytes) -> bool:
    return (data[:4] == b'\x89PNG' or data[:3] == b'\xff\xd8\xff' or
            data[:4] == b'RIFF' or data[:6] in (b'GIF87a', b'GIF89a'))

def _try_remove_background(image_bytes: bytes, output_path: str):
    """Try rembg background removal; on failure just write raw bytes."""
    try:
        from rembg import remove
        from PIL import Image
        import io
        img = remove(Image.open(io.BytesIO(image_bytes)))
        img.save(output_path)
        return
    except (ImportError, SystemExit):
        pass
    except Exception as e:
        logger.warning(f"Background removal failed: {e}")
    with open(output_path, "wb") as f:
        f.write(image_bytes)


# ── Generation backends ───────────────────────────────────────────────────────

async def _generate_pollinations(prompt: str) -> bytes | None:
    """Cloud generation via Pollinations.ai. Free, no auth, ~60-90s/img, rate-limited.
    
    Uses a module-level semaphore so only one request fires at a time — prevents
    multiple character generation tasks from competing and all hitting 402.
    """
    import urllib.parse
    encoded = urllib.parse.quote(prompt)
    url = f"https://image.pollinations.ai/prompt/{encoded}?width=768&height=1024&nologo=true"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    lock = _get_pollinations_lock()
    async with lock:  # only ONE Pollinations request at a time, globally
        for attempt in range(8):
            try:
                async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
                    resp = await client.get(url, headers=headers)
                    if resp.status_code == 402:
                        logger.warning(f"Pollinations rate-limited (402), waiting 30s…")
                        await asyncio.sleep(30)
                        continue
                    if resp.status_code == 200 and _is_valid_image(resp.content) and len(resp.content) > 5000:
                        return resp.content
                    logger.warning(f"Pollinations attempt {attempt+1}: HTTP {resp.status_code}, {len(resp.content)} bytes")
                    await asyncio.sleep(10)
            except Exception as e:
                logger.warning(f"Pollinations attempt {attempt+1} error: {e}")
                await asyncio.sleep(10)
    return None


async def _generate_huggingface(prompt: str, hf_token: str) -> bytes | None:
    """Cloud generation via HuggingFace Inference API. Free with account, fast."""
    # FLUX.1-schnell is fast and high quality; falls back to SDXL
    models = [
        "black-forest-labs/FLUX.1-schnell",
        "stabilityai/stable-diffusion-xl-base-1.0",
    ]
    headers = {"Authorization": f"Bearer {hf_token}", "Content-Type": "application/json"}
    payload = {"inputs": prompt, "parameters": {"width": 768, "height": 1024}}

    for model in models:
        url = f"https://api-inference.huggingface.co/models/{model}"
        for attempt in range(4):
            try:
                async with httpx.AsyncClient(timeout=120) as client:
                    resp = await client.post(url, json=payload, headers=headers)
                    if resp.status_code == 503:
                        # Model loading — wait and retry
                        wait = resp.json().get("estimated_time", 30) if resp.headers.get("content-type","").startswith("application/json") else 30
                        logger.info(f"HF model {model} loading, waiting {wait}s...")
                        await asyncio.sleep(min(float(wait), 60))
                        continue
                    if resp.status_code == 200 and _is_valid_image(resp.content) and len(resp.content) > 5000:
                        return resp.content
                    logger.warning(f"HF {model} attempt {attempt+1}: HTTP {resp.status_code}, {len(resp.content)} bytes")
                    if resp.status_code in (401, 403):
                        logger.error("HF token invalid or insufficient permissions")
                        return None
                    await asyncio.sleep(10)
            except Exception as e:
                logger.warning(f"HF {model} attempt {attempt+1} error: {e}")
                await asyncio.sleep(10)
    return None


async def _generate_a1111(prompt: str, base_url: str) -> bytes | None:
    """Local generation via AUTOMATIC1111 Stable Diffusion WebUI API."""
    import base64
    url = f"{base_url.rstrip('/')}/sdapi/v1/txt2img"
    payload = {
        "prompt": prompt,
        "negative_prompt": "blurry, low quality, text, watermark, extra limbs",
        "width": 512, "height": 768,
        "steps": 20, "cfg_scale": 7,
        "sampler_name": "DPM++ 2M Karras",
    }
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("images"):
                    img_bytes = base64.b64decode(data["images"][0])
                    if _is_valid_image(img_bytes) and len(img_bytes) > 5000:
                        return img_bytes
        logger.warning(f"A1111 response: {resp.status_code}")
    except Exception as e:
        logger.warning(f"A1111 error: {e}")
    return None


async def _generate_comfyui(prompt: str, base_url: str) -> bytes | None:
    """Local generation via ComfyUI API (basic txt2img workflow)."""
    import base64, random
    url = base_url.rstrip("/")
    # Minimal SDXL workflow
    workflow = {
        "3": {"class_type": "KSampler", "inputs": {
            "seed": random.randint(0, 2**32), "steps": 20, "cfg": 7,
            "sampler_name": "euler", "scheduler": "normal", "denoise": 1,
            "model": ["4", 0], "positive": ["6", 0], "negative": ["7", 0], "latent_image": ["5", 0],
        }},
        "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "v1-5-pruned-emaonly.safetensors"}},
        "5": {"class_type": "EmptyLatentImage", "inputs": {"width": 512, "height": 768, "batch_size": 1}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["4", 1]}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"text": "blurry, low quality, watermark, extra limbs", "clip": ["4", 1]}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
        "9": {"class_type": "SaveImage", "inputs": {"images": ["8", 0], "filename_prefix": "sprite"}},
    }
    try:
        client_id = str(uuid.uuid4())
        async with httpx.AsyncClient(timeout=180) as client:
            r = await client.post(f"{url}/prompt", json={"prompt": workflow, "client_id": client_id})
            if r.status_code != 200:
                return None
            prompt_id = r.json()["prompt_id"]
            # Poll for result
            for _ in range(60):
                await asyncio.sleep(3)
                hist = await client.get(f"{url}/history/{prompt_id}")
                if hist.status_code == 200 and hist.json():
                    outputs = hist.json().get(prompt_id, {}).get("outputs", {})
                    for node_output in outputs.values():
                        for img_info in node_output.get("images", []):
                            img_r = await client.get(f"{url}/view", params={
                                "filename": img_info["filename"], "subfolder": img_info.get("subfolder",""), "type": "output"
                            })
                            if img_r.status_code == 200 and _is_valid_image(img_r.content):
                                return img_r.content
    except Exception as e:
        logger.warning(f"ComfyUI error: {e}")
    return None


async def detect_backends() -> dict:
    """Auto-detect which image generation backends are available."""
    cfg = load_sprite_config()
    result = {
        "huggingface": {"available": bool(cfg.get("hf_token")), "reason": "Token configured" if cfg.get("hf_token") else "No HF token — get one free at huggingface.co"},
        "a1111":       {"available": False, "url": cfg.get("a1111_url", "http://localhost:7860")},
        "comfyui":     {"available": False, "url": cfg.get("comfyui_url", "http://localhost:8188")},
        "pollinations": {"available": True, "reason": "Free cloud, no auth needed (90s/image, rate-limited)"},
        "current":     cfg.get("backend", "auto"),
    }
    # Probe local backends
    for key, port, path in [("a1111", "7860", "/sdapi/v1/sd-models"), ("comfyui", "8188", "/object_info")]:
        url = cfg.get(f"{key}_url", f"http://localhost:{port}")
        try:
            async with httpx.AsyncClient(timeout=3) as client:
                r = await client.get(f"{url}{path}")
                result[key]["available"] = r.status_code == 200
                result[key]["reason"] = "Running locally ✅" if r.status_code == 200 else f"Not running (HTTP {r.status_code})"
        except Exception:
            result[key]["reason"] = f"Not found at {url}"
    return result


async def generate_single_pose(char_name: str, visual_description: str, art_style: str,
                                 pose_name: str, pose_prompt: str, output_dir: str) -> dict:
    """Generate a single sprite pose using the best available backend."""
    cfg = load_sprite_config()
    style_suffix = ART_STYLE_SUFFIXES.get(art_style, ART_STYLE_SUFFIXES["3d_figurine"])
    full_prompt = pose_prompt.replace("{char}", visual_description) + style_suffix

    output_path = os.path.join(output_dir, f"{pose_name}.png")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    backend = cfg.get("backend", "auto")
    hf_token = cfg.get("hf_token", "")
    a1111_url = cfg.get("a1111_url", "http://localhost:7860")
    comfyui_url = cfg.get("comfyui_url", "http://localhost:8188")

    # Backend priority: explicit choice, or auto-detect best available
    if backend == "auto":
        order = []
        if hf_token:          order.append("huggingface")
        order.append("a1111")
        order.append("comfyui")
        order.append("pollinations")
    else:
        order = [backend, "pollinations"]  # always fall back to pollinations

    image_bytes = None
    used_backend = None

    for b in order:
        logger.info(f"Pose '{pose_name}': trying backend '{b}'")
        if b == "huggingface" and hf_token:
            image_bytes = await _generate_huggingface(full_prompt, hf_token)
        elif b == "a1111":
            image_bytes = await _generate_a1111(full_prompt, a1111_url)
        elif b == "comfyui":
            image_bytes = await _generate_comfyui(full_prompt, comfyui_url)
        elif b == "pollinations":
            image_bytes = await _generate_pollinations(full_prompt)

        if image_bytes:
            used_backend = b
            break

    if not image_bytes:
        logger.error(f"Sprite generation failed for {pose_name} — all backends exhausted")
        return {"pose": pose_name, "status": "failed", "error": "All backends failed"}

    _try_remove_background(image_bytes, output_path)
    logger.info(f"Pose '{pose_name}' done via {used_backend} ({len(image_bytes):,} bytes)")
    return {"pose": pose_name, "status": "done", "path": output_path, "backend": used_backend}

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

        # For Pollinations (slow, rate-limited): wait between sprites to be polite.
        # For fast backends (HF, A1111, ComfyUI): no wait needed.
        if idx < total - 1:
            backend_used = result.get("backend", "pollinations")
            if backend_used == "pollinations":
                logger.info(f"Sprite {completed}/{total} done via Pollinations, waiting 5s...")
                await asyncio.sleep(5)  # small gap; the semaphore handles the real rate limit
    
    _generation_tasks[task_id]["status"] = "completed"

def get_task_status(task_id: str) -> dict:
    return _generation_tasks.get(task_id, {"status": "not_found"})
