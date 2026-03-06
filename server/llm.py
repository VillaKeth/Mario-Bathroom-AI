"""LLM integration via Ollama for Mario's brain.

Uses streaming for faster first-token response. Keeps model warm with periodic pings.
"""

import httpx
import json
import logging
import asyncio
import time

DEBUG_LLM = True
logger = logging.getLogger(__name__)

OLLAMA_URL = "http://localhost:11434"
MODEL_NAME = "qwen2:1.5b"  # Best balance of speed (~3-5s) and Mario character quality
MODEL_FALLBACK = "llama3"  # Fallback if qwen2 not available

_warmup_task = None


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

            # Pre-warm model so first real call is fast
            logger.info("[DEBUG_LLM] check_ollama: warming up model...")
            warmup_start = time.time()
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
            except Exception as e:
                logger.warning(f"[DEBUG_LLM] check_ollama: warmup failed (non-fatal): {e}")

            return True
    except Exception as e:
        logger.error(f"[DEBUG_LLM] check_ollama: Ollama not reachable: {e}")
        return False


async def generate_response(messages: list[dict], transcript: str = None) -> str:
    """Send messages to Ollama and get Mario's response.

    Uses streaming internally for faster first-token, but returns complete text.
    """
    if DEBUG_LLM:
        logger.info(f"[DEBUG_LLM] generate_response: START, transcript={transcript}")

    start = time.time()

    if transcript:
        messages.append({"role": "user", "content": transcript})

    import random
    # Slight temperature variation for response diversity
    temp = 0.85 + random.uniform(-0.05, 0.10)

    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "stream": True,
        "options": {
            "temperature": round(temp, 2),
            "top_p": 0.9,
            "num_predict": 35,
            "repeat_penalty": 1.3,
            "stop": ["\n\n", "User:", "Human:", "Assistant:", "Mario:", "[", "(OOC"],
        },
    }

    for attempt in range(2):  # One retry on timeout
        try:
            chunks = []
            async with httpx.AsyncClient() as client:
                async with client.stream(
                    "POST",
                    f"{OLLAMA_URL}/api/chat",
                    json=payload,
                    timeout=30.0,
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
            response_text = _clean_response(response_text)

            elapsed = time.time() - start
            if DEBUG_LLM:
                logger.info(f"[DEBUG_LLM] generate_response: {elapsed:.1f}s response={response_text[:100]}")
            return response_text

        except httpx.TimeoutException:
            if attempt == 0:
                logger.warning("[DEBUG_LLM] generate_response: timeout, retrying...")
                continue
            logger.error("[DEBUG_LLM] generate_response: Ollama timeout (2 attempts)")
            return "Mama mia! My brain is-a taking a break! Give me a moment!"
        except Exception as e:
            logger.error(f"[DEBUG_LLM] generate_response: error: {e}")
            return "Wahoo! Something went-a wrong in my head! Let's-a try again!"

    return "Mama mia! Mario needs-a moment to think!"


def _clean_response(text: str) -> str:
    """Clean up LLM response artifacts."""
    import re
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
    # Remove *action descriptions* like *jumps*, *laughs*
    text = re.sub(r'\*[a-z\s]+\*', '', text, flags=re.IGNORECASE)
    # Collapse excessive whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    # Remove trailing incomplete sentences (no period/!/?)
    if text and text[-1] not in '.!?♪"\'*':
        last_end = max(text.rfind('.'), text.rfind('!'), text.rfind('?'), text.rfind('♪'))
        if last_end > len(text) * 0.4:
            text = text[:last_end + 1]
    # Remove repetitive exclamations (e.g., "Wahoo! Wahoo! Wahoo!")
    text = re.sub(r'(\b\w+!)\s*\1', r'\1', text)
    # Remove double/triple punctuation (e.g., "!!!" -> "!", "..." stays)
    text = re.sub(r'([!?])\1{2,}', r'\1\1', text)
    # Ensure non-empty
    if not text.strip():
        text = "Wahoo!"
    # Cap response length for faster TTS (long text = very slow RVC on Quadro P1000)
    # Benchmarks: 18 chars→1.8s, 34 chars→1.6s, 104 chars→25.8s RVC
    if len(text) > 80:
        cut = text[:80]
        last_end = max(cut.rfind('.'), cut.rfind('!'), cut.rfind('?'))
        if last_end > 30:
            text = cut[:last_end + 1]
        else:
            text = cut.rsplit(' ', 1)[0] + '!'
    return text
