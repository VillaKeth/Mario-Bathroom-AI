"""Comprehensive E2E test for Mario AI — sends messages, checks responses, triggers events."""
import asyncio
import json
import time
import sys
import os
import traceback

# Add parent dir
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import websockets
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "websockets", "-q"])
    import websockets

try:
    import httpx
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "httpx", "-q"])
    import httpx

SERVER = "ws://localhost:8765/ws"
API_BASE = "http://localhost:8765"

results = {"pass": 0, "fail": 0, "errors": []}

def log_result(test_name, passed, detail=""):
    status = "✅ PASS" if passed else "❌ FAIL"
    results["pass" if passed else "fail"] += 1
    if not passed:
        results["errors"].append(f"{test_name}: {detail}")
    print(f"  {status}: {test_name}" + (f" — {detail}" if detail else ""))

async def test_websocket_chat():
    """Test sending a message and getting a response via WebSocket."""
    print("\n═══ TEST 1: WebSocket Chat ═══")
    try:
        async with websockets.connect(SERVER, ping_interval=None) as ws:
            # Send a text message
            msg = json.dumps({"type": "text_input", "text": "Hello Mario! What's your favorite food?"})
            await ws.send(msg)
            
            # Collect responses for up to 30 seconds
            responses = []
            got_text = False
            got_audio = False
            got_emotion = False
            start = time.time()
            
            while time.time() - start < 45:
                try:
                    data = await asyncio.wait_for(ws.recv(), timeout=5.0)
                    if isinstance(data, str):
                        parsed = json.loads(data)
                        responses.append(parsed)
                        msg_type = parsed.get("type", "")
                        if msg_type == "mario_response":
                            got_text = True
                            text = parsed.get("text", "")
                            emotion = parsed.get("emotion", "")
                            print(f"    Mario says: {text[:100]}...")
                            print(f"    Emotion: {emotion}")
                            if emotion:
                                got_emotion = True
                        elif msg_type == "thinking":
                            print(f"    [Thinking indicator received]")
                    elif isinstance(data, bytes):
                        got_audio = True
                        print(f"    [Audio received: {len(data)} bytes]")
                        if got_text:
                            break  # Got both text and audio
                except asyncio.TimeoutError:
                    if got_text:
                        break
            
            log_result("WebSocket connects", True)
            log_result("Mario responds with text", got_text, 
                      f"Got {len(responses)} JSON messages" if not got_text else "")
            log_result("Response includes emotion", got_emotion)
            log_result("Audio TTS received", got_audio,
                      "No audio bytes received" if not got_audio else f"{len(data)} bytes")
            
    except Exception as e:
        log_result("WebSocket connects", False, str(e))
        traceback.print_exc()

async def test_emotion_changes():
    """Test that different messages produce different emotions."""
    print("\n═══ TEST 2: Emotion Changes ═══")
    test_messages = [
        ("I love you Mario! You're the best!", "positive"),
        ("That's really annoying and stupid", "negative"),
        ("What is the meaning of life?", "thoughtful"),
    ]
    
    emotions_seen = set()
    try:
        async with websockets.connect(SERVER, ping_interval=None) as ws:
            for msg_text, expected_type in test_messages:
                msg = json.dumps({"type": "text_input", "text": msg_text})
                await ws.send(msg)
                
                start = time.time()
                while time.time() - start < 30:
                    try:
                        data = await asyncio.wait_for(ws.recv(), timeout=5.0)
                        if isinstance(data, str):
                            parsed = json.loads(data)
                            if parsed.get("type") == "mario_response":
                                emotion = parsed.get("emotion", "unknown")
                                emotions_seen.add(emotion)
                                print(f"    '{msg_text[:40]}...' → emotion: {emotion}")
                                break
                    except asyncio.TimeoutError:
                        break
                
                await asyncio.sleep(2)  # Wait between messages
        
        log_result("Multiple emotions produced", len(emotions_seen) >= 2,
                  f"Saw {len(emotions_seen)} emotions: {emotions_seen}")
    except Exception as e:
        log_result("Emotion changes", False, str(e))

async def test_health_endpoint():
    """Test the /health endpoint returns valid data."""
    print("\n═══ TEST 3: Health Endpoint ═══")
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{API_BASE}/health")
            data = r.json()
            
            log_result("/health returns 200", r.status_code == 200)
            log_result("Status is ok", data.get("status") == "ok")
            log_result("LLM is ok", data.get("llm") == "ok")
            log_result("TTS is ok", data.get("tts") == "ok")
            log_result("Has emotion field", "emotion" in data)
            log_result("Has hardware info", "hardware" in data)
            log_result("GPU temp valid", isinstance(data.get("gpu_temp_c"), (int, float)))
            log_result("Memory reported", isinstance(data.get("memory_mb"), (int, float)))
            log_result("Performance tier set", data.get("performance_tier") in ["low", "medium", "high", "ultra"])
    except Exception as e:
        log_result("Health endpoint", False, str(e))

async def test_admin_announce():
    """Test admin announce endpoint."""
    print("\n═══ TEST 4: Admin Announce ═══")
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(f"{API_BASE}/admin/announce", 
                                 json={"message": "Test announcement from E2E test!"})
            log_result("Admin announce returns 200", r.status_code == 200, 
                      f"Got {r.status_code}: {r.text[:100]}" if r.status_code != 200 else "")
    except Exception as e:
        log_result("Admin announce", False, str(e))

async def test_shot_event_trigger():
    """Test triggering a shot event."""
    print("\n═══ TEST 5: Shot Event Trigger ═══")
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # List available events
            r = await client.get(f"{API_BASE}/admin/events")
            if r.status_code == 200:
                events = r.json()
                event_count = len(events) if isinstance(events, list) else events.get("count", 0)
                log_result("Events list loads", True, f"{event_count} events available")
            else:
                log_result("Events list loads", False, f"Status {r.status_code}")
            
            # Trigger a specific event
            r = await client.post(f"{API_BASE}/admin/trigger_event/mario_kart")
            if r.status_code == 200:
                log_result("Event trigger works", True)
                print(f"    Event response: {r.text[:200]}")
            else:
                log_result("Event trigger works", False, f"Status {r.status_code}: {r.text[:200]}")
                
    except Exception as e:
        log_result("Shot event", False, str(e))

async def test_idle_behavior():
    """Test that idle messages are sent when nobody is talking."""
    print("\n═══ TEST 6: Idle Behavior ═══")
    try:
        async with websockets.connect(SERVER, ping_interval=None) as ws:
            print("    Waiting up to 90s for idle message...")
            idle_received = False
            start = time.time()
            
            while time.time() - start < 90:
                try:
                    data = await asyncio.wait_for(ws.recv(), timeout=10.0)
                    if isinstance(data, str):
                        parsed = json.loads(data)
                        if parsed.get("type") in ["mario_response", "idle_message"]:
                            text = parsed.get("text", "")
                            if text:
                                idle_received = True
                                print(f"    Idle: {text[:80]}...")
                                break
                except asyncio.TimeoutError:
                    continue
            
            log_result("Idle messages work", idle_received,
                      "No idle message in 90s" if not idle_received else "")
    except Exception as e:
        log_result("Idle behavior", False, str(e))

async def test_error_resilience():
    """Test that invalid inputs don't crash the server."""
    print("\n═══ TEST 7: Error Resilience ═══")
    try:
        async with websockets.connect(SERVER, ping_interval=None) as ws:
            # Send malformed JSON
            await ws.send("not json at all")
            await asyncio.sleep(1)
            
            # Send empty message
            await ws.send(json.dumps({"type": "text_input", "text": ""}))
            await asyncio.sleep(1)
            
            # Send very long message
            long_msg = json.dumps({"type": "text_input", "text": "x" * 10000})
            await ws.send(long_msg)
            await asyncio.sleep(2)
            
            # Send normal message to verify server still works
            await ws.send(json.dumps({"type": "text_input", "text": "Are you still alive Mario?"}))
            
            got_response = False
            start = time.time()
            while time.time() - start < 30:
                try:
                    data = await asyncio.wait_for(ws.recv(), timeout=5.0)
                    if isinstance(data, str):
                        parsed = json.loads(data)
                        if parsed.get("type") == "mario_response" and parsed.get("text"):
                            got_response = True
                            print(f"    Server survived: {parsed['text'][:60]}...")
                            break
                except asyncio.TimeoutError:
                    continue
            
            log_result("Server survives bad JSON", True)
            log_result("Server survives empty message", True)
            log_result("Server survives long message", True)
            log_result("Server responds after bad inputs", got_response)
    except Exception as e:
        log_result("Error resilience", False, str(e))

async def test_keyboard_mode():
    """Test that keyboard mode messages work."""
    print("\n═══ TEST 8: Text Input Via WS ═══")
    try:
        async with websockets.connect(SERVER, ping_interval=None) as ws:
            msg = json.dumps({"type": "text_input", "text": "Tell me a joke about mushrooms!", "speaker_id": "TestUser"})
            await ws.send(msg)
            
            got_response = False
            response_text = ""
            start = time.time()
            while time.time() - start < 30:
                try:
                    data = await asyncio.wait_for(ws.recv(), timeout=5.0)
                    if isinstance(data, str):
                        parsed = json.loads(data)
                        if parsed.get("type") == "mario_response":
                            got_response = True
                            response_text = parsed.get("text", "")
                            print(f"    Joke: {response_text[:100]}...")
                            break
                except asyncio.TimeoutError:
                    if got_response:
                        break
            
            log_result("Text input produces response", got_response)
            log_result("Response has content", len(response_text) > 10,
                      f"Only {len(response_text)} chars" if len(response_text) <= 10 else "")
    except Exception as e:
        log_result("Keyboard mode", False, str(e))

async def run_all_tests():
    """Run all tests in sequence."""
    print("╔══════════════════════════════════════════╗")
    print("║   Mario AI E2E Test Suite                ║")
    print("╚══════════════════════════════════════════╝")
    
    # Check server is up
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{API_BASE}/health")
            if r.status_code != 200:
                print("❌ Server is not responding! Aborting tests.")
                return
    except:
        print("❌ Cannot reach server at localhost:8765! Start server first.")
        return
    
    print("Server is up ✅\n")
    
    await test_health_endpoint()
    await test_websocket_chat()
    await test_emotion_changes()
    await test_keyboard_mode()
    await test_error_resilience()
    await test_admin_announce()
    await test_shot_event_trigger()
    # Skip idle test (takes 90s) for now
    # await test_idle_behavior()
    
    print(f"\n{'═' * 50}")
    print(f"  RESULTS: {results['pass']} passed, {results['fail']} failed")
    if results['errors']:
        print(f"\n  FAILURES:")
        for err in results['errors']:
            print(f"    ❌ {err}")
    print(f"{'═' * 50}")
    
    return results['fail'] == 0

if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
