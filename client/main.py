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

        self._running = False
        self._audio_thread = None
        self._health_thread = None
        self._last_play_end_time = 0  # Echo cancellation tracking

        # Wire up callbacks
        self.ws.on_text_response = self._on_mario_text
        self.ws.on_audio_response = self._on_mario_audio
        self.ws.on_connected = self._on_connected
        self.ws.on_disconnected = self._on_disconnected
        self.ws.on_state_update = self._on_state_update

        self.presence.on_enter = self._on_presence_enter
        self.presence.on_exit = self._on_presence_exit

        # Wire up keyboard input from display
        self.display.on_keyboard_submit = self._on_keyboard_submit

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
        if hasattr(self, '_speaking_timer') and self._speaking_timer is not None:
            self._speaking_timer.cancel()
        self.audio_capture.stop()
        self.audio_playback.stop()
        if self.presence:
            self.presence.stop()
        self.ws.close()
        self.display.quit()

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
                # Cap buffer to prevent memory bloat under heavy audio load
                logger.warning(f"[DEBUG_CLIENT] Audio buffer overflow ({len(audio_buffer)} bytes), trimming")
                audio_buffer = audio_buffer[-8000:]

            time.sleep(0.01)

    def _on_mario_text(self, text: str, metadata: dict = None):
        """Called when Mario has something to say."""
        if DEBUG_CLIENT:
            logger.info(f"[DEBUG_CLIENT] Mario says: {text}")
        self.display.set_thinking(False)
        self.display.set_mario_text(text)
        self.display.set_state(STATE_TALKING)
        self.display._speaking = True

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

            # Track response time for display
            resp_time = metadata.get("response_time")
            if resp_time:
                self.display._last_response_time = resp_time

    def _on_mario_audio(self, wav_bytes: bytes):
        """Called when Mario's voice audio arrives."""
        if not wav_bytes or len(wav_bytes) < 44:
            logger.warning("[DEBUG_CLIENT] Received empty or too-small audio, skipping")
            return
        if DEBUG_CLIENT:
            logger.info(f"[DEBUG_CLIENT] Playing audio: {len(wav_bytes)} bytes")
        self.audio_playback.play(wav_bytes)
        # Track when playback finishes for echo cancellation
        duration = max(0.5, len(wav_bytes) / 48000)
        self._last_play_end_time = time.time() + duration
        # Schedule speaking state clear using a reusable timer (avoids thread leak)
        if hasattr(self, '_speaking_timer') and self._speaking_timer is not None:
            self._speaking_timer.cancel()
        self._speaking_timer = threading.Timer(duration, self._clear_speaking_state)
        self._speaking_timer.daemon = True
        self._speaking_timer.start()

    def _clear_speaking_state(self):
        """Clear speaking state after audio finishes."""
        self.display._speaking = False
        self.display.set_state(STATE_IDLE)

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


if __name__ == "__main__":
    main()
