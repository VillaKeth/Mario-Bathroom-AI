"""Face-resolution logic for the person_detected pipeline.

Extracted from main.py so it can be unit-tested with an injected face store.
`face_memory` is duck-typed: it must provide
    find_match(encoding) -> dict | None                # dict has "name", "person_id", "visit_count"
    learn_guest(name, encoding, quality=0.0) -> int     # name-keyed enrollment
and SHOULD provide
    find_match_detail(encoding) -> {"match": dict | None, "ambiguous": bool}
which is what lets this module tell "stranger" apart from "two people are equally
close". A store without it degrades to find_match, i.e. it can never report
ambiguity, so only fakes/labs that never enroll should rely on that fallback.

See AUDIT_VOICE_FACE_RECOGNITION.md (F1, F2, F4).
See docs/superpowers/specs/2026-07-22-recognition-reliability-design.md (W3) for the
enrollment quality gate: a face's `quality` score is scored client-side and never
rejects a match, only an enrollment below `recognition_config.get("face_min_quality")`.
"""
import logging
import time
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

logger = logging.getLogger(__name__)

ENCODING_DIM = 128

# How long a stashed-but-unnamed face stays linkable. The stash exists to bridge
# "camera sees a new guest" -> "that guest says their name" inside ONE doorway
# visit. Past this, the guest it belongs to has very likely left, and binding it
# to whoever is speaking now is a wrong-name binding that lasts all night.
PENDING_FACE_TTL_SECONDS = 60.0


def _valid_encoding(enc) -> Optional[np.ndarray]:
    """Return a clean 128-dim float64 array, or None if the input is unusable."""
    if not isinstance(enc, (list, tuple, np.ndarray)) or len(enc) != ENCODING_DIM:
        return None
    arr = np.asarray(enc, dtype=np.float64)
    if np.any(np.isnan(arr)) or np.any(np.isinf(arr)):
        return None
    return arr


def _match_face(face_memory, enc):
    """Return `(match_dict_or_None, is_ambiguous)` for one encoding.

    Prefers `find_match_detail` so a margin-rejected face is distinguishable from a
    genuine stranger. Falls back to `find_match` for duck-typed stores that predate
    it, which can only ever report "no match" — safe for read-only use.
    """
    if face_memory is None:
        return None, False
    detail_fn = getattr(face_memory, "find_match_detail", None)
    if callable(detail_fn):
        detail = detail_fn(enc) or {}
        return detail.get("match"), bool(detail.get("ambiguous"))
    return face_memory.find_match(enc), False


def resolve_faces(faces: list, face_memory, speaker_name: Optional[str]) -> dict:
    """Match/enroll a batch of detected faces.

    Known faces are always reported. Enrollment is FAIL-CLOSED — it happens only when
    every one of these holds:

    1. Exactly ONE face in the batch is unknown. With two or more we cannot tell which
       face belongs to the name we are about to hear.
    2. NO face in the batch was ambiguous (the W4 margin fired). An ambiguous face is
       somebody the gallery already knows, we just cannot say who — binding it, or
       binding *around* it, writes one guest's encoding into another guest's gallery.
       Such a face is neither enrolled nor stashed; it only counts as a new face.
    3. The speaker is NOT already among the matched faces. If Alice is talking and
       Alice's own face is matched in this frame, then the unknown face is somebody
       else's — the "known guest walks in with a stranger" doorway case that main.py
       greets with "And who's your friend?". Enrolling there names the stranger Alice;
       stashing there is just as bad, because main.py links the stash to the CURRENT
       speaker on the next turn, who is still Alice.
    4. Its `quality` clears `face_min_quality` (W3) — too blurry/small/off-angle to
       become anyone's stored reference. A missing `quality` key defaults to 1.0 so an
       older client, which never sends the key, keeps enrolling exactly as before.

    A wrong binding is permanent, silent, and produces CONFIDENT wrong-name greetings
    for the rest of the night; a refused enrollment costs one greeting. Refuse.

    `new_face_count` is preserved for main.py's group greeting and recognition_events:
    0 when the single unknown face was enrolled, 1 when it was stashed or refused, and
    the count of unresolved faces otherwise.

    Returns:
        {"detected", "new_face_count", "pending_encoding", "ambiguous", "quality_rejected"}
    """
    detected = []
    unknown = []
    ambiguous_count = 0

    for face_data in faces or []:
        if not isinstance(face_data, dict):
            continue
        enc = _valid_encoding(face_data.get("encoding"))
        if enc is None:
            continue

        match, is_ambiguous = _match_face(face_memory, enc)
        if match and match.get("name"):
            detected.append({
                "name": match["name"],
                "person_id": match.get("person_id"),
                "visit_count": match.get("visit_count"),
                "confidence": match.get("confidence"),
            })
        elif is_ambiguous:
            # Known to the gallery, but we cannot say who. Never a write target.
            ambiguous_count += 1
        else:
            unknown.append((enc, float(face_data.get("quality", 1.0))))

    detected_names = {d["name"] for d in detected}
    ambiguous = ambiguous_count > 0 or len(unknown) > 1
    pending_encoding = None
    quality_rejected = False
    new_face_count = len(unknown) + ambiguous_count

    if ambiguous:
        if ambiguous_count:
            logger.info(f"[FACE_ENROLL] {ambiguous_count} face(s) matched ambiguously "
                        f"and {len(unknown)} unknown — enrollment refused (fail-closed)")
    elif len(unknown) == 1:
        enc, quality = unknown[0]
        min_quality = recognition_config.get("face_min_quality")
        if quality < min_quality:
            # Too blurry / small / off-angle to become someone's stored reference.
            # Still counted as new so the greeting logic is unaffected.
            quality_rejected = True
            new_face_count = 1
            logger.info(f"[FACE_ENROLL] enrollment refused: face quality {quality:.2f} "
                        f"below floor {min_quality:.2f} (face_min_quality) — "
                        f"not enrolled, not stashed")
        elif speaker_name and speaker_name in detected_names:
            # The speaker's own face is already accounted for in this frame, so this
            # unknown face belongs to somebody else. Neither enroll nor stash.
            new_face_count = 1
            logger.info(f"[FACE_ENROLL] enrollment refused: speaker '{speaker_name}' "
                        f"already matched in this frame, so the unknown face is "
                        f"someone else's (fail-closed)")
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

    return {
        "detected": detected,
        "new_face_count": new_face_count,
        "pending_encoding": pending_encoding,
        "ambiguous": ambiguous,
        "quality_rejected": quality_rejected,
    }


def link_pending_face(face_memory, name: str, pending_encoding,
                      stashed_at: Optional[float] = None,
                      now: Optional[float] = None,
                      ttl_seconds: Optional[float] = None) -> bool:
    """Enroll a previously-stashed unknown face to `name`. Returns True if enrolled.

    `stashed_at` is the `time.time()` at which the encoding was stashed. A stash older
    than `ttl_seconds` (default `PENDING_FACE_TTL_SECONDS`) is REFUSED: guest A can be
    stashed at the door and leave without speaking, then guest B arrives with every
    frame motion-blurred so nothing new is stashed, and B saying "my name is Bob"
    would otherwise bind guest A's FACE to Bob. `stashed_at=None` means the caller
    kept no timestamp and skips the check — server/main.py always passes one.
    """
    if face_memory is None or not name or pending_encoding is None:
        return False
    if stashed_at is not None:
        ttl = PENDING_FACE_TTL_SECONDS if ttl_seconds is None else ttl_seconds
        age = (time.time() if now is None else now) - float(stashed_at)
        if age > ttl:
            logger.info(f"[FACE_ENROLL] stashed face is {age:.0f}s old (TTL {ttl:.0f}s) — "
                        f"refusing to bind it to '{name}' (fail-closed)")
            return False
    enc = _valid_encoding(pending_encoding)
    if enc is None:
        return False
    face_memory.learn_guest(name, enc)
    return True
