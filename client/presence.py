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

    def start(self):
        """Start presence detection."""
        if DEBUG_PRESENCE:
            logger.info("[DEBUG_PRESENCE] PresenceDetector.start: opening camera")

        self._cap = cv2.VideoCapture(self.camera_index)
        if not self._cap.isOpened():
            logger.error("[DEBUG_PRESENCE] Failed to open camera!")
            return False

        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
        self._cap.set(cv2.CAP_PROP_FPS, 15)

        self._running = True
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
        if self._thread:
            self._thread.join(timeout=3.0)
        if self._cap:
            self._cap.release()
            self._cap = None

    def _detection_loop(self):
        """Background thread for continuous motion detection."""
        while self._running:
            ret, frame = self._cap.read()
            if not ret:
                time.sleep(0.1)
                continue

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

            time.sleep(0.033)  # ~30fps max
