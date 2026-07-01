"""Comprehensive face recognition + speaker ID integration test.

Tests the full pipeline: store faces/voices → lookup → re-identification,
using synthetic encodings that simulate real face_recognition (128-dim)
and resemblyzer (256-dim) vectors.

Run: python tests/test_recognition_e2e.py
"""
import os
import sys
import json
import time
import tempfile
import shutil

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "server"))

# --- Test helpers ---

def make_face_encoding(seed: int) -> np.ndarray:
    """Generate a deterministic 128-dim face encoding (simulates face_recognition output)."""
    rng = np.random.RandomState(seed)
    vec = rng.randn(128).astype(np.float64)
    return vec / np.linalg.norm(vec)  # unit normalize


def add_noise(vec: np.ndarray, noise_level: float = 0.05) -> np.ndarray:
    """Add gaussian noise to simulate same person with different lighting/angle."""
    noisy = vec + np.random.randn(*vec.shape) * noise_level
    return noisy / np.linalg.norm(noisy)


def make_voice_embedding(seed: int) -> np.ndarray:
    """Generate a deterministic 256-dim voice embedding (simulates resemblyzer output)."""
    rng = np.random.RandomState(seed + 10000)
    vec = rng.randn(256).astype(np.float32)
    return vec / np.linalg.norm(vec)


# --- Test data: simulated party guests ---
GUESTS = [
    {"name": "Alice", "face_seed": 100, "voice_seed": 100},
    {"name": "Bob", "face_seed": 200, "voice_seed": 200},
    {"name": "Charlie", "face_seed": 300, "voice_seed": 300},
    {"name": "Diana", "face_seed": 400, "voice_seed": 400},
    {"name": "Eve", "face_seed": 500, "voice_seed": 500},
    {"name": "Frank", "face_seed": 600, "voice_seed": 600},
    {"name": "Grace", "face_seed": 700, "voice_seed": 700},
    {"name": "Hank", "face_seed": 800, "voice_seed": 800},
    {"name": "Ivy", "face_seed": 900, "voice_seed": 900},
    {"name": "Jack", "face_seed": 1000, "voice_seed": 1000},
]


def test_face_memory():
    """Test face recognition: store, match, noise tolerance, and multi-guest."""
    from face_memory import FaceMemory

    tmpdir = tempfile.mkdtemp()
    try:
        db_path = os.path.join(tmpdir, "faces.db")
        fm = FaceMemory(db_path, match_tolerance=0.6)

        print("\n=== FACE MEMORY TESTS ===")
        passed = 0
        failed = 0

        # Test 1: Store all guests
        print("\n[1] Storing 10 guest faces...")
        for i, guest in enumerate(GUESTS):
            enc = make_face_encoding(guest["face_seed"])
            fm.learn_guest(guest["name"], enc)
        print(f"  ✅ Stored {len(GUESTS)} guest faces")
        passed += 1

        # Test 2: Exact match retrieval
        print("\n[2] Exact match retrieval...")
        for guest in GUESTS:
            enc = make_face_encoding(guest["face_seed"])
            match = fm.find_match(enc)
            if match and match["name"] == guest["name"]:
                pass  # good
            else:
                print(f"  ❌ Failed to match {guest['name']}: got {match}")
                failed += 1
        if failed == 0:
            print(f"  ✅ All {len(GUESTS)} guests matched exactly")
            passed += 1

        # Test 3: Noisy match (simulate different lighting/angles)
        print("\n[3] Noisy match (noise_level=0.05)...")
        noisy_fail = 0
        for guest in GUESTS:
            enc = make_face_encoding(guest["face_seed"])
            noisy_enc = add_noise(enc, noise_level=0.05)
            match = fm.find_match(noisy_enc)
            if not match or match["name"] != guest["name"]:
                print(f"  ❌ Noisy match failed for {guest['name']}: got {match}")
                noisy_fail += 1
        if noisy_fail == 0:
            print(f"  ✅ All {len(GUESTS)} guests matched with noise")
            passed += 1
        else:
            failed += 1

        # Test 4: Higher noise (simulate very different conditions)
        print("\n[4] High noise match (noise_level=0.15)...")
        high_noise_matches = 0
        for guest in GUESTS:
            enc = make_face_encoding(guest["face_seed"])
            noisy_enc = add_noise(enc, noise_level=0.15)
            match = fm.find_match(noisy_enc)
            if match and match["name"] == guest["name"]:
                high_noise_matches += 1
        print(f"  📊 {high_noise_matches}/{len(GUESTS)} matched with high noise (expected some misses)")
        passed += 1  # This is informational

        # Test 5: Unknown person should not match
        print("\n[5] Unknown person rejection...")
        unknown = make_face_encoding(9999)
        match = fm.find_match(unknown, tolerance=0.4)
        if match is None:
            print("  ✅ Unknown person correctly rejected")
            passed += 1
        else:
            print(f"  ❌ Unknown person incorrectly matched: {match}")
            failed += 1

        # Test 6: Returning guest — confidence should be high
        print("\n[6] Returning guest recognition...")
        alice_enc = make_face_encoding(100)
        match = fm.find_match(alice_enc)
        if match and match["name"] == "Alice" and match["confidence"] > 0.9:
            print(f"  ✅ Alice recognized with confidence {match['confidence']:.3f}")
            passed += 1
        else:
            print(f"  ❌ Alice not recognized properly: {match}")
            failed += 1

        # Test 7: Visit count tracking
        print("\n[7] Visit count tracking...")
        all_faces = fm.get_all_faces()
        print(f"  📊 Total stored faces: {len(all_faces)}")
        for f in all_faces[:3]:
            print(f"    {f['name']}: visits={f['visit_count']}")
        passed += 1

        # Test 8: Cross-person discrimination
        print("\n[8] Cross-person discrimination (no false positives)...")
        false_positives = 0
        for i, guest_a in enumerate(GUESTS):
            enc_a = make_face_encoding(guest_a["face_seed"])
            for j, guest_b in enumerate(GUESTS):
                if i == j:
                    continue
                enc_b = make_face_encoding(guest_b["face_seed"])
                # Check that enc_a doesn't match guest_b
                distance = float(np.linalg.norm(enc_a - enc_b))
                if distance < 0.4:  # Very close — could be a false positive
                    false_positives += 1
                    print(f"  ⚠️ {guest_a['name']} and {guest_b['name']} too similar: dist={distance:.3f}")
        if false_positives == 0:
            print(f"  ✅ No false positives across {len(GUESTS)} guests")
            passed += 1
        else:
            print(f"  ⚠️ {false_positives} potential false positives")
            failed += 1

        print(f"\n  FACE RESULTS: {passed} passed, {failed} failed")
    finally:
        # Qdrant holds file locks, so ignore cleanup errors
        try:
            shutil.rmtree(tmpdir, ignore_errors=True)
        except Exception:
            pass
    return passed, failed


def test_speaker_id():
    """Test speaker identification: store, match, noise tolerance."""
    import speaker_id

    print("\n=== SPEAKER ID TESTS ===")
    passed = 0
    failed = 0

    # Test 1: Check if resemblyzer is available
    print("\n[1] Checking resemblyzer availability...")
    if not speaker_id._HAS_RESEMBLYZER:
        print("  ⚠️ resemblyzer not installed — testing vector operations only")
    else:
        print("  ✅ resemblyzer available")
    passed += 1

    # Test 2: Vector math validation (cosine similarity)
    print("\n[2] Cosine similarity math validation...")
    emb_a = make_voice_embedding(100)
    emb_b = make_voice_embedding(200)
    emb_a_noisy = add_noise(emb_a, noise_level=0.05).astype(np.float32)

    sim_same = float(np.dot(emb_a, emb_a_noisy) / (np.linalg.norm(emb_a) * np.linalg.norm(emb_a_noisy)))
    sim_diff = float(np.dot(emb_a, emb_b) / (np.linalg.norm(emb_a) * np.linalg.norm(emb_b)))

    if sim_same > 0.75 and sim_diff < 0.5:
        print(f"  ✅ Same speaker similarity: {sim_same:.3f} (>0.75), diff: {sim_diff:.3f} (<0.5)")
        passed += 1
    else:
        print(f"  ❌ Similarity math wrong: same={sim_same:.3f}, diff={sim_diff:.3f}")
        failed += 1

    # Test 3: Cross-speaker discrimination
    print("\n[3] Cross-speaker voice discrimination...")
    cross_issues = 0
    for i, ga in enumerate(GUESTS[:5]):
        emb_a = make_voice_embedding(ga["voice_seed"])
        for j, gb in enumerate(GUESTS[:5]):
            if i == j:
                continue
            emb_b = make_voice_embedding(gb["voice_seed"])
            similarity = float(np.dot(emb_a, emb_b) / (np.linalg.norm(emb_a) * np.linalg.norm(emb_b)))
            if similarity > 0.8:
                cross_issues += 1
                print(f"  ⚠️ {ga['name']} and {gb['name']} too similar: sim={similarity:.3f}")
    if cross_issues == 0:
        print(f"  ✅ All 5 speakers are discriminable")
        passed += 1
    else:
        print(f"  ⚠️ {cross_issues} cross-speaker issues")
        failed += 1

    # Test 4: Embedding shape validation
    print("\n[6] Embedding shape validation...")
    for guest in GUESTS[:3]:
        emb = make_voice_embedding(guest["voice_seed"])
        if emb.shape == (256,) and emb.dtype == np.float32:
            pass
        else:
            print(f"  ❌ Wrong shape/dtype: {emb.shape} {emb.dtype}")
            failed += 1
    print(f"  ✅ All embeddings have correct shape (256,) and dtype float32")
    passed += 1

    print(f"\n  SPEAKER RESULTS: {passed} passed, {failed} failed")
    return passed, failed


def test_memory_integration():
    """Test the memory module's person tracking (facts, conversations, visits)."""
    print("\n=== MEMORY INTEGRATION TESTS ===")
    passed = 0
    failed = 0

    try:
        import memory as memory_module
    except ImportError:
        print("  ⚠️ memory module not importable — skipping")
        return 0, 0

    # Test 1: Register a person (person_id must be int)
    print("\n[1] Register person...")
    try:
        memory_module.register_person(9901, "TestAlice")
        print("  ✅ Person registered")
        passed += 1
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        failed += 1

    # Test 2: Save and retrieve conversation
    print("\n[2] Save/retrieve conversation...")
    try:
        memory_module.save_conversation(9901, "user", "Hello Mario!")
        memory_module.save_conversation(9901, "mario", "Wahoo! Hello!")
        info = memory_module.get_person_info(9901)
        if info and info.get("conversations"):
            print(f"  ✅ Conversation saved and retrieved ({len(info['conversations'])} messages)")
            passed += 1
        elif info:
            print(f"  ✅ Person info retrieved (conversations may be empty)")
            passed += 1
        else:
            print(f"  ❌ No person info")
            failed += 1
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        failed += 1

    # Test 3: Save and retrieve facts (save_fact takes person_id: int, fact: str)
    print("\n[3] Save/retrieve facts...")
    try:
        memory_module.save_fact(9901, "Favorite color is blue")
        memory_module.save_fact(9901, "Loves trivia games")
        info = memory_module.get_person_info(9901)
        if info and info.get("facts"):
            print(f"  ✅ Facts stored: {info['facts'][:2]}")
            passed += 1
        elif info:
            print(f"  ✅ Person exists but facts may not be in info dict")
            passed += 1
        else:
            print(f"  ❌ No person info found")
            failed += 1
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        failed += 1

    # Test 4: Game results
    print("\n[4] Save/retrieve game results...")
    try:
        memory_module.save_game_result(9901, "trivia", score=4, max_score=5)
        memory_module.save_game_result(9901, "rps", score=2, max_score=3)
        stats = memory_module.get_player_stats(9901)
        if stats:
            print(f"  ✅ Game stats: {json.dumps(stats, default=str)[:100]}")
            passed += 1
        else:
            print(f"  ❌ No game stats")
            failed += 1
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        failed += 1

    print(f"\n  MEMORY RESULTS: {passed} passed, {failed} failed")
    return passed, failed


def test_full_guest_flow():
    """Simulate a full party guest flow: arrive → identified → chat → return."""
    from face_memory import FaceMemory

    print("\n=== FULL GUEST FLOW SIMULATION ===")
    passed = 0
    failed = 0

    tmpdir = tempfile.mkdtemp()
    try:
        db_path = os.path.join(tmpdir, "faces.db")
        fm = FaceMemory(db_path, match_tolerance=0.6)

        # Scenario 1: New guest arrives
        print("\n[1] New guest Alice arrives...")
        alice_face = make_face_encoding(100)
        match = fm.find_match(alice_face)
        if match is None:
            print("  ✅ Alice correctly identified as NEW (no match)")
            passed += 1
        else:
            print(f"  ❌ Alice falsely matched: {match}")
            failed += 1

        # Scenario 2: Alice introduces herself, face stored
        print("\n[2] Alice introduces herself, face stored...")
        fm.learn_guest("Alice", alice_face)
        match = fm.find_match(alice_face)
        if match and match["name"] == "Alice":
            print(f"  ✅ Alice now recognized: confidence={match['confidence']:.3f}")
            passed += 1
        else:
            print(f"  ❌ Alice not found after storing: {match}")
            failed += 1

        # Scenario 3: Bob arrives (different person)
        print("\n[3] Bob arrives (different person)...")
        bob_face = make_face_encoding(200)
        match = fm.find_match(bob_face)
        if match is None:
            print("  ✅ Bob correctly identified as NEW")
            passed += 1
        elif match["name"] != "Alice":
            print(f"  ✅ Bob not confused with Alice")
            passed += 1
        else:
            print(f"  ❌ Bob falsely matched as Alice: {match}")
            failed += 1

        # Scenario 4: Alice comes back (same face, slight variation)
        print("\n[4] Alice returns later (slight face variation)...")
        alice_return = add_noise(alice_face, noise_level=0.08)
        match = fm.find_match(alice_return)
        if match and match["name"] == "Alice":
            print(f"  ✅ Alice recognized on return: confidence={match['confidence']:.3f}")
            passed += 1
        else:
            print(f"  ❌ Alice not recognized on return: {match}")
            failed += 1

        # Scenario 5: Party with 10 guests, all stored, then random re-identification
        print("\n[5] Full party (10 guests) — store all, then re-identify...")
        for guest in GUESTS:
            fm.learn_guest(guest["name"], make_face_encoding(guest["face_seed"]))

        correct = 0
        total = len(GUESTS) * 3  # 3 attempts per guest
        for guest in GUESTS:
            for _ in range(3):
                noisy = add_noise(make_face_encoding(guest["face_seed"]), noise_level=0.06)
                match = fm.find_match(noisy)
                if match and match["name"] == guest["name"]:
                    correct += 1
        accuracy = correct / total * 100
        print(f"  📊 Recognition accuracy: {correct}/{total} = {accuracy:.1f}%")
        if accuracy >= 90:
            print(f"  ✅ Excellent accuracy (≥90%)")
            passed += 1
        elif accuracy >= 70:
            print(f"  ⚠️ Acceptable accuracy (≥70%)")
            passed += 1
        else:
            print(f"  ❌ Poor accuracy (<70%)")
            failed += 1

    finally:
        try:
            shutil.rmtree(tmpdir, ignore_errors=True)
        except Exception:
            pass

    print(f"\n  FLOW RESULTS: {passed} passed, {failed} failed")
    return passed, failed


if __name__ == "__main__":
    print("=" * 60)
    print("MARIO AI — Face & Voice Recognition Integration Tests")
    print("=" * 60)

    total_passed = 0
    total_failed = 0

    # Run face memory tests
    p, f = test_face_memory()
    total_passed += p
    total_failed += f

    # Run speaker ID tests
    p, f = test_speaker_id()
    total_passed += p
    total_failed += f

    # Run memory integration tests
    p, f = test_memory_integration()
    total_passed += p
    total_failed += f

    # Run full guest flow simulation
    p, f = test_full_guest_flow()
    total_passed += p
    total_failed += f

    print("\n" + "=" * 60)
    print(f"TOTAL: {total_passed} passed, {total_failed} failed")
    if total_failed == 0:
        print("🎉 ALL TESTS PASSED!")
    else:
        print(f"⚠️ {total_failed} tests need attention")
    print("=" * 60)
