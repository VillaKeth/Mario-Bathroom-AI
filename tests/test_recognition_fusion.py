"""SNR-aware identity fusion: trust the face when it matched; only fall back to a
voice match if its confidence clears a noise-scaled floor (so loud rooms don't
produce false-accepts from a shaky voiceprint)."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

import recognition_fusion as rf  # noqa: E402


def V(name, conf, is_new=False):
    return {"name": name, "confidence": conf, "is_new": is_new}


def F(name, conf):
    return {"name": name, "confidence": conf}


def test_face_match_wins_even_when_voice_also_present():
    out = rf.fuse_identity(voice=V("Ava", 0.9), face=F("Ava", 0.7), noise_level=0.0)
    assert out["name"] == "Ava"
    assert out["source"] == "face"


def test_face_match_wins_over_disagreeing_voice():
    # camera says Ben (cleared the calibrated face threshold); noisy voice says Ava.
    out = rf.fuse_identity(voice=V("Ava", 0.66), face=F("Ben", 0.55), noise_level=0.8)
    assert out["name"] == "Ben"
    assert out["source"] == "face"


def test_voice_used_when_no_face_and_clean():
    out = rf.fuse_identity(voice=V("Cara", 0.72), face=None, noise_level=0.0)
    assert out["name"] == "Cara"
    assert out["source"] == "voice"


def test_voice_rejected_when_noisy_and_below_scaled_floor():
    # 0.70 passes the clean floor but not the raised floor under heavy noise.
    out = rf.fuse_identity(voice=V("Cara", 0.70), face=None, noise_level=1.0)
    assert out["name"] is None
    assert out["source"] is None


def test_voice_accepted_when_noisy_but_very_confident():
    out = rf.fuse_identity(voice=V("Dan", 0.92), face=None, noise_level=1.0)
    assert out["name"] == "Dan"
    assert out["source"] == "voice"


def test_new_or_missing_voice_and_no_face_is_unknown():
    assert rf.fuse_identity(voice=V(None, 0.0, is_new=True), face=None, noise_level=0.0)["name"] is None
    assert rf.fuse_identity(voice=None, face=None, noise_level=0.0)["name"] is None


def test_voice_floor_rises_with_noise():
    assert rf.voice_confidence_floor(1.0) > rf.voice_confidence_floor(0.0)
    assert rf.voice_confidence_floor(0.0) >= 0.6


def test_live_party_noise_default_is_strict():
    # The live default must demand a clearly-strict voice floor so an un-enrolled
    # stranger is not greeted by a guest's name (open-set rejection).
    assert 0.0 < rf.LIVE_PARTY_NOISE_LEVEL <= 1.0
    assert rf.voice_confidence_floor(rf.LIVE_PARTY_NOISE_LEVEL) >= 0.72
