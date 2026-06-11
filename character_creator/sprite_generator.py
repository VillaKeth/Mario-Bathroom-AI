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

def _load_pollinations_token() -> str:
    """Read the Pollinations token from env or the gitignored secrets file."""
    import os
    tok = os.environ.get("POLLINATIONS_TOKEN", "").strip()
    if tok:
        return tok
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    secret = os.path.join(here, ".secrets", "pollinations_token.txt")
    try:
        with open(secret, "r", encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


# ── Pollinations cost control ────────────────────────────────────────────────
# Free path: legacy host image.pollinations.ai + model `sana` (0 pollen), but it
# enforces a 1-request-per-IP queue that is often permanently "full".
# Paid path: gen.pollinations.ai + model `flux` (Flux Schnell, 0.00175 pollen per
# image — the cheapest flat-priced image model, verified 2026-06). The paid path
# is HARD-CAPPED by a budget (default 0 = never spend) and every successful
# image is recorded in a local spend ledger.
_POLLINATIONS_PAID_MODEL = "flux"
_POLLINATIONS_PAID_COST = 0.00175
_SPEND_LEDGER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                             ".secrets", "pollinations_spend.json")


def _pollinations_budget() -> float:
    """Max pollen this app may spend, ever (ledger-tracked). 0 = free tier only."""
    env = os.environ.get("POLLINATIONS_BUDGET", "").strip()
    if env:
        try:
            return float(env)
        except ValueError:
            pass
    try:
        return float(load_sprite_config().get("pollinations_budget", 0.0))
    except (TypeError, ValueError):
        return 0.0


def _pollinations_spent() -> float:
    try:
        with open(_SPEND_LEDGER, encoding="utf-8") as f:
            return float(json.load(f).get("spent", 0.0))
    except Exception:
        return 0.0


def _record_pollinations_spend(amount: float):
    os.makedirs(os.path.dirname(_SPEND_LEDGER), exist_ok=True)
    data = {"spent": _pollinations_spent() + amount}
    with open(_SPEND_LEDGER, "w", encoding="utf-8") as f:
        json.dump(data, f)


async def _generate_pollinations(prompt: str, width: int = 768, height: int = 1024) -> bytes | None:
    """Cloud generation via Pollinations.ai, free tier first, budgeted paid fallback.

    1. Legacy host + free `sana` model (0 pollen). Often queue-blocked per IP.
    2. If a token is configured AND budget remains: gen.pollinations.ai + `flux`
       (0.00175 pollen/img), spend recorded in the local ledger. With the default
       budget of 0 this path never fires, so the account can't be drained.
    """
    import urllib.parse
    encoded = urllib.parse.quote(prompt)
    token = _load_pollinations_token()
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    lock = _get_pollinations_lock()
    async with lock:  # only ONE Pollinations request at a time, globally
        # ---- free tier (sana, legacy host) — a 402 here costs nothing ----
        free_url = (f"https://image.pollinations.ai/prompt/{encoded}"
                    f"?width={width}&height={height}&nologo=true&model=sana")
        for attempt in range(2):
            try:
                async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
                    resp = await client.get(free_url, headers=headers)
                    # Free tier sometimes returns the image WITH a 402 status —
                    # trust the body, not the code.
                    if _is_valid_image(resp.content) and len(resp.content) > 5000:
                        return resp.content
                    if resp.status_code == 402:
                        logger.warning(f"Pollinations free tier queue full (402), attempt {attempt+1}/2")
                        await asyncio.sleep(15)
                        continue
                    logger.warning(f"Pollinations free attempt {attempt+1}: HTTP {resp.status_code}")
                    await asyncio.sleep(5)
            except Exception as e:
                logger.warning(f"Pollinations free attempt {attempt+1} error: {e}")
                await asyncio.sleep(5)

        # ---- budgeted paid fallback (flux, new host) ----
        if not token:
            return None
        budget, spent = _pollinations_budget(), _pollinations_spent()
        if spent + _POLLINATIONS_PAID_COST > budget:
            if budget > 0:
                logger.warning(f"Pollinations budget exhausted ({spent:.4f}/{budget:.4f} pollen)")
            return None
        paid_url = (f"https://gen.pollinations.ai/image/{encoded}"
                    f"?model={_POLLINATIONS_PAID_MODEL}&width={width}&height={height}")
        try:
            async with httpx.AsyncClient(timeout=180, follow_redirects=True) as client:
                resp = await client.get(paid_url, headers=headers)
                if resp.status_code == 200 and _is_valid_image(resp.content) and len(resp.content) > 5000:
                    _record_pollinations_spend(_POLLINATIONS_PAID_COST)
                    logger.info(f"Pollinations paid ({_POLLINATIONS_PAID_MODEL}): "
                                f"{_POLLINATIONS_PAID_COST} pollen, total spent "
                                f"{_pollinations_spent():.4f}/{budget:.4f}")
                    return resp.content
                logger.warning(f"Pollinations paid: HTTP {resp.status_code}, {len(resp.content)} bytes")
        except Exception as e:
            logger.warning(f"Pollinations paid error: {e}")
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


async def _generate_a1111(prompt: str, base_url: str, width: int = 512, height: int = 768) -> bytes | None:
    """Local generation via AUTOMATIC1111 Stable Diffusion WebUI API."""
    import base64
    url = f"{base_url.rstrip('/')}/sdapi/v1/txt2img"
    payload = {
        "prompt": prompt,
        "negative_prompt": "blurry, low quality, text, watermark, extra limbs",
        "width": width, "height": height,
        "steps": 18, "cfg_scale": 7,
        "sampler_name": "DPM++ 2M Karras",
    }
    try:
        # Generous timeout: a 4GB GPU can take a few minutes per image with
        # memory slicing enabled. Too short → aborted render → false failure.
        async with httpx.AsyncClient(timeout=360) as client:
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
        "pollinations": {"available": True, "reason": (
            f"Free sana first; paid flux fallback {_pollinations_spent():.4f}/"
            f"{_pollinations_budget():.4f} pollen used (budget in sprite_config.json)")},
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
                                 pose_name: str, pose_prompt: str, output_dir: str,
                                 output_key: str | None = None) -> dict:
    """Generate a single sprite pose using the best available backend."""
    cfg = load_sprite_config()
    style_suffix = ART_STYLE_SUFFIXES.get(art_style, ART_STYLE_SUFFIXES["3d_figurine"])
    full_prompt = pose_prompt.replace("{char}", visual_description) + style_suffix

    sprite_key = output_key or pose_name
    output_path = os.path.join(output_dir, f"{sprite_key}.png")
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

_BACKGROUND_STYLE_SUFFIX = (", scenic wide shot, no people, no characters, empty scene, "
                            "detailed environment art, high quality")


async def generate_background(char_name: str, prompt: str, filename: str = "") -> dict:
    """Generate a landscape scene background for a character (NO rembg cutout).

    Saves to characters/<char>/backgrounds/<filename>.png and returns
    {status, filename, path, backend}.
    """
    import re
    cfg = load_sprite_config()
    full_prompt = prompt.strip() + _BACKGROUND_STYLE_SUFFIX

    if not filename:
        slug = re.sub(r"[^a-z0-9]+", "_", prompt.lower()).strip("_")[:40] or "background"
        filename = f"{slug}.png"
    if not filename.lower().endswith((".png", ".jpg", ".jpeg")):
        filename += ".png"

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_dir = os.path.join(base_dir, "characters", char_name, "backgrounds")
    os.makedirs(out_dir, exist_ok=True)
    output_path = os.path.join(out_dir, filename)

    backend = cfg.get("backend", "auto")
    hf_token = cfg.get("hf_token", "")
    a1111_url = cfg.get("a1111_url", "http://localhost:7860")

    if backend == "auto":
        order = ["pollinations", "a1111"]
        if hf_token:
            order.insert(1, "huggingface")
    else:
        order = [backend, "pollinations"]

    image_bytes = None
    used_backend = None
    for b in order:
        logger.info(f"Background '{filename}' for {char_name}: trying backend '{b}'")
        if b == "pollinations":
            image_bytes = await _generate_pollinations(full_prompt, width=1280, height=720)
        elif b == "huggingface" and hf_token:
            image_bytes = await _generate_huggingface(full_prompt, hf_token)
        elif b == "a1111":
            image_bytes = await _generate_a1111(full_prompt, a1111_url, width=768, height=432)
        elif b == "comfyui":
            image_bytes = await _generate_comfyui(full_prompt, cfg.get("comfyui_url", "http://localhost:8188"))
        if image_bytes:
            used_backend = b
            break

    if not image_bytes:
        return {"status": "failed", "error": "All backends failed", "filename": filename}

    with open(output_path, "wb") as f:
        f.write(image_bytes)
    logger.info(f"Background '{filename}' done via {used_backend} ({len(image_bytes):,} bytes)")
    return {"status": "done", "filename": filename, "path": output_path, "backend": used_backend}


def _generation_pose_plan() -> list[dict]:
    """Return the canonical client-facing sprite paths to generate."""
    plan = []
    seen_paths = set()

    for name, prompt in POSE_PROMPTS.items():
        sprite_path = EMOTION_SPRITES.get(name, SPECIAL_EMOTIONS.get(name, name))
        if sprite_path in seen_paths:
            continue
        seen_paths.add(sprite_path)
        plan.append({
            "pose_name": name,
            "sprite_path": sprite_path,
            "prompt": prompt,
        })

    for state, paths in STATE_SPRITES.items():
        for sprite_path in paths:
            if sprite_path in seen_paths:
                continue
            seen_paths.add(sprite_path)
            prompt_key = sprite_path.split("/")[-1]
            prompt = STATE_PROMPTS.get(prompt_key, STATE_PROMPTS.get(state, ""))
            plan.append({
                "pose_name": f"state_{prompt_key}",
                "sprite_path": sprite_path,
                "prompt": prompt,
            })

    return plan


def expected_sprite_count() -> int:
    return len(_generation_pose_plan())


def _sprite_file_present(output_dir: str, sprite_path: str) -> bool:
    """A planned sprite counts as present if its PNG exists and is non-trivial."""
    p = os.path.join(output_dir, f"{sprite_path}.png")
    try:
        return os.path.exists(p) and os.path.getsize(p) > 2000
    except OSError:
        return False


def find_missing_sprites(output_dir: str, plan: list[dict] | None = None) -> list[dict]:
    """Return the subset of the canonical pose plan whose PNG is missing on disk."""
    plan = plan or _generation_pose_plan()
    return [info for info in plan if not _sprite_file_present(output_dir, info["sprite_path"])]


# Max repair sweeps over still-missing sprites after the first pass.
_MAX_REPAIR_SWEEPS = 3


async def _generate_pose_list(task_id: str, char_name: str, visual_description: str,
                              art_style: str, output_dir: str, poses: list[dict],
                              results: list, base_completed: int, total: int):
    """Generate a list of poses, updating task progress. Returns count newly done."""
    newly_done = 0
    for idx, info in enumerate(poses):
        pose_name = info["pose_name"]
        sprite_path = info["sprite_path"]
        _generation_tasks[task_id]["current"] = pose_name
        _generation_tasks[task_id]["current_pose"] = sprite_path
        result = await generate_single_pose(char_name, visual_description, art_style,
                                              pose_name, info["prompt"], output_dir,
                                              output_key=sprite_path)
        results.append(result)
        if result.get("status") == "done":
            newly_done += 1
        _generation_tasks[task_id]["completed"] = base_completed + newly_done

        if idx < len(poses) - 1 and result.get("backend") == "pollinations":
            logger.info(f"Sprite {base_completed + newly_done}/{total} via Pollinations, waiting 5s...")
            await asyncio.sleep(5)
    return newly_done


async def generate_all_poses(task_id: str, char_name: str, visual_description: str,
                               art_style: str, output_dir: str):
    """Generate ALL sprite poses as a background task.

    Guarantees full coverage: after the first pass, repeatedly sweeps over any
    sprites still missing on disk (rate limits, transient failures) up to
    _MAX_REPAIR_SWEEPS times before giving up. Final status is 'completed' only
    when every planned sprite exists, else 'incomplete' with the missing list.
    """
    all_poses = _generation_pose_plan()
    total = len(all_poses)
    results = []

    _generation_tasks[task_id] = {
        "status": "running", "total": total, "completed": 0,
        "current": "", "results": results, "char_name": char_name,
    }

    # First pass over everything.
    done = await _generate_pose_list(task_id, char_name, visual_description, art_style,
                                     output_dir, all_poses, results, 0, total)

    # Repair sweeps: only re-generate sprites whose file is still missing.
    sweep = 0
    while sweep < _MAX_REPAIR_SWEEPS:
        missing = find_missing_sprites(output_dir, all_poses)
        if not missing:
            break
        sweep += 1
        present = total - len(missing)
        logger.warning(f"[sprites] {len(missing)}/{total} still missing — repair sweep "
                       f"{sweep}/{_MAX_REPAIR_SWEEPS}: {[m['sprite_path'] for m in missing]}")
        _generation_tasks[task_id]["status"] = f"repairing (sweep {sweep})"
        await asyncio.sleep(15)  # let any rate limit cool down before retrying
        await _generate_pose_list(task_id, char_name, visual_description, art_style,
                                  output_dir, missing, results, present, total)

    missing = find_missing_sprites(output_dir, all_poses)
    _generation_tasks[task_id]["completed"] = total - len(missing)
    if missing:
        _generation_tasks[task_id]["status"] = "incomplete"
        _generation_tasks[task_id]["missing"] = [m["sprite_path"] for m in missing]
        logger.error(f"[sprites] generation INCOMPLETE: {len(missing)} missing after "
                     f"{_MAX_REPAIR_SWEEPS} repair sweeps: {[m['sprite_path'] for m in missing]}")
    else:
        _generation_tasks[task_id]["status"] = "completed"
        _generation_tasks[task_id]["missing"] = []
        logger.info(f"[sprites] all {total} sprites generated for {char_name}")

def get_task_status(task_id: str) -> dict:
    return _generation_tasks.get(task_id, {"status": "not_found"})
