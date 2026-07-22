"""Central tunables for face + voice recognition.

Every threshold used by face_memory, speaker_id, person_detector and
face_enrollment is read from here so the party box can be tuned without a code
change. Code defaults stand alone: a missing config.json, or a missing key inside
it, reproduces the shipped behavior exactly.

See docs/superpowers/specs/2026-07-22-recognition-reliability-design.md (W7).
"""
import json
import logging
import os

logger = logging.getLogger(__name__)

DEFAULTS = {
    "face_match_tolerance": 0.6,      # dlib euclidean, calibrated
    "face_match_margin": 0.05,        # best vs runner-up distance gap (W8: confirmed the knee)
    "voice_match_margin": 0.06,       # best vs runner-up cosine gap
    "face_min_box_px": 80,            # shorter side of the face box
    "face_min_sharpness": 40.0,       # laplacian variance floor
    "face_min_quality": 0.5,          # combined score required to ENROLL
    # W8 (tests/recognition_lab/results.json): no tau rejected >=80% of the lab's
    # two-speaker mixes while keeping >=95% single-speaker acceptance, so Stage B
    # is disabled (0.0 accepts everything) pending a redesign — see
    # results.json:tuned_thresholds.voice_consistency_tau for the measured curve
    # and an important caveat about the mix construction used to test it.
    "voice_consistency_tau": 0.0,     # sub-window agreement floor
    # W8 (tests/recognition_lab/results.json): the shipped 0.45 false-rejected
    # ~28% of genuine solo speech (Task 7) and no ceiling in the swept range
    # (0.45-0.80) separated real speech from real party-noise beds on flatness
    # alone, so this is the documented fallback: lowest ceiling keeping 100% of
    # the measured real-speech probes, energy test (Stage A's other half) unaffected.
    "voice_max_flatness": 0.55,       # spectral flatness ceiling (noise reject)
    "gallery_max_per_person": 5,      # encodings retained per identity
}

_CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")
_cache = None


def _load() -> dict:
    global _cache
    if _cache is not None:
        return _cache
    values = dict(DEFAULTS)
    try:
        with open(_CONFIG_PATH, encoding="utf-8") as f:
            server_cfg = json.load(f).get("server", {})
        for key in DEFAULTS:
            if key in server_cfg:
                values[key] = server_cfg[key]
    except FileNotFoundError:
        pass
    except Exception as e:
        logger.warning(f"[recognition_config] config read failed, using defaults: {e}")
    _cache = values
    return _cache


def get(name: str):
    """Return a recognition tunable (config.json server.<name>, else code default).

    Raises KeyError for an unknown tunable — a typo should fail loudly, not
    silently return None and disable a gate.
    """
    values = _load()
    if name not in values:
        raise KeyError(f"unknown recognition tunable: {name}")
    return values[name]


def override(name: str, value):
    """Force a tunable to `value` for the current process (tuning sweeps, tests).

    Raises KeyError for an unknown tunable, same as get().
    """
    values = _load()
    if name not in values:
        raise KeyError(f"unknown recognition tunable: {name}")
    values[name] = value


def reset_cache():
    """Drop the cached values (tests, config hot-reload)."""
    global _cache
    _cache = None


def clear_overrides():
    """Drop all overrides and re-read from config on next access."""
    reset_cache()
