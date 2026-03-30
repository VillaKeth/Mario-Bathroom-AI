"""
Audio distress detector — dual approach: PANNs + Spectral Analysis.
Detects vomiting/retching/gagging sounds from raw audio bytes.

PANNs: Uses Cnn14 model (AudioSet 527 classes) for class-based detection.
Spectral: Analyzes energy bursts, spectral flatness, and bandwidth
          to catch vomiting sounds that PANNs misclassifies.
"""

import logging
import numpy as np
import time

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

_model = None
_labels = None


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
