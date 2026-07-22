"""Face-resolution logic for the person_detected pipeline.

Extracted from main.py so it can be unit-tested with an injected face store.
`face_memory` is duck-typed: it must provide
    find_match(encoding) -> dict | None                # dict has "name", "person_id", "visit_count"
    learn_guest(name, encoding, quality=0.0) -> int     # name-keyed enrollment

See AUDIT_VOICE_FACE_RECOGNITION.md (F1, F2, F4).
See docs/superpowers/specs/2026-07-22-recognition-reliability-design.md (W3) for the
enrollment quality gate: a face's `quality` score is scored client-side and never
rejects a match, only an enrollment below `recognition_config.get("face_min_quality")`.
"""
from typing import Optional

import numpy as np

# Sibling import: this repo loads server/ modules as both bare top-level copies
# and server.* package copies (independent module instances). recognition_config
# holds a module-global cache, so every module in a process must resolve the
# SAME instance of it. Mirrors server/face_memory.py and server/speaker_id.py.
if __package__:
    from server import recognition_config
else:
    import recognition_config

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

    Known faces are always reported. Enrollment is FAIL-CLOSED: it happens only when
    the batch contains exactly ONE unknown face. With two or more unknowns we cannot
    tell which face belongs to the name we are about to hear, and a wrong binding is
    permanent and silent — so we enroll nothing and report `ambiguous`.

    W3 quality gate: a single unknown face below `face_min_quality` is never enrolled
    or stashed as pending — it is too blurry/small/off-angle to trust as a stored
    reference — but it still counts toward `new_face_count` so greeting logic is
    unaffected. A missing `quality` key defaults to 1.0 (fully enrollable) so an
    older client, which never sends the key, keeps enrolling exactly as before.

    Returns: {"detected", "new_face_count", "pending_encoding", "ambiguous"}
    """
    detected = []
    unknown = []

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
                "confidence": match.get("confidence"),
            })
        else:
            unknown.append((enc, float(face_data.get("quality", 1.0))))

    ambiguous = len(unknown) > 1
    pending_encoding = None
    new_face_count = 0

    if len(unknown) == 1:
        enc, quality = unknown[0]
        min_quality = recognition_config.get("face_min_quality")
        if quality < min_quality:
            # Too blurry / small / off-angle to become someone's stored reference.
            # Still counted as new so the greeting logic is unaffected.
            new_face_count = 1
        elif speaker_name:
            # Exactly one unknown face and we know who is talking -> safe to bind.
            if face_memory is not None:
                face_memory.learn_guest(speaker_name, enc, quality)
            detected.append({"name": speaker_name, "person_id": None,
                             "visit_count": None, "confidence": None})
            # Face was enrolled, so it is not "new" anymore.
            new_face_count = 0
        else:
            # Nobody identified yet -> remember it until a name arrives.
            pending_encoding = enc
            new_face_count = 1
    else:
        # Multiple unknowns (or none): count them as new, unenrolled faces.
        new_face_count = len(unknown)

    return {
        "detected": detected,
        "new_face_count": new_face_count,
        "pending_encoding": pending_encoding,
        "ambiguous": ambiguous,
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
