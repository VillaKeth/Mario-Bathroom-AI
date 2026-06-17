"""SNR-aware identity fusion.

Combine a voice match and a face match into one identity decision, biased toward
the FACE — a returned face match already cleared dlib's calibrated euclidean
threshold, so it is the signal that survives a loud party. A voice-only decision
must clear a confidence floor that RISES with the estimated party noise, so a shaky
voiceprint in a noisy room does not produce a false greeting.

Empirically (tests/recognition_lab) voice ID falls from ~100% clean to ~33% at 5 dB
SNR while face holds up, so "trust the face, gate the voice by noise" is the right
policy. See AUDIT_VOICE_FACE_RECOGNITION.md (F5).
"""

# Clean-room floor matches speaker_id.SIMILARITY_THRESHOLD; the noisy floor is what
# we demand of a voice-only decision when the room is very loud.
VOICE_FLOOR_CLEAN = 0.65
VOICE_FLOOR_NOISY = 0.85
# A face dict is only produced when find_match cleared the 0.6 tolerance, so any
# returned face match is already trustworthy; this is an extra optional gate.
FACE_MIN_CONFIDENCE = 0.0


def voice_confidence_floor(noise_level: float) -> float:
    """Minimum voice confidence to accept, scaled by noise_level in [0, 1]
    (0 = silent room, 1 = very loud party)."""
    n = max(0.0, min(1.0, noise_level))
    return VOICE_FLOOR_CLEAN + (VOICE_FLOOR_NOISY - VOICE_FLOOR_CLEAN) * n


def fuse_identity(voice=None, face=None, noise_level=0.0) -> dict:
    """Fuse a voice + face match into one identity.

    Args:
        voice: {"name", "confidence", "is_new"} from speaker_id.identify_speaker, or None
        face:  {"name", "confidence"} from face_memory.find_match, or None
               (present == matched within the face tolerance)
        noise_level: estimated party noise in [0, 1]; raises the voice floor.

    Returns: {"name", "source", "confidence", "reason"} — name is None if unknown.
    """
    # Face wins whenever it matched — the noise-robust signal.
    if face and face.get("name") and face.get("confidence", 0.0) >= FACE_MIN_CONFIDENCE:
        return {"name": face["name"], "source": "face",
                "confidence": float(face.get("confidence", 0.0)),
                "reason": "face match (robust to party noise)"}

    # Otherwise rely on voice, but only above the noise-scaled confidence floor.
    if voice and voice.get("name") and not voice.get("is_new", False):
        floor = voice_confidence_floor(noise_level)
        conf = float(voice.get("confidence", 0.0))
        if conf >= floor:
            return {"name": voice["name"], "source": "voice", "confidence": conf,
                    "reason": f"voice match >= noise floor {floor:.2f}"}
        return {"name": None, "source": None, "confidence": conf,
                "reason": f"voice {conf:.2f} below noise floor {floor:.2f}"}

    return {"name": None, "source": None, "confidence": 0.0, "reason": "no usable signal"}
