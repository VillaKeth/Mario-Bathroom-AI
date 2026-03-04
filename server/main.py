"""Mario AI Server — FastAPI WebSocket server.

Handles all heavy AI processing:
- Speech-to-text (faster-whisper)
- Speaker identification (resemblyzer)
- LLM conversation (Ollama)
- Text-to-speech (Edge TTS)
- Memory management (SQLite)
- Emotion system
- Party statistics
- Safety filtering
- Idle behavior / autonomous actions
"""

import asyncio
import json
import logging
import os
import time
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from contextlib import asynccontextmanager

import stt
import tts
import llm
import speaker_id
import memory
import mario_prompt
from emotions import EmotionSystem
from party_stats import PartyStats
from safety_filter import filter_response, check_input
from idle_behavior import IdleBehavior

DEBUG_SERVER = True
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("mario-server")

# Load config
CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")
config = {}
if os.path.exists(CONFIG_PATH):
    with open(CONFIG_PATH) as f:
        config = json.load(f)
    logger.info(f"Loaded config from {CONFIG_PATH}")
server_config = config.get("server", {})

# Systems
emotion_system = EmotionSystem()
party_stats = PartyStats()
idle_behavior = IdleBehavior()

# Track current conversation state
state_current = {
    "speaker_name": None,
    "speaker_id": None,
    "is_speaking": False,
    "presence": False,
    "audio_buffer": bytearray(),
    "conversation_history": [],
    "current_visit_id": None,
    "enter_time": None,
    "_last_audio_chunk": None,
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize all AI models on startup."""
    logger.info("=== Mario AI Server Starting ===")

    logger.info("Loading speech-to-text model...")
    stt.init_model(
        model_size=server_config.get("stt_model_size", "base"),
        device=server_config.get("stt_device", "auto"),
    )

    logger.info("Loading TTS engine...")
    tts.init_tts()

    logger.info("Loading speaker identification...")
    speaker_id.init_speaker_id()

    logger.info("Initializing memory system...")
    memory.init_memory()

    logger.info("Checking Ollama connection...")
    if server_config.get("llm_model"):
        llm.MODEL_NAME = server_config["llm_model"]
    has_model = await llm.check_ollama()
    if not has_model:
        logger.warning(f"⚠ Ollama model '{llm.MODEL_NAME}' not found! Run: ollama pull {llm.MODEL_NAME}")

    logger.info("=== Mario AI Server Ready! Let's-a go! ===")
    yield
    logger.info("=== Mario AI Server Shutting Down ===")


app = FastAPI(title="Mario AI Server", lifespan=lifespan)


@app.get("/health")
async def health():
    stats = party_stats.get_stats()
    return {
        "status": "ok",
        "message": "It's-a me, Mario!",
        "emotion": emotion_system.current,
        "total_visits": stats["total_visits"],
        "party_duration": stats["party_duration"],
    }


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    logger.info("Client connected!")

    # Send initial greeting with sound effect cue
    greeting_ctx = mario_prompt.build_context(event="idle")
    greeting_ctx.append({"role": "system", "content": emotion_system.get_prompt_addition()})
    greeting_text = await llm.generate_response(greeting_ctx)
    greeting_text = filter_response(greeting_text)
    greeting_audio = tts.synthesize(greeting_text)
    await send_response(ws, greeting_text, greeting_audio, sound="greeting")

    # Start idle behavior loop
    idle_task = asyncio.create_task(_idle_loop(ws))

    try:
        while True:
            data = await ws.receive()

            if "bytes" in data and data["bytes"]:
                await handle_audio(ws, data["bytes"])
            elif "text" in data and data["text"]:
                await handle_event(ws, json.loads(data["text"]))

    except WebSocketDisconnect:
        logger.info("Client disconnected")
    except Exception as e:
        if "disconnect" in str(e).lower():
            logger.info("Client disconnected")
        else:
            logger.error(f"WebSocket error: {e}")
    finally:
        idle_task.cancel()


async def _idle_loop(ws: WebSocket):
    """Background loop for idle behavior — Mario mumbles/sings when alone."""
    while True:
        await asyncio.sleep(5)

        if state_current["presence"]:
            # Check for long stays
            if state_current["enter_time"]:
                minutes = (time.time() - state_current["enter_time"]) / 60
                comment = idle_behavior.get_long_stay_comment(minutes)
                if comment:
                    audio = tts.synthesize(comment)
                    try:
                        await send_response(ws, comment, audio, sound="coin")
                    except Exception:
                        pass
            continue

        # Not present — do idle behavior
        action = idle_behavior.get_idle_action()
        if action:
            emotion_system.update()
            try:
                # Sometimes use LLM for richer idle behavior
                if len(action) > 5 and not action.startswith("♪") and not action.startswith("*"):
                    audio = tts.synthesize(action)
                    await send_response(ws, action, audio)
                else:
                    # Short actions (humming, actions) — just send text
                    await ws.send_json({
                        "type": "mario_response",
                        "text": action,
                        "has_audio": False,
                        "emotion": emotion_system.current,
                        "is_idle": True,
                    })
            except Exception:
                break


async def handle_audio(ws: WebSocket, audio_bytes: bytes):
    """Process incoming audio from the client microphone."""
    if DEBUG_SERVER:
        logger.info(f"[DEBUG_SERVER] handle_audio: received {len(audio_bytes)} bytes")

    state_current["audio_buffer"].extend(audio_bytes)

    CHUNK_SIZE = 96000
    if len(state_current["audio_buffer"]) < CHUNK_SIZE:
        return

    audio_chunk = bytes(state_current["audio_buffer"][:CHUNK_SIZE])
    state_current["audio_buffer"] = state_current["audio_buffer"][CHUNK_SIZE:]
    state_current["_last_audio_chunk"] = audio_chunk  # Save for name registration

    # Run STT + speaker ID in parallel
    loop = asyncio.get_event_loop()
    transcript_task = loop.run_in_executor(None, stt.transcribe, audio_chunk)
    speaker_task = loop.run_in_executor(None, speaker_id.identify_speaker, audio_chunk)

    transcript, speaker_info = await asyncio.gather(transcript_task, speaker_task)

    if not transcript or transcript.strip() == "":
        if DEBUG_SERVER:
            logger.info("[DEBUG_SERVER] handle_audio: no speech detected")
        return

    logger.info(f"Heard: '{transcript}' from {speaker_info.get('name', 'unknown')}")

    # Send "thinking" state to client for latency masking
    try:
        await ws.send_json({"type": "state", "thinking": True, "subtitle": transcript})
    except Exception:
        pass

    # Safety check on input
    safety = check_input(transcript)
    if not safety["safe"]:
        logger.warning(f"[SAFETY] Unsafe input detected, redirecting")
        redirect_audio = tts.synthesize(safety["redirect"])
        await send_response(ws, safety["redirect"], redirect_audio)
        return

    # Update emotion based on speech
    emotion_system.update(event="speech_detected", transcript=transcript)
    idle_behavior.reset_timer()

    # Update speaker state
    if speaker_info and not speaker_info["is_new"]:
        state_current["speaker_name"] = speaker_info["name"]
        state_current["speaker_id"] = speaker_info["speaker_id"]
    elif speaker_info and speaker_info["is_new"] and state_current["speaker_name"] is None:
        # Unknown speaker — Mario should ask their name
        pass

    # Check for special commands in transcript
    response_text = await _handle_special_commands(transcript)
    if response_text is None:
        # Normal conversation
        memories = []
        if state_current["speaker_id"]:
            memories = memory.get_memories_for_context(state_current["speaker_id"])

        ctx = mario_prompt.build_context(
            speaker_name=state_current["speaker_name"],
            memories=memories,
        )

        # Add emotion context
        ctx.append({"role": "system", "content": emotion_system.get_prompt_addition()})

        # Add party stats context
        ctx.append({"role": "system", "content": party_stats.get_stats_for_prompt()})

        # Add conversation history
        for msg in state_current["conversation_history"][-6:]:
            ctx.append(msg)

        response_text = await llm.generate_response(ctx, transcript)

    # Safety filter on output
    response_text = filter_response(response_text)
    logger.info(f"Mario says: '{response_text}'")

    # Save conversation
    state_current["conversation_history"].append({"role": "user", "content": transcript})
    state_current["conversation_history"].append({"role": "assistant", "content": response_text})

    if state_current["speaker_id"]:
        memory.save_conversation(state_current["speaker_id"], "user", transcript)
        memory.save_conversation(state_current["speaker_id"], "mario", response_text)

    # Generate speech with emotion-adjusted parameters
    voice_params = emotion_system.get_voice_params()
    response_audio = await loop.run_in_executor(
        None, lambda: tts.synthesize(response_text, rate=voice_params.get("rate"), pitch=voice_params.get("pitch"))
    )

    await send_response(ws, response_text, response_audio, emotion=emotion_system.current)


async def _handle_special_commands(transcript: str) -> str:
    """Handle special commands/requests in the transcript. Returns response text or None."""
    lower = transcript.lower()

    # Tell a joke
    if any(w in lower for w in ["tell me a joke", "know any jokes", "make me laugh", "say something funny"]):
        emotion_system.current = "mischievous"
        return idle_behavior.get_joke()

    # Trivia
    if any(w in lower for w in ["tell me a fact", "trivia", "fun fact", "did you know"]):
        emotion_system.current = "excited"
        return idle_behavior.get_trivia()

    # Sing
    if any(w in lower for w in ["sing", "song", "music", "hum"]):
        emotion_system.current = "happy"
        return idle_behavior.get_song()

    # Party stats
    if any(w in lower for w in ["how many people", "party stats", "how long", "statistics", "how many visits"]):
        stats = party_stats.get_stats()
        return (
            f"Wahoo! Let me-a check my notes! "
            f"Tonight we've had {stats['total_visits']} bathroom visits from "
            f"{stats['unique_visitors']} different people! "
            f"The party's been going for {stats['party_duration']}! "
            f"{'The record holder is ' + stats['most_frequent_name'] + '!' if stats['most_frequent_name'] else ''}"
        )

    # Name learning — register voice when user says their name
    if any(w in lower for w in ["my name is", "i'm called", "call me", "i am "]):
        import re
        match = re.search(r"(?:my name is|i'm called|call me|i am)\s+(\w+)", lower)
        if match:
            name = match.group(1).capitalize()
            # Register this voice with the name
            if state_current.get("_last_audio_chunk"):
                new_id = speaker_id.register_speaker(name, state_current["_last_audio_chunk"])
                memory.register_person(new_id, name)
                state_current["speaker_name"] = name
                state_current["speaker_id"] = new_id
                emotion_system.current = "excited"
                logger.info(f"Registered new speaker: {name} (id={new_id})")
                return f"Wahoo! Nice to meet-a you, {name}! I'll-a remember your voice from now on! Let's-a go!"
            else:
                state_current["speaker_name"] = name
                return f"Nice to meet-a you, {name}! Wahoo! I'll remember you!"

    # What time is it
    if any(w in lower for w in ["what time", "how late"]):
        stats = party_stats.get_stats()
        return f"It's-a {stats['current_hour']}! Time flies when you're having fun in the bathroom!"

    return None


async def handle_event(ws: WebSocket, event: dict):
    """Handle events from the client (presence, commands, etc.)."""
    event_type = event.get("type")
    if DEBUG_SERVER:
        logger.info(f"[DEBUG_SERVER] handle_event: {event_type}")

    if event_type == "presence_enter":
        state_current["presence"] = True
        state_current["conversation_history"] = []
        state_current["enter_time"] = time.time()
        emotion_system.update(event="presence_enter")
        idle_behavior.reset_timer()

        # Try to identify by audio
        if event.get("audio"):
            import base64
            audio_data = base64.b64decode(event["audio"])
            info = speaker_id.identify_speaker(audio_data)
            if not info["is_new"]:
                state_current["speaker_name"] = info["name"]
                state_current["speaker_id"] = info["speaker_id"]
                memory.record_visit(info["speaker_id"])

        # Record visit in party stats
        visit_id = party_stats.record_enter(
            person_id=state_current["speaker_id"],
            person_name=state_current["speaker_name"],
        )
        state_current["current_visit_id"] = visit_id
        party_stats.record_event("enter", state_current["speaker_name"])

        if state_current["speaker_name"]:
            memories = memory.get_memories_for_context(state_current["speaker_id"])
            ctx = mario_prompt.build_context(
                speaker_name=state_current["speaker_name"],
                memories=memories,
                event="enter_known",
                visit_count=len(memories),
                last_topic=memories[-1] if memories else "nothing special",
            )
        else:
            ctx = mario_prompt.build_context(event="enter_unknown")

        ctx.append({"role": "system", "content": emotion_system.get_prompt_addition()})

        response_text = await llm.generate_response(ctx)
        response_text = filter_response(response_text)

        # If unknown speaker, append name question
        if not state_current["speaker_name"]:
            response_text += " What's-a your name, friend?"

        response_audio = tts.synthesize(response_text)
        await send_response(ws, response_text, response_audio, sound="greeting", emotion=emotion_system.current)

    elif event_type == "presence_exit":
        state_current["presence"] = False
        emotion_system.update(event="presence_exit")

        # Record exit in party stats
        if state_current["current_visit_id"]:
            party_stats.record_exit(state_current["current_visit_id"])
        party_stats.record_event("exit", state_current["speaker_name"])

        if state_current["speaker_name"]:
            ctx = mario_prompt.build_context(
                speaker_name=state_current["speaker_name"],
                event="exit_known",
            )
        else:
            ctx = mario_prompt.build_context(event="exit_unknown")

        ctx.append({"role": "system", "content": emotion_system.get_prompt_addition()})

        response_text = await llm.generate_response(ctx)
        response_text = filter_response(response_text)
        response_audio = tts.synthesize(response_text)
        await send_response(ws, response_text, response_audio, sound="goodbye", emotion=emotion_system.current)

        # Reset state
        state_current["speaker_name"] = None
        state_current["speaker_id"] = None
        state_current["conversation_history"] = []
        state_current["current_visit_id"] = None
        state_current["enter_time"] = None

    elif event_type == "register_speaker":
        name = event.get("name", "Friend")
        audio_data = event.get("audio")
        if audio_data:
            import base64
            audio_bytes_data = base64.b64decode(audio_data)
            new_id = speaker_id.register_speaker(name, audio_bytes_data)
            memory.register_person(new_id, name)
            state_current["speaker_name"] = name
            state_current["speaker_id"] = new_id
            await ws.send_json({"type": "speaker_registered", "name": name, "id": new_id})

            # Mario celebrates registering a new friend
            celebrate = f"Wahoo! Nice to meet-a you, {name}! I'll-a remember your voice! Let's-a go!"
            celebrate_audio = tts.synthesize(celebrate)
            await send_response(ws, celebrate, celebrate_audio, sound="oneup", emotion="excited")

    elif event_type == "vad_start":
        state_current["is_speaking"] = True
        await ws.send_json({"type": "state", "listening": True})

    elif event_type == "vad_stop":
        state_current["is_speaking"] = False
        await ws.send_json({"type": "state", "listening": False})


async def send_response(ws: WebSocket, text: str, audio: bytes = None,
                        sound: str = None, emotion: str = None):
    """Send Mario's response (text + audio + metadata) to the client."""
    await ws.send_json({
        "type": "mario_response",
        "text": text,
        "has_audio": audio is not None and len(audio) > 0,
        "sound_effect": sound,
        "emotion": emotion or emotion_system.current,
        "animation": emotion_system.animation_state,
    })

    if audio and len(audio) > 0:
        await ws.send_bytes(audio)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=server_config.get("host", "0.0.0.0"),
        port=server_config.get("port", 8765),
    )
