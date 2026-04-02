# tests/test_sentiment_llm.py
import pytest

def test_all_26_emotions_defined():
    from server.emotions import Emotion
    expected = {"happy", "excited", "surprised", "confused", "annoyed", "sleepy",
                "mischievous", "laughing", "sad", "angry", "nervous", "scared",
                "love", "loving", "proud", "embarrassed", "disgusted", "determined",
                "bored", "worried", "curious", "thinking", "shocked", "idea",
                "frustrated", "neutral"}
    actual = {v for k, v in vars(Emotion).items() if not k.startswith("_") and isinstance(v, str)}
    assert expected == actual, f"Missing: {expected - actual}, Extra: {actual - expected}"

def test_emotion_voice_map_covers_all():
    from server.emotions import EMOTION_VOICE_MAP, Emotion
    all_emotions = {v for k, v in vars(Emotion).items() if not k.startswith("_") and isinstance(v, str)}
    for emotion in all_emotions:
        assert emotion in EMOTION_VOICE_MAP, f"Missing voice map for {emotion}"

def test_extract_emotion_from_llm_response():
    from server.emotions import extract_emotion_tag
    response = '{"reply": "Hello!", "emotion": "excited", "energy": 0.8}'
    emotion = extract_emotion_tag(response)
    assert emotion == "excited"

def test_extract_emotion_fallback():
    from server.emotions import extract_emotion_tag
    response = "Just a plain text response with no JSON"
    emotion = extract_emotion_tag(response)
    assert emotion == "neutral"
