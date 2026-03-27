"""
Audio distress detector using PANNs (Pre-trained Audio Neural Networks).
Detects vomiting/retching/gagging sounds from raw audio bytes.

Uses Cnn14 model trained on AudioSet (527 classes) to classify audio events.
Vomiting is detected as a combination of: gasp + groan + gargling + stomach rumble + cough.
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

        # Determine if distress
        is_distress = (combined >= _COMBINED_THRESHOLD and
                       len(distress_scores) >= 2 and
                       not is_mostly_speech)

        # Get top 5 detected classes for debugging
        top_indices = np.argsort(probs)[-5:][::-1]
        top_classes = [(str(_labels[i]), float(probs[i])) for i in top_indices]

        elapsed = time.time() - t0

        if DEBUG_DISTRESS and (is_distress or combined > 0.15):
            logger.info(f"[DEBUG_DISTRESS] detect: distress={is_distress}, "
                        f"combined={combined:.2f}, speech={speech_score:.2f}, "
                        f"classes={distress_scores}, top={top_classes}, "
                        f"time={elapsed:.2f}s")

        details = ""
        if is_distress:
            detected_names = [name for name, _ in distress_scores]
            details = f"Detected: {', '.join(detected_names)} (confidence: {combined:.0%})"

        return {
            "is_distress": is_distress,
            "confidence": combined,
            "top_classes": top_classes,
            "distress_classes": distress_scores,
            "speech_score": speech_score,
            "details": details,
        }

    except Exception as e:
        logger.error(f"[DEBUG_DISTRESS] detect failed: {e}")
        return {"is_distress": False, "confidence": 0.0, "top_classes": [], "details": f"Error: {e}"}


def is_available() -> bool:
    """Check if the distress detector is loaded and ready."""
    return _model is not None
