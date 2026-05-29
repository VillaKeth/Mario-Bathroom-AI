"""Pytest configuration — exclude standalone/integration scripts from collection.

These files either:
- Connect to live services (WebSocket, Qdrant, etc.) during import/collection
- Are standalone diagnostic scripts, not proper pytest tests
- Require hardware (camera, microphone) to run
"""

collect_ignore = [
    # Standalone diagnostic scripts (not pytest tests)
    "test_elevenlabs.py",
    "test_panns_direct.py",
    "test_ref_audio.py",
    "test_ref_audio_direct.py",
    "test_stt_intake.py",
    "test_vomit_voice_e2e.py",
    "party_stress_test.py",
    "e2e_party_guest_test.py",
    # Integration tests that connect to live server during collection
    "test_game_routing.py",
    "test_single_game.py",
    # E2E tests requiring full server + hardware
    "test_features_e2e.py",
    "test_e2e_comprehensive.py",
    "test_audio_e2e.py",
    "test_recognition_e2e.py",
    "test_guest_integration.py",
    # Live service tests
    "test_stt_live.py",
    "test_real_panns.py",
    "test_tts_panns.py",
    # WebSocket integration tests (connect during import)
    "test_interrupt.py",
    "test_interrupt_deep.py",
    "test_ws_chat.py",
    "test_integration.py",
    # Private/manual E2E scripts (prefixed with _)
    "_e2e_test.py",
    "_visual_test.py",
]
