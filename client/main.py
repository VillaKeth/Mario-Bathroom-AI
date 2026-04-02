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

from audio_capture import AudioCapture
from audio_playback import AudioPlayback
from presence import PresenceDetector
from mario_display import (MarioDisplay, STATE_IDLE, STATE_TALKING, STATE_LISTENING,
                           STATE_THINKING, STATE_GREETING, STATE_ENTERING, STATE_EXITING)
from ws_client import MarioWSClient
from sound_effects import SoundEffects

DEBUG_CLIENT = True
DEBUG_AUDIO = True
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("mario-client")

# Load config
CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")
client_config = {}
if os.path.exists(CONFIG_PATH):
    with open(CONFIG_PATH) as f:
        client_config = json.load(f).get("client", {})
    logger.info(f"Loaded config from {CONFIG_PATH}")

SERVER_URL = client_config.get("server_url", "ws://localhost:8765/ws")


class MarioClient:
    """Main client that ties everything together."""

    def __init__(self, server_url=SERVER_URL):
        self.audio_capture = AudioCapture()
        self.audio_playback = AudioPlayback()
        self.presence = PresenceDetector()
        self.display = MarioDisplay()
        self.ws = MarioWSClient(server_url)
        self.sfx = SoundEffects()

        # Apply audio gain from config
        audio_gain = client_config.get("audio_gain", 1.0)
        self.audio_playback.set_volume(audio_gain)
        if DEBUG_AUDIO:
            logger.info(f"[DEBUG_AUDIO] Initial audio gain from config: {audio_gain}")

        self._running = False
        self._audio_thread = None
        self._health_thread = None
        self._last_play_end_time = 0  # Echo cancellation tracking
        self._memorial_active = False  # Suppresses idle text during memorial
        self._audio_wait_cancel = threading.Event()  # Cancel audio-wait thread

        # Wire up callbacks
        self.ws.on_text_response = self._on_mario_text
        self.ws.on_audio_response = self._on_mario_audio
        self.ws.on_audio_chunk = self._on_audio_chunk
        self.ws.on_connected = self._on_connected
        self.ws.on_disconnected = self._on_disconnected
        self.ws.on_state_update = self._on_state_update
        self.ws.on_leaderboard_update = self._on_leaderboard_update
        self.ws.on_memorial_event = self._on_memorial_event

        self.presence.on_enter = self._on_presence_enter
        self.presence.on_exit = self._on_presence_exit

        # Enable person detection if configured
        if client_config.get("enable_person_detection", False):
            self.presence.enable_person_detection(client_config)
            self.presence.on_person_detected = self._on_person_detected

        # Wire up keyboard input from display
        self.display.on_keyboard_submit = self._on_keyboard_submit
        self.display.on_volume_change = self._on_volume_change

    def start(self):
        """Start all client components."""
        logger.info("=== Mario AI Client Starting ===")

        # Initialize display and sound effects
        self.display.init()
        self.display.set_state(STATE_IDLE)
        self.display.set_mario_text("Connecting to server...")
        self.sfx.init()

        # Start audio
        if not self.audio_capture.start():
            logger.warning("No microphone available — audio capture disabled")
            self.display.set_subtitle("⚠ No microphone detected")
        self.audio_playback.start()

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
                    self.display.set_mario_text("Server connected! Let's-a go!")
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
        
        # Update closed captions
        if self.display.captions:
            self.display.captions.set_text(text)

        if metadata:
            sfx_name = metadata.get("sound_effect")
            if sfx_name:
                self.sfx.play(sfx_name)

            emotion = metadata.get("emotion")
            if emotion:
                self.display.set_emotion(emotion)

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
        self.audio_playback.play(wav_bytes)
        # Track when playback finishes for echo cancellation
        # 48000 = 24kHz sample rate × 2 bytes/sample (16-bit mono PCM)
        duration = max(0.5, len(wav_bytes) / 48000)
        self._last_play_end_time = time.time() + duration
        # Start audio-wait thread that polls until playback actually finishes
        self._audio_wait_cancel.set()
        self._audio_wait_thread = threading.Thread(target=self._wait_for_audio_complete, daemon=True)
        self._audio_wait_thread.start()

    def _on_audio_chunk(self, wav_bytes: bytes, chunk_meta: dict):
        """Called when a streaming audio chunk arrives (sentence streaming)."""
        if not wav_bytes or len(wav_bytes) < 44:
            logger.warning("[DEBUG_CLIENT] Received empty audio chunk, skipping")
            return
        chunk_idx = chunk_meta.get("chunk_index", "?")
        total = chunk_meta.get("total_chunks", "?")
        is_last = chunk_meta.get("is_last", False)
        if DEBUG_CLIENT:
            logger.info(f"[DEBUG_CLIENT] Audio chunk {chunk_idx}/{total} ({len(wav_bytes)} bytes, is_last={is_last})")
        # Queue the chunk — AudioPlayback plays them sequentially
        self.audio_playback.play(wav_bytes)
        # Keep speaking state active; extend echo cancellation window
        duration = max(0.5, len(wav_bytes) / 48000)
        self._last_play_end_time = time.time() + duration
        # Only schedule speaking state clear on the last chunk
        if is_last:
            self._audio_wait_cancel.set()
            self._audio_wait_thread = threading.Thread(target=self._wait_for_audio_complete, daemon=True)
            self._audio_wait_thread.start()

    def _clear_speaking_state(self):
        """Clear speaking state after audio finishes."""
        self.display._speaking = False
        self.display.set_state(STATE_IDLE)
        
        # Clear closed captions
        if self.display.captions:
            self.display.captions.clear()

    def _on_connected(self):
        logger.info("Connected to Mario AI server!")
        self.display.connected = True
        self.display._reconnect_info = None
        self.display.set_state(STATE_GREETING)

    def _on_disconnected(self):
        logger.warning("Disconnected from server!")
        self.display.connected = False
        self.display._reconnect_info = self.ws.reconnect_info
        self.display.set_mario_text("Mama mia! Reconnecting...")
        self.display.set_state(STATE_IDLE)

    def _on_state_update(self, state: dict):
        if state.get("thinking"):
            self.display.set_state(STATE_THINKING)
            self.display.set_mario_text("Hmm, let me-a think...")
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

    def _on_person_detected(self, person):
        """Send person detection event to server via WebSocket."""
        try:
            event = {
                "type": "person_detected",
                "confidence": person.confidence,
                "has_face": person.face_encoding is not None,
            }
            if person.face_encoding is not None:
                event["face_encoding"] = person.face_encoding.tolist()
            self.ws.send_event(event)
        except Exception as e:
            logger.debug(f"Person detection event send failed: {e}")

    def _health_ping_loop(self):
        """Send periodic health pings to the server."""
        while self._running:
            time.sleep(60)
            if self.ws.connected:
                self.ws.send_health_ping()

    def _on_keyboard_submit(self, text: str):
        """Called when user submits text via keyboard input."""
        if DEBUG_CLIENT:
            logger.info(f"[DEBUG_CLIENT] Keyboard input: {text}")
        self.display.set_subtitle(text)
        self.display.set_thinking(True)
        if self.ws.connected:
            self.ws.send_event({"type": "text_input", "text": text})

    def _on_volume_change(self, delta: float):
        """Called when user adjusts volume with +/- keys."""
        current = self.audio_playback.get_volume()
        new_vol = max(0.0, min(2.0, current + delta))
        self.audio_playback.set_volume(new_vol)
        self.display.show_volume(new_vol)
        if DEBUG_AUDIO:
            logger.info(f"[DEBUG_AUDIO] Volume changed: {current:.1f} -> {new_vol:.1f}")

    def _on_leaderboard_update(self, data: dict):
        """Called when server sends leaderboard update."""
        if DEBUG_CLIENT:
            logger.info(f"[DEBUG_CLIENT] Leaderboard update received")
        self.display.update_leaderboard(data)

    def _on_memorial_event(self, data: dict):
        """Called when server sends memorial event — handles all 5 phases."""
        phase = data.get("phase", "silence")
        name = data.get("name", "")
        text = data.get("text", "")
        duration = data.get("duration", 15)
        if DEBUG_CLIENT:
            logger.info(f"[DEBUG_CLIENT] Memorial event: phase={phase} name={name}")

        # Set memorial active on first phase, clear after fadeout
        if phase == "announcement":
            self._memorial_active = True
        elif phase == "fadeout":
            # Clear flag after fadeout animation completes
            def _clear_flag():
                time.sleep(duration + 3)
                self._memorial_active = False
                if DEBUG_CLIENT:
                    logger.info("[DEBUG_CLIENT] Memorial flag cleared after fadeout")
            threading.Thread(target=_clear_flag, daemon=True).start()

        # Start/stop memorial music
        if phase == "music":
            music_path = os.path.join(os.path.dirname(__file__), "assets", "music", "lisa_webb_memorial.mp3")
            if os.path.exists(music_path):
                self.audio_playback.play_memorial_music(music_path, loops=1)  # Play twice
            else:
                logger.warning(f"[DEBUG_CLIENT] Memorial music not found: {music_path}")
        elif phase == "fadeout":
            self.audio_playback.stop_memorial_music(fadeout_ms=3000)

        # Route to display
        if self.display:
            self.display.show_memorial(name, phase, text, duration)

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

                line1 = font_big.render("Oops! Mario tripped on a Goomba!", True, (255, 80, 80))
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
