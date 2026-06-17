"""Face-resolution logic for the person_detected pipeline.

Extracted from main.py so it can be unit-tested with an injected face store.
`face_memory` is duck-typed: it must provide
    find_match(encoding) -> dict | None     # dict has "name", "person_id", "visit_count"
    learn_guest(name, encoding) -> None      # name-keyed enrollment

See AUDIT_VOICE_FACE_RECOGNITION.md (F1, F2, F4).
"""
from typing import Optional

import numpy as np

ENCODING_DIM = 128


def _valid_encoding(enc) -> Optional[np.ndarray]:
    """Return a clean 128-dim float64 array, or None if the input is unusable."""
    if not isinstance(enc, (list, tuple, np.ndarray)) or len(enc) != ENCODING_DIM:
        return None
    arr = np.asarray(enc, dtype=np.float64)
    if np.any(np.isnan(arr)) or np.any(np.isinf(arr)):
        return None
    return arr


def resolve_faces(faces: list, face_memory, speaker_name: Optional[str]) -> dict:
    """Match/enroll a batch of detected faces.

    For each face:
      - known face        -> add {name, person_id, visit_count} to `detected`
      - unknown + speaker  -> enroll the face to the current speaker (learn_guest)
      - unknown + nobody   -> count as new and stash the encoding for later naming

    Returns: {"detected": list[dict], "new_face_count": int, "pending_encoding": np.ndarray | None}
    """
    detected = []
    new_face_count = 0
    pending_encoding = None

    for face_data in faces or []:
        if not isinstance(face_data, dict):
            continue
        enc = _valid_encoding(face_data.get("encoding"))
        if enc is None:
            continue

        match = face_memory.find_match(enc) if face_memory is not None else None
        if match and match.get("name"):
            detected.append({
                "name": match["name"],
                "person_id": match.get("person_id"),
                "visit_count": match.get("visit_count"),
            })
        elif speaker_name:
            # Unknown face, but we know who is speaking -> link face to that guest.
            if face_memory is not None:
                face_memory.learn_guest(speaker_name, enc)
            detected.append({"name": speaker_name, "person_id": None, "visit_count": None})
        else:
            # Unknown face, nobody identified yet -> remember it until a name arrives.
            new_face_count += 1
            pending_encoding = enc

    return {
        "detected": detected,
        "new_face_count": new_face_count,
        "pending_encoding": pending_encoding,
    }


def link_pending_face(face_memory, name: str, pending_encoding) -> bool:
    """Enroll a previously-stashed unknown face to `name`. Returns True if enrolled."""
    if face_memory is None or not name or pending_encoding is None:
        return False
    enc = _valid_encoding(pending_encoding)
    if enc is None:
        return False
    face_memory.learn_guest(name, enc)
    return True
