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
from mario_display import MarioDisplay, STATE_IDLE, STATE_TALKING, STATE_LISTENING, STATE_THINKING, STATE_GREETING
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

        # Wire up callbacks
        self.ws.on_text_response = self._on_mario_text
        self.ws.on_audio_response = self._on_mario_audio
        self.ws.on_connected = self._on_connected
        self.ws.on_disconnected = self._on_disconnected
        self.ws.on_state_update = self._on_state_update

        self.presence.on_enter = self._on_presence_enter
        self.presence.on_exit = self._on_presence_exit

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
        if not self.presence.start():
            logger.warning("Webcam not available — presence detection disabled")
            self.display.set_subtitle("⚠ No webcam detected")

        # Connect to server
        self.ws.connect()

        # Start audio streaming thread
        self._running = True
        self._audio_thread = threading.Thread(target=self._audio_stream_loop, daemon=True)
        self._audio_thread.start()

        logger.info("=== Mario AI Client Ready! ===")

        # Main display loop (must run on main thread for Pygame)
        try:
            while self._running:
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
        self.audio_capture.stop()
        self.audio_playback.stop()
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
                # Don't send while Mario is talking (avoid echo)
                if not self.audio_playback.is_playing:
                    self.ws.send_audio(bytes(audio_buffer))
                    self.display.set_state(STATE_LISTENING)
                audio_buffer = bytearray()

            time.sleep(0.01)

    def _on_mario_text(self, text: str, metadata: dict = None):
        """Called when Mario has something to say."""
        if DEBUG_CLIENT:
            logger.info(f"[DEBUG_CLIENT] Mario says: {text}")
        self.display.set_mario_text(text)
        self.display.set_state(STATE_TALKING)

        # Play sound effect if specified
        if metadata:
            sfx_name = metadata.get("sound_effect")
            if sfx_name:
                self.sfx.play(sfx_name)
            
            # Update display emotion
            emotion = metadata.get("emotion")
            if emotion:
                self.display.set_emotion(emotion)

    def _on_mario_audio(self, wav_bytes: bytes):
        """Called when Mario's voice audio arrives."""
        if DEBUG_CLIENT:
            logger.info(f"[DEBUG_CLIENT] Playing audio: {len(wav_bytes)} bytes")
        self.audio_playback.play(wav_bytes)

    def _on_connected(self):
        logger.info("Connected to Mario AI server!")
        self.display.connected = True
        self.display.set_state(STATE_GREETING)

    def _on_disconnected(self):
        logger.warning("Disconnected from server!")
        self.display.connected = False
        self.display.set_mario_text("Mama mia! Lost connection...")
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
        self.display.set_state(STATE_GREETING)
        self.sfx.play("greeting")

    def _on_presence_exit(self):
        """Someone left the bathroom."""
        logger.info("Presence lost — someone left!")
        self.ws.send_event({"type": "presence_exit"})
        self.display.set_state(STATE_IDLE)
        self.display.set_subtitle("")
        self.sfx.play("goodbye")


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
