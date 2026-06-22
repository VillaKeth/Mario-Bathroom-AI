"""Mario AI Client — runs on the MacBook at the party.

Handles:
- Microphone capture and streaming to server
- Playing Mario's voice responses
- Webcam presence detection
- Mario sprite display (Pygame)
"""

import json
import logging
import os
import time
import threading
import sys

# Add project root to path for shared module
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLIENT_DIR = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
if CLIENT_DIR not in sys.path:
    sys.path.insert(0, CLIENT_DIR)

# Load config
CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")
_full_config = {}
if os.path.exists(CONFIG_PATH):
    with open(CONFIG_PATH, encoding="utf-8") as f:
        _full_config = json.load(f)
    client_config = _full_config.get("client", {})
else:
    client_config = {}

# Set up logging
DEBUG_CLIENT = True
DEBUG_AUDIO = True
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("mario-client")

# Debug MCP: in-memory client log ring (client stdout otherwise only hits the
# console). Tailed via the client debug server's /log when MARIO_DEBUG=1.
from collections import deque as _deque
_CLIENT_LOG_RING = _deque(maxlen=3000)


class _ClientRingHandler(logging.Handler):
    def emit(self, record):
        try:
            _CLIENT_LOG_RING.append({"msg": record.getMessage(), "level": record.levelname, "name": record.name})
        except Exception:
            pass


logging.getLogger().addHandler(_ClientRingHandler())


class _DebugProvider:
    """Adapts MarioClient to the client/debug_server route() provider interface."""

    def __init__(self, client):
        self._c = client

    def debug_state(self):
        return self._c.display.debug_state()

    def audio_log_snapshot(self, n=10):
        return self._c.audio_playback.audio_log_snapshot(n=n)

    def log_snapshot(self, n=200, grep="", level="DEBUG"):
        items = list(_CLIENT_LOG_RING)
        if grep:
            g = grep.lower()
            items = [l for l in items if g in l["msg"].lower()]
        return items[-n:]

    def latest_frame_png(self):
        return self._c.display.latest_frame_png()

    def inject_frame_b64(self, b64):
        try:
            import base64 as _b64
            import numpy as _np
            import cv2
            raw = _np.frombuffer(_b64.b64decode(b64), _np.uint8)
            frame = cv2.imdecode(raw, cv2.IMREAD_COLOR)
        except Exception as e:
            return {"error": f"decode failed: {e}"}
        if frame is None:
            return {"error": "could not decode image"}
        return self._c.presence.inject_frame(frame)

if _full_config:
    logger.info(f"Loaded config from {CONFIG_PATH}")

# Load character
from shared.character_loader import CharacterLoader
_characters_dir = os.path.join(PROJECT_ROOT, "characters")
_character_name = _full_config.get("character", "mario")
_character = CharacterLoader(_characters_dir, _character_name)
logger.info(f"Loaded character: {_character.display_name}")

# Override mario_display module-level constants BEFORE importing MarioDisplay
import mario_display as mario_display_module

if _character.sprite_dir:
    mario_display_module.SPRITE_DIR = _character.sprite_dir
if _character.ai_poses_dir:
    mario_display_module.AI_POSES_DIR = _character.ai_poses_dir
if _character.backgrounds_dir:
    mario_display_module.CHARACTER_BACKGROUNDS_DIR = _character.backgrounds_dir
if _character.default_background:
    mario_display_module.DEFAULT_BACKGROUND = _character.default_background
if _character.emotion_sprite_map:
    mario_display_module.EMOTION_SPRITE_MAP = _character.emotion_sprite_map
if _character.state_sprite_map:
    mario_display_module.STATE_SPRITE_MAP = _character.state_sprite_map
if _character.ai_pose_size:
    mario_display_module.AI_POSE_DISPLAY_SIZE = _character.ai_pose_size
mario_display_module.WINDOW_TITLE = _character.display_name
mario_display_module.BANNER_TITLE = _character.display_name

# Now import from mario_display
from mario_display import (MarioDisplay, STATE_IDLE, STATE_TALKING, STATE_LISTENING,
                           STATE_THINKING, STATE_GREETING, STATE_ENTERING, STATE_EXITING)
from audio_capture import AudioCapture
from audio_playback import AudioPlayback
from presence import PresenceDetector
from ws_client import MarioWSClient
from mirror_sender import MirrorSender
from sound_effects import SoundEffects

SERVER_URL = client_config.get("server_url", "ws://localhost:8765/ws")


class MarioClient:
    """Main client that ties everything together."""

    def __init__(self, server_url=SERVER_URL):
        self.audio_capture = AudioCapture()
        self.audio_playback = AudioPlayback()
        self.presence = PresenceDetector()
        self.display = MarioDisplay()
        self.ws = MarioWSClient(server_url)
        _mcfg = (_full_config or {}).get("mirror", {})
        self.mirror = MirrorSender(
            ingest_url=_mcfg.get("ingest_url", server_url.replace("/ws", "/mirror_ingest")),
            max_width=_mcfg.get("max_width", 640),
            quality=_mcfg.get("jpeg_quality", 55),
            fps=_mcfg.get("fps", 10),
        )
        self._mirror_enabled = bool(_mcfg.get("enabled", False))
        self.sfx = SoundEffects()

        # Apply audio gain from config
        audio_gain = client_config.get("audio_gain", 1.0)
        self.audio_playback.set_volume(audio_gain)
        if DEBUG_AUDIO:
            logger.info(f"[DEBUG_AUDIO] Initial audio gain from config: {audio_gain}")

        # Set party name from config (server section has event details)
        server_config = _full_config.get("server", {})
        party_theme = server_config.get("party_theme", "")
        if party_theme:
            self.display.set_party_name(party_theme)

        # Label for her lines in the chat backlog (F3)
        if hasattr(self.display, "set_chat_char_name"):
            self.display.set_chat_char_name(_character.name)

        self._running = False
        self._audio_thread = None
        self._health_thread = None
        self._last_play_end_time = 0  # Echo cancellation tracking
        self._memorial_active = False  # Suppresses idle text during memorial
        self._audio_wait_cancel = threading.Event()  # Cancel audio-wait thread
        self._pending_character_switch = None  # Queued switch for main thread

        # Wire up callbacks
        self.ws.on_text_response = self._on_mario_text
        self.ws.on_audio_response = self._on_mario_audio
        self.ws.on_audio_chunk = self._on_audio_chunk
        self.ws.on_connected = self._on_connected
        self.ws.on_disconnected = self._on_disconnected
        self.ws.on_state_update = self._on_state_update
        self.ws.on_leaderboard_update = self._on_leaderboard_update
        self.ws.on_memorial_event = self._on_memorial_event
        self.ws.on_clear_audio = self._on_clear_audio
        self.ws.on_character_switched = self._on_character_switched
        self.ws.on_mirror_request = self._on_mirror_request
        self.ws.on_set_volume = self._on_set_volume
        self.ws.on_user_message = self._on_user_message

        self.presence.on_enter = self._on_presence_enter
        self.presence.on_exit = self._on_presence_exit

        # Enable person detection if configured
        if client_config.get("enable_person_detection", False):
            self.presence.enable_person_detection(client_config)
            self.presence.on_person_detected = self._on_person_detected

        # Wire up keyboard input from display
        self.display.on_keyboard_submit = self._on_keyboard_submit
        self.display.on_volume_change = self._on_volume_change
        self.display._on_memorial_skip = self._on_memorial_skip

    def start(self):
        """Start all client components."""
        logger.info("=== Mario AI Client Starting ===")

        # Initialize display and sound effects
        self.display.init()
        self.display.set_state(STATE_IDLE)
        self.display.set_mario_text("Connecting to server...")
        self.sfx.init(character=getattr(_character, "name", "mario"))
        # Per-character SFX overrides (characters/<char>/sfx/*.wav) replace the
        # generic synthesized sounds — so startup/greeting etc. are not Mario.
        try:
            _csfx = os.path.join(_character.character_dir, "sfx")
            self.sfx.load_character_overrides(_csfx)
        except Exception as _e:
            logger.debug(f"[SFX] character override skipped: {_e}")

        # Start audio (honor enable_microphone — false skips the mic entirely so
        # ambient noise can't flood STT, interrupt playback, or flicker the
        # thinking bubble; text input still works)
        if client_config.get("enable_microphone", True):
            if not self.audio_capture.start():
                logger.warning("No microphone available — audio capture disabled")
                self.display.set_subtitle("⚠ No microphone detected")
        else:
            logger.info("[mic] disabled by config (enable_microphone=false) — text input only")
        self.audio_playback.start()

        # Debug MCP surface (only starts when MARIO_DEBUG=1; binds 127.0.0.1)
        try:
            from debug_server import start_debug_server
            self._debug_srv = start_debug_server(_DebugProvider(self))
        except Exception as _e:
            logger.debug(f"[debug] debug server not started: {_e}")

        # Start presence detection
        if self.presence and not self.presence.start():
            logger.warning("Webcam not available — presence detection disabled")
            self.display.set_subtitle("⚠ No webcam detected")

        # Pre-flight server health check
        self._preflight_check()

        # Connect to server
        self.ws.connect()

        # Start audio streaming thread
        self._running = True
        self._audio_thread = threading.Thread(target=self._audio_stream_loop, daemon=True)
        self._audio_thread.start()

        # Start health ping thread
        self._health_thread = threading.Thread(target=self._health_ping_loop, daemon=True)
        self._health_thread.start()

        logger.info("=== Mario AI Client Ready! ===")

        # Main display loop (must run on main thread for Pygame)
        try:
            while self._running:
                # Process pending character switch on main thread (pygame-safe)
                if self._pending_character_switch:
                    self._apply_character_switch(self._pending_character_switch)
                    self._pending_character_switch = None
                # Keep reconnect info fresh for display
                if not self.display.connected:
                    self.display._reconnect_info = self.ws.reconnect_info
                # Keep camera status fresh for display
                if self.presence:
                    self.display.set_camera_status(self.presence.camera_status)
                if not self.display.update():
                    break
        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        finally:
            self.stop()

    def stop(self):
        """Stop all client components."""
        logger.info("=== Mario AI Client Shutting Down ===")
        self._running = False
        # Send farewell if someone is present
        if self.presence and self.presence.someone_present and self.ws.connected:
            self.ws.send_event({"type": "presence_exit"})
            time.sleep(0.5)  # Brief delay to let server process
        self._audio_wait_cancel.set()
        self.audio_capture.stop()
        self.audio_playback.stop()
        try:
            self.mirror.stop()
        except Exception:
            pass
        if self.presence:
            self.presence.stop()
        self.ws.close()
        self.display.quit()

    def _preflight_check(self):
        """Check server is reachable before connecting WebSocket."""
        import urllib.request
        health_url = self.ws.server_url.replace("ws://", "http://").replace("/ws", "/health")
        self.display.set_mario_text("Checking server...")
        self.display.update()
        for attempt in range(3):
            try:
                req = urllib.request.urlopen(health_url, timeout=5)
                data = json.loads(req.read())
                if data.get("status") == "ok":
                    logger.info(f"Server health OK — TTS cache: {data.get('tts_cache_size', '?')}, LLM: {data.get('llm_model', '?')}")
                    self.display.set_mario_text("Server connected! Here we go!")
                    self.display.update()
                    return True
            except Exception as e:
                logger.warning(f"Health check attempt {attempt+1}/3 failed: {e}")
                self.display.set_mario_text(f"Waiting for server... ({attempt+1}/3)")
                self.display.update()
                time.sleep(3)
        logger.warning("Server health check failed — will try connecting anyway")
        self.display.set_mario_text("Server not responding — retrying...")
        self.display.update()
        return False

    def _audio_stream_loop(self):
        """Continuously stream audio to the server."""
        SEND_INTERVAL = 0.25  # Send audio every 250ms
        audio_buffer = bytearray()

        while self._running:
            # Collect audio
            chunk = self.audio_capture.get_audio(timeout=0.05)
            if chunk:
                audio_buffer.extend(chunk)

            # Send in batches
            if len(audio_buffer) >= 8000 and self.ws.connected:
                # Echo cancellation: don't send audio while playing OR for 500ms after
                play_ended_recently = (time.time() - self._last_play_end_time) < 0.5
                if not self.audio_playback.is_playing and not play_ended_recently:
                    self.ws.send_audio(bytes(audio_buffer))
                    self.display.set_state(STATE_LISTENING)
                    self.display.set_thinking(True)
                audio_buffer = bytearray()
            elif len(audio_buffer) > 64000:
                if self.ws.connected:
                    # Server connected but we're not sending — likely playing back; pause capture briefly
                    logger.warning(f"[DEBUG_CLIENT] Audio buffer overflow ({len(audio_buffer)} bytes), pausing capture")
                    time.sleep(0.3)
                # Keep only last 8KB to prevent memory bloat
                audio_buffer = audio_buffer[-8000:]

            time.sleep(0.01)

    def _on_user_message(self, text):
        """Guest's own line (echoed by the server) — add to the chat backlog."""
        if text:
            self.display.add_chat_message("user", text)

    def _on_mario_text(self, text: str, metadata: dict = None):
        """Called when Mario has something to say."""
        # Cancel any pending audio-wait thread from previous text
        self._audio_wait_cancel.set()
        
        # Suppress idle text bubbles during memorial ceremony
        if self._memorial_active:
            if DEBUG_CLIENT:
                logger.info("[DEBUG_CLIENT] Suppressed idle text during memorial")
            return
        if DEBUG_CLIENT:
            logger.info(f"[DEBUG_CLIENT] Mario says: {text}")
        self.display.set_thinking(False)
        self.display.set_mario_text(text)
        self.display.set_state(STATE_TALKING)
        self.display._speaking = True

        # Log her line to the chat backlog (skip thinking-filler placeholders)
        if not (metadata or {}).get("is_thinking_filler"):
            self.display.add_chat_message("mario", text, full_text=(metadata or {}).get("full_text"))

        # Don't set closed captions for regular speech — speech bubble already shows it.
        # Captions are only used during events (set in _on_memorial_event).

        if metadata:
            sfx_name = metadata.get("sound_effect")
            if sfx_name:
                self.sfx.play(sfx_name)

            # Set the censor state from THIS line's metadata every time (not just
            # when True) so a clean line authoritatively clears any leftover flag
            # from a prior censored line, regardless of audio-cleanup thread timing.
            _censor_on = bool(metadata.get("censor"))
            self.display._censor_active = _censor_on
            if _censor_on:
                self.sfx.play("censor")

            emotion = metadata.get("emotion")
            if emotion:
                self.display.set_emotion(emotion)

            mood_score = metadata.get("mood_score")
            if mood_score is not None:
                self.display.set_mood_score(mood_score)

            # Use pose hint from server for intelligent sprite selection
            pose_hint = metadata.get("pose_hint")
            if pose_hint:
                self.display.set_pose_hint(pose_hint)

            # Spawn keyword-based particle effects from server
            particle_effect = metadata.get("particle_effect")
            if particle_effect:
                self.display.spawn_keyword_particles(particle_effect)

            # Track response time for display
            resp_time = metadata.get("response_time")
            if resp_time:
                self.display._last_response_time = resp_time

    def _wait_for_audio_complete(self):
        """Wait for audio playback to finish, then clear speech bubble."""
        self._audio_wait_cancel.clear()
        
        # Wait for audio to start playing (up to 2s)
        for _ in range(20):
            if self.audio_playback.is_playing or self._audio_wait_cancel.is_set():
                break
            time.sleep(0.1)
        
        # Wait for audio to finish
        while self.audio_playback.is_playing and not self._audio_wait_cancel.is_set():
            time.sleep(0.1)
        
        # 500ms grace period after audio ends (only if not cancelled)
        if not self._audio_wait_cancel.is_set():
            time.sleep(0.5)
            self._clear_speaking_state()

    def _on_mario_audio(self, wav_bytes: bytes):
        """Called when Mario's voice audio arrives."""
        if not wav_bytes or len(wav_bytes) < 44:
            logger.warning("[DEBUG_CLIENT] Received empty or too-small audio, skipping")
            return
        if DEBUG_CLIENT:
            logger.info(f"[DEBUG_CLIENT] Playing audio: {len(wav_bytes)} bytes")
        # If a countdown number is pending, reveal it exactly when this clip
        # starts playing — so the visual countdown is driven by the audio.
        pending = getattr(self, "_pending_countdown_number", None)
        _spoken = getattr(self.display, "_typewriter_text", "")
        if pending is not None:
            self._pending_countdown_number = None
            self.audio_playback.play(wav_bytes, on_start=(lambda n=pending: self.display.set_countdown(n)), text=_spoken)
        else:
            self.audio_playback.play(wav_bytes, text=_spoken)
        self.mirror.send_audio(wav_bytes)   # tee to remote viewers (no-op if inactive)
        # Track when playback finishes for echo cancellation
        # 48000 = 24kHz sample rate × 2 bytes/sample (16-bit mono PCM)
        duration = max(0.5, len(wav_bytes) / 48000)
        self._last_play_end_time = time.time() + duration
        # Sync typewriter speed to audio duration
        self.display.sync_typewriter_to_audio(duration)
        # Start audio-wait thread that polls until playback actually finishes
        self._audio_wait_cancel.set()
        self._audio_wait_thread = threading.Thread(target=self._wait_for_audio_complete, daemon=True)
        self._audio_wait_thread.start()

    def _on_mirror_request(self, active: bool):
        """Server signals a viewer connected/left — start/stop capture."""
        if not self._mirror_enabled:
            return
        try:
            if active:
                self.mirror.start()
                self.display.on_frame_ready = self._capture_frame
            else:
                self.display.on_frame_ready = None
                self.mirror.stop()
        except Exception as e:
            if DEBUG_CLIENT:
                logger.error(f"[DEBUG_CLIENT] mirror_request handling failed: {e}")

    def _capture_frame(self, surface):
        """Called by the display after flip when the mirror is active. Cheap + safe."""
        try:
            import pygame
            try:
                rgb = pygame.image.tobytes(surface, "RGB")
            except AttributeError:
                rgb = pygame.image.tostring(surface, "RGB")  # older pygame
            self.mirror.submit_rgb(rgb, surface.get_size())
        except Exception:
            pass

    def _on_clear_audio(self):
        """Called when server requests immediate audio interruption (new user input)."""
        if DEBUG_CLIENT:
            logger.info("[DEBUG_CLIENT] clear_audio: stopping playback for new input")
        self._audio_wait_cancel.set()
        self.audio_playback.clear()
        self._last_play_end_time = 0
        self._clear_speaking_state()

    def _on_audio_chunk(self, wav_bytes: bytes, chunk_meta: dict):
        """Called when a streaming audio chunk arrives (sentence streaming)."""
        if not wav_bytes or len(wav_bytes) < 44:
            logger.warning("[DEBUG_CLIENT] Received empty audio chunk, skipping")
            return
        chunk_idx = chunk_meta.get("chunk_index", 0)
        total = chunk_meta.get("total_chunks", 1)
        is_last = chunk_meta.get("is_last", False)
        if DEBUG_CLIENT:
            logger.info(f"[DEBUG_CLIENT] Audio chunk {chunk_idx}/{total} ({len(wav_bytes)} bytes, is_last={is_last})")
        # Queue the chunk — AudioPlayback plays them sequentially
        self.audio_playback.play(wav_bytes, text=getattr(self.display, "_typewriter_text", ""))
        self.mirror.send_audio(wav_bytes)   # tee streaming chunk to remote viewers
        # Keep speaking state active; extend echo cancellation window
        duration = max(0.5, len(wav_bytes) / 48000)
        self._last_play_end_time = time.time() + duration
        # On first chunk, estimate total duration and sync typewriter
        if chunk_idx == 0 and isinstance(total, int) and total > 0:
            estimated_total = duration * total
            self.display.sync_typewriter_to_audio(estimated_total)
        # Only schedule speaking state clear on the last chunk
        if is_last:
            self._audio_wait_cancel.set()
            self._audio_wait_thread = threading.Thread(target=self._wait_for_audio_complete, daemon=True)
            self._audio_wait_thread.start()

    def _clear_speaking_state(self):
        """Clear speaking state after audio finishes."""
        self.display._speaking = False
        self.display._censor_active = False
        self.display.set_state(STATE_IDLE)
        
        # Clear closed captions
        if self.display.captions:
            self.display.captions.clear()

    def _on_connected(self):
        logger.info("Connected to Mario AI server!")
        self.display.connected = True
        self.display._reconnect_info = None
        self.display.set_state(STATE_GREETING)

    def _on_character_switched(self, data: dict):
        """Handle hot-swap character notification from server.
        
        Queues the switch for the main thread (pygame ops must be on main thread).
        """
        self._pending_character_switch = data
        logger.info(f"Character switch queued: {data.get('display_name')}")

    def _apply_character_switch(self, data: dict):
        """Apply character switch on main thread (pygame-safe)."""
        new_name = data.get("display_name", data.get("character", "Unknown"))
        char_key = data.get("character", "")
        logger.info(f"Applying character switch to: {new_name}")
        self.display.set_mario_text(f"Switching to {new_name}...")
        try:
            characters_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "characters")
            from shared.character_loader import CharacterLoader as CL
            new_char = CL(characters_dir, char_key)
            
            import mario_display as md
            if new_char.ai_poses_dir:
                md.AI_POSES_DIR = new_char.ai_poses_dir
            if new_char.sprite_dir:
                md.SPRITE_DIR = new_char.sprite_dir
            if new_char.emotion_sprite_map:
                md.EMOTION_SPRITE_MAP = new_char.emotion_sprite_map
            if new_char.state_sprite_map:
                md.STATE_SPRITE_MAP = new_char.state_sprite_map
            if new_char.ai_pose_size:
                md.AI_POSE_DISPLAY_SIZE = new_char.ai_pose_size
            
            self.display._sprites.clear()
            self.display._load_sprites()
            
            import pygame as _pg
            import mario_display as _md
            _pg.display.set_caption(new_name)
            _md.BANNER_TITLE = new_name
            _md.WINDOW_TITLE = new_name
            
            logger.info(f"Character switch complete: {new_name} ({len(self.display._sprites)} sprites)")
        except Exception as e:
            logger.warning(f"Failed to apply character switch: {e}")

    def _on_disconnected(self):
        logger.warning("Disconnected from server!")
        self.display.connected = False
        self.display._reconnect_info = self.ws.reconnect_info
        self.display.set_mario_text("Connection lost! Reconnecting...")
        self.display.set_state(STATE_IDLE)

    def _on_state_update(self, state: dict):
        if state.get("thinking"):
            self.display.set_state(STATE_THINKING)
            self.display.set_mario_text("Hmm, let me think...")
            subtitle = state.get("subtitle")
            if subtitle:
                self.display.set_subtitle(subtitle)
        elif state.get("listening"):
            self.display.set_state(STATE_LISTENING)

    def _on_presence_enter(self):
        """Someone entered the bathroom."""
        logger.info("Presence detected — someone entered!")
        self.ws.send_event({"type": "presence_enter"})
        self.display.start_transition("enter")
        self.display.set_state(STATE_GREETING)
        self.sfx.play("greeting")

    def _on_presence_exit(self):
        """Someone left the bathroom."""
        logger.info("Presence lost — someone left!")
        self.ws.send_event({"type": "presence_exit"})
        self.display.start_transition("exit")
        self.display.set_state(STATE_EXITING)
        self.display.set_subtitle("")
        self.sfx.play("goodbye")

    def _on_person_detected(self, people):
        """Send batched person detection event to server via WebSocket."""
        try:
            faces = []
            for person in people:
                face_entry = {"confidence": person.confidence}
                if person.face_encoding is not None:
                    face_entry["encoding"] = person.face_encoding.tolist()
                faces.append(face_entry)

            event = {
                "type": "person_detected",
                "faces": faces,
                "face_count": len(faces),
            }
            self.ws.send_event(event)
        except Exception as e:
            logger.debug(f"Person detection event send failed: {e}")

    def _health_ping_loop(self):
        """Send periodic health pings and update display health data."""
        consecutive_failures = 0
        while self._running:
            time.sleep(30)
            if self.ws.connected:
                self.ws.send_health_ping()
                try:
                    import urllib.request
                    health_url = self.ws.server_url.replace("ws://", "http://").replace("/ws", "/health")
                    req = urllib.request.urlopen(health_url, timeout=5)
                    data = json.loads(req.read())
                    self.display.update_health(data)
                    consecutive_failures = 0
                except Exception as e:
                    consecutive_failures += 1
                    if consecutive_failures <= 3 or consecutive_failures % 10 == 0:
                        logger.warning(f"[HEALTH] Ping failed ({consecutive_failures}x): {e}")

    def _on_keyboard_submit(self, text: str):
        """Called when user submits text via keyboard input."""
        if DEBUG_CLIENT:
            logger.info(f"[DEBUG_CLIENT] Keyboard input: {text}")

        # Admin slash commands
        if text.startswith("/"):
            self._handle_admin_command(text)
            return

        self.display.set_subtitle(text)
        self.display.set_thinking(True)
        if self.ws.connected:
            self.ws.send_event({"type": "text_input", "text": text})

    def _handle_admin_command(self, text: str):
        """Handle admin slash commands."""
        parts = text.strip().split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        if cmd == "/announce" and arg:
            self._send_admin_post("/admin/announce", {"text": arg})
            self.display.set_subtitle(f"📢 Announced: {arg}")
        elif cmd == "/emotion" and arg:
            self._send_admin_post("/admin/set_emotion", {"emotion": arg})
            self.display.set_subtitle(f"🎭 Emotion → {arg}")
        elif cmd == "/memorial":
            event_name = arg if arg else "lisa_webb_memorial"
            self._send_admin_post(f"/admin/trigger_event/{event_name}")
            self.display.set_subtitle(f"🕯️ Event triggered: {event_name}")
        elif cmd == "/event" and arg:
            self._send_admin_post(f"/admin/trigger_event/{arg}")
            self.display.set_subtitle(f"🎉 Event triggered: {arg}")
        elif cmd == "/events":
            self._fetch_and_display_events()
        elif cmd == "/stopgame":
            self._send_admin_post("/admin/force_stop_game")
            self.display.set_subtitle("🛑 Game stopped")
        elif cmd == "/reload":
            self._send_admin_post("/api/reload")
            self.display.set_subtitle("🔄 Config reloaded")
        elif cmd == "/reset":
            self._send_admin_post("/admin/reset")
            self.display.set_subtitle("🔄 Server reset")
        elif cmd == "/pause":
            self._send_admin_get("/pause_idle")
            self.display.set_subtitle("⏸️ Idle paused")
        elif cmd == "/sovits":
            self._send_admin_get("/restart_sovits")
            self.display.set_subtitle("🔄 SoVITS restarting...")
        elif cmd == "/help":
            help_text = "Commands: /announce, /emotion, /event, /events, /memorial, /stopgame, /reload, /reset, /pause, /sovits, /health, /leaderboard, /stats, /summary, /games, /help"
            self.display.set_mario_text(help_text)
            self.display.set_subtitle("ℹ️ Admin commands")
        elif cmd == "/health":
            self._fetch_and_display_health()
        elif cmd == "/leaderboard":
            self._fetch_and_display_leaderboard()
        elif cmd == "/stats":
            self._fetch_and_display_stats()
        elif cmd == "/summary":
            self._fetch_and_display_summary()
        elif cmd == "/games":
            games = "1:Trivia 2:RPS 3:Truth/Dare 4:Simon 5:20Q 6:Joke 7:Karaoke 8:Dance 9:WYR 0:Fortune | Also: riddles, hangman, hot takes, never have I ever, word chain, story builder, bathroom dare, name that character"
            self.display.set_mario_text(games)
            self.display.set_subtitle("🎮 Available games")
        else:
            self.display.set_subtitle(f"❌ Unknown command: {cmd}")

    def _send_admin_post(self, path: str, body: dict = None):
        """Send an admin POST request to the server."""
        import urllib.request
        try:
            base_url = self.ws.server_url.replace("ws://", "http://").replace("/ws", "")
            url = base_url + path
            data = json.dumps(body or {}).encode()
            req = urllib.request.Request(url, method="POST", data=data,
                                        headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=5)
        except Exception as e:
            logger.error(f"Admin command failed: {e}")
            self.display.set_subtitle(f"❌ Failed: {e}")

    def _send_admin_get(self, path: str):
        """Send an admin GET request to the server."""
        import urllib.request
        try:
            base_url = self.ws.server_url.replace("ws://", "http://").replace("/ws", "")
            url = base_url + path
            urllib.request.urlopen(url, timeout=5)
        except Exception as e:
            logger.error(f"Admin command failed: {e}")
            self.display.set_subtitle(f"❌ Failed: {e}")

    def _fetch_and_display_health(self):
        """Fetch server health and display as Mario text."""
        import urllib.request
        try:
            base_url = self.ws.server_url.replace("ws://", "http://").replace("/ws", "")
            req = urllib.request.urlopen(base_url + "/api/health", timeout=5)
            data = json.loads(req.read())
            health_lines = []
            health_lines.append(f"Status: {data.get('status', '?')}")
            health_lines.append(f"Uptime: {data.get('uptime_seconds', '?')}s")
            health_lines.append(f"TTS: {data.get('tts', '?')}")
            health_lines.append(f"LLM: {data.get('llm', '?')}")
            health_lines.append(f"Cache: {data.get('tts_cache_size', '?')} entries")
            health_lines.append(f"Memory: {data.get('memory_mb', '?')}MB")
            self.display.set_mario_text(" | ".join(health_lines))
            self.display.set_subtitle("📊 Server health")
        except Exception as e:
            self.display.set_subtitle(f"❌ Health check failed: {e}")

    def _fetch_and_display_events(self):
        """Fetch registered shot events and display them."""
        import urllib.request
        try:
            base_url = self.ws.server_url.replace("ws://", "http://").replace("/ws", "")
            req = urllib.request.urlopen(base_url + "/admin/events", timeout=5)
            data = json.loads(req.read())
            events = data.get("events", [])
            lines = [f"{e['name']} ({e['tone']}) {'[FIRED]' if e['fired'] else '[READY]'}" for e in events]
            self.display.set_mario_text(" | ".join(lines) if lines else "No events configured")
            self.display.set_subtitle(f"🎉 {len(events)} events loaded")
        except Exception as e:
            self.display.set_subtitle(f"❌ Events fetch failed: {e}")

    def _fetch_and_display_leaderboard(self):
        """Fetch leaderboard and toggle the overlay."""
        import urllib.request
        try:
            base_url = self.ws.server_url.replace("ws://", "http://").replace("/ws", "")
            req = urllib.request.urlopen(base_url + "/leaderboard", timeout=5)
            data = json.loads(req.read())
            self.display.update_leaderboard(data)
            self.display.toggle_leaderboard()
            self.display.set_subtitle("🏆 Leaderboard shown")
        except Exception as e:
            self.display.set_subtitle(f"❌ Leaderboard fetch failed: {e}")

    def _fetch_and_display_stats(self):
        """Fetch health + leaderboard and display compact stats summary."""
        import urllib.request
        try:
            base_url = self.ws.server_url.replace("ws://", "http://").replace("/ws", "")
            health = json.loads(urllib.request.urlopen(base_url + "/health", timeout=5).read())
            lb = json.loads(urllib.request.urlopen(base_url + "/leaderboard", timeout=5).read())
            dur = lb.get("party_duration", {})
            stats_text = (
                f"Party: {dur.get('hours', 0)}h {dur.get('minutes', 0)}m | "
                f"Guests: {lb.get('unique_visitors', 0)} | "
                f"Visits: {lb.get('total_visits', 0)} | "
                f"Cache: {health.get('tts_cache_size', '?')} | "
                f"Emotion: {health.get('emotion', '?')} | "
                f"Avg: {health.get('avg_response_time', '?')}"
            )
            self.display.set_mario_text(stats_text)
            self.display.set_subtitle("📊 Party stats")
        except Exception as e:
            self.display.set_subtitle(f"❌ Stats fetch failed: {e}")

    def _fetch_and_display_summary(self):
        """Fetch comprehensive party summary from /admin/party_summary."""
        import urllib.request
        try:
            base_url = self.ws.server_url.replace("ws://", "http://").replace("/ws", "")
            req = urllib.request.urlopen(base_url + "/admin/party_summary", timeout=5)
            data = json.loads(req.read())
            if data.get("status") == "ok":
                summary_text = (
                    f"Party: {data.get('uptime_hours', 0)}h | "
                    f"Guests: {data.get('unique_guests', 0)} | "
                    f"Visits: {data.get('total_visits', 0)} | "
                    f"Messages: {data.get('total_messages', 0)} | "
                    f"Games: {data.get('total_games_played', 0)} | "
                    f"Events: {data.get('events_fired', 0)}/{data.get('events_total', 0)} | "
                    f"Mood: {data.get('current_emotion', '?')} | "
                    f"Cache: {data.get('tts_cache_size', 0)}"
                )
                self.display.set_mario_text(summary_text)
                self.display.set_subtitle("Party summary")
            else:
                self.display.set_subtitle("Summary not available (server restart needed)")
        except Exception as e:
            self.display.set_subtitle("Summary not available (needs server restart)")

    def _on_volume_change(self, delta: float):
        """Called when user adjusts volume with +/- keys."""
        current = self.audio_playback.get_volume()
        new_vol = max(0.0, min(2.0, current + delta))
        self.audio_playback.set_volume(new_vol)
        self.display.show_volume(new_vol)
        if DEBUG_AUDIO:
            logger.info(f"[DEBUG_AUDIO] Volume changed: {current:.1f} -> {new_vol:.1f}")

    def _on_set_volume(self, gain):
        """Server-driven absolute volume set (from the admin control page)."""
        try:
            new_vol = max(0.0, min(2.0, float(gain)))
        except (TypeError, ValueError):
            logger.warning(f"[CLIENT] set_volume ignored bad gain: {gain!r}")
            return
        self.audio_playback.set_volume(new_vol)
        self.display.show_volume(new_vol)
        logger.info(f"[CLIENT] remote set_volume -> {new_vol:.2f}")

    def _on_memorial_skip(self):
        """Called when user presses Ctrl+Shift+L to skip memorial event."""
        if DEBUG_CLIENT:
            logger.info("[DEBUG_CLIENT] Memorial skip requested")
        try:
            # Stop memorial music
            self.audio_playback.stop_memorial_music()
            # Clear memorial flag
            self._memorial_active = False
            # Clear countdown
            self.display.clear_countdown()
            # Reset memorial flag in display 
            if hasattr(self.display, 'memorial_active'):
                self.display.memorial_active = False
        except Exception as e:
            logger.error(f"Error during memorial skip: {e}")

    def _on_leaderboard_update(self, data: dict):
        """Called when server sends leaderboard update."""
        if DEBUG_CLIENT:
            logger.info(f"[DEBUG_CLIENT] Leaderboard update received")
        self.display.update_leaderboard(data)

    def _on_memorial_event(self, data: dict):
        """Called when server sends memorial/shot event — handles all phases."""
        phase = data.get("phase", "silence")
        name = data.get("name", "")
        text = data.get("text", "")
        duration = data.get("duration", 15)
        tone = data.get("tone", "solemn")
        image_file = data.get("image_file")
        music_file = data.get("music_file")
        logger.info(f"[SHOT_EVENT] phase={phase} name={name} tone={tone} text='{text[:60]}...' duration={duration}")

        # Load event-specific image if provided (before showing overlay)
        if image_file and self.display:
            self.display.load_event_image(image_file)

        # Show the overlay on the display with text for every phase
        if self.display:
            self.display.show_memorial(name, phase, text, duration=duration, tone=tone)
            logger.info(f"[SHOT_EVENT] show_memorial called → _memorial_active={self.display._memorial_active}, _memorial_phase={self.display._memorial_phase}")

        # Don't route event text to closed captions — memorial overlay already renders it.
        # This prevents double subtitles (overlay text + captions text overlapping).

        # Phase-specific handling
        if phase == "announcement":
            self._memorial_active = True
            if hasattr(self.display, 'current_text'):
                self.display.current_text = ""
        elif phase == "countdown":
            countdown_number = self._convert_countdown_word_to_number(text)
            if countdown_number:
                # Show the number when its AUDIO starts (see _on_mario_audio),
                # not now — keeps the visual in sync with the spoken number.
                self._pending_countdown_number = countdown_number
        elif phase in ("music", "silence"):
            # Clear countdown when music/silence phase starts
            self.display.clear_countdown()
        elif phase == "toast":
            # Clear countdown number when transitioning to toast
            self.display.clear_countdown()
        elif phase == "fadeout":
            # Clear countdown and memorial flags
            self.display.clear_countdown()
            # Clear flag after fadeout animation completes
            def _clear_flag():
                time.sleep(duration + 3)
                self._memorial_active = False
                if DEBUG_CLIENT:
                    logger.info("[DEBUG_CLIENT] Memorial flag cleared after fadeout")
            threading.Thread(target=_clear_flag, daemon=True).start()
        elif phase == "recovery":
            # Recovery is the LAST phase — clear memorial flag after duration
            def _clear_flag_recovery():
                time.sleep(duration + 3)
                self._memorial_active = False
                self.display._memorial_active = False
                logger.info("[SHOT_EVENT] Memorial flags cleared after recovery")
            threading.Thread(target=_clear_flag_recovery, daemon=True).start()

        # A new event's announcement = a fresh start. Stop any music still
        # playing from a PREVIOUS shot event so the old song doesn't play under
        # the new announcement/countdown (the muddy overlap when you fire a
        # second shot while the first song is still going).
        if phase == "announcement" and self.audio_playback.is_music_playing:
            self.audio_playback.stop_memorial_music(fadeout_ms=600)

        # Start/stop memorial music
        if phase == "music":
            # Use event-specific music_file if provided, fall back to lisa_webb_memorial.mp3
            event_music = data.get("music_file", "")
            if event_music:
                if not os.path.isabs(event_music):
                    # Server sends paths relative to project root (e.g. "client/assets/audio/...")
                    project_root = os.path.dirname(os.path.dirname(__file__))
                    event_music = os.path.join(project_root, event_music)
                music_path = event_music
            else:
                music_path = os.path.join(os.path.dirname(__file__), "assets", "music", "lisa_webb_memorial.mp3")
            if os.path.exists(music_path):
                self.audio_playback.play_memorial_music(music_path)
            else:
                logger.warning(f"[DEBUG_CLIENT] Memorial music not found: {music_path}")
        elif phase == "fadeout":
            self.audio_playback.stop_memorial_music(fadeout_ms=3000)

        # Play SFX for specific phases
        sfx_dir = os.path.join(os.path.dirname(__file__), "assets", "sfx")
        if phase == "silence":
            chime_path = os.path.join(sfx_dir, "memorial_chime.wav")
            if os.path.exists(chime_path):
                try:
                    with open(chime_path, "rb") as f:
                        self.audio_playback.play(f.read())
                except Exception as e:
                    logger.warning(f"[DEBUG_CLIENT] Chime SFX error: {e}")
        elif phase == "toast":
            clink_path = os.path.join(sfx_dir, "memorial_clink.wav")
            if os.path.exists(clink_path):
                try:
                    with open(clink_path, "rb") as f:
                        self.audio_playback.play(f.read())
                except Exception as e:
                    logger.warning(f"[DEBUG_CLIENT] Clink SFX error: {e}")

    def _convert_countdown_word_to_number(self, text: str) -> str | None:
        """Convert countdown text like 'Ten!' to '10'."""
        word_to_number = {
            "ten": "10", "nine": "9", "eight": "8", "seven": "7",
            "six": "6", "five": "5", "four": "4", "three": "3",
            "two": "2", "one": "1",
        }
        # Strip punctuation and lowercase for flexible matching
        clean = text.strip().rstrip("!.-").lower()
        return word_to_number.get(clean)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Mario AI Client")
    parser.add_argument(
        "--server",
        default=SERVER_URL,
        help=f"Server WebSocket URL (default: {SERVER_URL})",
    )
    parser.add_argument(
        "--no-camera",
        action="store_true",
        help="Disable webcam presence detection",
    )
    args = parser.parse_args()

    client = MarioClient(server_url=args.server)

    if args.no_camera:
        client.presence = None  # Skip presence detection
        logger.info("Webcam presence detection disabled")

    client.start()


def _show_error_screen(error_msg: str, duration: float = 3.0):
    """Show a friendly error screen via Pygame instead of a raw traceback."""
    try:
        pygame_available = False
        try:
            import pygame as _pg
            if _pg.display.get_init():
                pygame_available = True
        except Exception:
            pass

        if pygame_available:
            screen = _pg.display.get_surface()
            if screen:
                w, h = screen.get_size()
                screen.fill((30, 10, 10))
                font_big = _pg.font.Font(None, 44)
                font_sm = _pg.font.Font(None, 26)

                line1 = font_big.render("Oops! Something went wrong!", True, (255, 80, 80))
                line2 = font_sm.render("Restarting automatically...", True, (200, 200, 200))
                # Truncate long error messages
                err_short = error_msg[:80] + ("..." if len(error_msg) > 80 else "")
                line3 = font_sm.render(err_short, True, (150, 150, 180))

                screen.blit(line1, (w // 2 - line1.get_width() // 2, h // 2 - 40))
                screen.blit(line2, (w // 2 - line2.get_width() // 2, h // 2 + 10))
                screen.blit(line3, (w // 2 - line3.get_width() // 2, h // 2 + 45))
                _pg.display.flip()

                # Hold the screen for `duration` seconds while draining events
                start = time.time()
                while time.time() - start < duration:
                    for event in _pg.event.get():
                        if event.type == _pg.QUIT:
                            return
                    _pg.time.wait(100)
    except Exception:
        pass  # Error screen itself failed — move on silently


def main_with_recovery():
    """Crash-recovery wrapper: never show a raw Python traceback on the party monitor."""
    import argparse
    parser = argparse.ArgumentParser(description="Mario AI Client")
    parser.add_argument(
        "--server",
        default=SERVER_URL,
        help=f"Server WebSocket URL (default: {SERVER_URL})",
    )
    parser.add_argument(
        "--no-camera",
        action="store_true",
        help="Disable webcam presence detection",
    )
    args = parser.parse_args()

    MAX_RAPID_CRASHES = 5
    RAPID_WINDOW = 30  # seconds
    crash_times = []

    while True:
        try:
            client = MarioClient(server_url=args.server)
            if args.no_camera:
                client.presence = None
                logger.info("Webcam presence detection disabled")
            logger.info("=== Starting client (crash recovery active) ===")
            client.start()
            break  # Clean exit
        except KeyboardInterrupt:
            logger.info("Interrupted by user — shutting down")
            break
        except Exception as e:
            logger.error(f"Client crashed: {e}", exc_info=True)
            crash_times.append(time.time())

            # Prevent infinite crash loops
            recent = [t for t in crash_times if time.time() - t < RAPID_WINDOW]
            crash_times[:] = recent
            if len(recent) >= MAX_RAPID_CRASHES:
                logger.critical(f"Too many crashes ({MAX_RAPID_CRASHES} in {RAPID_WINDOW}s) — giving up")
                _show_error_screen(f"Too many crashes. Giving up.\n{e}", duration=5.0)
                break

            _show_error_screen(str(e), duration=3.0)
            logger.info("Restarting client in 2 seconds...")
            time.sleep(2)
            continue


if __name__ == "__main__":
    main_with_recovery()
