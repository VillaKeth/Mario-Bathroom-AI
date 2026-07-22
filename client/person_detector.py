"""YOLO-based person detection + face encoding for guest identification.

Camera faces the bathroom door. Detects people entering, encodes faces
for returning-guest identification. Privacy-first: no face images stored,
only 128-dim numerical encodings.
"""
import logging
import os
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
    logger.warning(
        "[person_detector] ultralytics NOT installed — person detection DISABLED "
        "(no camera presence/face capture). pip install ultralytics"
    )

try:
    import face_recognition as face_rec
    _face_rec_available = True
except ImportError:
    logger.warning(
        "[person_detector] face_recognition NOT installed — face ID DISABLED, "
        "returning guests won't be recognized by face. pip install face_recognition"
    )


# Tiers that can afford the GPU-backed CNN face detector. `hardware.get_tier()`
# returns ultra/high/medium/low (four tiers, lowercase). The party box (24GB VRAM,
# 256GB RAM, 64 cores) resolves to "ultra"; the P1000 dev box resolves to "low".
_CNN_TIERS = ("ultra", "high")


def resolve_detector_model(tier: str, env_override: Optional[str] = None) -> str:
    """Pick the dlib face detector for a hardware tier. Env override always wins."""
    if env_override:
        return env_override
    return "cnn" if tier in _CNN_TIERS else "hog"


def _detect_tier() -> str:
    """Best-effort hardware tier. The client may not have server/ importable."""
    try:
        import sys as _sys
        _server_dir = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "server")
        if _server_dir not in _sys.path:
            _sys.path.insert(0, _server_dir)
        from hardware import get_tier
        return get_tier()
    except Exception:
        return "low"


class DetectedPerson:
    """A person detected in a frame."""
    __slots__ = ("bbox", "confidence", "face_encoding", "face_location", "face_quality")

    def __init__(self, bbox: tuple, confidence: float,
                 face_encoding: Optional[np.ndarray] = None,
                 face_location: Optional[tuple] = None,
                 face_quality: float = 0.0):
        self.bbox = bbox  # (x1, y1, x2, y2)
        self.confidence = confidence
        self.face_encoding = face_encoding  # 128-dim or None
        self.face_location = face_location
        self.face_quality = face_quality


def face_quality(rgb_crop: np.ndarray, face_location: tuple,
                 min_box_px: int = 80, min_sharpness: float = 40.0) -> float:
    """Score a detected face 0.0-1.0 for ENROLLMENT suitability.

    Combines three cheap checks and takes the worst: box size, blur (laplacian
    variance), and aspect ratio as a near-profile proxy. Matching ignores this
    score entirely — recognizing a guest from a mediocre frame is desirable,
    storing that frame as their reference is not.
    """
    try:
        top, right, bottom, left = face_location
        height, width = bottom - top, right - left
        if height <= 0 or width <= 0:
            return 0.0

        size_score = min(1.0, min(height, width) / float(min_box_px))

        ratio = width / float(height)
        aspect_score = 1.0 if 0.6 <= ratio <= 1.7 else 0.0

        face_img = rgb_crop[max(0, top):bottom, max(0, left):right]
        if face_img.size == 0:
            return 0.0
        gray = cv2.cvtColor(face_img, cv2.COLOR_RGB2GRAY)
        lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        sharp_score = min(1.0, lap_var / float(min_sharpness))

        return float(min(size_score, aspect_score, sharp_score))
    except Exception as e:
        logger.debug(f"[person_detector] quality scoring failed: {e}")
        return 0.0


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

    def __init__(self, yolo_model: str = "yolov8n.pt", face_detector_model: str = None,
                 match_tolerance: float = None, yolo_confidence: float = None,
                 frame_skip: int = None, hardware_tier: str = None):
        self._yolo_model_name = yolo_model
        self._yolo = None
        self._frame_count = 0
        self._lock = threading.Lock()
        self.is_available = False
        self.on_person_detected = None  # callback(DetectedPerson)

        # F6: tunable knobs (defaults preserve current behavior). The face detector
        # model can be raised to "cnn" on a GPU box (e.g. the RTX 3090 party machine)
        # for much better detection of non-frontal / low-light faces at the doorway.
        # Override in code or via env: FACE_DETECTOR_MODEL / FACE_MATCH_TOLERANCE.
        self.hardware_tier = hardware_tier or _detect_tier()
        self.face_detector_model = face_detector_model or resolve_detector_model(
            self.hardware_tier, os.environ.get("FACE_DETECTOR_MODEL"))
        if match_tolerance is None:
            match_tolerance = float(os.environ.get("FACE_MATCH_TOLERANCE", self.FACE_MATCH_TOLERANCE))
        self.match_tolerance = match_tolerance
        self.yolo_confidence = yolo_confidence if yolo_confidence is not None else self.YOLO_CONFIDENCE
        self.frame_skip = frame_skip if frame_skip is not None else self.YOLO_FRAME_SKIP

        # W3: enrollment quality thresholds (env-overridable for field tuning)
        self.min_box_px = int(os.environ.get("FACE_MIN_BOX_PX", "80"))
        self.min_sharpness = float(os.environ.get("FACE_MIN_SHARPNESS", "40.0"))

        # W5: run every frame while someone is at the door, back off when idle.
        self._last_person_ts = 0.0
        self.person_active_window = float(os.environ.get("PERSON_ACTIVE_WINDOW", "2.0"))

        if DEBUG_PERSON:
            logger.info(f"[person_detector] init: yolo={yolo_model} detector={self.face_detector_model} "
                        f"tol={self.match_tolerance} conf={self.yolo_confidence} skip={self.frame_skip}")

        if _yolo_available:
            try:
                self._yolo = YOLO(yolo_model)
                self.is_available = True
                if DEBUG_PERSON:
                    logger.info("[person_detector] YOLO model loaded OK")
            except Exception as e:
                logger.warning(f"[person_detector] YOLO load failed: {e}")

    def detect_people(self, frame) -> list:
        """Detect people in a frame. Returns list of DetectedPerson."""
        if not self.is_available or self._yolo is None:
            return []
        if frame is None or not isinstance(frame, np.ndarray) or frame.size == 0 or frame.ndim < 2:
            return []

        # W5: while a person was seen recently, examine every frame — more chances
        # at a good frontal capture. Fall back to the idle cadence after the window.
        now = time.time()
        effective_skip = 1 if (now - self._last_person_ts) < self.person_active_window \
            else self.frame_skip
        self._frame_count += 1
        if effective_skip > 1 and self._frame_count % effective_skip != 0:
            return []

        try:
            results = self._yolo.predict(
                frame, conf=self.yolo_confidence,
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
                        person.face_encoding, person.face_quality = self._encode_face(frame, person.bbox)
                    people.append(person)
            if people:
                self._last_person_ts = now
            return people
        except Exception as e:
            logger.error(f"[person_detector] detect error: {e}")
            return []

    def _encode_face(self, frame: np.ndarray, bbox: tuple) -> tuple:
        """Extract (128-dim face encoding, quality score) from a person bounding box."""
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
                return None, 0.0

            rgb_crop = cv2.cvtColor(person_crop, cv2.COLOR_BGR2RGB)
            face_locations = face_rec.face_locations(rgb_crop, model=self.face_detector_model)
            if not face_locations:
                return None, 0.0

            encodings = face_rec.face_encodings(rgb_crop, face_locations)
            if encodings:
                quality = face_quality(
                    rgb_crop, face_locations[0],
                    min_box_px=self.min_box_px, min_sharpness=self.min_sharpness)
                return encodings[0], quality      # 128-dim numpy array, 0.0-1.0
            return None, 0.0
        except Exception as e:
            logger.debug(f"[person_detector] face encode error: {e}")
            return None, 0.0

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
