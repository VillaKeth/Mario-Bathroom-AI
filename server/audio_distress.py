"""
Audio distress detector — dual approach: PANNs + Spectral Analysis.
Detects vomiting/retching/gagging sounds from raw audio bytes.

PANNs: Uses Cnn14 model (AudioSet 527 classes) for class-based detection.
Spectral: Analyzes energy bursts, spectral flatness, and bandwidth
          to catch vomiting sounds that PANNs misclassifies.

Enhanced with:
- Volume spike detection (RMS >3x baseline in <0.5s)
- Temporal coherence (2+ distress frames within 5s window)
- Confidence scoring (0.0-1.0) combining spectral + volume + temporal
- False-trigger suppression for music, laughter, clinking glasses
"""

import logging
import numpy as np
import time
from collections import deque

logger = logging.getLogger("audio_distress")

DEBUG_DISTRESS = True

# AudioSet class indices relevant to vomiting/distress
# These fire in combination when someone is actually sick
_DISTRESS_CLASSES = {
    38: ("Groan", 0.15),
    39: ("Grunt", 0.15),
    44: ("Gasp", 0.15),
    47: ("Cough", 0.20),
    48: ("Throat clearing", 0.20),
    56: ("Gargling", 0.10),     # lower threshold — very indicative
    57: ("Stomach rumble", 0.10),
    58: ("Burping, eructation", 0.15),
    25: ("Wail, moan", 0.15),
    42: ("Wheeze", 0.20),
    45: ("Pant", 0.20),
}

# If the combined score of distress classes exceeds this, flag as distress
_COMBINED_THRESHOLD = 0.35

# Classes that indicate normal conversation (suppress false positives)
_SPEECH_CLASSES = {0, 1, 2, 3, 4}  # Speech, Child speech, Conversation, etc.

# AudioSet classes that cause false triggers — music, laughter, glass sounds
_FALSE_TRIGGER_CLASSES = {
    132: "Music",
    137: "Singing",
    17:  "Laughter",
    18:  "Baby laughter",
    441: "Glass",
    395: "Clinking",
}
_FALSE_TRIGGER_THRESHOLD = 0.30  # If any of these score above this, suppress

_model = None
_labels = None


class DistressTracker:
    """
    Stateful tracker providing volume-spike detection and temporal coherence.

    - Maintains a rolling RMS baseline (exponential moving average).
    - Flags volume spikes when RMS jumps >3× baseline within a single frame.
    - Requires 2+ distress frames within a 5-second window before confirming.
    - Produces a combined confidence score (0.0–1.0).
    - Resets after the coherence window expires with no new events.
    """

    SPIKE_MULTIPLIER = 3.0       # RMS must exceed baseline × this
    COHERENCE_WINDOW = 5.0       # seconds
    MIN_FRAMES_FOR_TRIGGER = 2   # distress frames required in window
    BASELINE_ALPHA = 0.05        # EMA smoothing for RMS baseline

    def __init__(self):
        self._rms_baseline: float = 0.0
        self._baseline_initialized: bool = False
        self._distress_events: deque = deque()  # list of (timestamp, confidence)
        self._last_reset: float = time.time()
        if DEBUG_DISTRESS:
            logger.debug("[DEBUG_DISTRESS] DistressTracker: __init__")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update(self, frame_result: dict, audio_bytes: bytes,
               sample_rate: int = 16000) -> dict:
        """
        Feed a single-frame detection result and raw audio into the tracker.

        Returns an enriched dict with:
            - confirmed_distress: bool  (temporal-coherence gated)
            - combined_confidence: float (0.0–1.0)
            - volume_spike: bool
            - distress_frame_count: int (events in current window)
            - (plus everything from the original frame_result)
        """
        now = time.time()
        if DEBUG_DISTRESS:
            logger.debug("[DEBUG_DISTRESS] DistressTracker.update: START, "
                         f"frame is_distress={frame_result.get('is_distress')}")

        # --- Volume spike detection ---
        rms = self._compute_rms(audio_bytes)
        volume_spike = self._check_volume_spike(rms)
        if DEBUG_DISTRESS:
            logger.debug(f"[DEBUG_DISTRESS] DistressTracker.update: rms={rms:.5f}, "
                         f"baseline={self._rms_baseline:.5f}, spike={volume_spike}")

        # --- False-trigger suppression ---
        suppressed = self._check_false_triggers(frame_result)
        if suppressed and DEBUG_DISTRESS:
            logger.debug("[DEBUG_DISTRESS] DistressTracker.update: "
                         f"suppressed by false-trigger class: {suppressed}")

        # --- Decide if this frame counts as distress ---
        frame_is_distress = (
            (frame_result.get("is_distress", False) or volume_spike)
            and not suppressed
        )

        frame_confidence = frame_result.get("confidence", 0.0)
        if volume_spike and not suppressed:
            spike_conf = min(rms / (self._rms_baseline * self.SPIKE_MULTIPLIER + 1e-8), 1.0)
            frame_confidence = max(frame_confidence, spike_conf * 0.6)

        # --- Record event ---
        if frame_is_distress:
            self._distress_events.append((now, frame_confidence))
            if DEBUG_DISTRESS:
                logger.debug("[DEBUG_DISTRESS] DistressTracker.update: "
                             f"recorded distress event, confidence={frame_confidence:.3f}")

        # --- Prune old events ---
        self._prune_events(now)

        # --- Temporal coherence ---
        frame_count = len(self._distress_events)
        confirmed = frame_count >= self.MIN_FRAMES_FOR_TRIGGER

        # --- Combined confidence ---
        combined_confidence = self._compute_combined_confidence(
            frame_confidence, volume_spike, frame_count
        )

        if DEBUG_DISTRESS:
            logger.debug(f"[DEBUG_DISTRESS] DistressTracker.update: END, "
                         f"confirmed={confirmed}, combined_conf={combined_confidence:.3f}, "
                         f"events_in_window={frame_count}")

        return {
            **frame_result,
            "confirmed_distress": confirmed,
            "combined_confidence": combined_confidence,
            "volume_spike": volume_spike,
            "distress_frame_count": frame_count,
            "suppressed_by": suppressed or None,
        }

    def reset(self):
        """Clear distress event history (e.g. after comfort response sent)."""
        self._distress_events.clear()
        self._last_reset = time.time()
        if DEBUG_DISTRESS:
            logger.debug("[DEBUG_DISTRESS] DistressTracker.reset")

    @property
    def distress_frame_count(self) -> int:
        self._prune_events(time.time())
        return len(self._distress_events)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _compute_rms(self, audio_bytes: bytes) -> float:
        """Compute RMS energy from raw int16 PCM bytes."""
        audio = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        if len(audio) == 0:
            return 0.0
        return float(np.sqrt(np.mean(audio ** 2)))

    def _check_volume_spike(self, rms: float) -> bool:
        """Update EMA baseline and check for a >3× spike."""
        if not self._baseline_initialized:
            self._rms_baseline = rms
            self._baseline_initialized = True
            return False

        spike = rms > (self._rms_baseline * self.SPIKE_MULTIPLIER) and self._rms_baseline > 0.001
        # Update baseline with EMA (only when not spiking, to keep baseline stable)
        if not spike:
            self._rms_baseline = (
                self.BASELINE_ALPHA * rms
                + (1 - self.BASELINE_ALPHA) * self._rms_baseline
            )
        return spike

    def _check_false_triggers(self, frame_result: dict) -> str | None:
        """Return the name of a false-trigger class if it dominates, else None."""
        top_classes = frame_result.get("top_classes", [])
        for class_name, score in top_classes:
            clean = class_name.strip("'\"")
            for _, ft_name in _FALSE_TRIGGER_CLASSES.items():
                if ft_name.lower() in clean.lower() and score >= _FALSE_TRIGGER_THRESHOLD:
                    return clean
        return None

    def _prune_events(self, now: float):
        """Remove events older than the coherence window."""
        cutoff = now - self.COHERENCE_WINDOW
        while self._distress_events and self._distress_events[0][0] < cutoff:
            self._distress_events.popleft()

    def _compute_combined_confidence(self, frame_conf: float,
                                     volume_spike: bool,
                                     frame_count: int) -> float:
        """
        Combine spectral/PANNs confidence + volume spike + temporal coherence
        into a single 0.0–1.0 score.
        """
        # Spectral/PANNs component (max 0.5)
        spectral_component = min(frame_conf, 1.0) * 0.5

        # Volume spike component (0.2 bonus)
        spike_component = 0.2 if volume_spike else 0.0

        # Temporal coherence component — scales from 0 to 0.3
        temporal_component = min(frame_count / 4.0, 1.0) * 0.3

        combined = spectral_component + spike_component + temporal_component
        return min(combined, 1.0)


def init_detector(device: str = "cpu"):
    """Load the PANNs Cnn14 model for audio classification."""
    global _model, _labels
    if _model is not None:
        return

    t0 = time.time()
    if DEBUG_DISTRESS:
        logger.info("[DEBUG_DISTRESS] init_detector: START")

    try:
        from panns_inference import AudioTagging
        from panns_inference.config import labels as panns_labels

        _model = AudioTagging(checkpoint_path=None, device=device)
        _labels = panns_labels
        if DEBUG_DISTRESS:
            logger.info(f"[DEBUG_DISTRESS] init_detector: loaded in {time.time()-t0:.1f}s, "
                        f"{len(_labels)} classes, device={device}")
    except Exception as e:
        logger.error(f"[DEBUG_DISTRESS] init_detector FAILED: {e}")
        _model = None


def detect_distress(audio_bytes: bytes, sample_rate: int = 16000) -> dict:
    """
    Analyze raw audio bytes for vomiting/distress sounds.
    
    Returns dict with:
        - is_distress: bool — whether distress was detected
        - confidence: float — combined distress score (0-1)
        - top_classes: list of (class_name, score) tuples
        - details: str — human-readable explanation
    """
    if _model is None:
        return {"is_distress": False, "confidence": 0.0, "top_classes": [], "details": "Model not loaded"}

    t0 = time.time()

    try:
        # Convert bytes to numpy float32 array
        audio_np = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0

        if len(audio_np) < 1600:  # Less than 0.1s at 16kHz
            return {"is_distress": False, "confidence": 0.0, "top_classes": [], "details": "Audio too short"}

        # Save original for spectral analysis (before PANNs resampling)
        audio_np_original = audio_np.copy()

        # PANNs expects 32kHz, resample if needed
        if sample_rate != 32000:
            import librosa
            audio_np = librosa.resample(audio_np, orig_sr=sample_rate, target_sr=32000)

        # Add batch dimension
        audio_input = audio_np[None, :]

        # Run inference
        clipwise_output, _ = _model.inference(audio_input)
        probs = clipwise_output[0]  # shape: (527,)

        # Check distress classes
        distress_scores = []
        for class_idx, (class_name, threshold) in _DISTRESS_CLASSES.items():
            score = float(probs[class_idx])
            if score >= threshold:
                distress_scores.append((class_name, score))

        # Calculate combined distress confidence
        combined = sum(s for _, s in distress_scores)

        # Check if speech is dominant (reduce false positives)
        speech_score = max(float(probs[i]) for i in _SPEECH_CLASSES)
        is_mostly_speech = speech_score > 0.6  # Real vomiting won't register as speech

        # Determine if distress (PANNs)
        panns_distress = (combined >= _COMBINED_THRESHOLD and
                          len(distress_scores) >= 2 and
                          not is_mostly_speech)

        # Run spectral analysis (catches vomiting that PANNs misclassifies)
        spectral_result = _detect_spectral_distress(audio_np_original, sample_rate)
        spectral_distress = spectral_result.get("spectral_distress", False)
        # Spectral detection also requires non-speech audio
        if spectral_distress and is_mostly_speech:
            spectral_distress = False

        # Either detector triggers = distress
        is_distress = panns_distress or spectral_distress

        # Get top 5 detected classes for debugging
        top_indices = np.argsort(probs)[-5:][::-1]
        top_classes = [(str(_labels[i]), float(probs[i])) for i in top_indices]

        elapsed = time.time() - t0

        if DEBUG_DISTRESS and (is_distress or combined > 0.15 or spectral_result.get("spectral_score", 0) > 0.15):
            source = "panns" if panns_distress else ("spectral" if spectral_distress else "none")
            logger.info(f"[DEBUG_DISTRESS] detect: distress={is_distress} (source={source}), "
                        f"panns_combined={combined:.2f}, spectral_score={spectral_result.get('spectral_score', 0):.2f}, "
                        f"speech={speech_score:.2f}, "
                        f"classes={distress_scores}, top={top_classes}, "
                        f"spectral_reason={spectral_result.get('reason', '')}, "
                        f"time={elapsed:.2f}s")

        details = ""
        if is_distress:
            if panns_distress:
                detected_names = [name for name, _ in distress_scores]
                details = f"PANNs: {', '.join(detected_names)} ({combined:.0%})"
            if spectral_distress:
                spectral_info = f"Spectral: score={spectral_result['spectral_score']:.0%}"
                details = f"{details}; {spectral_info}" if details else spectral_info

        return {
            "is_distress": is_distress,
            "confidence": max(combined, spectral_result.get("spectral_score", 0)),
            "top_classes": top_classes,
            "distress_classes": distress_scores,
            "speech_score": speech_score,
            "spectral": spectral_result,
            "details": details,
        }

    except Exception as e:
        logger.error(f"[DEBUG_DISTRESS] detect failed: {e}")
        return {"is_distress": False, "confidence": 0.0, "top_classes": [], "details": f"Error: {e}"}


def is_available() -> bool:
    """Check if the distress detector is loaded and ready."""
    return _model is not None


def _detect_spectral_distress(audio_np: np.ndarray, sample_rate: int = 16000) -> dict:
    """
    Spectral analysis detector for vomiting/retching sounds.
    
    Vomiting has distinctive audio characteristics:
    - Bursty energy pattern (retch-pause-retch, NOT sustained like hand dryers)
    - Noise-like spectrum (high spectral flatness, NOT harmonic like speech)
    - Broad bandwidth (wet, chaotic sounds)
    - NOT recognized as speech
    
    Returns dict with spectral_distress flag and feature scores.
    """
    import librosa

    try:
        y = audio_np.astype(np.float32)
        if len(y) < sample_rate * 0.5:
            return {"spectral_distress": False, "spectral_score": 0.0, "reason": "too short"}

        # Core spectral features
        spectral_flatness = float(np.mean(librosa.feature.spectral_flatness(y=y)))
        spectral_bandwidth = float(np.mean(librosa.feature.spectral_bandwidth(y=y, sr=sample_rate)))
        rms_frames = librosa.feature.rms(y=y, frame_length=2048, hop_length=512)[0]
        rms_mean = float(np.mean(rms_frames))
        rms_max = float(np.max(rms_frames))

        # Silence check — lowered to catch quiet recordings
        if rms_mean < 0.001:
            return {"spectral_distress": False, "spectral_score": 0.0, "reason": "silence"}

        # Energy burst ratio — vomiting is bursty, sustained sounds are not
        burst_ratio = rms_max / (rms_mean + 1e-8)

        # Count energy peaks (retching bursts)
        threshold = rms_mean + 2 * np.std(rms_frames)
        peaks = np.where(rms_frames > threshold)[0]
        # Group consecutive peak frames into bursts
        burst_count = 0
        if len(peaks) > 0:
            gaps = np.diff(peaks)
            burst_count = 1 + np.sum(gaps > 5)  # gap of >5 frames = separate burst

        # Scoring: each feature contributes to confidence
        score = 0.0
        reasons = []

        # Spectral flatness: >0.015 = noise-like (vomiting, wet sounds)
        if spectral_flatness > 0.015:
            flat_score = min(spectral_flatness / 0.10, 1.0) * 0.30
            score += flat_score
            reasons.append(f"flatness={spectral_flatness:.3f}")

        # Burst ratio: >3.0 = irregular energy (retching pattern)
        if burst_ratio > 3.0:
            burst_score = min((burst_ratio - 3.0) / 10.0, 1.0) * 0.35
            score += burst_score
            reasons.append(f"burst_ratio={burst_ratio:.1f}")

        # Multiple bursts: >=2 = retch-pause-retch pattern
        if burst_count >= 2:
            multi_score = min(burst_count / 5.0, 1.0) * 0.20
            score += multi_score
            reasons.append(f"bursts={burst_count}")

        # Bandwidth: >600 = broad chaotic sound (not pure tone)
        if spectral_bandwidth > 600:
            bw_score = min(spectral_bandwidth / 2000.0, 1.0) * 0.15
            score += bw_score
            reasons.append(f"bw={spectral_bandwidth:.0f}")

        # Gate: sustained noise (hand dryers, running water) has high flatness
        # but NO bursts. Vomiting always has irregular energy bursts.
        has_burst_pattern = burst_ratio > 2.5 or burst_count >= 2
        is_distress = score >= 0.35 and has_burst_pattern

        if DEBUG_DISTRESS and score > 0.15:
            logger.info(f"[DEBUG_DISTRESS] spectral: score={score:.2f}, "
                        f"distress={is_distress}, {', '.join(reasons)}, "
                        f"rms={rms_mean:.4f}, emax={rms_max:.4f}")

        return {
            "spectral_distress": is_distress,
            "spectral_score": score,
            "features": {
                "spectral_flatness": spectral_flatness,
                "spectral_bandwidth": spectral_bandwidth,
                "burst_ratio": burst_ratio,
                "burst_count": burst_count,
                "rms_mean": rms_mean,
                "rms_max": rms_max,
            },
            "reason": "; ".join(reasons) if reasons else "below thresholds",
        }

    except Exception as e:
        logger.error(f"[DEBUG_DISTRESS] spectral analysis failed: {e}")
        return {"spectral_distress": False, "spectral_score": 0.0, "reason": f"error: {e}"}
