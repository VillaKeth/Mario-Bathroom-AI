"""WebSocket client for connecting to the Mario AI server."""

import json
import logging
import threading
import time
import websocket

DEBUG_WS = True
logger = logging.getLogger(__name__)


class MarioWSClient:
    """WebSocket client that connects to the Mario AI server."""

    def __init__(self, server_url="ws://localhost:8765/ws"):
        self.server_url = server_url
        self._ws = None
        self._connected = False
        self._thread = None
        self._reconnect_delay = 2.0

        # Callbacks
        self.on_text_response = None    # Called with (text: str, metadata: dict)
        self.on_audio_response = None   # Called with (wav_bytes: bytes)
        self.on_state_update = None     # Called with (state: dict)
        self.on_connected = None
        self.on_disconnected = None

        self._expecting_audio = False

    def connect(self):
        """Connect to the server in a background thread."""
        if DEBUG_WS:
            logger.info(f"[DEBUG_WS] connect: connecting to {self.server_url}")

        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        """Connection loop with exponential backoff auto-reconnect."""
        attempt = 0
        MAX_RECONNECT_ATTEMPTS = 20
        while True:
            try:
                self._ws = websocket.WebSocketApp(
                    self.server_url,
                    on_open=self._on_open,
                    on_message=self._on_message,
                    on_error=self._on_error,
                    on_close=self._on_close,
                )
                attempt += 1
                self._ws.run_forever(ping_interval=30, ping_timeout=10)
            except Exception as e:
                logger.error(f"[DEBUG_WS] connection error: {e}")

            self._connected = False
            if attempt >= MAX_RECONNECT_ATTEMPTS:
                logger.error(f"[DEBUG_WS] max reconnect attempts ({MAX_RECONNECT_ATTEMPTS}) reached, giving up")
                break
            # Exponential backoff: 2s, 4s, 8s, max 30s
            delay = min(30, self._reconnect_delay * (2 ** min(attempt - 1, 4)))
            if DEBUG_WS:
                logger.info(f"[DEBUG_WS] reconnecting in {delay:.0f}s (attempt {attempt}/{MAX_RECONNECT_ATTEMPTS})...")
            time.sleep(delay)

    def _on_open(self, ws):
        if DEBUG_WS:
            logger.info("[DEBUG_WS] connected!")
        self._connected = True
        if self.on_connected:
            self.on_connected()

    def _on_message(self, ws, message):
        if isinstance(message, bytes):
            # Binary = audio response
            if DEBUG_WS:
                logger.info(f"[DEBUG_WS] received audio: {len(message)} bytes")
            if self.on_audio_response:
                self.on_audio_response(message)
            self._expecting_audio = False
        else:
            # Text = JSON message
            try:
                data = json.loads(message)
                msg_type = data.get("type")

                if msg_type == "mario_response":
                    if DEBUG_WS:
                        logger.info(f"[DEBUG_WS] mario says: {data.get('text', '')[:60]}")
                    self._expecting_audio = data.get("has_audio", False)
                    if self.on_text_response:
                        self.on_text_response(data.get("text", ""), data)

                elif msg_type == "state":
                    if self.on_state_update:
                        self.on_state_update(data)

                elif msg_type == "speaker_registered":
                    logger.info(f"[DEBUG_WS] speaker registered: {data.get('name')}")

            except json.JSONDecodeError as e:
                logger.error(f"[DEBUG_WS] invalid JSON: {e}")

    def _on_error(self, ws, error):
        logger.error(f"[DEBUG_WS] error: {error}")

    def _on_close(self, ws, close_status, close_msg):
        if DEBUG_WS:
            logger.info(f"[DEBUG_WS] disconnected: {close_status} {close_msg}")
        self._connected = False
        if self.on_disconnected:
            self.on_disconnected()

    def send_audio(self, audio_bytes: bytes):
        """Send audio data to the server."""
        if self._connected and self._ws:
            try:
                self._ws.send(audio_bytes, opcode=websocket.ABNF.OPCODE_BINARY)
            except Exception as e:
                logger.error(f"[DEBUG_WS] send_audio error: {e}")

    def send_event(self, event: dict):
        """Send a JSON event to the server."""
        if self._connected and self._ws:
            try:
                self._ws.send(json.dumps(event))
                if DEBUG_WS:
                    logger.info(f"[DEBUG_WS] sent event: {event.get('type')}")
            except Exception as e:
                logger.error(f"[DEBUG_WS] send_event error: {e}")

    @property
    def connected(self):
        return self._connected

    def close(self):
        """Close the connection."""
        if self._ws:
            self._ws.close()
