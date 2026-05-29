"""Pytest configuration — exclude standalone scripts from collection."""

collect_ignore = [
    "test_elevenlabs.py",
    "test_panns_direct.py",
    "test_ref_audio.py",
    "test_ref_audio_direct.py",
    "test_stt_intake.py",
    "test_vomit_voice_e2e.py",
    "party_stress_test.py",
    "e2e_party_guest_test.py",
]
