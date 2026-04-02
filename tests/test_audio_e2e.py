"""
E2E Audio Distress Test + TTS Verification Script
Tests:
1. PANNs distress detection on synthetic retching audio
2. WebSocket audio-only vomit scenario (no text warning)
3. TTS output verification via STT (does Mario say what the text says?)
"""
import asyncio
import json
import sys
import os
import wave
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

# ---- Test 1: Direct PANNs detection on synthetic audio ----
def test_panns_direct():
    print("=" * 60)
    print("TEST 1: Direct PANNs detection on synthetic retching audio")
    print("=" * 60)
    
    try:
        from audio_distress import detect_distress, is_available
        if not is_available():
            print("SKIP: PANNs model not available")
            return False
        
        raw_path = os.path.join(os.path.dirname(__file__), "test_retch_raw.pcm")
        with open(raw_path, "rb") as f:
            audio_bytes = f.read()
        
        print(f"Audio: {len(audio_bytes)} bytes ({len(audio_bytes)/2/16000:.1f}s @ 16kHz)")
        
        result = detect_distress(audio_bytes, sample_rate=16000)
        print(f"  is_distress: {result['is_distress']}")
        print(f"  confidence:  {result['confidence']:.3f}")
        print(f"  speech_score: {result.get('speech_score', 'N/A')}")
        print(f"  details: {result.get('details', 'N/A')}")
        if result.get('top_classes'):
            print(f"  Top classes:")
            for name, score in result['top_classes'][:10]:
                print(f"    {name}: {score:.4f}")
        if result.get('distress_classes'):
            print(f"  Distress classes triggered:")
            for name, score in result['distress_classes']:
                print(f"    {name}: {score:.4f}")
        
        return result['is_distress']
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


# ---- Test 2: WebSocket audio-only vomit test ----
async def test_ws_audio_vomit():
    print("\n" + "=" * 60)
    print("TEST 2: WebSocket audio-only vomit (no text, just audio)")
    print("=" * 60)
    
    try:
        import websockets
    except ImportError:
        print("Installing websockets...")
        os.system("pip install websockets")
        import websockets
    
    raw_path = os.path.join(os.path.dirname(__file__), "test_retch_raw.pcm")
    with open(raw_path, "rb") as f:
        audio_bytes = f.read()
    
    uri = "ws://localhost:8765/ws"
    responses = []
    
    try:
        async with websockets.connect(uri) as ws:
            # Enter the bathroom first
            await ws.send(json.dumps({
                "type": "presence_enter",
                "visitor_name": "VomitTestGuest"
            }))
            print("Sent: presence_enter as VomitTestGuest")
            
            # Wait for greeting
            greeting_count = 0
            while greeting_count < 2:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=20)
                    if isinstance(msg, bytes):
                        continue  # Skip audio frames
                    data = json.loads(msg)
                    if data.get("type") in ("mario_response", "greeting"):
                        greeting_count += 1
                        print(f"  Greeting {greeting_count}: {data.get('text', '')[:80]}...")
                except asyncio.TimeoutError:
                    break
            
            # NOW: Send raw audio with NO text message first
            # This simulates someone walking in and immediately retching
            print(f"\nSending {len(audio_bytes)} bytes of retching audio (no text)...")
            
            # Send in chunks like a real mic would
            chunk_size = 16000  # 0.5s chunks
            for i in range(0, len(audio_bytes), chunk_size):
                chunk = audio_bytes[i:i + chunk_size]
                await ws.send(chunk)
                await asyncio.sleep(0.1)
            
            print("Audio sent. Waiting for distress response...")
            
            # Listen for comfort response
            start = time.time()
            got_comfort = False
            while time.time() - start < 30:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=10)
                    if isinstance(msg, bytes):
                        continue
                    data = json.loads(msg)
                    text = data.get("text", "")
                    msg_type = data.get("type", "")
                    print(f"  [{msg_type}] {text[:100]}")
                    responses.append(data)
                    
                    # Check if this is a comfort/distress response
                    comfort_keywords = ["water", "towel", "breathe", "nose", "rough", 
                                       "pipes", "karaoke", "worse", "cold", "passes",
                                       "right room", "take your time", "keep everyone out"]
                    if any(kw in text.lower() for kw in comfort_keywords):
                        got_comfort = True
                        print(f"\n  ✅ DISTRESS DETECTED! Mario responded with comfort!")
                        break
                except asyncio.TimeoutError:
                    break
            
            if not got_comfort:
                print(f"\n  ❌ No comfort response detected from audio alone")
                print(f"  Responses received: {len(responses)}")
            
            # Clean up - leave
            await ws.send(json.dumps({"type": "presence_exit"}))
            return got_comfort
            
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


# ---- Test 3: TTS verification via STT ----
def test_tts_verification():
    print("\n" + "=" * 60)
    print("TEST 3: TTS output verification via Whisper STT")
    print("=" * 60)
    
    try:
        from tts import tts_engine
        from stt import transcribe
        
        test_phrases = [
            "Hey friend, you're in the right room for this.",
            "Bowser?! Where?! Don't scare Mario like that!",
            "Why did Mario go to the doctor? Because he had too many extra lives!",
        ]
        
        results = []
        for phrase in test_phrases:
            print(f"\n  Original: \"{phrase}\"")
            
            # Generate TTS
            audio_data = tts_engine.synthesize(phrase)
            if not audio_data:
                print(f"  ❌ TTS failed to generate audio")
                results.append(False)
                continue
            
            print(f"  TTS: {len(audio_data)} bytes")
            
            # Run STT on the TTS output
            transcript = transcribe(audio_data)
            print(f"  STT heard: \"{transcript}\"")
            
            # Compare (fuzzy match - check key words)
            orig_words = set(phrase.lower().split())
            heard_words = set(transcript.lower().split()) if transcript else set()
            overlap = orig_words & heard_words
            similarity = len(overlap) / max(len(orig_words), 1)
            
            passed = similarity >= 0.5
            status = "✅" if passed else "❌"
            print(f"  {status} Word overlap: {similarity:.0%} ({len(overlap)}/{len(orig_words)} words)")
            results.append(passed)
        
        return all(results)
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("Mario AI - Audio E2E Test Suite")
    print("================================\n")
    
    # Test 1: Direct PANNs
    panns_ok = test_panns_direct()
    
    # Test 2: WebSocket vomit
    ws_ok = asyncio.run(test_ws_audio_vomit())
    
    # Test 3 is heavy (loads TTS+STT) - run if requested
    tts_ok = None
    if "--tts" in sys.argv:
        tts_ok = test_tts_verification()
    
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"  PANNs direct detection: {'✅ PASS' if panns_ok else '❌ FAIL'}")
    print(f"  WebSocket audio vomit:  {'✅ PASS' if ws_ok else '❌ FAIL'}")
    if tts_ok is not None:
        print(f"  TTS→STT verification:   {'✅ PASS' if tts_ok else '❌ FAIL'}")
    else:
        print(f"  TTS→STT verification:   SKIPPED (run with --tts)")
