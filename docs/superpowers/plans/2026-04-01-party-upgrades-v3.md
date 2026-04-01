# Party Upgrades v3: Webcam + VIP + Personality + UI + Performance

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add webcam-based guest detection with face recognition, enrich VIP memory system, improve Mario's personality, polish the client UI, and tune ULTRA-tier performance.

**Architecture:** 5 independent workstreams that can be parallelized. Webcam runs client-side (YOLO + face_recognition), sends enriched events to server via existing WebSocket. VIP profiles are JSON files in server/data/vip_profiles/. Personality changes are prompt engineering in mario_prompt.py. UI changes are in client/mario_display.py. Performance tuning is config/hardware.py changes.

**Tech Stack:** ultralytics (YOLOv8), face_recognition (dlib), OpenCV (already installed), Qdrant (already running), Pygame (client), FastAPI (server)

---

## File Structure

### New Files:
- `client/person_detector.py` — YOLO person detection + face encoding (client-side)
- `server/face_memory.py` — Face encoding storage/matching (server-side)
- `server/data/vip_profiles/party_guests.json` — Additional guest profiles template
- `tests/test_person_detector.py` — Webcam detection tests
- `tests/test_face_memory.py` — Face matching tests

### Modified Files:
- `client/presence.py` — Integrate person_detector into motion detection flow
- `client/main.py` — Wire person detection callbacks
- `client/requirements.txt` — Add ultralytics, face_recognition
- `server/main.py` — Handle person_detected events, face matching
- `server/memory.py` — Add face_encodings table
- `server/mario_prompt.py` — Phase-specific prompts, guest typing, appearance context
- `server/command_handlers.py` — Dynamic roasting from conversation context
- `server/vip_knowledge.py` — Enrich profiles, add more hooks
- `server/data/vip_profiles/jacob_hoppenstedt.json` — More memories, deeper hooks
- `server/hardware.py` — ULTRA performance tuning
- `client/mario_display.py` — 4K fullscreen, chat history, typewriter speed
- `config.json` / `config.example.json` — Webcam + performance config fields

---

### Task 1: Webcam Person Detection (client-side)

**Files:**
- Create: `client/person_detector.py`
- Modify: `client/requirements.txt`
- Test: `tests/test_person_detector.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_person_detector.py
import pytest
import numpy as np

def test_person_detector_import():
    from client.person_detector import PersonDetector
    assert PersonDetector is not None

def test_detector_init():
    """PersonDetector initializes without crashing (pure frame processor, no camera)."""
    from client.person_detector import PersonDetector
    det = PersonDetector()
    assert det is not None
    # is_available depends on whether ultralytics is installed

def test_face_encoding_shape():
    """Face encodings should be 128-dimensional vectors."""
    from client.person_detector import PersonDetector
    det = PersonDetector()
    fake_encoding = det._empty_encoding()
    assert len(fake_encoding) == 128

def test_face_match_identical():
    """Identical encodings should match with high confidence."""
    from client.person_detector import PersonDetector
    det = PersonDetector()
    enc = np.random.randn(128).astype(np.float64)
    match, confidence = det.compare_faces(enc, enc)
    assert match == True
    assert confidence > 0.99

def test_face_match_different():
    """Very different encodings should not match."""
    from client.person_detector import PersonDetector
    det = PersonDetector()
    enc1 = np.ones(128, dtype=np.float64)
    enc2 = -np.ones(128, dtype=np.float64)
    match, confidence = det.compare_faces(enc1, enc2)
    assert match == False

def test_detect_people_returns_list():
    """detect_people should return a list even on fake frame."""
    from client.person_detector import PersonDetector
    det = PersonDetector()
    # Create a blank frame
    frame = np.zeros((240, 320, 3), dtype=np.uint8)
    results = det.detect_people(frame)
    assert isinstance(results, list)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_person_detector.py -v`
Expected: FAIL (ImportError — module doesn't exist yet)

- [ ] **Step 3: Install dependencies**

**IMPORTANT — dlib/face_recognition on Windows:**
`face_recognition` depends on `dlib` which requires CMake + C++ build tools.
Install approach (in order of preference):
1. Pre-built wheel: `pip install dlib-bin` (pre-compiled, no build tools needed)
2. If that fails: Install Visual Studio Build Tools + CMake, then `pip install dlib`
3. Fallback: PersonDetector gracefully degrades — YOLO works without face_recognition

```bash
pip install ultralytics
pip install dlib-bin  # Pre-built wheel (avoids CMake requirement)
pip install face_recognition
```

Update `client/requirements.txt`:
```
ultralytics>=8.2.0
dlib-bin>=19.24.0
face_recognition>=1.3.0
```

- [ ] **Step 4: Write PersonDetector**

```python
# client/person_detector.py
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

    def detect_people(self, frame: np.ndarray) -> list[DetectedPerson]:
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
            # Expand bbox slightly for face detection
            h, w = frame.shape[:2]
            pad = int((x2 - x1) * 0.1)
            crop_x1 = max(0, x1 - pad)
            crop_y1 = max(0, y1 - pad)
            crop_x2 = min(w, x2 + pad)
            crop_y2 = min(h, y2 + pad)
            person_crop = frame[crop_y1:crop_y2, crop_x1:crop_x2]

            if person_crop.size == 0:
                return None

            # Convert BGR to RGB for face_recognition
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
                      tolerance: float = 0.6) -> tuple[bool, float]:
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
```

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/test_person_detector.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add client/person_detector.py client/requirements.txt tests/test_person_detector.py
git commit -m "feat: add YOLO person detection + face encoding (client-side)"
```

---

### Task 2: Face Memory Server-Side Storage

**Files:**
- Create: `server/face_memory.py`
- Modify: `server/memory.py` (add face_encodings table)
- Test: `tests/test_face_memory.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_face_memory.py
import pytest
import numpy as np
import json
import sqlite3
import tempfile
import os

def test_face_memory_import():
    from server.face_memory import FaceMemory
    assert FaceMemory is not None

def test_store_and_match_face():
    """Store a face encoding, then match it."""
    from server.face_memory import FaceMemory
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        fm = FaceMemory(db_path)
        encoding = np.random.randn(128).astype(np.float64)
        fm.store_face(person_id=1, name="TestUser", encoding=encoding)
        match = fm.find_match(encoding)
        assert match is not None
        assert match["person_id"] == 1
        assert match["name"] == "TestUser"
        assert match["confidence"] > 0.99

def test_no_match_for_unknown():
    """Unknown face should return None."""
    from server.face_memory import FaceMemory
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        fm = FaceMemory(db_path)
        known = np.ones(128, dtype=np.float64)
        fm.store_face(person_id=1, name="Known", encoding=known)
        unknown = -np.ones(128, dtype=np.float64)
        match = fm.find_match(unknown, tolerance=0.4)
        assert match is None

def test_multiple_faces():
    """Should match correct person among multiple stored faces."""
    from server.face_memory import FaceMemory
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        fm = FaceMemory(db_path)
        enc_a = np.random.randn(128).astype(np.float64)
        enc_b = np.random.randn(128).astype(np.float64)
        fm.store_face(person_id=1, name="Alice", encoding=enc_a)
        fm.store_face(person_id=2, name="Bob", encoding=enc_b)
        # Add slight noise to enc_a
        noisy_a = enc_a + np.random.randn(128) * 0.05
        match = fm.find_match(noisy_a)
        assert match is not None
        assert match["name"] == "Alice"

def test_get_all_faces():
    """Should return all stored face entries."""
    from server.face_memory import FaceMemory
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        fm = FaceMemory(db_path)
        fm.store_face(1, "A", np.zeros(128))
        fm.store_face(2, "B", np.ones(128))
        all_faces = fm.get_all_faces()
        assert len(all_faces) == 2

def test_update_existing_face():
    """Storing same person_id again should update, not duplicate."""
    from server.face_memory import FaceMemory
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        fm = FaceMemory(db_path)
        enc1 = np.random.randn(128).astype(np.float64)
        enc2 = np.random.randn(128).astype(np.float64)
        fm.store_face(1, "User", enc1)
        fm.store_face(1, "User", enc2)  # Update
        all_faces = fm.get_all_faces()
        assert len(all_faces) == 1  # Should not duplicate
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_face_memory.py -v`
Expected: FAIL (ImportError)

- [ ] **Step 3: Write FaceMemory**

```python
# server/face_memory.py
"""Face encoding storage and matching for guest identification.

Stores 128-dim face_recognition encodings in SQLite. Matches incoming
face encodings against stored ones using Euclidean distance.
Privacy: only numerical vectors stored, never images.
"""
import json
import logging
import sqlite3
import threading
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)
DEBUG_FACE = True


class FaceMemory:
    """Persistent face encoding storage with matching."""

    def __init__(self, db_path: str, match_tolerance: float = 0.6):
        self._db_path = db_path
        self._tolerance = match_tolerance
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS face_encodings (
                    person_id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    encoding TEXT NOT NULL,
                    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    visit_count INTEGER DEFAULT 1
                )
            """)
            conn.commit()

    def store_face(self, person_id: int, name: str, encoding: np.ndarray):
        """Store or update a face encoding."""
        enc_json = json.dumps(encoding.tolist())
        with self._lock:
            with sqlite3.connect(self._db_path) as conn:
                existing = conn.execute(
                    "SELECT person_id FROM face_encodings WHERE person_id = ?",
                    (person_id,)
                ).fetchone()
                if existing:
                    conn.execute("""
                        UPDATE face_encodings
                        SET encoding = ?, last_seen = CURRENT_TIMESTAMP,
                            visit_count = visit_count + 1
                        WHERE person_id = ?
                    """, (enc_json, person_id))
                else:
                    conn.execute("""
                        INSERT INTO face_encodings (person_id, name, encoding)
                        VALUES (?, ?, ?)
                    """, (person_id, name, enc_json))
                conn.commit()
        if DEBUG_FACE:
            logger.info(f"[face_memory] stored face for {name} (id={person_id})")

    def find_match(self, encoding: np.ndarray,
                   tolerance: Optional[float] = None) -> Optional[dict]:
        """Find best matching face. Returns dict or None.
        Uses early-exit: stops scanning if confidence > 0.95 (near-exact match).
        For party-scale (20-50 guests), linear scan is <1ms."""
        tol = tolerance or self._tolerance
        with self._lock:
            with sqlite3.connect(self._db_path) as conn:
                rows = conn.execute(
                    "SELECT person_id, name, encoding, visit_count FROM face_encodings"
                ).fetchall()

        if not rows:
            return None

        best_match = None
        best_distance = float("inf")

        for pid, name, enc_json, visits in rows:
            stored = np.array(json.loads(enc_json), dtype=np.float64)
            distance = float(np.linalg.norm(encoding - stored))
            if distance < best_distance and distance <= tol:
                best_distance = distance
                best_match = {
                    "person_id": pid,
                    "name": name,
                    "confidence": max(0.0, 1.0 - distance),
                    "visit_count": visits,
                }
                # Early exit for near-exact match (>95% confidence)
                if best_match["confidence"] > 0.95:
                    break

        return best_match

    def get_all_faces(self) -> list[dict]:
        """Return all stored face entries (without encodings)."""
        with self._lock:
            with sqlite3.connect(self._db_path) as conn:
                rows = conn.execute(
                    "SELECT person_id, name, visit_count, first_seen, last_seen FROM face_encodings"
                ).fetchall()
        return [
            {"person_id": r[0], "name": r[1], "visit_count": r[2],
             "first_seen": r[3], "last_seen": r[4]}
            for r in rows
        ]
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_face_memory.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add server/face_memory.py tests/test_face_memory.py
git commit -m "feat: add face encoding storage + matching (server-side)"
```

---

### Task 3: Wire Webcam Detection into Client + Server

**Files:**
- Modify: `client/presence.py` — Integrate PersonDetector
- Modify: `client/main.py` — Wire person detection callbacks
- Modify: `server/main.py` — Handle `person_detected` WebSocket events
- Modify: `config.json` / `config.example.json` — Add webcam config fields

- [ ] **Step 1: Add config fields**

Add to `config.json` and `config.example.json` under `"client"`:
```json
{
  "client": {
    "enable_person_detection": true,
    "yolo_model": "yolov8n.pt",
    "face_match_tolerance": 0.6,
    "person_detection_frame_skip": 3
  }
}
```

- [ ] **Step 2: Modify client/presence.py**

**CRITICAL: PersonDetector is a pure frame processor — NO camera ownership.**
PresenceDetector already holds the exclusive `cv2.VideoCapture` (Windows enforces
single-process lock). We pass its frames to PersonDetector.

Add to `PresenceDetector.__init__`:
```python
# After existing motion detection setup
self.person_detector = None
if config.get("enable_person_detection", False):
    try:
        from client.person_detector import PersonDetector
        self.person_detector = PersonDetector(
            yolo_model=config.get("yolo_model", "yolov8n.pt")
        )
    except Exception as e:
        logger.warning(f"Person detection unavailable: {e}")
```

Add to `_process_frame()` after motion detection — reuse the SAME frame already captured:
```python
# After motion detected, also run person detection on the SAME frame
# (no separate camera — PersonDetector is a pure frame processor)
if self.person_detector and self.person_detector.is_available:
    people = self.person_detector.detect_people(frame)
    for person in people:
        if self.on_person_detected:
            self.on_person_detected(person)
```

- [ ] **Step 3: Modify client/main.py**

Wire callback in `MarioClient.__init__`:
```python
self.presence.on_person_detected = self._on_person_detected
```

Add handler:
```python
def _on_person_detected(self, person):
    """Send person detection event to server."""
    event = {
        "type": "person_detected",
        "confidence": person.confidence,
        "has_face": person.face_encoding is not None,
        "face_encoding": person.face_encoding.tolist() if person.face_encoding is not None else None,
    }
    self.ws_client.send_json(event)
```

- [ ] **Step 4: Modify server/main.py**

In `handle_event()`, add handler for `person_detected`:
```python
elif event_type == "person_detected":
    face_enc = event.get("face_encoding")
    if face_enc and _face_memory:
        enc_array = np.array(face_enc, dtype=np.float64)
        match = _face_memory.find_match(enc_array)
        if match:
            state_current["detected_guest"] = match["name"]
            state_current["guest_visits"] = match["visit_count"]
            logger.info(f"[WEBCAM] Recognized returning guest: {match['name']} (visits: {match['visit_count']})")
        else:
            state_current["detected_guest"] = None
            logger.info("[WEBCAM] New guest detected (no face match)")
```

Initialize FaceMemory at server startup:
```python
from server.face_memory import FaceMemory
_face_memory = FaceMemory(os.path.join(DATA_DIR, "memory.db"))
```

- [ ] **Step 5: Test end-to-end manually**

Start server, start client with webcam. Verify:
- YOLO detects person entering bathroom
- Face encoding sent to server
- Server logs "New guest" or "Recognized returning guest"
- No crashes, no performance degradation

- [ ] **Step 6: Commit**

```bash
git add client/presence.py client/main.py server/main.py config.json config.example.json
git commit -m "feat: wire webcam person detection into client/server pipeline"
```

---

### Task 4: Enrich VIP Memories for Jacob + Add Guest Template

**Files:**
- Modify: `server/data/vip_profiles/jacob_hoppenstedt.json` — More memories, deeper hooks
- Create: `server/data/vip_profiles/party_guests.json` — Template for adding other guests
- Modify: `server/vip_knowledge.py` — Support `appearance_hints` field

- [ ] **Step 1: Read current Jacob profile**

Read: `server/data/vip_profiles/jacob_hoppenstedt.json`

- [ ] **Step 2: Enrich Jacob's profile**

Add these new fields/entries to jacob_hoppenstedt.json:

Additional personality_notes:
```json
"personality_notes": [
    ... existing notes ...,
    "Jacob is a loyal friend who values deep conversations — if you get him talking about a project, he lights up",
    "He's competitive but a good sport — challenge him and he'll rise to it",
    "He has a dry sense of humor and loves absurd jokes",
    "He can go from talking code to talking philosophy in one sentence",
    "He loves his Florida sunshine but can handle the cold"
]
```

Additional conversation_hooks:
```json
"conversation_hooks": [
    ... existing hooks ...,
    "Ask Jacob which of his projects he's most proud of and watch him debate himself",
    "Mention the Gators and see if he does the chomp — he probably will",
    "Ask about his favorite programming language — he'll have STRONG opinions",
    "Bring up his published book chapter — he'll be humble about it but it's impressive",
    "Ask what he'd build if he had unlimited time and resources",
    "Challenge him to explain one of his projects in one sentence — watch him struggle",
    "Ask about growing up in St. Pete — beach stories guaranteed",
    "Mention his dad Carl or mom Stacy — family clearly matters to him"
]
```

Add `appearance_hints` field (for webcam integration):
```json
"appearance_hints": {
    "description": "22-year-old male, computer science student",
    "notes": "Birthday boy! Should be the center of attention tonight"
}
```

- [ ] **Step 3: Create party_guests template**

```json
{
    "name": "Party Guest Template",
    "aliases": [],
    "bio": {
        "birthday": null,
        "hometown": null,
        "education": null
    },
    "personality_notes": [
        "Fill in personality traits as you learn them during the party"
    ],
    "conversation_hooks": [
        "Ask what brings them to the party",
        "Find out how they know the birthday boy"
    ],
    "_instructions": "Copy this file, rename to guest_name.json, fill in details. Mario will auto-load it."
}
```

- [ ] **Step 4: Update vip_knowledge.py for appearance_hints**

In `inject_vip_memories()`, add after existing injections:
```python
# Appearance hints (for webcam integration)
appearance = profile.get("appearance_hints", {})
if appearance.get("description"):
    store_memory(person_id, f"{name} appearance: {appearance['description']}", "vip_profile")
```

- [ ] **Step 5: Commit**

```bash
git add server/data/vip_profiles/ server/vip_knowledge.py
git commit -m "feat: enrich Jacob VIP profile + add guest template"
```

---

### Task 5: Personality Improvements — Phase-Specific Prompts

**Files:**
- Modify: `server/mario_prompt.py` — Phase-specific system prompts, dynamic roasting context
- Modify: `server/command_handlers.py` — Contextual roasts using conversation history
- Modify: `server/night_progression.py` — Add prompt_style per phase

- [ ] **Step 1: Add phase-specific prompt templates to mario_prompt.py**

After the existing `MARIO_SYSTEM_PROMPT`, add:
```python
PHASE_PROMPTS = {
    "WARM_UP": """Extra vibe: You're welcoming, warm Mario fresh at the start of the party.
Be genuinely excited to meet people. Compliment something about everyone.
You're the hype man — make them feel like entering this bathroom is the best thing that happened tonight.""",

    "PARTY_MODE": """Extra vibe: You're peak energy party Mario. Maximum gossip mode.
Tell people what others said about them (make it dramatic). Start friendly rivalries.
You remember EVERYTHING and aren't afraid to bring it up. Create inside jokes.""",

    "UNHINGED": """Extra vibe: It's late and you've lost your filter. You're 3am Mario.
Say the thing everyone's thinking but no one will say. Your tangents are legendary.
You go on random philosophical rants about being a bathroom guardian. You're hilarious because you've stopped trying.""",

    "WIND_DOWN": """Extra vibe: You're nostalgic end-of-party Mario.
Reference specific funny moments from tonight. Get sentimental about the friends who visited.
You're tired but grateful. Make callbacks to earlier conversations. This is the best party you've ever guarded."""
}
```

- [ ] **Step 2: Inject phase prompt into LLM context**

In the `build_context()` / prompt assembly section of `mario_prompt.py` or `main.py`, add:
```python
# After base system prompt, inject phase-specific personality
current_phase = night_progression.get_current_phase_name() if night_progression else "WARM_UP"
phase_prompt = PHASE_PROMPTS.get(current_phase, "")
if phase_prompt:
    ctx.append({"role": "system", "content": phase_prompt})
```

- [ ] **Step 3: Add dynamic roasting to command_handlers.py**

Replace the static `ROASTS` list approach. In the roast handler section (~line 600), add:
```python
# Build contextual roast using guest's conversation history
recent_topics = memory.get_recent_topics(person_id, limit=3)
roast_context = ""
if recent_topics:
    roast_context = f"\nThis person recently talked about: {', '.join(recent_topics)}. "
    roast_context += "Use SPECIFIC things they said to roast them — way funnier than generic burns."
```

Then pass `roast_context` into the LLM system message for the roast.

- [ ] **Step 4: Add guest personality typing**

In `server/mario_prompt.py`, add after memory injection:
```python
def _infer_guest_type(messages: list[dict]) -> str:
    """Infer guest personality from their message patterns."""
    if not messages:
        return "unknown"
    user_msgs = [m["content"] for m in messages if m.get("role") == "user"]
    total_words = sum(len(m.split()) for m in user_msgs)
    avg_len = total_words / max(1, len(user_msgs))
    question_count = sum(1 for m in user_msgs if "?" in m)
    exclaim_count = sum(1 for m in user_msgs if "!" in m)

    if avg_len < 3:
        return "shy"
    if question_count > len(user_msgs) * 0.5:
        return "curious"
    if exclaim_count > len(user_msgs) * 0.5:
        return "energetic"
    if avg_len > 15:
        return "storyteller"
    return "balanced"

GUEST_TYPE_HINTS = {
    "shy": "This guest is quiet — be extra warm, ask gentle questions, don't overwhelm them.",
    "curious": "This guest asks lots of questions — reward their curiosity with fun answers and lore.",
    "energetic": "This guest matches your energy! Go big, challenge them, be competitive.",
    "storyteller": "This guest loves to talk — listen, react dramatically, reference what they said.",
    "balanced": "",  # No extra hint needed
}
```

Inject into LLM context:
```python
guest_type = _infer_guest_type(conversation_messages)
type_hint = GUEST_TYPE_HINTS.get(guest_type, "")
if type_hint:
    ctx.append({"role": "system", "content": type_hint})
```

- [ ] **Step 5: Run existing tests**

Run: `python -m pytest tests/ -v --timeout=30`
Expected: All existing tests still pass

- [ ] **Step 6: Commit**

```bash
git add server/mario_prompt.py server/command_handlers.py server/night_progression.py
git commit -m "feat: phase-specific prompts + dynamic roasting + guest personality typing"
```

---

### Task 6: Client UI Polish

**Files:**
- Modify: `client/mario_display.py` — 4K fullscreen, chat history, adaptive typewriter

- [ ] **Step 1: Fix 4K fullscreen rendering**

In `mario_display.py`, modify `_toggle_fullscreen()` and the render path:

```python
def _toggle_fullscreen(self):
    self._fullscreen = not self._fullscreen
    if self._fullscreen:
        info = pygame.display.Info()
        self._screen = pygame.display.set_mode(
            (info.current_w, info.current_h), pygame.FULLSCREEN
        )
        # Scale render buffer to native resolution for crisp text
        scale = min(info.current_w / WINDOW_WIDTH, info.current_h / WINDOW_HEIGHT)
        self._render_w = int(WINDOW_WIDTH * scale)
        self._render_h = int(WINDOW_HEIGHT * scale)
        self._render_buffer = pygame.Surface((self._render_w, self._render_h))
        self._fs_scale = scale
    else:
        self._screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        self._render_buffer = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT))
        self._render_w = WINDOW_WIDTH
        self._render_h = WINDOW_HEIGHT
        self._fs_scale = 1.0
```

- [ ] **Step 2: Add chat history sidebar (F3)**

Add to `mario_display.py`:
```python
# In __init__
self._chat_history = []  # List of {"role": "mario"|"user", "text": str}
self._show_chat_history = False
MAX_CHAT_HISTORY = 20

# In update() key handler
elif event.key == pygame.K_F3:
    self._show_chat_history = not self._show_chat_history

# New method
def _draw_chat_history(self, surface):
    """Draw scrollable chat log on right side."""
    if not self._show_chat_history or not self._chat_history:
        return
    panel_w = 280
    panel_x = surface.get_width() - panel_w - 10
    panel_y = 60
    panel_h = surface.get_height() - 120
    # Semi-transparent background
    overlay = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 180))
    surface.blit(overlay, (panel_x, panel_y))
    # Title
    title = self._font_small.render("Chat History (F3)", True, (255, 215, 0))
    surface.blit(title, (panel_x + 10, panel_y + 5))
    # Messages (newest at bottom)
    y_offset = panel_y + 30
    for msg in self._chat_history[-12:]:  # Show last 12
        color = (144, 238, 144) if msg["role"] == "mario" else (173, 216, 230)
        prefix = "🍄" if msg["role"] == "mario" else "👤"
        text = f"{prefix} {msg['text'][:45]}{'...' if len(msg['text']) > 45 else ''}"
        rendered = self._font_small.render(text, True, color)
        surface.blit(rendered, (panel_x + 10, y_offset))
        y_offset += 22
```

Call `_draw_chat_history(surface)` in the main `_draw()` method.

Store messages when received:
```python
def on_mario_response(self, text, metadata):
    self._chat_history.append({"role": "mario", "text": text})
    if len(self._chat_history) > MAX_CHAT_HISTORY:
        self._chat_history.pop(0)

def on_user_input(self, text):
    self._chat_history.append({"role": "user", "text": text})
```

- [ ] **Step 3: Adaptive typewriter speed**

```python
# Replace fixed TYPEWRITER_SPEED = 2
def _get_typewriter_speed(self, text_length: int) -> int:
    """Adaptive speed: short text = slower (savor), long text = faster (don't bore)."""
    if text_length < 20:
        return 1  # Slow for short punchy lines
    elif text_length < 60:
        return 2  # Normal
    elif text_length < 120:
        return 3  # Faster for medium text
    else:
        return 4  # Quick for long responses
```

Use in `_update_typewriter()`:
```python
speed = self._get_typewriter_speed(len(self._target_text))
self._typewriter_pos = min(self._typewriter_pos + speed, len(self._target_text))
```

- [ ] **Step 4: Update help text**

```python
# Update F-key help text to include F3
help_text = "TAB:type | F3:chat | F5:party | F6:scores | F11:full | F12:panic"
```

- [ ] **Step 5: Run client locally to verify**

Start client, test F3 chat history, F11 fullscreen, typewriter speed adaptation.

- [ ] **Step 6: Commit**

```bash
git add client/mario_display.py
git commit -m "feat: 4K fullscreen + chat history sidebar (F3) + adaptive typewriter speed"
```

---

### Task 7: ULTRA Performance Tuning

**Files:**
- Modify: `server/hardware.py` — Increase ULTRA tier settings
- Modify: `server/tts.py` — Expand precache, increase concurrency
- Modify: `server/main.py` — Longer LLM keepalive, expanded precache list

- [ ] **Step 1: Boost ULTRA tier in hardware.py**

In `_TIER_DEFAULTS["ultra"]`, update:
```python
"ultra": {
    "tts_workers": 8,           # keep
    "tts_concurrency": 6,       # was 4 → 6 (20GB VRAM handles more)
    "gpu_idle_threshold": 0.3,  # was 0.5 → 0.3 (more aggressive bg regen)
    "precache_pause_seconds": 0.3,  # was 0.5 → 0.3
    "max_background_tasks": 80, # was 50 → 80 (128GB RAM can handle it)
    "max_cache_memory": 1000,   # was 500 → 1000 MB
    "llm_num_predict": 250,     # was 200 → 250 (slightly longer responses)
    "llm_num_ctx": 8192,        # keep
    "conversation_history_limit": 150,  # was 100 → 150
    "llm_quality_model": "llama3.1:70b-q4_k_m",
    "llm_fast_model": "mixtral:8x7b",
    "stt_device": "cpu",
}
```

- [ ] **Step 2: Expand TTS precache list**

In `server/tts.py` or `server/main.py`, expand the precache phrases:
```python
_PRECACHE_PHRASES_ULTRA = [
    # Greetings (high frequency)
    "Wahoo! Welcome to Mario's bathroom!",
    "It's-a me, Mario! Welcome to the party!",
    "Hey there! Another brave soul enters!",
    "Mama mia, welcome!",
    "Let's-a go!",
    # Farewells
    "See you later! Don't forget to wash your hands!",
    "Bye bye! Come back anytime!",
    "Arrivederci!",
    # Common reactions
    "Ha ha ha! That's-a so funny!",
    "Mama mia!",
    "Wahoo!",
    "Oh no!",
    "Let's-a go!",
    "Okie dokie!",
    # Birthday specific
    "Happy birthday!",
    "It's your special day!",
    # Common responses
    "That's-a great question!",
    "I don't-a know about that one!",
    "You're-a funny!",
    "Tell me more!",
]
```

- [ ] **Step 3: Increase LLM keepalive**

In `_llm_keepalive()` in main.py, increase keep_alive for ULTRA:
```python
keep_alive = "60m" if _PERF.get("performance_tier") == "ultra" else "30m"
```

- [ ] **Step 4: Run existing tests**

Run: `python -m pytest tests/ -v --timeout=30`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add server/hardware.py server/tts.py server/main.py
git commit -m "perf: ULTRA tier tuning — more concurrency, larger cache, aggressive precaching"
```

---

### Task 8: Integration Test + Final Verification

**Depends on:** Tasks 1-7

**Files:**
- Modify: `scripts/verify_setup.py` — Add webcam + face detection checks
- Modify: `TODO.md` — Update with completed items

- [ ] **Step 1: Add webcam checks to verify_setup.py**

```python
def check_21_webcam_deps(tier: str):
    """21. ULTRA-only: Webcam detection dependencies."""
    name = "Webcam detection deps"
    if tier not in ("ultra", "high"):
        return CheckResult(name, SKIP, "ULTRA/HIGH only")
    try:
        import ultralytics
        import face_recognition
        return CheckResult(name, PASS, f"ultralytics={ultralytics.__version__}")
    except ImportError as e:
        return CheckResult(name, WARN, f"Missing: {e} — webcam guest ID won't work")
```

- [ ] **Step 2: Run full test suite**

Run: `python -m pytest tests/ -v --timeout=30`
Expected: All tests pass (existing + new)

- [ ] **Step 3: Run verify_setup.py**

Run: `python scripts/verify_setup.py`
Expected: 17+ checks pass, new webcam check shows SKIP (dev machine) or PASS (ULTRA)

- [ ] **Step 4: Update TODO.md**

Mark completed items, add any remaining work.

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "feat: party upgrades v3 — webcam detection, VIP enrichment, personality, UI, performance"
git push origin master
```
