"""LLM integration via Ollama for Mario's brain.

Uses streaming for faster first-token response. Keeps model warm with periodic pings.
"""

import httpx
import json
import logging
import asyncio
import random
import re
import time

DEBUG_LLM = True
logger = logging.getLogger(__name__)

OLLAMA_URL = "http://localhost:11434"
MODEL_NAME = "qwen2:1.5b"  # Best balance of speed (~3-5s) and Mario character quality
MODEL_FALLBACK = "llama3"  # Fallback if qwen2 not available

_warmup_task = None

# Fallback responses when Ollama is unavailable or times out
LLM_FALLBACKS = [
    "Wahoo! Let's-a go!",
    "Mama mia! That's-a interesting!",
    "Ha ha! You're-a funny one!",
    "Okie dokie! Mario likes-a that!",
    "Bellissimo! Tell me more!",
    "That's-a so cool! What else?",
    "Magnifico! You're-a great company!",
    "Ha! That's what Luigi would say too!",
    "Mama mia, this party is-a amazing! Having fun?",
    "You remind me of a friend from the Mushroom Kingdom!",
    "I was just thinking about pasta! You hungry?",
    "Don't forget to wash-a your hands! It's-a important!",
    "This bathroom has-a great acoustics! Wahoo!",
    "You know what I love about parties? The people!",
    "Ha ha! That reminds me of the time Bowser tried to cook!",
    "Wow, you're-a really something! In a good way!",
    "I bet you could beat Bowser in a race!",
    "Speaking of pipes, this bathroom has-a nice plumbing!",
    "Are you having fun at the party? I hope so!",
    "If Princess Peach were here, she'd love this party!",
    "Ooh, that's-a spicy! Like a fire flower!",
    "You're braver than me — I always get scared of Boos!",
    "Wahoo! Every conversation is-a like a new adventure!",
    "Tell me something I don't know! Mario loves learning!",
    "Ha! You should come visit the Mushroom Kingdom sometime!",
    "Ooh, what's-a your favorite color? Mine is red, obviously!",
    "Did you know Toad can lift ten times his weight? Crazy!",
    "I wonder what Bowser is-a up to right now... probably cooking!",
    "This reminds me of World 4 — the giant world! Everything's huge!",
    "You ever play the tuba? Asking for a friend named Waluigi!",
    "Ha! I just remembered — I left my hat in Sarasaland!",
    "What do you think clouds taste like? Lakitu won't-a tell me!",
    "Daisy would love this conversation! She's-a really fun!",
    "I'm-a thinking about starting a cooking show. Mario's Kitchen!",
    "Okie dokie, pop quiz! How many coins in a coin block? Trick question!",
    "You're-a making my mustache twitch with excitement!",
    "Rosalina told me the stars are listening. Cool, right?",
    "Ever wonder why all the pipes are green? Even I don't know!",
    "Toadette baked cookies today! Wish I could share some with you!",
    "I've been to space, underwater, and a haunted house — all in one week!",
    "Luigi is-a probably hiding from ghosts right now. Poor guy!",
    "What's-a your special move? Mine is the triple jump! Yahoo!",
    "Donkey Kong and I are friends now! Took a while though, ha ha!",
    "I bet you'd be great at Mario Party! You seem-a competitive!",
    "Sometimes I just like to sit on a hill and watch the sunset. Peaceful!",
    "Kamek keeps turning things into monsters. Not cool, Kamek!",
    "Hey, what superpower would you want? I'd pick flying — oh wait, I have a cape!",
    "Shy Guys are actually pretty nice once you get to know them!",
    "The best sound in the world? Coin collecting! Cha-ching!",
    "You know what? You're-a cooler than an Ice Flower! And that's-a pretty cool!",
]

# Recent response ring buffer for repeat detection
_recent_responses: list[str] = []
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


async def generate_response(messages: list[dict], transcript: str = None) -> str:
    """Send messages to Ollama and get Mario's response.

    Uses streaming internally for faster first-token, but returns complete text.
    Dynamic temperature: higher for humor/fun, lower for questions/facts.
    """
    if DEBUG_LLM:
        logger.info(f"[DEBUG_LLM] generate_response: START, transcript={transcript}")

    start = time.time()

    if transcript:
        messages.append({"role": "user", "content": transcript})

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
        logger.info(f"[DEBUG_LLM] generate: temp={temp:.2f}, base={base_temp}, model={MODEL_NAME}")

    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "stream": True,
        "options": {
            "temperature": round(temp, 2),
            "top_p": 0.9,
            "num_predict": 50,
            "repeat_penalty": 1.3,
            "stop": ["\n\n", "\nUser:", "\nHuman:", "\nAssistant:", "\nMario:", "[", "(OOC"],
        },
    }

    try:
        chunks = []
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                f"{OLLAMA_URL}/api/chat",
                json=payload,
                timeout=8.0,
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
        if not response_text or len(response_text) < 3:
            logger.warning(f"[DEBUG_LLM] generate_response: empty/short response ({len(response_text)} chars), using fallback")
            return random.choice(LLM_FALLBACKS)
        response_text = _clean_response(response_text)

        # Repeat detection — if response is too similar to recent ones, retry once
        response_lower = response_text.lower().strip()
        is_repeat = any(response_lower == r.lower().strip() for r in _recent_responses)
        if is_repeat and not transcript:  # Only retry for non-user-prompted (idle/greeting)
            logger.info(f"[DEBUG_LLM] generate_response: repeat detected, using fallback")
            response_text = random.choice(LLM_FALLBACKS)
        
        # Track recent responses
        _recent_responses.append(response_text)
        if len(_recent_responses) > _RECENT_MAX:
            _recent_responses.pop(0)

        elapsed = time.time() - start
        if DEBUG_LLM:
            logger.info(f"[DEBUG_LLM] generate_response: {elapsed:.1f}s response={response_text[:100]}")
        return response_text

    except httpx.TimeoutException:
        elapsed = time.time() - start
        logger.warning(f"[DEBUG_LLM] generate_response: timeout after {elapsed:.1f}s, using fallback")
        return random.choice(LLM_FALLBACKS)
    except Exception as e:
        logger.error(f"[DEBUG_LLM] generate_response: error: {e}")
        return random.choice(LLM_FALLBACKS)


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
    # Ensure non-empty and meaningful (minimum 3 chars for a real word)
    if not text.strip() or len(text.strip()) < 3:
        text = "Wahoo! Let's-a go!"
    # Cap response length for faster TTS (long text = very slow RVC on Quadro P1000)
    # GPT-SoVITS handles its own 120-char truncation per sentence, so allow longer responses
    # that get streamed as 2 sentences for better conversation quality
    if len(text) > 120:
        cut = text[:120]
        last_end = max(cut.rfind('.'), cut.rfind('!'), cut.rfind('?'))
        if last_end > 40:
            text = cut[:last_end + 1]
        else:
            text = cut.rsplit(' ', 1)[0] + '!'
    return text
