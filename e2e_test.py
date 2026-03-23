"""End-to-end quality and latency test for Mario AI."""
import time
import requests
import httpx

SERVER = "http://localhost:8765"

def test_health():
    print("=== TEST 1: Server Health ===")
    t0 = time.time()
    r = requests.get(f"{SERVER}/health")
    h = r.json()
    print(f"  Status: {h['status']} ({time.time()-t0:.1f}s)")
    print(f"  TTS: {h.get('tts_engine', '?')}")
    print(f"  Precache: {h.get('precache_done', '?')}")

def test_cached_tts():
    print("\n=== TEST 2: Cached TTS Latency ===")
    phrases = ["It's-a me, Mario!", "Wahoo!", "Mama mia!", "Hello there!", "Welcome, welcome!"]
    for phrase in phrases:
        t0 = time.time()
        r = requests.get(f"{SERVER}/tts", params={"text": phrase})
        lat = time.time() - t0
        size = len(r.content) if r.status_code == 200 else 0
        status = "OK" if size > 100 else "EMPTY"
        print(f"  [{status}] \"{phrase}\" -> {lat*1000:.0f}ms, {size:,} bytes")

def test_live_tts():
    print("\n=== TEST 3: Live TTS Generation ===")
    phrases = [
        "Hey there, how are you doing tonight?",
        "That's a really great question, let me think about it!",
        "Welcome to the party, have a wonderful time!",
    ]
    for phrase in phrases:
        t0 = time.time()
        r = requests.get(f"{SERVER}/tts", params={"text": phrase, "nocache": 1})
        lat = time.time() - t0
        size = len(r.content) if r.status_code == 200 else 0
        status = "OK" if size > 100 else "EMPTY"
        print(f"  [{status}] \"{phrase[:45]}\" -> {lat:.1f}s, {size:,} bytes")

def test_llm():
    print("\n=== TEST 4: LLM Response Quality ===")
    prompts = [
        "Tell me a joke about being in the bathroom",
        "What do you think about pineapple on pizza?",
        "I just got here, what should I do?",
    ]
    for prompt in prompts:
        t0 = time.time()
        r = httpx.post("http://localhost:11434/api/generate", json={
            "model": "llama3",
            "prompt": f"You are Mario from Nintendo. Stay in character. Keep response under 25 words. User says: {prompt}",
            "stream": False,
            "options": {"num_predict": 35, "temperature": 0.8}
        }, timeout=30)
        lat = time.time() - t0
        resp = r.json().get("response", "?").strip()
        print(f"  [{lat:.1f}s] Q: \"{prompt}\"")
        print(f"         A: \"{resp[:80]}\"")
        print()

def test_full_pipeline():
    print("=== TEST 5: Full Pipeline (LLM + TTS) ===")
    prompts = [
        "Hey Mario, tell me something funny!",
        "What's your favorite food?",
    ]
    for prompt in prompts:
        t0 = time.time()
        # LLM
        r = httpx.post("http://localhost:11434/api/generate", json={
            "model": "llama3",
            "prompt": f"You are Mario from Nintendo. Stay in character. Keep response under 25 words. User says: {prompt}",
            "stream": False,
            "options": {"num_predict": 35, "temperature": 0.8}
        }, timeout=30)
        llm_time = time.time() - t0
        resp = r.json().get("response", "").strip()

        # TTS
        t1 = time.time()
        r2 = requests.get(f"{SERVER}/tts", params={"text": resp})
        tts_time = time.time() - t1
        total = time.time() - t0
        size = len(r2.content) if r2.status_code == 200 else 0

        print(f"  Q: \"{prompt}\"")
        print(f"  A: \"{resp[:80]}\"")
        print(f"  LLM: {llm_time:.1f}s | TTS: {tts_time:.1f}s | Total: {total:.1f}s | Audio: {size:,} bytes")
        print()

def test_websocket():
    """Test the WebSocket conversation flow."""
    import asyncio
    import websockets
    import json

    async def ws_test():
        print("\n=== TEST 6: WebSocket Conversation Flow ===")
        try:
            async with websockets.connect("ws://localhost:8765/ws", ping_timeout=30) as ws:
                print("  [OK] WebSocket connected")

                # 1. Send presence_enter
                await ws.send(json.dumps({"type": "presence_enter"}))
                print("  [SENT] presence_enter")

                # Wait for greeting response
                greeting = None
                for _ in range(10):  # Wait up to 30s
                    try:
                        msg = await asyncio.wait_for(ws.recv(), timeout=3.0)
                        if isinstance(msg, bytes):
                            continue  # Skip binary audio frames
                        data = json.loads(msg)
                        if data.get("type") == "mario_response":
                            greeting = data.get("text", "")
                            print(f"  [OK] Greeting: \"{greeting[:80]}\"")
                            break
                        elif data.get("type") == "state":
                            print(f"  [STATE] {data.get('presence_phase', '?')}")
                    except asyncio.TimeoutError:
                        continue

                if not greeting:
                    print("  [WARN] No greeting received (may need presence detection)")

                # 2. Send text input
                await ws.send(json.dumps({"type": "text_input", "text": "Hey Mario, what's your favorite thing about parties?"}))
                print("  [SENT] text_input")

                response = None
                audio_received = False
                for _ in range(20):  # Wait up to 60s for LLM + TTS
                    try:
                        msg = await asyncio.wait_for(ws.recv(), timeout=3.0)
                        if isinstance(msg, bytes):
                            audio_received = True
                            print(f"  [OK] Audio: received {len(msg):,} bytes")
                            continue
                        data = json.loads(msg)
                        if data.get("type") == "mario_response":
                            response = data.get("text", "")
                            print(f"  [OK] Response: \"{response[:80]}\"")
                            break
                        elif data.get("type") == "mario_thinking":
                            print(f"  [THINKING] {data.get('text', '...')[:50]}")
                        elif data.get("type") == "audio_chunk":
                            pass  # Chunk metadata, audio follows as binary
                    except asyncio.TimeoutError:
                        continue

                if not response:
                    print("  [FAIL] No response to text input!")

                # 3. Send presence_exit
                await ws.send(json.dumps({"type": "presence_exit"}))
                print("  [SENT] presence_exit")

                farewell = None
                for _ in range(15):
                    try:
                        msg = await asyncio.wait_for(ws.recv(), timeout=3.0)
                        if isinstance(msg, bytes):
                            continue  # Skip binary audio frames
                        data = json.loads(msg)
                        if data.get("type") == "mario_response":
                            farewell = data.get("text", "")
                            print(f"  [OK] Farewell: \"{farewell[:80]}\"")
                            break
                    except asyncio.TimeoutError:
                        continue

                if not farewell:
                    print("  [WARN] No farewell (may be delayed)")

                print("  [OK] WebSocket flow complete")

        except Exception as e:
            print(f"  [FAIL] WebSocket error: {e}")

    asyncio.run(ws_test())

def test_memory():
    """Test the memory/speaker database."""
    print("\n=== TEST 7: Memory System ===")
    r = requests.get(f"{SERVER}/health")
    h = r.json()
    visitors = h.get("unique_visitors", 0)
    total = h.get("total_visits", 0)
    print(f"  Unique visitors: {visitors}")
    print(f"  Total visits: {total}")
    print(f"  Party duration: {h.get('party_duration', '?')}")
    print(f"  [OK] Memory system responsive")

def test_response_quality():
    """Test that Mario's responses are fun and in-character."""
    print("\n=== TEST 8: Response Quality ===")
    test_cases = [
        ("Tell me a joke", ["ha", "funny", "laugh", "!"]),
        ("What do you think of Bowser?", ["bowser", "bad", "villain", "turtle", "koopa", "enemy", "fight"]),
        ("I love mushrooms", ["mushroom", "power", "1-up", "grow", "super", "mama", "delicious"]),
        ("Should I wash my hands?", ["wash", "clean", "hands", "yes", "soap", "scrub"]),
        ("What games do you like?", ["game", "play", "mario", "kart", "party", "smash", "adventure"]),
    ]
    passed = 0
    for prompt, expected_keywords in test_cases:
        r = httpx.post("http://localhost:11434/api/generate", json={
            "model": "llama3",
            "prompt": f"You are Mario from Nintendo, the plumber. Stay in character as Mario. Keep response under 30 words. Be fun and energetic. User says: {prompt}",
            "stream": False,
            "options": {"num_predict": 40, "temperature": 0.8}
        }, timeout=30)
        resp = r.json().get("response", "").strip().lower()
        has_keyword = any(kw in resp for kw in expected_keywords)
        status = "PASS" if has_keyword else "WEAK"
        if has_keyword:
            passed += 1
        print(f"  [{status}] Q: \"{prompt}\"")
        print(f"         A: \"{resp[:80]}\"")
    print(f"  Score: {passed}/{len(test_cases)} in-character responses")

if __name__ == "__main__":
    test_health()
    test_cached_tts()
    test_live_tts()
    test_memory()
    test_llm()
    test_response_quality()
    test_full_pipeline()
    test_websocket()
    print("\n=== ALL E2E TESTS COMPLETE ===")
