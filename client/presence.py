"""Presence detection using webcam motion detection."""

import logging
import time
import threading
import cv2
import numpy as np

DEBUG_PRESENCE = True
logger = logging.getLogger(__name__)

# Detection parameters
MOTION_THRESHOLD = 5000       # Minimum contour area to count as motion
ENTER_FRAMES = 10             # Frames of motion to trigger "enter"
EXIT_SECONDS = 8.0            # Seconds of no motion to trigger "exit"
FRAME_SKIP = 2                # Process every Nth frame for performance


class PresenceDetector:
    """Detects when someone enters/leaves using webcam motion detection."""

    def __init__(self, camera_index=0):
        self.camera_index = camera_index
        self._cap = None
        self._running = False
        self._thread = None
        self._camera_status = "disconnected"  # connected, reconnecting, disconnected
        self._bg_subtractor = cv2.createBackgroundSubtractorMOG2(
            history=500, varThreshold=50, detectShadows=False
        )

        # State
        self.someone_present = False
        self._motion_count = 0
        self._last_motion_time = 0
        self._frame_count = 0

        # Callbacks
        self.on_enter = None  # Called when someone enters
        self.on_exit = None   # Called when someone leaves

        # Person detection (optional — depends on ultralytics)
        self.person_detector = None
        self.on_person_detected = None  # callback(list[DetectedPerson])

    def enable_person_detection(self, config: dict = None):
        """Enable YOLO person detection. Call after __init__."""
        config = config or {}
        try:
            from person_detector import PersonDetector
            self.person_detector = PersonDetector(
                yolo_model=config.get("yolo_model", "yolov8n.pt")
            )
            if self.person_detector.is_available:
                logger.info("[DEBUG_PRESENCE] Person detection enabled (YOLO)")
            else:
                logger.info("[DEBUG_PRESENCE] Person detection unavailable (YOLO not installed)")
        except Exception as e:
            logger.warning(f"[DEBUG_PRESENCE] Person detection init failed: {e}")
            self.person_detector = None

    def start(self):
        """Start presence detection."""
        if DEBUG_PRESENCE:
            logger.info("[DEBUG_PRESENCE] PresenceDetector.start: opening camera")

        self._cap = cv2.VideoCapture(self.camera_index)
        if not self._cap.isOpened():
            logger.error("[DEBUG_PRESENCE] Failed to open camera!")
            self._cap.release()
            self._cap = None
            return False

        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
        self._cap.set(cv2.CAP_PROP_FPS, 15)

        self._running = True
        self._camera_status = "connected"
        self._thread = threading.Thread(target=self._detection_loop, daemon=True)
        self._thread.start()

        if DEBUG_PRESENCE:
            logger.info("[DEBUG_PRESENCE] PresenceDetector.start: running")
        return True

    def stop(self):
        """Stop presence detection."""
        if DEBUG_PRESENCE:
            logger.info("[DEBUG_PRESENCE] PresenceDetector.stop")
        self._running = False
        self._camera_status = "disconnected"
        if self._thread:
            self._thread.join(timeout=3.0)
        cap = self._cap
        self._cap = None
        if cap:
            cap.release()

    @property
    def camera_status(self):
        """Current camera status: connected, reconnecting, disconnected."""
        return self._camera_status

    def _detection_loop(self):
        """Background thread for continuous motion detection."""
        _consecutive_read_failures = 0
        _camera_retry_count = 0
        _max_camera_retries = 10
        while self._running:
            if self._cap is None or not self._cap.isOpened():
                # Exponential backoff camera recovery
                _camera_retry_count += 1
                if _camera_retry_count > _max_camera_retries:
                    logger.error(f"[DEBUG_PRESENCE] Camera failed {_max_camera_retries} retries, waiting 60s before reset")
                    time.sleep(60.0)
                    _camera_retry_count = 0  # Reset and try again indefinitely
                    continue
                backoff = min(30, 2 ** min(_camera_retry_count - 1, 4))
                logger.warning(f"[DEBUG_PRESENCE] Camera not open, retry {_camera_retry_count}/{_max_camera_retries} in {backoff}s")
                self._camera_status = "reconnecting"
                time.sleep(backoff)
                try:
                    self._cap = cv2.VideoCapture(self.camera_index)
                    if self._cap.isOpened():
                        logger.info("[DEBUG_PRESENCE] Camera reconnected successfully!")
                        _camera_retry_count = 0
                        self._camera_status = "connected"
                except Exception as e:
                    logger.error(f"[DEBUG_PRESENCE] Camera reconnect failed: {e}")
                continue
            ret, frame = self._cap.read()
            if not ret:
                _consecutive_read_failures += 1
                if _consecutive_read_failures > 30:
                    logger.warning("[DEBUG_PRESENCE] Camera read failed 30 times, restarting camera...")
                    try:
                        self._cap.release()
                        self._cap = None  # Triggers reconnection logic above
                        _consecutive_read_failures = 0
                    except Exception as e:
                        logger.error(f"[DEBUG_PRESENCE] Camera release failed: {e}")
                        self._cap = None
                        _consecutive_read_failures = 0
                time.sleep(0.1)
                continue
            _consecutive_read_failures = 0

            self._frame_count += 1
            if self._frame_count % FRAME_SKIP != 0:
                continue

            # Apply background subtraction
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (21, 21), 0)
            fg_mask = self._bg_subtractor.apply(gray)

            # Clean up mask
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
            fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel)
            fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, kernel)

            # Find contours
            contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            motion_detected = any(cv2.contourArea(c) > MOTION_THRESHOLD for c in contours)

            now = time.time()

            if motion_detected:
                self._last_motion_time = now
                self._motion_count += 1

                if not self.someone_present and self._motion_count >= ENTER_FRAMES:
                    self.someone_present = True
                    self._motion_count = 0
                    if DEBUG_PRESENCE:
                        logger.info("[DEBUG_PRESENCE] === SOMEONE ENTERED ===")
                    if self.on_enter:
                        self.on_enter()
            else:
                self._motion_count = max(0, self._motion_count - 1)

                if self.someone_present and (now - self._last_motion_time) > EXIT_SECONDS:
                    self.someone_present = False
                    if DEBUG_PRESENCE:
                        logger.info("[DEBUG_PRESENCE] === SOMEONE LEFT ===")
                    if self.on_exit:
                        self.on_exit()

            # Person detection on the SAME frame (no separate camera)
            if self.person_detector and self.person_detector.is_available and frame is not None:
                try:
                    people = self.person_detector.detect_people(frame)
                    if people and self.on_person_detected:
                        self.on_person_detected(people)  # Pass entire list
                except Exception as e:
                    logger.debug(f"[DEBUG_PRESENCE] Person detection error: {e}")

            time.sleep(0.033)  # ~30fps max
