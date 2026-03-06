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
from pose_analyzer import analyze_text

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
    "_user_request_active": False,  # Prevents idle TTS during user requests
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
    if server_config.get("tts_voice"):
        tts.EDGE_VOICE = server_config["tts_voice"]
    if server_config.get("tts_rate"):
        tts.RATE = server_config["tts_rate"]
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

    # Pre-cache common phrases in background (truly non-blocking)
    import threading
    threading.Thread(target=tts.precache_phrases, daemon=True).start()
    logger.info("Pre-caching common Mario phrases in background...")

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
        "emotion_intensity": emotion_system.intensity,
        "total_visits": stats["total_visits"],
        "unique_visitors": stats["unique_visitors"],
        "party_duration": stats["party_duration"],
        "current_hour": stats["current_hour"],
        "tts_cache_size": len(tts._audio_cache),
        "conversation_length": len(state_current["conversation_history"]),
        "user_active": state_current["_user_request_active"],
        "llm_model": llm.MODEL_NAME,
    }


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    logger.info("Client connected!")

    # Send initial greeting
    loop = asyncio.get_event_loop()
    try:
        greeting_ctx = mario_prompt.build_context(event="startup")
        greeting_ctx.append({"role": "system", "content": emotion_system.get_prompt_addition()})
        greeting_text = await llm.generate_response(greeting_ctx)
        greeting_text = filter_response(greeting_text)
        analyzed = analyze_text(greeting_text)
        greeting_audio = await loop.run_in_executor(None, lambda: tts.synthesize(analyzed["tts_text"]))
        await send_response(ws, analyzed["display_text"], greeting_audio, sound="greeting",
                            pose_hint=analyzed["pose_hint"])
    except Exception as e:
        logger.error(f"Startup greeting failed: {e}")
        try:
            fallback_audio = await loop.run_in_executor(None, lambda: tts.synthesize("Wahoo!"))
            await send_response(ws, "It's-a me, Mario! Wahoo!", fallback_audio, sound="greeting",
                                pose_hint="positive/excited_jump")
        except Exception:
            pass

    # Start idle behavior loop
    idle_task = asyncio.create_task(_idle_loop(ws))

    try:
        while True:
            data = await ws.receive()

            if "bytes" in data and data["bytes"]:
                try:
                    await handle_audio(ws, data["bytes"])
                except Exception as e:
                    logger.error(f"handle_audio error: {e}")
            elif "text" in data and data["text"]:
                try:
                    await handle_event(ws, json.loads(data["text"]))
                except json.JSONDecodeError as e:
                    logger.warning(f"Invalid JSON from client: {e}")
                except Exception as e:
                    logger.error(f"handle_event error: {e}")

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
    loop = asyncio.get_event_loop()
    while True:
        await asyncio.sleep(5)

        # Skip idle TTS when a user request is being processed (prevents GPU contention)
        if state_current.get("_user_request_active"):
            continue

        if state_current["presence"]:
            if state_current["enter_time"]:
                minutes = (time.time() - state_current["enter_time"]) / 60
                comment = idle_behavior.get_long_stay_comment(minutes)
                if comment:
                    analyzed = analyze_text(comment)
                    audio = await loop.run_in_executor(None, lambda: tts.synthesize(analyzed["tts_text"]))
                    try:
                        await send_response(ws, analyzed["display_text"], audio,
                                            sound="coin", pose_hint=analyzed["pose_hint"])
                    except Exception:
                        pass
            continue

        action = idle_behavior.get_idle_action()
        if action:
            emotion_system.update()
            analyzed = analyze_text(action)
            try:
                # If it's purely an action (no spoken text after stripping), just send pose change
                if not analyzed["tts_text"] or analyzed["tts_text"] == action.strip():
                    has_spoken = len(analyzed["tts_text"]) > 3 and not analyzed["tts_text"].startswith("♪")
                else:
                    has_spoken = True

                if has_spoken and len(analyzed["tts_text"]) > 5:
                    audio = await loop.run_in_executor(
                        None, lambda: tts.synthesize(analyzed["tts_text"])
                    )
                    await send_response(ws, analyzed["display_text"], audio,
                                        pose_hint=analyzed["pose_hint"])
                else:
                    # No TTS needed — just send text + pose change
                    msg = {
                        "type": "mario_response",
                        "text": analyzed["display_text"],
                        "has_audio": False,
                        "emotion": emotion_system.current,
                        "is_idle": True,
                    }
                    if analyzed["pose_hint"]:
                        msg["pose_hint"] = analyzed["pose_hint"]
                    await ws.send_json(msg)
            except asyncio.CancelledError:
                logger.info("Idle loop cancelled")
                return
            except Exception as e:
                logger.error(f"Idle loop error: {e}")
                break


async def handle_audio(ws: WebSocket, audio_bytes: bytes):
    """Process incoming audio from the client microphone."""
    if DEBUG_SERVER:
        logger.info(f"[DEBUG_SERVER] handle_audio: received {len(audio_bytes)} bytes")

    state_current["audio_buffer"].extend(audio_bytes)

    CHUNK_SIZE = 96000
    # Prevent unbounded buffer growth (max 500KB)
    MAX_BUFFER = 500000
    if len(state_current["audio_buffer"]) > MAX_BUFFER:
        state_current["audio_buffer"] = state_current["audio_buffer"][-CHUNK_SIZE:]
    if len(state_current["audio_buffer"]) < CHUNK_SIZE:
        return

    audio_chunk = bytes(state_current["audio_buffer"][:CHUNK_SIZE])
    state_current["audio_buffer"] = state_current["audio_buffer"][CHUNK_SIZE:]
    state_current["_last_audio_chunk"] = audio_chunk  # Save for name registration

    state_current["_user_request_active"] = True
    try:
        await _process_audio(ws, audio_chunk)
    finally:
        state_current["_user_request_active"] = False


async def _process_audio(ws: WebSocket, audio_chunk: bytes):
    """Inner audio processing — separated so we can wrap with request flag."""

    # Run STT + speaker ID in parallel
    _response_start = time.time()
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
        redirect_audio = await loop.run_in_executor(None, lambda: tts.synthesize(safety["redirect"]))
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

        # Add conversation history (12 messages = 6 exchanges for better context)
        for msg in state_current["conversation_history"][-12:]:
            ctx.append(msg)

        await send_thinking(ws, subtitle=transcript)
        response_text = await llm.generate_response(ctx, transcript)
    response_text = filter_response(response_text)
    analyzed = analyze_text(response_text)
    logger.info(f"Mario says: '{analyzed['tts_text']}' (pose={analyzed['pose_hint']})")

    # Save conversation
    state_current["conversation_history"].append({"role": "user", "content": transcript})
    state_current["conversation_history"].append({"role": "assistant", "content": response_text})
    # Trim history to prevent memory bloat (trim at 40 → keep last 30)
    if len(state_current["conversation_history"]) > 40:
        state_current["conversation_history"] = state_current["conversation_history"][-30:]

    if state_current["speaker_id"]:
        memory.save_conversation(state_current["speaker_id"], "user", transcript)
        memory.save_conversation(state_current["speaker_id"], "mario", response_text)
        # Auto-extract facts from user speech
        for fact in memory.extract_facts(transcript):
            memory.save_fact(state_current["speaker_id"], fact)
            logger.info(f"Learned fact: {fact}")
    voice_params = emotion_system.get_voice_params()
    try:
        response_audio = await loop.run_in_executor(
            None, lambda: tts.synthesize(analyzed["tts_text"], rate=voice_params.get("rate"), pitch=voice_params.get("pitch"))
        )
    except Exception as e:
        logger.error(f"TTS failed: {e} — sending text only")
        response_audio = None

    await send_response(ws, analyzed["display_text"], response_audio,
                        emotion=emotion_system.current, pose_hint=analyzed["pose_hint"],
                        response_time=time.time() - _response_start)

    _total_time = time.time() - _response_start
    logger.info(f"⏱ Total response time: {_total_time:.1f}s (STT+SpeakerID → LLM → TTS → Send)")


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

    # Compliment request
    if any(w in lower for w in ["compliment", "say something nice", "make me feel", "cheer me up"]):
        emotion_system.current = "loving"
        return idle_behavior.get_compliment()

    # Challenge request
    if any(w in lower for w in ["challenge", "quiz me", "test me", "trivia"]):
        emotion_system.current = "mischievous"
        return idle_behavior.get_challenge()

    # Hand wash reminder
    if any(w in lower for w in ["wash my hands", "should i wash", "hygiene", "wash hands", "hand wash", "soap"]):
        return idle_behavior.get_hand_wash_reminder()

    # How many visitors
    if any(w in lower for w in ["how many visitors", "how busy", "popular"]):
        stats = party_stats.get_stats()
        if stats['total_visits'] > 10:
            return f"Mama mia! We've had {stats['total_visits']} visits tonight! This bathroom is-a the hottest spot at the party!"
        else:
            return f"So far {stats['total_visits']} visits! The party is-a still warming up!"

    # Who was here last
    if any(w in lower for w in ["who was here", "who came", "last person", "before me"]):
        stats = party_stats.get_stats()
        last = stats.get('last_visitor_name')
        if last:
            return f"The last person before you was-a {last}! Nice person!"
        else:
            return f"You know, I've been here a while but my memory is-a fuzzy! Too many guests!"

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

        # Check for milestone visits
        stats = party_stats.get_stats()
        total = stats.get("total_visits", 0)
        event_type_greeting = "enter_unknown"

        if state_current["speaker_name"]:
            event_type_greeting = "enter_known"
            memories = memory.get_memories_for_context(state_current["speaker_id"])
            ctx = mario_prompt.build_context(
                speaker_name=state_current["speaker_name"],
                memories=memories,
                event="enter_known",
                visit_count=len(memories),
                last_topic=memories[-1] if memories else "nothing special",
            )
        elif total == 1:
            ctx = mario_prompt.build_context(event="first_visitor")
        elif total in (10, 25, 50, 100):
            ctx = mario_prompt.build_context(event="milestone_visit", count=total)
        else:
            ctx = mario_prompt.build_context(event="enter_unknown")

        ctx.append({"role": "system", "content": emotion_system.get_prompt_addition()})

        response_text = await llm.generate_response(ctx)
        response_text = filter_response(response_text)

        if not state_current["speaker_name"]:
            response_text += " What's-a your name, friend?"

        analyzed = analyze_text(response_text)
        loop = asyncio.get_event_loop()
        response_audio = await loop.run_in_executor(None, lambda: tts.synthesize(analyzed["tts_text"]))
        await send_response(ws, analyzed["display_text"], response_audio, sound="greeting",
                            emotion=emotion_system.current, pose_hint=analyzed["pose_hint"] or "greeting/wave_high")

    elif event_type == "presence_exit":
        state_current["presence"] = False
        emotion_system.update(event="presence_exit")

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

        # Always add hand wash reminder on exit
        wash_reminder = idle_behavior.get_hand_wash_reminder()
        response_text = f"{response_text} {wash_reminder}"

        analyzed = analyze_text(response_text)
        loop = asyncio.get_event_loop()
        response_audio = await loop.run_in_executor(None, lambda: tts.synthesize(analyzed["tts_text"]))
        await send_response(ws, analyzed["display_text"], response_audio, sound="goodbye",
                            emotion=emotion_system.current, pose_hint=analyzed["pose_hint"] or "greeting/farewell")

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
            loop = asyncio.get_event_loop()
            celebrate_audio = await loop.run_in_executor(None, lambda: tts.synthesize(celebrate))
            await send_response(ws, celebrate, celebrate_audio, sound="oneup", emotion="excited")

    elif event_type == "vad_start":
        state_current["is_speaking"] = True
        await ws.send_json({"type": "state", "listening": True})

    elif event_type == "vad_stop":
        state_current["is_speaking"] = False
        await ws.send_json({"type": "state", "listening": False})

    elif event_type == "text_input":
        # Handle keyboard-typed text (same pipeline as audio, but skip STT)
        text = event.get("text", "").strip()
        if not text:
            return

        state_current["_user_request_active"] = True
        try:
            await _handle_text_input(ws, text)
        finally:
            state_current["_user_request_active"] = False


async def _handle_text_input(ws: WebSocket, text: str):
    """Process text input — extracted so we can wrap with request flag."""
    logger.info(f"Text input: '{text}'")
    _text_start = time.time()

    # Send thinking state
    try:
        await ws.send_json({"type": "state", "thinking": True, "subtitle": text})
    except Exception:
        pass

    # Safety check
    safety = check_input(text)
    if not safety["safe"]:
        loop = asyncio.get_event_loop()
        redirect_audio = await loop.run_in_executor(None, lambda: tts.synthesize(safety["redirect"]))
        await send_response(ws, safety["redirect"], redirect_audio)
        return

    emotion_system.update(event="speech_detected", transcript=text)
    idle_behavior.reset_timer()

    # Check special commands
    response_text = await _handle_special_commands(text)
    if response_text is None:
        memories = []
        if state_current["speaker_id"]:
            memories = memory.get_memories_for_context(state_current["speaker_id"])

        ctx = mario_prompt.build_context(
            speaker_name=state_current["speaker_name"],
            memories=memories,
        )
        ctx.append({"role": "system", "content": emotion_system.get_prompt_addition()})
        ctx.append({"role": "system", "content": party_stats.get_stats_for_prompt()})

        for msg in state_current["conversation_history"][-12:]:
            ctx.append(msg)

        await send_thinking(ws, subtitle=text)
        response_text = await llm.generate_response(ctx, text)

    response_text = filter_response(response_text)
    analyzed = analyze_text(response_text)
    logger.info(f"Mario says: '{analyzed['tts_text']}' (pose={analyzed['pose_hint']})")

    state_current["conversation_history"].append({"role": "user", "content": text})
    state_current["conversation_history"].append({"role": "assistant", "content": response_text})
    if len(state_current["conversation_history"]) > 40:
        state_current["conversation_history"] = state_current["conversation_history"][-30:]

    if state_current["speaker_id"]:
        memory.save_conversation(state_current["speaker_id"], "user", text)
        memory.save_conversation(state_current["speaker_id"], "mario", response_text)
        for fact in memory.extract_facts(text):
            memory.save_fact(state_current["speaker_id"], fact)
            logger.info(f"Learned fact: {fact}")

    voice_params = emotion_system.get_voice_params()
    loop = asyncio.get_event_loop()
    try:
        response_audio = await loop.run_in_executor(
            None, lambda: tts.synthesize(analyzed["tts_text"], rate=voice_params.get("rate"), pitch=voice_params.get("pitch"))
        )
    except Exception as e:
        logger.error(f"TTS failed for text_input: {e} — sending text only")
        response_audio = None
    await send_response(ws, analyzed["display_text"], response_audio,
                        emotion=emotion_system.current, pose_hint=analyzed["pose_hint"],
                        response_time=time.time() - _text_start)

    logger.info(f"⏱ Text response time: {time.time() - _text_start:.1f}s")


async def send_thinking(ws: WebSocket, subtitle: str = None):
    """Notify client that Mario is thinking (waiting for LLM)."""
    try:
        msg = {"type": "state", "thinking": True}
        if subtitle:
            msg["subtitle"] = subtitle
        await ws.send_json(msg)
    except Exception:
        pass


async def send_response(ws: WebSocket, text: str, audio: bytes = None,
                        sound: str = None, emotion: str = None,
                        pose_hint: str = None, response_time: float = None):
    """Send Mario's response (text + audio + metadata) to the client."""
    try:
        msg = {
            "type": "mario_response",
            "text": text,
            "has_audio": audio is not None and len(audio) > 0,
            "sound_effect": sound,
            "emotion": emotion or emotion_system.current,
            "animation": emotion_system.animation_state,
        }
        if pose_hint:
            msg["pose_hint"] = pose_hint
        if response_time is not None:
            msg["response_time"] = round(response_time, 1)

        await ws.send_json(msg)

        if audio and len(audio) > 0:
            await ws.send_bytes(audio)
    except Exception as e:
        logger.error(f"send_response failed: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=server_config.get("host", "0.0.0.0"),
        port=server_config.get("port", 8765),
    )
