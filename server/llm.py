"""LLM integration via Ollama for Mario's brain.

Uses streaming for faster first-token response. Keeps model warm with periodic pings.
"""

import httpx
import json
import logging
import asyncio
import os
import random
import re
import time
import threading
import hardware

DEBUG_LLM = os.environ.get("DEBUG_LLM", "").lower() in ("1", "true", "yes")
logger = logging.getLogger(__name__)

# Load config
_config_path = os.path.join(os.path.dirname(__file__), "..", "config.json")
try:
    with open(_config_path, "r", encoding="utf-8") as f:
        _config = json.load(f).get("server", {})
except Exception:
    _config = {}

def _get_ollama_url():
    """Get Ollama URL from config or environment."""
    env_url = os.environ.get("OLLAMA_URL")
    if env_url:
        return env_url
    return _config.get("ollama_url", "http://localhost:11434")

OLLAMA_URL = _get_ollama_url()
MODEL_NAME = _config.get("llm_model", "llama3")
MODEL_FALLBACK = "qwen2:1.5b"
LLM_TIMEOUT = float(_config.get("llm_timeout_seconds", 30))
LLM_NUM_PREDICT = hardware.resolve("llm_num_predict", _config.get("llm_num_predict", "auto"))
LLM_NUM_CTX = hardware.resolve("llm_num_ctx", _config.get("llm_num_ctx", "auto"))
logger.info(f"[LLM] num_predict={LLM_NUM_PREDICT}, num_ctx={LLM_NUM_CTX} (hardware tier: {hardware.get_tier()})")

_warmup_task = None

_CHARACTER_NAME = "assistant"
_CHARACTER_DISPLAY_NAME = "Assistant"


def set_character(name: str, display_name: str):
    global _CHARACTER_NAME, _CHARACTER_DISPLAY_NAME
    if name:
        _CHARACTER_NAME = name
    if display_name:
        _CHARACTER_DISPLAY_NAME = display_name


# Fallback responses when Ollama is unavailable or times out
LLM_FALLBACKS = [
    "Tell me more about that!",
    "That's interesting. What happened next?",
    "I'm listening. What's on your mind?",
    "Good one. Give me another detail.",
    "That sounds fun. How's it going?",
    "Nice. What made you think of that?",
    "I'm with you. Keep going.",
    "Okay, now you've got my attention.",
    "That paints a picture. What happened after that?",
    "I like where this is going. Tell me more.",
    "That sounds like a story. What's the best part?",
    "I'm curious. What happened right before that?",
    "That has my attention. What else should I know?",
    "You've got a point there. Keep going.",
    "That sounds memorable. How did it play out?",
    "I'm following. What happened next?",
    "That's a fun thought. What would you do with it?",
    "You make that sound interesting. Tell me more.",
    "I'm into this. Give me the next detail.",
    "That sounds like a moment. How did it end?",
    "You have my full attention. What's next?",
    "That feels important. Want to unpack it a bit?",
    "I can work with that. Give me one more detail.",
    "That sounds cool. What's your favorite part?",
]


def _default_short_fallback() -> str:
    label = (_CHARACTER_DISPLAY_NAME or _CHARACTER_NAME or "your assistant").strip()
    return f"{label} is here. What's on your mind?"

# Recent response ring buffer for repeat detection
_recent_responses: list[str] = []
_recent_responses_lock = threading.Lock()
_RECENT_MAX = 10


async def check_ollama():
    """Check if Ollama is running, model is available, and pre-warm it."""
    global MODEL_NAME
    if DEBUG_LLM:
        logger.info("[DEBUG_LLM] check_ollama: START")
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{OLLAMA_URL}/api/tags", timeout=5.0)
            models = resp.json().get("models", [])
            model_names = [m["name"] for m in models]
            if DEBUG_LLM:
                logger.info(f"[DEBUG_LLM] check_ollama: available models = {model_names}")

            has_model = any(MODEL_NAME in name for name in model_names)
            if not has_model:
                # Try fallback model
                has_fallback = any(MODEL_FALLBACK in name for name in model_names)
                if has_fallback:
                    logger.info(f"[DEBUG_LLM] {MODEL_NAME} not found, using fallback {MODEL_FALLBACK}")
                    MODEL_NAME = MODEL_FALLBACK
                else:
                    logger.warning(f"[DEBUG_LLM] Neither {MODEL_NAME} nor {MODEL_FALLBACK} found!")
                    return False

            # Pre-warm model so first real call is fast (2 attempts)
            logger.info("[DEBUG_LLM] check_ollama: warming up model...")
            warmup_start = time.time()
            for warmup_attempt in range(2):
                try:
                    await client.post(
                        f"{OLLAMA_URL}/api/chat",
                        json={
                            "model": MODEL_NAME,
                            "messages": [{"role": "user", "content": "Say hi"}],
                            "stream": False,
                            "options": {"num_predict": 1},
                        },
                        timeout=30.0,
                    )
                    logger.info(f"[DEBUG_LLM] check_ollama: model warmed in {time.time() - warmup_start:.1f}s")
                    break
                except Exception as e:
                    if warmup_attempt == 0:
                        logger.warning(f"[DEBUG_LLM] check_ollama: warmup failed, retrying: {e}")
                        await asyncio.sleep(2)
                    else:
                        logger.warning(f"[DEBUG_LLM] check_ollama: warmup failed after 2 attempts (non-fatal): {e}")

            return True
    except Exception as e:
        logger.error(f"[DEBUG_LLM] check_ollama: Ollama not reachable: {e}")
        return False


async def generate_response(messages: list[dict], transcript: str = None, model: str = None,
                            num_predict: int = None) -> dict:
    """Send messages to Ollama and get Mario's response with sentiment data.

    Uses streaming internally for faster first-token, returns complete text + sentiment.
    Dynamic temperature: higher for humor/fun, lower for questions/facts.
    Optional model parameter overrides the default MODEL_NAME for dual-model routing.
    
    Returns: {"text": str, "emotion": str, "energy": float}
    """
    use_model = model or MODEL_NAME
    logger.info(f"[LLM] generate_response: START transcript='{(transcript or '')[:60]}' model={use_model} ctx_msgs={len(messages)}")

    start = time.time()

    if transcript:
        messages.append({"role": "user", "content": transcript})
    
    # Log full context for debugging
    for i, m in enumerate(messages):
        logger.info(f"[LLM_CTX {i:02d}] {m.get('role'):9s} | {m.get('content', '')[:80]}")

    # Dynamic temperature based on input content
    base_temp = 0.85
    if transcript:
        lower = transcript.lower()
        if any(w in lower for w in ["joke", "funny", "laugh", "roast", "dare", "crazy", "wild"]):
            base_temp = 0.95  # More creative for humor
        elif any(w in lower for w in ["?", "what", "how", "why", "when", "where", "who"]):
            base_temp = 0.75  # More focused for questions
        elif any(w in lower for w in ["sad", "upset", "angry", "mad", "hate", "crying"]):
            base_temp = 0.70  # More careful/empathetic for emotional topics
    temp = base_temp + random.uniform(-0.05, 0.05)
    if DEBUG_LLM:
        logger.info(f"[DEBUG_LLM] generate: temp={temp:.2f}, base={base_temp}, model={use_model}")

    payload = {
        "model": use_model,
        "messages": messages,
        "stream": True,
        "keep_alive": "30m",
        "options": {
            "temperature": round(temp, 2),
            "top_p": 0.9,
            "num_predict": num_predict if isinstance(num_predict, int) else LLM_NUM_PREDICT,
            "num_ctx": LLM_NUM_CTX,
            "repeat_penalty": 1.15,
            "seed": random.randint(1, 2**31),
            "stop": ["\nUser:", "\nHuman:", "\nAssistant:", "\nMario:", "(OOC"],
        },
    }

    # Qwen3 / DeepSeek-R1 style hybrid models emit a chain-of-thought by default.
    # On a small GPU that reasoning wastes 20-30s per reply, and we only read the
    # final 'content' so it is discarded anyway. Disable thinking for those models
    # so replies are fast and short. Name-gated because Ollama errors if you send
    # think=false to a model that has no thinking mode.
    if any(t in str(use_model).lower() for t in ("qwen3", "deepseek-r1", "magistral")):
        payload["think"] = False

    try:
        chunks = []
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                f"{OLLAMA_URL}/api/chat",
                json=payload,
                timeout=LLM_TIMEOUT,
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                        token = data.get("message", {}).get("content", "")
                        if token:
                            chunks.append(token)
                        if data.get("done"):
                            break
                    except json.JSONDecodeError:
                        continue

        response_text = "".join(chunks).strip()
        logger.info(f"[LLM] RAW response ({len(response_text)} chars): {response_text[:200]}")
        if not response_text or len(response_text) < 3:
            logger.warning(f"[DEBUG_LLM] generate_response: empty/short response ({len(response_text)} chars), using fallback")
            fallback_text = random.choice(LLM_FALLBACKS)
            return {"text": fallback_text, "emotion": "neutral", "energy": 0.5, "was_fallback": True}

        # Import emotions module for sentiment extraction
        try:
            from . import emotions
        except ImportError:
            import emotions
        
        # Extract emotion and energy from LLM response, get clean text
        sentiment_data = emotions.extract_emotion_tag(response_text)
        response_text = sentiment_data["clean_text"]
        extracted_emotion = sentiment_data["emotion"]
        extracted_energy = sentiment_data["energy"]
        
        response_text = _clean_response(response_text)

        # Repeat detection — fuzzy similarity check against recent responses
        response_lower = response_text.lower().strip()
        is_repeat = False
        with _recent_responses_lock:
            for r in _recent_responses:
                r_lower = r.lower().strip()
                if response_lower == r_lower:
                    is_repeat = True
                    break
                # Fuzzy check: if responses share >80% of words, consider repeat
                if len(response_lower) > 20 and len(r_lower) > 20:
                    words_new = set(response_lower.split())
                    words_old = set(r_lower.split())
                    if words_new and words_old:
                        overlap = len(words_new & words_old) / max(len(words_new), len(words_old))
                        if overlap > 0.80:
                            is_repeat = True
                            break
        if is_repeat:
            logger.info(f"[DEBUG_LLM] generate_response: repeat/similar detected, using fallback")
            response_text = random.choice(LLM_FALLBACKS)
            return {"text": response_text, "emotion": "neutral", "energy": 0.5, "was_fallback": True}
        
        # Track recent responses
        with _recent_responses_lock:
            _recent_responses.append(response_text)
            if len(_recent_responses) > _RECENT_MAX:
                _recent_responses.pop(0)

        elapsed = time.time() - start
        if DEBUG_LLM:
            logger.info(f"[DEBUG_LLM] generate_response: {elapsed:.1f}s response={response_text[:100]} emotion={extracted_emotion} energy={extracted_energy}")
        
        return {"text": response_text, "emotion": extracted_emotion, "energy": extracted_energy}

    except httpx.TimeoutException:
        elapsed = time.time() - start
        logger.warning(f"[DEBUG_LLM] generate_response: timeout after {elapsed:.1f}s, using fallback")
        fallback_text = random.choice(LLM_FALLBACKS)
        return {"text": fallback_text, "emotion": "neutral", "energy": 0.5, "was_fallback": True}
    except Exception as e:
        logger.error(f"[DEBUG_LLM] generate_response: error: {e}")
        fallback_text = random.choice(LLM_FALLBACKS)
        return {"text": fallback_text, "emotion": "neutral", "energy": 0.5, "was_fallback": True}


def _clean_response(text: str) -> str:
    """Clean up LLM response artifacts."""
    # Remove thinking tags, brackets, meta-commentary
    text = re.sub(r'\[.*?\]', '', text)
    text = re.sub(r'\(.*?OOC.*?\)', '', text, flags=re.IGNORECASE)
    text = re.sub(r'<.*?>', '', text)  # Remove HTML-like tags
    # Remove "Mario:" or similar role prefixes
    text = re.sub(r'^(?:Mario|Assistant|AI|Bot|System|User)\s*:\s*', '', text, flags=re.IGNORECASE)
    # Remove leading/trailing quotes if wrapping entire response
    text = text.strip()
    if text.startswith('"') and text.endswith('"') and text.count('"') == 2:
        text = text[1:-1]
    if text.startswith("'") and text.endswith("'") and text.count("'") == 2:
        text = text[1:-1]
    # Remove parenthetical stage directions like (laughs) (excited)
    text = re.sub(r'\((?:laughs?|sighs?|giggles?|pauses?|excited|nervous|whispers?|shouts?|winks?|smiles?|grins?|nods?|waves?|jumps?|dances?|flexes?|claps?|cheers?|bows?)\)', '', text, flags=re.IGNORECASE)
    # Markdown emphasis / *action* markers (*jumps*, **Rudi**): strip the MARKERS but
    # KEEP the words, so the bot still SAYS them (and analyze_text can still read them
    # for a sprite pose). Replace each run with a space so space-less markers don't
    # mash adjacent words; tidy any space left before punctuation.
    text = re.sub(r'\*+', ' ', text)
    text = re.sub(r'\s+([.,!?;:])', r'\1', text)
    # Collapse excessive whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    # Remove trailing incomplete sentences (no period/!/?)
    if text and text[-1] not in '.!?♪"\'*':
        last_end = max(text.rfind('.'), text.rfind('!'), text.rfind('?'), text.rfind('♪'))
        if last_end > len(text) * 0.4:
            text = text[:last_end + 1]
    # Remove repetitive exclamations (e.g., "Wahoo! Wahoo! Wahoo!")
    text = re.sub(r'(\b\w+!)\s*\1', r'\1', text)
    # Remove double/triple punctuation (e.g., "!!!" -> "!", "..." -> ",")
    text = re.sub(r'([!?])\1{2,}', r'\1\1', text)
    # Strip ellipsis — TTS garbles "..." even though prompt says not to use them
    text = text.replace('…', ', ')
    text = re.sub(r'\.{2,}', ', ', text)
    text = re.sub(r'^[\s,]+', '', text)  # Clean leading comma artifacts
    text = re.sub(r',\s*([!?])', r'\1', text)  # ", !" → "!"
    # Ensure non-empty and meaningful (minimum 3 chars for a real word)
    if not text.strip() or len(text.strip()) < 3:
        text = _default_short_fallback()
    # No length cap here: response length policy is config-owned
    # (response_char_ceiling via LiveConfig, enforced in main.py) so replies
    # are never silently amputated by a buried constant.
    return text


async def keepalive_loop(interval_seconds: int = 240):
    """Periodically ping Ollama to keep the model loaded in VRAM.
    
    Default Ollama unloads after 5 minutes. This pings every 4 minutes
    with a minimal 1-token request to prevent unloading during the party.
    """
    while True:
        await asyncio.sleep(interval_seconds)
        try:
            async with httpx.AsyncClient() as client:
                await client.post(
                    f"{OLLAMA_URL}/api/chat",
                    json={
                        "model": MODEL_NAME,
                        "messages": [{"role": "user", "content": "hi"}],
                        "stream": False,
                        "keep_alive": "30m",
                        "options": {"num_predict": 1},
                    },
                    timeout=15.0,
                )
            if DEBUG_LLM:
                logger.debug("[DEBUG_LLM] keepalive: model ping OK")
        except Exception as e:
            logger.warning(f"[DEBUG_LLM] keepalive: ping failed: {e}")
