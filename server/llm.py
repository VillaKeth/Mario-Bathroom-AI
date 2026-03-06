"""LLM integration via Ollama for Mario's brain."""

import httpx
import json
import logging

DEBUG_LLM = True
logger = logging.getLogger(__name__)

OLLAMA_URL = "http://localhost:11434"
MODEL_NAME = "qwen2:1.5b"  # Fast model (~1-3s) for low-latency party responses


async def check_ollama():
    """Check if Ollama is running and the model is available."""
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
                logger.warning(
                    f"[DEBUG_LLM] check_ollama: {MODEL_NAME} not found. "
                    f"Run: ollama pull {MODEL_NAME}"
                )
            return has_model
    except Exception as e:
        logger.error(f"[DEBUG_LLM] check_ollama: Ollama not reachable: {e}")
        return False


async def generate_response(messages: list[dict], transcript: str = None) -> str:
    """Send messages to Ollama and get Mario's response.
    
    Args:
        messages: System/context messages from mario_prompt.build_context()
        transcript: The user's spoken text to respond to
    """
    if DEBUG_LLM:
        logger.info(f"[DEBUG_LLM] generate_response: START, transcript={transcript}")

    if transcript:
        messages.append({"role": "user", "content": transcript})

    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": 0.8,
            "top_p": 0.9,
            "num_predict": 20,  # Ultra-short for speed (~half sentence)
        },
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{OLLAMA_URL}/api/chat",
                json=payload,
                timeout=15.0,
            )
            resp.raise_for_status()
            result = resp.json()
            response_text = result["message"]["content"]
            if DEBUG_LLM:
                logger.info(f"[DEBUG_LLM] generate_response: response={response_text[:100]}")
            return response_text
    except httpx.TimeoutException:
        logger.error("[DEBUG_LLM] generate_response: Ollama timeout")
        return "Mama mia! My brain is-a taking a break! Give me a moment!"
    except Exception as e:
        logger.error(f"[DEBUG_LLM] generate_response: error: {e}")
        return "Wahoo! Something went-a wrong in my head! Let's-a try again!"
