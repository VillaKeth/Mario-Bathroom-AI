import pytest
from server.emotions import extract_emotion_tag


def test_extract_emotion_from_response():
    text = 'Wahoo! Let\'s-a go!\n{"emotion": "excited", "energy": 0.9}'
    result = extract_emotion_tag(text)
    assert result["emotion"] == "excited"
    assert result["energy"] == 0.9


def test_extract_strips_json_from_text():
    text = 'Hello friend!\n{"emotion": "happy", "energy": 0.7}'
    result = extract_emotion_tag(text)
    # The clean text shouldn't contain the JSON
    clean_text = result.get("clean_text", "")
    assert "emotion" not in clean_text
    assert "Hello friend!" in clean_text


def test_extract_fallback_neutral():
    text = "Just a normal response with no JSON"
    result = extract_emotion_tag(text)
    assert result["emotion"] == "neutral"
    assert result["energy"] == 0.5


def test_extract_invalid_json():
    text = 'Hello!\n{"emotion": "invalid_emotion", "energy": 0.8}'
    result = extract_emotion_tag(text)
    # Should fall back to neutral for invalid emotions
    assert result["emotion"] == "neutral"
    assert result["energy"] == 0.8  # But energy should still be extracted


def test_extract_energy_clamped():
    text = 'Wow!\n{"emotion": "excited", "energy": 1.5}'
    result = extract_emotion_tag(text)
    assert result.get("energy", 1.0) <= 1.0
    assert result.get("energy", 1.0) == 1.0  # Should be clamped to 1.0


def test_extract_energy_negative_clamped():
    text = 'Ugh...\n{"emotion": "sad", "energy": -0.2}'
    result = extract_emotion_tag(text)
    assert result.get("energy", 0.0) >= 0.0
    assert result.get("energy", 0.0) == 0.0  # Should be clamped to 0.0


def test_extract_multiline_response():
    text = '''Wahoo! This is a longer response.
    It has multiple lines and stuff.
    But ends with sentiment data!
    {"emotion": "mischievous", "energy": 0.8}'''
    result = extract_emotion_tag(text)
    assert result["emotion"] == "mischievous"
    assert result["energy"] == 0.8
    clean_text = result.get("clean_text", "")
    assert "Wahoo! This is a longer response." in clean_text
    assert "mischievous" not in clean_text  # JSON should be stripped


def test_extract_malformed_json():
    text = 'Hello!\n{"emotion": "happy", "energy": not_a_number}'
    result = extract_emotion_tag(text)
    # Should fall back to defaults on malformed JSON
    assert result["emotion"] == "neutral"
    assert result["energy"] == 0.5


def test_extract_partial_json():
    text = 'Hello!\n{"emotion": "curious"}'  # Missing energy
    result = extract_emotion_tag(text)
    assert result["emotion"] == "curious"
    assert result["energy"] == 0.5  # Should default to 0.5


def test_extract_energy_only():
    text = 'Hello!\n{"energy": 0.3}'  # Missing emotion
    result = extract_emotion_tag(text)
    assert result["emotion"] == "neutral"  # Should default to neutral
    assert result["energy"] == 0.3