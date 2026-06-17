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

# Appended to EVERY sprite prompt. Models frame the figure flush to the canvas
# edge, clipping head/feet/arms; this forces head-to-toe framing with margin so
# nothing runs off the edge (the #1 cause of "missing body parts" sprites).
FRAMING_SUFFIX = (", entire character fully visible from head to toe, full body in frame, "
                  "centered composition, generous empty margin around the character, "
                  "wide shot, nothing cropped or cut off at the edges, standing in frame")

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
        pass
    # Fresh clone: sprite_config.json is gitignored (it holds API keys) — seed
    # it from the committed example so the wizard works with zero setup.
    example = _SPRITE_CONFIG_PATH.replace(".json", ".example.json")
    try:
        with open(example, encoding="utf-8") as f:
            cfg = json.load(f)
        save_sprite_config(cfg)
        return cfg
    except Exception:
        return {"backend": "auto", "hf_token": "", "a1111_url": "http://localhost:7860", "comfyui_url": "http://localhost:8188"}

def save_sprite_config(cfg: dict):
    with open(_SPRITE_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)

def _is_valid_image(data: bytes) -> bool:
    return (data[:4] == b'\x89PNG' or data[:3] == b'\xff\xd8\xff' or
            data[:4] == b'RIFF' or data[:6] in (b'GIF87a', b'GIF89a'))

_REMBG_SESSION = None


def _get_rembg_session():
    """Cache an isnet-general-use session — better than the default u2net at
    keeping thin/pale limbs (gloves, sleeves) that blend into the studio bg,
    which u2net tended to erase, leaving holes mid-figure."""
    global _REMBG_SESSION
    if _REMBG_SESSION is None:
        from rembg import new_session
        _REMBG_SESSION = new_session(os.environ.get("REMBG_MODEL", "isnet-general-use"))
    return _REMBG_SESSION


def _try_remove_background(image_bytes: bytes, output_path: str):
    """Try rembg background removal; on failure just write raw bytes.

    Uses isnet-general-use + alpha matting for cleaner edges and fewer holes.
    """
    try:
        from rembg import remove
        from PIL import Image
        import io
        img = remove(
            Image.open(io.BytesIO(image_bytes)),
            session=_get_rembg_session(),
            alpha_matting=True,
            alpha_matting_foreground_threshold=240,
            alpha_matting_background_threshold=10,
            alpha_matting_erode_size=10,
        )
        img.save(output_path)
        return
    except (ImportError, SystemExit):
        pass
    except Exception as e:
        logger.warning(f"Background removal failed: {e}")
        # Fall back to the default model (no matting) before giving up entirely.
        try:
            from rembg import remove
            from PIL import Image
            import io
            remove(Image.open(io.BytesIO(image_bytes))).save(output_path)
            return
        except Exception:
            pass
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
    """Cloud generation via HuggingFace Inference Providers. Free monthly credits.

    Prefers huggingface_hub.InferenceClient with provider auto-routing — that is
    the ONLY path that reaches partner-served models like FLUX.1-dev (the raw
    hf-inference REST endpoint serves schnell but 410s on dev). Falls back to
    the REST endpoint if the hub client is unavailable.
    """
    # Model try-order is configurable (sprite_config.json "hf_models") so
    # different checkpoints can be A/B tested. FLUX.1-dev first: picked by ear
    # in the 2026-06 Reze sprite A/B ("best we got"); schnell as free fallback.
    models = load_sprite_config().get("hf_models") or [
        "black-forest-labs/FLUX.1-dev",
        "black-forest-labs/FLUX.1-schnell",
        "stabilityai/stable-diffusion-xl-base-1.0",
    ]

    # Preferred path: hub client with provider auto-routing
    try:
        from huggingface_hub import InferenceClient
        import io

        def _hub_t2i(model):
            client = InferenceClient(token=hf_token, provider="auto")
            img = client.text_to_image(prompt, model=model, width=768, height=1024)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            return buf.getvalue()

        for model in models:
            try:
                data = await asyncio.to_thread(_hub_t2i, model)
                if _is_valid_image(data) and len(data) > 5000:
                    return data
            except Exception as e:
                msg = str(e)
                logger.warning(f"HF hub {model}: {msg[:120]}")
                if "402" in msg or "Payment Required" in msg:
                    return None  # credits exhausted — no point trying more models
        return None
    except ImportError:
        pass
    headers = {"Authorization": f"Bearer {hf_token}", "Content-Type": "application/json"}
    payload = {"inputs": prompt, "parameters": {"width": 768, "height": 1024}}

    for model in models:
        # api-inference.huggingface.co was retired (DNS gone) — HF moved to
        # Inference Providers at router.huggingface.co; hf-inference is the
        # provider that serves classic serverless text-to-image.
        url = f"https://router.huggingface.co/hf-inference/models/{model}"
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


# ── Premium cloud providers (Grok / OpenAI / Gemini) ─────────────────────────
# One OFFICIAL key per provider, entered in the wizard settings. The router
# rotates across DIFFERENT providers (never duplicate accounts of one service).
# Every paid image is recorded in a per-provider USD ledger and hard-capped by
# a per-provider budget (default 0 = that provider never spends).

_IMAGE_SPEND_LEDGER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                   ".secrets", "image_spend.json")

# Approx USD per image (verified 2026-06; treat as ceiling for budgeting).
_PROVIDER_COSTS = {"openai": 0.063, "grok": 0.07, "gemini": 0.039}

# Higher = tried first under the "quality" routing policy.
_PROVIDER_QUALITY = {"openai": 9, "grok": 9, "gemini": 8, "huggingface": 7,
                     "a1111": 6, "comfyui": 6, "pollinations": 5}

_provider_cooldowns: dict[str, float] = {}   # provider -> unix ts it can retry
_round_robin_idx = 0


def _provider_spent(provider: str) -> float:
    try:
        with open(_IMAGE_SPEND_LEDGER, encoding="utf-8") as f:
            return float(json.load(f).get(provider, 0.0))
    except Exception:
        return 0.0


def _provider_budget(provider: str, cfg: dict | None = None) -> float:
    cfg = cfg or load_sprite_config()
    try:
        return float(cfg.get(f"{provider}_budget", 0.0))
    except (TypeError, ValueError):
        return 0.0


def _record_provider_spend(provider: str, amount: float):
    os.makedirs(os.path.dirname(_IMAGE_SPEND_LEDGER), exist_ok=True)
    try:
        with open(_IMAGE_SPEND_LEDGER, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {}
    data[provider] = round(float(data.get(provider, 0.0)) + amount, 6)
    with open(_IMAGE_SPEND_LEDGER, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)


def _provider_can_spend(provider: str, cfg: dict | None = None) -> bool:
    return _provider_spent(provider) + _PROVIDER_COSTS.get(provider, 0.05) \
        <= _provider_budget(provider, cfg)


def _cooldown_active(provider: str) -> bool:
    import time
    return _provider_cooldowns.get(provider, 0) > time.time()


def _set_cooldown(provider: str, seconds: float):
    import time
    _provider_cooldowns[provider] = time.time() + seconds
    logger.warning(f"{provider}: rate-limited, cooling down {seconds:.0f}s")


def _retry_after(resp) -> float:
    try:
        return min(float(resp.headers.get("retry-after", 60)), 600)
    except (TypeError, ValueError):
        return 60.0


async def _generate_grok(prompt: str, key: str) -> bytes | None:
    """xAI Grok image generation (grok-2-image). Excellent character framing."""
    import base64
    url = "https://api.x.ai/v1/images/generations"
    payload = {"model": "grok-2-image", "prompt": prompt, "n": 1,
               "response_format": "b64_json"}
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(url, json=payload, headers=headers)
        if resp.status_code == 429:
            _set_cooldown("grok", _retry_after(resp))
            return None
        if resp.status_code == 200:
            data = resp.json().get("data") or []
            if data and data[0].get("b64_json"):
                img = base64.b64decode(data[0]["b64_json"])
                if _is_valid_image(img) and len(img) > 5000:
                    _record_provider_spend("grok", _PROVIDER_COSTS["grok"])
                    return img
        logger.warning(f"Grok image: HTTP {resp.status_code} {resp.text[:120]}")
    except Exception as e:
        logger.warning(f"Grok image error: {e}")
    return None


async def _generate_openai_image(prompt: str, key: str, portrait: bool = True) -> bytes | None:
    """OpenAI gpt-image-1. Strong prompt adherence and full-body framing."""
    import base64
    url = "https://api.openai.com/v1/images/generations"
    payload = {"model": "gpt-image-1", "prompt": prompt, "n": 1,
               "size": "1024x1536" if portrait else "1536x1024",
               "quality": "medium"}
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=180) as client:
            resp = await client.post(url, json=payload, headers=headers)
        if resp.status_code == 429:
            _set_cooldown("openai", _retry_after(resp))
            return None
        if resp.status_code == 200:
            data = resp.json().get("data") or []
            if data and data[0].get("b64_json"):
                img = base64.b64decode(data[0]["b64_json"])
                if _is_valid_image(img) and len(img) > 5000:
                    _record_provider_spend("openai", _PROVIDER_COSTS["openai"])
                    return img
        logger.warning(f"OpenAI image: HTTP {resp.status_code} {resp.text[:120]}")
    except Exception as e:
        logger.warning(f"OpenAI image error: {e}")
    return None


async def _generate_gemini_image(prompt: str, key: str) -> bytes | None:
    """Google Gemini image output (gemini-2.5-flash-image)."""
    import base64
    url = ("https://generativelanguage.googleapis.com/v1beta/models/"
           "gemini-2.5-flash-image:generateContent")
    payload = {"contents": [{"parts": [{"text": prompt}]}],
               "generationConfig": {"responseModalities": ["IMAGE"]}}
    headers = {"x-goog-api-key": key, "Content-Type": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(url, json=payload, headers=headers)
        if resp.status_code == 429:
            _set_cooldown("gemini", _retry_after(resp))
            return None
        if resp.status_code == 200:
            for cand in resp.json().get("candidates", []):
                for part in (cand.get("content") or {}).get("parts", []):
                    inline = part.get("inlineData") or part.get("inline_data")
                    if inline and inline.get("data"):
                        img = base64.b64decode(inline["data"])
                        if _is_valid_image(img) and len(img) > 5000:
                            _record_provider_spend("gemini", _PROVIDER_COSTS["gemini"])
                            return img
        logger.warning(f"Gemini image: HTTP {resp.status_code} {resp.text[:120]}")
    except Exception as e:
        logger.warning(f"Gemini image error: {e}")
    return None


def _premium_providers(cfg: dict) -> list[str]:
    """Premium providers that have a key, budget headroom, and no cooldown."""
    out = []
    for p in ("grok", "openai", "gemini"):
        if cfg.get(f"{p}_key") and _provider_can_spend(p, cfg) and not _cooldown_active(p):
            out.append(p)
    return out


def _backend_order(cfg: dict) -> list[str]:
    """Compute the try-order for generation based on the routing policy.

    - cheapest (default): free/local first, premium last — original behavior
      until the user adds keys AND budgets.
    - quality: highest-quality configured provider first.
    - round_robin: rotate the lead premium provider per call to spread load
      across providers; free/local appended as fallback.
    An explicit `backend` choice (not "auto") pins that backend first.
    """
    global _round_robin_idx
    backend = cfg.get("backend", "auto")
    policy = cfg.get("router_policy", "cheapest")
    premium = _premium_providers(cfg)
    free_local = []
    if cfg.get("hf_token"):
        free_local.append("huggingface")
    free_local += ["a1111", "comfyui", "pollinations"]

    if backend != "auto":
        rest = [b for b in premium + free_local if b != backend]
        return [backend] + rest

    if policy == "quality":
        ranked = sorted(premium + free_local,
                        key=lambda b: -_PROVIDER_QUALITY.get(b, 0))
        return ranked
    if policy == "round_robin" and premium:
        lead = premium[_round_robin_idx % len(premium)]
        _round_robin_idx += 1
        rest = [p for p in premium if p != lead]
        return [lead] + rest + free_local
    # cheapest
    return free_local + premium


async def _run_backend(name: str, prompt: str, cfg: dict, portrait: bool = True) -> bytes | None:
    """Dispatch one backend by name. Returns image bytes or None."""
    if name == "grok":
        return await _generate_grok(prompt, cfg.get("grok_key", ""))
    if name == "openai":
        return await _generate_openai_image(prompt, cfg.get("openai_key", ""), portrait)
    if name == "gemini":
        return await _generate_gemini_image(prompt, cfg.get("gemini_key", ""))
    if name == "huggingface":
        return await _generate_huggingface(prompt, cfg.get("hf_token", ""))
    if name == "a1111":
        w, h = (512, 768) if portrait else (768, 432)
        return await _generate_a1111(prompt, cfg.get("a1111_url", "http://localhost:7860"), w, h)
    if name == "comfyui":
        return await _generate_comfyui(prompt, cfg.get("comfyui_url", "http://localhost:8188"))
    if name == "pollinations":
        w, h = (768, 1024) if portrait else (1280, 720)
        return await _generate_pollinations(prompt, w, h)
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
        "router_policy": cfg.get("router_policy", "cheapest"),
    }
    # Premium providers: report key/budget/ledger state
    for p in ("grok", "openai", "gemini"):
        has_key = bool(cfg.get(f"{p}_key"))
        budget = _provider_budget(p, cfg)
        spent = _provider_spent(p)
        if not has_key:
            reason = "No API key set"
        elif budget <= 0:
            reason = "Key set — budget is 0, set a budget to enable"
        elif not _provider_can_spend(p, cfg):
            reason = f"Budget exhausted (${spent:.2f}/${budget:.2f})"
        else:
            reason = f"Ready — ${spent:.2f}/${budget:.2f} spent"
        result[p] = {"available": has_key and _provider_can_spend(p, cfg),
                     "reason": reason, "spent": spent, "budget": budget}
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
    full_prompt = pose_prompt.replace("{char}", visual_description) + style_suffix + FRAMING_SUFFIX

    sprite_key = output_key or pose_name
    output_path = os.path.join(output_dir, f"{sprite_key}.png")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    image_bytes = None
    used_backend = None

    for b in _backend_order(cfg):
        logger.info(f"Pose '{pose_name}': trying backend '{b}'")
        image_bytes = await _run_backend(b, full_prompt, cfg, portrait=True)
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

    image_bytes = None
    used_backend = None
    for b in _backend_order(cfg):
        logger.info(f"Background '{filename}' for {char_name}: trying backend '{b}'")
        image_bytes = await _run_backend(b, full_prompt, cfg, portrait=False)
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


def _pose_direction(key: str) -> str:
    """Canonical pose direction template for an emotion/state key. Falls back to a
    generic '{char} with a <key> expression' so custom map keys still produce a
    usable prompt."""
    p = POSE_PROMPTS.get(key) or STATE_PROMPTS.get(key)
    return p or ("{char} with a " + key.replace("_", " ") + " expression and a matching body pose")


def build_sprite_prompts_text(char_dir: str) -> tuple[str, int]:
    """Build batch-compatible sprite_prompts.txt content from a character's OWN
    character.yaml — works for canonical wizard characters AND hand-authored ones
    with custom sprite paths (mario, rudi).

    Output format is exactly what mcp_chatgpt/batch_sprites.py parses:

        [NN] sprites/<path>.png
        ----------------------------------------------------------------------
        <full self-contained image prompt>

    Each prompt = the character's visual_description + the pose direction for that
    sprite + the art-style suffix + the framing suffix — i.e. identical to what
    the wizard would send a backend (generate_single_pose), so the file always
    matches how this character actually gets drawn.

    Returns (text, n_blocks).
    """
    import yaml
    y = yaml.safe_load(open(os.path.join(char_dir, "character.yaml"), encoding="utf-8")) or {}
    vis = y.get("visuals", {}) or {}
    ident = y.get("identity", {}) or {}
    disp = ident.get("display_name") or ident.get("name") or os.path.basename(char_dir.rstrip("/\\"))
    desc = (vis.get("visual_description") or vis.get("drip_description")
            or f"{disp}, {ident.get('description', '')}".strip().rstrip(","))
    art = vis.get("art_style", "3d_figurine")
    style = ART_STYLE_SUFFIXES.get(art, ART_STYLE_SUFFIXES["3d_figurine"])

    # Unique sprite paths from the character's own maps, each tagged with the
    # emotion/state key that drives its pose direction. Emotions first, then states.
    seen: dict[str, str] = {}
    for emotion, path in (vis.get("emotion_sprite_map") or {}).items():
        if path and path not in seen:
            seen[path] = emotion
    for state, val in (vis.get("state_sprite_map") or {}).items():
        for path in (val if isinstance(val, list) else [val]):
            if path and path not in seen:
                seen[path] = state

    lines = [
        f"# {disp} — sprite image prompts (mcp_chatgpt batch format).",
        f"# art_style: {art}. Generate on a plain background; the app cuts it out.",
        "# Each block is [NN] sprites/<path>.png then the full prompt to generate.",
        "",
    ]
    for i, (path, key) in enumerate(sorted(seen.items()), 1):
        full = _pose_direction(key).replace("{char}", desc) + style + FRAMING_SUFFIX
        lines.append(f"[{i:02d}] sprites/{path}.png")
        lines.append("-" * 70)
        lines.append(full)
        lines.append("")
    return "\n".join(lines), len(seen)


def write_sprite_prompts_file(char_dir: str) -> int:
    """Write characters/<char>/sprite_prompts.txt in batch format. Returns block count.
    Called by the wizard at build time so every character ships a paste-ready,
    mcp_chatgpt-batch-ready prompt sheet (no hand-writing 39 prompts)."""
    text, n = build_sprite_prompts_text(char_dir)
    with open(os.path.join(char_dir, "sprite_prompts.txt"), "w", encoding="utf-8") as f:
        f.write(text)
    return n


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
