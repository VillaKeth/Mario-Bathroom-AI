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
    # Fix wave 2 (task-8-report.md "## Fix wave 2"): swept for the first time --
    # Task 8 shipped this at its Task 4/W4 value with "not swept in this task."
    # voice_margin_sweep measures three outcomes (not recall alone) per
    # (margin, SNR) cell against noise-mixed speech, with every lab person
    # enrolled so a "wrong" result means one enrolled guest mistaken for
    # another -- the exact wrong-name-greeting failure this margin exists to
    # prevent. Measured: margin 0.00 misnames 2/18 probes at 10dB and 1/18 at
    # 5dB; 0.02 misnames 1/18 at 10dB and 1/18 at 5dB; 0.04 misnames 1/18 at
    # 5dB; 0.06 and above misname 0/18 at every SNR tested. 0.06 is therefore
    # the lowest margin with zero measured wrong-name greetings -- CONFIRMED by
    # a real sweep, not left unchanged for lack of one. See results.json's
    # voice_margin_sweep / tuned_thresholds.voice_match_margin.
    "voice_match_margin": 0.06,       # best vs runner-up cosine gap (Fix wave 2: confirmed via sweep)
    # NOTE: the face quality SUB-thresholds (box px, laplacian sharpness) are NOT here.
    # They are scored inside the client process (client/person_detector.py), which is
    # separate from the server and cannot read this config. They live as client env
    # vars FACE_MIN_BOX_PX / FACE_MIN_SHARPNESS. Only the combined FLOOR the server
    # gates enrollment against belongs here — advertising the sub-thresholds as server
    # config was dead config that silently drifted from the client's actual scale.
    "face_min_quality": 0.5,          # combined score required to ENROLL (server-side gate)
    # Fix wave 1 (task-8-report.md "## Fix wave 1"): reverses W8's disable. W8's
    # own sweep (measured with voice_max_flatness still at W8's 0.55) found, at
    # tau=0.60, single_kept=1.0 (zero false-rejects on genuine solo speech) and
    # double_rejected=0.17 (real, if modest, two-speaker protection). Re-measured
    # under Fix wave 1's own voice_max_flatness=1.0, double_rejected reads 0.0
    # instead (some two-speaker mixes W8's flatness sub-check happened to catch
    # incidentally are no longer caught that way) — see results.json's own
    # stage_b_sweep/tuned_thresholds for whichever figure is current. Either way
    # single_kept stays 1.0, so tau=0.60 remains harmless and strictly better
    # than 0.0, which discarded Task 7's whole mechanism for no accuracy gain.
    # No tau reached W8's >=80% double_rejected target because the lab's
    # two-speaker fixture (mix_two_speakers) overlaps both speakers CONTINUOUSLY
    # across the whole chunk, so both halves look alike to Stage B's half-vs-half
    # agreement check by construction — Stage B is designed to catch a chunk
    # that CHANGES character partway through (a handoff or interruption), which
    # this fixture never produces. That is a fixture gap, not a Stage B defect —
    # see results.json:known_limitations.double_speaker_mix_may_not_exercise_stage_b.
    # Follow-up: a mid-chunk speaker-change fixture to actually test the 0.80
    # target. (Also, incidentally, back to the pre-W8 default.)
    "voice_consistency_tau": 0.60,    # sub-window agreement floor
    # Fix wave 1 (task-8-report.md "## Fix wave 1"): W8's 0.55 kept 100% of
    # CLEAN speech, but its sweep never tested noise-MIXED speech — the actual
    # party operating condition. Measured there (extended stage_a_flatness_sweep,
    # results.json), 0.55 discarded a real fraction of genuine noisy voice
    # chunks, regressing voice_only.multi to 61/39/17% at 10/5/0dB (baseline
    # 83/67/44%). An extended sweep found NO ceiling in [0.45, 0.80] keeps
    # noise-mixed speech at every tested SNR (10/5/0dB) while also rejecting
    # pure party noise — spectral flatness does not separate "speech + party
    # noise" from "party noise" on this corpus. This is a deliberate disable of
    # the flatness sub-check, backed by that measured negative result, not an
    # untuned guess: 1.0 is the top of flatness's bounded [0, 1] range, so the
    # check always passes. Stage A's energy test (2-of-3 windows >=
    # MIN_SPEECH_RMS) is untouched and still rejects silence/mostly-empty
    # chunks. Re-enable by lowering this once a better feature (e.g. a
    # Welch-averaged periodogram, or flatness computed only on the
    # highest-energy window) is measured to actually separate the two.
    "voice_max_flatness": 1.0,        # spectral flatness ceiling — DISABLED, see above
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
