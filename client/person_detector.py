"""YOLO-based person detection + face encoding for guest identification.

Camera faces the bathroom door. Detects people entering, encodes faces
for returning-guest identification. Privacy-first: no face images stored,
only 128-dim numerical encodings.
"""
import logging
import threading
import time
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)

DEBUG_PERSON = True

# Lazy imports for optional dependencies
_yolo_available = False
_face_rec_available = False

try:
    from ultralytics import YOLO
    _yolo_available = True
except ImportError:
    logger.debug("[person_detector] ultralytics not installed — YOLO disabled")

try:
    import face_recognition as face_rec
    _face_rec_available = True
except ImportError:
    logger.debug("[person_detector] face_recognition not installed — face ID disabled")


class DetectedPerson:
    """A person detected in a frame."""
    __slots__ = ("bbox", "confidence", "face_encoding", "face_location")

    def __init__(self, bbox: tuple, confidence: float,
                 face_encoding: Optional[np.ndarray] = None,
                 face_location: Optional[tuple] = None):
        self.bbox = bbox  # (x1, y1, x2, y2)
        self.confidence = confidence
        self.face_encoding = face_encoding  # 128-dim or None
        self.face_location = face_location


class PersonDetector:
    """Detects people via YOLO and encodes faces for identification.

    IMPORTANT: This is a pure frame processor — it does NOT own a camera.
    PresenceDetector already holds exclusive cv2.VideoCapture access (Windows
    enforces single-process camera lock). Frames are passed in via detect_people().
    """

    PERSON_CLASS_ID = 0  # COCO class 0 = person
    YOLO_CONFIDENCE = 0.5
    FACE_MATCH_TOLERANCE = 0.6  # Lower = stricter matching
    YOLO_FRAME_SKIP = 3  # Run YOLO every Nth frame

    def __init__(self, yolo_model: str = "yolov8n.pt"):
        self._yolo_model_name = yolo_model
        self._yolo = None
        self._frame_count = 0
        self._lock = threading.Lock()
        self.is_available = False
        self.on_person_detected = None  # callback(DetectedPerson)

        if DEBUG_PERSON:
            logger.info(f"[person_detector] init: yolo={yolo_model}")

        if _yolo_available:
            try:
                self._yolo = YOLO(yolo_model)
                self.is_available = True
                if DEBUG_PERSON:
                    logger.info("[person_detector] YOLO model loaded OK")
            except Exception as e:
                logger.warning(f"[person_detector] YOLO load failed: {e}")

    def detect_people(self, frame: np.ndarray) -> list:
        """Detect people in a frame. Returns list of DetectedPerson."""
        if not self.is_available or self._yolo is None:
            return []

        self._frame_count += 1
        if self._frame_count % self.YOLO_FRAME_SKIP != 0:
            return []

        try:
            results = self._yolo.predict(
                frame, conf=self.YOLO_CONFIDENCE,
                classes=[self.PERSON_CLASS_ID],
                verbose=False
            )
            people = []
            for r in results:
                for box in r.boxes:
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
                    conf = float(box.conf[0])
                    person = DetectedPerson(
                        bbox=(int(x1), int(y1), int(x2), int(y2)),
                        confidence=conf
                    )
                    # Try face encoding
                    if _face_rec_available:
                        person.face_encoding = self._encode_face(frame, person.bbox)
                    people.append(person)
            return people
        except Exception as e:
            logger.error(f"[person_detector] detect error: {e}")
            return []

    def _encode_face(self, frame: np.ndarray, bbox: tuple) -> Optional[np.ndarray]:
        """Extract 128-dim face encoding from person bounding box region."""
        try:
            x1, y1, x2, y2 = bbox
            h, w = frame.shape[:2]
            pad = int((x2 - x1) * 0.1)
            crop_x1 = max(0, x1 - pad)
            crop_y1 = max(0, y1 - pad)
            crop_x2 = min(w, x2 + pad)
            crop_y2 = min(h, y2 + pad)
            person_crop = frame[crop_y1:crop_y2, crop_x1:crop_x2]

            if person_crop.size == 0:
                return None

            rgb_crop = cv2.cvtColor(person_crop, cv2.COLOR_BGR2RGB)
            face_locations = face_rec.face_locations(rgb_crop, model="hog")
            if not face_locations:
                return None

            encodings = face_rec.face_encodings(rgb_crop, face_locations)
            if encodings:
                return encodings[0]  # 128-dim numpy array
            return None
        except Exception as e:
            logger.debug(f"[person_detector] face encode error: {e}")
            return None

    @staticmethod
    def compare_faces(enc1: np.ndarray, enc2: np.ndarray,
                      tolerance: float = 0.6) -> tuple:
        """Compare two face encodings. Returns (match, confidence)."""
        if enc1 is None or enc2 is None:
            return False, 0.0
        distance = np.linalg.norm(enc1 - enc2)
        confidence = max(0.0, 1.0 - distance)
        return distance <= tolerance, confidence

    @staticmethod
    def _empty_encoding() -> np.ndarray:
        """Return a zero 128-dim encoding (for testing)."""
        return np.zeros(128, dtype=np.float64)
